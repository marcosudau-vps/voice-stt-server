# AP-SRV-070 — W0 EXECUTION BACKLOG (W1 BIS W6)

**Datum:** 2026-08-29
**Basis:** Canonical `c82923fc6ce889b4dfbbde1f9877b8b76481a1e8` (TREE `de6fe364545b508a47a87ead67a01c5732477e71`)

---

## Block W1: Runtime Legacy Cleanup & Protocol Boundary Hardening

| ID | Scope | Dateien/Symbole | Akzeptanzkriterium | Tests/Evidence | Abhängigkeiten | Priorität |
|---|---|---|---|---|---|---|
| W1-01 | Dead Code Removal | `api_fastapi_server/server.py` (`RealtimeSession`, `VoiceActivityDetector`) | Beide Klassen sind vollständig aus `server.py` entfernt. Typannotationen sind auf `RecorderBackedRealtimeSession` bereinigt. Keine Import- oder Typfehler. | `pytest tests/unit/test_fastapi_server_multi_user.py` | Keine | P0 |
| W1-02 | Action Alias Cleanup | `api_fastapi_server/activation_commands.py` (`ACTION_ALIASES`), `api_fastapi_server/server.py` (`ACTIVATION_ACTION_ALIASES_PUBLIC`) | `ACTION_ALIASES` und `ACTIVATION_ACTION_ALIASES_PUBLIC` sind entfernt. `_normalized_action` ist ein direkter Passthrough. Veralteter `extend`-Alias wird vom v1-Parser nicht mehr akzeptiert. | `pytest tests/unit/test_server_activation_commands.py` | Keine | P0 |
| W1-03 | Retired Query Fields | `api_fastapi_server/server.py` (`SESSION_ACTIVATION_RETIRED_QUERY_FIELDS`) | Die Konstante und die Filterlogik für `extensionSeconds` sind entfernt. | `pytest tests/unit/test_server_trigger_contract.py` | Keine | P1 |
| W1-04 | Wake Catalog Migration | `VoiceSTT/core/openwakeword_catalog.py`, `VoiceSTT_server/operations.py` (`WakeWordRegistry`), `VoiceSTT/core/wakeword.py` | `WakeWordRegistry` und `wakeword.py` nutzen ausschließlich den kanonischen `WakeWordCatalog` aus `VoiceSTT/core/wakeword_catalog.py`. `openwakeword_catalog.py` ist gelöscht. | `pytest tests/unit/test_server_operations.py tests/unit/test_wakeword_catalog.py` | Keine | P0 |
| W1-05 | Protocol Boundary Negative Tests | `tests/unit/test_protocol_v1_v2_boundary.py` (neu) | Explizite negative Tests beweisen: (1) `/ws/transcribe` weist v2-Envelopes mit Fehler ab; (2) `/ws/v2` ignoriert/weist v1-Messages ohne Zustandsänderung ab; (3) 32-Zeichen Hex-Session-IDs werden auf v2 abgewiesen; (4) `SUPPORTED_PROTOCOL_VERSIONS == (2,)`; (5) Server-Identität ist über alle v2-Responses konsistent. | `pytest tests/unit/test_protocol_v1_v2_boundary.py` | W1-01..W1-04 | P0 |

---

## Block W2: Product Documentation & Repository Cleanliness

| ID | Scope | Dateien/Symbole | Akzeptanzkriterium | Tests/Evidence | Abhängigkeiten | Priorität |
|---|---|---|---|---|---|---|
| W2-01 | Main Documentation Update | `README.md` | `README.md` beschreibt Protocol v2 (`/ws/v2`), die einheitliche Triggerarchitektur, Wake-Word-Funktionen und empfohlene Installationskommandos. | Doku-Review / Link-Check | Keine | P1 |
| W2-02 | Server API Documentation | `docs/fastapi-server.md` | Endpunkte `/ws/v2`, `GET /api/v2/wake-words` und `POST /api/v2/wake-words/refresh` sind mit Request/Response-Beispielen vollständig dokumentiert. | Doku-Review | Keine | P1 |
| W2-03 | Technical Docs Cleanliness | `docs/einheitliche-triggerarchitektur.md`, `docs/module-map.md`, `docs/configuration.md`, `docs/api-compatibility.md` | Tippfehler korrigiert, Verweis auf `ARCHITECTURE.md` entfernt, hardcodierte Pfade ersetzt, gemischtsprachige Abschnitte vereinheitlicht. | Doku-Review | Keine | P2 |
| W2-04 | Document Archival | `Planning/logging-fixes-implementierungsplan.md`, `api_fastapi_server/MULTI_USER_IMPLEMENTATION_GUIDE.md`, `docs/stt-server-specification.md`, `docs/session-wakeword-erweiterung.md` | Historische Planungs- und Spezifikationsdokumente sind ordnungsgemäß nach `docs/.archiv/` verschoben und verlinkt. | `git status`, Dateiprüfung | Keine | P1 |
| W2-05 | Repository Hygiene | `tests/suh_mahn_thuh.onnx`, `tests/suh_man_tuh.onnx`, `tests/samanta.tflite`, redundante `.bat`-Skripte | Binärdateien im Testverzeichnis und redundante Batchdateien sind gelöscht. Testsuite bleibt grün. | `pytest tests/unit/` | Keine | P1 |

---

## Block W3: Packaging, Assets & Installation Hard-Gates

