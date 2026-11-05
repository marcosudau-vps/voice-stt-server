# 06 – HTTP-/REST-API

Alle Routen werden in `create_app` (`api_fastapi_server/server.py:8817ff.`)
bzw. im Router `create_openai_router` (`api_fastapi_server/openai_routes.py`)
registriert. Die Liste unten ist vollständig gegen eine AST-Auswertung aller
`@app.<methode>`-/`@router.<methode>`-Dekoratoren abgeglichen (37 Routen
inklusive 3 WebSockets, diese siehe Seite 07). FastAPI liefert zusätzlich
seine Standardrouten (`/docs`, `/openapi.json`, `/redoc`); im Code sind diese
nicht abgeschaltet.

## Auth-Klassen

| Kürzel | Bedeutung | Implementierung |
| --- | --- | --- |
| **öffentlich** | keine Prüfung | – |
| **Admin** | Ist ein Admin-Schlüssel konfiguriert: Header `X-VoiceSTT-Admin-Key`, `Authorization: Bearer <key>` oder `X-Admin-Key` muss passen, sonst `401`. Ohne Schlüssel: nur Clients mit Host `127.0.0.1`, `::1`, `localhost`, `testclient`, sonst `403` | `security/admin.py:AdminGate.http_error` |
| **OpenAI** | Ist `openai_api_key`/`VOICESTT_API_KEY` gesetzt: `Authorization: Bearer <key>` muss exakt passen, sonst `401` (`invalid_api_key`) und Audit-Event `authentication.failed`. Ohne Schlüssel: offen | `security/openai.py:OpenAIGate.http_error` |
| **Log** | Admin-Schlüssel, oder ohne Schlüssel Loopback-Client (dann Admin-Scope), oder sitzungsgebundenes Log-Token in `X-VoiceSTT-Log-Token` bzw. `Authorization: Bearer` (dann Session-Scope); sonst `401` | `security/logs.py:LogGate.http_scope` |

Beobachtet: `PATCH /api/config` von `127.0.0.1` ohne konfigurierten
Admin-Schlüssel → `200`.

## Routenübersicht

| Methode | Pfad | Auth | Handler (Zeile) |
| --- | --- | --- | --- |
| GET | `/` | öffentlich | `index` (8883) – liefert `api_fastapi_server/static/index.html` |
| GET | `/health` | öffentlich | `health` (8887) |
| GET | `/api/v2/info` | öffentlich | `server_info_v2` (8876) |
| GET | `/api/config` | öffentlich | `config` (8909) |
| PATCH | `/api/config` | Admin | `update_config` (8923) |
| POST | `/api/config/validate` | Admin | `validate_config` (9851) |
| POST | `/api/config/reload` | Admin | `reload_config` (9872) |
| GET | `/api/metrics` | öffentlich | `metrics` (8941) |
| GET | `/api/models` | Admin | `api_models` (8945) |
| GET | `/api/models/management` | Admin | `get_stt_model_management` (8961) |
| POST | `/api/models/refresh` | Admin | `refresh_stt_model_management` (8968) |
| GET / PUT | `/api/models/lifecycle` | Admin | `get_model_lifecycle` (9031), `configure_model_lifecycle` (9038) |
| POST | `/api/models/load` | Admin | `load_models` (9076) |
| POST | `/api/models/unload` | Admin | `unload_models` (9086) |
| GET / PUT | `/api/models/active` | Admin | `active_models` (9096), `switch_active_models` (9103) |
| POST | `/api/kroko/license/refresh` | Admin | `refresh_kroko_license` (8981) |
| GET / PUT | `/api/language` | Admin | `get_language` (9117), `set_language` (9124) |
| GET / PUT | `/api/wake-word` | Admin | `get_wake_word` (9140), `set_wake_word` (9161) |
| GET | `/api/v2/settings/schema` | öffentlich | `settings_schema_v2` (9225) |
| GET | `/api/v2/settings/server` | öffentlich | `settings_server_v2` (9237) |
| PATCH | `/api/v2/settings/server` | Admin | `patch_settings_server_v2` (9246) |
| GET | `/api/v2/wake-words` | öffentlich | `wake_words_v2` (9296) |
| POST | `/api/v2/wake-words/refresh` | Admin | `refresh_wake_words_v2` (9305) |
| GET / PUT | `/api/logging` | Admin | `get_logging_config` (9322), `set_logging_config` (9385) |
| GET | `/api/logs/events` | Log | `get_log_events` (9541) |
| GET | `/api/logs/sessions/{session_id}` | Log | `get_session_log_events` (9545) |
| GET | `/api/logs/transcriptions/{transcription_id}` | Log | `get_transcription_log_events` (9552) |
| GET | `/v1/models` | OpenAI | `openai_models` (`openai_routes.py:44`) |
| POST | `/v1/audio/transcriptions` | OpenAI | `openai_transcriptions` (`openai_routes.py:68`) |

