# AP-SRV-040 – PROTOKOLL v2 / HANDSHAKE / EVENTS / SNAPSHOT
# KANONISCHES CLAUDE EXECUTION PACKAGE

## 0. Rolle

Du übernimmst die **kanonische Ausführung von AP-SRV-040** für die einheitliche
Triggerarchitektur des Voice-STT-Servers.

Dieses Paket folgt unmittelbar auf den final akzeptierten Stand von AP-SRV-030.

Du bist:
- Implementierungs-Agent,
- Protokoll-/Schema-Reviewer,
- Integrationsautor,
- Testautor.

Du bist **nicht** Root-Abnahme.

Der Protocol-v2-Vertrag ist eingefroren. Du darfst keinen alternativen Wire-Contract
entwerfen. Deine Aufgabe ist, den Frozen Contract sauber auf den final akzeptierten
serverautoritativen SRV-030-Domainpfad abzubilden.

---

## 1. Zielarchitektur

```text
WebSocket Transport
    ↓
Protocol-v2 Handshake / Envelope Validation
    ↓
Protocol Session State
    ↓
schmaler Domain Adapter
    ↓
bestehende SRV-030-Domainlogik
    ↓
Ack / Event / Snapshot Projection
    ↓
WebSocket Transport
```

Wichtig:

```text
Protocol State ≠ Activation State Machine
```

SRV-040 darf keine zweite Activation-, Timer-, Ledger-, Wake- oder
Settings-State-Machine bauen.

SRV-030 bleibt Domainautorität für:
- Activation,
- Foregroundphasen,
- Triggerlock,
- Timer,
- Close,
- Cancel-Publikationsgrenze,
- Segment-/Ledger-Lifecycle.

SRV-040 besitzt die kanonische Wire-/Session-/Projection-Grenze.

---

## 2. Exakte Repositories

### Server – Arbeitsrepository

```text
P:\GithubRepos\marcosudau-vps\voice-stt-server
```

### Client – zentrale Planung, NUR LESEN

```text
P:\GithubRepos\marcosudau-vps\voice-stt-client\workspaces\einheitliche-triggerarchitektur
```

Planungsbasis:

```text
P:\GithubRepos\marcosudau-vps\voice-stt-client\workspaces\einheitliche-triggerarchitektur\ARBEITSDATEIEN\10_AKTUELL\EINHEITLICHE_TRIGGERARCHITEKTUR
```

Keine Clientdatei ändern.

---

## 3. Harte Start-Sperre – finaler SRV-030-Stand

Produktive AP-SRV-040-Änderungen dürfen erst beginnen, wenn Root diese Werte liefert:

```text
SRV030_FINAL_SHA=<MUSS_GESETZT_SEIN>
SRV030_FINAL_TREE=<MUSS_GESETZT_SEIN>
```

Dieser Stand muss der **final akzeptierte AP-SRV-030-Tree** sein.

Nicht zulässig als Ersatz:
- SRV-030 C1,
- C2,
- uncommitteter C3,
- irgendein einzelner Prep-Branch,
- ein geratenes SHA.

Fehlen SHA oder Tree:

```text
BLOCKED – AP-SRV-040 MUTATION DARF NICHT STARTEN
```

Analyse/Lesen ist trotzdem erlaubt.

---

## 4. Kanonischer AP-SRV-040-Worktree

Nach Freigabe:

```text
P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-040
```

Branch:

```text
review/AP-SRV-040/run-01
```

Der Worktree wird exakt aus `SRV030_FINAL_SHA` erzeugt.

Beispiel:

```powershell
cd "P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\einheitliche-triggerarchitektur-distributed"

git worktree add `
  -b "review/AP-SRV-040/run-01" `
  "P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-040" `
  "<SRV030_FINAL_SHA>"
