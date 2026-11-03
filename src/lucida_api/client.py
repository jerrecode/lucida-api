"""Async SDK. One journal and one filesystem workflow for all frontends."""
from __future__ import annotations
import asyncio
import math
import hashlib
import os
import re
import stat
import time
import struct
import uuid
import wave
from pathlib import Path
from collections.abc import Callable
import httpx
from .checkpoint import read_checkpoint, write_checkpoint, manifest_path, strong_etag
from .filesystem import publish_no_replace
from .config import Config
from .models import (API_VERSION, SCHEMA_VERSION, CapabilityUnavailable,
                     FileConflict, Job, JobState, TrackInfo, TransferError)
from .providers import DirectMediaProvider, MusicBrainzProvider, ProviderRegistry, SampleProvider
from .security import check_source
from .storage import JobStore, JobOwnershipError

ProgressCallback = Callable[[Job], None]


def safe_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    if not name or name.split('.')[0].upper() in {
        "CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))
    }:
        name = "file_" + name
    return name[:180].rstrip(" .") or "download"


class LucidaClient:
    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self.store = JobStore(self.config.state_dir / "jobs.sqlite3")
        # Leases expire only after a worker fails to heartbeat for two minutes.
        self.store.recover_expired()
        self._owner = uuid.uuid4().hex
        self._lease_seconds = 120.0
        self.registry = ProviderRegistry()
        self.registry.register(SampleProvider())
        self.registry.register(DirectMediaProvider())
        self.registry.register(MusicBrainzProvider())
        self._search_lock = asyncio.Lock()
        self._last_search_at = 0.0
        self._limit = asyncio.Semaphore(self.config.max_concurrent)
        self._active: dict[str, asyncio.Task[Job]] = {}

    def version(self) -> dict[str, str | int]:
        return {"api": API_VERSION, "schema": SCHEMA_VERSION}

    def providers(self) -> list[dict]:
        return [p.to_dict() for p in self.registry.capabilities()]

    def recover_interrupted(self, *, confirm_no_active_workers: bool = False) -> int:
        """Explicit recovery, dangerous if any CLI/GUI/service workers remain active."""
        if not confirm_no_active_workers:
            raise ValueError("Stop all Lucida applications first; then pass confirm_no_active_workers=True")
        return self.store.recover_interrupted()

    def jobs(self, limit: int = 100) -> list[Job]:
        return self.store.list(limit)

    async def search(self, query: str, limit: int = 10,
                     transport: httpx.AsyncBaseTransport | None = None) -> list[TrackInfo]:
        """Search MusicBrainz recording metadata, never audio/download links.

        The optional transport is for deterministic integration testing.
        Rate limiting is per client, not global across independent processes.
        """
        if not query.strip() or len(query) > 256 or not 1 <= limit <= 20:
            raise ValueError("Search requires 1..256 query chars and 1..20 results")
        async with self._search_lock:
            gap = time.monotonic() - self._last_search_at
            if gap < 1.1:
                await asyncio.sleep(1.1 - gap)
            self._last_search_at = time.monotonic()
        try:
            async with httpx.AsyncClient(
                transport=transport, timeout=self.config.timeout_seconds,
                follow_redirects=False, trust_env=False,
                headers={"User-Agent": "LucidaCore/0.1.0 (https://github.com/jerrecode/lucida-api)",
                         "Accept": "application/json"},
            ) as http:
                response = await http.get("https://musicbrainz.org/ws/2/recording/",
                                          params={"query": query, "fmt": "json", "limit": limit})
                if response.status_code != 200:
                    raise CapabilityUnavailable(f"MusicBrainz search unavailable (HTTP {response.status_code})")
                if len(response.content) > 2_000_000:
                    raise TransferError("Metadata response too large")
                payload = response.json()
                recordings = payload.get("recordings", []) if isinstance(payload, dict) else []
                if not isinstance(recordings, list):
                    raise TransferError("Invalid metadata response")
                results = []
                for record in recordings[:limit]:
                    if not isinstance(record, dict) or not isinstance(record.get("id"), str):
                        continue
                    credits = record.get("artist-credit", [])
                    artist = "".join(
                        item.get("name", "") if isinstance(item, dict) else item
                        for item in credits if isinstance(item, (dict, str))) if isinstance(credits, list) else ""
                    results.append(TrackInfo(id=record["id"], title=str(record.get("title", "")),
                        artist=artist, provider="musicbrainz",
                        duration_ms=record.get("length") if isinstance(record.get("length"), int) else None,
                        score=record.get("score") if isinstance(record.get("score"), int) else None))
                return results
        except httpx.HTTPError as exc:
            raise CapabilityUnavailable(f"MusicBrainz request failed: {exc}") from exc
        except (ValueError, TypeError) as exc:
            raise TransferError("Unable to parse MusicBrainz metadata") from exc

    async def _prepare_job(self, source: str, filename: str | None) -> tuple[Job, object]:
        provider = self.registry.resolve(source)
        if provider is None:
            raise CapabilityUnavailable("No verified acquisition provider for this source")
        if isinstance(provider, DirectMediaProvider):
            await check_source(source, self.config.allowed_hosts, self.config.allow_private)
        basename = safe_filename(filename or (
            "sample-tone.wav" if isinstance(provider, SampleProvider) else "download.audio"))
        dest = self.config.output_dir / basename
        if dest.exists() or dest.is_symlink():
            raise FileConflict(f"File already exists: {dest}")
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        job = Job(str(uuid.uuid4()), source, str(dest), JobState.QUEUED)
        await asyncio.to_thread(self.store.add, job)
        return job, provider

    async def acquire(self, source: str, filename: str | None = None,
                      progress: ProgressCallback | None = None,
                      expected_sha256: str | None = None) -> Job:
        """Acquire one source, optionally verifying SHA-256 before publication."""
        self._check_hash(expected_sha256)
        job, provider = await self._prepare_job(source, filename)
        return await self._run_job(job, provider, progress, expected_sha256=expected_sha256)

    async def submit(self, source: str, filename: str | None = None,
                     progress: ProgressCallback | None = None,
                     expected_sha256: str | None = None) -> str:
        """Start an in-process background job and return its persistent identifier.

        The owning event loop must remain alive. Jobs are not run after process exit.
        """
        self._check_hash(expected_sha256)
        job, provider = await self._prepare_job(source, filename)
        task = asyncio.create_task(self._run_job(job, provider, progress,
                                                 expected_sha256=expected_sha256))
        self._active[job.id] = task
        def completed(finished: asyncio.Task[Job]) -> None:
            self._active.pop(job.id, None)
            if not finished.cancelled():
                finished.exception()  # consume logged failure: journal retains details
        task.add_done_callback(completed)
        return job.id

    async def wait(self, job_id: str) -> Job:
        """Wait on a job started by this client; return its persisted final state."""
        task = self._active.get(job_id)
        if task is not None:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass  # the recorded job state is the result of interest
        result = await asyncio.to_thread(self.store.get, job_id)
        if result is None:
            raise ValueError(f"Unknown job ID: {job_id}")
        return result

    async def cancel(self, job_id: str) -> bool:
        """Cancel an in-process submitted job; never manipulate another process."""
        task = self._active.get(job_id)
        if task is None or task.done():
            return False
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
        return True

    async def shutdown(self) -> None:
        """Cancel and await all background jobs owned by this client."""
        tasks = list(self._active.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def retry(self, job_id: str, progress: ProgressCallback | None = None,
                    expected_sha256: str | None = None) -> Job:
        """Retry a terminal failed job from scratch, never claiming HTTP resume."""
        previous = await asyncio.to_thread(self.store.get, job_id)
        if previous is None:
            raise ValueError(f"Unknown job ID: {job_id}")
        if previous.state not in (JobState.FAILED, JobState.CANCELLED, JobState.INTERRUPTED):
            raise ValueError("Only failed, cancelled and interrupted jobs can be retried")
        original = Path(previous.destination)
        if original.parent.resolve() != self.config.output_dir.resolve():
            raise ValueError("Retry requires the original output directory")
        return await self.acquire(previous.source, original.name, progress,
                                  expected_sha256=expected_sha256)

    async def resume(self, job_id: str, progress: ProgressCallback | None = None,
                     expected_sha256: str | None = None) -> Job:
        """Resume an existing partial only when the server provides a strong ETag.

        Requires RFC 9110 compliant Range and If-Range. A changed source fails
        without modifying the previous partial; call retry() to start over.
        """
        self._check_hash(expected_sha256)
        previous = await asyncio.to_thread(self.store.get, job_id)
        if previous is None:
            raise ValueError(f"Unknown job ID: {job_id}")
        if previous.state not in (JobState.FAILED, JobState.CANCELLED, JobState.INTERRUPTED):
            raise ValueError("Only failed, cancelled and interrupted jobs can resume")
        provider = self.registry.resolve(previous.source)
        if not isinstance(provider, DirectMediaProvider):
            raise CapabilityUnavailable("Resuming this provider type is unsupported")
        await check_source(previous.source, self.config.allowed_hosts, self.config.allow_private)
        destination = Path(previous.destination)
        if destination.parent.resolve() != self.config.output_dir.resolve():
            raise ValueError("Resume requires the original output directory")
        if destination.exists() or destination.is_symlink():
            raise FileConflict(f"Destination already exists: {destination}")
        part = destination.with_name(f".{destination.name}.{job_id}.part")
        read_checkpoint(part, previous.source, self.config.max_bytes)
        if not await asyncio.to_thread(self.store.requeue, job_id):
            raise TransferError("Job was already claimed by another worker")
        return await self._run_job(previous, provider, progress, resume=True,
                                   expected_sha256=expected_sha256)

    @staticmethod
    def _check_hash(expected: str | None) -> None:
        if expected is not None and re.fullmatch(r"[0-9a-fA-F]{64}", expected) is None:
            raise ValueError("Expected SHA-256 must contain exactly 64 hexadecimal digits")

    async def _run_job(self, job: Job, provider: object,
                       progress: ProgressCallback | None = None,
                       resume: bool = False,
                       expected_sha256: str | None = None) -> Job:
        dest = Path(job.destination)
        transferred = 0
        total = None
        part = dest.with_name(f".{dest.name}.{job.id}.part")
        claimed = False
        heartbeat_task: asyncio.Task | None = None
        def report(state: JobState, error: str | None = None) -> Job:
            updated = Job(job.id, job.source, str(dest), state, transferred, total, error)
            if claimed:
                self.store.update_owned(job.id, self._owner, state, transferred, total, error,
                                        self._lease_seconds)
            else:
                self.store.set_queued_state(job.id, state, error or "Cancelled before start")
            if progress:
                progress(updated)
            return updated
        try:
            async with self._limit:
                if not await asyncio.to_thread(self.store.claim, job.id, self._owner,
                                               self._lease_seconds):
                    raise JobOwnershipError(f"Unable to claim queued job: {job.id}")
                claimed = True
                runner = asyncio.current_task()
                async def maintain_lease():
                    while True:
                        await asyncio.sleep(20)
                        if not await asyncio.to_thread(self.store.heartbeat, job.id,
                                                       self._owner, self._lease_seconds):
                            if runner is not None:
                                runner.cancel()
                            return
                heartbeat_task = asyncio.create_task(maintain_lease())
                report(JobState.RUNNING)
                if isinstance(provider, SampleProvider):
                    def write_sample() -> int:
                        with wave.open(str(part), "wb") as wav:
                            wav.setnchannels(1)
                            wav.setsampwidth(2)
                            wav.setframerate(8000)
                            pcm = b"".join(struct.pack("<h", int(5000 * math.sin(2 * math.pi * 220 * i / 8000))) for i in range(8000))
                            wav.writeframes(pcm)
                        return part.stat().st_size
                    transferred = await asyncio.to_thread(write_sample)
                    total = transferred
                    report(JobState.RUNNING)
                else:
                    headers = {}
                    if resume:
                        transferred, etag, known_total = read_checkpoint(
                            part, job.source, self.config.max_bytes)
                        headers = {"Range": f"bytes={transferred}-", "If-Range": etag}
                    async with httpx.AsyncClient(timeout=self.config.timeout_seconds,
                                                 follow_redirects=False, trust_env=False) as http:
                        async with http.stream("GET", job.source, headers=headers) as response:
                            if response.status_code != (206 if resume else 200):
                                raise TransferError(
                                    f"HTTP {response.status_code}; " +
                                    ("safe resumption refused, retry from scratch" if resume else "redirects not followed"))
                            mime = response.headers.get("content-type", "").split(";", 1)[0].lower().strip()
                            if not (mime.startswith("audio/") or mime in ("application/ogg", "application/octet-stream")):
                                raise TransferError(f"Refusing unexpected MIME type: {mime or 'unknown'}")
                            content_length = response.headers.get("content-length")
                            length = None
                            if content_length is not None:
                                try:
                                    length = int(content_length)
                                except ValueError as exc:
                                    raise TransferError("Invalid content length") from exc
                                if length < 0 or length > self.config.max_bytes:
                                    raise TransferError("Remote file exceeds configured size limit")
                            if resume:
                                # The server must honor both byte offset and original ETag.
                                if response.headers.get("etag") != etag:
                                    raise TransferError("Source ETag changed during resume")
                                header = response.headers.get("content-range", "")
                                match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", header)
                                if not match:
                                    raise TransferError("Missing or invalid Content-Range")
                                start, end, whole = map(int, match.groups())
                                if start != transferred or end < start or whole != end + 1 or whole > self.config.max_bytes:
                                    raise TransferError("Content-Range contradicts partial file")
                                if known_total is not None and whole != known_total:
                                    raise TransferError("Remote length changed since original transfer")
                                if length is not None and length != end - start + 1:
                                    raise TransferError("Content-Length contradicts Content-Range")
                                total = whole
                                flags = os.O_WRONLY | os.O_APPEND | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
                                fd = os.open(part, flags)
                                try:
                                    st = os.fstat(fd)
                                    if not stat.S_ISREG(st.st_mode) or st.st_size != transferred:
                                        raise TransferError("Partial file changed during resume")
                                    file = os.fdopen(fd, "ab")
                                    fd = -1
                                finally:
                                    if fd != -1:
                                        os.close(fd)
                            else:
                                total = length
                                fresh_etag = strong_etag(response.headers.get("etag"))
                                if fresh_etag:
                                    write_checkpoint(part, job.source, fresh_etag, total)
                                file = part.open("xb")
                            with file:
                                report(JobState.RUNNING)
                                async for chunk in response.aiter_bytes(chunk_size=262144):
                                    transferred += len(chunk)
                                    if transferred > self.config.max_bytes:
                                        raise TransferError("Transfer exceeds configured size limit")
                                    await asyncio.to_thread(file.write, chunk)
                                    report(JobState.RUNNING)
                                await asyncio.to_thread(file.flush)
                                await asyncio.to_thread(os.fsync, file.fileno())
                            if transferred == 0:
                                raise TransferError("Empty download is not a usable audio file")
                            if total is not None and total != transferred:
                                raise TransferError("Truncated transfer; length mismatch")
                # The checksum covers the actual bytes written, including any
                # validated resumed prefix, not just the last HTTP response.
                if expected_sha256 is not None:
                    def digest() -> str:
                        with part.open("rb") as src:
                            return hashlib.file_digest(src, "sha256").hexdigest()
                    actual = await asyncio.to_thread(digest)
                    if actual.lower() != expected_sha256.lower():
                        raise TransferError("SHA-256 mismatch; output not published")
                # Publish only if absent, and only after full stream verification.
                await asyncio.to_thread(publish_no_replace, part, dest)
                completed = report(JobState.COMPLETED)
                # Publication is complete. Cleanup errors must not mark a valid
                # published file as failed or invite an unsafe duplicate retry.
                try:
                    part.unlink(missing_ok=True)
                except OSError:
                    pass
                try:
                    manifest_path(part).unlink(missing_ok=True)
                except OSError:
                    pass
                return completed
        except asyncio.CancelledError:
            try:
                report(JobState.CANCELLED, "Cancelled by caller")
            except JobOwnershipError:
                # Recovery may have reclaimed an expired job: never overwrite it.
                pass
            raise
        except Exception as exc:
            # If ownership was lost, avoid clobbering another worker's state.
            if not isinstance(exc, JobOwnershipError):
                report(JobState.FAILED, f"{type(exc).__name__}: {exc}")
            if isinstance(exc, httpx.HTTPError):
                raise TransferError(f"Network transfer failed: {exc}") from exc
            raise
        finally:
            if heartbeat_task is not None:
                heartbeat_task.cancel()
                await asyncio.gather(heartbeat_task, return_exceptions=True)
