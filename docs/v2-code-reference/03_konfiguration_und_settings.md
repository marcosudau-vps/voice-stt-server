# 03 – Konfiguration und Settings

Der Server kennt zwei voneinander getrennte Konfigurationsebenen:

1. **Servereinstellungen** (`ServerSettings`, snake_case) – Start per CLI,
   Umgebungsvariablen und YAML; teilweise zur Laufzeit über
   `PATCH /api/config` änderbar.
2. **V2-Settings-Registry** (`settings_control.py`, Punkt-Schlüssel wie
   `activation.followupTimeoutMs`) – versioniert, mit Revision, Scope und
   Anwendungsrichtlinie; Server-Scope über `PATCH /api/v2/settings/server`,
   Session-Scope über das V2-Kommando `session_settings.patch`.

## 1. Auflösungsreihenfolge der Servereinstellungen

`parse_args` (`api_fastapi_server/server.py:10392`) und `create_app`
(`server.py:8817`) ergeben folgende Priorität (höchste zuerst):

1. **Persistierte Laufzeitwerte** aus `<data_root>/config/runtime.json`
   (nur wenn `data_root_path` gesetzt ist). `create_app` überschreibt damit die
   Startwerte – ausgenommen abgeleitete Pfade, `admin_api_key`,
   `openai_api_key` und `data_root_path`.
2. **Explizite CLI-Argumente**.
3. **YAML-Datei** aus `--config` oder `VOICESTT_CONFIG`
   (`parser.set_defaults(**yaml_defaults)`, `server.py:10653`). Weil
   `set_defaults` die argparse-Defaults ersetzt, gewinnt YAML auch gegen
   Umgebungsvariablen, die nur als argparse-Default eingelesen werden.
4. **Umgebungsvariablen**, die als argparse-Default dienen (Tabelle unten).
5. **Code-Defaults** (`ServerSettings`, argparse-Defaults).
6. Für `beam_size`, `beam_size_realtime`, `batch_size`, `realtime_batch_size`,
   `realtime_processing_pause`, `min_length_of_recording`,
   `post_speech_silence_duration`, `early_transcription_on_silence` gilt:
   Fehlt der CLI-/YAML-Wert, kommt er aus dem **Tuning-Profil**
   (`_value_or_default`, `BASE_TUNING_DEFAULTS`, `TUNING_PROFILES`).

Beobachtet (lokal): `parse_args(['--config','config.yaml'])` liefert
`max_sessions=8` aus der Root-`config.yaml`; zusätzlich `--max-sessions 2`
ergibt `2`; `VOICESTT_LOG_LIVE=0` ohne YAML ergibt `log_live_enabled=False`.

### YAML-Format

```yaml
version: 1          # andere Werte -> SystemExit
settings:           # optional; fehlt der Abschnitt, gilt die Datei selbst
  port: 8010
  language: de
  transcription_engine: faster_whisper
  realtime_transcription_engine: kroko_onnx
```

Regeln aus `load_yaml_config_defaults` (`server.py:10334`):

- Schlüssel werden normalisiert (`-` → `_`); nur Felder von `ServerSettings`
  sind erlaubt, sonst `Unbekannter YAML-Konfigurationswert`.
- `admin_api_key` und `openai_api_key` sind in YAML **verboten**
  („Verwende dafür ausschließlich die Env-Datei.“).
- Abgeleitete Felder (`tuning_description`, alle Log-/Store-/Runtime-Pfade)
  sind verboten.
- `device` darf nur `cpu` sein; `tuning_profile` muss existieren.
- Einige YAML-Namen werden auf invertierte CLI-Ziele abgebildet
  (`YAML_CONFIG_TO_ARG_DEST`), z. B. `model_warmup: false` → `--no-model-warmup`,
  `vad_filter: false` → `--no-vad-filter`, `openai_api_enabled: false` →
  `--disable-openai-api`.
- Weitere Top-Level-Abschnitte (z. B. `deployment`, `example_app` in der
  Root-`config.yaml`) ignoriert der Server; sie werden von `tools/compose.py`
  bzw. der Beispiel-App gelesen.

## 2. Umgebungsvariablen

