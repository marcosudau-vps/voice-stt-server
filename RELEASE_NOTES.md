# Release Notes

## Unreleased

## 2.0.0

### Added

- VoiceSTT is now published as two complete, alternative distributions
  (AP-SRV-070 W5-R04): `voice-stt-server` embeds the Kroko Free native
  runtime and `voice-stt-server-pro` embeds the Kroko Pro one. Each wheel
  contains its runtime, so `pip install voice-stt-server` needs no native
  Kroko build, no `stt-install-kroko`, no Docker and no separate wheel.
  Both expose the same import package `voice_stt_server` and the same CLI
  `voice-stt-server` (with `stt-server`, `stt-server-legacy` and `stt` kept
  as compatibility aliases), so application code is identical on Free and
  Pro. The two distributions are alternatives and must not be installed
  into the same environment, and the installed distribution - never a
  runtime licence key - decides which native runtime is present. Supported
  targets are CPython 3.12 on Linux x86-64 and Windows x86-64, which is the
  matrix the embedded runtime is actually built and qualified for. No sdist
  is published for these distributions, because an sdist cannot carry a
  native runtime and would break that guarantee.
- Added the GitHub-native release infrastructure (AP-SRV-070 W5-R04): a
  dispatch-only candidate workflow that builds and qualifies a complete
  release candidate on a clean GitHub-hosted runner from an exact source
  commit, and a dispatch-only publish workflow gated by a protected
  environment that publishes the already-qualified candidate without
  rebuilding it. The canonical publication order now creates the immutable
  Git tag *before* the first irreversible public write, publishes both
  distributions to PyPI via Trusted Publishing (no stored token), publishes
  the exact Free and Pro images to Docker Hub and then promotes the same OCI
  manifests to GHCR by digest, moves the `2.0`/`2`/`latest` aliases only
  after every exact artifact is verified in both registries, and creates the
  GitHub Release last. See `docs/release-process.md`.

### Changed

- The public documentation surface now names only Faster-Whisper and
  Kroko-ONNX as supported production STT engines. `docs/engines/` was
  removed; the two retained guides moved to `docs/faster-whisper.md` and
  `docs/kroko-onnx.md`, and the README was rewritten. The other engine
  adapters remain in the source tree but are internal/experimental and are
  no longer advertised as product features.
- The Kroko Linux builder container is now a declared, source-controlled
  build authority (base image pinned by digest, declared apt package set,
  exactly pinned packaging tools), and the production image base is pinned
  by digest. The OCI `created` timestamp is derived from the commit rather
  than the wall clock, so rebuilding the same source keeps the same image
  identity.

### Added (earlier in this version)

- Added the AP-SRV-070 W5 release infrastructure: a canonical repository-root
  `release.py` entry point with read-only preflight and a true no-publish
  dry-run over the fixed W6 publication order (PyPI, then GHCR, then Docker
  Hub, then external artifact verification, then the Git tag, then the
  GitHub Release), a non-secret resumable release-state contract so a
  partial W6 run resumes the same product version instead of ever
  advancing to a new one, a canonical RC manifest format that binds the
  exact source, package, Kroko, and image identities a release candidate is
  qualified against, and a public GitHub Actions CI workflow that builds
  the wheel/sdist, validates them with `twine check`, installs from the
  built wheel (never editable), and runs the fast unit/guard/release-tool
  suite on Windows and Ubuntu 24.04 with Python 3.12. `release.py` performs
  no public write in this release; W6 is the first run that actually
  publishes anything.
- Added a reusable Kroko runtime artifact pipeline (`VoiceSTT/kroko/`): the
  native Kroko build is pinned to an immutable upstream commit, described by a
  canonical build fingerprint, and cached in a persistent, configurable
  artifact store with strictly separated free/pro namespaces. A matching
  verified artifact is reused by default, `--rebuild-kroko` forces a real
  rebuild with atomic replacement, and a failed rebuild leaves the previous
  good artifact intact. The fingerprint deliberately excludes the VoiceSTT
  product version, server, wake-word and documentation sources, so an ordinary
  change or a release version bump no longer triggers a native recompilation.
- Added a Kroko model authority (`VoiceSTT/assets/kroko/models.json`) that pins
  each known model's identity, SHA-256, size, license class and required
  runtime variant. It ships metadata only: no Kroko model is bundled, because
  the upstream redistribution grant is not unambiguous. A normal server start
  no longer downloads models by itself - provisioning is explicit and
  hash-verifiable, and free/pro mismatches are refused instead of silently
  tolerated.
