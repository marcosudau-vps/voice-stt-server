# AP-SRV-070 — W1A TEST REPORT

**Datum:** 2026-08-29
**Teilblock:** W1A — Protocol / Session / Activation / Lifecycle Hard Cut
**Commit:** `24f3a6e0d321fe02ce3b5aef681380b500db1b81`
**Umgebung:** Windows 11, CPython 3.12.10, pytest 9.1.1, FastAPI 0.135.4
**Aufrufmuster:** `python -m pytest -q -o addopts="" --basetemp=<isolierte Temp>`

---

## 1. Neue Testdatei: `tests/unit/test_protocol_v1_v2_boundary.py`

15 Tests in 5 Klassen, jeder Test negativ formuliert: er beweist, dass eine
Nachricht, ein Identifier oder eine Protokollversion der einen Welt in der
anderen keine Wirkung hat. Jeder Test läuft durch den echten
Produktionseinstieg (`/ws/transcribe` bzw. `/ws/v2` über `TestClient`), nicht
gegen gemockte Interna.

### Invariante 1 — v1 nimmt keine v2-Envelopes (`V1RefusesV2EnvelopesTests`)

| Test | Beweis |
|---|---|
| `test_every_v2_command_type_is_an_unknown_v1_command` | Alle fünf v2-Commandtypen (`activation.command`, `trigger_suppression.set`, `audio_availability.set`, `session_settings.patch`, `session.snapshot.request`) werden auf v1 mit `{"type":"error","where":"command","message":"Unbekannter Befehl: …"}` beantwortet. Die Antwort trägt die v1-Session-ID, nie die im Envelope behauptete |
| `test_a_v2_activation_command_never_becomes_a_v1_activation` | Nach dem Refusal und einem Round-Trip über einen echten v1-Befehl existiert kein `trigger_ack` und kein Timeline-Event `activation.started` |
| `test_a_v2_envelope_does_not_occupy_a_v1_command_id` | Ein abgelehnter Fremd-Envelope belegt keinen v1-Replay-Slot: dieselbe `commandId` wird danach von einem echten v1-`trigger` noch akzeptiert |

### Invariante 2 — v2 nimmt keine v1-Wire-Messages (`V2IgnoresV1WireMessagesTests`)

| Test | Beweis |
|---|---|
| `test_v1_messages_are_neither_acknowledged_nor_effective` | Sieben echte v1-Nachrichten (`trigger`, `audio_availability`, `start`, `stop`, `clear`, `ping`, `metrics`) erzeugen auf v2 kein `trigger_ack`, kein `pong`, kein `metrics`, kein `audio_availability_ack`, kein `error` und keinen `command.ack` auf ihre `commandId`. `input.phase` und `stateVersion` bleiben unverändert |
| `test_the_deprecated_v1_extend_spelling_is_unknown_on_both_wires` | `extend` ist auf v2 `invalid_payload` **und** auf v1 `invalid_action` — nach dem W1A-Cut kennt keine der beiden Welten die Schreibweise |

### Invariante 3 — Session-Identitäten kreuzen nicht (`SessionIdentityIsolationTests`)

| Test | Beweis |
|---|---|
| `test_the_two_transports_mint_different_id_shapes` | v1 vergibt 32-stellige kompakte Hex-IDs (nicht kanonisch), v2 kanonische UUIDs |
| `test_a_compact_v1_session_id_is_invalid_payload_on_v2` | Eine echte, laufende v1-Session-ID wird auf v2 mit `invalid_payload` abgewiesen; der Ack antwortet in der v2-Session, die Phase bleibt `idle` |
| `test_the_hyphenated_form_of_a_v1_id_is_still_a_foreign_session` | Auch die kanonisch umformatierte v1-ID wird nicht adoptiert, sondern ist `stale_session`. Damit ist Boundary-Reformatting als Angriffsweg ausgeschlossen |
| `test_a_canonical_v2_session_id_does_not_steer_a_v1_command` | Ein v1-`trigger` mit fremder v2-`sessionId` wird in der eigenen v1-Session beantwortet; die v2-Session bleibt `idle` |

### Invariante 4 — Protokollversion ist deterministisch (`ProtocolVersionBoundaryTests`)

