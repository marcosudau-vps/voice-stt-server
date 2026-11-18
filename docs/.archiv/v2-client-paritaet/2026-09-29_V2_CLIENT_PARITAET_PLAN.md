# V2-Client-Parität: neun konkrete Arbeitspunkte vor der Cliententwicklung

**Datum:** 2026-09-29 · **Status:** Geplant, nicht implementiert.

Dieses Dokument hält den unmittelbar am Code überprüften Ist-Zustand und das
empfohlene Umsetzungsziel fest. Es ist eine Arbeitsgrundlage für nachfolgende
Serverarbeiten, keine Bestätigung ihrer Durchführung und keine neue, bereits
gültige Protokollreferenz. Die Erstellung verändert ausschließlich Dokumentation.

## 1. Ergebnis und verbindlicher fachlicher Umfang

Der vorhandene V2-Server unterstützt bereits den gewünschten Grundablauf:
Audiostream öffnen, auch lange auf ein Wake Word warten, nach einer zulässigen
Aktivierung Sprache aufnehmen, Ergebnisse liefern und anschließend wieder auf
einen Trigger warten. **Dauerhaftes Wake-Word-Lauschen muss nicht als neuer Modus
implementiert werden.** Die ursprüngliche V2-State-Machine hatte bereits einen
Idle-Zustand ohne Deadline. Das ist vom Timeout nach erfolgter Aktivierung zu
unterscheiden. Ein realer Dauerbetriebstest bleibt erforderlich.

Finaltexte werden ebenfalls bereits als strukturierte `transcription.completed`-
Logeinträge erzeugt. Ihre Speicherung mit Text hängt von der Text-Logging-Policy
und einem verfügbaren Eventstore ab. Eine neue Ergebnisdatenbank ist dafür nicht
erforderlich.

Vor der Desktop-Cliententwicklung sollten dagegen die Zuordnungs- und
Recoveryfehler, der sessionweite Reset, beobachtbare Fehler und Audiozustände,
eine ausdrückliche Audiopause sowie der Umgang mit langsamen Clients bearbeitet
werden. Segmentmetadaten ergänzen die Client-Parität mit vergleichsweise geringer
Änderung an der Projektion. Die neun Punkte sind unten einzeln abgegrenzt.

### Vom Auftraggeber bereits entschiedene Produktgrenzen

- Kein triggerloser Dauerdiktat-Modus. Sprache allein soll keine dauerhafte Folge
  neuer Diktate eröffnen. Zulässige Auslöser bleiben die vorgesehenen Trigger.
- Langes, ereignisloses Wake-Word-Warten innerhalb einer bestehenden, verbundenen
  Session ist ausdrücklich gewünscht. Dafür muss der Client weiterhin Audio
  liefern; keine Pakete zu senden entspricht nicht digitaler Stille.
- Keine garantierte spätere Nachladung verlorener Finaltexte, keine Wiederaufnahme
  einer alten Session und kein Domain-Event-Replay als neues Produktmerkmal.
- Finaltexte sollen regulär in den strukturierten Logs stehen. Log-Historie bleibt
  Diagnosehistorie mit Aufbewahrungs-, Berechtigungs- und Verfügbarkeitsgrenzen.
- Wake-Word-Modellbestand, Modellauswahl und Katalogänderungen sind ausgeschlossen.

Die technischen Sollregeln dieses Plans sind Umsetzungsempfehlungen. Insbesondere
die unten konkretisierte Regel »Pause beendet die Eingabe regulär, Reset verwirft
offene Arbeit« wurde nicht zuvor ausdrücklich vom Auftraggeber gewählt. Sie wird
hier als empfohlene Arbeitsvorgabe festgelegt und darf nicht nachträglich als
bereits erteilte Detailfreigabe ausgegeben werden. Es besteht kein Auftrag zur
Implementierung durch die Erstellung dieses Dokuments.

## 2. Überprüfte Stände und Beweisgrenzen

Repository: `marcosudau-vps/voice-stt-server`.

| Rolle | Ref | Tatsächlicher Commit |
| --- | --- | --- |
| V1-Vergleich | Remote `main`, lokal `origin/main` | `714b1cf9199bc83b69ca7a531143d174bb60354b` |
| V2-Arbeitsstand | `feat/einheitliche-triggerarchitektur-distributed`, lokal und remote | `70c46235bd74ad464626ed39b3c1e42df57ab9b0` |
| Wiederherstellung Realtime/Logzugriff | AP-SRV-080, im V2-HEAD enthalten | `d410fc61ecf2471bd36d981067460277b132920c` |
| Frühe V2-State-Machine | AP-SRV-010, historische Implementierung | `3262079` |

Die beiden Remote-Branchstände wurden mit `git ls-remote` überprüft. Es wurden
keine Branches gewechselt, keine Remote-Refs durch Fetch verändert und keine
Abhängigkeiten installiert. Der lokale Hauptcheckout liegt auf einem älteren
`main`-Stand (`13c162950b944dc715fdd81983a7465f8eb0fd79`); dieser wurde nicht mit
dem aktuellen Remote-`main` gleichgesetzt. V1-Code wurde über `git show origin/main:…`
gelesen. V2 wurde im vorhandenen Worktree `workspaces/ap-srv-070-w5-r04` geprüft.

Alle folgenden Codezeilen beziehen sich auf den genannten V2-HEAD, sofern nicht
ausdrücklich V1 oder ein historischer Commit genannt ist. Die relativen Links
zeigen auf Dateien dieses Worktrees. Nach einer Implementierung können sich
Zeilennummern verschieben; Funktionsnamen und Baseline bleiben Referenz.

**NACHGEWIESEN** bezeichnet direkt nachvollzogene Implementierung, vorhandene
Tests oder eine ausdrücklich beschriebene Entscheidung. **PLAUSIBEL** bezeichnet
ein daraus abgeleitetes Betriebsrisiko ohne beobachteten Produktionsfehler.
**UNKLAR** bezeichnet insbesondere historische Absichten, für die die Quellen
keinen eindeutigen Grund liefern. Ein fehlender Adapterpfad allein beweist keine
bewusste Produktentscheidung.

### Durchgeführte Validierung

145 ausgewählte bestehende Tests wurden unter Python mit `-B` und einem
Audit-Hook ausgeführt, der Dateischreiben und Dateisystemmutationen verweigert:
**144 bestanden, 1 übersprungen, keine fehlgeschlagen.** Auswahl:

- `tests.unit.test_server_activation_controller`
- `tests.unit.test_server_segment_ledger`
- `tests.unit.test_wake_admission`
- `tests.unit.test_wakeword_recording_path`
- Aus `tests.unit.test_protocol_v2_contract`: `ContractVectorFileTests`,
  `CanonicalIdentityTests`, `StrictEnvelopeTests`, `ResultMappingTests`,
  `ProtocolSessionStateTests`, `EventProjectionTests`, `DeadlineProjectionTests`,
  `SnapshotCombinationTests`.

Übersprungen wurde der Vergleich mit einer externen Original-Vektor-Datei, weil
`VOICESTT_PROTOCOL_V2_VECTORS` nicht gesetzt ist. Die vorhandene Vektordatei selbst
wurde durch die übrigen ausgewählten Prüfungen berücksichtigt. Die im Testlauf
ausgegebene simulierte Exception »controller unavailable« gehört zu einem
bestandenen Wake-Admission-Fehlertest.