| Variable | Wirkung | Beleg |
| --- | --- | --- |
| `VOICESTT_CONFIG` | Pfad der YAML-Datei | `parse_args` |
| `VOICESTT_DATA_ROOT` | `data_root_path` | `parse_args` |
| `VOICESTT_ADMIN_API_KEY` | Admin-Schlüssel (auch zur Laufzeit gelesen) | `parse_args`, `security/admin.py` |
| `VOICESTT_API_KEY` | OpenAI-Bearer-Schlüssel, falls `openai_api_key` leer | `security/openai.py` |
| `VOICESTT_MODEL_IDLE_UNLOAD`, `VOICESTT_MODEL_IDLE_TIMEOUT_SECONDS`, `VOICESTT_MODEL_MEMORY_POLICY`, `VOICESTT_ALLOW_TWO_MEDIUM_MODELS` | Modell-Lebenszyklus | `parse_args` |
| `VOICESTT_REQUEST_LOGGING`, `VOICESTT_REQUEST_LOG_STDOUT`, `VOICESTT_REQUEST_LOG_TRANSCRIPTS`, `VOICESTT_TRANSCRIPT_MODE` | Audit-Log | `parse_args` |
| `VOICESTT_PERFORMANCE_LOGGING`, `VOICESTT_PERFORMANCE_LOG_STDOUT`, `VOICESTT_PERFORMANCE_LOG_MIRROR` | Performance-Log | `parse_args` |
| `VOICESTT_TRANSCRIPTION_LOGGING`, `VOICESTT_TRANSCRIPTION_LOG_STDOUT` | Transkriptions-Log | `parse_args` |
| `VOICESTT_SYSTEM_EVENT_LOGGING`, `VOICESTT_SYSTEM_EVENT_LOG_STDOUT` | System-Log | `parse_args` |
| `VOICESTT_LOG_CALENDAR_TIMEZONE` (Default `Europe/Berlin`), `VOICESTT_REALTIME_LOG_DETAIL` (Default `events`) | Logformat | `parse_args` |
| `VOICESTT_EVENT_STORE`, `VOICESTT_LOG_LIVE`, `VOICESTT_SAVE_AUDIO_FILES` | Eventstore/Live-Logs/Audio-Ablage | `parse_args` |
| `VOICESTT_FASTER_WHISPER_MODEL_ROOT`, `VOICESTT_KROKO_MODEL_ROOT` | zusätzliche Modell-Suchwurzeln | `stt_model_management.py:STTModelManager.discovery_roots` |
| `VOICESTT_OFFLINE_MODELS` | Offline-Modellauflösung | `VoiceSTT/transcription_engines/model_resolver.py` |
| `VOICESTT_WAKEWORD_ASSET_ROOT` | alternative Wake-Word-Assetwurzel | `VoiceSTT/core/wakeword_catalog.py:89` |
| `KROKO_API_KEY`, `KROKO_ONNX_KEY`, `VOICESTT_KROKO_ONNX_KEY`, `KROKO_KEY` | Kroko-Schlüssel (in dieser Reihenfolge) | `VoiceSTT/kroko/credentials.py` |
| `VOICESTT_SERVER_COMMIT` | Commit in der Laufzeitidentität | `protocol_v2/identity.py` |

Boolesche Env-Werte gelten als wahr bei `1`, `true`, `yes`, `on`
(`_env_bool`, `server.py:10295`).

## 3. `ServerSettings` – wichtige Defaults

Vollständige Liste: Dataclass in `server.py:428–582`. Auszug:

