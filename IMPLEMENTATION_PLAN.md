# Hierarchical implementation plan (updated 2026-11-03)

**Completion rule:** a parent checkbox is completed only if all mandatory descendants are verified. Repository status: development preview, NOT release ready. Code and tests in the first vertical slice are locally verified under Python 3.13; CI matrices on Ubuntu and Windows have passed all 12 jobs, including Qt offscreen GUI launch. Full interactive Windows desktop and installer testing remain pending.

- [ ] Phase 1: Discovery and architecture [API; P0]
  - [x] Inspect all three initial repositories (empty via GitHub API)
  - [x] Review lucidadl and lucida-flow architecture and license
  - [x] Document candidate capability matrix and missing upstream evidence
  - [x] ADR for shared async Python core and two frontends
  - [ ] Verify live lucida.to protocol against authorized and documented endpoints [blocked HTTP 403]
- [ ] Phase 2: Foundations [all; P0]
  - [x] Establish three independent Python packages and declared dependency direction
  - [x] Add per-project tests and Linux/Windows GitHub Actions definitions
  - [x] Verify 2026-11-02 CI results on GitHub Windows and Ubuntu runners (12/12 jobs)
  - [x] Verify all three wheel builds on both OS runners
  - [x] Linux and Windows hosted CI installer smoke tests for all three packages (2026-11-03)
  - [ ] Full update/uninstall workflows and real desktop graphical sessions in clean VMs
- [ ] Phase 3: API [API; P0]
  - [x] Domain contracts, version and errors
  - [x] Capability registry, offline sample provider and MusicBrainz metadata-only search
  - [x] Configuration and app storage paths
  - [x] SQLite journal and explicitly confirmed interrupted job recovery marker
  - [x] Transactional cross-process job ownership, heartbeat and stale-lease detection (verified 2026-11-03)
  - [ ] Fully durable cross-process queue worker and automatic safe resume
  - [x] Controlled HTTP test transfer with length and MIME verification
  - [x] Transactionally serialized v1-to-v2 SQLite schema migration and ownership collision tests
  - [x] Strong-ETag HTTP Range resume for unchanged content with checked boundaries and refusal on changed source (local tests 2026-11-03)
  - [ ] Broader resume strategies and end-to-end multiprocess crash/restart testing
  - [x] In-process SDK background job submission, wait, cancellation, shutdown and new-job retry (verified locally 2026-11-03)
  - [ ] Cross-process cancellation dispatch, durable queue rescheduling and resumable jobs without strong ETags where safely feasible
- [ ] Phase 4: Real providers [API; P0]
  - [ ] Validate authorized provider interfaces, search and metadata
  - [ ] Implement and contract-test a real supported provider
  - [ ] Handle network/service-side refusal transparently
- [ ] Phase 5: Media engine [API; P0]
  - [x] Bounded streaming and no-clobber publication
  - [x] Strong-ETag partial resume and optional complete-file SHA-256 verification
  - [ ] Source-provided trusted digest discovery and integrity checking for non-ETag sources
  - [x] Atomic no-replace publication fallback for Linux/Windows filesystems where supported (local tests)
  - [ ] Advanced filename collision policy and unsupported filesystem handling
  - [ ] Album/playlist import and tested ordering
  - [ ] Optional FFmpeg conversion + verification
- [ ] Phase 6: CLI [CLI; P0]
  - [x] Version, doctor, providers, MusicBrainz search, offline demo, direct download, JSON jobs
  - [x] Bounded CLI batch import and terminal-failure retry (local tests 2026-11-03)
  - [ ] Persistent cross-process queues, pause, remote cancellation and interactive TUI
  - [ ] Linux and Windows real terminal validation
- [ ] Phase 7: GUI [GUI; P0]
  - [x] Qt downloads interface, metadata search, test provider, asynchronous workers and journal view
  - [x] GUI current-worker cancellation button and periodic history refresh (code implemented; Qt CI pending)
  - [x] GUI selected-job retry/resume and optional SHA-256 input (implemented; CI pending)
  - [ ] Provider-specific search, artwork, adaptive settings and model-view virtual queue
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

Run the combined tests (`PYTHONPATH=lucida-api/src:lucida-cli/src:lucida-gui/src pytest -q lucida-api/tests lucida-cli/tests lucida-gui/tests`) from sibling checkout directories. Next required tasks: implement automatic cross-process queue rescheduling, more complete download recovery, safe real-provider acquisition; create verified authorized real-provider adapter; verify the GitHub Actions matrix on Windows and Ubuntu. Keep Windows verification separate from Linux results. Do not mark parent phases complete yet.
