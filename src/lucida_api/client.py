"""Async SDK. One journal and one filesystem workflow for all frontends."""
from __future__ import annotations
import asyncio
import math
import os
import re
import struct
import uuid
import wave
from pathlib import Path
from collections.abc import Callable
import httpx
from .config import Config
from .models import (API_VERSION, SCHEMA_VERSION, CapabilityUnavailable,
                     FileConflict, Job, JobState, TransferError)
from .providers import DirectMediaProvider, ProviderRegistry, SampleProvider
from .security import check_source
from .storage import JobStore

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
        self.registry = ProviderRegistry()
        self.registry.register(SampleProvider())
        self.registry.register(DirectMediaProvider())
        self._limit = asyncio.Semaphore(self.config.max_concurrent)

    def version(self) -> dict[str, str | int]:
        return {"api": API_VERSION, "schema": SCHEMA_VERSION}

    def providers(self) -> list[dict]:
        return [p.to_dict() for p in self.registry.capabilities()]

    def jobs(self, limit: int = 100) -> list[Job]:
        return self.store.list(limit)

    async def acquire(self, source: str, filename: str | None = None,
                      progress: ProgressCallback | None = None) -> Job:
        provider = self.registry.resolve(source)
        if provider is None:
            raise CapabilityUnavailable("No verified acquisition provider for this source")
        if isinstance(provider, DirectMediaProvider):
            await check_source(source, self.config.allowed_hosts, self.config.allow_private)
        dest = self.config.output_dir / safe_filename(filename or ("sample-tone.wav" if isinstance(provider, SampleProvider) else "download.audio"))
        if dest.exists() or dest.is_symlink():
            raise FileConflict(f"File already exists: {dest}")
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        job = Job(str(uuid.uuid4()), source, str(dest), JobState.QUEUED)
        await asyncio.to_thread(self.store.add, job)
        transferred = 0
        total = None
        part = dest.with_name(f".{dest.name}.{job.id}.part")
        def report(state: JobState, error: str | None = None) -> Job:
            updated = Job(job.id, source, str(dest), state, transferred, total, error)
            self.store.update(job.id, state, transferred, total, error)
            if progress:
                progress(updated)
            return updated
        async with self._limit:
            try:
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
                    # Reuse a connection pool within the job; fail closed on redirects/HTML.
                    async with httpx.AsyncClient(timeout=self.config.timeout_seconds,
                                                 follow_redirects=False, trust_env=False) as http:
                        async with http.stream("GET", source) as response:
                            if response.status_code != 200:
                                raise TransferError(f"HTTP {response.status_code}; redirects not followed")
                            mime = response.headers.get("content-type", "").split(";", 1)[0].lower().strip()
                            if not (mime.startswith("audio/") or mime in ("application/ogg", "application/octet-stream")):
                                raise TransferError(f"Refusing unexpected MIME type: {mime or 'unknown'}")
                            content_length = response.headers.get("content-length")
                            if content_length:
                                try:
                                    total = int(content_length)
                                except ValueError as exc:
                                    raise TransferError("Invalid content length") from exc
                                if total < 0 or total > self.config.max_bytes:
                                    raise TransferError("Remote file exceeds configured size limit")
                            with part.open("xb") as file:
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
                # Hard-link publication creates destination only if absent: no silent overwrite.
                await asyncio.to_thread(os.link, part, dest)
                await asyncio.to_thread(part.unlink)
                return report(JobState.COMPLETED)
            except asyncio.CancelledError:
                report(JobState.CANCELLED, "Cancelled by caller")
                raise
            except Exception as exc:
                report(JobState.FAILED, f"{type(exc).__name__}: {exc}")
                if isinstance(exc, httpx.HTTPError):
                    raise TransferError(f"Network transfer failed: {exc}") from exc
                raise
            finally:
                # Failed partial files remain for inspection, never confused with completed outputs.
                pass