## Details

### `GET /api/v2/info`

Antwort mit `Cache-Control: no-store`. Beobachtet (Quell-Checkout, nicht
installierte Distribution):

```json
{"schemaVersion":1,"protocolVersion":2,"serverVersion":"2.0.0","serverCommit":"unknown",
 "identityStatus":"incomplete","build":{"sourceTree":null,"sourceDirty":null,"sourceDate":null},
 "distribution":{"name":"voicestt","packageVersion":"2.0.0"},"runtime":{"krokoVariant":null},
 "serverInstanceId":"<32 hex>"}
```

### `GET /health`

Felder: `ok` (Scheduler gesund **und** – bei aktivem Live-Log – Eventstore
verfügbar), `ready`, `activeSessions`, `activeSpeakers`, `rejectedSessions`,
`scheduler`, `models`, `sttReady`, `sttModels`, `startupErrors`, `eventStore`.
Statuscode ist immer `200`; Bereitschaft steckt im Body. (Der Container-
`HEALTHCHECK` prüft nur Erreichbarkeit bzw. HTTP-Status.)

### `GET /api/config`

`settings` (`ServerSettings.public_dict()` – ohne Schlüssel und
Engine-Optionen, Kroko-Credentials entfernt, plus `wake_word_enabled`),
`limits`, `supportedEngines`, `runtimeSettings`, `sessionCapabilities`,
`adminAuthRequired`.

### `PATCH /api/config`

Body: `{"settings": {...}}` oder direkt das Objekt. Antwort und Status siehe
Seite 03, Abschnitt 4.

```bash
curl -X PATCH http://127.0.0.1:8010/api/config \
  -H 'content-type: application/json' \
  -d '{"settings": {"max_sessions": 6}}'
```

### `POST /api/config/validate`

Wendet die Änderungen auf eine Kopie an, ruft `__post_init__` und die
CPU-Modellrichtlinie auf. Antwort `{"valid": true, "settings": ...}` oder
`400` mit `{"valid": false, "error": ...}`. Unbekannte Felder und abgeleitete
Pfadfelder sind Fehler.

### `POST /api/config/reload`

Lädt `runtime.json` neu, teilt in Modell- und Laufzeitfelder, wendet beide an.
Antwort `{"runtime": ..., "models": ..., "skipped": [...]}`; Fehler `400`.

### `POST /api/kroko/license/refresh`

Body optional `{"timeout": <0 < t <= 60>}` (Default 5.0), sonst `400`.
Führt die Lizenzprüfung im Thread aus; ergibt sich eine Pro-Freigabe, wird die
Modellverwaltung neu aufgebaut. Antwort `{"decisions": [...], "management":
..., "license": <public_snapshot>, "runtime": ...}`; Refresh-Fehler → `409`.

### `PUT /api/language`

Body `{"language": "<code>"}`; leer → `400`. Gilt für neue Anfragen/Sitzungen
(`appliesTo: "new_requests_and_sessions"`).

### `PUT /api/wake-word`

Body z. B. `{"enabled": true, "backend": "openwakeword", "words": "hey_jarvis",
"sensitivity": 0.5, "timeout": 5, "bufferDuration": 0.1, "followupWindow": 0}`.
`enabled: false` leert Backend und Wake-Words. Gilt für neue Sitzungen.

### `PUT /api/logging`