```

Nur nach Root-Freigabe ausführen.

---

## 5. Vorhandener spekulativer Donor

Es kann bereits einen spekulativen Stand geben:

```text
P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\prep-srv-040
```

Branch:

```text
prep/AP-SRV-040/protocol-v2
```

Dieser Stand ist:
- Donor für Code,
- Donor für Tests,
- Donor für Analyse,

aber **nicht kanonisch**.

Verbindlich:

```text
finaler SRV-030-Stand
→ neuer review/AP-SRV-040/run-01
→ Prep-Diff analysieren
→ brauchbare Änderungen gezielt portieren
→ jede Semantik gegen Frozen Contract prüfen
→ vollständig neu validieren
```

Kein blindes:

```text
git merge prep/AP-SRV-040/protocol-v2
```

---

## 6. Normative Quellen – vollständig lesen

Im Client-Planungsrepo mindestens:

```text
PLANUNG\ENTSCHEIDUNGEN_UND_OFFENE_PUNKTE.md
PLANUNG\ZIELBILD.md
PLANUNG\TECHNISCHER_CONTRACT_FREEZE.md
PLANUNG\PROTOKOLL_V2_WIRE_SCHEMA.md
PLANUNG\VERTRAGSVEKTOREN\protocol-v2-vectors.json
PLANUNG\IMPLEMENTIERUNGSPLAN.md
PLANUNG\AUSFUEHRUNGS_WORKFLOW.md
NACHVERFOLGUNG\TRACEABILITY.md
NACHVERFOLGUNG\FUNDE.md
```

Serverseitig mindestens:

```text
AGENTS.md
docs\.archiv\README.md
docs\einheitliche-triggerarchitektur.md
docs\module-map.md
```

Zusätzlich:
- finaler SRV-030-Code,
- finale SRV-030-Tests,
- vorhandene WebSocket-/Protocoltests,
- Session-/ConnectionManager-Code.

Priorität:

```text
1. bestätigte Entscheidungen / Frozen Contract
2. Frozen Wire-Schema
3. Vertragsvektoren
4. Implementierungsplan
5. final akzeptierter SRV-030-Code
6. Tests
7. alte Analysen / Alt-Doku
```

Tests können Alt-Soll enthalten.

---

## 7. Precheck

Im AP-SRV-040-Worktree:

```powershell
git branch --show-current
git rev-parse HEAD
git rev-parse "HEAD^{tree}"
git status --short
```

Erwartet exakt:

```text
branch = review/AP-SRV-040/run-01
HEAD   = SRV030_FINAL_SHA
tree   = SRV030_FINAL_TREE
tracked working tree = clean
```

Bei Abweichung: `BLOCKED`.

---

## 8. Frozen Wire-Grundsätze

Protocol v2:

```text
UTF-8 JSON
camelCase
protocolVersion = 2
```

Nach akzeptiertem Handshake gehört `sessionId` zu jeder sessiongebundenen Nachricht.

Unbekannte additive Felder derselben Protokollversion:
- ignorieren,
- sofern keine bekannte Semantik überschrieben wird.

Keine implizite Typkonversion bei IDs oder Protokollfeldern.

UUIDs nach Frozen Schema kanonisch verwenden.

---

## 9. Handshake

Die **erste Textnachricht** einer neuen v2-Verbindung muss `hello` sein.

Vor:

```text
hello.accepted
```

ist verboten:
- Audioannahme,
- Manual Trigger,
- Wake-Word-Admission,
- Domaincommands,
- Domaintraffic.

Hello enthält mindestens:

```text
supportedProtocolVersions
clientVersion
clientCommit
clientRunId
requestedSession.trigger.manual
requestedSession.trigger.wakeWord
requestedSession.wakeWordIds
runtimeSuppression.manual
runtimeSuppression.wakeWord
```

Exakte Feldstruktur nach `PROTOKOLL_V2_WIRE_SCHEMA.md`.

---

## 10. Protokollnegotiation / Close Codes

Keine gemeinsame Version:

```text
protocol.incompatible
keine sessionId
keine teilweise Session
Close 4406
```

Ungültiger Handshake:

```text
Close 4400
```

Handshake-Timeout nach Frozen Schema:

```text
Close 4408
```

Sessionadmission abgelehnt:

```text
session.rejected
keine sessionId
Close 4409
```

Unerwarteter interner Fehler:

```text
Close 1011
```

Keine Domain-Session darf bereits halb erzeugt sein, wenn Handshake/Admission scheitert.

---

## 11. hello.accepted

Erst nach kompletter Validierung und erfolgreicher Sessionadmission:

```text
hello.accepted
```

Danach:
- stabile `sessionId`,
- stabile ausgewählte `protocolVersion`,
- Domaintraffic erlaubt.

Serverversion/Servercommit/Capabilities nach Frozen Schema liefern.

Keine erfundenen Wirefelder.

---

## 12. ProtocolSessionState

Führe eine klar verantwortete v2-Session-State-Komponente ein.

Mindestens:

```text
protocolVersion
sessionId
stateVersion
settingsRevision
lastEventSeq / nextEventSeq
```

Verantwortlich für:
- Wire-State-Versionierung,
- Eventsequenzierung,
- Snapshot-Konsistenz,
- Resync-Metadaten.

Nicht verantwortlich für:
- Activationphasen,
- Domain-Timer,
- Ledgerterminalisierung,
- Wake-Word-Modelllogik,
- Settingspersistenz.

---

## 13. stateVersion

`stateVersion`:
- monoton pro Session,
- steigt nur bei sichtbarer bestätigter Zustandsänderung.

Nicht jedes:
- Ack,
- Retry,
- Log,
- Transportereignis

erhöht `stateVersion`.

`no_change` darf nicht fälschlich eine neue sichtbare Domainversion erzeugen.

Nicht blind `ActivationController.version` als gesamten Wire-State übernehmen.

---

## 14. Eventidentität

Jedes Domainereignis besitzt mindestens:

```text
eventId
eventSeq
stateVersion
occurredAtUnixMs
```

Regeln:
- `eventSeq` streng monoton je Session,
- `eventId` einmal je logischem Ereignis,
- Transportretry erzeugt kein neues logisches Event,
- gleiche logische Zustellung darf keine neue Eventidentität erfinden.

---

## 15. Command Envelope

Commands besitzen nach Frozen Schema mindestens:

```text
protocolVersion
sessionId
commandId
type
...
```

Jeder syntaktisch erkennbare Command mit brauchbarer `commandId` erhält genau ein
logisches `command.ack`.

SRV-030-Replay-/Conflict-Semantik wiederverwenden, nicht duplizieren.

---

## 16. activation.command

### Activate

```json
{
  "type": "activation.command",
  "action": "activate",
  "source": "manual"
}
```

Regeln:
- Client darf nur `source=manual`.
- `wake_word` kommt serverintern.
- `activate` verbietet `activationId`.

### Controls

```json
{
  "type": "activation.command",
  "action": "refresh|finish|cancel",
  "activationId": "..."
}
```

Regeln:
- `activationId` zwingend,
- `source` verboten,
- Controls source-neutral.

Keine Legacy-Ausnahme im canonical v2 parser.

---

## 17. Weitere Commands

Mindestens:

```text
trigger_suppression.set
audio_availability.set
session_settings.patch
session.snapshot.request
```

SRV-040 implementiert:
- Envelope,
- Parsing,
- Session-/Identity-/Revisionvalidation,
- Ack-Projection,
- Routing.

SRV-040 implementiert **nicht** die vollständige SRV-050-Settings-Control-Plane.

Für `session_settings.patch`:
- schmaler Adapter/Port,
- keine zweite Settingsregistry.

---

## 18. command.ack – Resultcodes

Verbindlich:

```text
applied
no_change
activation_locked
not_active
invalid_phase
closing_input
stale_session
stale_activation
command_id_conflict
invalid_payload
trigger_suppressed
audio_unavailable
settings_revision_conflict
settings_rejected
internal_error
```

`accepted=true` nur:

```text
applied
no_change
```

Alle anderen `accepted=false`.

Keine freien neuen Resultcodes.

---

## 19. Replay

```text
same commandId + same semantic payload
→ exakt dieselbe logische Ack-Antwort
→ keine zweite Wirkung
```

Originale IDs/Versionen/Resultatdaten bleiben dieselben.

```text
same commandId + different semantic payload
→ command_id_conflict
→ keine Wirkung
```

Additive unbekannte Transportfelder dürfen semantischen Replay-Key nicht unnötig ändern.

---

## 20. stale_session

Nach Handshake muss sessiongebundener Traffic exakt die aktuelle `sessionId` tragen.

Falsche/alte Session-ID:

```text
stale_session
```

Keine Wirkung.
Keine Neuinterpretation als neue Session.

---

## 21. Trigger Suppression

Abbilden:

```text
configured
suppressed
effective
```

Effective:

```text
configured && !suppressed
```

Runtime darf beide Sources gleichzeitig suppressen.

Suppression:
- beeinflusst neue Admission live,
- ändert keine laufende Activationquelle,
- beendet keine laufende Activation,
- merged keine Quellen.

---

## 22. Audio Availability

`audio_availability.set` transportiert nur:

```text
audioAvailable = true|false
```

Keine Geräteidentität serverseitig erfinden.

Bei `false`:
- bestehende SRV-030-Policy verwenden,
- offene Activation canceln,
- Session bleibt grundsätzlich bestehen,
- neue Activate-Versuche → `audio_unavailable`.

Availability-`commandId` darf nicht `causedByCommandId` des Close-Events werden.

---

## 23. Kanonische v2 Events

Mindestens:

```text
activation.started
activation.phase_changed
activation.input_closed
activation.completed
activation.cancelled
activation.failed
activation.trigger_suppressed

