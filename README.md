# VoiceSTT

**A speech-to-text engine and streaming server for applications that need voice
activity detection, fast transcription, live partial results, and wake words —
installed complete, with no native build step.**

VoiceSTT is a Python library and a production FastAPI server in one project. It
turns microphone or application-supplied audio into text, and it ships the
speech recognition runtime it needs inside the distribution you install.

```python
from voice_stt_server import AudioToTextRecorder

if __name__ == "__main__":
    with AudioToTextRecorder() as recorder:
        print("Speak now")
        print(recorder.text())
```

---


**V2-Handbuch:** [vollständige Dokumentation mit 104 Kapiteln](docs/v2-handbuch/README.md). Technische Betriebs- und Lizenzgates: [Releaseprozess](docs/v2-handbuch/ressourcen/release-process.md), [Lizenzübersicht](docs/v2-handbuch/ressourcen/licenses.md).

## Status

Version `2.0.0`. The server architecture (protocol v2, activation lifecycle,
settings control plane, wake-word catalog, structured event store) is frozen
and covered by an extensive automated test suite.

The public release infrastructure described under
[Release model](#release-model) is complete in source and runs on GitHub
Actions. **The `2.0.0` packages are not published yet**, so this README
deliberately contains no PyPI, Docker Hub or GHCR badge and no links to
registry pages that do not exist. Build from source until the first release is
published; the exact commands are below.

---

## One V2 distribution

`voice-stt-server` is the single public product. Its wheel and container image
include the qualified Pro-capable Kroko runtime. Community models work without
a Kroko key. Pro models require a valid entitlement for the actual model UUID;
a key or `runtime_variant=pro` cannot manufacture native capability. The key is
a runtime credential for model-specific permission.

The public import is `voice_stt_server` and the CLI is `voice-stt-server`.
No separate native package or operator native build is needed. The historical
`voicestt` source/development distribution remains available for contributors.

Real Linux and Windows native/product qualification has passed; the
[qualification record](docs/.archiv/kroko_v2_finalization/2026-10-27_NACHTRAG_FINALE_QUALIFIKATION.md)
binds the tested artifacts to their source commit. Technical feature review is
separate from public release approval, which remains **BLOCKED**: verified
redistribution rights, a complete two-platform RC with verified OCI staging
manifest identity, and independent acceptance remain outstanding. See
[license gates](docs/v2-handbuch/ressourcen/licenses.md#unified-v2-release-gate).

---

## Installation

Supported targets for the public product are **CPython 3.12** on
**Linux x86-64** and **Windows x86-64**. That is the matrix the embedded native
runtime is actually built and qualified for, so it is the only matrix the
packaging claims.

```bash
pip install voice-stt-server
```

That is the whole installation. Faster-Whisper, the packaged Silero ONNX voice
activity detector, the Kroko-ONNX runtime and the FastAPI server are all
included.

On Linux, PortAudio's headers are needed for microphone capture:

```bash
sudo apt-get update && sudo apt-get install -y python3-dev portaudio19-dev
```

On macOS (development only — no qualified native runtime is published for it):

```bash
brew install portaudio
```

Optional wake-word backends are an extra, because `openwakeword` pulls a
`tflite-runtime` dependency that has no wheel on every supported target:

```bash
pip install "voice-stt-server[wake-words]"
```

Building from source, and the development distribution used by this
repository's own tests, are described in
[`build/BUILD.md`](build/BUILD.md) and [docs/v2-handbuch/06-betrieb/06.02-installationskonzept.md](docs/v2-handbuch/06-betrieb/06.02-installationskonzept.md).

---

## Speech recognition engines

Two engines are supported, documented and qualified as the production surface:

| Engine | Use it for | Guide |
| --- | --- | --- |
| `faster_whisper` | The default. Mature Whisper transcription, CPU or GPU, broad language coverage. | [docs/v2-handbuch/02-funktionsweise/02.06-engines.md](docs/v2-handbuch/02-funktionsweise/02.06-engines.md) |
| `kroko_onnx` | Low-latency local streaming recognition with Kroko/Banafo `.data` models, Community or licensed Pro. | [docs/v2-handbuch/02-funktionsweise/02.06-engines.md](docs/v2-handbuch/02-funktionsweise/02.06-engines.md) |

```python
from voice_stt_server import AudioToTextRecorder

recorder = AudioToTextRecorder(
    model="small.en",
    transcription_engine="faster_whisper",
)
```

Final and live transcription can use different engines:

```python
recorder = AudioToTextRecorder(
    transcription_engine="faster_whisper",
    model="small.en",
    enable_realtime_transcription=True,
    realtime_transcription_engine="kroko_onnx",
)
```

The source tree still contains lazily-loaded adapters for other engine families.
They are internal and experimental: they are not part of the supported
production surface, they are not qualified by the release process, and they are
not documented here. See [docs/v2-handbuch/02-funktionsweise/02.06-engines.md](docs/v2-handbuch/02-funktionsweise/02.06-engines.md).

---

## Working with audio

### Microphone

```python
from voice_stt_server import AudioToTextRecorder

if __name__ == "__main__":
    with AudioToTextRecorder() as recorder:
        print(recorder.text())
```

Use the `if __name__ == "__main__":` guard when running scripts — especially on
Windows — because VoiceSTT uses multiprocessing for model work.

### Continuous dictation

Pass a callback so transcription completes asynchronously while the loop keeps
listening:

```python
from voice_stt_server import AudioToTextRecorder

def process_text(text):
    print(text)

if __name__ == "__main__":
    recorder = AudioToTextRecorder()
    while True:
        recorder.text(process_text)
```

### External audio

Set `use_microphone=False` when the audio comes from a file, a stream, a
websocket or another process. Feed 16-bit mono PCM at 16 kHz, or pass the
original sample rate and let VoiceSTT resample:

```python
from voice_stt_server import AudioToTextRecorder

if __name__ == "__main__":
    recorder = AudioToTextRecorder(use_microphone=False)
    with open("audio_chunk.pcm", "rb") as audio_file:
        recorder.feed_audio(audio_file.read(), original_sample_rate=16000)
    print(recorder.text())
    recorder.shutdown()
```

More patterns: [docs/v2-handbuch/06-betrieb/06.06-ersteinrichtung.md](docs/v2-handbuch/06-betrieb/06.06-ersteinrichtung.md) and
[docs/v2-handbuch/04-schnittstellen/04.05-audiotransport.md](docs/v2-handbuch/04-schnittstellen/04.05-audiotransport.md).
Every constructor parameter is documented in
[docs/v2-handbuch/03-konfiguration/03.07-session-einstellungen.md](docs/v2-handbuch/03-konfiguration/03.07-session-einstellungen.md).

---

## Server

The same distribution installs a production FastAPI server with multi-user
session isolation, a shared model scheduler, metrics and health endpoints:

```bash
voice-stt-server --host 0.0.0.0 --port 8010
```

`voice-stt-server` is the canonical command. The older `stt-server`, `stt` and
`stt-server-legacy` names remain as compatibility aliases.

### Protocol v2

New clients integrate against the frozen v2 WebSocket:

```text
WS /ws/v2
```

A v2 session opens with a strict `hello`/`hello.accepted` handshake, declares
its trigger sources (`manual`, `wake_word`, or both) and its wake-word
selection by canonical id, and is admitted atomically or refused with a
machine-readable reason. Every subsequent state change is server-authoritative
through one activation lifecycle shared by both trigger sources, projected as
versioned domain events (`eventId` / `eventSeq` / `stateVersion`), with
`session.snapshot` as the resync surface.

Session and server settings run through a versioned control plane, and wake
words resolve against one package-bundled catalog with no runtime downloads:

```text
GET   /api/v2/settings/schema
GET   /api/v2/settings/server
PATCH /api/v2/settings/server

GET   /api/v2/wake-words
POST  /api/v2/wake-words/refresh
```

The legacy `/ws/transcribe` (v1) transport remains a supported compatibility
path. v1 and v2 are isolated at the transport level and never fall back into
each other.

Full endpoint reference: [docs/v2-handbuch/04-schnittstellen/04.01-schnittstellenuebersicht.md](docs/v2-handbuch/04-schnittstellen/04.01-schnittstellenuebersicht.md).
The canonical v2 client contract (handshake, commands, acks, events, audio
framing, snapshot/resync, wake words, settings) starts at
[docs/.archiv/stand_vor_handbuch_2026-11-16/client-development/README.md](docs/.archiv/stand_vor_handbuch_2026-11-16/client-development/README.md).
Legacy v1 documentation is kept separately under
[docs/.archiv/stand_vor_handbuch_2026-11-16/client-development/legacy-v1](docs/.archiv/stand_vor_handbuch_2026-11-16/client-development/legacy-v1/README.md)
and must not be used for new clients.

---

## Models

Production deployments run **offline**: automatic model downloads are disabled
and models are resolved from configured directories or read-only volumes. The
model management authority validates that a model matches the installed runtime
variant, so a licensed Pro model can never be loaded silently by a Free
runtime.

See [docs/v2-handbuch/02-funktionsweise/02.07-modelle-und-modellverwaltung.md](docs/v2-handbuch/02-funktionsweise/02.07-modelle-und-modellverwaltung.md).

---

## Containers

One production image is intended for publication in both registries:

```text
marcosudau/voice-stt-server            ghcr.io/marcosudau-vps/voice-stt-server
```

Each release publishes an immutable exact tag (`2.0.0`) plus the movable
aliases `2.0`, `2` and `latest` for stable releases. The image contains the
Pro-capable runtime; model entitlement is checked separately at runtime.

The image is CPU-only, runs as a non-root user, and exposes port `8010`. It
installs the complete pre-built product wheel and never compiles Kroko during
the image build. Build it locally with:

```bash
python tools/build_production.py all
```

See [`build/BUILD.md`](build/BUILD.md) for the full build matrix, and
[docs/v2-handbuch/06-betrieb/06.03-windows-installation.md](docs/v2-handbuch/06-betrieb/06.03-windows-installation.md) for the tested
Windows setup.

---

## Release model

A VoiceSTT release is produced by GitHub-hosted automation from an exact source
commit — no operator machine is part of the release authority. The bytes and
container manifests that were qualified are the ones that get published; nothing
is rebuilt after qualification.

```text
exact commit -> candidate build + qualification -> approval
  -> git tag -> PyPI (voice-stt-server) -> Docker Hub -> GHCR (manifest promotion)
  -> verification -> movable aliases -> GitHub Release -> final verification
```

The immutable Git tag exists before the first irreversible public write, a
partially published version resumes under the same version instead of being
abandoned, conflicting or unverifiable remote state stops the release, and the
GitHub Release is the last public success marker.

Full description and the operator setup checklist:
[docs/v2-handbuch/ressourcen/release-process.md](docs/v2-handbuch/ressourcen/release-process.md).

---

## Documentation

**Getting started**

- [Quick start](docs/v2-handbuch/06-betrieb/06.06-ersteinrichtung.md)
- [Installation](docs/v2-handbuch/06-betrieb/06.02-installationskonzept.md)
- [Configuration reference](docs/v2-handbuch/03-konfiguration/03.07-session-einstellungen.md)
- [External audio](docs/v2-handbuch/04-schnittstellen/04.05-audiotransport.md)

**Engines and models**

- [Transcription engines](docs/v2-handbuch/02-funktionsweise/02.06-engines.md)
- [Faster-Whisper](docs/v2-handbuch/02-funktionsweise/02.06-engines.md)
- [Kroko-ONNX](docs/v2-handbuch/02-funktionsweise/02.06-engines.md)
- [STT model management](docs/v2-handbuch/02-funktionsweise/02.07-modelle-und-modellverwaltung.md)
- [Wake words](docs/v2-handbuch/02-funktionsweise/02.04-wake-word.md)

**Server**

- [FastAPI server](docs/v2-handbuch/04-schnittstellen/04.01-schnittstellenuebersicht.md)
- [OpenAI-compatible HTTP module](docs/v2-handbuch/04-schnittstellen/04.10-openai-kompatible-api.md)
- [Server authentication and SecurityService](docs/v2-handbuch/05-administration/05.01-sicherheitsarchitektur.md)
- [Client development](docs/.archiv/stand_vor_handbuch_2026-11-16/client-development/README.md)
- [Trigger architecture](docs/v2-handbuch/02-funktionsweise/02.03-activation.md)
- [Structured logging](docs/v2-handbuch/06-betrieb/06.09-logging.md)
- [API compatibility](docs/v2-handbuch/09-anhaenge/09.05-kompatibilitaetsvertraege.md)

**Build, release and operations**

- [Build reference](build/BUILD.md)
- [Release process and operator setup](docs/v2-handbuch/ressourcen/release-process.md)
- [Windows / CPU deployment](docs/v2-handbuch/06-betrieb/06.03-windows-installation.md)
- [Troubleshooting](docs/v2-handbuch/06-betrieb/06.12-fehlerdiagnose.md)
- [Engine licenses](docs/v2-handbuch/ressourcen/licenses.md)

**Development**

- [Documentation overview](docs/v2-handbuch/README.md)
- [Module map](docs/v2-handbuch/07-entwicklung/07.02-repository-architektur.md)
- [Testing](docs/v2-handbuch/07-entwicklung/07.06-testverfahren.md)
- [Test scripts](docs/v2-handbuch/07-entwicklung/07.06-testverfahren.md)

---

## Development and testing

```bash
python -m pip install -e ".[recommended,server]"
python -m pip install -r requirements-dev.txt
python -m pytest -q tests/unit
```

`tests/unit` is the fast suite that CI runs on Ubuntu 24.04 and Windows with
Python 3.12; it needs no model downloads, no network and no GPU. Real-model and
hardware tests are opt-in and separate — see [docs/v2-handbuch/07-entwicklung/07.06-testverfahren.md](docs/v2-handbuch/07-entwicklung/07.06-testverfahren.md).

Larger changes to architecture, public protocols, persisted formats, security
boundaries or deployment structure follow the process in
[docs/.archiv/README.md](docs/.archiv/README.md): a dated plan before the change
and a dated plan-versus-implementation review afterwards. The archive is a
historical record — the current reference documentation under `docs/` is updated
as part of the same change.

---

## Security and licensing

VoiceSTT is released under the MIT License (see [LICENSE](LICENSE)).

Bundled and optional third-party runtimes and model families carry their own
licenses; the Kroko-ONNX runtime embedded in each distribution ships its license
text inside the wheel. Kroko Pro models additionally require a commercial
license from Kroko/Banafo. See [docs/v2-handbuch/ressourcen/licenses.md](docs/v2-handbuch/ressourcen/licenses.md).

The release process holds no long-lived PyPI token — publication uses PyPI
Trusted Publishing (OIDC) — and container registry credentials live only in a
protected, approval-gated GitHub Environment. No credential is ever written to
a release manifest, release state or log. Runtime license keys are supplied at
run time only and are never build inputs.

Please report security issues privately through GitHub's security advisory form
on this repository rather than in a public issue.

---

## Contributing

Small, focused changes with tests are easiest to review. Please run
`python -m pytest -q tests/unit` before opening a pull request, and see
[docs/v2-handbuch/07-entwicklung/07.06-testverfahren.md](docs/v2-handbuch/07-entwicklung/07.06-testverfahren.md) for what belongs in the fast suite versus the
opt-in real-model suite.

If VoiceSTT is useful to you, a GitHub star genuinely helps: it is the main way
the project gets found, tested on real hardware, and improved.
