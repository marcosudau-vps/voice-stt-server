# Nachprüfung und Abweichungen zu Commit b99b71b

> **Status:** In Umsetzung
> **Datum:** 2. August 2026
> **Geprüfter Branch:** `feature/sqlite-first-admin-eventstream`
> **Geprüfter Commit:** `b99b71b18756f7073d9179f67baf9f9f8f2de88a`
> **Veröffentlichung:** nicht erfolgt

## Anlass

Eine externe Nachprüfung des ersten Korrekturcommits hat zwei weitere
funktionale Abweichungen innerhalb des lokalen AP07-S1-/AP07-S2-Umfangs sowie
eine fehlerhafte Fortschreibung bereits archivierter Originaldokumente
festgestellt. Diese Datei dokumentiert die spätere Einordnung regelkonform,
ohne die ursprüngliche Planung oder den ursprünglichen Soll-/Ist-Bericht
inhaltlich umzuschreiben.

## Abweichung 1: Performance-Quellschalter

### Feststellung

`performance_logging_enabled=false` unterdrückt im geprüften Commit die
Erzeugung von Performanceevents nicht. Bereits erzeugte Performanceevents
werden weiterhin in SQLite gespeichert.

### Ursache

Der erste Korrekturcommit entfernte die Channel-Enable-Prüfung allgemein aus
`StructuredEventHub.emit()`, um optionale Spiegel von der kanonischen
Persistenz zu entkoppeln. Dabei wurde nicht zwischen dem fachlichen
Performance-Quellschalter und einem Spiegel-Schalter unterschieden.

### Auswirkung

AP07-S1 Abschnitt 4.4 ist nicht erfüllt: deaktivierte Performanceevents werden
trotzdem erzeugt und belasten Store sowie Eventstream.

### Handlungsbedarf

- `performance_logging_enabled` muss die Performancequelle vor dem EventHub
  deaktivieren.
- Die optionale Performance-Dateispiegelung erhält eine getrennte
  Konfiguration.
- Ein bereits erzeugtes Performanceevent bleibt unabhängig vom Spiegelzustand
  SQLite-first.
- Servicepfad, Laufzeitänderung und Spiegeltrennung werden getestet.

## Abweichung 2: Duplicate Empty-Final im Textworker

### Feststellung

Zwei leere Resultate im echten `_text_worker` werden im geprüften Commit als
zwei Terminalereignisse für synthetisch aufeinanderfolgende Segment-IDs
verarbeitet.

### Ursache

Der Worker liest vor jedem blockierenden `recorder.text()` lediglich die
aktuelle Segment-ID. Nach dem ersten Terminalereignis ist diese bereits erhöht;
ein dupliziertes Resultat erscheint dadurch fälschlich als Ergebnis eines neuen
Segments.

### Auswirkung

AP07-S2 Abschnitt 5.4 ist nicht erfüllt: ein Segment kann durch ein dupliziertes
Recorderresultat eine zweite synthetische Terminalisierung verursachen.

### Handlungsbedarf

- Der Recorder-Callback für den tatsächlichen Transkriptionsstart muss ein
  generation-/segmentgebundenes Ergebnisticket erzeugen.
- Der Textworker darf ein Resultat nur mit einem solchen Ticket verarbeiten.
- Ein weiteres Resultat ohne neuen Transkriptionsstart wird verworfen.
- Der Fall wird über den tatsächlich laufenden Worker integriert getestet.

## Abweichung 3: Archivfortschreibung

### Feststellung

Commit `b99b71b` änderte die bereits archivierten Originaldateien
`2026-08-02_SQLITE_FIRST_ADMIN_EVENTSTREAM_PLAN.md` und
`2026-08-02_SQLITE_FIRST_ADMIN_EVENTSTREAM_UMSETZUNGSVERGLEICH.md`
nachträglich.

### Korrektur

Beide Originaldateien werden inhaltlich auf den Stand von Commit `28035dd`
zurückgeführt. Die spätere Prüfung und sämtliche Abweichungen werden
ausschließlich in dieser neuen datierten Datei fortgeschrieben. Das zentrale
Register bleibt bis zum erfolgreichen Abschluss der Nachbesserung auf
`In Umsetzung`.

## Abnahmestatus

- AP07-S1: wegen Abweichung 1 noch nicht abnahmefähig.
- AP07-S2 Abschnitte 5.1 bis 5.5: wegen Abweichung 2 noch nicht abnahmefähig.
- AP07-S2 Abschnitt 5.6: auftragsgemäß nicht ausgeführt und nicht bewertet.
- Livefreigabe: nicht erteilt.

Die Datei wird nach Implementierung und erneuter technischer Prüfung durch eine
weitere datierte Nachprüfungsdatei abgeschlossen. Ihr historischer Inhalt wird
danach nicht umgeschrieben.
