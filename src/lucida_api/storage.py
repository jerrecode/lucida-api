"""Cross-process SQLite job journal with transactional ownership leases.

A lease is only a crash-recovery signal, not a distributed lock for output files.
The final hard-link publication independently prevents accidental overwrites.
"""
from __future__ import annotations
import sqlite3
import time
from pathlib import Path
from .models import Job, JobState

_RECORD = "id, source, destination, state, transferred, total, error"
_TERMINAL = (JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED, JobState.INTERRUPTED)


class JobOwnershipError(RuntimeError):
    """An attempt to modify a job without holding its current ownership lease."""


class JobStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._connect() as db:
            # Serialize migrations across simultaneous CLI / GUI startup.
            db.execute("BEGIN IMMEDIATE")
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
              id TEXT PRIMARY KEY, source TEXT NOT NULL, destination TEXT NOT NULL,
              state TEXT NOT NULL, transferred INTEGER NOT NULL DEFAULT 0,
              total INTEGER, error TEXT)""")
            # Migration from the original seven-column 0.1.0 database.
            columns = {row[1] for row in db.execute("PRAGMA table_info(jobs)")}
            if "owner" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN owner TEXT")
            if "lease_until" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN lease_until REAL")
            db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_state_lease ON jobs(state, lease_until)")
            db.execute("PRAGMA user_version = 2")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=15)

    def add(self, job: Job) -> None:
        with self._connect() as db:
            db.execute(f"INSERT INTO jobs ({_RECORD}) VALUES(?,?,?,?,?,?,?)", (
                job.id, job.source, job.destination, job.state, job.transferred, job.total, job.error))

    def claim(self, job_id: str, owner: str, lease_seconds: float = 120.0) -> bool:
        """Atomically claim a queued job; only one process can become its owner."""
        if not owner or lease_seconds <= 0:
            raise ValueError("A nonempty owner and positive lease are required")
        with self._connect() as db:
            result = db.execute("""UPDATE jobs SET state=?, owner=?, lease_until=?
                         WHERE id=? AND state=? AND owner IS NULL""",
                         (JobState.RUNNING, owner, time.time() + lease_seconds,
                          job_id, JobState.QUEUED))
            return result.rowcount == 1

    def heartbeat(self, job_id: str, owner: str, lease_seconds: float = 120.0) -> bool:
        """Renew only a running job held by the same owner."""
        with self._connect() as db:
            result = db.execute("""UPDATE jobs SET lease_until=?
                WHERE id=? AND owner=? AND state=?""",
                (time.time() + lease_seconds, job_id, owner, JobState.RUNNING))
            return result.rowcount == 1

    def update_owned(self, job_id: str, owner: str, state: JobState, transferred: int,
                     total: int | None, error: str | None = None,
                     lease_seconds: float = 120.0) -> None:
        """Persist progress only while owned; terminal states release their lease."""
        if transferred < 0 or (total is not None and total < 0):
            raise ValueError("Invalid transfer byte counts")
        terminal = state in _TERMINAL
        with self._connect() as db:
            result = db.execute("""UPDATE jobs SET state=?, transferred=?, total=?, error=?,
                 owner=?, lease_until=? WHERE id=? AND owner=? AND state=?""",
                (state, transferred, total, error,
                 None if terminal else owner,
                 None if terminal else time.time() + lease_seconds,
                 job_id, owner, JobState.RUNNING))
            if result.rowcount != 1:
                raise JobOwnershipError(f"Job ownership lost: {job_id}")

    def requeue(self, job_id: str) -> bool:
        """Atomically move a terminal job back to queued without touching active work."""
        with self._connect() as db:
            result = db.execute("""UPDATE jobs SET state=?, error=NULL
                       WHERE id=? AND state IN (?, ?, ?)
                       AND owner IS NULL""",
                       (JobState.QUEUED, job_id, JobState.FAILED,
                        JobState.CANCELLED, JobState.INTERRUPTED))
            return result.rowcount == 1

    def set_queued_state(self, job_id: str, state: JobState, error: str) -> bool:
        """Mark an unclaimed job cancelled or failed without touching active work."""
        if state not in (JobState.CANCELLED, JobState.FAILED):
            raise ValueError("Only terminal queued transitions are permitted")
        with self._connect() as db:
            return db.execute("""UPDATE jobs SET state=?, error=? WHERE id=?
                      AND state=? AND owner IS NULL""",
                      (state, error, job_id, JobState.QUEUED)).rowcount == 1

    def update(self, id: str, state: JobState, transferred: int, total: int | None,
               error: str | None = None) -> None:
        """Legacy update API. Never overwrite an owned in-progress job."""
        with self._connect() as db:
            result = db.execute("""UPDATE jobs SET state=?, transferred=?, total=?, error=?
                                   WHERE id=? AND owner IS NULL""",
                                (state, transferred, total, error, id))
            if result.rowcount != 1:
                raise JobOwnershipError(f"Cannot update owned or missing job: {id}")

    def get(self, id: str) -> Job | None:
        with self._connect() as db:
            row = db.execute(f"SELECT {_RECORD} FROM jobs WHERE id=?", (id,)).fetchone()
        return Job(*row) if row else None

    def list(self, limit: int = 100) -> list[Job]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self._connect() as db:
            rows = db.execute(f"SELECT {_RECORD} FROM jobs ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
        return [Job(*r) for r in rows]

    def recover_expired(self, now: float | None = None) -> int:
        """Mark leased RUNNING work interrupted only after its heartbeat expires.

        Legacy rows without leases are intentionally excluded; those require the
        explicit manual recovery method to avoid disrupting older live clients.
        """
        if now is None:
            now = time.time()
        with self._connect() as db:
            result = db.execute("""UPDATE jobs SET state=?, error=?, owner=NULL,
                lease_until=NULL WHERE state=? AND lease_until IS NOT NULL
                AND lease_until < ?""", (JobState.INTERRUPTED,
                 "Worker heartbeat expired; output not verified", JobState.RUNNING, now))
            return result.rowcount

    def recover_interrupted(self) -> int:
        """Manual force-recovery; caller must ensure all job owners are stopped."""
        with self._connect() as db:
            result = db.execute("""UPDATE jobs SET state=?, error=?, owner=NULL,
                 lease_until=NULL WHERE state IN (?, ?)""",
                (JobState.INTERRUPTED, "Interrupted before completion; output not verified",
                 JobState.RUNNING, JobState.QUEUED))
            return result.rowcount
