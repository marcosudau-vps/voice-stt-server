# Configuration

The repository has one versioned runtime configuration:
[`config.yaml`](../config.yaml). Server defaults are under `settings`, portable
Docker paths and ports under `deployment`, and desktop-example defaults under
`example_app`. Credentials are deliberately rejected from YAML and belong only
in the ignored root `.env`.

`AudioToTextRecorder` is the main library entry point. This page is a parameter
reference for its constructor. Examples and recommended starting patterns live
in [quick-start.md](quick-start.md).

This page covers every public constructor parameter, grouped by purpose so the
reference stays searchable without making the README too large.

```python
from VoiceSTT import AudioToTextRecorder

recorder = AudioToTextRecorder(
    model="small.en",
    language="en",
    enable_realtime_transcription=True,
)
```

## Model And Engine Parameters

| Parameter | Default | Description |
| --- | --- | --- |
| `model` | `"tiny"` | Main transcription model name or model path. Interpretation depends on `transcription_engine`. |
| `transcription_engine` | `"faster_whisper"` | Main transcription backend. See [transcription-engines.md](transcription-engines.md). |
| `transcription_engine_options` | `None` | Engine-specific dictionary passed only to the main backend. |
| `download_root` | `None` | Directory for model downloads or lookup. Behavior is engine-specific. |
| `language` | `""` | Language code. Empty string lets engines auto-detect when they support it. Some engines require a language. |
| `compute_type` | `"default"` | Numeric precision/quantization hint. For faster-whisper, see CTranslate2 quantization. Other engines map this where possible. |
| `gpu_device_index` | `0` | GPU id, or a list of GPU ids for compatible engines. |
| `device` | `"cuda"` | Device hint, usually `"cuda"` or `"cpu"`. CPU-only engines ignore GPU settings. |
| `batch_size` | `16` | Main transcription batch size. Set `0` to disable batched faster-whisper inference. |
| `beam_size` | `5` | Main transcription beam size where supported. |
| `initial_prompt` | `None` | String or token iterable passed to the main engine as prompt/context where supported. |
| `suppress_tokens` | `[-1]` | Token ids suppressed by Whisper-family engines where supported. |
| `faster_whisper_vad_filter` | `True` | Enables faster-whisper's own VAD filter during transcription in addition to recorder VAD. |
| `normalize_audio` | `False` | Normalizes audio peak before transcription in engine adapters that use the shared normalization helper. |

## Audio Input Parameters

| Parameter | Default | Description |
| --- | --- | --- |
| `input_device_index` | `None` | PyAudio input device index. `None` lets PyAudio choose the default device. |
| `use_microphone` | `True` | When `False`, audio must be supplied through `feed_audio()`. |
| `buffer_size` | `512` | Recorder audio buffer size. Changing this can affect VAD behavior. |
| `sample_rate` | `16000` | Recorder sample rate. WebRTC VAD is sensitive to sample rate changes. |
| `handle_buffer_overflow` | platform-dependent | Logs and drops overflowed microphone input. Defaults to `True` except on macOS. |
| `allowed_latency_limit` | `100` | Maximum unprocessed input chunks before old chunks may be discarded. |
| `on_recorded_chunk` | `None` | Callback receiving each recorded audio chunk. |

## Text Formatting And Lifecycle

| Parameter | Default | Description |
| --- | --- | --- |
| `ensure_sentence_starting_uppercase` | `True` | Capitalizes detected sentence starts. |
| `ensure_sentence_ends_with_period` | `True` | Adds a final period when final text does not end in punctuation. |
| `spinner` | `True` | Shows the console state spinner. |
| `level` | `logging.WARNING` | Logger level used by the recorder. |
| `debug_mode` | `False` | Prints additional debug information. |
| `print_transcription_time` | `False` | Logs main transcription processing time. |
| `no_log_file` | `False` | Skips the debug log file. |
| `use_extended_logging` | `False` | Enables more detailed recording worker logs. |
| `start_callback_in_new_thread` | `False` | Runs callbacks in new threads instead of the recorder thread. |

## Recording And VAD Parameters

