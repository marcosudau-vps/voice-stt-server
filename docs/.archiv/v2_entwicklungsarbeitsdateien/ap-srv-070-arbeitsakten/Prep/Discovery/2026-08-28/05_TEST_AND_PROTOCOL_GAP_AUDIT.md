# 05_TEST_AND_PROTOCOL_GAP_AUDIT

**Discovery-Basis:** `c901cda3f2c19eeb78c468524161728498b6e27e`
**Datum:** 2026-08-28

---

## A. Legacy-Tests

### A1: Keine Tests mit Legacy-Erwartungen gefunden

**Suche nach:**
- `session.mode` als Runtime-Autorität
- Source-Merge-Verhalten
- Additiver `extend`-Semantik
- v1 Trigger-Pfaden als primär
- `finalizing` als Vordergrund-Phase
- Alter Session-Admission

**Ergebnis:** Keine Tests assertieren Legacy-Verhalten als Soll.

**Spezifische Beweise:**

| Legacy-Verhalten | Test | Status |
|---|---|---|
| `session.mode` als Runtime-Autorität | Keine | CLEAN |
| Source-Merge | Keine | CLEAN |
| Additive `extend` | `test_server_activation_controller.py` | PROVEN DEAD – Test beweist, dass `extend`-Attribut und `extension_seconds` nicht existieren |
| v1 Trigger-Pfad | `test_server_trigger_contract.py`, `test_server_controlled_e2e.py` | COMPATIBILITY_TEST – korrekt als Kompatibilität isoliert |
| `finalizing` als Phase | `test_server_activation_controller.py` | PROVEN EXCLUDED – Test beweist, dass "finalizing" nicht in beobachteten Phasen vorkommt |
| Alte Session-Admission | Keine | CLEAN |

---

## B. Stale Fixtures / Testdoubles

### B1: Keine STALE_FIXTURE oder MISLEADING_DOUBLE gefunden

**Analyse:**
- `GateAwareRecorder` in `test_server_controlled_e2e.py` verwendet das **reale** Produktions-Gate-Modul (`VoiceSTT.core.activation_control`)
- `FakeRecorder` in `test_fastapi_server_multi_user.py` ist explizit ein Non-Gate-Fake, nur für Multi-User-Plumbing-Tests, bei denen das Gate irrelevant ist
- `FakeController`/`FakeLedger` in `test_protocol_v2_contract.py` sind dokumentierte Snapshot-Projektions-Stands

**Fazit:** Testdoubles sind explizit darüber, was sie faken (Audio-Hardware, Transkriptionsmodell) und was sie an Produktion delegieren (Gate, Controller, Ledger, v2-Connection).

---

## C. Fehlende Cut-Guards

### C1: `MCG-1` – v1-Transport akzeptiert nie v2-Envelope-Nachrichten

**Unguarded Invariant:** Kein Test beweist, dass das Senden von `{"type":"activation.command", ...}` (einem v2-Command) an `/ws/transcribe` abgelehnt wird, statt stillschweigend fehlinterpretiert zu werden.

**Testtyp:** Integration (v1 WebSocket)
**Zieldatei:** `tests/unit/test_server_trigger_contract.py`
**Begründung:** v1-Router hat Catch-All, aber Fehlermeldung könnte irreführend sein.
**Risiko:** LOW – v1 hat Catch-All, aber keine explizite Test-Abdeckung

---

### C2: `MCG-2` – v2-Transport akzeptiert nie v1-Nachrichtentypen

**Unguarded Invariant:** Kein Test beweist, dass das Senden von `{"type":"trigger", ...}` (einem v1-Command) an `/ws/v2` nach `hello.accepted` abgelehnt wird. `commands.py` `COMMAND_TYPES` schließt es aus, aber keine E2E-Test führt dies aus.

**Testtyp:** Integration (v2 WebSocket)
**Zieldatei:** `tests/unit/test_protocol_v2_e2e.py`
**Begründung:** `commands.py:100-103` gibt `None` für unbekannte Typen zurück (still ignoriert). Kein Ack, kein Fehler – Client müsste fehlende Antwort erkennen.
**Risiko:** MEDIUM – verwirrter Client könnte auf Ack warten, das nie kommt

---

### C3: `MCG-3` – `SUPPORTED_PROTOCOL_VERSIONS` ist geschlossen bei `{2}`

