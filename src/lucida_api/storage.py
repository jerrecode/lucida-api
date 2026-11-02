"""SQLite job journal; transactions use independent connections for thread safety."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from .models import Job, JobState

class JobStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
              id TEXT PRIMARY KEY, source TEXT NOT NULL, destination TEXT NOT NULL,
              state TEXT NOT NULL, transferred INTEGER NOT NULL DEFAULT 0,
              total INTEGER, error TEXT)""")


    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=15)

    def add(self, job: Job) -> None:
        with self._connect() as db:
            db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?)", (
                job.id, job.source, job.destination, job.state, job.transferred, job.total, job.error))

    def update(self, id: str, state: JobState, transferred: int, total: int | None,
               error: str | None = None) -> None:
        with self._connect() as db:
            db.execute("UPDATE jobs SET state=?,transferred=?,total=?,error=? WHERE id=?",
                       (state, transferred, total, error, id))

    def get(self, id: str) -> Job | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (id,)).fetchone()
        return Job(*row) if row else None

    def list(self, limit: int = 100) -> list[Job]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self._connect() as db:
            rows = db.execute("SELECT * FROM jobs ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
        return [Job(*r) for r in rows]

    def recover_interrupted(self) -> int:
        """Mark incomplete jobs interrupted. ONLY call with all job owners stopped.

        Another client or process may be actively processing shared journal rows.
        Automatically running this on every connection would corrupt live state.
        """
        with self._connect() as db:
            cursor = db.execute("UPDATE jobs SET state=?, error=? WHERE state IN (?, ?)",
                (JobState.INTERRUPTED, "Interrupted before completion; output not verified",
                 JobState.RUNNING, JobState.QUEUED))
            return cursor.rowcount