| Parameter | Default | Description |
| --- | --- | --- |
| `silero_sensitivity` | `0.4` | Silero VAD sensitivity, from `0` to `1`. |
| `silero_use_onnx` | `False` | Uses Silero's ONNX path instead of the PyTorch path. |
| `silero_deactivity_detection` | `False` | Uses Silero for end-of-speech detection instead of the default WebRTC end detection path. |
| `deactivity_silence_confirmation_duration` | `0.16` | Required continuous VAD silence before end-of-speech silence is confirmed. |
| `webrtc_sensitivity` | `3` | WebRTC VAD aggressiveness from `0` to `3`; higher is more aggressive and less sensitive. |
| `warmup_vad` | `True` | Runs a small VAD warmup during initialization to avoid first-chunk lazy setup cost. |
| `post_speech_silence_duration` | `0.6` | Required silence after speech before a recording is considered complete. |
| `min_length_of_recording` | `0.5` | Minimum recording duration in seconds. |
| `min_gap_between_recordings` | `0` | Minimum gap in seconds between recordings. |
| `pre_recording_buffer_duration` | `1.0` | Amount of pre-roll audio to keep before detected speech. |
| `early_transcription_on_silence` | `0` | Starts an early final transcription after this many milliseconds of silence; the result is discarded if speech resumes. |

## Realtime Transcription Parameters

| Parameter | Default | Description |
| --- | --- | --- |
| `enable_realtime_transcription` | `False` | Enables interim transcription while recording is still active. |
| `use_main_model_for_realtime` | `False` | Reuses the main model for realtime updates instead of loading a separate realtime model. |
| `realtime_transcription_engine` | `None` | Realtime backend. `None` uses `transcription_engine`. |
| `realtime_transcription_engine_options` | `None` | Engine-specific options for realtime. `None` reuses `transcription_engine_options`. |
| `realtime_model_type` | `"tiny"` | Realtime model name or path. |
| `realtime_processing_pause` | `0.2` | Seconds between realtime transcription attempts. Lower values increase load. |
| `init_realtime_after_seconds` | `0.2` | Initial delay after recording starts before the first realtime update. |
| `realtime_batch_size` | `16` | Realtime transcription batch size. |
| `beam_size_realtime` | `3` | Realtime beam size where supported. |
| `initial_prompt_realtime` | `None` | Prompt/context for the realtime model where supported. |
| `realtime_transcription_use_syllable_boundaries` | `False` | Schedules realtime updates from a lightweight acoustic boundary detector instead of only a fixed timer. |
| `realtime_boundary_detector_sensitivity` | `0.6` | Boundary detector sensitivity, from conservative `0` to eager `1`. |
| `realtime_boundary_followup_delays` | `(0.05, 0.2)` | Extra realtime update delays after a detected boundary. `None` or empty disables follow-ups. |

## Wake Word Parameters

| Parameter | Default | Description |
| --- | --- | --- |
| `wakeword_backend` | `""` | Wake word backend. Use `"pvporcupine"`/`"pvp"` or `"oww"`/`"openwakeword"`. |
| `wake_words` | `""` | Comma-separated Wake Word keywords or logical OpenWakeWord model IDs. Also enables wake word mode. |
| `wake_words_sensitivity` | `0.6` | Wake word sensitivity from `0` to `1`. |
| `wake_word_activation_delay` | `0.0` | Delay before switching from normal voice activation to wake word activation. |
| `wake_word_timeout` | `5.0` | Seconds after wake word detection to wait for speech before returning to wake word mode. |
| `wake_word_buffer_duration` | `0.1` | Audio removed/buffered around wake word detection so the wake word is not included in the transcription. |
| `openwakeword_model_paths` | `None` | Comma-separated OpenWakeWord classifier paths, a model directory, or a `models.json` manifest path. |
| `openwakeword_inference_framework` | `"onnx"` | OpenWakeWord inference framework: `"onnx"` or `"tflite"`. |

