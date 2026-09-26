# Wake Words

The `AudioToTextRecorder` library supports Porcupine and OpenWakeWord to wait
for a wake word before recording the following speech. The FastAPI server's
current admin, browser, and session contracts deliberately publish only
OpenWakeWord.

Install the OpenWakeWord extra:

```bash
python -m pip install "VoiceSTT[openwakeword]"
```

For the library-level Porcupine backend instead:

```bash
python -m pip install "VoiceSTT[porcupine]"
```

```python
from VoiceSTT import AudioToTextRecorder

recorder = AudioToTextRecorder(
    wakeword_backend="pvporcupine",
    wake_words="jarvis",
)
```

If `wake_words` is set without an explicit backend, the recorder selects
Porcupine for backward compatibility. This Porcupine path is a library feature;
it is not selectable through the current FastAPI session or admin contract.

## Bundled and local model catalog

VoiceSTT never downloads Wake Word assets at runtime. V1 ships fourteen ONNX
classifiers plus the required feature pipeline:

| Logical ID | Spoken phrase |
| --- | --- |
| `hey_jarvis` | Hey Jarvis |
| `alexa` | Alexa |
| `hey_mycroft` | Hey Mycroft |
| `hey_rhasspy` | Hey Rhasspy |
| `computer` | Computer |
| `hey_nabu` | Hey Nabu |
| `hey_rocky` | Hey Rocky |
| `jarvis` | Jarvis |
| `stop` | Stop |
| `hey_alfred` | Hey Alfred |
| `hey_billy` | Hey Billy |
| `hey_bro` | Hey Bro |
| `hey_glados` | Hey Glados |
| `hey_mira` | Hey Mira |

`hey_jarvis` is the default. These files make Wake Word mode usable without a
model mount. Their non-commercial/share-alike terms and hashes are recorded in
`VoiceSTT/assets/wakeword_models/ATTRIBUTION.md` and `models.json`.

An external `models.json` or directory extends the bundled catalog. A model
with the same logical ID overrides its bundled counterpart. Set the external
search root with:

```bash
VOICESTT_OPENWAKEWORD_MODEL_ROOT=/models/openwakeword
```

Relevant manifest structure:

```json
{
  "openwakeword_models": {
    "path": "/models/openwakeword/all_models",
    "default_model": "alexa",
    "pipeline_models": {
      "embedding_model_onnx": "embedding_model.onnx",
      "melspectrogram_onnx": "melspectrogram.onnx",
      "embedding_model_tflite": "embedding_model.tflite",
      "melspectrogram_tflite": "melspectrogram.tflite"
    },
    "onnx_models": {
      "alexa": "alexa.onnx",
      "hey_jarvis": "jarvis_v2.onnx"
    },
    "tflite_models": {
      "alexa": "alexa.tflite"
    }
  }
}
```

The dictionary keys are stable logical Wake Word IDs; the values are local
filenames. Only entries whose files exist are exposed. Pipeline models and
support files such as `silero_vad` are not selectable Wake Words.

The manifest `path` is tried first. If that platform-specific path is not
available in the running container or host, VoiceSTT also checks the configured
model root and the manifest directory. This allows the same generated manifest
to remain usable after a model directory is mounted at a different path.

`openwakeword_model_paths` remains backward compatible. It may contain:

- one or more comma-separated `.onnx` or `.tflite` classifier paths;
- a directory containing models and optionally `models.json`;
- the path to `models.json` itself.

Without a usable external manifest, VoiceSTT scans external `.onnx` and
`.tflite` files and merges them with the bundled catalog. A manifest is
recommended because it provides exact logical IDs, the default model and
pipeline-file mappings.

## Python recorder

Direct classifier paths remain supported:

```python
from VoiceSTT import AudioToTextRecorder

if __name__ == "__main__":
    recorder = AudioToTextRecorder(
        wakeword_backend="openwakeword",
        openwakeword_model_paths="/models/openwakeword/alexa.onnx",
        wake_words="alexa",
        wake_words_sensitivity=0.35,
        wake_word_buffer_duration=1.0,
    )
    print(recorder.text())
    recorder.shutdown()
```

Using the manifest:

```python
recorder = AudioToTextRecorder(
    wakeword_backend="openwakeword",
    openwakeword_model_paths="/models/openwakeword/models.json",
    wake_words="hey_jarvis",
)
```

Model IDs are resolved case-insensitively. An empty `wake_words` value selects
`default_model` when the manifest is used.

Supported inference frameworks are `onnx` and `tflite`, selected with
`openwakeword_inference_framework`.

## FastAPI session-local configuration

The WebSocket endpoint resolves Wake Word configuration before creating the
session recorder:

```text
/ws/transcribe?wakeWordEnabled=false
/ws/transcribe?wakeWordEnabled=true
/ws/transcribe?wakeWordEnabled=true&wakeWords=hey_jarvis
```

Clients send logical model IDs, not filesystem paths. The effective result,
fallbacks and available IDs are returned in `hello.sessionConfig` and
`hello.sessionCapabilities`. A session can choose a locally available ONNX or
TensorFlow Lite variant with `wakeWordInferenceFramework=onnx` or
`wakeWordInferenceFramework=tflite`.

See
[Betriebsmodi und sessionlokale Wake-Word-Konfiguration](client-development/09-betriebsmodi-und-serverkonfiguration.md)
for the complete contract.

## Sensitivity and timing

| Parameter | Default | Meaning |
| --- | --- | --- |
| `wake_words_sensitivity` | `0.6` | Detection threshold from `0` to `1`; lower values can increase false positives |
| `wake_word_activation_delay` | `0.0` | Delay before entering Wake Word mode when no initial speech is detected |
| `wake_word_timeout` | `5.0` | Seconds to wait for speech after detection |
| `wake_word_buffer_duration` | `0.1` | Audio removed/buffered around detection |
| `wake_word_followup_window` | server setting | Window in which follow-up speech can continue |

A sensitivity around `0.35` can be a useful starting point for custom models,
but it must be tuned against real microphones and room noise.

## Callbacks

```python
def detected():
    print("wake word detected")


def timeout():
    print("wake word timeout")


recorder = AudioToTextRecorder(
    wakeword_backend="openwakeword",
    openwakeword_model_paths="/models/openwakeword/models.json",
    on_wakeword_detected=detected,
    on_wakeword_timeout=timeout,
)
```

Available callbacks:

- `on_wakeword_detection_start`
- `on_wakeword_detection_end`
- `on_wakeword_detected`
- `on_wakeword_timeout`

## Troubleshooting

- Confirm that the manifest and every referenced classifier/pipeline file are
  readable inside the current host or container.
- Check `default_model` against the logical keys, including spelling.
- Use the admin Wake Word catalog or WebSocket `sessionCapabilities` to see
  which models passed validation.
- Raise sensitivity if false activations are common; lower it if detections are
  consistently missed.
- Increase `wake_word_buffer_duration` if the Wake Word appears in the final
  transcript.
