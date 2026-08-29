# AP-SRV-040 – ROOT UNBLOCK / Folgeauftrag nach AP-SRV-030 PASS

## Begleitnachricht

AP-SRV-030 ist inzwischen durch Root vollständig abgenommen und kanonisch gepusht. Dein früherer `STATUS: BLOCKED` war zum damaligen Zeitpunkt korrekt; der Blocker ist jetzt aufgehoben. Bitte setze dieselbe AP-SRV-040-Session anhand dieses Folgeauftrags fort. Der ursprüngliche Canonical Prompt bleibt vollständig verbindlich; dieser Folgeauftrag ergänzt die echten finalen Basiswerte, entscheidet K1–K4 und regelt den Worktree-Start.

---

# Verbindlicher Folgeauftrag

## 0. Statusänderung

Dein bisheriger Precheck für AP-SRV-040 war korrekt:

- kein Produktcode wurde auf einer C1/C2/C3-Zwischenbasis verändert,
- der leere `prep/AP-SRV-040/protocol-v2`-Branch wurde nicht als Donor missverstanden,
- der fehlende finale AP-SRV-030-SHA/Tree war ein echter Blocker.

Dieser Blocker ist jetzt durch Root geschlossen.

**AP-SRV-030 = PASS.**

Verbindliche finale Basis:

```text
SRV030_FINAL_SHA=325e55c186713069b25208871da4fef16470f85a
SRV030_FINAL_TREE=ec5b6e0849bb7a0949ae5da05d168b8c19a4456e
SRV030_PARENT_SHA=8535ee79bb2d898d9897e91b57d6a735c479edf0
```

Kanonischer Serverbranch:

```text
feat/einheitliche-triggerarchitektur-distributed
```

Root-Abnahme im finalen Servercommit:

```text
docs/.archiv/einheitliche_triggerarchitektur/AP-SRV-030/ABNAHME.md
```

Der zentrale Ausführungsstatus im Client wurde durch Root auf

```text
AP-SRV-030 = PASS
AP-SRV-040 = READY
```

aktualisiert.

Pfad:

```text
ARBEITSDATEIEN/10_AKTUELL/EINHEITLICHE_TRIGGERARCHITEKTUR/NACHVERFOLGUNG/AUSFUEHRUNGSSTATUS.md
```

Falls `CURRENT_STATE.md` noch eine ältere "Next: AP-SRV-030 starten"-Zeile enthält, ist diese Zeile zeitlich überholt und **kein Blocker**. Für das Ausführungsgate gilt der oben genannte aktualisierte `AUSFUEHRUNGSSTATUS.md`-Eintrag zusammen mit diesem Root-Folgeauftrag.

---

## 1. Beweis der AP-SRV-030-Basis vor jeder Mutation

Vor AP-SRV-040-Produktänderungen:

```powershell
git fetch origin

git rev-parse "origin/feat/einheitliche-triggerarchitektur-distributed"
git rev-parse "origin/feat/einheitliche-triggerarchitektur-distributed^{tree}"
```

MUSS exakt ergeben:

```text
325e55c186713069b25208871da4fef16470f85a
ec5b6e0849bb7a0949ae5da05d168b8c19a4456e
```

Wenn nicht:

```text
STATUS: BLOCKED
```

und keine Mutation.

Nicht auf C1, C2, C3-Reviewbranch oder dem alten Prep-Branch aufsetzen.

---

## 2. Bestehenden Nicht-Worktree-Ordner sauber behandeln

Der Pfad

```text
P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-040
```

enthält derzeit nur das ursprüngliche Auftragspaket und ist **noch kein Git-Worktree**.

Diese Dateien dürfen nicht verloren gehen und dürfen auch nicht versehentlich in den Produktcommit geraten.

Vor Worktree-Erstellung:

1. Erstelle den stabilen Ablageordner:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-040\AUFTRAGSPAKET_ORIGINAL
```

2. Verschiebe ausschließlich die dort vorhandenen Prompt-/Auftragsdateien aus

```text
P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-040
```

nach

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-040\AUFTRAGSPAKET_ORIGINAL
```

3. Verifiziere, dass der alte `ap-srv-040`-Ordner danach leer ist, und entferne nur diesen leeren Ordner.

