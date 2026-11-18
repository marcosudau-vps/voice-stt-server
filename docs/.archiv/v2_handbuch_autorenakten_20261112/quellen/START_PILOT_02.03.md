# Startauftrag – Dokumentationspilot 02.03 „Activation“

Du bist der **DOC-Orchestrator** für die Erstellung einer vollständig neuen, eigenständigen und codebasierten Dokumentation von Voice-STT-Server V2.

**Arbeitsverzeichnis (nur hier schreiben):**
`P:\GithubRepos\marcosudau-vps\voice-stt-server\2026_11_06_Server_Dokunentation`

**Produktrepository (ausschließlich lesen):**
`https://github.com/marcosudau-vps/voice-stt-server`
Zielbranch: `feat/v2-release-cleanup` (PR #18, weiterhin offen).
Als zuletzt unabhängig geprüfter Ausgangspunkt ist Commit `a8993c5c68042d996eab680d84a5b138a214bb5d` bekannt; überprüfe ausdrücklich, ob der Branch inzwischen weiter ist.

## Auftrag und Grenzen

**Starte ausschließlich den vollständigen Pilotdurchlauf für Kapitel 02.03 „Activation“.** Die übrigen 103 Kapitel bleiben `PLANNED`. Der Pilot soll beweisen, dass die Orchestrierung wirklich funktioniert: eigenständige Code-Recherche → verständliches Kapitel → unabhängige Prüfung → Korrektur bei Bedarf → dokumentierte Abnahme. Starte anschließend **nicht** automatisch die übrigen Kapitel.

Lies zu Beginn vollständig und beachte:
- `AGENTS.md`, `SPEZIFIKATION_v0.2.md`, `GLIEDERUNG.md`.
- `workflow/master-plan.md`, `workflow/README.md`, `workflow/task-registry.json`.
- `workflow/pilot/02.03-activation.md`.
- `workflow/notes/02.03.md` und `workflow/diagram-notes/02.03.md`.

## Modellzuordnung und Agenten

Verwende die bestehenden projektlokalen Agentenprofile unter `.opencode/agents/`:
- **Orchestrator:** `doc-orchestrator` – Muse Spark 1.3 Contributor.
- **Researcher:** `doc-researcher` – DeepSeek V4.1 Flash.
- **Writer:** `doc-writer` – DeepSeek V4.1 Flash.
- **Reviewer:** `doc-reviewer` – Muse Spark 1.3 Contributor.

Rufe Researcher, Writer und Reviewer als **tatsächlich getrennte OpenCode-Subagenten** auf, keine bloße Rollensimulation innerhalb dieser Hauptsession. Wenn ein Profil nicht geladen wird, ein Modell nicht erreichbar ist oder der Subagenten-Aufruf scheitert, dokumentiere den konkreten Blocker. Keine Scheinabnahme.

## Schritt 1 – Quellcode eindeutig identifizieren

Der aktuelle OpenChamber-Projektordner enthält ausschließlich den Dokumentationsarbeitsplatz, **nicht** den aktuellen Server-Quellcode. Suche lesend nach einem lokalen Git-Worktree für `feat/v2-release-cleanup`, überprüfe dessen tatsächlichen Branch, HEAD und Arbeitsbaum und gleiche den Commit möglichst mit dem aktuellen GitHub-Branch ab. Ältere Checkouts unter `workspaces/` nicht unbesehen als Quelle verwenden.

Wenn kein eindeutiger aktueller Quellstand verfügbar oder ein sicherer Lesezugriff nicht möglich ist, melde den Blocker mit den konkreten nötigen Schritten. **Keine Quell-Repositories verändern oder eigenmächtig Branches auschecken.** Für externen lesenden Zugriff gegebenenfalls die ausdrücklich vorgesehene OpenCode-Freigabe anfordern.

Fixiere den geprüften Quellcommit in der Pilotakte und verwende denselben Commit für Research und Review.

## Schritt 2 – Unabhängige technische Recherche

Beauftrage `doc-researcher` mit **02.03 Activation** einschließlich Controller, Triggerquellen, Prioritäten, Phasen, Zustandsübergängen, Commands, Admission/Reject, Locks, Timings, Watchdogs, Follow-up, Audiofreigabe, Idempotenz, Race Conditions, Recovery und Zusammenwirken mit Wake-Word, VAD, Session und Transcription.

**Quellenregel:** Forschungsgrundlage sind ausschließlich aktueller **Produktquellcode**, tatsächliche Schemas/Registrierungen, Tests und für das Verhalten nötige technische Konfiguration. **Keine alten oder neuen Dokumentationsseiten, README-Dateien, Archivberichte, Agentenbehauptungen oder Legacy-STT-Texte als Faktenquelle verwenden.** Gliederung und persönliche Notizen sind Arbeitsanweisungen, keine technischen Beweise.

Liefere eine strukturierte Faktenakte mit IDs, Quellpfaden, Symbolen, Belegen und expliziten Ungewissheiten unter `workflow/research/02.03.json`. Bei Meinungsverschiedenheiten zwischen Code und Tests den Konflikt kennzeichnen, nicht wegerklären.

## Schritt 3 – Anschauliches Kapitel verfassen

Übergebe die verifizierte Faktenakte an `doc-writer`. Ziel ist ein **gut lesbares, verständliches und praxisorientiertes Handbuchkapitel**, nicht eine unkommentierte Faktensammlung oder ein Telefonbuch.

Erkläre:
- Wozu Activation dient und welches Problem sie löst.
- Den Ablauf anhand mindestens eines vollständig belegten Beispiels.
- Bedeutung der einzelnen Phasen und Timer für die Cliententwicklung.
- Warum und wann Trigger angenommen oder zurückgewiesen werden.
- Verhalten bei Abbruch, Fehler, Race Conditions und Wiederanlauf.

Die Datei für den Entwurf liegt bereits unter `docs/v2-handbuch/02-funktionsweise/` und ist über `workflow/task-registry.json` referenziert. Ersetze dort den Platzhalter durch die tatsächliche Ausarbeitung.

Bitte die Diagrammwünsche aus `workflow/diagram-notes/02.03.md` berücksichtigen:
1. **Mermaid-Zustandsdiagramm** für die real implementierten Activation-Phasen.
2. **Mermaid-Sequenzdiagramm** für Trigger, Timings, Audiofreigabe und Events.

Nutze nur tatsächlich belegte Übergänge und Fristen. Jede relevante Diagrammaussage muss über die Faktenakte prüfbar sein. Erläutere die Grafiken mit verständlichem Fließtext; die Diagramme sollen den Text ergänzen, nicht ersetzen.

## Schritt 4 – Unabhängiger Review und Korrekturschleife

Beauftrage `doc-reviewer` **nach** dem Entwurf. Der Reviewer prüft eigenständig die Aussagen und beide Diagramme gegen den **Originalcode desselben Commits** und bewertet außerdem Gliederungsabdeckung, Praxisbezug, Verständlichkeit und Widersprüche.

Speichere den Prüfbericht unter `workflow/reviews/02.03.md`. Der Reviewer meldet `PASS`, `CHANGES_REQUESTED` oder `ESCALATE` mit konkreten Findings und Fundstellen.

Bei `CHANGES_REQUESTED` erhält der Writer beziehungsweise Researcher den präzisen Mangel zurück. Anschließend erfolgt eine erneute unabhängige Prüfung. Höchstens drei Korrekturrunden ohne substanzielle Fortschritte; dann `ESCALATE` statt endloser Wiederholungen.

**Keine Selbstabnahme durch Writer oder Orchestrator.** Ein bloßes „sieht gut aus“ reicht nicht.

## Schritt 5 – Ergebnisse und Status korrekt sichern

Verwende `workflow/task-registry.json` als einzige Statusautorität und `tools/workflow_cli.py` für kontrollierte Statusübergänge. Dokumentiere Research, Entwurf, Review, Korrekturen und den tatsächlichen Quellcommit. Danach:
- `python tools/workflow_cli.py refresh`
- `python tools/workflow_cli.py validate`
- `python tools/workflow_cli.py status`

Setze `02.03` nur bei echten Nachweisen auf `ACCEPTED` beziehungsweise `INTEGRATED`. Fehlende Evidenz darf niemals durch eine Statusänderung kaschiert werden. Alle anderen Kapitel bleiben unangetastet.

Abschlussmeldung **`PILOT_READY_FOR_REVIEW`** mit: verwendeten Subagenten/Modellen, geprüfter Git-SHA, erzeugten Artefakten, Testergebnissen, Reviewurteil, Korrekturrunden, verbleibenden offenen Punkten und einer Einschätzung, ob wir die Methodik für die übrigen 103 Kapitel verwenden können.

**Verboten:** Produktcode verändern, bestehende Legacy-STT-/V2-Dokumentation überschreiben, andere Kapitel bearbeiten, Git-Merge/Push/Release/Deployment ausführen, andere kostenpflichtige Modellanbieter ohne Freigabe nutzen.

**Beginne jetzt mit diesem einen Pilotprojekt und führe es so weit wie technisch möglich bis zur unabhängigen Abnahme durch.**
