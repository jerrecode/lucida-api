"""No-clobber publication with a same-directory atomic fallback.

Hard links work on most desktop filesystems. Linux RENAME_NOREPLACE and
Windows' non-replacing rename semantics cover some filesystems without links.
Unsupported filesystems fail closed, keeping the partial file for recovery.
"""
from __future__ import annotations
import ctypes
import errno
import os
import sys
from pathlib import Path
from .models import FileConflict

_RENAME_FALLBACK = {errno.EPERM, errno.EACCES, errno.ENOTSUP, errno.EOPNOTSUPP,
                    errno.EMLINK, errno.ENOSYS}


def publish_no_replace(part: Path, destination: Path) -> None:
    """Make a complete partial file visible at destination, never replacing existing data.

    The caller must place `part` and `destination` in the same directory and
    fsync the partial file first. Publication is atomic only where the
    underlying filesystem supports the selected operation.
    """
    if part.parent != destination.parent:
        raise ValueError("Publication requires the same destination directory")
    try:
        os.link(part, destination)
        return
    except FileExistsError as exc:
        raise FileConflict(f"Destination already exists: {destination}") from exc
    except OSError as exc:
        if exc.errno not in _RENAME_FALLBACK:
            raise

    try:
        if os.name == "nt":
            # os.rename on Windows fails if the destination already exists.
            os.rename(part, destination)
        elif sys.platform.startswith("linux"):
            libc = ctypes.CDLL(None, use_errno=True)
            renameat2 = getattr(libc, "renameat2", None)
            if renameat2 is None:
                raise OSError(errno.ENOSYS, "Atomic no-replace rename unavailable")
            renameat2.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                                  ctypes.c_char_p, ctypes.c_uint)
            renameat2.restype = ctypes.c_int
            at_fdcwd, rename_noreplace = -100, 1
            result = renameat2(at_fdcwd, os.fsencode(part), at_fdcwd,
                               os.fsencode(destination), rename_noreplace)
            if result != 0:
                err = ctypes.get_errno()
                raise OSError(err, os.strerror(err))
        else:
            raise OSError(errno.ENOTSUP, "Atomic no-replace rename unavailable")
    except FileExistsError as exc:
        raise FileConflict(f"Destination already exists: {destination}") from exc