Zusätzlich wurden zwei ausschließlich speicherbasierte Proben mit produktiven
Methoden ausgeführt: falsche Activation-Zuordnung beim Start einer älteren
Transkription und Projektion eines Interims nach einem Final. Details in Punkt 1
und 7. Andere unten genannte Tests wurden als Quellen gelesen; sie sind dadurch
nicht automatisch Teil des ausgeführten Testumfangs. Kein vollständiger
Integrationstest mit realen Modellen, kein Netzwerk-Lasttest und kein
mehrstündiger Dauerbetrieb wurden durchgeführt.

## 3. Priorität und Aufwand

»Klein« bedeutet eine örtlich begrenzte Erweiterung mit Vertrag und Tests.
»Mittel« bedeutet mehrere vorhandene Module und Nebenläufigkeit, aber kein neues
Produkt-Subsystem. Die Einschätzung schließt Tests und Dokumentation ein und ist
keine belastbare Tagesplanung. Bei Reset und Backpressure kann ein unvorsichtiges
Vorgehen den Aufwand deutlich erhöhen.

| Nr. | Arbeitspunkt | Priorität | Aufwand | Vorhandene Grundlage |
| --- | --- | --- | --- | --- |
| 1 | Segmentzuordnung und terminale Recovery zuverlässig machen | P0 | mittel | Immutable SegmentContext, Ledger, V2-Observer, Connection-Close |
| 2 | Sessionweiten Reset ergänzen | P1 | mittel | Generationen, `cancel_all`, Recorder-Abbruch, Scheduler-Cancel |
| 3 | Audio-, Admission- und Recorderfehler für V2 beobachtbar machen | P1 | mittel | Fehlerstellen, Terminalevents, strukturierte Logs, Sessiontoken |
| 4 | Audio-/Recorderstatus für Tray und Feedback bereitstellen | P1 | mittel | Recordercallbacks, Sessionmetriken, V2-Snapshot |
| 5 | Audiopause und Fortsetzung in derselben Session | P1 | mittel | `streaming`, Start/Stop, Gate-Close, Lifecycle-Epochen |
| 6 | Vorhandene Segmentmetadaten projizieren | P2 | klein bis mittel | `SegmentTimelineTracker`, bestehende V1-Felder |
| 7 | Interim-Gültigkeit und ausgehende Puffer absichern | P0 | mittel, Lastnachweis nötig | Recorderidentität, Stabilizer, Dispatch-Lock, V2-Writer |
| 8 | Langes Wake-Word-Warten und Final-Logging absichern | P1 | klein für Vertrag/Tests; Dauerprüfung zusätzlich | Beides bereits implementiert |
| 9 | Vertrag, aktive Dokumentation und Tests konsistent abschließen | P1 | klein bis mittel, begleitend | Client-Dokumentation, Contract-Vektoren, bestehende Tests |

P0 bedeutet vor Freigabe für den neuen Client behandeln. P1 gehört zum hier
empfohlenen Funktionsumfang; P2 ist weniger kritisch für korrekte Diktate, sollte
aber vor Festlegung der Client-Datenmodelle abgeschlossen werden. Punkt 9 läuft
mit allen anderen mit und ist Voraussetzung für den abschließenden Vertragsstand.

## 4. Punkt 1 – Segmentzuordnung und terminale Recovery

### Ist-Verhalten und Fehlerursache

**NACHGEWIESEN: Eine ältere Transkription kann im V2-Event der neuen Activation
zugeordnet werden.** `_on_transcription_start()` liest den unveränderlichen
`_current_transcription_context`. Der strukturierte Eintrag
`transcription.accepted` übernimmt daraus die richtige Activation. Der direkt
danach erzeugte Timeline-Aufruf `transcription_started` übergibt jedoch nur
Segment-ID und Timeline-Snapshot. `_publish_timeline_event()` ergänzt die
Activation aus dem aktuell offenen Vordergrund. `EventProjector._segment_fields()`
bevorzugt diese explizite Payload-Activation gegenüber seiner gespeicherten
Segmentzuordnung.

Konkretes Szenario: A1 hat mehrere angenommene Segmente; ihre Verarbeitung ist
noch nicht vollständig angelaufen. A1 schließt die Eingabe, A2 beginnt. Beginnt
jetzt die Transkription eines älteren A1-Segments, kann `transcription.accepted`
A2 nennen. `_publish_ordered_final()` verwendet später wieder den ursprünglichen
Kontext. Damit kann derselbe Segmentlebenszyklus widersprüchliche Eltern haben.

Die speicherbasierte Probe band die echten Methoden `_on_transcription_start`,
`_publish_timeline_event` und `_activation_correlation` an einen minimalen
Session-Doppelgänger, setzte A1 im Recorderkontext und A2 im Controller und
verwendete den echten V2-Projektor. Ergebnis: Log-Activation A1, V2-Accepted A2.
Das belegt den fehlerhaften Adapterpfad unter dieser Bedingung; es ist kein
Nachweis seiner Häufigkeit mit einem realen Modell.

**NACHGEWIESEN: Terminale Domain-Recovery beendet den V2-Transport nicht
ausdrücklich.** `fail_closed_for_recovery()` sendet eine Legacy-Warnung und ruft
`self.close()` auf. V2 ist absichtlich nicht im Legacy-ConnectionManager
registriert. Die V2-Receive-Schleife prüft `connection.closed`, nicht den terminalen
Status der Domain-Session. Ein Observerpfad, der diesen Recoveryfall an
`ProtocolV2Connection.request_close()` bindet, fehlt. **PLAUSIBEL:** Der Client
kann eine noch offene Verbindung zu einer bereits geschlossenen Session sehen,
bis ein anderer Transportabbruch auftritt; ein belegter Produktionsvorfall liegt
nicht vor.

### Soll und Umsetzung

- Segmentgebundene Ereignisse erhalten immer den Kontext des betreffenden
  Segments, auch wenn im Vordergrund schon eine andere Activation läuft.
- Die aktuelle Controller-Activation darf nur für tatsächlich
  activationgebundene Ereignisse die Quelle sein. Fehlender Segmentkontext darf
  nicht durch die zufällig aktuelle Activation kaschiert werden.
- Technisch endgültiger Sessionabbruch wird über einen expliziten Adapterpfad
  an den WebSocket weitergegeben: verständlicher Grund, definierter Close-Code,
  Aufwecken einer wartenden Receive-Schleife und Freigabe des Session-Slots.
  Nur ein Close-Marker für den Writer reicht dafür nicht aus.
- Bereits terminale Segmente/Activations erhalten keine zweite fachliche
  Terminierung. Aufräumaktionen bleiben idempotent.

**Desktop-Auswirkung:** Richtige Zuordnung von Vorschau, Verarbeitungsanzeige und
Finaltext; nach fataler Recovery eindeutig »Verbindung neu aufbauen« statt einer
scheinbar betriebsbereiten, wirkungslosen Session.

**Abnahme:** A1 mit mindestens zwei verzögerten Jobs, A2 bereits offen; sämtliche
Segmentevents bleiben A1 zugeordnet. Erfolgreiche und fehlgeschlagene Recovery
über den echten V2-Endpunkt prüfen, einschließlich wartendem Receive, genau einem
Close, Session-Slot-Freigabe und neuem Handshake. Den bisherigen Final-Overlap-Test
um den Start der späteren Transkription ergänzen.