| ID | Scope | Dateien/Symbole | Akzeptanzkriterium | Tests/Evidence | Abhängigkeiten | Priorität |
|---|---|---|---|---|---|---|
| W3-01 | Version Authority | `setup.py`, `VoiceSTT/__init__.py`, `api_fastapi_server/protocol_v2/identity.py` | Einheitliche Versionsquelle (Single Source of Truth) etabliert. Package-Version und Server-Version sind konsistent synchronisiert. | `python setup.py --version`, Identity-Test | Keine | P0 |
| W3-02 | Package Manifest Hardening | `MANIFEST.in`, `setup.py` | `MANIFEST.in` enthält alle benötigten Dateien inklusive `static/index.html` und Wake-Word-Modelle. Source-Distribution enthält alle Assets. | `python -m build --sdist`, `tar -tf dist/*.tar.gz` | W3-01 | P0 |
| W3-03 | Hard-Gate: Wheel Build & Offline Smoke | `dist/voicestt-*.whl` | Gebautes Wheel lässt sich in einer frischen, isolierten venv installieren. Katalog lädt alle 36 Modelle via `importlib.resources`. Server startet offline ohne Fehler. `GET /api/v2/wake-words` liefert Status 200. | `pip install <wheel>`, Smoke-Test-Skript | W3-01, W3-02 | P0 |

---

## Block W4: Dockerfile, OCI Metadata & Production Deployment

| ID | Scope | Dateien/Symbole | Akzeptanzkriterium | Tests/Evidence | Abhängigkeiten | Priorität |
|---|---|---|---|---|---|---|
| W4-01 | Dockerfile Multi-Stage Build | `Dockerfile` | Multi-Stage-Build baut ein Wheel im Builder-Stage und installiert das fertige Wheel im Runtime-Stage. Kein Source-Checkout (`COPY . /app`) im finalen Image, kein Editable Install. | `docker build -t voicestt:test .` | W3-03 | P0 |
| W4-02 | Non-Root & OCI Metadata | `Dockerfile` | Dedizierter unprivilegierten Nutzer (`appuser`), standardkonforme OCI Image Labels und Build-Arg `VOICESTT_SERVER_COMMIT` integriert. | `docker inspect voicestt:test` | W4-01 | P1 |
| W4-03 | Deployment Smoke Test | `docker-compose.yml`, `build/vps/docker-compose.yml` | Container startet erfolgreich mit Offline-Flags (`HF_HUB_OFFLINE=1`), Healthcheck wird nach Start grün (`assert ready and ok`). | `docker compose up -d`, Healthcheck-Prüfung | W4-01, W4-02 | P0 |

---

## Block W5: End-to-End Integration, Negative Testing & Regression Suite

| ID | Scope | Dateien/Symbole | Akzeptanzkriterium | Tests/Evidence | Abhängigkeiten | Priorität |
|---|---|---|---|---|---|---|
| W5-01 | Full Test Regression Suite | `tests/unit/` (gesamte Testsuite) | Alle bestehenden Unit- und Integrationstests (Trigger State Machine, Ledger, Commands, Timer, Protocol v2, Settings, Wake-Word, Multi-User) laufen fehlerfrei durch (100% PASS). | `pytest tests/unit/` | W1..W4 | P0 |
| W5-02 | Protocol Boundary Regression | `tests/unit/test_protocol_v1_v2_boundary.py`, `test_protocol_v2_contract.py` | Alle negativen Boundary- und Contract-Tests bestehen. Keine Cross-Transport-Leakage. | `pytest tests/unit/test_protocol_v1_v2_boundary.py tests/unit/test_protocol_v2_contract.py` | W1-05 | P0 |
| W5-03 | Live Server E2E Lifecycle Smoke | `api_fastapi_server/server.py` | FastAPI Server startet, führt WebSocket-Handshake auf `/ws/v2` durch, verarbeitet Streaming-Audio, liefert Events und schließt sauber über Signal/Shutdown. | E2E-Lifecycle-Testlauf | W5-01, W5-02 | P0 |

---

## Block W6: Release Candidate Freeze, Packaging Verification & Archive Closure

| ID | Scope | Dateien/Symbole | Akzeptanzkriterium | Tests/Evidence | Abhängigkeiten | Priorität |
|---|---|---|---|---|---|---|
| W6-01 | Release Artifacts & Hashes | `dist/` (`.whl`, `.tar.gz`) | Finale Build-Artefakte gebaut, SHA-256 Prüfsummen generiert und dokumentiert. | `sha256sum dist/*` | W5-01..W5-03 | P0 |
| W6-02 | Release Notes & Changelog | `RELEASE_NOTES.md` | Release Notes dokumentieren alle Neuerungen von AP-SRV-010 bis AP-SRV-070, Breaking Changes, Deprecations und Upgrade-Pfade. | Doku-Review | W6-01 | P1 |
| W6-03 | Archive & Register Closure | `docs/.archiv/einheitliche_triggerarchitektur/AP-SRV-070/`, `docs/.archiv/README.md` | Gesamtplanung, Soll-/Ist-Vergleich und Abweichungsdokumentation für AP-SRV-070 vollständig abgelegt. Register in `docs/.archiv/README.md` auf `Abgeschlossen` aktualisiert. | Archiv-Prüfung nach Projektregeln | W6-01, W6-02 | P0 |

---

## Backlog-Statistik

| Block | Anzahl Aufgaben | P0 | P1 | P2 |
|---|---|---|---|---|
| **W1: Runtime Legacy & Boundary** | 5 | 4 | 1 | 0 |
| **W2: Docs & Repository Hygiene** | 5 | 0 | 4 | 1 |
| **W3: Packaging & Hard-Gates** | 3 | 3 | 0 | 0 |
| **W4: Docker & Deployment** | 3 | 2 | 1 | 0 |
| **W5: E2E Regression & Quality** | 3 | 3 | 0 | 0 |
| **W6: Release Freeze & Closure** | 3 | 2 | 1 | 0 |
| **Gesamt** | **22** | **14** | **7** | **1** |
