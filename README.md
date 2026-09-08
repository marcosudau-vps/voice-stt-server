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

## Two distributions: Free and Pro

Kroko-ONNX Free and Kroko-ONNX Pro are different native runtimes and cannot be
swapped at runtime. VoiceSTT therefore ships as **two complete, alternative
distributions**, each with its matching runtime already inside it:

| | Free | Pro |
| --- | --- | --- |
| PyPI distribution | `voice-stt-server` | `voice-stt-server-pro` |
| Container image | `voice-stt-server` | `voice-stt-server-pro` |
| Embedded Kroko runtime | Free | Pro |
| Kroko Community models | yes | yes |
| Kroko licensed Pro models | no | yes (runtime key required) |

Both expose the **same import package and the same CLI**, so nothing in your
application changes when you move between them:

```python
from voice_stt_server import AudioToTextRecorder
```

Three consequences worth stating plainly:

- **The installed distribution decides the runtime.** A Pro license key is a
  runtime credential for a Pro runtime that is already installed; it never
  turns a Free installation into a Pro one.
- **They are alternatives, not layers.** Install one or the other into an
  environment, never both.
- **No native build.** Neither distribution asks you to compile Kroko or to
  install a separate wheel afterwards.

---

## Installation

Supported targets for the two public distributions are **CPython 3.12** on
**Linux x86-64** and **Windows x86-64**. That is the matrix the embedded native
runtime is actually built and qualified for, so it is the only matrix the
packaging claims.

```bash
# Free
pip install voice-stt-server

# Pro
pip install voice-stt-server-pro
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
[`build/BUILD.md`](build/BUILD.md) and [docs/installation.md](docs/installation.md).

---

## Speech recognition engines

Two engines are supported, documented and qualified as the production surface:

| Engine | Use it for | Guide |
| --- | --- | --- |
| `faster_whisper` | The default. Mature Whisper transcription, CPU or GPU, broad language coverage. | [docs/faster-whisper.md](docs/faster-whisper.md) |
| `kroko_onnx` | Low-latency local streaming recognition with Kroko/Banafo `.data` models, Community or licensed Pro. | [docs/kroko-onnx.md](docs/kroko-onnx.md) |

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
not documented here. See [docs/transcription-engines.md](docs/transcription-engines.md).

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

More patterns: [docs/quick-start.md](docs/quick-start.md) and
[docs/external-audio.md](docs/external-audio.md).
Every constructor parameter is documented in
[docs/configuration.md](docs/configuration.md).

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

Full endpoint reference: [docs/fastapi-server.md](docs/fastapi-server.md).
Complete wire contract, event catalog and client state model:
[docs/client-development](docs/client-development/README.md).

---

## Models

Production deployments run **offline**: automatic model downloads are disabled
and models are resolved from configured directories or read-only volumes. The
model management authority validates that a model matches the installed runtime
variant, so a licensed Pro model can never be loaded silently by a Free
runtime.

See [docs/stt-model-management.md](docs/stt-model-management.md).

---

## Containers

Two production images are published per release, mirroring the two
distributions:

```text
marcosudau/voice-stt-server            ghcr.io/marcosudau-vps/voice-stt-server
marcosudau/voice-stt-server-pro        ghcr.io/marcosudau-vps/voice-stt-server-pro
```

Each release publishes an immutable exact tag (`2.0.0`) plus the movable
aliases `2.0`, `2` and `latest`. Free/Pro is a build-time identity: it is fixed
by which image you run, never inferred from a runtime key.

The images are CPU-only, run as a non-root user, and expose port `8010`. They
install pre-built wheels and never compile anything at image-build time. Build
them locally with:

```bash
python tools/build_production.py all
```

See [`build/BUILD.md`](build/BUILD.md) for the full build matrix, and
[docs/windows-cpu-deployment.md](docs/windows-cpu-deployment.md) for the tested
Windows setup.

---

## Release model

A VoiceSTT release is produced by GitHub-hosted automation from an exact source
commit — no operator machine is part of the release authority. The bytes and
container manifests that were qualified are the ones that get published; nothing
is rebuilt after qualification.

```text
exact commit -> candidate build + qualification -> approval
  -> git tag -> PyPI (Free + Pro) -> Docker Hub -> GHCR (manifest promotion)
  -> verification -> movable aliases -> GitHub Release -> final verification
```

The immutable Git tag exists before the first irreversible public write, a
partially published version resumes under the same version instead of being
abandoned, conflicting or unverifiable remote state stops the release, and the
GitHub Release is the last public success marker.

Full description and the operator setup checklist:
[docs/release-process.md](docs/release-process.md).

---

## Documentation

**Getting started**

- [Quick start](docs/quick-start.md)
- [Installation](docs/installation.md)
- [Configuration reference](docs/configuration.md)
- [External audio](docs/external-audio.md)

**Engines and models**

- [Transcription engines](docs/transcription-engines.md)
- [Faster-Whisper](docs/faster-whisper.md)
- [Kroko-ONNX](docs/kroko-onnx.md)
- [STT model management](docs/stt-model-management.md)
- [Wake words](docs/wake-words.md)

**Server**

- [FastAPI server](docs/fastapi-server.md)
- [Client development](docs/client-development/README.md)
- [Trigger architecture](docs/einheitliche-triggerarchitektur.md)
- [Structured logging](docs/structured-logging.md)
- [API compatibility](docs/api-compatibility.md)

**Build, release and operations**

- [Build reference](build/BUILD.md)
- [Release process and operator setup](docs/release-process.md)
- [Windows / CPU deployment](docs/windows-cpu-deployment.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Engine licenses](docs/licenses.md)

**Development**

- [Documentation overview](docs/README.md)
- [Module map](docs/module-map.md)
- [Testing](docs/testing.md)
- [Test scripts](docs/test-scripts.md)

---

## Development and testing

```bash
python -m pip install -e ".[recommended,server]"
python -m pip install -r requirements-dev.txt
python -m pytest -q tests/unit
```

`tests/unit` is the fast suite that CI runs on Ubuntu 24.04 and Windows with
Python 3.12; it needs no model downloads, no network and no GPU. Real-model and
hardware tests are opt-in and separate — see [docs/testing.md](docs/testing.md).

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
license from Kroko/Banafo. See [docs/licenses.md](docs/licenses.md).

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
[docs/testing.md](docs/testing.md) for what belongs in the fast suite versus the
opt-in real-model suite.

If VoiceSTT is useful to you, a GitHub star genuinely helps: it is the main way
the project gets found, tested on real hardware, and improved.