Keine Repositorydateien verschieben. Kein `git clean`. Kein `reset --hard` in irgendeinem bestehenden Arbeits-Worktree.

---

## 3. Kanonischen AP-SRV-040-Worktree erstellen

Verwende als Git-Anker den bestehenden Server-Worktree:

```text
P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\einheitliche-triggerarchitektur
```

Ziel:

```text
P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-040
```

Branch:

```text
review/AP-SRV-040/run-01
```

Vorher prüfen, dass der Branch nicht bereits unerwartet existiert:

```powershell
git -C "P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\einheitliche-triggerarchitektur" branch --list "review/AP-SRV-040/run-01"
git -C "P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\einheitliche-triggerarchitektur" branch -r --list "origin/review/AP-SRV-040/run-01"
```

Wenn ein solcher Branch unerwartet bereits existiert: nicht löschen/überschreiben, sondern `STATUS: BLOCKED` mit SHA/Tree melden.

Wenn frei:

```powershell
git -C "P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\einheitliche-triggerarchitektur" worktree add `
  -b "review/AP-SRV-040/run-01" `
  "P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-040" `
  "325e55c186713069b25208871da4fef16470f85a"
```

Danach im neuen Worktree zwingend:

```powershell
git branch --show-current
git rev-parse HEAD
git rev-parse "HEAD^{tree}"
git status --short
```

Erwartet:

```text
branch = review/AP-SRV-040/run-01
HEAD   = 325e55c186713069b25208871da4fef16470f85a
tree   = ec5b6e0849bb7a0949ae5da05d168b8c19a4456e
status = clean
```

Erst danach Baseline-Tests und Produktmutation.

---

# 4. ROOT-ENTSCHEIDUNGEN K1–K4

Deine vier offenen Punkte wurden von Root geprüft.

## K1 – kanonische UUIDs

**ROOT: APPROVED MIT VERBINDLICHER PRÄZISIERUNG**

Der Frozen Wire Contract verlangt UUIDs in kanonischer Darstellung mit Bindestrichen.

Also beispielsweise:

```text
30000000-0000-4000-8000-000000000001
```

und nicht:

```text
30000000000040008000000000000001
```

Wichtig: **Keine ID-Konversion an der Wire-Grenze.**

Verboten:

```text
domain activationId A
→ Wire erzeugt daraus Alias/zweite ID B
```

oder:

```text
compact domain id
→ beim Serialisieren kosmetisch mit Bindestrichen umformatieren
```

Stattdessen muss jede v2-relevante UUID bereits an ihrer autoritativen Erzeugungsstelle kanonisch erzeugt werden und danach unverändert durch Domain, Ledger, Events und Snapshot laufen.

### Konkrete Regel

Für v2:

```python
str(uuid.uuid4())
```

bzw. injizierbare äquivalente Factory.

Der bestehende `ActivationController` besitzt bereits `id_factory`. Nutze diese vorhandene Seam. Für eine v2-Session muss der Controller eine kanonische UUID-Factory erhalten.

Analog alle weiteren ID-Owner auditieren:

- `sessionId`
- `activationId`
- `segmentId`
- `eventId`

`commandId` wird vom Client geliefert und im v2-Envelope als kanonische UUID validiert.

Falls der Segment-ID-Owner noch keine Factory besitzt, darf AP-SRV-040 eine schmale ID-Factory-Seam an der **tatsächlichen autoritativen Erzeugungsstelle** ergänzen.

Legacy/v1 darf bis AP-SRV-070 seine bisherige kompakte Darstellung behalten, sofern für v1 nötig.

Aber:

**ein v2-Objekt darf nie gleichzeitig eine interne kompakte und eine externe kanonische ID für dieselbe Identität besitzen.**

Eine Identität = ein String = Ende-zu-Ende stabil.

Tests müssen beweisen:

- kanonisches UUID-Format,
- dieselbe `activationId` in Controller, Ledger, Ack/Event/Snapshot,
- dieselbe `segmentId` in Ledger, Events und Resultaten,
- keine Boundary-Reformatierung.

---

## K2 – v1/v2 Handshake und Endpoint

**ROOT: APPROVED**

AP-SRV-040 erhält einen **eigenen v2-WebSocket-Endpunkt**:

```text
/ws/v2
```

Der bestehende v1/Legacy-WebSocket-Pfad bleibt bis AP-SRV-070 isoliert bestehen.

Keine `if protocolVersion == 2`-Verzweigung mitten in einer bereits admittierten v1-Session.

### v2-Handshakeregel

Auf `/ws/v2` gilt:

1. WebSocket-Verbindung darf technisch angenommen werden.
2. Es existiert noch **keine fachlich admittierte Session mit `sessionId`**.
3. Erste Client→Server-Textnachricht MUSS `hello` sein.
4. `hello` wird vollständig syntaktisch und fachlich validiert.
5. Erst nach erfolgreicher Versionsaushandlung und atomarer Sessionadmission:
   - kanonische `sessionId` erzeugen,
   - Domain-/ProtocolSessionState anlegen,
   - `hello.accepted` mit Snapshot senden.
6. Vor `hello.accepted`:
   - kein Audio,
   - keine manuelle Activation,
   - keine Wake-Word-Erkennung,
   - keine Domaincommands.

Close Codes exakt nach Frozen Wire Contract:

```text
4400 invalid first message / non-parseable handshake
4406 no common protocol version
4408 handshake timeout
4409 session admission rejected
1011 unexpected internal server error
```

`protocol.incompatible` und `session.rejected` erzeugen keine Session-ID.

Der alte v1-Pfad darf seine bisherige Server→Client-Hello-/Query-Admission-Semantik bis AP-SRV-070 behalten.

---

## K3 – strikte v2-Command-Vorvalidierung

**ROOT: APPROVED**

Der v2-Wire-Layer validiert den v2-Envelope **vor semantischem Dispatch** an SRV-030.

Zulässig:

```text
activate:
  action=activate
  source=manual
  activationId VERBOTEN