segment.recording_started
segment.recording_ended

transcription.accepted
transcription.completed
transcription.discarded
transcription.failed

watchdog.warning

wakeword.detected
wakeword.availability_changed

settings.changed
```

Falls Provider erst SRV-050/SRV-060 vollständig werden:
- Modell/Adapterport sauber vorbereiten,
- keine Ersatzdomainlogik erfinden.

---

## 24. activation.input_closed – kritisch

`activation.input_closed` genau einmal je effektivem Input-Close.

Bedeutung:

```text
Inputseite ist sicher geschlossen
```

Nicht:

```text
Backgroundinference ist fertig
```

Foreground darf bereits idle sein, während alte Activation im Ledger drainet.

---

## 25. causedByCommandId

Normaler `finish`/`cancel`-Close:

```text
causedByCommandId = akzeptierte Command UUID
```

Nicht command-korrelierte Abschlüsse:

```text
timer
VAD
watchdog
audio/device/session
recovery
```

→

```text
causedByCommandId = null
```

Wenn Finish/Cancel logisch initiiert, physisch aber erst Recovery abschließt:
- interne ursprüngliche ID darf erhalten bleiben,
- Wire-Abschluss Recovery → `null`.

---

## 26. Foregroundphasen

Exakt:

```text
idle
waiting_first_speech
segment_active
followup_wait
closing_input
```

`finalizing` ist keine Foregroundphase.

---

## 27. Snapshot – Zweck

`session.snapshot` ist die serverautoritative Resync-Sicht.

Sie bildet gleichzeitig ab:

```text
Foreground Input State
+
Background Pending Activations
```

Keine Rekonstruktion alter Finals über globalen Current-Activation-Zeiger.

---

## 28. Snapshot – Pflichtstruktur

Nach Frozen Schema mindestens:

```text
protocolVersion
serverVersion
serverCommit
sessionId
stateVersion
lastEventSeq
settingsRevision
input
pendingActivations
trigger
audioAvailable
effectiveSettings
wakeWordCapabilities
```

---

## 29. snapshot.input

Mindestens:

```text
phase
activationId
primarySource
deadlineAtUnixMs
remainingMs
closeRequested
```

Idle:

```text
phase = idle
activationId = null
primarySource = null
deadlineAtUnixMs = null
remainingMs = null
closeRequested = false
```

---

## 30. pendingActivations

Aus Ledger-/Backgroundzustand, nicht globalem Current-Activation-Zeiger.

Regeln:
- streng nach `activationSequence`,
- mehrere Pendingactivations möglich.

Beweisen:

```text
idle + 0 pending
idle + 1 pending
idle + mehrere pending
offene Activation + ältere pending
```

---

## 31. Timerprojektion

Domainwahrheit bleibt monotonic.

Wire darf projizieren:

```text
deadlineAtUnixMs
remainingMs
```

Keine neue wall-clock Timerautorität.

---

## 32. Event Gap / Resync

Bei Eventlücke:
- Client kann `session.snapshot.request` verwenden,
- Snapshot stellt autoritativen Stand her.

Keine unnötige zweite Event-History-Engine bauen, sofern Frozen Contract nur Snapshotresync fordert.

---

## 33. Wake-Bindung

SRV-040 besitzt nicht die Wake-Engine.

Für späteres `wakeword.detected` Adaptermodell mindestens:

```text
activationId
wakeWordId
score
primarySource = wake_word
```

Wenn SRV-060 noch nicht kanonisch integriert:
- Eventmodell/Port vorbereiten,
- keine anonyme Boolean-Wake-Semantik festschreiben.

Markieren:

```text
REQUIRES_AP_SRV_060_BINDING
```

---

## 34. Settings-Bindung

SRV-040 besitzt nicht die Settings-Control-Plane.

Für:
- `settingsRevision`,
- `effectiveSettings`,
- `settings.changed`,
- `session_settings.patch`

schmalen Provider/Port verwenden.

Keine zweite Registry/Persistenz.

Markieren:

```text
REQUIRES_AP_SRV_050_BINDING
```

---

## 35. v1 / Legacy

Legacyabbau kommt erst SRV-070.

In SRV-040:
- v2 vollständig hinzufügen,
- v1-/Browserpfade nicht ungefragt entfernen,
- aber klare Isolation,
- kein v1-Fallback innerhalb einer angenommenen v2-Verbindung.

Koexistenz darf nur Transport-/Compatibility-Ebene sein, nicht Domain-Doppelautorität.

---

## 36. Browserclient

Nicht Scope:
- keine Browsermigration,
- kein großer JS-Umbau,
- kein Browserclient-Löschen.

---

## 37. Modularität

Neue v2-Logik bevorzugt in kleinen testbaren Modulen, z.B.:

```text
api_fastapi_server/protocol_v2/
    models.py
    parser.py
    handshake.py
    session_state.py
    events.py
    snapshot.py
    adapter.py
