"""Cross-platform application storage and explicit network trust policy."""
from __future__ import annotations
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


def app_data_dir() -> Path:
    override = os.environ.get("LUCIDA_HOME")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "Lucida"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / "lucida"


def default_output_dir() -> Path:
    return Path(os.environ.get("LUCIDA_OUTPUT_DIR", str(Path.home() / "Music" / "Lucida"))).expanduser()


@dataclass(frozen=True, slots=True)
class Config:
    state_dir: Path = field(default_factory=app_data_dir)
    output_dir: Path = field(default_factory=default_output_dir)
    allowed_hosts: tuple[str, ...] = ()
    allow_private: bool = False  # only for local isolated test servers
    max_bytes: int = 256 * 1024 * 1024
    max_concurrent: int = 2
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.max_bytes <= 0 or self.max_concurrent < 1 or self.timeout_seconds <= 0:
            raise ValueError("Invalid resource limits")
        if any(not h or "/" in h or ":" in h for h in self.allowed_hosts):
            raise ValueError("allowed_hosts must contain plain DNS names/IPs")
