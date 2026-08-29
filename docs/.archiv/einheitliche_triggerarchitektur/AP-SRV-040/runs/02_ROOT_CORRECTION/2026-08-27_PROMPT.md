# AP-SRV-040 – ROOT CORRECTION C2 / stateVersion-Härtung

## Begleitnachricht

Der Root-Review des vollständigen `SRV030_FINAL -> AP-SRV-040 Candidate`-Diffs ist abgeschlossen. Die Architektur, K1–K4, Handshake-/Replay-/Event-/Snapshot-Struktur und die bisherigen Tests sind grundsätzlich tragfähig. Es gibt aber einen begrenzten, echten Contract-Verstoß bei `stateVersion`: sichtbare Zustandsänderungen, die kein kanonisches Domain-Event erzeugen, erhöhen die v2-State-Version derzeit nicht zuverlässig.

Bitte ändere ausschließlich diesen Befund und die dafür notwendigen Tests/Dokumentationsstellen. Keine Architektur-Neuschreibung, kein Rebase, kein Push und keine fachfremden Änderungen.

---

## 1. Unveränderliche Ausgangslage

Bestehender Candidate:

```text
BASE SRV030:
325e55c186713069b25208871da4fef16470f85a
TREE:
ec5b6e0849bb7a0949ae5da05d168b8c19a4456e

AP-SRV-040 C1:
49a251fa69601494940185e08d360074de2b41e3
TREE:
e1461a756da318d0ff979a2b03d38c1f01063fc1
```

Branch/Worktree:

```text
review/AP-SRV-040/run-01
P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-040
```

Vor Mutation verifizieren:

```powershell
git branch --show-current
git rev-parse HEAD
git rev-parse "HEAD^{tree}"
git status --short
```

Erwartet: exakt obiger Candidate und sauberer Working Tree.

---

## 2. Root-Finding C2-01 – `stateVersion` ist nicht vollständig an sichtbaren State gebunden

Frozen Contract:

```text
stateVersion = Server; steigt bei jeder sichtbaren Zustandsänderung.
```

Der aktuelle `ProtocolSessionState` erhöht `_state_version` faktisch nur über `mint_event(..., state_change=True)`.

Das ist für Zustandsänderungen korrekt, die synchron ein kanonisches Event erzeugen. Es ist aber unvollständig für sichtbare Änderungen ohne eigenes Wire-Event.

### Belegt problematische Pfade

#### A. `trigger_suppression.set`

Aktuell:

```python
changed = controller.set_runtime_suppression(...)
return (
    RESULT_APPLIED if changed else RESULT_NO_CHANGE
), None
```

Danach baut `_emit_ack()` das Ack nur aus:

```python
state_version, settings_revision = self.state.versions()
```

Es gibt bei einer wirksamen Suppressionsänderung kein kanonisches `settings.changed` oder anderes State-Event. `activation.trigger_suppressed` ist ausdrücklich diagnostisch und entsteht erst beim später abgewiesenen Trigger.

Folge im C1-Candidate:

```text
trigger.suppressed ändert sich sichtbar
trigger.effective ändert sich sichtbar
Ack/Snapshot können trotzdem dieselbe stateVersion wie vorher tragen
```

Das ist verboten.

#### B. `audio_availability.set`

`audioAvailable` ist Pflichtfeld des `session.snapshot` und damit sichtbarer Serverzustand.

Wenn `audio_availability.set` den Wert wirksam ändert, muss die State-Version diese Änderung abbilden – auch wenn kein eigenes `audio_availability.changed`-Event im Frozen Eventkatalog existiert.

Besonders prüfen:

```text
idle + audioAvailable true -> false
```

Hier gibt es keine Activation, deren Lifecycle-Event den Versionsbump nebenbei übernehmen könnte.

#### C. Accepted `finish` / `cancel` -> `closing_input`

`closing_input` ist eine der fünf kanonischen sichtbaren Foregroundphasen.

Der Candidate legt bewusst fest, dass für den Eintritt in `closing_input` kein eigenes `activation.phase_changed`-Event erzeugt wird. Das ist als Wire-Design zulässig, **wenn** `stateVersion` trotzdem beim sichtbaren Eintritt in `closing_input` steigt.

Das Ack kann bereits:

```text
inputPhase = closing_input
```

zeigen, während `activation.input_closed` erst später nach der Safe-Close-Barriere entsteht.

Daher gilt:

```text
open phase
 -> accepted finish/cancel
 -> closing_input sichtbar
 -> stateVersion MUSS bereits höher sein
 -> später activation.input_closed / idle
 -> erneute sichtbare Änderung, erneute höhere stateVersion
```

Nicht erst beim späteren `activation.input_closed` erhöhen.

Dasselbe Prinzip gilt für jeden weiteren Commandpfad, der synchron sichtbaren State ändert, ohne dass während desselben Aufrufs bereits ein State-Event gemintet wurde.

---

## 3. Gewünschte strukturelle Lösung

Keine zweite Domain-State-Machine einführen.

`ProtocolSessionState` darf weiterhin ausschließlich Wire-/Projection-Versionierung besitzen.

Ergänze eine kleine, explizite API, sinngemäß:

```python
def advance_state(self):
    with self._lock:
        self._state_version += 1
        return self._state_version
```

