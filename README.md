# VoiceSTT

VoiceSTT is a Python speech-to-text library for applications that need
voice activity detection, fast transcription, optional realtime text updates,
wake words, and direct access to audio streams. It is designed for assistants,
dictation tools, browser streaming servers, and prototypes that need to turn
speech into text with only a few lines of code.

This checkout is configured as a CPU-only deployment. The supported production
path uses Faster Whisper, Kroko ONNX, Silero ONNX, OpenWakeWord and Porcupine.
Model downloads are disabled in deployment; existing model directories are
resolved from environment variables or read-only Docker volumes.

The central build and deployment reference is
[`build/BUILD.md`](build/BUILD.md). Server-specific files for Marcos VPS are
kept separately under [`build/vps`](build/vps/README.md).

## V1.0.0 preservation packages

The preserved V1.0.0 public products target **CPython 3.12** on Linux x86_64
and Windows AMD64:

```bash
pip install voice-stt-server
# or, for the licensed Pro runtime:
pip install voice-stt-server-pro
```

These published platform wheels already contain the matching Kroko native
runtime. End users do **not** compile Kroko and do not install a second Kroko
wheel. Kroko `.data` model files remain separate. The Free package uses the
Community model path; the Pro package never auto-downloads a private model and
requires a separately provisioned licensed model plus runtime credential.

See [V1 preservation release](docs/v1-preservation-release.md) for the exact
release contract. `stt-install-kroko --build` remains available for developers
and source builds only.

## Support VoiceSTT

If VoiceSTT saved you time, one GitHub star is a simple way to help make it more stable.

Stars improve visibility and visibility brings more users, more real-world testing, more bug reports, more fixes, and better releases for everyone.

## Demo

`https://github.com/user-attachments/assets/797e6552-27cd-41b1-a7f3-e5cbc72094f5`

[CLI demo code (reproduces the video above)](tests/realtimestt_test.py)

## Featured Integration: Kroko/Banafo ASR

VoiceSTT includes native support for `kroko_onnx`, the local streaming ASR
engine from the Kroko/Banafo team.

For normal V1.0.0 consumers, Kroko is already embedded by the public package
shown above. The builder flow below is specifically for source/developer work:

```bash
pip install "voice-stt-server[kroko-builder,silero-onnx-cpu]"
stt-install-kroko --build --variant free
```