**Code:** [server.py](../../../api_fastapi_server/server.py),
`_activation_correlation` 3460–3478, `_on_transcription_start` 5393–5433,
`_publish_timeline_event` 5726–5796, `_publish_ordered_final` 4782–4859,
`fail_closed_for_recovery` 4224–4270, V2-Endpoint 9763–9855;
[events.py](../../../api_fastapi_server/protocol_v2/events.py), 187–219;
[connection.py](../../../api_fastapi_server/protocol_v2/connection.py), 140–152.
Vorhandene Ansatzpunkte: [Controlled-E2E](../../../tests/unit/test_server_controlled_e2e.py),
`BackgroundDrainOverlapTests`, und [Timer-E2E](../../../tests/unit/test_server_command_timer_e2e.py),
Recoveryprüfungen. Nicht nur Domain-Doppelgänger testen.

## 5. Punkt 2 – Vollständiger Session-Reset

### Ist-Verhalten

V1-`clear` auf `origin/main` erhöht die Generation, setzt Segment-/Timeline- und
Realtime-Statistikzustände zurück, verwirft die aktuelle Aufnahme, beendet
Followup-Zustände, storniert Scheduler- und Recorder-Warteaufträge, gibt den
Speaker frei und ruft `recorder.abort()` auf. Anschließend kommen `clear` und
Status. Verbindung und Sessionkonfiguration bleiben erhalten. Das ist ein
logischer Abbruch; ein schon laufender Modellaufruf muss dadurch nicht physisch
sofort beendet werden.

V2-`cancel` adressiert die Vordergrund-Activation. Bereits geschlossene ältere
Activations mit noch ausstehenden Segmenten werden dadurch nicht insgesamt
verworfen. Bei Idle gibt es keine aktuelle Activation, die man dafür abbrechen
könnte. Auch `audio_availability.set(false)` lässt den Hintergrund anderer
Activations bestehen. Disconnect verwirft sessionweit, verliert aber die Session.

**NACHGEWIESEN:** `SegmentLedger.cancel_all()` besitzt bereits eine geeignete
sessionweite Abbruchbarriere: erst sämtliche unpublizierten Ergebnisse markieren,
dann gemeinsam drainieren. `close()` benutzt sie. Die auf dem V2-Branch weiterhin
vorhandene Legacy-Methode `clear()` darf nicht blind als neuer V2-Befehl exportiert
werden: Bei offener Activation schließt sie zunächst diese; nur der andere Zweig
ruft unmittelbar `cancel_all()` auf. Dazu kommen Legacy-Nachrichten und
V1-Segmentreset-Semantik. Ein dokumentierter fachlicher Verzicht auf jeden
Gesamtreset ist aus der bloßen Abwesenheit des V2-Befehls nicht ableitbar.

### Soll und Umsetzung

Arbeitsname des neuen Commands: `session.reset`, ohne Activation-ID.

1. Eine einzige sessionweite Publikationsbarriere gewinnt entweder vor oder nach
   einem konkurrierenden Final. Vorher veröffentlichte Ergebnisse bleiben
   veröffentlicht; danach darf kein alter Finaltext mehr neu veröffentlicht
   werden. Bereits vor dem Reset an den Transport übergebene Nachrichten sind
   nicht rückrufbar und müssen vor der Reset-Bestätigung geordnet bleiben.
2. Alle offenen und alle geschlossenen, noch nicht abgearbeiteten Activations
   einschließlich vorbereiteter Finals werden verworfen und nachvollziehbar
   terminalisiert. Nicht nur die aktuelle Aufnahme behandeln.
3. Gate, Recorderpuffer, ausstehende Jobs, Timer, Wake-Latch, Realtimezustand und
   Timeline-Kontexte werden sicher bereinigt; spät eintreffende Callbacks alter
   Generationen bleiben wirkungslos.
4. Session-ID, Einstellungen, Triggerfreigaben und Audiopause-Zustand bleiben
   erhalten. Reset ist weder neue Session noch »Mikrofon einschalten«.
5. `eventSeq`, `stateVersion`, Settings-Revision und öffentlich verwendete
   Identitäten werden nicht auf null zurückgesetzt oder wiederverwendet.
   Command-Idempotenz einschließlich des Reset-Commands bleibt erhalten.
6. Nach bestätigtem Abschluss ist die Eingabe wieder Idle, sofern ihr sicheres
   Schließen gelang. Andernfalls greift die terminale Recovery aus Punkt 1.
   Alte Ledger-Arbeit darf nicht mehr als pending erscheinen.

**Desktop-Auswirkung:** Ein »Alles verwerfen«-Knopf arbeitet auch bei mehreren
nachlaufenden Diktaten. Ein reiner UI-Reset oder Cancel der neuesten Activation
wäre dafür unzureichend.

**Abnahme:** A1 geschlossen mit laufendem S1 und fertig vorbereitetem S2, A2 offen
mit S3; Reset muss alle drei korrekt behandeln. Parallel dazu Final-Publikation,
neue Audiopakete und Recordercallback blockiert/freigegeben variieren. Kein alter
Text nach der Reset-Bestätigung, keine Doppelterminals, kein Identitätsrecycling;
anschließend neue Activation erfolgreich. Reset auch bei Idle mit Hintergrundjobs,
bei vollständig leerer Session sowie Wiederholung derselben `commandId` prüfen.