Der genaue Name ist frei.

Wichtig ist die Regel:

```text
Ein logischer sichtbarer State-Change -> genau ein Versionsfortschritt.
```

Kein Doppelbump, wenn der Domainpfad synchron bereits ein State-Event durch den EventProjector gemintet hat.

Robustes Muster:

```text
stateVersion before
authoritativen Domain-/Commandpfad anwenden
stateVersion after event projection prüfen

wenn sichtbarer Zustand wirklich verändert UND
stateVersion noch unverändert:
    explizit einmal advance_state()
```

Damit dürfen synchron erzeugte Events wie `activation.started`/`activation.phase_changed` ihren bestehenden Bump behalten, während eventlose Änderungen ergänzt werden.

Für rein wire-eigene Mutationen wie `trigger_suppression.set` kann der wirksame `changed=True`-Pfad direkt genau einmal bumpen.

### Keine Versionsänderung bei

```text
no_change
Replay desselben Commands
command_id_conflict
invalid_payload
stale_session
stale_activation
reiner snapshot.request
diagnostischem watchdog.warning
diagnostischem activation.trigger_suppressed
```

Transport-Retry darf weiterhin keine neue Version minten.

---

## 4. Replay bleibt wie in C1

Keine Änderung an der bereits korrekten Additive-Field-Semantik:

```text
gültiger Command
+ nur unbekanntes additives Feld
+ gleiche bekannte Semantik
=> Replay / identisches Ack
```

Das folgt aus der Frozen-Regel, dass unbekannte additive Felder derselben Protokollversion bekannte Semantik nicht verändern.

Weiterhin Conflict bei einer Änderung **bekannter/semantischer** Commandfelder.

Für v2-invalid/rejected Payloads bleibt die bereits implementierte vollständige typstabile Raw-Payload-Identität bestehen.

---

## 5. Pflicht-Regressionsfälle

Ergänze deterministische Tests mindestens für:

```text
1. trigger_suppression applied:
   before stateVersion = N
   Ack stateVersion = N+1
   Snapshot stateVersion = N+1
   suppressed/effective tatsächlich geändert

2. trigger_suppression no_change:
   keine Erhöhung

3. trigger_suppression replay:
   exakt dasselbe ursprüngliche Ack inkl. stateVersion
   keine weitere Erhöhung

4. audioAvailable true -> false in idle:
   stateVersion steigt
   Ack und Snapshot stimmen überein

5. audio availability no_change/replay:
   keine zweite Erhöhung

6. finish aus waiting_first_speech:
   activation.started-Version = N
   accepted finish Ack zeigt closing_input
   Ack stateVersion > N
   später activation.input_closed hat nochmals höhere stateVersion

7. cancel analog zu finish

8. falls device close gleichzeitig audioAvailable und Phase ändert:
   deterministisch beweisen, dass die Wire-Versionierung der logischen
   Zustandsänderung konsistent ist und kein Doppel-/Missing-Bump entsteht.

9. snapshot.request:
   stateVersion unverändert

10. diagnostics:
    watchdog.warning und activation.trigger_suppressed erhöhen stateVersion nicht.
```

Keine Sleep-basierten Ordnungsbeweise; vorhandene Barrier/Event-Methodik verwenden.

---

## 6. Bestehende C1-Architektur nicht aufreißen

Nicht verändern, sofern kein direkter C2-Need entsteht:

```text
/ws/v2 Trennung
Handshake-first
K1 UUID ownership
K2 endpoint isolation
K3 strict envelope
K4 result mapping
CommandReplayCache als einzige Replay-Autorität
Input-close-Seam
EventProjector
Ledger-basierte pendingActivations
SRV-050 / SRV-060 Ports
v1-Kompatibilität
```

---

## 7. Tests nach Korrektur

Mindestens erneut:

```text
tests/unit/test_protocol_v2_contract.py
tests/unit/test_protocol_v2_e2e.py
tests/unit/test_protocol_v2_races.py

AP-SRV-030 Regression/Fokus
AP-SRV-020 Regression
vollständige tests/unit
```

Die stateVersion-relevanten Race-/Replay-Tests wiederholt 20x.

`git diff --check` sauber.

---

## 8. Git-Regel

Den vorhandenen C1-Commit **nicht** amendieren.

Erzeuge genau einen lokalen C2-Commit auf demselben Branch, z. B.:

```text
fix(protocol): harden AP-SRV-040 state versioning
```

Kein Push.
Kein Merge.
Kein Rebase.

Danach berichten:

```text
STATUS: READY FOR ROOT RE-REVIEW

C1 SHA:
49a251fa69601494940185e08d360074de2b41e3

C2 SHA:
...

C2 TREE:
...

PARENT:
49a251fa69601494940185e08d360074de2b41e3

FINDING C2-01:
...

STATEVERSION TEST MATRIX:
...

PROTOCOL V2 TESTS:
...

SRV030 REGRESSION:
...

SRV020 REGRESSION:
...

FULL UNIT:
...

RACE REPEAT:
...

git diff --check:
clean

WORKING TREE:
clean

PUSH:
no
```

Root wird danach C1+C2 als einen finalen kanonischen AP-SRV-040-Commit auf `feat/einheitliche-triggerarchitektur-distributed` squashen. Nicht selbst mergen oder pushen.