Use `--variant pro` only when intentionally building a licensed Pro runtime;
the API/license key is supplied at runtime, not as a build input. See the
[build guide](build/BUILD.md#kroko-im-detail),
[Kroko-ONNX engine guide](docs/engines/kroko-onnx.md), and
[Kroko ASR docs](https://docs.kroko.ai/on-premise/).

## Install

For the V1 preservation release, use Python 3.12 and one of the two product
packages above. Optional backends remain available as extras, for example:

```bash
pip install "voice-stt-server[faster-whisper]"
```

On Linux, install PortAudio headers before installing the package:

```bash
sudo apt-get update
sudo apt-get install python3-dev portaudio19-dev
```

On macOS:

```bash
brew install portaudio
```

For the tested Windows venv and Docker setup, see
[docs/windows-cpu-deployment.md](docs/windows-cpu-deployment.md).

## Microphone Example

```python
from VoiceSTT import AudioToTextRecorder

if __name__ == "__main__":
    with AudioToTextRecorder() as recorder:
        print("Speak now")
        print(recorder.text())
```

Use the `if __name__ == "__main__":` guard when running scripts, especially on
Windows, because VoiceSTT uses multiprocessing for model work.

## Automatic Recording Loop

```python
from VoiceSTT import AudioToTextRecorder


def process_text(text):
    print(text)


if __name__ == "__main__":
    recorder = AudioToTextRecorder()
    while True:
        recorder.text(process_text)
```

## External Audio

Set `use_microphone=False` when audio comes from a file, stream, websocket, or
another process. Feed 16-bit mono PCM chunks at 16 kHz, or pass the original
sample rate so VoiceSTT can resample:

```python
from VoiceSTT import AudioToTextRecorder

if __name__ == "__main__":
    recorder = AudioToTextRecorder(use_microphone=False)
    with open("audio_chunk.pcm", "rb") as audio_file:
        recorder.feed_audio(audio_file.read(), original_sample_rate=16000)
    print(recorder.text())
    recorder.shutdown()
```

More examples are in [docs/quick-start.md](docs/quick-start.md) and
[docs/external-audio.md](docs/external-audio.md).

## Configuration Reference

All project and deployment defaults live in the versioned root
[`config.yaml`](config.yaml). It is grouped into `settings`, `deployment` and
`example_app`. The only local env file is `.env`, and it contains credentials
only. It is ignored by Git.

Docker model paths are selected automatically from the existing candidates in
`deployment.model_paths`. A new machine therefore requires no change when one
of those paths exists; otherwise add one candidate in that single section.

Every `AudioToTextRecorder` constructor parameter is documented in
[docs/configuration.md](docs/configuration.md), including model/engine
selection, realtime transcription, VAD timing, wake words, callbacks, external
audio, logging, and executor injection.

## Features

- Voice activity detection with WebRTC VAD and Silero VAD.
- Final and realtime transcription with selectable engines.
- Optional wake word activation through Porcupine or OpenWakeWord.
- Session-local OpenWakeWord selection for FastAPI WebSocket clients without changing the server baseline or other sessions.
- Direct microphone input or application-fed audio chunks.
- Event callbacks for recording, VAD, realtime text, transcription, and wake word state.
- A FastAPI browser streaming server example with multi-user session isolation, shared inference resources, metrics, and health endpoints.
- Four SQLite-first structured server event channels with calendar JSONL mirrors, indexed history, session-scoped client access, server-wide Admin history/live access, and a separate replayable log WebSocket.

## Documentation

- [V1 preservation release](docs/v1-preservation-release.md): exact V1.0.0 packaging, qualification, and publication contract.
- [Build and deployment](build/BUILD.md): canonical package, Docker and Kroko build paths, validation and rollback.
- [Marcos VPS deployment](build/vps/README.md): server-only paths, configuration and release automation.
- [Documentation overview](docs/README.md): authoritative guides, client contract, and archive process.
- [Quick start](docs/quick-start.md)
- [Windows CPU deployment](docs/windows-cpu-deployment.md)
- [Configuration](docs/configuration.md)
- [Transcription engines](docs/transcription-engines.md)
- [Wake words](docs/wake-words.md)
- [External audio](docs/external-audio.md)
- [Testing](docs/testing.md)
- [Test scripts](docs/test-scripts.md)
- [FastAPI server](docs/fastapi-server.md)
- [Structured logging](docs/structured-logging.md)
- [Session-local Wake Word](docs/session-wakeword-erweiterung.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Engine licenses](docs/licenses.md)

### Process for larger changes

Larger changes to architecture, public protocols or APIs, persisted formats,
security boundaries, deployment structure, or cross-module behavior must be
registered in the [archive for larger change actions](docs/.archiv/README.md)
before implementation begins. Every action requires a dated overall plan and a
later plan-versus-implementation review. Material deviations require their own
rationale file.

Engine-specific references:

- [faster-whisper](docs/engines/faster-whisper.md)
- [whisper.cpp](docs/engines/whisper-cpp.md)
- [OpenAI Whisper](docs/engines/openai-whisper.md)
- [Moonshine](docs/engines/moonshine.md)
- [sherpa-onnx](docs/engines/sherpa-onnx.md)
- [Kroko-ONNX](docs/engines/kroko-onnx.md)
- [Parakeet NeMo](docs/engines/parakeet-nemo.md)
- [Meta Omnilingual ASR](docs/engines/omnilingual-asr.md)
- [Granite/Qwen Transformers engines](docs/engines/hf-transformers.md)
- [Cohere Transcribe](docs/engines/cohere.md)
- [FunASR](docs/engines/funasr.md)

## Server Example

The browser FastAPI server is also the installed `VoiceSTT_server` production
entry point. It provides independent multi-user WebSockets and the
OpenAI-compatible transcription route through one shared model scheduler.

```bash
.\install_windows_cpu.ps1
python .\tools\compose.py up --build -d
```

This is the portable development path. Marcos VPS uses the separate,
Pro-aware release process under [build/vps](build/vps/README.md). Open
`http://localhost:8010` for the local setup. See
[docs/fastapi-server.md](docs/fastapi-server.md) for engine recipes, websocket
protocol details, health checks, and metrics.

## Contributing

Focused tests and small changes are easiest to review. The project keeps fast
unit tests separate from opt-in real-model tests; see [docs/testing.md](docs/testing.md).

## License

MIT
