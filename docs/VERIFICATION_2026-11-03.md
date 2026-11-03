# Verification record: 2026-11-03 (incremental)

## Local results

From `/mnt/data/lucida-dev` under Python 3.13:

```sh
PYTHONPATH=lucida-api/src:lucida-cli/src:lucida-gui/src python -m pytest -q lucida-api/tests lucida-cli/tests lucida-gui/tests
```

**29 passed, 1 skipped** (PySide6 unavailable locally). The five original lifecycle/CLI tests cover bounded background submission and wait, queued cancellation, new-job retry, HTTP job ID lookup and terminal conflict semantics, CLI bounded batch ordering and partial failure, and CLI retry. Existing tests continue to pass. Four additional tests cover legacy SQLite schema migration, exclusive cross-process lease ownership, stale-lease-only recovery, owner release after completion, and parallel database initialization.

## Caveats

- GUI changes compile but have not been physically tested in a visible desktop; GitHub CI still required for this revision.
- SDK cancellations affect tasks within one client instance only; they cannot control processes remotely. GUI worker cancellation propagates to its thread-owned asyncio event loop.
- New leased jobs use automatic expiry detection and heartbeat renewal; old unleased jobs still require explicit manual recovery. There is no automatic cross-process queue relaunch. A retry starts from byte 0; `.part` artifacts from prior failures are retained for inspection.
- No real Lucida provider, HTTP byte-range resume, artwork, audio conversion or packaged native executable is claimed.

This file is a local verification record; cross-platform CI outcomes must be appended only after GitHub reports them.

## Second development slice: partial resume and safe publication

A deterministic local HTTP server truncated a transfer with a strong ETag. Resumption sent `Range` and `If-Range` and verified the reconstructed file byte for byte. A simulated changed entity returned HTTP 200 and was rejected without modifying the old partial. Additional tests verify SHA-256 rejection, Linux atomic rename fallback and existing-file preservation. The CLI `resume`, `--sha256`, and GUI buttons were implemented locally; Windows and Qt CI checks are required before claiming cross-platform verification for these new changes.

Installer smoke runs succeeded for all three repositories on the 2026-11-03 GitHub Actions Windows and Ubuntu matrices before this second slice.
