# Lucida API Core (0.1.0, development preview)

Reusable Python 3.11+ backend for the coordinated [Lucida CLI](https://github.com/jerrecode/lucida-cli) and [Lucida GUI](https://github.com/jerrecode/lucida-gui) projects. This is a new independent project, **not** an official client of lucida.to.

## Currently implemented

- Typed async SDK with provider capability registry, strict URL host allowlisting, offline sample WAV provider and MusicBrainz recording metadata search (no audio from MusicBrainz).
- Streaming HTTP(S) audio downloads from trusted, explicitly approved source domains. No redirects. MIME type and configured byte caps validated. HTTPS is required outside explicit local-test mode.
- SQLite job journal with automatically expired worker leases (database schema v2), legacy manual orphaned-job recovery (`recover_interrupted`), in-process async job submission (`submit`), wait (`wait`), cancellation (`cancel`), shutdown (`shutdown`) and terminal-failure retry from the beginning (`retry`). No-overwrite publication uses a same-filesystem hard link or an atomic no-replace rename fallback where supported.
- Config paths use XDG on Linux and LocalAppData on Windows. `LUCIDA_HOME` / `LUCIDA_OUTPUT_DIR` override for local tests.
- Optional FastAPI `/v1/version`, `/v1/providers`, `/v1/jobs`, `/v1/jobs/{id}`, `/v1/jobs/{id}/cancel`, `/v1/demo` endpoints (`pip install '.[server]'`). Loopback 127.0.0.1 only.

## Python example

```python
import asyncio
from lucida_api import LucidaClient, Config

async def main():
    api = LucidaClient(Config())
    print(api.providers())
    # Optional online metadata: await api.search("artist title")
    job = await api.acquire('sample://tone')
    print(job.destination)
    ident = await api.submit("sample://tone", filename="other-tone.wav")
    print((await api.wait(ident)).state)

asyncio.run(main())
```

For approved publicly accessible audio, pass `Config(allowed_hosts=('trusted.example',))`. This whitelist assumes the host is trustworthy. **It does not provide strong DNS-rebinding resistance**, and the service must not be exposed to untrusted users. Do not trust arbitrary public addresses on a machine that has sensitive network access.

## Install from cloned source

Linux: `./install.sh` (creates `.venv` in this repository). Windows: `./install.ps1` (PowerShell). Or run `python -m venv .venv`, activate it and `python -m pip install -e .`. A Python distribution must already be installed.

Tests: `python -m pip install -e '.[dev,server]' && python -m pytest -q`. Local test uses an ephemeral HTTP server rather than copyrighted material.

## Important limits

This preview does **not** yet connect to lucida.to, Qobuz, TIDAL, or other streaming providers. Streaming-provider search, album/playlist acquisition, arbitrary pause/resume, automatic conversion, rate limits, cross-process remote cancellation, and commercial-provider acquisition are not yet implemented. Partials can be resumed explicitly with `LucidaClient.resume(job_id)` only when a strong HTTP ETag was checkpointed, the provider honors a compatible `If-Range` request, and the file length and identity match. Changing remote content is rejected without corrupting the existing partial. Optional complete-file SHA-256 validation is available with `expected_sha256`, and mismatches are never published. A partial lacking a strong validator must be retried from scratch. A local API `/v1/demo` response confirms scheduling only, not completion. The API is intended for user-authorized media only.

See [the roadmap](IMPLEMENTATION_PLAN.md), [the capability matrix](docs/CAPABILITY_MATRIX.md) and [architecture decision](docs/ADR-0001.md).

### Shared journal recovery safety

Multiple clients can share the same SQLite journal. Opening another client **does not** automatically mark other clients' running jobs as interrupted. After confirming every CLI, GUI and service process has stopped, call `LucidaClient().recover_interrupted(confirm_no_active_workers=True)` or `lucida recover --confirm-inactive` in the CLI. This records interrupted state; it does not resume partial transfers or verify any completed media. Newly started jobs acquire transactional SQLite ownership leases and renew them while running. A newly opened client only marks **expired leased jobs** as interrupted; old unleased rows are excluded. Migration from the original seven-column database is performed under a write transaction. This supports safe detection of stale jobs but does not yet resume them across processes. Users must not run old and new application versions against the same live SQLite database. `cancel` only operates on jobs submitted by the same client and event loop; it cannot terminate a CLI or GUI task in another process. `retry` starts a new job and new transfer, not an HTTP byte-range resume. The optional REST service exposes same-process job cancellation. The service demo endpoint is development-only and must not be publicly exposed.

### Verified limited resume and integrity example

```python
# A failed trusted HTTPS audio job with a strong ETag can be resumed:
# completed = await api.resume(previous_job_id, expected_sha256="a" * 64)
# Replace the hash with the actual trusted SHA-256 of the complete media.
```

Resume is **not** guaranteed for servers that omit strong entity tags, serve compressed inconsistent responses, change the resource, or fail to honor HTTP Range semantics. The optional checksum is user-supplied; the application does not invent an expected value.