| Feld | Default | CLI |
| --- | --- | --- |
| `host` / `port` | `0.0.0.0` / `8010` | `--host`, `--port` |
| `model` | `small` | `--model` |
| `realtime_model` | `Kroko-DE-Community-64-L-Streaming-001.data` | `--realtime-model` |
| `language` | `de` | `--language` |
| `transcription_engine` | `faster_whisper` | `--engine` / `--transcription-engine` |
| `realtime_transcription_engine` | `kroko_onnx` | `--realtime-engine` |
| `compute_type` / `device` | `int8` / `cpu` | `--compute-type`, `--device {cpu}` |
| `realtime_callback` | `update` (CLI erlaubt `update`, `stabilized`) | `--realtime-callback` |
| `post_speech_silence_duration` | `0.55` s | `--post-speech-silence-duration` |
| `silero_sensitivity` / `webrtc_sensitivity` | `0.05` / `3` | gleichnamig |
| `pre_recording_buffer_duration` | `0.75` s | gleichnamig |
| `wakeword_backend` / `wake_words` | leer / leer (mit `--wake-words` wird `openwakeword` gesetzt) | `--wakeword-backend`, `--wake-words` |
| `wake_word_timeout` | `5.0` s | `--wake-word-timeout` |
| `max_sessions` / `max_active_speakers` | `4` / `4` | gleichnamig |
| `max_audio_packet_bytes` | `524288` | gleichnamig |
| `max_final_queue_depth_per_session` / `max_global_inference_queue_depth` | `8` / `64` | gleichnamig |
| `max_realtime_queue_age_ms` | `1500` | gleichnamig |
| `model_idle_unload_enabled` / `model_idle_timeout_seconds` | `True` / `3600.0` | `--[no-]model-idle-unload`, `--model-idle-timeout-seconds` |
| `stt_auto_download_enabled` | `False` | `--[no-]stt-auto-download` |
| `openai_api_enabled` | `True` | `--disable-openai-api` |
| `openai_model_aliases` | `{"whisper-1": "final", "fast": "realtime"}` | `--openai-model-aliases` (JSON) |
| `openai_max_file_bytes` | `26214400` (25 MiB) | gleichnamig |
| `event_store_enabled` / `log_live_enabled` | `True` / `True` | `--[no-]event-store`, `--[no-]log-live` |
| `realtime_log_detail` | `events` (`off`, `summary`, `events`) | `--realtime-log-detail` |

Validierungen in `__post_init__`: `realtime_log_detail` muss `off|summary|events`
sein; `log_live_enabled` erfordert `event_store_enabled`.

Die vollständige CLI-Hilfe erzeugt `voice-stt-server --help`.

## 4. Änderungen zur Laufzeit (`PATCH /api/config`)

`VoiceSTTService.update_settings` (`server.py:7850`) teilt jedes Feld in eine
von drei Klassen (`runtime_settings_contract`, `server.py:1235`):

| Klasse | Menge im Code | `appliesTo` in der Antwort |
| --- | --- | --- |
| aktiv für laufende Sitzungen | `ACTIVE_RUNTIME_SETTINGS` | `active_sessions` (bzw. `model_refresh` für `MODEL_MANAGEMENT_SETTINGS`) |
| nur für neue Sitzungen | `NEW_SESSION_RUNTIME_SETTINGS` | `new_sessions` |
| nur beim Start | `STARTUP_ONLY_SETTINGS` | abgelehnt mit `reason: "startup_only"` |

Unbekannte Felder werden mit `reason: "unknown"`, ungültige mit
`invalid_value`, unzulässige Kombinationen mit `invalid_dependency`
abgelehnt. Antwortform:

```json
{"applied": {"<name>": {"value": "...", "appliesTo": "new_sessions"}},
 "rejected": {"<name>": {"reason": "startup_only", "message": "..."}},
 "settings": {}, "runtimeSettings": {}, "modelRefreshRequired": false}
```

HTTP-Status ist `400`, sobald `rejected` nicht leer ist. Typprüfung über
`coerce_setting_value` (`server.py:1243`): Booleans müssen echte JSON-Booleans
sein, `*_max_bytes > 0`, `*_backup_count >= 0`, `*_retention_days >= 0`,
`event_log_queue_size >= 100`, `transcript_log_mode ∈ {none, final, full}`.

Weitere Konfigurations-Routen (Details Seite 06): `POST /api/config/validate`
(Trockenprüfung), `POST /api/config/reload` (lädt `runtime.json` neu),
`PUT /api/language`, `PUT /api/wake-word`, `PUT /api/models/lifecycle`,
`PUT /api/logging`.

## 5. V2-Settings-Registry

Ausgabe von `build_default_registry().schema_payload()` (lokal erzeugt,
identisch mit `GET /api/v2/settings/schema`):

