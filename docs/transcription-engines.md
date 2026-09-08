# Transcription Engines

VoiceSTT routes speech recognition through a lazy-loaded engine factory.
`AudioToTextRecorder` selects the main final-transcription backend with
`transcription_engine`; live transcription can use the same backend or a
different one via `realtime_transcription_engine`.

## Supported production engines

Exactly two engines are supported, documented and qualified as the production
surface. Both are installed and ready in the public distributions
(`voice-stt-server` / `voice-stt-server-pro`) — there is nothing extra to
install or compile.

| Engine names | Role | Guide |
| --- | --- | --- |
| `faster_whisper` | Default production backend. Whisper transcription through CTranslate2, CPU or GPU, broad language coverage. | [faster-whisper.md](faster-whisper.md) |
| `kroko_onnx`, `kroko`, `banafo_kroko` | Local streaming recognition with Kroko/Banafo `.data` models and low-latency live previews. | [kroko-onnx.md](kroko-onnx.md) |

The compatibility default is `faster_whisper`.

Engine names are normalised by replacing `-` with `_`, so both Python-style and
CLI-style spellings work.

## About the other adapters in the source tree

`VoiceSTT/transcription_engines/` still contains lazily-loaded adapters for
other engine families (whisper.cpp, OpenAI Whisper, sherpa-onnx, Parakeet,
Moonshine, Transformers-based models, and others).

They are **internal and experimental**, and this documentation deliberately no
longer describes them as product features:

- they are not part of the supported production surface;
- they are not built, qualified or verified by the release process;
- their optional dependencies are not installed by the public distributions;
- they receive no compatibility guarantee across releases.

They are kept in the source tree because removing them would be an unrelated
compatibility break, not because they are recommended. If you use one, you are
using an internal interface and you own the dependency management for it.

## Selecting a backend

Use the default:

```python
from voice_stt_server import AudioToTextRecorder

recorder = AudioToTextRecorder(
    model="small.en",
    transcription_engine="faster_whisper",
)
```

Use Kroko for low-latency live previews and Faster-Whisper for the final,
higher-quality transcript:

```python
from voice_stt_server import AudioToTextRecorder

recorder = AudioToTextRecorder(
    transcription_engine="faster_whisper",
    model="small.en",
    enable_realtime_transcription=True,
    realtime_transcription_engine="kroko_onnx",
)
```

If `realtime_transcription_engine` is `None`, live transcription uses the same
backend as `transcription_engine`.

## Engine-specific options

`transcription_engine_options` and `realtime_transcription_engine_options` pass
backend-specific dictionaries straight through:

```python
recorder = AudioToTextRecorder(
    transcription_engine="kroko_onnx",
    transcription_engine_options={"num_threads": 2},
)
```

These dictionaries are intentionally backend-specific. A key that is meaningful
for one engine may be ignored or invalid for another.

## Model behaviour

| Engine | Automatic download | Manual placement |
| --- | --- | --- |
| `faster_whisper` | Yes, for known Hugging Face / CTranslate2 model ids — **disabled in production deployments**, which run offline. | A local CTranslate2 model directory may be passed as `model`. |
| `kroko_onnx` | Yes, for known public Community `.data` files when enabled — likewise disabled in production. | Pro/private models need an existing `.data` path, a direct URL, or explicit repo/token options. |

Production images and offline deployments resolve models from configured
directories or read-only volumes instead of downloading them. The model
authority also refuses a model whose required runtime variant does not match the
installed one, so a licensed Pro model can never be loaded by a Free runtime.
See [stt-model-management.md](stt-model-management.md).

## Free and Pro

Kroko Free and Kroko Pro are different native runtimes. Which one you have is
decided by which distribution or image you installed
(`voice-stt-server` vs `voice-stt-server-pro`), never by a runtime license key —
the key is a credential for an already-installed Pro runtime. See
[kroko-onnx.md](kroko-onnx.md) and [../build/BUILD.md](../build/BUILD.md).

## Extending

A new engine implements `BaseTranscriptionEngine`, returns `TranscriptionResult`
and is registered in `VoiceSTT/transcription_engines/factory.py`. Keep imports
lazy so optional dependencies are only imported when the engine is selected.

Contract tests should cover missing-dependency messages, parameter mapping,
audio normalisation, result conversion and factory selection. Real-model tests
stay opt-in.
