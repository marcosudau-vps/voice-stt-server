# Arbeitsakten und Statuspflege

**Einzige Statusautorität:** task-registry.json. coverage-matrix.json wird daraus mit tools/workflow_cli.py refresh neu erzeugt.

**Fortschrittsanzeige:** [PROGRESS.md](PROGRESS.md) zeigt alle 104 Kapitel als automatisch abhakenbare Checkliste mit Status, Übersicht und prozentualem Fortschritt. Bei jedem kontrollierten Statuswechsel und bei `python tools/workflow_cli.py refresh` wird sie neu erstellt. Sie ist eine Ansicht, keine Statusautorität. Der Orchestrator muss nach jedem Kapitel und nach jeder Arbeitscharge die Registry aktualisieren und `refresh`/`validate` ausführen.

Die Dateien unter notes/ gehören dem Auftraggeber und dürfen vor und während der Arbeit ergänzt werden.
Die Dateien unter diagram-notes/ enthalten zunächst rein redaktionelle Visualisierungsideen.
Researcher nutzen NUR Implementierung, Schemas, Tests und echte Build-/CI-Konfigurationen; nie alte Dokumente.

Jede Faktenakte und jeder Review nennt den exakten Quell-Commit. Nie PLACEHOLDER als abgenommene technische Dokumentation ausgeben.

Status: PLANNED → RESEARCHED → DRAFTED → IN_REVIEW → ACCEPTED → INTEGRATED. Bei Fehlern CHANGES_REQUESTED, nach drei erfolglosen Runden ESCALATE.