| Test | Beweis |
|---|---|
| `test_the_v2_endpoint_advertises_exactly_one_version` | `SUPPORTED_PROTOCOL_VERSIONS == (2,)` |
| `test_a_v1_only_client_is_refused_with_protocol_incompatible` | Genau eine Nachricht (`protocol.incompatible`, `reason=no_common_protocol_version`, `supportedProtocolVersions=[2]`), Close-Code `4406`, und **keine** zurückgelassene Session im Session-Store |
| `test_a_v1_protocol_version_on_a_v2_command_is_invalid_payload` | `protocolVersion: 1` auf einem v2-Command ist `invalid_payload` ohne Zustandswirkung |

### Invariante 5 — Metadaten widersprechen sich nicht (`ServerIdentityConsistencyTests`)

| Test | Beweis |
|---|---|
| `test_every_v2_wire_surface_publishes_the_same_identity` | `serverVersion`/`serverCommit` sind auf allen vier v2-Oberflächen (`hello.accepted`, `session.snapshot`, `protocol.incompatible`, `session.rejected`) identisch mit `identity.server_version()`/`identity.server_commit()` |
| `test_the_rest_metadata_agrees_with_the_wire` | `GET /api/v2/settings/schema` und `GET /api/v2/settings/server` liefern dieselbe Identität; die dort gemeldete `protocolVersion` liegt in `SUPPORTED_PROTOCOL_VERSIONS` |
| `test_both_transports_advertise_the_same_activation_vocabulary` | Die v1-Capability meldet exakt die vier kanonischen Aktionen, kein `deprecatedActionAliases`, kein `retiredQueryParameters`, kein `extensionSeconds` in `queryParameters` |

---

## 2. RED-FIRST-Nachweis

Prompt §6 verlangt RED-FIRST, wo ein Defekt existiert, und verbietet
künstliche RED-Tests für bereits korrektes Verhalten. Beide Fälle traten auf
und wurden unterschieden.

### 2.1 Echtes RED → GREEN (Verhaltensänderung durch W1A)

Vorgehen: die beiden geänderten Quelldateien wurden im Arbeitsworktree
vorübergehend auf den Baselinestand `1e74fec…` zurückgesetzt, die Tests
ausgeführt und die Arbeitsstände anschließend per gespeicherter Kopie und
MD5-Prüfung wiederhergestellt.

| Test | Baseline `1e74fec…` | Nach W1A |
|---|---|---|
| `test_server_activation_commands.py::test_the_deprecated_extend_alias_is_gone` | **FAIL** (`CommandRejected not raised`) | PASS |
| `test_protocol_v1_v2_boundary.py::…::test_the_deprecated_v1_extend_spelling_is_unknown_on_both_wires` | **FAIL** | PASS |
| `test_protocol_v1_v2_boundary.py::…::test_both_transports_advertise_the_same_activation_vocabulary` | **FAIL** | PASS |

Ergebnis der Baselineprüfung: `3 failed in 3.05s`.
Ergebnis nach Wiederherstellung: `3 passed in 2.67s`, MD5 beider Dateien `OK`.

### 2.2 Regressionsfestschreibung (Verhalten war bereits korrekt)

Die übrigen zwölf Boundary-Tests beschreiben Verhalten, das der Server schon
vor W1A korrekt zeigte. Es wurde kein Defekt und kein Leak gefunden. Nach §6
wurden dafür deshalb **keine** künstlichen RED-Tests gebaut; das bestehende
Verhalten ist stattdessen als Regression festgeschrieben.

### 2.3 Eine korrigierte Testerwartung

Der erste Entwurf von `test_v1_messages_are_neither_acknowledged_nor_effective`
erwartete, dass ein Snapshot-Round-Trip `stateVersion` um 1 erhöht. Der Server
zählt einen Snapshot-Request korrekterweise **nicht** als Zustandsänderung. Die
Erwartung war falsch, nicht der Server; der Test fordert jetzt die schärfere
Aussage, dass sich `stateVersion` überhaupt nicht bewegt.

---

## 3. Regressionslauf

Die gesamte Unit-Suite (`tests/unit`, 59 Testdateien inklusive der neuen)
wurde in Chargen ausgeführt. Alle Chargen sind grün.