**Code:** V1 [server.py am Vergleichscommit](https://github.com/marcosudau-vps/voice-stt-server/blob/714b1cf9199bc83b69ca7a531143d174bb60354b/api_fastapi_server/server.py#L2569),
2569–2606; V2 [server.py](../../../api_fastapi_server/server.py), `clear` 2933–2989,
`close` 2875–2931, Cancel-Publikationsbarriere ab 3554;
[segment_ledger.py](../../../api_fastapi_server/segment_ledger.py), `cancel_all`
375–419. Vorhandener Test:
[test_server_segment_ledger.py](../../../tests/unit/test_server_segment_ledger.py),
`test_cancel_all_marks_every_activation_before_one_session_drain`.

## 6. Punkt 3 – Fehler und Warnungen für den Client beobachtbar machen

### Ist-Verhalten und konkrete Lücken

| Pfad | Tatsächliche V2-Beobachtbarkeit | Benötigte Ergänzung |
| --- | --- | --- |
| `max_active_speakers` überschritten | Recorder verwirft; nur Legacy-`warning`, kein entsprechendes V2-Ereignis | Sessiongebundener Hinweis, dass diese Aufnahme nicht angenommen wurde |
| Ungültiges/zu großes Audiopaket | `handle_binary` fängt `AudioPacketError`, schreibt Debuglog und gibt `False` zurück | Maschinenlesbarer, begrenzter Diagnosehinweis und Zähler |
| Fehler beim `feed_audio` | `recorder.failed` im Kanal `system`; Rückgabehinweis wird in V2 als `_warning` ignoriert | Sessionbezogene Projektion ohne Freigabe globaler Systemlogs |
| Aufnahmelimit/erzwungenes Ende und verworfene gepufferte Aufnahme | Legacy-Warnungen, Zähler und je nach Kontext Segmentterminals; kein einheitlicher V2-Diagnosepfad | Sichtbarer Grund für verkürzte oder verworfene Aufnahme, mit vorhandenen Terminals abgleichen |
| Scheduler lehnt Final ab/verwirft ihn | Bei vorhandenem SegmentContext bereits Ledger-Terminal und V2-Failure/Discard | Bestehendes Terminal behalten; Diagnosegrund und Korrelation prüfen |
| Realtime verworfen/coalesced/stale | Teilweise Metrikzähler; nicht jeder Fall als V2-Event | Aggregierte Diagnose; normale Vorschau-Ersetzung nicht als Diktatfehler behandeln |
| Modell-/Workerfehler | Systemlogs, Health; segmentbezogene Folgeschäden können terminal sichtbar werden | Falls die eigene Session betroffen ist: verständlicher Fehlergrund; globale Details bleiben administrativ |
| Harte Lifecycle-Recovery | Legacy-Warnung; Transportlücke aus Punkt 1 | Eindeutiger V2-Abbruchpfad |

**NACHGEWIESEN:** Ein V2-Sessiontoken erlaubt für die eigene Session `audit`,
`performance`, `transcription`; `system` bleibt ausgeschlossen. Fehlende strukturierte
Einträge und ausgeschlossene Systemfehler werden nicht allein durch AP-SRV-080
sichtbar. Logs sind außerdem kein Ersatz für ein verbindliches Segmentterminal.

### Soll und Umsetzung

- Vorhandene Domain-Terminals weiterverwenden. Zusätzlich einen kleinen
  sessiongebundenen Diagnoseeventtyp mit stabilen Codes vorsehen; Arbeitsname
  `session.diagnostic`. Keine pauschale Durchleitung von V1-`warning/error`.
- Felder festlegen: `code`, `severity`, `message`, `recoverable`, optional
  `activationId`, `segmentId`, `requestId`, aggregierte Anzahl. Rohes Audio,
  interne Exceptions mit Secrets und Daten anderer Sessions nicht exportieren.
- Dieselben relevanten Vorfälle strukturiert im berechtigten Sessionumfang
  protokollieren. Keine pauschale Erweiterung der Tokenrechte auf `system`.
- Paketfehler und Realtime-Verwerfungen begrenzen/zusammenfassen, damit die
  Diagnose selbst keinen neuen Backpressure-Pfad schafft.
- Diagnoseereignisse allein verändern nicht die Domain-`stateVersion`.
  Tatsächliche Zustandsänderungen werden weiterhin durch Lifecycle/Snapshot
  abgebildet. Ihre Einordnung in `eventSeq` und Coalescing wird mit Punkt 7
  festgelegt.

**Desktop-Auswirkung:** Die Tray-Anwendung kann »Aufnahme wegen Auslastung
abgewiesen« oder »Audio wird nicht verarbeitet« anzeigen, statt auf einen Text zu
warten, der nie entstehen wird. Ein eigener dritter WebSocket-Endpunkt ist dafür
nicht erforderlich; Domainevents, ein schlanker Diagnoseeventtyp, HTTP-Metriken
und vorhandene Sessionlogs genügen.

**Abnahme:** Jeden Tabellenpfad gezielt auslösen. Verfügbarkeit über den normalen
V2-Client und dessen Sessiontoken prüfen; Fremdsession/Systemdetails bleiben
unzugänglich. Häufige ungültige Pakete erzeugen begrenzte Meldungsraten. Ein Final
erhält genau ein Terminal, auch wenn zusätzlich ein Diagnoseeintrag entsteht.

**Code:** [connection.py](../../../api_fastapi_server/protocol_v2/connection.py),
`handle_binary` 181–198; [server.py](../../../api_fastapi_server/server.py),
`ingest_audio_packet` 2991–3022, `on_job_dropped`/`on_submit_result` 3030–3071,
`_on_recording_start` 5184–5216, Dauerbegrenzung/erzwungenes Ende/Queue-Trim ab
5851/5901/5927, `_submit_scheduler_job` ab 6598,
`packet_to_server_samples` ab 6760, HTTP-Logscope 8486–8540 und WS-Logscope ab 8615.
V2-Logzugriffstest:
[test_protocol_v2_e2e.py](../../../tests/unit/test_protocol_v2_e2e.py),
`test_v2_log_access_token_authorizes_session_history_and_live_logs`.

## 7. Punkt 4 – Recorder-/Audiozustand für Tray und Feedback

### Ist-Verhalten

V2-Phase und Lifecycle beantworten »Welche Activation/Segmenteingabe ist offen?«.
Sie beantworten nicht vollständig »Wird gerade Audio empfangen?«, »Ist der
Recorder sprachaktiv?« oder »Arbeitet im Hintergrund noch eine Transkription?«.
Letzteres ist getrennt über die Ledger-/Snapshot-Zähler erkennbar. `idle` darf
daher nicht als »Server tut nichts« interpretiert werden.

`publish_status()` erstellt weiterhin Legacy-Statusnachrichten mit Zuständen und
Queue-/Drop-Werten. Diese gelangen nicht an V2. Die Sessionmetrik `snapshot()`
enthält `streaming`, `recording`, `state`, Queue-Tiefe und zahlreiche Zähler und
wird über HTTP-Metriken verfügbar gemacht. Ein Poll ist aber kein identischer
Ersatz für zeitnahes Feedback auf einen Recorderzustandswechsel.

**Wichtige Einschränkung:** Die V2-Aufnahme ist durch ein Activation-Gate
geschützt. Im Recorder wird vor Aufnahmebeginn erst das Gate geprüft, dann die
Sprachaktivität. Im Wake-Wartezustand liefert die bestehende VAD-Pipeline deshalb
nicht zwangsläufig ein fortlaufendes, unabhängig verwertbares `voice/silence`-
Signal. Auch die bisherigen Wake-Statushilfen bilden dies teilweise auf
`wakeword_wait` ab. Ein neuer dauernd laufender Idle-VAD wäre eine zusätzliche
Audiofunktion, keine reine Wiederherstellung eines fehlenden Events.

### Soll und Umsetzung

- Einen kleinen, konsistenten Audiozustand im V2-Snapshot sowie ein passendes
  Änderungsereignis ergänzen. Inhaltliche Dimensionen: Stream läuft/pausiert,
  Recorder nimmt auf/nimmt nicht auf, Wake-Warten soweit zuverlässig bestimmbar,
  gemessene Sprachaktivität `voice`/`silence`/`unknown`.
- `unknown` verwenden, wenn tatsächlich keine aktuelle VAD-Messung vorliegt.
  Aus »keine Pakete« oder »keine Activation« keine gemessene Stille erfinden.
- Domainphase, Audiozustand und Diagnosezähler getrennt halten. Kein globales
  `transcribing`, das eine gleichzeitige neue Aufnahme verdeckt. Hintergrundarbeit
  wird aus den bestehenden Lifecycle-/Ledgerinformationen dargestellt.
- Snapshot-relevante Audiozustandsänderungen versionieren; reine Zähler-/
  Zeitaktualisierungen nicht ungebremst zu Domainänderungen machen. Ereignisrate
  begrenzen und keine unveränderten Zustände ständig neu senden.
- Ein optionales Signal »zuletzt Audio empfangen« als Diagnose ausweisen, nicht
  als garantierten Beweis eines funktionierenden physischen Mikrofons.

**Desktop-Auswirkung:** Tray kann »verbunden und wartet auf Wake Word«, »pausiert«,
»nimmt auf« und zusätzlich »Ergebnis wird verarbeitet« korrekt kombinieren.
Feedback kann auf tatsächliche Zustandswechsel reagieren. Für eine ständig
animierte Mikrofonpegelanzeige kann der Windows-Client seine lokal verfügbaren
Audiodaten nutzen; ein neuer serverseitiger Pegel-/Idle-VAD-Dienst ist nicht Teil
dieses Plans.

**Abnahme:** Wake-Idle ohne Activation, manuelle Aufnahme, VAD-Ende, Hintergrund-
Final bei neuer Aufnahme, Audiopause und Audioverlust prüfen. Snapshot und zuletzt
bestätigter Audiozustand stimmen überein; unbekannte Aktivität wird nicht als
Stille dargestellt. Kein Recorderstatus kann eine terminale Session reaktivieren.

**Code:** [server.py](../../../api_fastapi_server/server.py), `publish_status`
3082–3117, Session-`snapshot` 4590–4632, VAD-Callbacks 5553–5579;
[recording.py](../../../VoiceSTT/core/recording.py), Gate/VAD-Pfad um 331–341;
[activation_control.py](../../../VoiceSTT/core/activation_control.py),
`recording_activation_gate_is_open` 191–226;
[snapshot.py](../../../api_fastapi_server/protocol_v2/snapshot.py).

## 8. Punkt 5 – Audiopause und Fortsetzung derselben Session

### Ist-Verhalten

**NACHGEWIESEN:** `_activate_session()` öffnet mit dem erfolgreichen Handshake
automatisch den Audiopfad. Der Kommentar bezeichnet dies ausdrücklich als Teil
der zugelassenen Session ohne separaten V2-Startbefehl. Das ist beabsichtigtes
Bootstrap-Verhalten; daraus folgt noch keine belegte Entscheidung gegen jede
spätere Pause.

V2 hat keinen Pause-/Resume-Command. `audio_availability.set(false)` meldet fehlende
Audioverfügbarkeit und storniert die offene Activation, lässt ältere Hintergrund-
Arbeit aber bestehen. `ingest_audio_packet()` prüft `streaming`, nicht
`_audio_available`. Dieser Command ist deshalb keine serverseitige Ingest-Sperre.
Einfach keine Pakete mehr zu senden hält die Session offen; die Recorderqueue
wartet weiter und Activation-Timer laufen unabhängig davon weiter. Ohne Samples
wird keine zusätzliche VAD-Stille gemessen.

### Soll und Umsetzung

Arbeitsname: `audio_stream.set` mit booleschem `enabled`. Der automatische Start
beim Handshake bleibt erhalten. Der neue Zustand wird im Snapshot abgebildet.

- `enabled=false`: sofort keine neue Audioannahme/Wake-Erkennung mehr; offene
  Eingabe geordnet wie `finish` schließen. Bereits angenommene Segmente dürfen
  regulär ihre Finals liefern. Restpuffer dürfen nach der Pause nicht als neue
  Aufnahme oder Wake-Erkennung wieder auftauchen.
- `enabled=true`: Audioannahme wieder ermöglichen, neue Lifecycle-Epoche starten
  und zum Trigger-Warten zurückkehren. Keine alte Activation wiederbeleben und
  nicht allein durch Resume ein neues Diktat eröffnen.
- Pause und Resume müssen gegen Recordercallbacks, Reset und Wake-Kandidaten
  serialisiert werden. Ein Resume während noch unsicherem Input-Close darf nicht
  vorzeitig den alten Eingabepfad öffnen.
- `audioAvailable` bleibt eine unabhängige Clientmeldung. Resume setzt einen
  gemeldeten Geräteausfall nicht automatisch zurück. Trigger-Suppression bleibt
  ebenfalls unabhängig erhalten.
- Wiederholungen sind idempotent. Audiopakete während der Pause werden verworfen
  und diagnostisch gezählt; nicht für später sammeln.

Die bestehende Legacy-`stop_streaming()` enthält nützliche Bereinigung, setzt auf
dem V2-Branch aber ausdrücklich `requested_terminal="cancelled"` und
`cancel_pending=True` für die geschlossene Activation. Das entspricht nicht der
hier vorgeschlagenen Finish-Semantik einer Pause. Auch deshalb ist sie kein
ungeprüft direkt weiterzureichender Adapter. Der gemeinsame sichere Input-Close
soll die Autorität bleiben.

**Desktop-Auswirkung:** »Mikrofon pausieren« beendet die serverseitige
Audioverarbeitung ohne neue Session. PTT verwendet weiterhin Activate/Finish;
ein bloßes Loslassen mit anschließend fehlenden Paketen ersetzt Finish nicht.
Für »Aufnahme verwerfen und pausieren« sind Reset und Pause kombinierbar, mit
definierter Command-Reihenfolge. Die Pause selbst bedeutet nicht automatisch
Verwerfen eines bereits gesprochenen Diktats.

**Abnahme:** Pause während Wake-Idle, aktiver Aufnahme und Hintergrundverarbeitung;
Resume nach beliebig langer Pause; alte Wake-/Recordercallbacks; parallel
Geräteausfall und Reset; mehrfach dieselbe `commandId`. Nach bestätigter Pause
keine neue Aufnahme, nach Resume nur neuer Trigger. Kein veraltetes Audio wird
nachgeholt.

**Code:** [connection.py](../../../api_fastapi_server/protocol_v2/connection.py),
307–343; [schema.py](../../../api_fastapi_server/protocol_v2/schema.py), 44–57;
[server.py](../../../api_fastapi_server/server.py), `start_streaming`/`stop_streaming`
2837–2874, `ingest_audio_packet` 2991–3022, Verfügbarkeitscommand ab 3710,
gemeinsamer Input-Close ab 4031; [recording.py](../../../VoiceSTT/core/recording.py),
Queue-Warten 158–175. Bestehende Epochentests:
[test_server_controlled_e2e.py](../../../tests/unit/test_server_controlled_e2e.py),
`LifecycleEpochEndToEndTests`.

## 9. Punkt 6 – Segmentmetadaten aus der vorhandenen Timeline

### Ist-Verhalten

**NACHGEWIESEN:** `SegmentTimelineTracker` ermittelt Aufnahmebeginn/-ende, Dauer,
Endgrund und Pre-Recording-Buffer-Angaben, einschließlich der Unterscheidung
zwischen tatsächlicher und lediglich konfigurierter Preroll-Dauer. Die V1-
Finalnachricht erhält diese Daten durch `segment_text_fields()`. Die V2-Builder
für Recording-Start/-Ende, Accepted und Completed projizieren im Wesentlichen
Identitäten, Grund und Text; der mitgeführte Segment-Snapshot wird nicht als
gleichwertiger Metadatensatz übertragen.

### Soll und Umsetzung

- Einen begrenzten optionalen `segment`-Metadatenblock definieren und an den
  passenden Recording-/Finalevents aus dem bereits existierenden Tracker füllen.
- Mindestumfang: Aufnahmebeginn, Aufnahmeende, Dauer, fachlicher Endgrund und
  Preroll-Information mit ihrer Genauigkeitskennzeichnung. Einheitliche
  Zeit-/Dauereinheiten festlegen; weder ISO- noch Unix-Duplikate sind zwingend.
- Fehlende Werte bleiben fehlend/null gemäß Vertrag. Keine Millisekundengenauigkeit
  behaupten, die die Quelle nicht liefert. `occurredAtUnixMs` ist der
  Ereigniszeitpunkt und ersetzt nicht den Aufnahmebeginn.
- Für ältere Hintergrundsegmente deren gespeicherte Timeline verwenden, nicht
  die aktuelle Aufnahme. Reset darf keine Metadaten eines neuen Segments mit
  einem alten Ergebnis kombinieren.
- Keine Änderung an Wake-Modellen/Katalogen; Wake-Zuordnung nur soweit für die
  schon vorhandene Activation-/Segmentkorrelation erforderlich.

**Desktop-Auswirkung:** Der Client kann Dauer und zeitliche Einordnung eines
Diktats korrekt anzeigen und ungewollt abgeschnittene/erzwungen beendete Aufnahmen
erklären, ohne aus Netzwerkempfangszeiten eine unzuverlässige Dauer zu errechnen.

**Abnahme:** Normales Segment, tatsächlicher Preroll, nur geschätzter Preroll,
erzwungenes Ende, verspäteter Final nach neuer Activation. Prüfen, dass alte
Clients fehlende optionale Felder und neue Clients unbekannte optionale Felder
robust behandeln. Nicht das gesamte interne Timelineobjekt unkontrolliert zum
öffentlichen Vertrag machen.

**Code:** [server.py](../../../api_fastapi_server/server.py), `segment_text_fields`
1377–1391, `SegmentTimelineTracker` ab 1394, `mark_recording_started` ab 1462,
`_publish_ordered_final` 4782–4815;
[events.py](../../../api_fastapi_server/protocol_v2/events.py), Builder 282–336.
Testansatz: [test_protocol_v2_e2e.py](../../../tests/unit/test_protocol_v2_e2e.py),
`test_segment_lifecycle_events_carry_the_frozen_segment_fields`.

## 10. Punkt 7 – Interim-Gültigkeit und begrenzte ausgehende Puffer

### Ist-Verhalten: drei unterschiedliche Probleme

**A. Späte Vorschau. NACHGEWIESEN:** Der V2-Projektor unterdrückt Interims nach
einem Segmentterminal nicht selbst. Eine speicherbasierte Probe mit dem echten
Projektor erzeugte nacheinander `transcription.completed` und
`transcription.interim` für dasselbe Segment. Die aktive Clientregel »erstes
Terminal gewinnt; danach keine Vorschau anzeigen« ist deshalb weiterhin nötig.
Die Probe belegt die Adapterfähigkeit, nicht die Häufigkeit eines solchen
Callbacks im Livebetrieb.

**B. Wechsel der Aufnahme während Realtime-Inferenz. NACHGEWIESENER riskanter
Pfad, PLAUSIBLES Rennen:** Der Realtime-Worker nimmt Frames und `recording_id`
vor der Inferenz auf, liest Teile des Aufnahmezeitkontexts erst danach und prüft
beim Publizieren lediglich, ob gerade eine Aufnahme läuft. Die Observation setzt
keine `segment_id`. Der Stabilizer erkennt unter anderem `wrong-recording` und
`finalized`, aber der strukturierte Callback wird nicht ausschließlich für
`accepted/should_publish` aufgerufen. Der Server kann ohne explizite Segment-ID
auf `segment_state.realtime()` zurückfallen. Somit ist ein alter Befund während
einer neuen Aufnahme separat zu prüfen. Ein durchgängig nachgewiesener realer
Modell-Race liegt bislang nicht vor. Nicht pauschal alle `accepted=false`-
Diagnosen verwerfen: Outlier-/Stabilisierungsinformationen können absichtlich
Teil einer zulässigen Vorschau sein.

**C. Langsamer Client. NACHGEWIESENE fehlende Begrenzung, PLAUSIBLES
Betriebsrisiko:** Der produktive Endpoint erzeugt `asyncio.Queue()` ohne
Maximalgröße. Jeder Sink-Aufruf plant über `call_soon_threadsafe` ein
`put_nowait`; der Writer wartet auf `send_text`. Bei dauerhaft schnellerem
Produzenten kann sich die Warteschlange vergrößern. Auch geplante Loop-Callbacks
sind zu berücksichtigen. Bei Sendefehler kehrt der Writer zurück, ohne selbst die
Receive-Schleife zu beenden. Ein gemessener Speicherüberlauf liegt nicht vor.

Zusätzlich halten `EventProjector._segments` und `ProtocolSessionState._minted`
Identitäten während der Session vor. Ein genereller Terminal-Cleanup ist dort
nicht sichtbar. Bei vielen Diktaten in einer sehr langen Session ist deren
Wachstum mitzuprüfen. Reines Wake-Idle ohne erzeugte Segmentevents ist davon zu
unterscheiden.

### Soll und Umsetzung

- Jede Realtime-Arbeit bindet schon bei ihrer Entstehung Recording-ID, Segment-
  Kontext und Generation. Vor Veröffentlichung Identität und Terminalstatus
  erneut prüfen; alte Ergebnisse niemals der neuen Aufnahme zuordnen.
- Serverseitig bekannte terminale/verworfene Segmente erzeugen keine neue
  Vorschau mehr. Clientseitiges First-Terminal-Wins bleibt als Schutz gegen
  bereits unterwegs befindliche Nachrichten bestehen.
- Den gesamten Weg vom Producer zum Socket begrenzen: Anzahl/Bytes wartender
  Nachrichten und geplante Zustellungen, plus begrenzte Sendewartezeit. Eine
  kleine `asyncio.Queue(maxsize=…)` allein löst ungebremstes Scheduling nicht.
- Vorschauen vor Vergabe endgültiger Eventidentitäten zusammenfassen. Je Segment
  genügt die neueste vollständige Vorschau. Bereits mit `eventSeq` nummerierte
  Events nicht stillschweigend löschen: Der Client würde Sequenzlücken erkennen,
  und ein Snapshot kann verlorenen Text nicht reparieren.
- Bei Coalescing vollständige `text`/Stabilitätsstände erhalten. Deltas wie
  `stableDelta` nicht versehentlich zum einzigen erforderlichen Wiederaufbaupfad
  machen; deren Semantik bei übersprungenen Beobachtungen ausdrücklich festlegen.
- Acks, Snapshots, Final-/Terminal- und wesentliche Lifecycleevents nicht wie
  ersetzbare Vorschau behandeln. Kann die Verbindung diese nicht innerhalb des
  begrenzten Budgets zustellen, ausdrücklich beenden und Ressourcen freigeben.
  Ohne die ausgeschlossene Ergebnisgarantie kann ein Client dabei ein Final
  verpassen; Logs bleiben separate Diagnose, kein garantierter Ersatztransport.
- Identitäts-/Terminalwissen nur mit einer geprüften Retentionsregel bereinigen:
  monotone Generationen/Sequenzen oder begrenzte Historie dürfen keine alten
  Callbacks wieder zulassen und keine zugesagte Retry-Identität zerstören.

**Desktop-Auswirkung:** Kein alter Vorschautext in einem neuen Diktat; kurzzeitige
UI-Verzögerungen führen nicht zu unbegrenzt wachsendem Serverspeicher. Ein
dauerhaft zu langsamer Client erhält einen eindeutigen Verbindungsabbruch.

**Abnahme:** Verzögerte alte Inferenz bei neuer Recording-ID; Interim nach Final,
Cancel und Reset; Produzent über längere Zeit schneller als künstlich blockierter
Socket; Writer-Exception bei wartendem Receive. Speicher/Pufferzahl müssen nach
definiertem Budget begrenzt bleiben. Reihenfolge, `eventSeq`, `stateVersion`,
Final-/Terminalzustellung innerhalb des Budgets und Close außerhalb des Budgets
prüfen. Viele aufeinanderfolgende Activations auf Cachewachstum untersuchen.

**Code:** [realtime.py](../../../VoiceSTT/core/realtime.py), 529–614, 658–708;
[realtime_text_stabilizer.py](../../../VoiceSTT/core/realtime_text_stabilizer.py),
`observe` 291–313, `_ignored_event` 531–574;
[server.py](../../../api_fastapi_server/server.py), strukturierter Callback
4905–4965 und Endpoint 9783–9854;
[events.py](../../../api_fastapi_server/protocol_v2/events.py), `project` 108–138,
Interim-Builder 295–329;
[session.py](../../../api_fastapi_server/protocol_v2/session.py), 48–53, 105–155;
[schema.py](../../../api_fastapi_server/protocol_v2/schema.py), `NON_STATE_EVENTS`
189–197. Vorhandene [Race-Tests](../../../tests/unit/test_protocol_v2_races.py)
prüfen unter anderem Dispatch-Reihenfolge und lückenlose Nummerierung; sie
ersetzen keinen Test des langsamen produktiven WebSocket-Writers.

## 11. Punkt 8 – Bestehendes Wake-Warten und Final-Logging absichern

### Wake Word: bereits vorgesehener Normalfall

**NACHGEWIESEN, auch historisch:** Schon `activation.py` in Commit `3262079`
(AP-SRV-010) initialisiert und beendet eine Activation mit `IDLE` und
`_deadline = None`. Im aktuellen Code gilt das weiter. Erst `activate()` setzt
`WAITING_FIRST_SPEECH` mit Frist; danach betreffen Followup-/Watchdog-/Recovery-
Timer eine konkrete Activation. Ohne Deadline wird kein Activation-Timer
gestartet. Der V2-Handshake-Timeout gilt vor Annahme, nicht als Idle-Timeout für
eine angenommene Session.

Der Recording-Worker verarbeitet fortlaufend eintreffende Samples. Ohne offene
Aufnahme und ohne Wake-Latch wird bei freigegebener Erkennung wiederholt der
Wake-Detektor aufgerufen. Nach dem sicheren Input-Close löst der gemeinsame
`activation_closed`-Pfad den Latch der zugehörigen Activation. Final-Inferenz und
deren Ende sind hierfür nicht die Freigabeautorität.

Die Aussage »von Anfang an« ist damit für die frühe V2-State-Machine belegt;
eine Aussage über jede noch frühere Planungsabsicht ist dafür nicht nötig.
Erforderliche Betriebsbedingungen bleiben: intakte Verbindung, weiterhin Audio,
wirksamer Wake-Trigger, verfügbare Erkennung und keine Pause/Suppression.

STT-Modelle können während langer Ruhe automatisch entladen werden. Der
Modell-Idle-Worker beendet dadurch nicht die Session; die nächste Job-Einreichung
geht über `ensure_models_loaded()`. Das Wiederanlaufen kann Latenz verursachen
und muss im Dauerbetriebstest enthalten sein. Wake-Erkennung im Recorder und
Scheduler-Modelllebenszyklus dürfen nicht gleichgesetzt werden.

### Finals: bereits vorhandenes Logging

`_publish_ordered_final()` erzeugt `transcription.completed` mit `text`, Session-,
Activation-, Segment- und Request-Korrelation. `sanitize_event_value()` lässt
Finaltext bei `transcript_mode=final` und `full` zu, bei `none` nicht. Die öffentliche
Servereinstellung heißt `transcript_log_mode`; `transcript_mode` ist der daraus
abgeleitete interne Wert des Eventloggers. Die
Kanal-`enabled`-Schalter betreffen laut Implementierung optionale JSONL-/stdout-
Spiegel; ein deaktivierter Spiegel beweist daher nicht, dass der kanonische
SQLite-Eintrag fehlt. Ein fehlerhafter Eventstore kann die Speicherung dennoch
verhindern und wird als degraded behandelt.

AP-SRV-080 liefert `hello.accepted.logAccess`. History und `/ws/logs` verwenden
dieselben Sessionrechte. `eventId`/Cursor der Logs sind ein eigener Vertrag und
kein Replay der nummerierten V2-Domainevents. Der V2-Snapshot enthält weder
Finaltextarchiv noch vollständige Liste aller abgeschlossenen Activations;
terminale Ledger-Einträge werden entfernt.

### Soll, Grenzen und Abnahme

- Kein neuer triggerloser Betriebsmodus und kein neuer Ergebnisnachladedienst.
- Finaltexte im normalen Betrieb mit Policy `final` oder `full` und gesundem
  Eventstore speichern. Die bewusste Datenschutzoption `none` nicht heimlich
  umgehen; für einen Betrieb mit gewünschtem Textlog nicht `none` konfigurieren.
- Wake-Idle hat keine neue fachliche Ablaufzeit. Langlaufprüfung mit
  anhaltenden Audiosamples ohne Treffer, anschließendem Wake Word, Diktat,
  erfolgreichem Final und erneuter Wake-Bereitschaft durchführen. Mindestens
  mehrere Stunden und über die konfigurierte STT-Modell-Idle-Frist hinaus testen.
- Simulator-/Uhrtests für Timerlogik mit realem Audio-/Modell-Dauerlauf ergänzen;
  ein schnell abgespielter Fake-Sample-Test beweist keinen Stundenbetrieb.
- Final-Logging bei `final`, `full`, `none`, deaktivierten Spiegeln und
  Eventstorefehler prüfen. HTTP-Historie und Log-WebSocket müssen dieselbe
  Sessionisolation zeigen. Logs dürfen nicht als erfolgreiche Diktatzustellung
  an den Client gewertet werden.

**Bekannte Betriebsgrenze:** Logtokens laufen derzeit nach 24 Stunden ab; eine
neue HTTP-/WS-Logautorisierung mit abgelaufenem Token scheitert. Das begrenzt nicht
die Wake-Session oder das Schreiben von Final-Logs. Falls ein Client über Tage
ohne neue Session zusätzlich jederzeit seinen Logstream neu authentifizieren
können soll, wäre Token-Erneuerung eine gesonderte Ergänzung. Die Forderung
»Finaltexte normal loggen« allein verlangt diesen Ausbau nicht.

**Code:** [activation.py](../../../api_fastapi_server/activation.py), 245–263,
`activate` 464–510, `tick` 746–798, `_clear_locked` ab 829;
[server.py](../../../api_fastapi_server/server.py), Timer 4359–4386,
Wake-Admission 2581–2653, Latch-Release 2692–2706 und 5737–5744,
Final-Logging 4842–4858, Modell-Lifecycle 6533–6605/6644–6745,
Logtoken 6879–6937;
[recording.py](../../../VoiceSTT/core/recording.py), Worker ab 119,
Wakepfad 228–316, Legacy-Timeout-Abgrenzung 582–597;
[event_logging.py](../../../VoiceSTT_server/event_logging.py), 116–155, 916–980;
[segment_ledger.py](../../../api_fastapi_server/segment_ledger.py), 549–552.
Vorhandene Tests: [Wake-Admission](../../../tests/unit/test_wake_admission.py),
`LatchLifecycleTests`; [Recording-Pfad](../../../tests/unit/test_wakeword_recording_path.py),
`test_a_latched_detector_is_not_released_by_the_legacy_timeout`;
[Wake-Session-E2E](../../../tests/unit/test_wakeword_session_e2e.py),
`test_the_latch_is_released_at_the_safe_input_close`.

## 12. Punkt 9 – Vertrag, Dokumentation und Regressionen abschließen

### Nachgewiesene Widersprüche am geprüften Stand

1. Die historische [V1→V2-Migrationsmatrix](../../audits/v2-client-contract/V1_TO_V2_CLIENT_MIGRATION_MATRIX.md)
   ist auf Baseline `f7d2b3ccd07757172a45b371829b04bcedffab4b` bezogen. Sie nennt
   noch 17 Events, keine Zwischentexte und keinen V2-Session-Logtoken. Nach
   AP-SRV-080 ist das als Beschreibung des aktuellen V2 falsch. Die Matrix soll
   historisch bleiben; problematisch sind unqualifizierte Verweise aus der
   aktuellen [Client-Übersicht](../../client-development/README.md) und
   [Protokollabgrenzung](../../client-development/08-protokollabgrenzung.md).
2. [HTTP/API-Dokumentation](../../client-development/06-http-api-und-authentifizierung.md),
   Zeile 42, nennt für `/ws/logs` nur V1-Sessiontoken, während ab Zeile 91 V2
   korrekt berücksichtigt wird.
3. [Client-Zustandsmodell](../../client-development/05-client-zustandsmodell.md),
   Zeilen 158–159, behauptet, der Snapshot zeige nach verlorenem
   Transkriptionsevent noch die terminale Activation. Vollständig drainierte
   Activations werden aber aus dem Ledger entfernt. Ein aktueller Snapshot ist
   kein Terminalarchiv. Die kategorische Nichtwiederherstellbarkeit von Text
   muss zugleich von möglicher manueller/diagnostischer Suche in aufbewahrten
   Logs unterschieden werden; garantiertes Ergebnis-Replay bleibt ausgeschlossen.

### Soll und Umsetzung

- Aktive Referenzen, Schemas, Parser, Eventbuilder, Snapshot, Resultcodes und
  [Contract-Vektoren](../../../tests/contracts/protocol-v2-vectors.json) gemeinsam
  aktualisieren. Neue Commands/Events nicht bloß in Prosa ankündigen.
- Neue Wire-Namen in diesem Plan sind Arbeitsnamen. Vor Implementierung die
  endgültigen Feldnamen, Nullbarkeit, Zeit-/Dauereinheiten, Fehlercodes,
  Command-Replay-Regeln und Erweiterungsverhandlung festschreiben. Erweiterungen
  müssen für Clients eindeutig erkennbar sein; strikt eingefrorene Validatoren
  nicht unangekündigt anders auslegen.
- Historische Audits in `docs/audits/v2-client-contract/` und
  `docs/audits/v2-client-contract-review/` auf ihrer Baseline belassen. Aktuelle
  Einstiegspunkte ausdrücklich auf die heutigen Regeln und AP-SRV-080 bzw. die
  nachfolgende Umsetzung verweisen lassen. Auch
  [Architekturübersicht](../../einheitliche-triggerarchitektur.md) angleichen.
- Reset, Pause, Geräteverfügbarkeit und Trigger-Suppression getrennt erklären.
  Domainphase, Audioaktivität und Diagnose nicht wieder zu einem mehrdeutigen
  Statusfeld vermischen. Snapshots, Log-Replay und Domain-Replay klar abgrenzen.
- Regressionsfälle aus Punkten 1–8 als echte Verhaltenstests ergänzen. Danach
  gesamten vorgesehenen Testumfang des Repositorys ausführen; Probleme iterativ
  beheben. Modell-/Hardware-/Dauerlaufprüfungen zusätzlich ausweisen, statt aus
  Unit-Tests uneingeschränkte Betriebsfreigabe abzuleiten.
- Gemäß Archivprozess später separaten datierten Soll-/Ist-Vergleich und bei
  materiellen Abweichungen eine eigene Begründung anlegen. Erst dann den
  Registerstatus entsprechend ändern. Dieses Planungsdokument ist keine Abnahme.

**Abnahme:** Ein Cliententwickler kann allein mit aktueller Referenz und Vektoren
einen konsistenten Reducer sowie Reset/Pause/Diagnose implementieren. Jeder neue
Wire-Typ ist im echten V2-Endpoint erreichbar und getestet. Kein historischer
Vor-AP-SRV-080-Befund wird als aktuelle Funktionsgrenze präsentiert.

## 13. Umsetzungsreihenfolge und bewusste Nicht-Ziele

1. **Verhalten absichern:** Punkt 1 reproduzierbar in Regressionstests aufnehmen;
   in Punkt 7 Produzenten-/Transportgrenzen und Identitäten klären. Diese beiden
   Punkte verhindern widersprüchliche Clientdaten und unkontrolliertes Wachstum.
2. **Sessionsteuerung festlegen und ergänzen:** Punkt 2 und 5 zusammen planen,
   weil Reset, Pause und Input-Close dieselben Lifecycle-Grenzen berühren.
   Vorhandene genau-einmal-Abschlüsse und Generationen weiterverwenden.
3. **Beobachtbarkeit ergänzen:** Punkt 3 und 4 mit gemeinsamem, kleinem
   Snapshot-/Diagnosevertrag; Metadaten aus Punkt 6 im selben Vertragsdurchgang.
4. **Betriebsfälle absichern:** Punkt 8 einschließlich Modell-Wiederanlauf und
   tatsächlicher Final-Log-Speicherung. Keine neue Daueraufnahmefunktion bauen.
5. **Clientvertrag freigeben:** Punkt 9 abschließen, vollständige Regression plus
   gezielte E2E-/Race-/Last-/Dauerprüfungen durchführen und Ist-Stand dokumentieren.

Bewusst nicht aufgenommen werden ein triggerloser kontinuierlicher Diktatmodus,
persistente Ergebniszustellung mit Acknowledgements/Nachladegarantie, Session-
Resume, Domain-Event-Replay, neue Wake-Modelle/Katalogpolitik und die bloße
Wiedereinführung alter Nachrichtennamen. Transport-Ping/Pong, HTTP-Metriken und
Health müssen nicht aus Namenskompatibilität erneut als V1-JSON-Kommandos
implementiert werden. Ein zusätzliches Readiness-Pushsignal wäre eine eigene
Komfortentscheidung, keine Voraussetzung für die neun hier festgelegten Punkte.

Die beiden zuvor als groß eingeordneten Erweiterungen – triggerloser Dauerbetrieb
und garantierte Ergebnisrekonstruktion – entfallen aufgrund der fachlichen
Entscheidung. Die vorhandenen Grundlagen reichen für die verbleibenden Aufgaben
aus; keiner der neun Punkte verlangt erkennbar ein neues Gesamtsystem. Das
bedeutet bei den Nebenläufigkeitsarbeiten ausdrücklich nicht, dass ein einfacher
Transportalias oder ein zusätzlicher Eventbuilder bereits eine korrekte Lösung
wäre.
