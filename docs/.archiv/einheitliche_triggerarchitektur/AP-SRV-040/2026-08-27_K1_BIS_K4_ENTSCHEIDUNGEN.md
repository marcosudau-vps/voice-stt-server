# AP-SRV-040 – Root-Entscheidungen K1 bis K4 und ihre Umsetzung

Die vier Konfliktpunkte stammen aus dem Precheck vor der Freigabe. Root hat
alle vier entschieden; hier steht, wie sie umgesetzt und nachgewiesen sind.

## K1 – kanonische UUIDs ohne Grenzkonversion

**Entscheidung:** APPROVED mit Präzisierung. Jede v2-relevante UUID wird
bereits an ihrer autoritativen Erzeugungsstelle kanonisch erzeugt und läuft
unverändert durch Domain, Ledger, Events und Snapshot. Eine Identität ist ein
String. Legacy behält bis AP-SRV-070 die kompakte Darstellung.

**Umsetzung:**

| ID | Erzeugungsstelle | v2 | v1 |
|---|---|---|---|
| `sessionId` | `ProtocolV2Connection._admit` | `schema.new_canonical_id()` | `uuid.uuid4().hex` |
| `activationId` | `ActivationController.id_factory` | injizierte kanonische Factory | kompakt |
| `segmentId` | `SegmentState.id_factory` (neue Seam) | injizierte kanonische Factory | Integer-Zähler |
| `eventId` | `ProtocolSessionState` | `schema.new_canonical_id()` | – |
| `commandId` | Client | kanonisch validiert, nie umgeschrieben | – |

`SegmentState` bekam die von Root ausdrücklich erlaubte schmale
ID-Factory-Seam. Das Ledger coerciert `segment_id` nicht mehr blind auf `int`
(`normalize_segment_id`), behält für Integer und numerische Strings aber exakt
das bisherige Verhalten.

`schema.is_canonical_uuid` weist kompakte **und** großgeschriebene Formen ab:
zwei Schreibweisen einer UUID wären zwei Replay-Schlüssel für einen Command.

**Nachweis:** `ProtocolV2IdentityTests`, `CanonicalIdentityTests`.

## K2 – eigener v2-Endpunkt

**Entscheidung:** APPROVED. `/ws/v2` ist ein eigener Endpunkt; der v1-Pfad
bleibt bis AP-SRV-070 unverändert. Keine `protocolVersion`-Verzweigung
innerhalb einer bereits admittierten v1-Session.

**Umsetzung:** `websocket_protocol_v2` in `api_fastapi_server/server.py`.
Der Socket wird technisch angenommen, aber es existiert keine fachliche
Session, bis `hello` vollständig validiert und die Admission atomar
erfolgreich ist. Ein v2-Socket wird bewusst **nicht** im gemeinsamen
`ConnectionManager` registriert, damit kein Legacy-Payload eine v2-Verbindung
erreichen kann.

**Nachweis:** `ProtocolV2HandshakeTests`, `ProtocolV2IsolationTests`,
`ProtocolV2EventTests.test_no_legacy_event_name_reaches_a_v2_connection`.

## K3 – strikte v2-Vorvalidierung ohne Replay-Verlust

**Entscheidung:** APPROVED. Der v2-Envelope wird vor dem semantischen Dispatch
validiert; ein abgelehnter Command behält trotzdem seine Replay-/Conflict-
Identität, und die Legacy-Normalisierung darf ein im v2 verbotenes Feld nicht
unsichtbar machen.

**Umsetzung:** `protocol_v2/commands.py`. Der v2-Replay-Key ist ein
typstabiler Freeze des gesamten v2-Payloads ohne `commandId` – inklusive
`source` bei Controls. Gespeichert wird er in **derselben**
`CommandReplayCache` der Session (`protocol_replay_lookup`/`_store`), sodass
es genau eine Replay-Autorität gibt:

- v2-abgelehnter Command → v2-Schicht speichert die Ablehnung;
- v2-gültiger Command → AP-SRV-030 speichert seinen semantischen Key.

Weil ein Replay die *ursprünglichen* Versionswerte zurückgeben muss,
memoisiert die Verbindung zusätzlich das erste v2-Ack je `commandId`.

**Nachweis:** `StrictEnvelopeTests`, `test_rejected_command_keeps_its_replay_identity`,
`test_forbidden_control_source_changes_the_replay_key`,
`test_replay_with_unknown_additive_field_is_still_a_replay`.

## K4 – exhaustives Result-Mapping

**Entscheidung:** APPROVED. Genau eine explizite Projektionsschicht auf die
fünfzehn frozen Result-Codes; `accepted=true` nur bei `applied`/`no_change`;
kein stillschweigender `internal_error`-Fallback.

**Umsetzung:** `commands.DOMAIN_REASON_RESULTS` ist die vollständige Tabelle,
`commands.NON_COMMAND_REASONS` listet die Reasons, die per Definition kein
Ack-Ergebnis sind. `map_domain_reason` wirft `UnmappedDomainReason` statt
stillschweigend zu degradieren; die Verbindung loggt einen solchen Fall als
`ERROR`, bevor sie `internal_error` sendet.

`controlled_activation_disabled`, `session_closed` und `stream_not_started`
sind explizit auf `internal_error` abgebildet und in einer v2-Session
strukturell unerreichbar: die Admission verlangt den kontrollierten Modus und
startet den Audiopfad atomar mit `hello.accepted`.

**Nachweis:** `ResultMappingTests`, insbesondere
`test_every_domain_reason_is_mapped_or_declared_non_command`, das die Reasons
direkt aus `api_fastapi_server/activation.py` liest.
