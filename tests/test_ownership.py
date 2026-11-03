"""Persistent DB migration and competing-process lease safety."""
import sqlite3
import time
import pytest
from lucida_api import Config, LucidaClient, JobState
from lucida_api.models import Job
from lucida_api.storage import JobStore, JobOwnershipError


def test_migrates_original_database_and_ownership(tmp_path):
    path = tmp_path / "jobs.db"
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE jobs (id TEXT PRIMARY KEY, source TEXT NOT NULL,
               destination TEXT NOT NULL, state TEXT NOT NULL,
               transferred INTEGER NOT NULL DEFAULT 0, total INTEGER, error TEXT)""")
        db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?)",
                   ("legacy", "sample://tone", "old.wav", "queued", 0, None, None))
    first = JobStore(path)
    second = JobStore(path)
    assert first.get("legacy").state == JobState.QUEUED
    assert first.claim("legacy", "owner-1")
    assert not second.claim("legacy", "owner-2")
    with pytest.raises(JobOwnershipError):
        second.update_owned("legacy", "owner-2", JobState.COMPLETED, 1, 1)
    assert second.get("legacy").state == JobState.RUNNING
    assert first.heartbeat("legacy", "owner-1")
    assert first.recover_expired(now=time.time() - 10) == 0
    first.update_owned("legacy", "owner-1", JobState.COMPLETED, 7, 7)
    assert second.get("legacy").state == JobState.COMPLETED
    assert not first.heartbeat("legacy", "owner-1")
    with sqlite3.connect(path) as db:
        columns = {row[1] for row in db.execute("PRAGMA table_info(jobs)")}
        assert {"owner", "lease_until"} <= columns
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2


def test_expire_only_stale_leases(tmp_path):
    store = JobStore(tmp_path / "jobs.db")
    store.add(Job("stale", "sample://tone", "stale.wav", JobState.QUEUED))
    store.add(Job("fresh", "sample://tone", "fresh.wav", JobState.QUEUED))
    store.add(Job("old", "sample://tone", "old.wav", JobState.RUNNING))
    assert store.claim("stale", "owner-a", lease_seconds=5)
    assert store.claim("fresh", "owner-b", lease_seconds=300)
    assert store.recover_expired(now=time.time() + 10) == 1
    assert store.get("stale").state == JobState.INTERRUPTED
    assert store.get("fresh").state == JobState.RUNNING
    assert store.get("old").state == JobState.RUNNING  # no lease on legacy rows
    with pytest.raises(JobOwnershipError):
        store.update_owned("stale", "owner-a", JobState.COMPLETED, 1, 1)
    assert store.heartbeat("fresh", "owner-b")
    assert store.recover_expired(now=time.time() + 100) == 0


def test_completed_sdk_job_releases_lease(tmp_path):
    import asyncio
    cfg = Config(state_dir=tmp_path / "state", output_dir=tmp_path / "output")
    first = LucidaClient(cfg)
    result = asyncio.run(first.acquire("sample://tone"))
    with sqlite3.connect(first.store.path) as db:
        owner, expiration = db.execute("SELECT owner, lease_until FROM jobs WHERE id=?",
                                       (result.id,)).fetchone()
    assert result.state == JobState.COMPLETED
    assert owner is None and expiration is None
    assert LucidaClient(cfg).store.recover_expired() == 0


def test_simultaneous_database_migration(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    path = tmp_path / "same.sqlite3"
    with ThreadPoolExecutor(max_workers=8) as pool:
        stores = list(pool.map(JobStore, [path] * 24))
    assert len(stores) == 24
    assert stores[-1].list() == []
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2
