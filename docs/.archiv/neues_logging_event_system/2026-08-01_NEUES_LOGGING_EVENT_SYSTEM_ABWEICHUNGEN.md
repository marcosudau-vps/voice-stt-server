# Abweichungen: neues Logging- und Event-System

Erstellt am 01.08.2026 als separate Ergänzung zum
[Soll-/Ist-Vergleich](2026-08-01_logging-projekt-live-stand.md) und zur
[ursprünglichen Planung](2026-07-30_LOGGING_EVENT_SYSTEM.md).

## 1. Sink-spezifische `log.gap`-Meldung bei gleichzeitiger Überlast

**Plan:** Verluste jedes Sinks sollten als `log.gap` sichtbar sein, ohne den
Emit-Pfad zu blockieren.

**Ist:** Der Emit-Pfad bleibt nichtblockierend und die Verlustzähler erkennen
Überlast. Bei einer extrem kleinen Queue und gleichzeitiger Überlast mehrerer
Sinks kann die ebenfalls begrenzte Control-Queue jedoch einen bereits
eingereihten Gap-Hinweis behalten und einen weiteren sink-spezifischen Hinweis
verwerfen. Dadurch bleibt der Gesamtverlust sichtbar, aber nicht zwingend jeder
betroffene Sink einzeln.

**Grund:** Die Control-Queue wurde bewusst begrenzt, damit auch die
Fehlerberichterstattung selbst keinen Rückstau in der Audio- und
Transkriptionsverarbeitung erzeugt. Die aktuelle Deduplizierungs- und
Kapazitätslogik garantiert dabei keine Meldung pro Sink.

**Auswirkung:** Diagnoseinformationen können im gleichzeitigen
Mehrfachüberlastungsfall unvollständig sein. Normale Eventverarbeitung,
Persistenz und Cursorvergabe bleiben davon unberührt.

**Status:** Offener technischer Nachbesserungspunkt. Der zugehörige Gruppentest
ist zeitabhängig; isoliert besteht er.

## 2. Leeres finales WebSocket-Ergebnis ohne terminales Event

**Plan:** Pro finalem WebSocket-Segment sollte ein zusammenfassendes
Erfolgs- oder Fehlerereignis entstehen.

**Ist:** Liefert der Recorder ein leeres finales Ergebnis, wird dieses Ergebnis
übersprungen. Für das Segment entsteht dann kein
`transcription.completed`, `transcription.failed` oder
`transcription.cancelled`.

**Grund:** Leere Ergebnisse wurden bisher nicht als fachlich erfolgreiche
Transkription behandelt und sollten keinen leeren finalen Clientblock
erzeugen. Eine eigene Ereigniskategorie für verworfene leere Segmente wurde
nicht eingeführt.

**Auswirkung:** In der strukturierten Historie ist für diesen Randfall kein
terminaler Transkriptionsstatus vorhanden.

**Status:** Offene fachliche Entscheidung. Eine spätere Lösung sollte entweder
ein ausdrückliches `transcription.discarded` einführen oder den vorhandenen
Lifecycle mit einem begründeten terminalen Ereignis schließen.
