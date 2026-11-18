# AP-SRV-070 — W0 DELTA-REVALIDATION UND SCOPE FREEZE

**Datum:** 2026-08-29
**Verfasser:** Antigravity (AI Pair Programmer)
**Status:** VALIDATED / SCOPE_FROZEN
**Canonical Workspace:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\einheitliche-triggerarchitektur`
**Canonical Git HEAD:** `c82923fc6ce889b4dfbbde1f9877b8b76481a1e8`
**Canonical Git TREE:** `de6fe364545b508a47a87ead67a01c5732477e71`
**Distributed Git HEAD:** `1e74fec3096778d78c4f91e3916ef272c762ebd3`
**Historische Discovery-Basis:** `c901cda3f2c19eeb78c468524161728498b6e27e` (AP-SRV-050 Stand vom 2026-08-28)

---

## 1. Ausgangslage und Ziel

Vor Beginn der Umsetzung von **AP-SRV-070** (Server-Legacyabbau und Protokollgrenze) wurde die historische Discovery vom 2026-08-28 gegen den finalen, integrierten Stand von **AP-SRV-060** (`c82923fc6ce889b4dfbbde1f9877b8b76481a1e8`) revalidiert.

In der historischen Discovery vom 2026-08-28 war die gesamte Wake-Word-Zone als `EXCLUDED_WAKEWORD_ZONE` markiert, da AP-SRV-060 zu diesem Zeitpunkt noch nicht abgeschlossen war. Mit dem Abschluss von AP-SRV-060 sind nun alle Wake-Word-Assets, Katalogstrukturen, Detection-Module und Endpunkte im Repository vorhanden.

Diese Delta-Revalidation beweist für jeden alten und neuen Kandidaten den tatsächlichen Ist-Zustand, friert den Scope für AP-SRV-070 verbindlich ein und definiert den priorisierten Ausführungsbacklog für die Blöcke **W1 bis W6**.

---

## 2. Prüffelder: Detaillierte Befunde

### A. Runtime / Legacy

Jeder historische Remove- und Migration-Candidate wurde im aktuellen Codebaum (`c82923f`) nachgewiesen:

1. **`RealtimeSession` (server.py:2292–2724):**
   - *Befund:* Eine monolithische Inline-Session-Klasse mit eigenem VAD und Streaming-Loop (ca. 433 Zeilen).
   - *Callsites:* Exakt **0 Instanziierungen** im gesamten Produktiv- und Testcode. Die einzige Erwähnung ist eine veraltete Typannotation in `server.py:6391` (`self._sessions: Dict[str, RealtimeSession]`), während die tatsächliche Session-Erzeugung an Zeile 6752 `RecorderBackedRealtimeSession` instanziiert.
   - *Klassifikation:* `CONFIRMED_REMOVE`.

2. **`VoiceActivityDetector` (server.py:2256–2291):**
   - *Befund:* VAD-Wrapperklasse um `webrtcvad` mit RMS-Energie-Fallback (36 Zeilen).
   - *Callsites:* Wird ausschließlich innerhalb von `RealtimeSession.__init__` (Zeile 2299) instanziiert.
   - *Klassifikation:* `CONFIRMED_REMOVE`.

3. **`ACTION_ALIASES = {"extend": REFRESH}` (activation_commands.py:52):**
   - *Befund:* Normalisiert die veraltete v1-Aktion `extend` auf `refresh`.
   - *Callsites:* Wird in `_normalized_action()` an Zeile 179 genutzt. Additive Extend-Semantik ist bereits seit AP-SRV-030 entfernt.
   - *Klassifikation:* `CONFIRMED_REMOVE`.

4. **`SESSION_ACTIVATION_RETIRED_QUERY_FIELDS = ("extensionSeconds",)` (server.py:996):**
   - *Befund:* Veralteter Query-Parameter-Filter. Ignoriert `extensionSeconds` bei der URL-Auswertung.
   - *Callsites:* Wird an Zeile 7134 in `_extract_activation_parameters` referenziert.
   - *Klassifikation:* `CONFIRMED_REMOVE`.

5. **`ACTIVATION_ACTION_ALIASES_PUBLIC = ("extend",)` (server.py:1001):**
   - *Befund:* Öffentliche Liste für v1-Aktionsaliase. Redundant mit `activation_commands.py`.
   - *Klassifikation:* `CONFIRMED_REMOVE`.

6. **`ActivationController.finalized()` und Phase `finalizing`:**
   - *Befund:* Weder die Methode `finalized()` noch die Phase `finalizing` existieren in `api_fastapi_server/activation.py`. Die 5 kanonischen Phasen sind `IDLE`, `WAITING_FIRST_SPEECH`, `SEGMENT_ACTIVE`, `FOLLOWUP_WAIT`, `CLOSING_INPUT`.
   - *Klassifikation:* `SUPERSEDED_ALREADY`.

7. **Veralteter Wake-Word-Katalog `VoiceSTT/core/openwakeword_catalog.py` (310 Zeilen):**
   - *Befund:* Stand vor AP-SRV-060. Paralleler Legacy-Scanner, der noch von `VoiceSTT_server/operations.py` (`WakeWordRegistry`) und `VoiceSTT/core/wakeword.py` importiert wird, während der kanonische, package-gebundene Katalog in `VoiceSTT/core/wakeword_catalog.py` liegt.
   - *Klassifikation:* `MIGRATE_BEFORE_REMOVE` / `CONFIRMED_REMOVE` in W1.

8. **`WakeWordRegistry` in `VoiceSTT_server/operations.py` (Zeilen 244–275):**
   - *Befund:* Nutzt `OpenWakeWordCatalog`. Dient als Zwischenadapter.
   - *Klassifikation:* `MIGRATE_BEFORE_REMOVE` (auf `wakeword_catalog.py` umstellen).

9. **Kompatibilitätsweiche `activation_config.mode == "legacy"` (server.py:1167, 2801, etc.):**
   - *Befund:* Schützt Aufrufer ohne Triggerparameter (z. B. unkoordinierte Browser-Clients oder Multi-User-Legacy-Tests) und routet ungesteuerte Sessions über den Legacy-Pfad.
   - *Klassifikation:* `KEEP_REQUIRED` (solange v1-Transport und bestehende Tests aktiv sind).

10. **`_compat_final_context` (server.py:5120):**
    - *Befund:* Erzeugt synthetische Segment-Kontexte (`legacy-{session_id}-{seq}`) für unkoordinierte Aufnahmen ohne aktiven `ActivationController`.
    - *Klassifikation:* `KEEP_REQUIRED`.

11. **`_start_wakeword_followup_window` (server.py:5860):**
    - *Befund:* Legacy Wake-Word-Follow-up-Timer, explizit verdrahtet hinter `if self._activation is None:`.
    - *Klassifikation:* `KEEP_REQUIRED` (für Legacy-Mode).

12. **`AudioToTextRecorderClient` (`VoiceSTT/audio_recorder_client.py`):**
    - *Befund:* Öffentliche Client-Bibliothek. Außerhalb des Server-Bereichs.
    - *Klassifikation:* `OUT_OF_SCOPE`.

---

### B. Protocol v1/v2 Boundary

Die Untersuchung der Protokollgrenze zwischen `/ws/transcribe` (v1) und `/ws/v2` (v2) ergab:

1. **Transport-Isolation:**
   - Beide Transporte sind strikt über die URL getrennt (`/ws/transcribe` vs `/ws/v2`).
   - v1 nutzt Query-Parameter-basierte Admission ohne Handshake. Session-IDs sind 32-stellige hexadezimale Strings (`uuid.uuid4().hex`).
   - v2 nutzt einen strikten 3-Stufen-Handshake (`hello` -> `hello.accepted`). Session-IDs sind kanonische UUIDv4 mit Bindestrichen (36 Zeichen).

2. **Negative Boundary Tests (W1-Anforderung):**
   - *Invariante 1:* v1 (`/ws/transcribe`) lehnt v2-Envelope-Nachrichten (`{"type": "activation.command", ...}`, `{"type": "session_settings.patch", ...}`) mit einem wohlgeformten `{"type": "error", "where": "command", "message": "Unbekannter Befehl: ..."}` ab und interpretiert sie niemals als State-Change.
   - *Invariante 2:* v2 (`/ws/v2`) ignoriert unbekannte Nachrichtentypen oder v1-Befehle (`{"type": "trigger", ...}`, `{"type": "audio_availability", ...}`) nach `hello.accepted` gemäß dem eingefrorenen Wire-Contract ohne Ack oder wirft bei syntaktischen Fehlern den kanonischen Fehlercode.
   - *Invariante 3:* Cross-Transport Session-ID Isolation: Eine 32-Zeichen-v1-Session-ID wird auf v2 immer mit `invalid_payload` abgelehnt (`is_canonical_uuid` Guard).
   - *Invariante 4:* Protocol-Versionen: `SUPPORTED_PROTOCOL_VERSIONS` ist fixiert auf `(2,)`.
   - *Invariante 5:* Server-Identität: `serverVersion` und `serverCommit` sind über alle v2-Wire-Oberflächen (`hello.accepted`, `session.snapshot`, `protocol.incompatible`, `session.rejected`) konsistent.

---

### C. Wake Words nach AP-SRV-060

Die Prüfung des mit AP-SRV-060 integrierten Wake-Word-Systems ergab:

1. **Lokale Asset-Verankerung:**
   - 36 ONNX- und TFLite-Klassifikatoren sowie die Basis-Pipelinemodelle (`embedding_model.onnx`, `embedding_model.tflite`, `melspectrogram.onnx`, `melspectrogram.tflite`, `silero_vad.onnx`) liegen fest im Paket unter `VoiceSTT/assets/wakeword_models/`.
   - Die Manifestdatei `VoiceSTT/assets/wakeword_models/models.json` ist vorhanden und enthält alle Metadaten.
   - Es finden **keine Runtime-Downloads** statt. Offline-Betrieb ist vollständig sichergestellt.

2. **Katalog & API:**
   - `VoiceSTT/core/wakeword_catalog.py` ist die alleinige Wahrheitsquelle für die Modellauflösung.
   - Endpunkte `GET /api/v2/wake-words` und `POST /api/v2/wake-words/refresh` sind vollumfänglich in `server.py` implementiert.
   - Historischer Legacy-Katalog `VoiceSTT/core/openwakeword_catalog.py` muss in W1 entfernt und Verweise bereinigt werden.

---

### D. Product Surface & Dokumentation

Prüfung aller Dokumente und Repository-Ordnung für W2:

1. **`README.md` (Root):**
   - Muss auf Protocol v2 (`/ws/v2`), die einheitliche Triggerarchitektur und moderne Installations-Extras aktualisiert werden.
2. **`docs/fastapi-server.md`:**
   - Ergänzung der Dokumentation für `/ws/v2` und `/api/v2/wake-words`.
3. **`docs/einheitliche-triggerarchitektur.md`:**
   - Korrektur von Tippfehlern (z. B. `activation_command.py` -> `activation_commands.py`).
4. **`docs/module-map.md`:**
   - Entfernen des toten Verweises auf `docs/ARCHITECTURE.md`.
5. **`docs/api-compatibility.md`:**
   - Entfernen des hardcodierten Pfads `D:/Projekte/STT/...`.
6. **`docs/configuration.md`:**
   - Bereinigung gemischtsprachiger Abschnitte.
7. **Archivierungsbedürftige Planungs- und Spezifikationsdokumente:**
   - `Planning/logging-fixes-implementierungsplan.md` -> `docs/.archiv/logging-fixes/`.
   - `api_fastapi_server/MULTI_USER_IMPLEMENTATION_GUIDE.md` -> `docs/.archiv/multi-user-design/`.
   - `docs/stt-server-specification.md` -> `docs/.archiv/desktop-client-spec/`.
   - `docs/session-wakeword-erweiterung.md` -> Historische Teile archivieren.
8. **Bereinigung von Test-Binaries und redundanten Skripten:**
   - Binärdateien in `tests/` (`tests/suh_mahn_thuh.onnx`, `tests/suh_man_tuh.onnx`, `tests/samanta.tflite`) entfernen.
   - Redundante Batch-Wrapper (`app_browserclient/start_server.bat`, `app_talk_with_llm/start.bat`, `app_talk_with_llm/install_cpu.bat`) bereinigen.

---

### E. Packaging

Prüfung des Ist-Zustands von Packaging und Distributionsartefakten:

1. **Versions-Autorität:**
   - In `setup.py` ist `current_version = "1.0.2"` definiert, während `api_fastapi_server/protocol_v2/identity.py` `SERVER_VERSION = "2.0.0"` führt. Eine einheitliche Versionsautorität muss etabliert werden.
2. **Paket-Assets (`package_data` und `MANIFEST.in`):**
   - `package_data` in `setup.py` enthält `assets/wakeword_models/*` und `static/index.html`.
   - In `MANIFEST.in` fehlt die explizite Aufnahme von `api_fastapi_server/static/index.html` für Source-Distributionen (`sdist`).
3. **W3 Hard-Gates:**
   - Hard-Gate 1: `models.json` und alle 36+ Wake-Word-Modelle sind im gebauten Wheel enthalten.
   - Hard-Gate 2: Auflösung des Katalogs funktioniert in einer isolierten Installation rein über `importlib.resources`.
   - Hard-Gate 3: `GET /api/v2/wake-words` liefert in einer sauberen Wheel-Installation Status 200 und korrekten Kataloginhalt.
   - Hard-Gate 4: Zero-Download-Garantie bei Start des Servers aus dem installierten Paket.

---

### F. Docker & Deployment

Prüfung der Container- und Deploymentkonfigurationen:

1. **`Dockerfile`:**
   - Ist-Zustand: Nutzt `COPY . /app` und `pip install -e '.[faster-whisper,silero-onnx-cpu]'` (Editable Install auf Source-Checkout).
   - Soll-Zustand (W4): Sauberes Multi-Stage-Build mit Wheel-Erzeugung im Builder-Stage und reinem `pip install <wheel>` im Runtime-Stage.
   - Non-Root User: Einrichtung eines dedizierten unprivilegierten Nutzers (`appuser`).
   - OCI-Metadaten: Standard-Labels nach OCI Image Spec hinzufügen.
   - Traceability: `VOICESTT_SERVER_COMMIT` über Build-Arg in das Image übergeben.
2. **Compose-Dateien:**
   - `docker-compose.yml` und `build/vps/docker-compose.yml` bleiben kompatibel und werden gegen das neue Container-Image geprüft.

---

### G. Release Candidate & Publikation (W6 Planung)

Verbindliche Ablaufschritte für den finalen Block W6:

1. **Full Test Regression:** Ausführung der gesamten Testsuite auf Canonical.
2. **Package Build & Smoke:** Bau von `sdist` und `wheel`, Installation in einer frischen venv, Smoke Test aller Entry Points (`stt-server --help`, `GET /health`, `GET /api/v2/wake-words`).
3. **Container Build & Smoke:** Bau des Docker-Images, Container-Start mit Offline-Flags, Healthcheck-Verifikation.
4. **Hashes & Freeze:** Erzeugung von SHA-256 Hashes für alle Release-Artefakte.
5. **Archiv- & Registerabschluss:** Aktualisierung von `docs/.archiv/README.md` auf `Abgeschlossen`.

---

## 3. Fazit und Scope Freeze

- Die historische Discovery wurde lückenlos überprüft und mit dem Stand nach AP-SRV-060 abgeglichen.
- Alle Dead-Code-Stellen, Kompatibilitätsbrücken, Dokumentationslücken, Packaging- und Deploymentanforderungen sind eindeutig klassifiziert.
- Der Implementierungsplan für die Blöcke W1 bis W6 ist in `2026-08-29_W0_EXECUTION_BACKLOG.md` vollständig operationalisiert.
- **Scope Freeze ist wirksam.**
