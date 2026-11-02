# Lucida API Core (0.1.0, development preview)

Reusable Python 3.11+ backend for the coordinated [Lucida CLI](https://github.com/jerrecode/lucida-cli) and [Lucida GUI](https://github.com/jerrecode/lucida-gui) projects. This is a new independent project, **not** an official client of lucida.to.

## Currently implemented

- Typed async SDK with provider capability registry, strict URL host allowlisting and offline sample WAV provider.
- Streaming HTTP(S) audio downloads from trusted, explicitly approved source domains. No redirects. MIME type and configured byte caps validated. HTTPS is required outside explicit local-test mode.
- SQLite job journal with interrupted-job detection, state inspection, and no-overwrite publication through a same-filesystem hard link.
- Config paths use XDG on Linux and LocalAppData on Windows. `LUCIDA_HOME` / `LUCIDA_OUTPUT_DIR` override for local tests.
- Optional FastAPI `/v1/version`, `/v1/providers`, `/v1/jobs`, `/v1/demo` endpoints (`pip install '.[server]'`). Loopback 127.0.0.1 only.

## Python example

```python
import asyncio
from lucida_api import LucidaClient, Config

async def main():
    api = LucidaClient(Config())
    print(api.providers())
    job = await api.acquire('sample://tone')
    print(job.destination)

asyncio.run(main())
```

For approved publicly accessible audio, pass `Config(allowed_hosts=('trusted.example',))`. This whitelist assumes the host is trustworthy. **It does not provide strong DNS-rebinding resistance**, and the service must not be exposed to untrusted users. Do not trust arbitrary public addresses on a machine that has sensitive network access.

## Install from cloned source

Linux: `./install.sh` (creates `.venv` in this repository). Windows: `./install.ps1` (PowerShell). Or run `python -m venv .venv`, activate it and `python -m pip install -e .`. A Python distribution must already be installed.

Tests: `python -m pip install -e '.[dev]' && python -m pytest -q`. Local test uses an ephemeral HTTP server rather than copyrighted material.

## Important limits

This preview does **not** yet connect to lucida.to, Qobuz, TIDAL, or other streaming providers. Search, album/playlist acquisition, secure URL-to-file redirects, true pause/resume, automatic conversion, rate limits, cross-process job locking, and real-provider metadata retrieval are not yet implemented. Partial `.part` files are retained after a failed transfer but are not automatically resumed. A local API `/v1/demo` response confirms scheduling only, not completion. The API is intended for user-authorized media only.

See [the roadmap](IMPLEMENTATION_PLAN.md), [the capability matrix](docs/CAPABILITY_MATRIX.md) and [architecture decision](docs/ADR-0001.md).