- Added a single automatic product version authority (`VERSION` plus
  `VoiceSTT/_version.py`): `setup.py`, the importable package, the running
  server and the Protocol-v2 handshake now all read the same resolved
  version instead of three independently hardcoded values. Migrated the
  baseline to `2.0.0`, the already-established v2 server identity - this is
  a packaging/versioning-authority consolidation, not a new release bump.
- Added a deterministic, manifest-derived wake-word package-data authority
  (`wakeword_package_resources.py`) so the public wheel/sdist only ever
  contains the 25 manifested dual-backend wake words, the shared pipeline
  assets and the bundled VAD asset - never the historical, unmanifested
  model variants that also live under `VoiceSTT/assets/wakeword_models/`.
- Added `build/BUILD.md` as the canonical project-wide reference for Python
  packaging, Docker builds, Kroko Community/Pro variants, testing, deployment
  acceptance and rollback.
- Added a separate `build/vps` area with secret-free snapshots of the active
  server stack, a Pro-aware release script and reproducible build-area helpers.
- Added log protocol version 2 with SQLite-first replay/live delivery,
  committed cursor metadata, channel-/session-aware retention watermarks,
  retention-gap and cursor-ahead semantics, and explicit event-store
  availability.
- Added fully authenticated server-wide Admin history/replay/live access,
  including bounded history/filter controls in the browser Admin drawer.
- Added `transcription.discarded(reason=empty_final)` as the terminal event for
  empty final recorder results without emitting an empty final text frame.

- Added a session-local OpenWakeWord contract on `/ws/transcribe`, including
  tri-state enablement, optional tuning overrides, explicit fallbacks, and
  effective configuration/capabilities in `hello` and `ready`.
- Added `models.json`-backed OpenWakeWord discovery with logical IDs, default
  model selection, pipeline-model mappings, local file validation, and support
  for configuring the manifest or its directory directly.
- Added protocol, isolation, model-catalog, fallback, and WebSocket tests for
  independent Hotkey and Wake Word sessions.
- Added a detailed implementation and operations guide plus a PowerShell live
  verification script for the session-local Wake Word contract.
- Added a versioned structured event system with `system`, `audit`,
  `transcription`, and `performance` channels, transport-independent
  correlation and centralized redaction.
- Added calendar-based JSONL files, indexed SQLite history, filtered history
  endpoints, and a separate authenticated session-/admin-scoped `/ws/logs`
  connection with replay and live delivery.
- Added a mandatory documentation archive process for larger change actions,
  including a dated plan, a later plan-versus-implementation review, and a
  separate rationale for material deviations.
- Added a public production Docker/Compose release path
  (`tools/build_production.py`, `build/kroko-builder.Dockerfile`, the
  rewritten `Dockerfile`/`docker-compose.yml`): the production image installs
  a pre-built VoiceSTT wheel and a pre-resolved, W4A-verified Kroko wheel
  instead of compiling or editable-installing anything itself, runs Ubuntu
  24.04 as the non-root `voicestt` user with a persistent
  `/var/lib/voicestt` root, and produces the two public product identities
  `voice-stt-server` (free) and `voice-stt-server-pro` with the same
  VoiceSTT build. The public Compose file no longer needs a separate
  browserclient/nginx container - the FastAPI server serves the browser
  client from its own installed package - and its Docker health probe now
  only proves the process/control plane is alive, never that an STT model is
  loaded, so a container with no model provisioned yet stays healthy instead
  of restart-looping.

### Changed

- The portable Compose launcher now passes an explicit Kroko build variant
  from `deployment.kroko_variant`; its project default remains `free`.
- The VPS release path now defaults to Kroko Pro, verifies the Pro key/model
  prerequisites without exposing secrets, validates the active Pro-16 model
  and shared recognizer in `/health`, and restores persisted runtime
  configuration together with the previous image on rollback.
- The productive VPS profile uses one shared
  `Kroko-DE-Pro-16-L-Streaming-001.data` recognizer for final and realtime
  transcription because two licensed recognizers caused a reproducible native
  exit 139 with the validated runtime.
- Audit, transcription, and system `*_logging_enabled` switches now control
  only optional JSONL/stdout mirrors. Performance uses separate source and
  mirror switches: `performance_logging_enabled` controls generation and
  `performance_log_mirror_enabled` controls optional mirroring. No mirror
  switch suppresses an already generated SQLite or `/ws/logs` event.
- Empty final results now use a transcription-start ticket to claim their
  generation/segment terminal exactly once, including duplicate-result and
  disconnect races through the real text worker.

- Structured events are now committed to SQLite before cursor assignment,
  optional JSONL/stdout mirroring, or `/ws/logs` visibility. Live handlers use
  payload-free commit wakeups and rescan SQLite, so subscriber queue pressure
  cannot lose committed events.
