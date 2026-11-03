# Evidence-bounded capability matrix (updated 2026-11-03)

Legend: V = verified locally, R = described in reference implementation but not independently runtime-verified, U = unknown / upstream dependent, N = not implemented. Direct live lucida.to request returned HTTP 403 at research time.

| Capability | Source and evidence | Proposed owner | Category | State and verification |
| --- | --- | --- | --- | --- |
| Offline sample WAV | Current own test fixture | API | Verified Required | V: WAV decoded by stdlib wave |
| Direct trusted HTTP(S) audio | Own implemented provider | API | Useful Extension | V: local HTTP server binary check; public remote unverified |
| Persistent transfer journal | Own SQLite store | API | Verified Required | V: transactional v2 migration, atomic owner claims, heartbeat expiry, reopen and interrupted marker |
| MusicBrainz metadata search | Official MusicBrainz API documentation | API / CLI / GUI | Useful Extension | V: HTTP mock contract; live service not tested; never audio acquisition |
| Public Python SDK | Own source and imports | API | Verified Required | V: client import and tests |
| FastAPI local service | Own ASGI integration tests | API | Useful Extension | V: /v1/version/providers/jobs through in-process HTTP adapter; network socket deployment unverified |
| CLI JSON and demo | Own CLI tests | CLI | Verified Required | V: output, error, completion and history |
| Qt download and history | Own GUI, Qt not present in test runtime | GUI | Verified Required | Source compiled/imported; native window unverified |
| Provider discovery | Own capability records | API | Verified Required | V: API and CLI tests |
| Lucida Qobuz/Amazon search | Jude-A/lucidadl README, 2026-10-15 reports fluctuating access | API | Upstream-Dependent | N: do not represent as enabled |
| Playlist import from eight services | Jude-A/lucidadl README | API | Useful Extension | R only; N here |
| Playwright browser transfer | ryanlong1004/lucida-flow README | API optional | Upstream-Dependent | R only; rejected as mandatory core |
| Strong-ETag HTTP Range resume | Own local HTTP fixtures, RFC HTTP Range protocol | API / CLI / GUI | Useful Extension | V locally: 206 partial, ETag mismatch refusal; live server unspecified |
| File checksum integrity | Own SHA-256 fixture | API / CLI / GUI | Verified Required | V locally: matched and deliberately mismatched hashes |
| No-overwrite filesystem publication | Own fallback tests | API | Verified Required | V locally: hard link, Linux no-replace rename fallback; Windows CI pending |
| Lossy/lossless transcoding | Jude-A/lucidadl README | API | Future Extension Point | R only; N here |
| Format/quality selection | Lucida third-party descriptions | API | Upstream-Dependent | U: must confirm authorized upstream |
| Windows standalone EXE | No verified build | CLI / GUI | Future Extension Point | N |
| Direct DRM/circumvention | Outside permitted scope | none | Unavailable/Unsupported | Must not implement |

Upstream sources: https://github.com/Jude-A/lucidadl , https://github.com/ryanlong1004/lucida-flow , https://lucida.to . Source licensing MIT for both reference repositories; no third-party code copied.
