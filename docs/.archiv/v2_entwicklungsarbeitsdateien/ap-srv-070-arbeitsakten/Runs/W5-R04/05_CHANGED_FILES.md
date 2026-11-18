# W5-R04 — 05 Changed Files

All paths relative to the repository root. Generated from
`git diff --name-status -M` against the start commit
`934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`.

## Release engine (`release_tooling/`)

| File | Change |
| --- | --- |
| `release_tooling/adapters.py` | modified |
| `release_tooling/aliases.py` | added |
| `release_tooling/candidate.py` | added |
| `release_tooling/cli.py` | modified |
| `release_tooling/config.py` | modified |
| `release_tooling/engine.py` | modified |
| `release_tooling/pipeline.py` | modified |
| `release_tooling/preflight.py` | modified |
| `release_tooling/rc_manifest.py` | modified |
| `release_tooling/remote_checks.py` | modified |
| `release_tooling/state.py` | modified |

## Build and packaging tooling

| File | Change |
| --- | --- |
| `Dockerfile` | modified |
| `build/kroko-builder.Dockerfile` | modified |
| `tools/build_distribution.py` | added |
| `tools/build_production.py` | modified |
| `tools/release_candidate.py` | added |

## Product packaging surface

| File | Change |
| --- | --- |
| `VoiceSTT/kroko/artifacts.py` | modified |
| `VoiceSTT/kroko/buildinputs.py` | modified |
| `setup.py` | modified |
| `voice_stt_server/__init__.py` | added |
| `voice_stt_server/_embedded.py` | added |

## GitHub Actions workflows

| File | Change |
| --- | --- |
| `.github/workflows/ci.yml` | modified |
| `.github/workflows/release-candidate.yml` | added |
| `.github/workflows/release-publish.yml` | added |

## Tests

| File | Change |
| --- | --- |
| `tests/unit/release_support.py` | added |
| `tests/unit/test_build_distribution.py` | added |
| `tests/unit/test_build_production.py` | modified |
| `tests/unit/test_docs_surface.py` | added |
| `tests/unit/test_kroko_fingerprint.py` | modified |
| `tests/unit/test_production_docker_contract.py` | modified |
| `tests/unit/test_release_adapters.py` | modified |
| `tests/unit/test_release_aliases.py` | added |
| `tests/unit/test_release_candidate.py` | added |
| `tests/unit/test_release_cli.py` | modified |
| `tests/unit/test_release_engine.py` | modified |
| `tests/unit/test_release_pipeline.py` | modified |
| `tests/unit/test_release_preflight.py` | modified |
| `tests/unit/test_release_rc_manifest.py` | modified |
| `tests/unit/test_release_remote_checks.py` | modified |
| `tests/unit/test_release_state.py` | modified |
| `tests/unit/test_release_workflows.py` | added |

## Documentation

| File | Change |
| --- | --- |
| `README.md` | modified |
| `RELEASE_NOTES.md` | modified |
| `build/BUILD.md` | modified |
| `build/vps/README.md` | modified |
| `docs/README.md` | modified |
| `docs/engines/cohere.md` | deleted |
| `docs/engines/funasr.md` | deleted |
| `docs/engines/hf-transformers.md` | deleted |
| `docs/engines/moonshine.md` | deleted |
| `docs/engines/omnilingual-asr.md` | deleted |
| `docs/engines/openai-whisper.md` | deleted |
| `docs/engines/parakeet-nemo.md` | deleted |
| `docs/engines/sherpa-onnx.md` | deleted |
| `docs/engines/whisper-cpp.md` | deleted |
| `docs/fastapi-server.md` | modified |
| `docs/faster-whisper.md` | renamed from `docs/engines/faster-whisper.md` |
| `docs/installation.md` | modified |
| `docs/kroko-onnx.md` | renamed from `docs/engines/kroko-onnx.md` |
| `docs/licenses.md` | modified |
| `docs/module-map.md` | modified |
| `docs/quick-start.md` | modified |
| `docs/release-process.md` | added |
| `docs/testing.md` | modified |
| `docs/transcription-engines.md` | modified |
| `docs/troubleshooting.md` | modified |

## Project process archive

| File | Change |
| --- | --- |
| `docs/.archiv/README.md` | modified |
| `docs/.archiv/einheitliche_triggerarchitektur/AP-SRV-070/2026-09-08_W5_R04_ABWEICHUNGEN.md` | added |
| `docs/.archiv/einheitliche_triggerarchitektur/AP-SRV-070/2026-09-08_W5_R04_PLAN.md` | added |
| `docs/.archiv/einheitliche_triggerarchitektur/AP-SRV-070/2026-09-08_W5_R04_UMSETZUNGSVERGLEICH.md` | added |

