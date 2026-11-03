"""Atomic no-replace finalization and fallback on non-hardlink filesystems."""
import errno
from pathlib import Path
import pytest
from lucida_api import FileConflict
from lucida_api.filesystem import publish_no_replace
import lucida_api.filesystem as fs


def test_no_overwrite_existing_destination(tmp_path):
    partial = tmp_path / "temporary.part"
    destination = tmp_path / "final.wav"
    partial.write_bytes(b"new")
    destination.write_bytes(b"original")
    with pytest.raises(FileConflict):
        publish_no_replace(partial, destination)
    assert destination.read_bytes() == b"original"
    assert partial.read_bytes() == b"new"


def test_fallback_atomic_no_replace(tmp_path, monkeypatch):
    partial = tmp_path / "temporary.part"
    destination = tmp_path / "final.wav"
    partial.write_bytes(b"valid")
    def cannot_link(*_):
        raise OSError(errno.EPERM, "No hardlinks")
    monkeypatch.setattr(fs.os, "link", cannot_link)
    publish_no_replace(partial, destination)
    assert destination.read_bytes() == b"valid"
    assert not partial.exists()
    second = tmp_path / "another.part"
    second.write_bytes(b"not allowed")
    with pytest.raises(FileConflict):
        publish_no_replace(second, destination)
    assert destination.read_bytes() == b"valid"
    assert second.read_bytes() == b"not allowed"