- Store outages now suppress uncommitted normal events, expose degraded health
  and access metadata, close existing log streams with code `1011`, and reject
  new log streams until a successful committed event recovers the store.
- Admin-key comparisons for HTTP and log WebSocket access now use
  `secrets.compare_digest`.

- Corrected the logging rollout so Docker has one generated-data root
  (`data_root_path: /data`). Audit, performance, transcription, system, audio,
  SQLite history, and persisted runtime configuration paths are now derived
  internally and can no longer drift outside the mounted volume.
- The FastAPI Wake Word admin and session contracts now expose OpenWakeWord
  only; Porcupine is omitted from the model catalog and browser selector.
- Ready notifications are session-specific so they cannot leak another
  session's effective Wake Word profile.
- Audit, transcription, performance, and system events now share one event
  envelope and monotonically assigned cursor across HTTP and WebSocket paths.

## 1.0.2 - 2026-05-31

### Changed in V 1.0.2

- Split the `AudioToTextRecorder` implementation behind the existing public
  facade into focused core modules for lifecycle, recording, realtime
  transcription, voice activity, wake-word handling, initialization, shutdown,
  and formatting.
- Refreshed recorder architecture and compatibility documentation so the public
  facade, threading boundaries, and regression checks are easier to audit.
- Normalized package docstrings and comments to use block-style summaries and
  focused runtime explanations.

### Removed

- Removed an unused internal console color helper from `audio_recorder.py`.

## 1.0.1 - 2026-05-20

### Added

- Added a generic streaming transcription session interface so engines can
  opt in to incremental realtime decoding while existing engines keep the
  full-buffer fallback behavior.
- Added `kroko_onnx` transcription engine for Kroko/Banafo `.data` streaming
  models.
- Added Kroko realtime preview support that feeds streaming engines only newly
  recorded audio frames through a persistent session.
- Added `stt-install-kroko`, exposed through the `kroko-builder` extra, to help
  build and install Kroko-ONNX for the active Python environment.
- Added focused Kroko and realtime streaming unit coverage plus a public manual
  `tests/voicestt_kroko_test.py` smoke script.
- Added `omnilingual_asr` transcription engine for Meta
  Omnilingual ASR on Linux/WSL2 with Python 3.11.x, with support for the
  published CTC and LLM model cards. Native Windows is not supported because
  `fairseq2n` has no Windows wheel; Python 3.12.x is blocked by upstream
  `omnilingual-asr` package metadata.
- Added `docs/licenses.md` with engine and model-family license notes.

### Changed

- Kroko Community models with known public filenames can be auto-downloaded
  into the VoiceSTT cache when `auto_download_model` is enabled.
- Kroko final transcription remains one-shot. The new streaming path is used
  for realtime previews only when the realtime engine advertises streaming
  support.
- Kroko model cadence is used to choose automatic finalization tail padding.
- Omnilingual ASR uses `omniASR_CTC_1B_v2` as the default when the
  recorder is still configured with a Whisper default model name.
- Omnilingual in-memory audio is passed to the backend as predecoded waveform
  dictionaries to avoid the upstream package treating raw float arrays as
  encoded audio bytes.

### Notes

- Install/build Kroko-ONNX separately with
  `pip install "VoiceSTT[kroko-builder,silero-onnx-cpu]"` followed by
  `stt-install-kroko --build`, or install a compatible Kroko-ONNX wheel in the
  same Python environment. The `silero-onnx-cpu` extra provides the local VAD
  backend used by recorder-based Kroko smoke tests and live microphone use.
- Licensed Pro models require a Pro-capable Kroko wheel and a key supplied at
  runtime through configuration, CLI, or environment variables. Do not commit
  keys, Pro models, generated logs, local wheels, or local cache contents.
- `Pro-16-L` is the recommended realtime model for the fastest partials. Local
  private validation observed the expected low-latency partial behavior, but
  exact cadence depends on runtime, provider, hardware, and scheduling.
- `suppress_native_output=True` redirects Kroko native stdout/stderr during
  recognizer calls and sets `KROKO_ONNX_SUPPRESS_LICENSE_OUTPUT=1`. Reliable
  suppression of asynchronous Pro license refresh messages requires a Kroko
  wheel rebuilt with VoiceSTT's native quiet-output patch; older Kroko wheels
  may still print background license status text.
- Omnilingual ASR support is optional and Linux/WSL2 Python 3.11.x-oriented.
  Native Windows installs are not supported by the upstream dependency stack at
  this time, and Python 3.12.x cannot resolve the current upstream package.
- `omniASR_CTC_1B_v2` is the recommended Omnilingual starting point for local
  realtime tests in this release. Smaller/larger CTC and LLM models are exposed
  through model-card plumbing but require their own quality and memory checks.
