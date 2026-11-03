"""File integrity constraints are checked before final publication."""
import asyncio
import hashlib
from pathlib import Path
import pytest
from lucida_api import Config, LucidaClient, JobState, TransferError


def test_integrity_accepted_and_rejected(tmp_path):
    cfg = Config(state_dir=tmp_path / "state", output_dir=tmp_path / "media")
    client = LucidaClient(cfg)
    good = asyncio.run(client.acquire("sample://tone", "good.wav"))
    digest = hashlib.sha256(Path(good.destination).read_bytes()).hexdigest()
    checked = asyncio.run(client.acquire("sample://tone", "verified.wav", expected_sha256=digest))
    assert checked.state == JobState.COMPLETED
    with pytest.raises(TransferError, match="SHA-256 mismatch"):
        asyncio.run(client.acquire("sample://tone", "bad.wav", expected_sha256="0" * 64))
    assert not (cfg.output_dir / "bad.wav").exists()
    assert client.jobs()[0].state == JobState.FAILED
    with pytest.raises(ValueError, match="64 hexadecimal"):
        asyncio.run(client.acquire("sample://tone", "invalid.wav", expected_sha256="abc"))
    assert not (cfg.output_dir / "invalid.wav").exists()
