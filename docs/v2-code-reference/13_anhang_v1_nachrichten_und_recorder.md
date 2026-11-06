# 13 – Anhang: V1-Nachrichtenfelder und `AudioToTextRecorder`-Parameter

Dieser Anhang schließt zwei in Seite 12 genannte Lücken. Beide Tabellen sind
**maschinell aus dem Quellcode erzeugt** (2026-11-05) und nicht von Hand
zusammengestellt:

- V1-Nachrichten: AST-Auswertung aller Dict-Literale mit konstantem
  `"type"`-Schlüssel in `api_fastapi_server/server.py` (ohne `log.*`, siehe
  Seite 07).
- Recorder-Parameter: `inspect.signature(AudioToTextRecorder.__init__)` auf
  dem importierten Modul, d. h. mit den tatsächlich aufgelösten Defaults.

## 1. Server → Client: V1-Nachrichtentypen (`/ws/transcribe`)

Die Felder sind die Vereinigung aller Erzeugungsstellen eines Typs. Nicht jede
Stelle setzt jedes Feld. Zusätzlich ergänzt der Code bei `realtime` und
`final` zur Laufzeit ein Feld `segment` (Snapshot des Segment-Timelines) und
die Zeitfelder aus `segment_text_fields` (`server.py:1399`: `recordingStartedAt`,
`recordingStartedAtIso`, `recordingEndedAt`, `recordingEndedAtIso`,
`durationSeconds`, `endReason`, `preRecordingBuffer`, `wakeWord`), wenn ein
Segment-Snapshot existiert.

| `type` | Felder (Vereinigung aller Erzeugungsstellen) | Zeilen in `server.py` |
| --- | --- | --- |
| `audio_availability_ack` | `accepted`, `activationId`, `audioAvailable`, `commandId`, `phase`, `reason`, `sessionId` | 3848 |
| `clear` | `nextSegmentId`, `sessionId` | 3027 |
| `error` | `code`, `limits`, `message`, `sessionId`, `where` | 617, 4726, 8654, 9984, 10001, 10053, 10062, 10079, 10088, 10122 |
| `final` | `activationId`, `activationSequence`, `requestId`, `segmentId`, `segmentSequence`, `sessionId`, `text`, `timestamp`, `timestampIso` | 4844 |
| `hello` | `activationConfig`, `clientId`, `limits`, `logAccess`, `runtimeSettings`, `sessionCapabilities`, `sessionConfig`, `sessionId`, `settings`, `supportedEngines` | 10024 |
| `metrics` | `metrics`, `sessionId` | 10110 |
| `pong` | `serverTime`, `sessionId` | 10104 |
| `ready` | `activationConfig`, `limits`, `models`, `ok`, `runtimeSettings`, `sessionCapabilities`, `sessionConfig`, `sessionId`, `settings` | 7837 |
| `realtime` | `commitReason`, `committedStableDelta`, `committedStableText`, `consensusDisplayText`, `consensusText`, `consensusUnstableText`, `displayText`, `internalRevision`, `isOutlier`, `publicConsensusAligned`, `rawText`, `recordingId`, `segmentId`, `sequence`, `sessionId`, `stableDelta`, `stableNormalizedOffset`, `stablePrefixConflict`, `stableText`, `text`, `timestamp`, `timestampIso`, `unstableText`, `visualStableText`, `visualUnstableText` | 4982, 5083 |
| `status` | `activeClientId`, `activeSessions`, `activeSpeakers`, `coalescedRealtime`, `droppedChunks`, `queueDepth`, `sessionId`, `staleRealtimeDiscarded`, `state`, `timestamp`, `wakeWord`, `wakeWordEnabled` | 3139 |
| `timeline` | `event`, `sessionId`, `timestamp`, `timestampIso` | 5924 |
| `trigger_ack` | `accepted`, `activationId`, `commandId`, `phase`, `reason`, `sessionId` | 3441 |
| `warning` | `activationId`, `message`, `recovery`, `sessionId` | 3064, 4291, 5346, 6104, 6145, 10070 |

Client → Server (`start`, `stop`, `clear`, `ping`, `metrics`, `trigger`,
`audio_availability`) siehe Seite 07, Abschnitt 1.

## 2. `AudioToTextRecorder` – vollständige Konstruktorparameter

Klasse `VoiceSTT.audio_recorder.AudioToTextRecorder` (öffentlich auch als
`voice_stt_server.AudioToTextRecorder`). Der Server erzeugt sie mit
`use_microphone=False` und eigenen Werten (`RecorderBackedRealtimeSession._create_recorder`);
die folgenden Defaults gelten für die direkte Bibliotheksnutzung. Im
V2-Produkt sind als `transcription_engine` / `realtime_transcription_engine`
nur `faster_whisper` und `kroko_onnx` zulässig; `device` wird von der
Engine-Fabrik immer auf `cpu` gesetzt.