| Schlüssel | Scope | Schreibrecht | Typ | Default | Anwendung | Constraints |
| --- | --- | --- | --- | --- | --- | --- |
| `activation.closingRecoveryTimeoutMs` | session | session | int | 5000 | next_activation | 1000–30000 ms |
| `activation.followupTimeoutMs` | session | session | int | 3000 | next_activation | 100–60000 ms |
| `activation.initialSpeechTimeoutMs` | session | session | int | 15000 | next_activation | 100–3600000 ms |
| `activation.segmentWatchdogInitialMs` | session | session | int | 600000 | next_activation | 60000–3600000 ms |
| `activation.segmentWatchdogRefreshMs` | session | session | int | 180000 | next_activation | 30000–600000 ms |
| `activation.segmentWatchdogWarningMs` | session | session | int | 30000 | next_activation | ≥ 5000 ms, kleiner als Initial- und Refresh-Wert |
| `kroko.forceCommunity` | server | admin | bool | false | live | – |
| `runtimeSuppression.manual` | session | session | bool | false | live | – |
| `runtimeSuppression.wakeWord` | session | session | bool | false | live | – |
| `wakeWord.cooldownMs` | session | session | int | 0 | next_activation | ≥ 0 ms, Kalibrierung `pending` |
| `wakeWord.detectorGain` | session | session | float | 1.0 | next_activation | 0.0–3.0, Kalibrierung `pending` |
| `wakeWord.globalDisabledIds` | server | admin | string_list | [] | next_session | – |
| `wakeWord.inferenceBackend` | server | admin | string | "auto" | next_session | `auto`, `onnx`, `tflite` |
| `wakeWord.minConsecutivePredictionFrames` | session | session | int | 1 | next_activation | ≥ 1, Kalibrierung `pending` |
| `wakeWord.noiseSuppressionEnabled` | session | session | bool | false | next_session | – |
| `wakeWord.preRollMs` | session | session | int | 0 | next_activation | ≥ 0 ms, Kalibrierung `pending` |
| `wakeWord.selection` | session | session | string_list | [] | next_session | – |
| `wakeWord.sensitivity` | session | session | float | 0.5 | next_activation | 0.0–1.0 |
| `wakeWord.vadThreshold` | session | session | float | 0.0 | next_session | 0.0–1.0, Kalibrierung `pending` |

Anwendungsrichtlinien (`APPLY_POLICIES`): `live`, `next_activation`,
`next_session`, `server_restart`. Ergebniscodes eines Patches:
`applied`, `no_change`, `settings_revision_conflict`, `settings_rejected`,
`internal_error`.

**Server-Patch** (`PATCH /api/v2/settings/server`, Admin):

```json
{"baseSettingsRevision": 0, "changes": {"kroko.forceCommunity": true}}
```

HTTP-Status: `200` (angewendet/keine Änderung), `409`
(`settings_revision_conflict`), `422` (`settings_rejected`), `500`
(`internal_error`), `400` bei Nicht-Objekt. Wird `kroko.forceCommunity`
geändert, invalidiert `apply_kroko_force_change` eine Pro-Freigabe noch vor der
Antwort; wird `wakeWord.globalDisabledIds` geändert, wird der Wake-Word-Katalog
neu projiziert.

Persistenz: Overlay und Revision landen in derselben `runtime.json` unter
`settingsControlOverlay` / `settingsRevision`
(`RuntimeConfigStore.save_settings_control`).

## Primäre Quellen

- [`api_fastapi_server/server.py`](../../api_fastapi_server/server.py) – `ServerSettings` (428), Mengenkonstanten (202–426), `coerce_setting_value` (1243), `load_yaml_config_defaults` (10334), `parse_args` (10392), `settings_from_args` (10681), `update_settings` (7850)
- [`api_fastapi_server/settings_control.py`](../../api_fastapi_server/settings_control.py) – `builtin_definitions`, `SettingsRegistry.schema_payload`, `ServerSettingsState`
- [`VoiceSTT_server/operations.py`](../../VoiceSTT_server/operations.py) – `RuntimeConfigStore`
- [`config.yaml`](../../config.yaml)
- Tests: [`tests/unit/test_settings_control_plane.py`](../../tests/unit/test_settings_control_plane.py), [`tests/unit/test_settings_runtime_persistence.py`](../../tests/unit/test_settings_runtime_persistence.py), [`tests/unit/test_protocol_v2_settings.py`](../../tests/unit/test_protocol_v2_settings.py), [`tests/unit/test_project_config.py`](../../tests/unit/test_project_config.py), [`tests/unit/test_server_operations.py`](../../tests/unit/test_server_operations.py)
