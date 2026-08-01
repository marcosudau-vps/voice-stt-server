# Projektregeln für Agenten

Diese Regeln gelten für Arbeiten im gesamten Repository. Spezifischere
`AGENTS.md`-Dateien in Unterordnern können sie für ihren Bereich ergänzen.

## Größere Änderungsaktionen

Vor jeder größeren Änderung an Architektur, öffentlichen Protokollen oder APIs,
persistierten Datenformaten, Sicherheitsgrenzen, Deploymentstruktur oder
mehrere Module übergreifendem Verhalten ist der Prozess unter
[`docs/.archiv/README.md`](docs/.archiv/README.md) verpflichtend zu befolgen.

Insbesondere gilt:

1. Die Aktion vor der Umsetzung im zentralen Register eintragen.
2. Einen eigenen Aktionsordner unter `docs/.archiv/` anlegen.
3. Vor der Implementierung eine datierte Gesamtplanung erstellen.
4. Nach der Implementierung eine getrennte datierte Soll-/Ist-Prüfung gegen
   den tatsächlich veröffentlichten Stand erstellen.
5. Materielle Abweichungen in einer weiteren datierten Datei begründen.
6. Alle aktionsbezogenen Dateinamen mit `YYYY-MM-DD_` beginnen lassen.
7. Zusätzlich die dauerhaft gültige Fachdokumentation aktualisieren und Links
   prüfen; das Archiv ersetzt die aktuelle Dokumentation nicht.

Eine Aktion darf im Register erst dann als `Abgeschlossen` markiert werden,
wenn Umsetzung, Gegenprüfung, Abweichungsdokumentation und aktuelle
Fachdokumentation konsistent sind.

## Umgang mit dem Archiv

- Archivierte Planungen und historische Prüfberichte nicht stillschweigend an
  den aktuellen Stand umschreiben.
- Spätere Einordnungen als neue datierte Datei ergänzen.
- Keine Secrets, Zugangsdaten, erzeugten Logs oder Binärartefakte im Archiv
  ablegen.
- Verweise aus der aktuellen Dokumentation auf verschobene Archivdateien bei
  jeder Umstrukturierung aktualisieren.
