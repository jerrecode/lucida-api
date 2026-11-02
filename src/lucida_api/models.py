"""Shared data contracts. Public schema version 1."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

API_VERSION = "0.1.0"
SCHEMA_VERSION = 1

class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"

@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    name: str
    search: bool = False
    metadata: bool = False
    acquisition: bool = False
    formats: tuple[str, ...] = ()
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True, slots=True)
class Job:
    id: str
    source: str
    destination: str
    state: str
    transferred: int = 0
    total: int | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

class LucidaError(Exception):
    code = "lucida_error"

class CapabilityUnavailable(LucidaError):
    code = "capability_unavailable"

class UnsafeSource(LucidaError):
    code = "unsafe_source"

class FileConflict(LucidaError):
    code = "file_conflict"

class TransferError(LucidaError):
    code = "transfer_error"
