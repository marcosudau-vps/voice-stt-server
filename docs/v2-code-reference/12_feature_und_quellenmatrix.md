# 12 – Feature- und Quellenmatrix

Statuswerte:

- **getestet** – Implementierung vorhanden und durch automatisierte Tests im
  Repository abgedeckt (Testdatei genannt).
- **beobachtet** – zusätzlich am 2026-11-05 lokal ausgeführt (ohne Modelle).
- **experimentell** – Code und ggf. Unit-Tests vorhanden, aber nicht in
  Server-Modellverwaltung/Richtlinien eingebunden bzw. im Code als
  nicht kalibriert markiert.
- **blockiert** – im Code vorhanden, durch ein explizites Gate gesperrt.

| # | Feature | Implementierung | Tests | Status | Seite |
| --- | --- | --- | --- | --- | --- |
| F01 | Öffentliche Importfläche `voice_stt_server` (lazy) | `voice_stt_server/__init__.py` | `tests/compatibility/test_client_v2_identity.py`, CI-Importprüfung | getestet | 01 |
| F02 | CLI `voice-stt-server` + Aliase | `setup.py` `console_scripts`, `VoiceSTT_server/server.py` | `tests/unit/test_engineering_path_contract.py`, CI | getestet, beobachtet | 02 |
| F03 | YAML-Startkonfiguration mit Secret-Verbot | `server.py:load_yaml_config_defaults` | `tests/unit/test_project_config.py` | getestet, beobachtet | 03 |
| F04 | Laufzeitänderung `PATCH /api/config` (3 Klassen) | `server.py:VoiceSTTService.update_settings` | `tests/unit/test_fastapi_server_protocol.py` | getestet, beobachtet | 03 |
| F05 | Persistenz `runtime.json` (atomar) | `VoiceSTT_server/operations.py:RuntimeConfigStore` | `tests/unit/test_settings_runtime_persistence.py`, `test_server_operations.py` | getestet | 03, 09 |
| F06 | V2-Settings-Registry (19 Schlüssel, Revision) | `api_fastapi_server/settings_control.py` | `tests/unit/test_settings_control_plane.py`, `test_protocol_v2_settings.py` | getestet, beobachtet | 03 |
| F07 | Final-/Realtime-Lanes, fairer Scheduler | `server.py:FairInferenceQueue`, `InferenceScheduler` | `tests/unit/test_fastapi_server_multi_user.py`, `test_fastapi_server_multi_user_asr_integration.py` | getestet, beobachtet (`/health.scheduler`) | 04 |
| F08 | Engine `faster_whisper` | `VoiceSTT/transcription_engines/faster_whisper_engine.py` | `tests/unit/test_faster_whisper_engine.py` | getestet | 04 |
| F09 | Engine `kroko_onnx` | `VoiceSTT/transcription_engines/kroko_onnx_engine.py` | `tests/unit/test_kroko_onnx_engine.py`, `test_kroko_native_integration.py` | getestet | 04 |
| F10 | Engine-Produktgrenze: nur `faster_whisper`, `kroko_onnx`; 5 Entwürfe isoliert, 7 Engines entfernt | `VoiceSTT/transcription_engines/factory.py`, `engineering/drafts/transcription_engines/` | `tests/unit/test_v2_engine_boundary.py`, `tests/packaging/test_v2_distribution_contents.py` | getestet | 04 |
| F11 | CPU-Speicherrichtlinie + Kroko-Einzelidentität | `server.py:enforce_cpu_model_policy`, `kroko_runtime.py` | `tests/unit/test_fastapi_server_multi_user.py`, `test_kroko_pr15_final_correction.py` | getestet | 04 |
| F12 | Server-Modellverwaltung (Discovery, Readiness, Recovery) | `VoiceSTT_server/stt_model_management.py` | `tests/unit/test_stt_model_management.py`, `test_kroko_model_authority.py` | getestet | 04 |
| F13 | Automatische Modellprovisionierung | `AtomicModelProvisioner`, `STTModelManager._provision` | `tests/unit/test_stt_model_management.py` | blockiert für alle 23 ausgelieferten Modelle (`provisioning_allowed = False`) | 04 |
| F14 | Realtime-Textstabilisierung | `VoiceSTT/core/realtime_text_stabilizer.py` | `tests/unit/test_realtime_text_stabilizer.py`, `test_realtime_text_stabilizer_eval.py` | getestet | 04 |
| F15 | Akustischer Grenzdetektor | `VoiceSTT/core/realtime_boundary_detector.py` | `tests/unit/test_realtime_boundary_detector.py` | getestet | 04 |
| F16 | Binäres Audiopaketformat | `api_fastapi_server/protocol.py`, `server.py:packet_to_server_samples` | `tests/unit/test_fastapi_server_protocol.py` | getestet | 05 |
| F17 | Pre-Roll | `VoiceSTT/core/preroll.py` | `tests/unit/test_preroll.py`, `test_audio_recorder_preroll_integration.py` | getestet | 05 |
| F18 | Silero-ONNX-VAD | `VoiceSTT/core/silero_vad.py` | `tests/unit/test_silero_vad_backend.py` | getestet | 05 |
| F19 | Aktivierungs-Zustandsmaschine (5 Phasen, 4 Timer) | `api_fastapi_server/activation.py` | `tests/unit/test_server_activation_controller.py`, `test_server_command_timer_e2e.py` | getestet | 05 |
| F20 | Manueller Trigger / Befehls-Idempotenz | `activation_commands.py`, `server.py:handle_trigger_command` | `tests/unit/test_server_activation_commands.py`, `test_server_trigger_contract.py` | getestet | 05, 07 |
| F21 | Audio-Verfügbarkeit | `server.py:handle_audio_availability_command`, V2 `audio_availability.set` | `tests/unit/test_protocol_v2_e2e.py`, `test_server_controlled_e2e.py` | getestet | 05 |
| F22 | Wake-Word-Katalog (25 Einträge, atomarer Refresh) | `VoiceSTT/core/wakeword_catalog.py` | `tests/unit/test_wakeword_catalog.py`, `test_wakeword_catalog_api.py`, `test_wakeword_asset_integrity.py` | getestet, beobachtet | 05 |
| F23 | Wake-Erkennung → Admission (exactly-once) | `VoiceSTT/core/wake_detection.py`, `api_fastapi_server/wake_admission.py` | `tests/unit/test_wake_detection.py`, `test_wake_admission.py`, `test_wakeword_session_e2e.py` | getestet | 05 |
| F24 | Wake-Audiogrenze | `VoiceSTT/core/wake_audio_boundary.py` | `tests/unit/test_wake_audio_boundary.py` | getestet | 05 |
| F25 | Wake-Parameter `cooldownMs`, `detectorGain`, `minConsecutivePredictionFrames`, `preRollMs`, `vadThreshold` | `settings_control.py` | `tests/unit/test_settings_control_plane.py` | experimentell (`calibration: "pending"`) | 03, 05 |
| F26 | TFLite-Wake-Backend | `wakeword_catalog.py` | `tests/unit/test_wakeword_catalog.py` | lokal `runtime_unavailable` beobachtet; Verfügbarkeit hängt von installierter Runtime ab | 05 |
| F27 | HTTP-Admin-/Status-API (30 HTTP-Routen) | `server.py:create_app` | `tests/unit/test_fastapi_server_protocol.py`, `test_server_security_modularization.py` | getestet, teilweise beobachtet | 06 |
| F28 | OpenAI-kompatible Transkription inkl. SSE | `openai_routes.py`, `openai_compat.py` | `tests/unit/test_openai_compatible_endpoint.py` | getestet, `/v1/models` beobachtet | 06 |
| F29 | WebSocket V1 `/ws/transcribe` | `server.py:websocket_transcribe` | `tests/unit/test_server_trigger_contract.py`, `test_protocol_v1_v2_boundary.py`, `test_browser_client_contract.py` | getestet | 07 |
| F30 | WebSocket V2 `/ws/v2` (Handshake, 5 Kommandos, 15 Result-Codes, 18 Ereignisse, Snapshot) | `api_fastapi_server/protocol_v2/*` | `tests/unit/test_protocol_v2_contract.py`, `_e2e.py`, `_races.py`, `_state_version.py`, `_terminal_recovery.py` | getestet | 07 |
| F31 | Live-Logs `/ws/logs` + Historie | `server.py:websocket_logs`, `_log_events_response` | `tests/unit/test_fastapi_server_multi_user.py`, `test_protocol_v2_e2e.py` | getestet | 07, 09 |
| F32 | Admin-/OpenAI-/Log-Zugriffskontrolle | `api_fastapi_server/security/*` | `tests/unit/test_server_security_modularization.py` | getestet, beobachtet (Loopback-Admin) | 08 |
| F33 | Kroko-Lizenzprüfung modellbezogen, Force-Community | `security/kroko.py`, `VoiceSTT/kroko/license_*.py` | `tests/unit/test_kroko_license_lifecycle.py`, `test_kroko_live_license.py` | getestet | 08 |
| F34 | Kroko-Native-Guard (Neustartpflichten) | `VoiceSTT/kroko/native_guard.py` | `tests/unit/test_kroko_pr15_final_correction.py`, `test_kroko_pr15_b1b2_regression.py` | getestet | 08 |
| F35 | Eventkanäle, Redaktion, SQLite-Store | `VoiceSTT_server/event_logging.py` | `tests/unit/test_server_operations.py`, `test_fastapi_server_multi_user.py` | getestet | 09 |
| F36 | Entwickler-Wheel + CI-Installationsprüfung | `setup.py`, `.github/workflows/ci.yml` | CI, `tests/packaging/test_identity_installation.py` | getestet | 10 |
| F37 | Produkt-Wheel mit eingebettetem Kroko | `engineering/tools/build_distribution.py` | `tests/unit/test_build_distribution.py`, `test_unified_product.py` | getestet (ohne echten Native-Build lokal) | 10 |
| F38 | Produktionsimage | `Dockerfile`, `engineering/tools/build_production.py` | `tests/unit/test_production_docker_contract.py`, `test_build_production.py` | getestet (Vertragsprüfung, kein lokaler Docker-Build) | 02, 10 |
| F39 | Release-Candidate-Workflow | `release-candidate.yml`, `engineering/tools/release_candidate.py` | `tests/unit/test_release_candidate.py`, `test_release_workflows.py` | getestet (statisch); nicht ausgeführt | 10 |
| F40 | Release-State-Machine + Veröffentlichung | `engineering/release/*`, `release-publish.yml` | `tests/unit/test_release_*.py` | blockiert (`build/kroko-redistribution.json: BLOCKED`) | 08, 10 |
| F41 | Alt-Server `stt-server-legacy` / CLI `stt` | `VoiceSTT_server/stt_server.py`, `stt_cli_client.py` | CI prüft nur Existenz der Console-Scripts | im Code nicht eindeutig als V2-qualifiziert nachweisbar | 02 |
| F43 | CPU-only-Abhängigkeitsvertrag (CPU-Torch + Constraint + Nachweis) | `engineering/tools/cpu_only.py`, `.github/workflows/ci.yml`, `engineering/tools/qualify_build_identity.py`, `Dockerfile` | `tests/unit/test_cpu_only_contract.py`; echte Installation nur in GitHub-CI (lokal: `download.pytorch.org` durch Netzwerkrichtlinie gesperrt) | getestet (Logik/Verdrahtung); Installationsnachweis über CI | 02, 10 |
| F44 | Engineering-Struktur + Kompatibilitätseinstiege (`tools/`, `release_tooling/`, `build/vps/*.sh`) | `engineering/`, `tools/*.py`, `release_tooling/__init__.py` | `tests/unit/test_engineering_path_contract.py` | getestet | 01, 11 |
| F42 | Beispiel-Browserclient | `examples/app_browserclient/` | `tests/unit/test_browser_client_contract.py` | getestet (Vertrag) | 07 |