Diese Parameter beschreiben den Recorder-/v1-Pfad. Der v2-Serverpfad verwendet
seit AP-SRV-060 den gebündelten Build-Katalog unter
`VoiceSTT/assets/wakeword_models/` und dessen `models.json` als Autorität; die
Sessionauswahl läuft über kanonische IDs im `hello`-Handshake. Details in
[Wake Words](wake-words.md). Ein abweichender Bundleort wird mit
`VOICESTT_WAKEWORD_ASSET_ROOT` gesetzt; Runtime-Downloads gibt es auf keinem
Pfad.

## Callback Parameters

All callbacks are optional. By default they run in the recorder flow; set
`start_callback_in_new_thread=True` if callbacks may block.

| Parameter | Called when |
| --- | --- |
| `on_recording_start` | A recording starts. |
| `on_recording_stop` | A recording stops. |
| `on_transcription_start` | Final transcription starts. |
| `on_realtime_transcription_update` | New interim realtime text is available. Receives text. |
| `on_realtime_transcription_stabilized` | Higher-quality stabilized realtime text is available. Receives text. |
| `on_realtime_text_stabilization_update` | Structured realtime stabilization event is available. |
| `on_vad_start` | Voice activity is detected. |
| `on_vad_stop` | Voice activity ends. |
| `on_vad_detect_start` | Recorder starts listening for voice activity. |
| `on_vad_detect_stop` | Recorder stops listening for voice activity. |
| `on_turn_detection_start` | Turn detection starts. |
| `on_turn_detection_stop` | Turn detection stops. |
| `on_wakeword_detected` | Wake word is detected. |
| `on_wakeword_timeout` | Wake word was detected but no speech arrived before timeout. |
| `on_wakeword_detection_start` | Wake word listening starts. |
| `on_wakeword_detection_end` | Wake word listening stops. |
| `on_recorded_chunk` | A raw recorded chunk is available. Receives bytes. |

## Executor Injection

| Parameter | Default | Description |
| --- | --- | --- |
| `transcription_executor` | `None` | Optional callable used instead of the default main transcription execution path. Primarily used by tests and server integration. |
| `realtime_transcription_executor` | `None` | Optional callable used instead of the default realtime transcription execution path. Primarily used by tests and shared-model server integration. |

## External Audio API

When `use_microphone=False`, call:

```python
recorder.feed_audio(chunk, original_sample_rate=16000)
```

`chunk` should be 16-bit mono PCM bytes. If `original_sample_rate` is not
16000, the recorder resamples before placing audio into its queue. More detail
lives in [external-audio.md](external-audio.md).

## Shutdown

Prefer the context manager:

```python
with AudioToTextRecorder() as recorder:
    print(recorder.text())
```

If you do not use `with`, call:

```python
recorder.shutdown()
```

## Server Runtime Settings (AP-SRV-050)

The server persistence document (`runtime.json`, unter `data_root_path/config/`)
ist ein Coexistenzformat: Die Legacysektion `settings` bleibt unverändert,
daneben existieren die AP-SRV-050-Sektionen `settingsControlOverlay` und
`settingsRevision`. Beide Schreibfamilien erhalten die jeweils fremden
Sektionen; es geht keine Top-Level-Sektion verloren. Secrets werden nie
persistiert.

Die serverautoritative Settings-Control-Plane verwaltet als triggerrelevant
`session`-Scoped Werte mit admin-managed Serverdefault:

| Key (public) | Typ | Standard | Bereich |
|---|---:|---:|---:|
| `activation.initialSpeechTimeoutMs` | int | 15000 | 100–3600000 |
| `activation.followupTimeoutMs` | int | 3000 | 100–60000 |
| `activation.segmentWatchdogInitialMs` | int | 600000 | 60000–3600000 |
| `activation.segmentWatchdogRefreshMs` | int | 180000 | 30000–600000 |
| `activation.segmentWatchdogWarningMs` | int | 30000 | >=5000, < wirksame Frist |
| `activation.closingRecoveryTimeoutMs` | int | 5000 | 1000–30000 |
| `wakeWord.sensitivity` | float | 0.5 | 0.0–1.0 |
| `wakeWord.minConsecutivePredictionFrames` | int | 1 | >= 1 |
| `wakeWord.cooldownMs` | int | 0 | >= 0 |
| `wakeWord.preRollMs` | int | 0 | >= 0 |
| `wakeWord.detectorGain` | float | 1.0 | 0.0–3.0 |
| `wakeWord.noiseSuppressionEnabled` | bool | `false` | – |
| `wakeWord.vadThreshold` | float | 0.0 | 0.0–1.0 |

