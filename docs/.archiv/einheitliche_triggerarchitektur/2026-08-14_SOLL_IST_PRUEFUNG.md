# Soll-/Ist-Prüfung – Einheitliche serverseitige Triggerarchitektur

**Datum:** 2026-08-14
**Prüfgegenstand:** der tatsächlich im Working Tree vorliegende Serverstand
**Soll-Quelle:** der normative Ausführungsauftrag „Einheitliche serverseitige
Triggerarchitektur"

> **Hinweis zur Quellenwahl.** Diese Prüfung vergleicht gegen den **normativen
> Ausführungsauftrag**, nicht gegen die ältere Planungsdatei
> `2026-08-12_EINHEITLICHE_TRIGGERARCHITEKTUR_PLAN.md` in diesem Ordner. Jene
> Datei stammt aus einem früheren Bearbeitungsanlauf, dessen Bewertungen
> anschließend verworfen wurden; sie bleibt als historisches Dokument
> unverändert erhalten (Archivregel: „Archivierte Planungen nicht stillschweigend
> an den aktuellen Stand umschreiben").

---

## 1. Soll-/Ist-Vergleich

| Soll laut Auftrag | Ist | Bewertung |
| --- | --- | --- |
| Eine Session besitzt genau einen Stream, einen ActivationController, einen Recorderpfad | erfüllt: `RecorderBackedRealtimeSession` erzeugt im Controlled-Modus genau einen `ActivationController`; der Recorder läuft in der `controlled`-Policy | **erfüllt** |
| Zwei unabhängig aktivierbare Triggerquellen | `manualTriggerEnabled` / `wakeWordTriggerEnabled` je Session | **erfüllt** |
| `false/false` bereits auf Konfigurationsebene abgelehnt | `activation_trigger_required`, Close 1008 | **erfüllt** |
| Controlled Gate ist alleinige Recorder-Autorität | `recording_activation_gate_is_open()` wertet im Controlled-Modus ausschließlich das Gate aus; `recorder.wakeword_detected` bleibt unberücksichtigt | **erfüllt** |
| Kein zweiter Recorderpfad, kein paralleler Follow-up-Timer | Legacy-Wakeword-Follow-up im Controlled-Modus abgeschaltet | **erfüllt** |
| Monotone Timer | alle Deadlines über `time.monotonic`; Wallclock nur für Logs | **erfüllt** |
| `primarySource` über die Activation stabil | im Controller unveränderlich gesetzt | **erfüllt** |
| `sources` enthält jede Quelle höchstens einmal | duplikatfreie Aggregation | **erfüllt** |
| Kollidierende Trigger erzeugen genau eine Activation, ein Segment, ein Final | serverseitig automatisiert nachgewiesen | **erfüllt** (real offen, siehe Abschnitt 2) |
| `trigger` / `trigger_ack` mit idempotenter `commandId` | implementiert, begrenzte Historie, deterministisches Wiederholungs-Ack | **erfüllt** |
| `start`/`stop` bleiben Streambefehle | serverseitig unverändert | **erfüllt** |
| Keine Capability vor funktionierendem Vertrag | `activationTriggers` erst nach vollständiger Verdrahtung veröffentlicht | **erfüllt** |
| Activation-Events | `activation.started` / `.extended` / `.closed` | **erfüllt** |
| Recording-/Transkriptionsevents tragen `activationId`, `primarySource`, `sources` | zentral in `_publish_timeline_event` ergänzt | **erfüllt** |
| Timeout/Scheduler mit Generationsschutz | generationsgebundener Timerthread je Session; `expire(version)` verwirft veraltete Timer | **erfüllt** |
| Reconnect belebt keine alte Activation | `close`/`stop_streaming`/`clear` setzen zurück | **erfüllt** |
| Legacykompatibilität | Sessions ohne Triggerparameter verhalten sich unverändert | **erfüllt** |
| Reale Abnahme mit Audio und Hardware | nicht durchgeführt | **offen**, siehe Abschnitt 2 |

---

## 2. Materielle Abweichungen

### A-1 – Reale Abnahme nicht durchgeführt

**Abweichung:** Der Auftrag verlangt eine reale E2E-Abnahme mit echter
Audioeingabe, echtem Clientbuild und echter ReSpeaker-Hardware.

**Ist:** Der Clientbuild wurde erzeugt und startet nachweislich
(`voice-stt-client.exe 0.2.0`, Smoke-Test `exit=0`). Echte Audioeingabe,
LED-Simulator und ReSpeaker-Hardware sind in der Bearbeitungsumgebung nicht
vorhanden.

**Begründung:** Ein Hardware- oder Audio-PASS ohne durchgeführten Test wäre
eine Falschaussage. Die betroffenen Punkte sind als
`MANUAL VALIDATION REQUIRED` mit konkreter Testanweisung ausgewiesen.

**Folge:** Der Gesamtstatus ist `PARTIAL`, nicht `DONE`.

### A-2 – Kein Commit, kein Push, kein Deployment

**Abweichung:** Der ursprüngliche Auftrag sieht Push, Remote-Verifikation und
CI-Prüfung vor.

**Begründung:** Die aktuelle Benutzerentscheidung verbietet Commit und Push
ausdrücklich. Nach der Quellenhierarchie des Auftrags gehen explizite aktuelle
Benutzerentscheidungen allen anderen Quellen vor.

**Folge:** Die gesamte Arbeit liegt uncommitted im Working Tree; alle drei
Repositories stehen unverändert auf ihrem Ausgangs-HEAD.

### A-3 – Wake-Word-Trigger nur über den Detektions-Callback geprüft

**Abweichung:** Der Wake-Word-Pfad wurde nicht mit einer laufenden
OpenWakeWord-Engine geprüft.

**Begründung:** In der Bearbeitungsumgebung sind keine
OpenWakeWord-Modelle installiert; eine Session mit aktivem Wake-Word-Profil
wird deshalb bereits bei der Admission abgelehnt.

**Ist:** Geprüft wurde der Callback `on_wakeword_detected`, also genau die
Schnittstelle, über die die Engine die Session erreicht. Ergänzend wurde der
Vertrag so verschärft, dass eine Session mit dem Wake Word als **einziger**
Triggerquelle ohne aktives Profil mit `activation_wake_word_unavailable`
abgelehnt wird, statt taub zu laufen.

### A-4 – Browserclient nicht geprüft

**Abweichung:** Der Auftrag verlangt einen Browserclient-Nachweis.

**Ist:** `app_browserclient/client.js` verbindet sich auf den Wurzelpfad, für
den der Server keine WebSocket-Route registriert. Das ist ein **vorbestehender**
Zustand des Beispielclients und unabhängig von dieser Aktion; sämtliche
Vertragsänderungen sind additiv.

**Folge:** Als `MANUAL VALIDATION REQUIRED` ausgewiesen.

---

## 3. Konsistenz der Fachdokumentation

| Dokument | Zustand |
| --- | --- |
| `docs/einheitliche-triggerarchitektur.md` | neu, beschreibt den implementierten Stand inkl. Zustandsdiagrammen |
| `docs/README.md` | verlinkt die neue Fachdokumentation |
| `docs/.archiv/README.md` | Registereintrag vorhanden, Status **In Umsetzung** |

Der Registerstatus bleibt bewusst auf **In Umsetzung**. Die Archivregel erlaubt
`Abgeschlossen` erst, wenn Umsetzung, Gegenprüfung, Abweichungsdokumentation
**und** die aktuelle Fachdokumentation konsistent sind. Solange die reale
Abnahme (A-1) aussteht, ist diese Bedingung nicht erfüllt.

---

## 4. Nachweise

Die vollständigen Gate-Nachweise, Testprotokolle und Mutationsnachweise liegen
außerhalb dieses Repositories im Arbeitsbereich der Aktion:

```text
zusammenarbeit/aktionen/einheitliche-triggerarchitektur/
├── STATUS.md      Übergabestand
├── PLAN.md        Arbeitsplanung
├── CONTRACTS.md   Cross-Repository-Vertragsmatrix mit PASS/FAIL/N-A
├── DECISIONS.md   Bewertung der übernommenen Vorarbeit
├── VALIDATION.md  Gate-Nachweise
├── REPORT.md      Abschlussbericht
└── evidence/      Rohprotokolle der Test-, Build- und Mutationsläufe
```