```

```text
controls:
  action=refresh|finish|cancel
  activationId PFLICHT
  source VERBOTEN
```

Explizit ungültig:

```text
source=wake_word vom Client
extend
activate + activationId
refresh/finish/cancel ohne activationId
refresh/finish/cancel + source
```

`source=wake_word` bleibt ausschließlich serverinterne Admission.

Die Frozen Vertragsvektoren sind bindend, insbesondere:

```text
client_claims_wake_word -> invalid_payload
activate_with_activation_id -> invalid_payload
refresh_without_activation_id -> invalid_payload
```

### Wichtig: Replay darf durch Vorvalidierung NICHT verloren gehen

Die v2-Vorvalidierung darf einen syntaktisch erkennbaren Command mit nutzbarer kanonischer `commandId` nicht einfach vor dem Replay-Layer wegwerfen.

Auch ein fachlich/strukturell abgelehnter Command muss die sessionweite Replay-/Conflict-Semantik erhalten:

- gleiche `commandId` + exakt gleicher v2-Payload → dasselbe ursprüngliche Ack, kein zweiter Effekt;
- gleiche `commandId` + anderer Payload → `command_id_conflict`.

Für v2-invalid payloads ist ein deterministischer, typstabiler Raw-Payload-Key zu verwenden.

Beachte: Das Legacy-SRV-030-Parsing ignoriert bei Controls ein `source`-Feld absichtlich für v1-Kompatibilität. Im v2-Envelope ist `source` bei Controls jedoch **verboten**. Daher darf die v2-Replay-Identität eines invaliden Control-Payloads nicht versehentlich die Legacy-Normalisierung übernehmen und das verbotene Feld unsichtbar machen.

Keine Änderung der SRV-030-v1-Kompatibilität nötig; v2 bekommt eine schmale strikte Envelope-/Projection-Schicht.

---

## K4 – Domain-Reasons → Frozen Wire Result Codes

**ROOT: APPROVED**

Genau eine explizite v2-Mapping-/Projection-Schicht.

Der v2-Wire darf ausschließlich diese 15 Result-Codes ausgeben:

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

`accepted=true` ausschließlich bei:

```text
applied
no_change
```

### Grundmapping für Activation Commands

```text
activated            -> applied
refreshed            -> applied
finished             -> applied
cancelled            -> applied

activation_locked    -> activation_locked
not_active           -> not_active
invalid_phase        -> invalid_phase
closing_input        -> closing_input
stale_activation     -> stale_activation
command_id_conflict  -> command_id_conflict
audio_unavailable    -> audio_unavailable

trigger_disabled /
runtime suppressed   -> trigger_suppressed

