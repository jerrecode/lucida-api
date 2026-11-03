"""Strict ETag-backed partial-transfer checkpoint handling (no weak validators)."""
from __future__ import annotations
import hashlib
import json
import os
import uuid
from pathlib import Path
from .models import TransferError


def manifest_path(part: Path) -> Path:
    return part.with_name(part.name + ".checkpoint.json")


def strong_etag(value: str | None) -> str | None:
    """Accept bounded strong HTTP entity-tags only; weak tags cannot prove identity."""
    if value is None or not 3 <= len(value) <= 256 or value.startswith("W/"):
        return None
    if value[0] != '"' or value[-1] != '"':
        return None
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        return None
    return value


def write_checkpoint(part: Path, source: str, etag: str, total: int | None) -> None:
    if strong_etag(etag) is None:
        raise TransferError("Cannot checkpoint without a strong ETag")
    data = {"version": 1, "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "etag": etag, "total": total}
    target = manifest_path(part)
    temporary = target.with_name(target.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as out:
            json.dump(data, out, separators=(",", ":"))
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def read_checkpoint(part: Path, source: str, maximum: int) -> tuple[int, str, int | None]:
    checkpoint = manifest_path(part)
    if not part.is_file() or part.is_symlink() or not checkpoint.is_file() or checkpoint.is_symlink():
        raise TransferError("No safely resumable partial file and checkpoint")
    if checkpoint.stat().st_size > 2048:
        raise TransferError("Checkpoint exceeds safe size")
    try:
        data = json.loads(checkpoint.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise TransferError("Invalid partial-download checkpoint") from exc
    if not isinstance(data, dict) or data.get("version") != 1:
        raise TransferError("Unsupported checkpoint format")
    if data.get("source_sha256") != hashlib.sha256(source.encode()).hexdigest():
        raise TransferError("Checkpoint belongs to a different source")
    etag = strong_etag(data.get("etag") if isinstance(data.get("etag"), str) else None)
    if etag is None:
        raise TransferError("Unsafe checkpoint without a strong ETag")
    total = data.get("total")
    if total is not None and (type(total) is not int or not 0 < total <= maximum):
        raise TransferError("Invalid checkpoint total")
    offset = part.stat().st_size
    if not 0 < offset < maximum or (total is not None and offset >= total):
        raise TransferError("Partial file length cannot be resumed")
    return offset, etag, total