| Parameter | Typ | Default |
| --- | --- | --- |
| `model` | str | `'tiny'` |
| `transcription_engine` | str | `'faster_whisper'` |
| `transcription_engine_options` | Optional | `None` |
| `download_root` | str | `None` |
| `language` | str | `'de'` |
| `compute_type` | str | `'int8'` |
| `input_device_index` | int | `None` |
| `gpu_device_index` | Union | `0` |
| `device` | str | `'cpu'` |
| `on_recording_start` |  | `None` |
| `on_recording_stop` |  | `None` |
| `on_transcription_start` |  | `None` |
| `ensure_sentence_starting_uppercase` |  | `True` |
| `ensure_sentence_ends_with_period` |  | `True` |
| `use_microphone` |  | `True` |
| `spinner` |  | `True` |
| `level` |  | `30` |
| `batch_size` | int | `16` |
| `enable_realtime_transcription` |  | `False` |
| `use_main_model_for_realtime` |  | `False` |
| `realtime_transcription_engine` | str | `None` |
| `realtime_transcription_engine_options` | Optional | `None` |
| `realtime_model_type` |  | `'tiny'` |
| `realtime_processing_pause` |  | `0.2` |
| `init_realtime_after_seconds` |  | `0.2` |
| `on_realtime_transcription_update` |  | `None` |
| `on_realtime_transcription_stabilized` |  | `None` |
| `realtime_batch_size` | int | `16` |
| `silero_sensitivity` | float | `0.4` |
| `silero_use_onnx` | Optional | `None` |
| `silero_deactivity_detection` | bool | `False` |
| `webrtc_sensitivity` | int | `3` |
| `warmup_vad` | bool | `True` |
| `post_speech_silence_duration` | float | `0.6` |
| `min_length_of_recording` | float | `0.5` |
| `min_gap_between_recordings` | float | `0` |
| `pre_recording_buffer_duration` | float | `1.0` |
| `pre_recording_buffer_trim_config` | Optional | `None` |
| `on_vad_start` |  | `None` |
| `on_vad_stop` |  | `None` |
| `on_vad_detect_start` |  | `None` |
| `on_vad_detect_stop` |  | `None` |
| `on_turn_detection_start` |  | `None` |
| `on_turn_detection_stop` |  | `None` |
| `wakeword_backend` | str | `''` |
| `openwakeword_model_paths` | str | `None` |
| `openwakeword_inference_framework` | str | `'onnx'` |
| `wake_words` | str | `''` |
| `wake_words_sensitivity` | float | `0.6` |
| `wake_word_activation_delay` | float | `0.0` |
| `wake_word_timeout` | float | `5.0` |
| `wake_word_buffer_duration` | float | `0.1` |
| `wake_word_selection` |  | `None` |
| `wake_word_engine_options` |  | `None` |
| `on_wakeword_detected` |  | `None` |
| `on_wakeword_timeout` |  | `None` |
| `on_wakeword_detection_start` |  | `None` |
| `on_wakeword_detection_end` |  | `None` |
| `on_recorded_chunk` |  | `None` |
| `debug_mode` |  | `False` |
| `handle_buffer_overflow` | bool | `True` |
| `beam_size` | int | `5` |
| `beam_size_realtime` | int | `3` |
| `buffer_size` | int | `512` |
| `sample_rate` | int | `16000` |
| `initial_prompt` | Union | `None` |
| `initial_prompt_realtime` | Union | `None` |
| `suppress_tokens` | Optional | `[-1]` |
| `print_transcription_time` | bool | `False` |
| `early_transcription_on_silence` | int | `0` |
| `allowed_latency_limit` | int | `100` |
| `no_log_file` | bool | `False` |
| `use_extended_logging` | bool | `False` |
| `faster_whisper_vad_filter` | bool | `True` |
| `normalize_audio` | bool | `False` |
| `start_callback_in_new_thread` | bool | `False` |
| `realtime_transcription_use_syllable_boundaries` | bool | `False` |
| `realtime_boundary_detector_sensitivity` | float | `0.6` |
| `realtime_boundary_followup_delays` | Optional | `(0.05, 0.2)` |
| `transcription_executor` | Optional | `None` |
| `realtime_transcription_executor` | Optional | `None` |
| `on_realtime_text_stabilization_update` |  | `None` |
| `silero_backend` | str | `'auto'` |
| `silero_onnx_model_path` | Optional | `None` |
| `silero_onnx_threads` | int | `2` |
| `deactivity_silence_confirmation_duration` | float | `0.16` |

Gesamt: 86 Parameter, kein `**kwargs`.

## Primäre Quellen

- [`api_fastapi_server/server.py`](../../api_fastapi_server/server.py) – Erzeugungsstellen der V1-Nachrichten, `segment_text_fields`
- [`VoiceSTT/audio_recorder.py`](../../VoiceSTT/audio_recorder.py) – `AudioToTextRecorder.__init__` (Zeile 103)
- [`VoiceSTT/core/recorder_config.py`](../../VoiceSTT/core/recorder_config.py), [`VoiceSTT/core/initialization.py`](../../VoiceSTT/core/initialization.py)
- Tests: [`tests/unit/test_audio_recorder_public_api.py`](../../tests/unit/test_audio_recorder_public_api.py), [`tests/unit/test_server_trigger_contract.py`](../../tests/unit/test_server_trigger_contract.py), [`tests/unit/test_fastapi_server_protocol.py`](../../tests/unit/test_fastapi_server_protocol.py)
