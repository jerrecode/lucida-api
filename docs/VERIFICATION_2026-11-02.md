# Verification record: 2026-11-02

Status: verified development preview, not production ready.

## Local verification

`PYTHONPATH=lucida-api/src:lucida-cli/src:lucida-gui/src pytest -q lucida-api/tests lucida-cli/tests lucida-gui/tests`

Result: **12 passed, 1 skipped** (PySide6 unavailable locally). Tests cover offline WAV generation and decoding, trusted local HTTP streaming, MIME rejection, no-overwrite behavior, SQLite persistence and explicit job recovery, MusicBrainz metadata contract via mock HTTP, FastAPI ASGI endpoints, and CLI operations.

All three wheels were built locally using `python -m pip wheel --no-deps --no-build-isolation .` and installed as wheels in an isolated smoke-test virtual environment using preinstalled dependency packages. This does not establish clean internet installation success.

## GitHub Actions

All **12 jobs passed**, covering Ubuntu and Windows with Python 3.11 and 3.13, dependency consistency, compilation, automated tests and wheel packaging:

- API: https://github.com/jerrecode/lucida-api/actions/runs/41453647381
- CLI: https://github.com/jerrecode/lucida-cli/actions/runs/41453667417
- GUI: https://github.com/jerrecode/lucida-gui/actions/runs/41453683660

GUI CI genuinely creates and closes a Qt window with the offscreen platform plugin. Earlier failures due to missing libEGL.so.1 and unsafe QObject teardown were repaired. This is **not** a visually tested desktop application.

## Release blockers

- lucida.to could not be directly inspected successfully (HTTP 403); Lucida music-provider acquisition is not implemented or verified.
- MusicBrainz uses its documented API, tested with deterministic mock responses; no live integration success is claimed.
- Windows PowerShell and Linux Bash install scripts have not been tested in clean end-user environments.
- No packaged standalone Windows executable, graphical real-device usability tests, durable cross-process job leasing, safe resume, broad playlist support, complete cancellation/retry controls, or transcoding.
- Direct trusted HTTP transfer is a separate authorized-source feature, not a substitute for Lucida upstream parity.

Next milestone: durable cross-process leases and bounded queue/cancellation, then clean Linux/Windows installer validation and authorized real-provider adapters.