**Unguarded Invariant:** Kein Test assertiert den Tupel-Inhalt. Eine zukünftige Ergänzung von Version 3 könnte die Menge still erweitern, ohne dass ein Test den Wire-Contract-Change bemerkt.

**Testtyp:** Unit (schema)
**Zieldatei:** `tests/unit/test_protocol_v2_contract.py`
**Begründung:** Schutz vor unbeabsichtigter Protocol-Expansion
**Risiko:** LOW – naming convention, aber könnte Clients verwirren

---

### C4: `MCG-4` – Serverversion ist über alle veröffentlichten Oberflächen konsistent

**Unguarded Invariant:** `identity.SERVER_VERSION = "2.0.0"` ist hartcodiert; Testvektoren verwenden `"2.0.0-test"`. Kein Test assertiert, dass `hello.accepted`, `session.snapshot`, `protocol.incompatible` und `session.rejected` alle dieselbe `serverVersion`/`serverCommit` in einer Verbindung tragen.

**Testtyp:** Integration
**Zieldatei:** `tests/unit/test_protocol_v2_e2e.py`
**Begründung:** Konsistenzprüfung über alle Server-Antworten
**Risiko:** LOW – operationelles Concern

---

### C5: `MCG-5` – v1 Session-IDs sind kompaktes Hex; v2 Session-IDs sind kanonische UUIDs – keines leckt über die Grenze

**Unguarded Invariant:** Kein Test beweist, dass eine v1 kompakte Hex-`sessionId` vom v2-Endpunkt abgelehnt wird (der v2-Endpunkt erstellt eigene kanonische IDs, aber eine vom Client gelieferte kompakte Hex in einem Command wird nur auf `is_canonical_uuid`-Ablehnung getestet, nicht auf Cross-Transport-Verwechslung).

**Testtyp:** Integration
**Zieldatei:** `tests/unit/test_protocol_v2_e2e.py`
**Begründung:** Schutz vor Cross-Transport-ID-Verwechslung
**Risiko:** LOW – by-design Isolation, aber keine Test-Abdeckung

---

### C6: `MCG-6` – `DEFAULT_HANDSHAKE_TIMEOUT_SECONDS` ist auffindbar und konsistent

**Unguarded Invariant:** Der 10-Sekunden-Timeout ist in `schema.py:202` hartcodiert und auf Verhalten getestet (`test_a_silent_client_hits_the_handshake_timeout`), aber kein Test assertiert, dass der spezifische Wert dokumentiert/veröffentlicht ist.

**Testtyp:** Unit
**Zieldatei:** `tests/unit/test_protocol_v2_contract.py`
**Begründung:** Sicherstellung, dass Timeout-Wert nicht still driftet
**Risiko:** LOW

---

### C7: `MCG-7` – Kein v1-Endpunkt-Test assertiert, dass v1 nie kanonische v2-Event-Namen emittiert

**Unguarded Invariant:** Der Test `test_no_legacy_event_name_reaches_a_v2_connection` in `test_protocol_v2_e2e.py:1104-1124` beweist dies für v2, aber kein symmetrischer Test beweist, dass v1 nie `activation.started`, `activation.phase_changed`, etc. emittiert.

**Testtyp:** Integration
**Zieldatei:** `tests/unit/test_server_trigger_contract.py`
**Begründung:** Symmetrische Protokoll-Isolationsprüfung
**Risiko:** LOW

---

### C8: `MCG-8` – `PROTOCOL_VERSION = 2` Konstante ist der einzige Wert, den `negotiate()` zurückgeben kann

**Unguarded Invariant:** Der Negotiation-Test `test_negotiation_picks_the_highest_shared_version` (`test_protocol_v2_contract.py:1078`) testet mit `[1,2,3]` → `2` und `[2]` → `2`, aber kein Test assertiert, dass `PROTOCOL_VERSION` und `max(SUPPORTED_PROTOCOL_VERSIONS)` immer gleich sind, was einen zukünftigen Drift verhindert, bei dem die Konstante erhöht wird, das Tupel aber nicht (oder umgekehrt).

**Testtyp:** Unit (schema)
**Zieldatei:** `tests/unit/test_protocol_v2_contract.py`
**Begründung:** Schutz vor Version-Drift zwischen Konstante und Tupel
**Risiko:** LOW

---

### C9: `MCG-9` – Kein Test assertiert, dass v1 `activationConfig.mode` `"legacy"` ist, wenn keine Trigger-Parameter gesendet werden UND dass der v1-Endpunkt nie `"controlled"` Modus für query-freie Verbindungen bewirbt

