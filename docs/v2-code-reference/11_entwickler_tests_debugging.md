# 11 – Entwickler, Tests und Debugging

## 1. Modultopologie (wo liegt was?)

| Thema | Primärmodul(e) |
| --- | --- |
| App-Fabrik, Settings, Routen, Sitzungen, Scheduler | `api_fastapi_server/server.py` |
| Aktivierungs-Zustandsmaschine, Timer | `api_fastapi_server/activation.py` |
| Befehlsparser V1, Replay-Cache | `api_fastapi_server/activation_commands.py` |
| Hintergrund-Ledger finaler Segmente | `api_fastapi_server/segment_ledger.py` |
| Wake-Admission (Erkennung → Aktivierung) | `api_fastapi_server/wake_admission.py` |
| V2-Settings-Registry und -Zustände | `api_fastapi_server/settings_control.py` |
| Protokoll V2 (Schema, Handshake, Kommandos, Events, Snapshot, Verbindung, Ports, Identität) | `api_fastapi_server/protocol_v2/*.py` |
| OpenAI-Router | `api_fastapi_server/openai_routes.py`, `VoiceSTT_server/openai_compat.py` |
| Sicherheit | `api_fastapi_server/security/*.py` |
| Kroko-Einzelidentitätsregel | `api_fastapi_server/kroko_runtime.py` |
| Modellverwaltung | `VoiceSTT_server/stt_model_management.py` |
| Eventlogging, SQLite-Store | `VoiceSTT_server/event_logging.py` |
| Laufzeitkonfigurationsspeicher | `VoiceSTT_server/operations.py` |
| Recorder (Bibliothek) | `VoiceSTT/audio_recorder.py`, `VoiceSTT/core/*.py` |
| Engines | `VoiceSTT/transcription_engines/*.py` |
| Kroko-Native, Fingerprint, Lizenz | `VoiceSTT/kroko/*.py`, `VoiceSTT/install_kroko.py` |
| Build/Release | `tools/*.py`, `release_tooling/*.py`, `release.py` |

## 2. Sichere Erweiterungspunkte

Aus Konstruktorsignaturen und Registrierungsstellen abgeleitet:

- **Testbare App ohne echte Modelle:** `create_app(settings,
  scheduler_factory=..., recorder_factory=...)`. Die Unit-Tests ersetzen damit
  Scheduler und Recorder (z. B. `tests/unit/test_fastapi_server_multi_user.py`).
- **Neue Engine:** Klasse auf Basis `BaseTranscriptionEngine`
  (`VoiceSTT/transcription_engines/base.py`) und Eintrag in
  `ENGINE_CLASS_PATHS`. Ohne Adapter in `STTModelManager` und Rang in
  `model_size_rank` bleibt sie außerhalb der Server-Modellverwaltung und der
  CPU-Richtlinie (siehe Seite 04).
- **Modellautorität / Lizenz:** `STTModelManager(authority=..., intent=...,
  load_probe=..., provisioner=..., license_policy=...)` ist vollständig
  injizierbar.
- **V2-Verbindung ohne Socket:** `ProtocolV2Connection` ist laut Docstring
  transportagnostisch (`set_sink`, `handle_text`, `handle_binary`, `drain`) und
  lässt sich synchron testen.
- **Zeit/Uhren:** `LogTokenAuthority(clock=...)`, `ProtocolSessionState`
  (`_clock`, `_id_factory`) sind für deterministische Tests ausgelegt.

Nicht als Erweiterungspunkt vorgesehen (Code-Kommentare markieren sie als
eingefroren bzw. autoritativ): das V2-Vokabular (`protocol_v2/schema.py`,
„No free additions“ bei Result-Codes), `DOMAIN_REASON_RESULTS` (erschöpfend),
Kroko-Build-Inputs (Revisionspflicht, Guard-Test).

## 3. Tests ausführen

`pytest.ini`: `testpaths = tests/unit`, `python_files = test_*.py`.

```bash
python -m pytest -q tests/unit tests/compatibility
```

```bash
python -m pytest -q tests/packaging
```

Gezielte Auswahl nach Thema:

| Thema | Tests |
| --- | --- |
| Protokoll V2 | `tests/unit/test_protocol_v2_*.py`, `tests/unit/test_protocol_v1_v2_boundary.py` |
| V1/Trigger/Aktivierung | `tests/unit/test_server_trigger_contract.py`, `test_server_activation_*.py`, `test_server_command_timer_e2e.py`, `test_server_controlled_e2e.py` |
| HTTP/OpenAI | `tests/unit/test_fastapi_server_protocol.py`, `test_openai_compatible_endpoint.py`, `test_server_info.py` |
| Settings | `tests/unit/test_settings_control_plane.py`, `test_settings_runtime_persistence.py` |
| Wake-Word | `tests/unit/test_wake*.py`, `test_wakeword*.py` |
| Modelle/Kroko | `tests/unit/test_stt_model_management.py`, `test_kroko_*.py` |
| Build/Release | `tests/unit/test_release_*.py`, `test_build_*.py`, `test_production_docker_contract.py`, `test_unified_product.py` |
| Pfadverträge / diese Referenz | `tests/unit/test_engineering_path_contract.py`, `tests/unit/test_v2_code_reference.py` |

**Beobachtet am 2026-11-05** (Python 3.12.x, Linux, CPU-Torch, ohne
Modelldateien): `python -m pytest -q -p no:cacheprovider tests/unit
tests/compatibility` → `2341 passed, 24 skipped, 1362 subtests passed` in
9:31 min (Stand vor Hinzufügen von `test_v2_code_reference.py`).

Die Dateien direkt unter `tests/` (z. B. `realtimestt_test.py`,
`openwakeword_test.py`) sind manuelle Skripte für Mikrofon/Live-Betrieb und
werden von `pytest.ini` nicht eingesammelt.

## 4. Häufige Fehlerbilder (mit Codebeleg)

| Symptom | Ursache im Code | Abhilfe |
| --- | --- | --- |
| `/health` → `ready: false`, Log: „could not resolve local faster-whisper model …; engine libraries are not allowed to download models implicitly“ | `model_resolver.resolve_faster_whisper_model` | Modell lokal in einer Suchwurzel ablegen (Seite 04) |
| Start bricht ab: „Die CPU-Modellrichtlinie hat diese Kombination abgelehnt …“ | `enforce_cpu_model_policy` | kleineres Modell, `--use-main-model-for-realtime` oder bewusst `--no-model-memory-policy` |
| Start bricht ab: zwei verschiedene Kroko-Modelle | `enforce_kroko_single_identity` | dasselbe Kroko-Modell für beide Lanes |
| `SystemExit: 'admin_api_key' darf nicht in der YAML-Konfiguration stehen` | `load_yaml_config_defaults` | Schlüssel per Env setzen |
| `ValueError: log_live_enabled erfordert event_store_enabled` | `ServerSettings.__post_init__` | Eventstore aktivieren oder Live-Log aus |
| Admin-Route liefert `403` „Remote-Verwaltung ist deaktiviert …“ | `AdminGate.http_error` ohne Schlüssel und Nicht-Loopback | `VOICESTT_ADMIN_API_KEY` setzen |
| V2 schließt sofort mit `4400` | erstes Frame kein gültiges `hello` oder Binärdaten vor Annahme | Handshake korrigieren (Seite 07) |
| V2 sendet kein Ack | `commandId` fehlt oder ist keine kanonische UUID; oder `type` unbekannt | kanonische Kleinbuchstaben-UUID verwenden |
| `trigger_ack.reason = invalid_action` bei `extend` | Alias entfernt | `refresh` verwenden |
| Audiopaket abgelehnt | Format ≠ `pcm_s16le`, `sampleRate` fehlt, `frames` passt nicht, Paket zu groß | Seite 05 |
| Kroko-Pro wird nicht geladen, `restartRequired: true` | `KrokoNativeGuard` (Pro-Identitäts- oder Schlüsselwechsel) | Prozess neu starten |

## 5. Diagnosepunkte

- `GET /health`, `GET /api/metrics` – Scheduler, Worker-Latenzen, Modelle,
  Startfehler.
- `GET /api/models/management` (Admin) – Kandidaten, Diagnosen inkl.
  `blocked_ineligible`, `missing_not_requested`.
- `GET /api/v2/info` – Version, Commit, Identitätsstatus, Kroko-Variante.
- V1 `metrics`-Befehl – Sitzungs-Snapshot.
- Logs unter `<data_root>/logs/*` bzw. `GET /api/logs/events`.

## Primäre Quellen

- [`pytest.ini`](../../pytest.ini), [`requirements-dev.txt`](../../requirements-dev.txt)
- [`api_fastapi_server/server.py`](../../api_fastapi_server/server.py) – `create_app`-Parameter
- [`VoiceSTT/transcription_engines/base.py`](../../VoiceSTT/transcription_engines/base.py), [`factory.py`](../../VoiceSTT/transcription_engines/factory.py)
- [`api_fastapi_server/protocol_v2/connection.py`](../../api_fastapi_server/protocol_v2/connection.py)
- [`tests/unit/conftest.py`](../../tests/unit/conftest.py)