missing_command_id
invalid_command_id
invalid_action
invalid_source
invalid_payload
v2 envelope/schema violation
                      -> invalid_payload
```

`stale_session` entsteht auf der v2-Session-/Envelope-Grenze.

Settingscodes werden erst durch den SRV-050-Binding-Port vollständig fachlich gespeist:

```text
settings_revision_conflict
settings_rejected
```

`no_change` wird nur bei einem **wirklich erfolgreichen idempotenten No-op** verwendet, nicht als Sammelcode für Ablehnungen.

`internal_error` ausschließlich für unerwartete interne Fehler. Es darf kein Fallback für einen vergessenen bekannten Domain-Reason sein.

Implementiere die Tabelle zentral, exhaustiv und testbar.

Wenn ein bekannter Domain-Reason keinen Mappingeintrag besitzt, muss das in Tests/Entwicklung sichtbar fehlschlagen; nicht stillschweigend `internal_error` senden.

Domain-Reasons bleiben intern erhalten. Der Wire-Mapper ist Projection, keine zweite State Machine.

---

# 5. AP-SRV-030-SEAM FÜR `activation.input_closed`

Der frühere Blocker ist jetzt absichtlich beseitigt.

Final AP-SRV-030 besitzt:

```text
_registered_input_close_events
_reserve_input_close_event(...)
_publish_registered_input_close_event(...)
_discard_registered_input_close_event(...)
```

Diese Seam garantiert PHASE-04:

```text
safe physical close
→ ledger close
→ logical input-close registration
→ controller idle/unlock
→ transport publication
```

AP-SRV-040 MUSS an diese bestehende logische Registrierungsgrenze anbinden.

Nicht erlaubt:

- zweite Input-Close-Autorität,
- zweites unabhängig erzeugtes Close-Ereignis,
- Event erst nach Idle logisch erzeugen,
- neues Race zwischen Unlock und Eventregistration.

Ziel:

Die bestehende logische Reservation erhält im v2-Protokoll genau einmal:

```text
eventId
eventSeq
stateVersion
occurredAtUnixMs
```

und wird als

```text
activation.input_closed
```

projiziert.

Transport-Retry darf **keine neue logische Eventidentität** erzeugen.

Publisherfehler muss über Snapshot/Event-Resync reparierbar bleiben.

---

# 6. ProtocolSessionState – Ownership

Eine neue v2-ProtocolSessionState-/äquivalente Komponente darf ausschließlich Protokoll-/Projection-State besitzen:

```text
protocolVersion
sessionId
stateVersion
settingsRevision
next/last eventSeq
event registry / event metadata
handshake/protocol admission metadata
```

Sie besitzt NICHT:

- Activation-Phase,
- Activation-Deadline,
- Triggerlock,
- Segmentledger,
- Wake-Latch,
- Settings-Domainzustand,
- Recorderzustand.

Diese Authorities bleiben in ihren bestehenden Domainkomponenten.

`stateVersion` steigt nur bei einer nach außen sichtbaren logischen Zustandsänderung.

Transportwiederholung eines bereits registrierten Events:

```text
kein neuer eventId
kein neuer eventSeq
kein neuer stateVersion
```

---

# 7. Snapshot

`session.snapshot` ist Projection bestehender Authorities.

Pflichtfelder laut Frozen Schema:

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

`input`:

```text
phase
activationId
primarySource
deadlineAtUnixMs
remainingMs
closeRequested
```

`pendingActivations`:

- aus SegmentLedger/Hintergrundzustand ableiten,
- nach `activationSequence` streng sortieren,
- niemals über einen globalen Current-Activation-Zeiger korrelieren,
- `idle + ältere pending activations` muss darstellbar sein,
- `offene foreground activation + ältere pending activations` muss darstellbar sein.

Monotone Domain-Deadlines werden nur bei Projection gegen eine definierte Wallclock in `deadlineAtUnixMs`/`remainingMs` übersetzt; die Domain-Timerauthority bleibt monotonic.

---

# 8. Handshake-/Session-Atomarität

`hello.accepted` erst dann, wenn alle AP-SRV-040-seitig verfügbaren Admissionbedingungen erfolgreich sind.

Noch nicht final integrierte spätere APs nur über klare Ports:

```text
REQUIRES_AP_SRV_050_BINDING
REQUIRES_AP_SRV_060_BINDING
```

Nicht vortäuschen, dass Settings-/Wake-Word-Finalintegration schon abgeschlossen sei.

Für Wake-Auswahl darf AP-SRV-040 den Vertrag/Port vorbereiten; die endgültige Katalog-/selected-only-Implementation gehört SRV-060.

Für Settings darf AP-SRV-040 `settingsRevision` und Projection-Port vorbereiten; die autoritative Settings-Control-Plane gehört SRV-050.

---

# 9. Eventvertrag

Gemeinsame Pflichtfelder jedes v2-Domain-Events:

```text
type
protocolVersion
sessionId
eventId
eventSeq
stateVersion
occurredAtUnixMs
```

Canonical Events exakt nach Frozen Schema, darunter:

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

Keine freien Legacy-Eventnamen als v2-Domainvertrag durchreichen.

Legacy-Events dürfen im v1-Adapter bis SRV-070 weiterbestehen.

---

# 10. `causedByCommandId`

Für `activation.input_closed` verbindlich:

```text
normal accepted finish  -> commandId
normal accepted cancel  -> commandId
VAD/timer/watchdog      -> null
audio/device/session    -> null
Recovery completion     -> null
```

Auch wenn Recovery intern aus einem vorherigen Finish/Cancel entstanden ist:

```text
wire causedByCommandId = null
```

Der interne `CloseContext` darf die ursprüngliche Commandidentität weiterhin behalten.

Keine Ableitung über „letzter Command“.

---

# 11. Vertragsvektoren als ausführbare Quelle

Verwende direkt:

```text
ARBEITSDATEIEN/10_AKTUELL/EINHEITLICHE_TRIGGERARCHITEKTUR/PLANUNG/VERTRAGSVEKTOREN/protocol-v2-vectors.json
```

Mindestens:

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

Die Tests sollen die Datei laden, nicht Beispiele manuell auseinanderdriften lassen.

---

# 12. Baseline vor Produktmutation

Im neuen AP-SRV-040-Worktree vor der ersten Produktänderung:

```powershell
python -m pytest -q --basetemp=.pytest-tmp\baseline tests/unit
git diff --check
git status --short
```

Baseline-Ergebnis in AP-Akte dokumentieren.

Falls ein umgebungsabhängiger Test wegen fehlender externer Hardware/Weights sauber `skipped` ist, dokumentieren.

Keine rote Baseline einfach als AP-SRV-040-Fehler überschreiben; Ursache konkret klassifizieren.

---

# 13. Implementationsstruktur

Bevorzugt schmale Module statt weiterer Großblock in `server.py`, z. B. sinngemäß:

```text
api_fastapi_server/protocol_v2/
    __init__.py
    schema.py
    session.py
    events.py
    snapshot.py
    commands.py