## Abdeckungsprüfung

- **HTTP-Routen:** Eine AST-Auswertung aller Routen-Dekoratoren
  (`api_fastapi_server/*.py`, `VoiceSTT_server/*.py`,
  `voice_stt_server/*.py`) ergab 37 Einträge (32 HTTP-Methoden/Pfad-Paare
  aus `server.py` und `openai_routes.py`, 3 WebSockets). Alle stehen in
  Seite 06 bzw. 07. `tests/unit/test_v2_code_reference.py` prüft, dass jeder
  per AST gefundene Pfad in Seite 06 oder 07 vorkommt.
- **V2-Vokabular:** `tests/unit/test_v2_code_reference.py` prüft, dass alle
  `COMMAND_TYPES`, `RESULT_CODES` und `EVENT_TYPES` aus
  `protocol_v2/schema.py` in Seite 07 genannt sind.
- **V2-Settings:** derselbe Test prüft, dass jeder Registry-Schlüssel in
  Seite 03 steht.
- **Engines:** derselbe Test prüft, dass jeder Name aus `ENGINE_CLASS_PATHS`
  in Seite 04 steht.
- **V1-Nachrichtenfelder und Recorder-Parameter:** seit dieser Fassung
  maschinell erzeugt in Seite 13 (AST bzw. `inspect.signature`, 86
  Parameter).
- **Grenzen:** Die Feldlisten in Seite 13 sind die Vereinigung literaler
  Dict-Schlüssel; zur Laufzeit dynamisch ergänzte Felder sind dort nur
  benannt, soweit der Code sie explizit hinzufügt. Eine „100 %“-Aussage wird
  nicht getroffen.