**Unguarded Invariant:** `test_a_session_without_trigger_parameters_stays_legacy` (`test_server_controlled_e2e.py:437-453`) deckt dies ab, aber nur für den `trigger`-Ablehnungspfad, nicht für die volle `activationConfig`-Form-Stabilität.

**Testtyp:** Integration
**Zieldatei:** `tests/unit/test_server_controlled_e2e.py`
**Begründung:** Vollständige Shape-Stabilitätsprüfung für v1-Admission
**Risiko:** LOW

---

## D. Aktuelle Protocol Boundary

### D1: Zwei unabhängige Protokoll-Transporte

**v1-Transport** (`/ws/transcribe`, `server.py:9206`):
- Session über **Query-Parameter** admitted (`manualTriggerEnabled`, `wakeWordTriggerEnabled`, Wake-Word-Query-Parameter)
- Session-ID ist **kompaktes Hex** (`uuid.uuid4().hex`, 32 Zeichen, `server.py:9232`)
- Hello wird **sofort vom Server** gesendet (kein Client-Handshake erforderlich)
- Nachrichten-Vokabular: `start`, `stop`, `trigger`/`trigger_ack`, `audio_availability`/`audio_availability_ack`, `metrics`, `timeline`, `realtime`, `final`, `status`, `error`, `clear`
- Activation-Config über `activationConfig.mode` ∈ `{"legacy", "controlled"}` angekündigt
- Keine Protocol-Version-Negotiation; kein `protocolVersion`-Feld in Nachrichten
- Serverversion in Hello veröffentlicht, aber kein `serverCommit`

**v2-Transport** (`/ws/v2`, `server.py:9415`):
- Session über **`hello`-Handshake** mit drei Stufen (Envelope → Version → Session)
- Session-ID ist **kanonische UUID** (mit Bindestrichen, 36 Zeichen, `schema.py:207-209`)
- Client muss zuerst `hello` senden; nichts wird vor `hello.accepted` akzeptiert
- Nachrichten-Vokabular: `hello`/`hello.accepted`, `activation.command`/`command.ack`, `trigger_suppression.set`, `audio_availability.set`, `session_settings.patch`, `session.snapshot.request`, `session.snapshot`
- Protocol-Version negotiiert: `PROTOCOL_VERSION = 2`, `SUPPORTED_PROTOCOL_VERSIONS = (2,)`
- Server-Identität: `serverVersion` + `serverCommit` in jeder Antwort
- Eingefrorener Event-Katalog mit `stateVersion` + `eventSeq` monotonen Invarianten

**Grenze:** Die beiden Transporte sind **isoliert über URL-Pfad** (`/ws/transcribe` vs `/ws/v2`) und **isoliert über Admission** (Query-Parameter vs `hello`-Handshake). Sie teilen denselben `VoiceSTTService.admit_session()`, aber mit unterschiedlichen Parametern.

---

## E. Protocol Gaps

### E1: `GAP-1` – v1-Endpunkt hat kein Protocol-Version-Gate

**Risiko:** MEDIUM
**Ort:** `server.py:9206-9280`
**Problem:** Ein v2-fähiger Client, der sich mit `/ws/transcribe` verbindet, wird mit Query-Parameter-basierter Admission admitted und erhält v1-Nachrichten. Es gibt keinen "please upgrade to /ws/v2" Redirect oder Negotiation-Hinweis.
**Auswirkung:** Ein Client, der beide Protokolle implementiert, könnte versehentlich v1 verwenden und die v2-Garantien verpassen.

---

### E2: `GAP-2` – v1-Endpunkt lehnt v2-Command-Typen nicht ab

**Risiko:** LOW
**Ort:** `server.py` v1 command handler
**Problem:** Das Senden von `{"type":"activation.command", ...}` an `/ws/transcribe` wird vom v1-Command-Router behandelt, der es wahrscheinlich als unbekanntes Command behandelt (gibt `error` zurück), aber dies ist nicht getestet (siehe MCG-1).
**Auswirkung:** Die Fehlermeldung könnte irreführend sein.

---

### E3: `GAP-3` – v2-Endpunkt lehnt v1-Command-Typen nicht explizit ab