```

Die exakten Namen dürfen an vorhandene Repositorykonventionen angepasst werden.

Wichtig ist die Ownership-Trennung:

```text
v2 transport/envelope
→ projection/adapters
→ vorhandene Domain Authorities
```

Nicht:

```text
v2 transport
→ zweite Activation-/Ledger-/Timer-State-Machine
```

---

# 14. v1-Kompatibilität

AP-SRV-040 entfernt Legacy noch NICHT.

Bis SRV-070:

```text
v1 endpoint -> Legacy Adapter
/ws/v2      -> Frozen v2 Contract
```

Kein v1-Fallback innerhalb einer bereits akzeptierten v2-Verbindung.

Kein v2-Client darf nach Handshake still auf v1-Semantik zurückfallen.

Der leere alte Prep-Branch ist kein Donor und wird nicht gemergt.

---

# 15. Pflicht-Testklassen

Mindestens:

## Handshake

- hello muss erste Textnachricht sein
- malformed JSON -> 4400
- falscher first message type -> 4400
- keine gemeinsame Version -> `protocol.incompatible` + 4406
- Handshake timeout -> 4408
- session rejected -> keine sessionId + 4409
- interner Fehler -> 1011
- vor hello.accepted kein Audio/Trigger/Wake

## UUID

- alle v2-generierten IDs kanonisch
- invalid commandId abgelehnt
- kein Compact→Canonical-Reformatalias
- ID bleibt Domain→Ledger→Wire identisch

## Commands

- alle Positiv-/Negativvektoren
- `extend` in v2 invalid_payload
- client `source=wake_word` invalid_payload
- source bei controls invalid_payload
- Replay exakt gleiches Ack
- Konflikt anderer Payload
- rejected command replay/conflict
- stale_session
- stale_activation

## Events

- eventSeq streng monoton
- eventId stabil
- stateVersion nur bei sichtbarer logischer Zustandsänderung
- Retry erzeugt keine neue Eventidentität
- genau ein `activation.input_closed`
- Finish-/Cancel-Korrelation korrekt
- Recovery `causedByCommandId=null`

## Snapshot

- idle ohne pending
- idle + mehrere pending activations
- foreground + ältere pending activations
- Sortierung activationSequence
- Eventgap → `session.snapshot.request`
- Snapshot ändert Domainstate nicht

## Regression

- vollständige AP-SRV-030-Fokussuite
- AP-SRV-020-Ledgerregression
- vollständige `tests/unit`

Race-/Exactly-once-relevante Tests deterministisch mit `Event`/`Barrier`, nicht mit Sleep als Ordnungsbeweis.

Kritische Event-/Replay-Races wiederholt ausführen, bevorzugt 20x.

---

# 16. Dokumentation / Akte

AP-SRV-040-Akte gemäß:

```text
docs/.archiv/README.md
```

anlegen/fortführen.

Mindestens:

- Originalprompt bzw. Referenz auf Auftrag
- dieser Root-Unblock/Folgeauftrag
- Implementierungsreport
- Evidence
- Abweichungsnotizen, falls nötig

Produktdokumentation aktualisieren.

Keine zentrale Root-Gate-Datei im Client eigenmächtig umdeuten.

---

# 17. Commit-Regel

Nach vollständiger grüner Validierung:

genau **ein lokaler Candidate-Commit** auf:

```text
review/AP-SRV-040/run-01
```

Empfohlene Message:

```text
feat(protocol): implement AP-SRV-040 protocol v2
```

Kein Push.

Kein Merge.

Kein Rebase.

Kein Amend fremder Commits.

Root bekommt zuerst Candidate-SHA/Tree und Evidence.

---

# 18. Handoff an Root

Am Ende exakt berichten:

```text
STATUS: READY FOR ROOT REVIEW | BLOCKED