## Diffstat

```text
 .github/workflows/ci.yml                           |  46 +-
 .github/workflows/release-candidate.yml            | 330 +++++++++
 .github/workflows/release-publish.yml              | 312 +++++++++
 Dockerfile                                         |  11 +-
 README.md                                          | 511 ++++++++------
 RELEASE_NOTES.md                                   |  45 ++
 VoiceSTT/kroko/artifacts.py                        |  50 +-
 VoiceSTT/kroko/buildinputs.py                      | 105 ++-
 build/BUILD.md                                     | 108 ++-
 build/kroko-builder.Dockerfile                     |  42 +-
 build/vps/README.md                                |   2 +-
 docs/.archiv/README.md                             |   2 +-
 .../AP-SRV-070/2026-09-08_W5_R04_ABWEICHUNGEN.md   | 178 +++++
 .../AP-SRV-070/2026-09-08_W5_R04_PLAN.md           | 190 +++++
 .../2026-09-08_W5_R04_UMSETZUNGSVERGLEICH.md       | 109 +++
 docs/README.md                                     |  17 +
 docs/engines/cohere.md                             |  97 ---
 docs/engines/funasr.md                             |  55 --
 docs/engines/hf-transformers.md                    | 123 ----
 docs/engines/moonshine.md                          |  88 ---
 docs/engines/omnilingual-asr.md                    | 297 --------
 docs/engines/openai-whisper.md                     |  75 --
 docs/engines/parakeet-nemo.md                      | 105 ---
 docs/engines/sherpa-onnx.md                        | 149 ----
 docs/engines/whisper-cpp.md                        | 113 ---
 docs/fastapi-server.md                             |  92 +--
 docs/{engines => }/faster-whisper.md               |   0
 docs/installation.md                               |  53 +-
 docs/{engines => }/kroko-onnx.md                   |   6 +-
 docs/licenses.md                                   |  13 +
 docs/module-map.md                                 |   2 +-
 docs/quick-start.md                                |  23 +-
 docs/release-process.md                            | 316 +++++++++
 docs/testing.md                                    |  11 +-
 docs/transcription-engines.md                      | 164 +++--
 docs/troubleshooting.md                            |   5 +-
 release_tooling/adapters.py                        | 534 +++++++++++----
 release_tooling/aliases.py                         | 106 +++
 release_tooling/candidate.py                       | 282 ++++++++
 release_tooling/cli.py                             | 343 +++++++---
 release_tooling/config.py                          | 141 +++-
 release_tooling/engine.py                          |  91 ++-
 release_tooling/pipeline.py                        |   5 +-
 release_tooling/preflight.py                       | 151 +++-
 release_tooling/rc_manifest.py                     | 416 ++++++++---
 release_tooling/remote_checks.py                   | 291 ++++++--
 release_tooling/state.py                           | 167 +++--
 setup.py                                           | 115 +++-
 tests/unit/release_support.py                      | 286 ++++++++
 tests/unit/test_build_distribution.py              | 250 +++++++
 tests/unit/test_build_production.py                | 100 ++-
 tests/unit/test_docs_surface.py                    | 251 +++++++
 tests/unit/test_kroko_fingerprint.py               |  91 +++
 tests/unit/test_production_docker_contract.py      |  63 +-
 tests/unit/test_release_adapters.py                | 662 +++++++++---------
 tests/unit/test_release_aliases.py                 |  71 ++
 tests/unit/test_release_candidate.py               | 358 ++++++++++
 tests/unit/test_release_cli.py                     | 762 +++++++++------------
 tests/unit/test_release_engine.py                  | 622 ++++++++---------
 tests/unit/test_release_pipeline.py                | 183 ++---
 tests/unit/test_release_preflight.py               | 179 ++++-
 tests/unit/test_release_rc_manifest.py             | 386 ++++++++---
 tests/unit/test_release_remote_checks.py           | 276 +++++---
 tests/unit/test_release_state.py                   | 345 ++++++----
 tests/unit/test_release_workflows.py               | 404 +++++++++++
 tools/build_distribution.py                        | 483 +++++++++++++
 tools/build_production.py                          | 126 +++-
 tools/release_candidate.py                         | 499 ++++++++++++++
 voice_stt_server/__init__.py                       |  68 ++
 voice_stt_server/_embedded.py                      |  82 +++
 70 files changed, 9508 insertions(+), 3526 deletions(-)
```
