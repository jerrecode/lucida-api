# Hierarchical implementation plan (2026-11-02)

**Completion rule:** a parent checkbox is completed only if all mandatory descendants are verified. Repository status: development preview, NOT release ready. Code and tests in the first vertical slice are locally verified under Python 3.13; CI and real Windows testing pending.

- [ ] Phase 1: Discovery and architecture [API; P0]
  - [x] Inspect all three initial repositories (empty via GitHub API)
  - [x] Review lucidadl and lucida-flow architecture and license
  - [x] Document candidate capability matrix and missing upstream evidence
  - [x] ADR for shared async Python core and two frontends
  - [ ] Verify live lucida.to protocol against authorized and documented endpoints [blocked HTTP 403]
- [ ] Phase 2: Foundations [all; P0]
  - [x] Establish three independent Python packages and declared dependency direction
  - [x] Add per-project tests and Linux/Windows GitHub Actions definitions
  - [ ] Verify CI results on GitHub Windows and Ubuntu runners
  - [ ] Verify built wheels and install/update/uninstall in clean VMs
- [ ] Phase 3: API [API; P0]
  - [x] Domain contracts, version and errors
  - [x] Capability registry and offline sample provider
  - [x] Configuration and app storage paths
  - [x] SQLite journal and interrupted job recovery marker
  - [x] Controlled HTTP test transfer with length and MIME verification
  - [ ] Durable transactional resume, migration tests, multi-process locking
  - [ ] Job cancellation/resume API and bounded batch scheduling
- [ ] Phase 4: Real providers [API; P0]
  - [ ] Validate authorized provider interfaces, search and metadata
  - [ ] Implement and contract-test a real supported provider
  - [ ] Handle network/service-side refusal transparently
- [ ] Phase 5: Media engine [API; P0]
  - [x] Bounded streaming and no-clobber publication
  - [ ] True partial resume and cryptographic integrity verification
  - [ ] Advanced filename collisions and cross-filesystem fallback
  - [ ] Album/playlist import and tested ordering
  - [ ] Optional FFmpeg conversion + verification
- [ ] Phase 6: CLI [CLI; P0]
  - [x] Version, doctor, providers, offline demo, direct download, JSON jobs
  - [ ] Batch queues, pause, cancel, retry and interactive TUI
  - [ ] Linux and Windows real terminal validation
- [ ] Phase 7: GUI [GUI; P0]
  - [x] Qt downloads interface, test provider, asynchronous worker and journal view
  - [ ] Provider search, artwork, retry, cancel, adaptive settings and model-view virtual queue
  - [ ] Test actual GUI on Linux and Windows screens / accessibility tooling
- [ ] Phase 8: Installation [all; P0]
  - [x] Initial isolated Python venv installer scripts for Unix and PowerShell
  - [ ] Signed/checksummed release artifacts and rollback
  - [ ] Linux desktops and Windows 11 clean-install matrix
- [ ] Phase 9: Reliability [all; P0]
  - [ ] Failure injection, resource leak checks and security audit
  - [ ] Full cross-repo SDK/API contract tests
- [ ] Phase 10: Performance / UX [all; P1]
  - [ ] Benchmark startup, memory, transfer, GUI updates, large queue
  - [ ] Profile and improve measured bottlenecks
- [ ] Phase 11: Release [all; P0]
  - [ ] Verify required capabilities, tests, installers, packaging, documentation
  - [ ] Publish coordinated compatible releases
- [ ] Phase 12: Later extensions [all; P2]
  - [ ] Optional plugin SDK, additional providers, storage adapters, extended media library

## Continuation point

Run the combined tests (`PYTHONPATH=lucida-api/src:lucida-cli/src:lucida-gui/src pytest -q lucida-api/tests lucida-cli/tests lucida-gui/tests`) from sibling checkout directories. Next required tasks: fix and harden filesystem finalization on non-hardlink volumes; implement job lifecycle controls; create verified authorized real-provider adapter; verify the GitHub Actions matrix on Windows and Ubuntu. Keep Windows verification separate from Linux results. Do not mark parent phases complete yet.
