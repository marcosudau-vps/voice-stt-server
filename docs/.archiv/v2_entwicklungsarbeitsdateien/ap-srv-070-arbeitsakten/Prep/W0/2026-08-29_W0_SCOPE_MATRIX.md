# AP-SRV-070 — W0 SCOPE MATRIX

**Datum:** 2026-08-29
**Basis:** Canonical `c82923fc6ce889b4dfbbde1f9877b8b76481a1e8` (TREE `de6fe364545b508a47a87ead67a01c5732477e71`)

---

## Scope-Matrix nach Prüffeldern

| ID | Bereich | Klassifikation | Dateien/Symbole | Begründung | Abhängigkeiten | Risiko | Zielblock W1-W6 |
|---|---|---|---|---|---|---|---|
| S01 | Runtime / Legacy | CONFIRMED_REMOVE | `api_fastapi_server/server.py` (`class RealtimeSession`) | Monolithische Inline-Session-Klasse (ca. 433 Z.). 0 Aufrufer / Instanziierungen im gesamten Code. Veraltet. | Keine (dead code) | LOW | W1 |
| S02 | Runtime / Legacy | CONFIRMED_REMOVE | `api_fastapi_server/server.py` (`class VoiceActivityDetector`) | VAD-Wrapperklasse für `RealtimeSession`. 0 Aufrufer außerhalb von `RealtimeSession.__init__`. | S01 | LOW | W1 |
| S03 | Runtime / Legacy | CONFIRMED_REMOVE | `api_fastapi_server/activation_commands.py` (`ACTION_ALIASES = {"extend": REFRESH}`) | Veraltetes v1-Alias-Mapping (`extend` -> `refresh`). Additive Semantik ist bereits tot. | `_normalized_action` | LOW | W1 |
| S04 | Runtime / Legacy | CONFIRMED_REMOVE | `api_fastapi_server/server.py` (`SESSION_ACTIVATION_RETIRED_QUERY_FIELDS`) | Ignoriert alte `extensionSeconds`-Parameter in URL-Querys. | Keine | LOW | W1 |
| S05 | Runtime / Legacy | CONFIRMED_REMOVE | `api_fastapi_server/server.py` (`ACTIVATION_ACTION_ALIASES_PUBLIC`) | Öffentliche Alias-Liste. Redundant mit S03. | S03 | LOW | W1 |
| S06 | Runtime / Legacy | SUPERSEDED_ALREADY | `api_fastapi_server/activation.py` (`finalized()`, `FINALIZING`) | Weder Methode noch Phase existieren in `activation.py`. Bereits in SRV-010..030 durch 5-Phasen-Modell ersetzt. | Keine | NONE | W1 (Dokumentation) |
| S07 | Wake Words / Legacy | MIGRATE_BEFORE_REMOVE | `VoiceSTT/core/openwakeword_catalog.py` | Veralteter Legacy-Katalog (310 Z.) vor SRV-060. Muss durch `VoiceSTT/core/wakeword_catalog.py` ersetzt und danach gelöscht werden. | `operations.py`, `wakeword.py` | LOW | W1 |
| S08 | Wake Words / Registry | MIGRATE_BEFORE_REMOVE | `VoiceSTT_server/operations.py` (`WakeWordRegistry`) | Verwendet noch `OpenWakeWordCatalog`. Auf kanonischen `WakeWordCatalog` (`wakeword_catalog.py`) umstellen. | S07 | LOW | W1 |
| S09 | Runtime / Legacy | KEEP_REQUIRED | `api_fastapi_server/server.py` (`activation_config.mode == "legacy"`) | Aktive Kompatibilitätsweiche für v1-Transport und Aufrufer ohne Triggerparameter (Browserclient, Multi-User-Tests). | v1-Transport | HIGH (bei Cut) | W1 (Schutz) |
| S10 | Runtime / Legacy | KEEP_REQUIRED | `api_fastapi_server/server.py` (`_compat_final_context`) | Erzeugt synthetische `legacy-{session_id}-{seq}`-Kontexte für ungesteuerte Sessions. | S09 | MEDIUM | W1 (Schutz) |
| S11 | Runtime / Legacy | KEEP_REQUIRED | `api_fastapi_server/server.py` (`_start_wakeword_followup_window`) | Legacy-Follow-up-Timer. Explizit hinter `if self._activation is None:` isoliert. | S09 | LOW | W1 (Schutz) |
| S12 | Runtime / Legacy | KEEP_REQUIRED | `api_fastapi_server/server.py` (`_trigger_ack`) | Ack-Format für den v1-Transport (`/ws/transcribe`). | v1-Transport | MEDIUM | W1 (Schutz) |
| S13 | Runtime / Legacy | KEEP_REQUIRED | `api_fastapi_server/protocol_v2/connection.py` (`_handle_activation_command`) | v2-zu-v1-Bridge für Session-Methoden. | `RecorderBackedRealtimeSession` | MEDIUM | W1 (Schutz) |
| S14 | Library API | OUT_OF_SCOPE | `VoiceSTT/audio_recorder_client.py` (`AudioToTextRecorderClient`) | Öffentliche Client-Bibliothek, wird u.a. von externen Skripten/CLI genutzt. Außerhalb des Server-Refactoring-Scopes. | Keine | NONE | W1 (Non-Touch) |
| S15 | Protocol Boundary | NEEDS_RUNTIME_PROOF | Negative Boundary Tests (`test_protocol_v1_v2_boundary.py`) | Konkrete negative Tests für Boundary-Schutz: v1 lehnt v2-Envelopes ab, v2 ignoriert v1-Typen ohne Ack, UUID-Isolation. | `/ws/transcribe`, `/ws/v2` | LOW | W1 |
| S16 | Protocol Boundary | NEEDS_RUNTIME_PROOF | Server-Identitätskonsistenz | `serverVersion`, `serverCommit` und `supportedProtocolVersions` über alle 4 Wire-Oberflächen einheitlich. | `identity.py`, `schema.py` | LOW | W1 |
| S17 | Product Surface / Docs | CONFIRMED_REMOVE | `Planning/logging-fixes-implementierungsplan.md` | Historischer Implementierungsplan, bereits umgesetzt. Gehört ins Archiv. | `.archiv/logging-fixes/` | LOW | W2 |
| S18 | Product Surface / Docs | CONFIRMED_REMOVE | `api_fastapi_server/MULTI_USER_IMPLEMENTATION_GUIDE.md` | Historischer Multi-User-Design-Guide von vor der Umsetzung. Gehört ins Archiv. | `.archiv/multi-user-design/` | LOW | W2 |
| S19 | Product Surface / Docs | CONFIRMED_REMOVE | `docs/stt-server-specification.md` | Übergabespezifikation für einen externen Desktop-Client. Gehört ins Archiv. | `.archiv/desktop-client-spec/` | LOW | W2 |
| S20 | Product Surface / Docs | MIGRATE_BEFORE_REMOVE | `docs/session-wakeword-erweiterung.md` | Enthält veraltete PowerShell-Verifikation und redundante Teile. Historisches archivieren, Fachliches in `docs/wake-words.md`. | `docs/wake-words.md` | LOW | W2 |
| S21 | Repo-Hygiene / Tests | CONFIRMED_REMOVE | `tests/suh_mahn_thuh.onnx`, `tests/suh_man_tuh.onnx`, `tests/samanta.tflite` | Binäre Modelldateien im Testverzeichnis. Modelle werden via Package-Assets gebündelt. | Testfixtures | LOW | W2 |
| S22 | Repo-Hygiene / Scripts | CONFIRMED_REMOVE | Redundante Batchskripte (`app_browserclient/start_server.bat`, `app_talk_with_llm/start.bat`, `app_talk_with_llm/install_cpu.bat`) | Redundante Wrapper-Batchskripte. PowerShell-Skripte sind kanonisch. | Keine | LOW | W2 |
| S23 | Product Surface / Docs | MIGRATE_BEFORE_REMOVE | `README.md` (Root) | Aktualisierung auf v2-Protokoll, einheitliche Triggerarchitektur, moderne Package-Extras. | Doku-Baseline | LOW | W2 |
| S24 | Product Surface / Docs | MIGRATE_BEFORE_REMOVE | `docs/fastapi-server.md` | Dokumentation für `/ws/v2`, `GET /api/v2/wake-words`, `POST /api/v2/wake-words/refresh` ergänzen. | Doku-Baseline | LOW | W2 |
| S25 | Product Surface / Docs | MIGRATE_BEFORE_REMOVE | `docs/einheitliche-triggerarchitektur.md`, `docs/module-map.md`, `docs/configuration.md`, `docs/api-compatibility.md` | Tippfehler, tote Links (`ARCHITECTURE.md`), hardcodierte Pfade und Sprachmischung bereinigen. | Doku-Baseline | LOW | W2 |
| S26 | Packaging | MIGRATE_BEFORE_REMOVE | `setup.py`, `VoiceSTT/__init__.py`, `api_fastapi_server/protocol_v2/identity.py` | Vereinheitlichung der Versionsautorität (Single Source of Truth für Package- und Serverversion). | Build-System | MEDIUM | W3 |
| S27 | Packaging / Manifest | MIGRATE_BEFORE_REMOVE | `MANIFEST.in` | Aufnahme von `api_fastapi_server/static/index.html` und Absicherung aller Wake-Word-Modelle für `sdist`. | `setup.py` | LOW | W3 |
| S28 | Packaging / Gates | NEEDS_RUNTIME_PROOF | W3 Hard-Gates (Wheel-Build & Isolated Install Smoke) | Nachweis, dass Wheel vollständig ohne Netzwerk installierbar ist, `models.json` findet und `GET /api/v2/wake-words` ausliefert. | S26, S27 | MEDIUM | W3 |
| S29 | Docker / Deployment | MIGRATE_BEFORE_REMOVE | `Dockerfile` | Umstellung auf Multi-Stage-Wheel-Install (kein Source-Checkout / kein Editable-Install), Non-Root-User (`appuser`), OCI-Labels, `VOICESTT_SERVER_COMMIT`. | S26, S28 | MEDIUM | W4 |
| S30 | Docker / Compose | NEEDS_RUNTIME_PROOF | `docker-compose.yml`, `build/vps/docker-compose.yml` | Validierung der Compose-Konfigurationen gegen das gehärtete Container-Image mit Offline-Flags. | S29 | LOW | W4 |
| S31 | Quality Assurance | NEEDS_RUNTIME_PROOF | Vollständige Unit- & Integrationsregression (W5) | Gesamte Testsuite (inkl. Wake-Word, Settings, Ledger, Protocol v2, Multi-User) läuft fehlerfrei durch. | W1..W4 | MEDIUM | W5 |
| S32 | Release / Archive | MIGRATE_BEFORE_REMOVE | Release Candidate Freeze & Archivabschluss (W6) | Artefakt-Hashes, Version Freeze, Tagging-Plan, `docs/.archiv/README.md` Statusabschluss. | W1..W5 | LOW | W6 |

---

## Zusammenfassung nach Klassifikation

| Klassifikation | Anzahl Positionen | Erläuterung |
|---|---|---|
| `CONFIRMED_REMOVE` | 10 | Sicher identifizierter Dead Code, veraltete Aliase, historische Planungsdateien, Binaries in Tests |
| `MIGRATE_BEFORE_REMOVE` | 9 | Notwendige Überarbeitungen vor Löschung (Katalog, Doku, Versioning, Manifest, Dockerfile) |
| `KEEP_REQUIRED` | 5 | Zwingend erforderliche Kompatibilitätsanker (Legacy-Mode-Weiche, v1-Ack, v2-Bridge) |
| `SUPERSEDED_ALREADY` | 1 | Bereits vor AP-SRV-070 beseitigt (finalized/finalizing) |
| `NEEDS_RUNTIME_PROOF` | 6 | Zu beweisende Hard-Gates, negative Tests, Regression, Docker-Smoke |
| `OUT_OF_SCOPE` | 1 | Unberührte externe Bibliotheksbestandteile (`AudioToTextRecorderClient`) |
| **Gesamt** | **32** | Vollständiges Portfolio für W1 bis W6 |