```

Exakte Aufteilung Repo-konform.

Nicht noch einen großen Block in `server.py` stapeln.

---

## 38. Contract Vectors

Direkt verwenden:

```text
PLANUNG\VERTRAGSVEKTOREN\protocol-v2-vectors.json
```

Mindestens bekannte Fälle automatisieren:

```text
hello_v2
manual_activate
manual_activate_replay
refresh_active_activation
activation_started_event
idle_snapshot
wake_enabled_without_selection
client_claims_wake_word
activate_with_activation_id
refresh_without_activation_id
command_id_conflict
```

Assertions gegen echte Parser-/Projectionsemantik.

---

## 39. Pflicht-Negativtests Handshake

Mindestens:

```text
first message != hello
invalid JSON
hello missing fields
empty supportedProtocolVersions
no common version
invalid requested session
audio before hello.accepted
command before hello.accepted
wake admission before hello.accepted
no partial session after rejection
```

---

## 40. Pflicht-Negativtests Commands

Mindestens:

```text
activate claims wake_word
activate with activationId
control without activationId
control with source
stale sessionId
stale activationId
same commandId changed payload
invalid payload
audio unavailable activate
suppressed trigger
```

---

## 41. Event-/Versionstests

Beweisen:

```text
eventSeq strictly monotonic
eventId unique per logical event
transport retry mints no new logical event
stateVersion monotonic
no_change does not falsely mutate state
snapshot lastEventSeq consistent
snapshot stateVersion consistent
```

---

## 42. Snapshottests

Mindestens:

```text
idle
waiting_first_speech
segment_active
followup_wait
closing_input
idle + 1 pending
idle + multiple pending
open + older pending
audio unavailable
manual suppressed
wake suppressed
both suppressed
```

Fehlende spätere Provider mit Fakes testen, echte Bindung separat markieren.

---

## 43. Exactly-once input close

Auf echtem Domainpfad beweisen:

```text
finish   → genau ein activation.input_closed
cancel   → genau ein activation.input_closed
timer    → genau ein activation.input_closed
recovery → genau ein activation.input_closed
```

Mit korrekter `causedByCommandId`-Policy.

Kein Doppel-Event aus Controller + Ledger + Legacy Timeline.

---

## 44. Replay darf keine zweiten Events erzeugen

```text
same command replay
→ same Ack
→ no second domain effect
→ no second event
→ no second stateVersion bump
```

Expliziter Test.

---

## 45. Session Close / stale output

Prüfe:
- spätes Event alter Session,
- später Timer,
- spätes Wakeevent,
- alte Domainpublication.

Nach Sessionclose keine neue v2-Domainmutation.

---

## 46. Concurrencytests

Ordering mit:
- `threading.Event`,
- Barrier,
- Hookpoints.

Keine Sleeps als Ordnungsmechanismus.

Timeouts nur Failsafe.

---

## 47. Baseline vor Mutation

Vor Implementierung:

1. vorhandene Protocol-/WebSockettests,
2. finale SRV-030-Fokussuite,
3. SRV-020-Regression,
4. `tests/unit`.

Counts im Bericht.

---

## 48. Prep-Donor-Review

Wenn `prep/AP-SRV-040/protocol-v2` existiert, vor Portierung Matrix erstellen:

```text
Prep-Datei/Feature
Contract-konform?
abhängig von altem SRV-030?
direkt übernehmbar?
anpassen?
verwerfen?
```

Frozen Contract gewinnt immer.

---

## 49. Dokumentation / Akte

Serverdocs aktualisieren:

```text
docs/einheitliche-triggerarchitektur.md
docs/module-map.md
relevante WebSocket-/Protocol-Doku
relevante Client-Development-Kurzreferenz
```

AP-Akte gemäß `docs/.archiv/README.md`.

Keine finale `ABNAHME.md` vor Root PASS.

---

## 50. Git-Regeln

- finaler SRV-030-Commit immutable,
- kein Rebase,
- kein Merge in canonical branch,
- kein Push,
- kein Amend fremder Commits,
- kein neues venv,
- keine Clientänderungen.

Am Ende genau **ein lokaler AP-SRV-040-Candidate-Commit** auf:

```text
review/AP-SRV-040/run-01
```

Empfohlene Message:

```text
feat(protocol): implement AP-SRV-040 protocol v2
```

---

## 51. Vollvalidierung

Fokus:
- Parser/models,
- Handshake,
- Commands/Acks,
- Events,
- Snapshot,
- Contract vectors,
- WebSocket integration.

SRV-030 Regression vollständig relevant erneut.

Vollsuite:

```powershell
python -m pytest -q --basetemp=.pytest-tmp\pt tests/unit
```

Zusätzlich:

```powershell
git diff --check
```

---

## 52. Race-Wiederholung

Neue Concurrency-/Orderingtests mindestens 20x, insbesondere:
- Replay/Event exactly-once,
- Eventseq unter konkurrierenden Domainereignissen,
- Snapshot bei Backgrounddrain,
- Sessionclose vs stale events.

Keine Sleeps.

---

## 53. Root-Review-Handoff

Am Ende liefern:

```text
Candidate SHA
Candidate Tree
Parent SHA
Parent Tree
Commits seit final SRV-030
Working Tree Status
```

Root prüft den tatsächlichen Diff unabhängig.

---

## 54. Abschlussbericht – verbindlich

```text
STATUS: READY FOR ROOT REVIEW / BLOCKED

