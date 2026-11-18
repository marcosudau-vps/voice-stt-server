# OpenCode V2: Vorbereitete Agenten

Auf diesem PC wurde OpenCode v2.2.5 festgestellt. Die vorbereiteten vier Agenten liegen projektlokal unter .opencode/agents/.

Modelle nach der tatsächlich verfügbaren Liste:

- Orchestrator & Reviewer: opencode-go/muse-spark-1.3-contributor
- Researcher & Writer: opencode-go/deepseek-v4.1-flash

**Achtung:** Das gewählte Modell der bereits geöffneten Hauptsession wird separat gespeichert. In einer **neuen OpenChamber-Session** `doc-orchestrator` als Agent und `opencode-go/muse-spark-1.3-contributor` als Hauptmodell auswählen; die drei Subagenten verwenden ihre jeweiligen Profilmodelle. Der Pilot `02.03 Activation` ist abgeschlossen (`ROOT_PASS`). Für den Gesamtlauf `START_GESAMTLAUF.md` verwenden und alle 103 übrigen Kapitel bearbeiten.

Die vier Agentenprofile wurden im Pilot erfolgreich geladen; getrennte Researcher-, Writer- und Reviewer-Sessions wurden nachgewiesen. Bei einem neuen Gesamtlauf trotzdem Modellzugriff, Berechtigungen und Worktree-Zugriff prüfen.

Achtung: Der Dokumentationsordner ist kein vollständiger Git-Quellcheckout. Die Produktquellen müssen als aktueller Git-Worktree auf feat/v2-release-cleanup explizit identifiziert und lesend eingebunden werden. Die Pfade aus workspaces/ dürfen nicht einfach als aktueller Stand vorausgesetzt werden.

Agentenprofile allein liefern keine harte Filesystem-Sandbox. Vor autonomer Bearbeitung Schreibzugriffe auf diesen Ordner begrenzen, keine produktiven Commits/Pushes zulassen und die Pilotrecherche separat testen.