BASE
SRV030_FINAL_SHA:
SRV030_FINAL_TREE:
verified origin branch:
worktree:
branch:

BASELINE
tests/unit:
diff-check:
working tree:

IMPLEMENTATION
v2 endpoint:
handshake:
ProtocolSessionState:
UUID ownership:
command envelope:
replay:
result mapping:
event registry:
stateVersion:
eventSeq:
snapshot:
input_closed binding:
v1 isolation:
SRV050 binding:
SRV060 binding:

K1
implementation:
proof:

K2
implementation:
proof:

K3
implementation:
proof:

K4
implementation:
proof:

TESTS
contract vectors:
negative handshake:
commands/replay:
events/versioning:
snapshot/resync:
input-closed exactly-once:
SRV030 regression:
SRV020 regression:
full tests/unit:
race repeat:
git diff --check:

CHANGED FILES

AP ARCHIVE

CANDIDATE COMMIT:
<sha>

CANDIDATE TREE:
<tree>

PARENT:
325e55c186713069b25208871da4fef16470f85a

WORKING TREE:
clean

PUSH:
no
```

---

# 19. Wichtigste Root-Regel

AP-SRV-040 darf nur eine **Wire-/Session-/Projection-Schicht** über die bereits akzeptierten Authorities legen.

Der Zielpfad ist:

```text
/ws/v2
→ hello/admission
→ ProtocolSessionState
→ strict v2 envelope
→ SRV-030 Command/Activation Authority
→ SRV-020 SegmentLedger
→ v2 event projection + snapshot
```

Nicht:

```text
/ws/v2
→ neue Activation State Machine
→ neues Ledger
→ neue Timer
→ zweite Close-Authority
```

Insbesondere die neue AP-SRV-030-Input-Close-Seam ist zu **binden**, nicht zu ersetzen.

Wenn kein neuer echter Frozen-Contract-Blocker auftritt, beginne nach Worktree-/Baseline-Verifikation direkt mit der Implementierung. Keine weitere Freigaberückfrage nötig.