PRECHECK
Branch:
SRV030_FINAL_SHA:
SRV030_FINAL_TREE:
Working Tree:
Baseline tests:

PREP DONOR REVIEW
prep branch:
prep sha:
übernommen:
angepasst:
verworfen:

ARCHITEKTUR
Protocol modules:
Handshake ownership:
ProtocolSessionState:
Domain adapter:
Event projection:
Snapshot projection:
Settings adapter:
Wake adapter:

HANDSHAKE
hello:
negotiation:
rejection paths:
close codes:
no-domain-before-accepted:

COMMANDS
activation.command:
trigger_suppression.set:
audio_availability.set:
session_settings.patch:
session.snapshot.request:
ack/replay:

EVENTS
eventId:
eventSeq:
stateVersion:
exactly-once:
activation.input_closed correlation:

SNAPSHOT
input:
pendingActivations:
trigger:
audioAvailable:
effectiveSettings:
wakeWordCapabilities:
resync:

CONTRACT VECTORS
passed:
failed:

NEGATIVE TESTS
...

SRV-030 REGRESSION
...

FULL SUITE
...

RACE REPETITION
...

git diff --check:

CHANGED FILES
...

ARCHIVE / DOCS
...

KNOWN FOLLOW-UP BINDINGS
REQUIRES_AP_SRV_050_BINDING:
REQUIRES_AP_SRV_060_BINDING:

