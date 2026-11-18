# Voice-STT-V2 – lokaler Dokumentationsarbeitsplatz

**Stand:** 104/104 Kapitel intern abgenommen und integriert (Pilot 02.03 extern ROOT-abgenommen, übrige 103 intern PASS); externe ROOT-Endfreigabe des Gesamtlaufs ausstehend.

- [Verbindliche Spezifikation](SPEZIFIKATION_v0.2.md)
- [Komplette Gliederung mit 104 Kapiteln](GLIEDERUNG.md)
- [Vorbereitete Dokumentationsdateien](docs/v2-handbuch/README.md)
- [Fortschrittsanzeige mit 104 abhakbaren Kapiteln](workflow/PROGRESS.md)
- [Task-Registry](workflow/task-registry.json)
- [Diagrammideen](workflow/diagram-briefs.json)
- [Arbeitsakten und Statusverfahren](workflow/README.md)
- [OpenCode-Einrichtung](OPEN_CODE_EINRICHTUNG.md)
- [Gesamtstartauftrag für OpenChamber (103 offene Kapitel)](START_GESAMTLAUF.md)
- [Historische Startnachricht für den abgeschlossenen Pilot 02.03](START_PILOT_02.03.md)
- [Pilot Activation](workflow/pilot/02.03-activation.md)

## Eigene Ergänzungen

Jedes Unterkapitel besitzt workflow/notes/<ID>.md. Dort kannst du Wünsche, Beispiele, mögliche Schaubilder und erläuterungsbedürftige Punkte frei ergänzen.
Für 43 ausgewählte Kapitel gibt es zusätzliche workflow/diagram-notes/<ID>.md mit konkreten Visualisierungsvorschlägen.

## Status prüfen

Im lokalen Ordner: python tools/workflow_cli.py validate

Danach: python tools/workflow_cli.py status

Der Activation-Pilot ist abgeschlossen; `workflow/reviews/02.03-ROOT-FINAL-2026-11-06.md` hält die externe Abnahme fest. Dieser Dokumentationsarbeitsplatz ist vom Produkt-Repository getrennt. Kein automatischer Git-Merge, Push oder Release.