| Charge | Umfang | Ergebnis |
|---|---|---|
| Lifecycle / Command / Timer / Ledger | `test_protocol_v1_v2_boundary`, `test_server_activation_commands`, `test_server_activation_controller`, `test_server_trigger_contract`, `test_server_controlled_e2e`, `test_server_command_timer_e2e`, `test_server_segment_ledger` | **212 passed**, 98 subtests, 122 s |
| Protocol v2 (inkl. Races) | `test_protocol_v2_contract`, `test_protocol_v2_e2e`, `test_protocol_v2_races`, `test_protocol_v2_settings`, `test_protocol_v2_state_version` | **205 passed**, 1 skipped, 281 subtests, 247 s |
| Session / Settings / Client-Contract | `test_fastapi_server_multi_user`, `test_fastapi_server_protocol`, `test_recorder_activation_control`, `test_settings_control_plane`, `test_settings_runtime_persistence`, `test_browser_client_contract`, `test_wakeword_session_e2e` | **210 passed**, 34 subtests, 74 s |
| Wake Words / Operations / Recorder | 16 Dateien inkl. `test_server_operations`, `test_wakeword_root_findings_c2/c3`, `test_wakeword_catalog*` | **334 passed**, 307 subtests, 110 s |
| Audio / Realtime | 9 Dateien | **59 passed**, 1 skipped, 5 subtests, 11 s |
| ASR-Engines | 13 Dateien | **135 passed**, 11 skipped, 24 subtests, 22 s |
| Stabilizer-Eval | `test_realtime_text_stabilizer_eval` | **36 passed**, 29 subtests, 0,4 s |
| Multi-User-ASR-Integration | `test_fastapi_server_multi_user_asr_integration` | **4 passed**, 1 skipped, 0,5 s |
| **Summe** | **59 Dateien** | **1195 passed, 14 skipped, 778 subtests, 0 failed** |

Die Skips sind Umgebungs-Skips (nicht installierte optionale
Engine-/Backend-Abhängigkeiten), keine Ausblendungen von W1A-Verhalten.

### Race-Abdeckung

W1A verändert keinen Nebenläufigkeitsseam. Die vorhandenen Race-Suiten
(`test_protocol_v2_races.py`, `F10AtomicRefreshTests` in
`test_wakeword_root_findings_c2.py`) laufen unverändert grün und arbeiten mit
deterministischer Synchronisation, nicht mit Sleeps.

### Zwei Umgebungsbefunde, beide erklärt und beide kein Produktdefekt

1. **`PermissionError` auf `%LOCALAPPDATA%\Temp\pytest-of-marco`.** Pytests
   Temp-Factory konnte das Standard-Temp-Root nicht scannen (`WinError 5`), was
   in einem Lauf 16 Setup-Errors in `test_settings_*` auslöste. Mit explizitem
   `--basetemp` außerhalb dieses Verzeichnisses laufen dieselben Dateien
   vollständig grün (210 passed). Der Befund liegt in der Testumgebung, nicht
   im Produktcode; kein Testinhalt wurde dafür geändert.
2. **Scheinbar hängender Gesamtlauf.** Ein erster `pytest -q tests/unit | tail`
   schien zu blockieren. Ursache ist die Pufferung: `-q` gibt bei Umleitung
   erst am Ende aus, und die Gesamtlaufzeit der Suite liegt bei rund zehn
   Minuten. Der Lauf wurde deshalb in Chargen wiederholt; jede Datei ist
   einzeln und in Chargen nachweislich grün. Es gab keinen Hänger.

---

## 4. Diff-Hygiene

- `git diff --cached --check` → Exit 0, keine Whitespace-Fehler.
- Nach dem Staging wurden die geänderten Dateien aus dem Index neu ausgecheckt,
  damit die Arbeitskopie der Repo-Konvention (`* text=auto`, `core.autocrlf=true`,
  CRLF im Windows-Checkout) entspricht. Der Indexinhalt blieb dabei unverändert.
- `git status --porcelain` nach dem Commit: leer.
- Die gezielten Tests wurden nach der Zeilenendennormalisierung erneut
  ausgeführt: **37 passed, 42 subtests**.

---

## 5. Nicht ausgeführt (bewusst, gehört nicht in W1A)

- Wheel-/sdist-Build und Isolated-Install-Smoke (W3-03).
- Docker-Build, Compose-Start und Healthcheck (W4).
- Live-Server-E2E-Lifecycle-Smoke gegen einen realen Serverprozess (W5-03).

Prompt §8 schließt Release-, Packaging- und Dockerprüfungen für W1A
ausdrücklich aus. Die vollständige Regression bleibt formal W5-01 zugeordnet;
der oben dokumentierte Lauf über alle 59 Unit-Testdateien geht bereits darüber
hinaus, was W1A verlangt.