CANDIDATE
SHA:
Tree:
Parent:
Commits since SRV030:

WORKING TREE:
clean

PUSH: no
MERGE: no
REBASE: no
AMEND: no
```

---

## 55. Blocked-Kriterien

`BLOCKED`, wenn:
- finaler SRV-030 SHA/Tree fehlt,
- Branch/Worktree falsch,
- Frozen Contract intern widersprüchlich ist,
- notwendige SRV-030-Domainfunktion fehlt,
- Lösung nur durch neuen erfundenen Contract möglich wäre.

Nicht blocked nur weil Prep-Code schlecht ist oder viel Arbeit nötig ist.

---

## 56. Definition of Done

```text
1. v2 Handshake blockiert jede Domainnutzung vor accepted.
2. Commands werden frozen validiert und auf SRV-030 geroutet.
3. Ack/Replay deterministisch.
4. Events mit stabiler eventId/eventSeq/stateVersion.
5. activation.input_closed genau-einmal und korrekt korreliert.
6. Snapshot rekonstruiert Foreground + Pendingactivations.
7. Eventgap kann per Snapshot resynchronisiert werden.
8. v1/Browsercompat bleibt bis SRV-070 isoliert.
9. Keine zweite Domain-State-Machine.
10. Contractvectors + Negativtests + SRV-030 Regression + Vollsuite grün.
11. Genau ein lokaler Candidate-Commit.
12. Kein Push.
```

Danach stoppen und Root-Review abwarten.