`wakeWord.sensitivity` ist die gemeinsame Score-Schwelle aller ausgewählten
Wake Words, `wakeWord.minConsecutivePredictionFrames` die Mindestanzahl
aufeinanderfolgender OpenWakeWord-Prediction-Frames mit Score >= Schwelle,
bevor ein Trefferbereich qualifiziert. Gezählt werden ausschließlich echte neue
Prediction-Frames – nicht Recorderchunks und kein intern wiederholter Score.

`wakeWord.preRollMs` bezieht sich auf den operationalen Nullpunkt, die Trailing
Edge des gewonnenen qualifizierten Wake-Hits. Aus dem Classifier-Receptive-Field
wird **keine** Obergrenze mehr abgeleitet; die reale Grenze ist die vorgehaltene
Audiohistorie und wird zur Laufzeit geclampt. `wakeWord.cooldownMs` ist der
explizit konfigurierte Betreiber-Cooldown nach einem akzeptierten Wake-Hit und
nicht die interne Gruppierung desselben Trefferbereichs.

`wakeWord.detectorGain` wirkt nur auf einer PCM-Kopie für die Wake-Inferenz
(sättigendes int16-Clipping); das Originalaudio für Aufnahme, Transkription und
Audiohistorie bleibt unverändert. `wakeWord.vadThreshold` schaltet das
OpenWakeWord-interne VAD-Gate vor der Wake-Inferenz (`0.0` = aus),
`wakeWord.noiseSuppressionEnabled` die vorhandene Speex-Unterstützung.

Die Kalibrierschlüssel sind **ausdrücklich vorläufig**: ihre Schemaeinträge
tragen `constraints.calibration = "pending"` samt der abhängigen
Traceability-IDs. `0`, `1` und `1.0` sind neutrale Defaults, keine Empfehlungen.
Die kalibrierten Betriebswerte erfordern reale positive Wake-Word-Aufnahmen:
`WW-18` und `WW-19` sind derzeit `EVIDENCE_BLOCKED`.

Weitere Wake-Word-Settings der Control Plane: `wakeWord.selection` (Session,
`next_session`), `wakeWord.inferenceBackend` (Server, Admin-Key,
`next_session`, zulässig `auto`/`onnx`/`tflite` über die generische
`constraints.allowedValues`-Prüfung), `wakeWord.globalDisabledIds` (Server,
Admin-Key, `next_session`) und `runtimeSuppression.wakeWord` (Session, `live`,
Schreibautorität bleibt `trigger_suppression.set`).

`wakeWord.inferenceBackend` wählt das **eine gemeinsame** Inference Backend
einer Live-Engine für alle ausgewählten Wake Words. `auto` bevorzugt ONNX unter
Windows und TFLite/LiteRT unter Linux und fällt für die gesamte Auswahl auf das
jeweils andere Backend zurück; eine explizite Wahl wechselt nie still.

Die öffentliche Verwaltung läuft über `GET/PATCH /api/v2/settings/server`
(`PATCH` admin-geschützt, optimistische Concurrency) und das Schema über
`GET /api/v2/settings/schema`. Sessionseitig wird der Wert pro Activation
gelatcht: eine laufende Activation behält ihren Timingsnapshot, die nächste
verwendet den neuen Wert real. `session.snapshot` veröffentlicht zusätzlich zu
`effectiveSettings` das additive Feld `requestedSettings`, damit
Requested/Effective-Unterschiede (`next_activation`/`next_session`) nach einem
Resync vollständig unterscheidbar sind. Persistierte Control-Daten werden beim
Startup streng validiert; ein Persistenzfehler eines Serverportches lässt RAM
und Revision unverändert und wird als `internal_error` (HTTP 500) gemeldet.