**Risiko:** MEDIUM
**Ort:** `commands.py:100-103`, `connection.py:342-345`
**Problem:** Das Senden von `{"type":"trigger", ...}` an `/ws/v2` fällt in `commands.py:102` (`message_type not in schema.COMMAND_TYPES`), das `None` zurückgibt (still ignoriert). Kein Ack, kein Fehler – der Client muss die fehlende Antwort erkennen.
**Auswirkung:** Ein verwirrter Client könnte warten auf ein Ack, das nie kommt. Der eingefrorene Contract sagt "unbekannte Nachrichtentypen dürfen nicht als bekannte Zustandsänderung interpretiert werden", verlangt aber keine Fehlerantwort.

---

### E4: `GAP-4` – Keine Version-Anzeige auf v1

**Risiko:** LOW
**Ort:** `server.py:9296-9302`
**Problem:** Das v1-Hello enthält nicht `supportedProtocolVersions` oder irgendeinen Hinweis, dass v2 existiert. Ein v1-Client hat keine maschinenlesbare Möglichkeit, v2 zu entdecken.
**Auswirkung:** Verpasste Gelegenheit für Protocol-Evolution.

---

### E5: `GAP-5` – `SERVER_VERSION = "2.0.0"` ist unabhängig von der Protocol-Version hartcodiert

**Risiko:** LOW
**Ort:** `identity.py:16`, `schema.py:27`
**Problem:** Die Version `2.0.0` entspricht nicht mechanisch `PROTOCOL_VERSION = 2`. Wenn das Protocol auf 3 fortschreitet, könnte die Serverversion nicht entsprechend fortschreiten, und umgekehrt. Kein Test verknüpft sie.
**Auswirkung:** Könnte Clients verwirren.

---

### E6: `GAP-6` – v1 Session-IDs lecken kompaktes Hex in eine UUID-Namespace-Welt

**Risiko:** LOW
**Ort:** `server.py:9232`, `schema.py:212-226`
**Problem:** v1 verwendet `uuid.uuid4().hex` (32 Zeichen, keine Bindestriche). v2 verwendet kanonische UUIDs (36 Zeichen, Bindestriche). Ein Client, der eine v1-Session-ID speichert und sie später v2 präsentiert, erhält `RESULT_INVALID_PAYLOAD` (nicht `RESULT_STALE_SESSION`), was technisch korrekt, aber verwirrend sein kann.
**Auswirkung:** By-design Isolation, aber kein Test beweist die Grenze.

---

### E7: `GAP-7` – `serverCommit` fällt still auf `"unknown"` zurück

**Risiko:** LOW
**Ort:** `identity.py:26-30`
**Problem:** Wenn `VOICESTT_SERVER_COMMIT` nicht gesetzt ist (was für Nicht-CI-Builds der Standard ist), trägt jede Handshake-Antwort `"serverCommit": "unknown"`. Ein Client kann nicht unterscheiden "Server kennt seinen Commit nicht" von "der Commit ist buchstäblich der String 'unknown'".
**Auswirkung:** Operationelles Concern.

---

### E8: `GAP-8` – Kein gemeinsames Versionsmanifest

**Risiko:** MEDIUM
**Ort:** `identity.py:16`, `schema.py:27-30`, `protocol-v2-vectors.json:3`
**Problem:** `SERVER_VERSION`, `PROTOCOL_VERSION`, `SUPPORTED_PROTOCOL_VERSIONS`, die Testvektor-`clientVersion` und der Contract-`protocolVersion` sind alle unabhängig definiert. Ein Drift zwischen ihnen würde nur vom `test_the_vector_file_targets_this_protocol_version`-Test bemerkt (der nur die Vektordatei prüft, nicht die Server-Identität).
**Auswirkung:** Ein zukünftiger Version-Bump könnte eine der fünf Stellen verfehlen.

---

### E9: `GAP-9` – v1 `activationConfig.mode` ist eine serverseitige Entscheidung, die der Client nicht überschreiben kann

**Risiko:** LOW
**Ort:** `server.py:1120-1160`
**Problem:** Der Modus ("legacy" vs "controlled") wird durch das Vorhandensein von `manualTriggerEnabled`/`wakeWordTriggerEnabled` Query-Parametern entschieden. Ein Client, der weder sendet, erhält "legacy"-Modus ohne Möglichkeit, "controlled"-Modus anzufordern, außer durch Hinzufügen der Query-Parameter. Dies ist by-design, aber nicht maschinenlesbar dokumentiert.
**Auswirkung:** Informationell.

---

### E10: `GAP-10` – v1-Endpunkt akzeptiert Verbindungen ohne jegliche Client-Identität