Pfadfelder (`audioDirectory`, `file`, `performanceFile`, `systemDirectory`,
`transcriptionDirectory`) werden abgelehnt, da sie aus `data_root_path`
abgeleitet sind.

### `GET /api/logs/events` (und Varianten)

Query: `sessionId`, `channels` (kommagetrennt), `events`, `transcriptionId`,
`from`, `to`, `afterCursor` (Default 0), `limit` (Default 200). Session-Scope
sieht nur die Kanäle `audit`, `performance`, `transcription` und nur die
eigene Sitzung. Antwort:

```json
{"object":"list","data":[...],"nextCursor":123,"oldestCursor":1,"latestCursor":456,
 "retentionCursor":0,"authorizationScope":"session","allSessions":false,
 "deliveryMode":"sqlite_first"}
```

`503` mit `code: "event_store_unavailable"`, wenn der SQLite-Store fehlt.

### `GET /v1/models`

Liste aus dem Modellkatalog; `whisper-1` wird ergänzt, falls nicht vorhanden.
Beobachtet:

```json
{"object":"list","data":[{"id":"whisper-1","object":"model","created":0,"owned_by":"voicestt",
 "engine":"routing_alias","loaded":true,"lanes":["final"]}]}
```

### `POST /v1/audio/transcriptions`

Multipart-Formular (`VoiceSTT_server/openai_compat.py:parse_transcription_form`):

| Feld | Regel |
| --- | --- |
| `file` | Pflicht; Endung ∈ `.flac .mp3 .mp4 .mpeg .mpga .m4a .ogg .wav .webm`; Größe ≤ `openai_max_file_bytes`, sonst `413` |
| `model` | Pflicht; Auflösung über `openai_model_aliases` (Default `whisper-1` → Final-Lane, `fast` → Realtime-Lane) |
| `language`, `prompt` | optional |
| `response_format` | `json` (Default), `text`, `srt`, `vtt`, `verbose_json`, `diarized_json` |
| `timestamp_granularities` | `segment` (Default), `word` – andere als `["segment"]` nur mit `verbose_json` |
| `include` | nur `logprobs` |
| `known_speaker_names` | höchstens 4 |
| `temperature`, `threshold` | Zahl im Bereich 0–1 |
| `stream` | boolesch; `true` → `text/event-stream` mit `data: {"type":"transcript.text.delta","delta":...}` und abschließend `transcript.text.done` |
| `voicestt_model` / `model_override` bzw. Header `X-VoiceSTT-Model` | serverseitige Modellübersteuerung |

`404` mit OpenAI-Fehlerobjekt, wenn `openai_api_enabled = false`.
Fehlerformat: `{"error": {"message", "type", "param", "code"}}`.

```bash
curl http://127.0.0.1:8010/v1/audio/transcriptions \
  -H "Authorization: Bearer $VOICESTT_API_KEY" \
  -F file=@sample.wav -F model=whisper-1 -F response_format=verbose_json
```

## Primäre Quellen

- [`api_fastapi_server/server.py`](../../api_fastapi_server/server.py) – `create_app` (8817–10295)
- [`api_fastapi_server/openai_routes.py`](../../api_fastapi_server/openai_routes.py), [`VoiceSTT_server/openai_compat.py`](../../VoiceSTT_server/openai_compat.py)
- [`api_fastapi_server/security/admin.py`](../../api_fastapi_server/security/admin.py), [`api_fastapi_server/security/openai.py`](../../api_fastapi_server/security/openai.py), [`api_fastapi_server/security/logs.py`](../../api_fastapi_server/security/logs.py)
- Tests: [`tests/unit/test_fastapi_server_protocol.py`](../../tests/unit/test_fastapi_server_protocol.py), [`tests/unit/test_openai_compatible_endpoint.py`](../../tests/unit/test_openai_compatible_endpoint.py), [`tests/unit/test_server_info.py`](../../tests/unit/test_server_info.py), [`tests/unit/test_server_security_modularization.py`](../../tests/unit/test_server_security_modularization.py), [`tests/unit/test_wakeword_catalog_api.py`](../../tests/unit/test_wakeword_catalog_api.py), [`tests/unit/test_kroko_license_lifecycle.py`](../../tests/unit/test_kroko_license_lifecycle.py)