**Risiko:** LOW
**Ort:** `server.py:9207-9211`
**Problem:** Keine `clientRunId`, keine `clientVersion`, kein `clientCommit`. Das v1-Hello trägt `clientId` (optional, aus Query-Parameter oder Header), aber nichts Versionsbezogenes.
**Auswirkung:** v1 ist der Kompatibilitätspfad; volle Identität ist ein v2-Feature.

---

## F. Empfohlene spätere Tests

### F1: `LATER_CUT_ACTIONS` – Zukünftige Änderungen zum Schließen der Gaps

| # | Aktion | Begründung | Priorität |
|---|--------|-----------|----------|
| LCA-1 | Upgrade-Hinweis zu v1-Hello hinzufügen. `"protocolUpgrade": {"recommendedVersion": 2, "endpoint": "/ws/v2"}` in v1-Hello einfügen. | Schließt GAP-1 und GAP-4. Non-breaking: v1-Clients ignorieren unbekannte Felder. | High |
| LCA-2 | Explizite v2-Ablehnung für v1-Nachrichtentypen hinzufügen. `RESULT_INVALID_PAYLOAD` (mit Ack) zurückgeben statt unbekannte Nachrichtentypen still zu ignorieren auf `/ws/v2`. | Schließt GAP-3. | Medium |
| LCA-3 | Test hinzufügen, der beweist, dass v1 v2-Command-Typen mit klarem Fehler ablehnt. | Schließt MCG-1 und GAP-2. | High |
| LCA-4 | Test hinzufügen, der beweist, dass v2 v1-Command-Typen mit Ack ablehnt. | Schließt MCG-2 und GAP-3. | High |
| LCA-5 | `SERVER_VERSION` und `PROTOCOL_VERSION` in ein Versionsmanifest vereinheitlichen. Eine einzige Quelle der Wahrheit, aus der alle fünf Stellen (`identity.py`, `schema.py`, Testvektoren, Doku, Hello) lesen. Test hinzufügen, der assertiert, dass `SERVER_VERSION`, `PROTOCOL_VERSION` und `max(SUPPORTED_PROTOCOL_VERSIONS)` gegenseitig konsistent sind. | Schließt GAP-5, GAP-8, MCG-3, MCG-8. | Medium |
| LCA-6 | Cross-Surface-Server-Identitäts-Konsistenztest hinzufügen. Assertieren, dass `hello.accepted`, `session.snapshot`, `protocol.incompatible` und `session.rejected` alle dieselbe `serverVersion`/`serverCommit`/`supportedProtocolVersions` in einer Verbindung tragen. | Schließt MCG-4 und GAP-7. | Medium |
| LCA-7 | v1 `/ws/transcribe` mit Sunset-Timeline deprecated kennzeichnen. `Deprecation: true` Header oder Deprecation-Hinweis in v1-Hello hinzufügen. Sunset-Datum dokumentieren. | Strategisch: v1 ist die größte Angriffsfläche für Protocol-Boundary-Probleme. | Low (future) |
| LCA-8 | `clientRunId`-Äquivalent zu v1 hinzufügen. Selbst eine einfache UUID würde es v1-Sessions ermöglichen, in Logs eindeutig identifiziert zu werden und den Übergang zu v2 für Clients zu erleichtern. | Low – v1 ist der Kompatibilitätspfad. | Low |
| LCA-9 | `serverCommit` fail-closed machen. Wenn `VOICESTT_SERVER_COMMIT` nicht gesetzt ist, Sentinel wie `"not-provided"` statt `"unknown"` zurückgeben, oder Start verweigern. | Schließt GAP-7. | Low |
| LCA-10 | Protocol-Version-Feld zu v1-Hello hinzufügen. Selbst ein statisches `"protocolVersion": 1` würde die Version explizit machen und zukünftige Negotiation ermöglichen. | Schließt GAP-4, GAP-10. | Low |

---

## Zusammenfassung

| Kategorie | Anzahl |
|---|---|
| A. Legacy-Tests | 0 (alle CLEAN oder COMPATIBILITY_TEST) |
| B. Stale Fixtures / Testdoubles | 0 (keine Probleme gefunden) |
| C. Fehlende Cut-Guards | 9 |
| D. Protocol Boundary | 2 Transport-Systeme dokumentiert |
| E. Protocol Gaps | 10 |
| F. Empfohlene spätere Tests | 10 (LATER_CUT_ACTIONS) |
