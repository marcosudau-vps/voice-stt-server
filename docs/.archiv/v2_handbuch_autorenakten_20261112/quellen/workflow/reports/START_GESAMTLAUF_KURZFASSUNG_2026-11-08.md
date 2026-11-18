# Startauftrag – Gesamtdokumentation Voice-STT-Server V2 (103 offene Kapitel)

**Ziel:** Das vollständige Voice-STT-V2-Handbuch aus dem aktuellen, geprüften Produktcode erstellen. 104 verbindliche Unterkapitel, davon Pilot 02.03 bereits intern abgeschlossen und extern ROOT-abgenommen; **103 sind noch offen**.

**Auftraggeberziel:** Arbeite autonom in überschaubaren Chargen. Nachweisbare technische Recherche, verständliche Texte, passende Schaubilder, unabhängige Reviews und kontrollierte Statusübergänge. Keine fortlaufende manuelle Kapitelbeauftragung.

**Arbeitsverzeichnis:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\2026_11_06_Server_Dokunentation`
**Produktrepository (nur lesend):** `https://github.com/marcosudau-vps/voice-stt-server`
**Branch:** `feat/v2-release-cleanup`
**Pilot-/Baseline-SHA:** `a8993c5c68042d996eab680d84a5b138a214bb5d`

## 1. Zuerst den Arbeitsstand ermitteln

Lies vollständig: `AGENTS.md`, `SPEZIFIKATION_v0.2.md`, `GLIEDERUNG.md`, `workflow/master-plan.md`, `workflow/README.md`, `workflow/task-registry.json`, `workflow/coverage-matrix.json`, `workflow/terminology.json`, `workflow/diagram-briefs.json`, `OPEN_CODE_EINRICHTUNG.md` und den Pilot-ROOT-Abnahmebericht `workflow/reviews/02.03-ROOT-FINAL-2026-11-06.md`.

Die **neun Hauptkapitel und alle 104 Unterkapitel-IDs samt Umfang** stehen verbindlich in `GLIEDERUNG.md` und `SPEZIFIKATION_v0.2.md`. Sie sind keine optionalen Vorschläge. Bevor du eine ID bearbeitest, lies auch `workflow/notes/<ID>.md` sowie gegebenenfalls `workflow/diagram-notes/<ID>.md`. Persönliche Hinweise sind redaktionelle Anforderungen, keine technischen Belege.

Prüfe den Ist-Zustand vor jeder Charge. `02.03 Activation` ist bereits `INTEGRATED`, besitzt einen eigenständigen `ROOT_PASS` und bleibt **unverändert**. Bearbeite nur die übrigen 103 `PLANNED`-Kapitel. Bei neu entdeckten Widersprüchen zum Piloten: Befund in der Konsistenzakte dokumentieren, nicht stillschweigend das bereits ROOT-abgenommene Kapitel editieren.

Verifiziere, wo der tatsächliche Produktcode liegt und welcher Git-Commit vorliegt; verwechsel den Dokumentationsarbeitsordner nicht mit dem Server-Quellcheckout. Ein früher verwendeter, sauberer lokaler Lesespiegel befand sich unter `C:\Users\user\AppData\Local\Temp\opencode\voice-stt-v2-src`. Nutze ihn nur, wenn der HEAD geprüft und der gewünschte Stand nachweisbar ist. Recherchiere alle Kapitel gegen eine **explizit fixierte, einheitliche Quellrevision**. Wenn der Branch mittlerweile weiter ist, dokumentiere die Abweichung und wähle eine nachvollziehbare konsistente Basis; den Pilot nicht ohne neuen gesonderten Abnahmeauftrag auf einen anderen SHA umdeuten.

## 2. Agenten und klare Rollen

Verwende die bereits vorhandenen projektlokalen OpenCode-Profile unter `.opencode/agents/`:

- `doc-orchestrator` – **Muse Spark 1.3 Contributor**. Du koordinierst, integrierst, kontrollierst Status und Nachweise.
- `doc-researcher` – **DeepSeek V4.1 Flash**. Recherche ausschließlich im Implementierungscode.
- `doc-writer` – **DeepSeek V4.1 Flash**. Leserfreundliche technische Dokumentation und Diagramme.
- `doc-reviewer` – **Muse Spark 1.3 Contributor**. Unabhängige technische und redaktionelle Prüfung.

Research, Schreiben und Review müssen **tatsächlich in getrennten Subagenten-Sessions** stattfinden, nicht als vom Orchestrator simulierte Rollen. Lege Session-IDs und verwendete Modelle in den jeweiligen Arbeitsakten ab. Keine Selbstabnahme. Wenn ein Subagent nicht erreichbar ist, prüfe Berechtigungen/Modellkonfiguration und dokumentiere einen echten externen Blocker nur bei tatsächlich fehlender Einflussmöglichkeit. Keine eigenmächtigen Wechsel zu kostenpflichtigen anderen Anbietern.

## 3. Die Forschung muss ausschließlich vom Code ausgehen

**Ausschließlich zulässige technische Evidenz:** Implementierung und registrierte Laufzeitpfade in Python, tatsächlich aktive Routen und Endpoint-Handler, Konfigurations-/Settings-Registries, Schemas/Datentypen, Tests, Build-/CI-/Packaging-Konfigurationen und weitere tatsächliche Produktquellartefakte.

**Als Quelle für Tatsachen verboten:** alte Legacy-STT-Dokumentation, bestehende Voice-STT-Dokumentation einschließlich `docs/v2-code-reference`, README-Dateien, frühere Agententexte, Reports, historische Audits. Gliederung und Notizen bestimmen die zu untersuchenden Fragen, nicht die Antworten. Stütze keinen neuen Fakt lediglich auf den Pilottext; überprüfe gemeinsame Grundlagen erneut gegen den festgelegten Code.

Je Kapitel eine nachvollziehbare `workflow/research/<ID>.json` mit Fakt-ID, Codepfad, Symbol/Funktion, Geltungsbereich, Evidenz, Default/Range, Zuständen, Fehlerfällen, Grenzen, Risiken und `UNKNOWN`/`NOT_IMPLEMENTED`, soweit relevant. Erstelle für Diagramme belegte Zustände, Datenkanten, Fristen und Ereignisse. Unbelegte Aussagen oder ungeprüfte Behauptungen sind nicht erlaubt. Markiere Differenzen zwischen Tests und Code explizit.

Dokumentiere nur tatsächlich unterstützte V2-Produktfunktionen (insbesondere CPU-only und die vorhandenen produktiven Engines Faster-Whisper und Kroko ONNX Community/Pro). Historische oder experimentelle Engines nicht als aktuell unterstützt darstellen. Native-Lizenz-/Distributionsfreigaben nicht ohne Beleg als erteilt behandeln.

## 4. Der Writer schreibt ein Handbuch – kein Telefonbuch

Verwandle die verifizierte Faktenakte in gut lesbare Fachprosa: Motivation, Verantwortung der Komponenten, Schritt-für-Schritt-Abläufe, klare Begriffe, praktische Client-/Anwender-/Admin-Szenarien, Fehlerbilder und Grenzen. Erkläre „Warum?“ und „Wie verhält es sich im Alltag?“ statt nur Methoden/Parameter aufzuzählen.

Schreibe in die bereits angelegte Datei aus `workflow/task-registry.json` (`draft_path`), nicht in zufällig neue Dateinamen. Strukturiere sinnvoll in Überschriften, Erläuterungen, Beispielen und gezielten Tabellen. Schematische Beispiele deutlich als solche markieren; keine erfundenen Payloadfelder, Garantien, Parameterwerte oder Engines. Relevante Querverweise auf andere Kapitel anlegen und ihre spätere Auflösbarkeit überprüfen.

Die **43 vorbereiteten Diagrammideen** unter `workflow/diagram-notes/` sind einzeln auszuwerten. Nutze Mermaid-Flowcharts, Zustands-, Sequenz- und Datenflussdiagramme, **wo sie dem Verständnis dienen**. Jede technisch wesentliche Kante und Zeitangabe ist per Fakten-ID gegen den Code belegbar; Diagramme zusätzlich im Fließtext erklären. Nicht belegbare oder ungeeignete Diagrammvorschläge mit Begründung markieren, nicht fingieren.

## 5. Unabhängiger Reviewer und Korrekturschleife

Für **jedes** Kapitel erfolgt ein unabhängiger Review, der selbst die Originalquellen überprüft (nicht lediglich die Faktenakte nachliest). Er muss Genauigkeit, Vollständigkeit gegenüber der Gliederung, Settings/Defaults/Scopes, API-Verträge, Beispiele, Diagramme, Verständlichkeit und Konsistenz mit anderen Kapiteln abnehmen.

Urteile: `PASS`, `CHANGES_REQUESTED`, `ESCALATE`. Konkrete Finding-IDs mit Severity, Codebeleg und präziser verlangter Korrektur. Bei Befund Researcher/Writer gezielt erneut beauftragen und durch einen unabhängigen Reviewer nachprüfen. Keine „PASS“-Behauptung ohne tatsächlich nachweisbaren Reviewer-Durchlauf. Nach drei erfolglosen identischen Korrekturrunden die Ursache untersuchen und Aufgabenstruktur ändern statt endlos zu wiederholen; nötigenfalls ESCALATE.

Sichere sämtliche Runden, Session-IDs, Befunde und Ergebnisse unter `workflow/reviews/<ID>.md` bzw. ergänzenden Nachträgen. Bestehende Prüfhistorie erhalten. Ein Kapitel erreicht `ACCEPTED` und `INTEGRATED` erst mit tatsächlichem `PASS`, Commit-Bezug, belegter Akte und korrekter Registry-Evidenz.

## 6. Referenzkataloge und mechanische Vollständigkeit

Für die gesamte Gruppe 08 und verwandte Abschnitte die **tatsächlich vollständigen registrierten Mengen** systematisch aus dem Code ermitteln. Dies umfasst Events, Commands, Session-/Server-Settings, HTTP-Endpunkte, WS-Felder/-Schemas, Status-/Phasencodes, Timings, Fehlermeldungen, Authentisierung, Engines/Modelle, Metriken, Logging, CLI/Environment und Daten-/SQLite-Strukturen.

Für jeden Katalog: Sollmenge ermitteln, dokumentierte Menge erfassen, Differenz mechanisch prüfen, interne/nicht unterstützte Einträge korrekt abgrenzen. Wo sinnvoll Prüfskripte **nur in diesem Dokumentationsarbeitsordner** erstellen. Eine bloß lange Liste ist kein Vollständigkeitsnachweis. Keine stillschweigend ausgelassenen Einträge.

## 7. Abhängigkeiten, Parallelität und Persistenz

Bearbeite zuerst Grundlagen, zentrale Abläufe, Konfiguration und Schnittstellen in nachvollziehbarer Reihenfolge; danach Betrieb, Sicherheit, Entwicklung und Referenzen. Parallele **Recherche** bei disjunkten Themen ist erwünscht, gleichzeitige Schreibzugriffe auf dieselbe Datei sind verboten. Die Integration und globalen Querverweise gehören dem Orchestrator.

**Fortschrittsanzeige für den Auftraggeber:** `workflow/PROGRESS.md` ist die zentrale, lesbare Checkliste aller 104 Unterkapitel. Sie wird durch `tools/workflow_cli.py` bei kontrollierten Statusübergängen und jedem `refresh` automatisch aus der Registry erzeugt. Aktualisiere den jeweiligen Status **direkt nach jedem abgeschlossenen Arbeitsschritt** und führe nach jedem Kapitel und jeder Charge `python tools/workflow_cli.py refresh` aus, damit die Anzeige während des Laufs nicht veraltet. Die Checkbox für eine Kapitel-ID darf erst bei `INTEGRATED` gesetzt sein; die Generierung erledigt das Skript automatisch. Eine manuelle Checkbox oder ein künstliches Setzen von `INTEGRATED` ist ausdrücklich unzulässig. Gib in deinen regelmäßigen Fortschrittsberichten die Anzahl `INTEGRATED / 104`, Kapitel in Bearbeitung und offene Reviewerbefunde an.

**Die Dateien sind die Statusautorität, nicht die Chat-Historie:** `workflow/task-registry.json`, `workflow/coverage-matrix.json`, `workflow/terminology.json`, `workflow/master-plan.md`, `workflow/decisions.md` sowie die Fakten-, Review- und Reportakten. Nach jeder abgeschlossenen Charge Zustand persistieren; `python tools/workflow_cli.py refresh`, `validate` und `status` anwenden. Statusübergänge nur kontrolliert und mit Evidenz. Bei Kontextkomprimierung oder Sitzungsfortsetzung Registry, letzten Report und offene Findings wieder einlesen. Nicht von vorne beginnen.

## 8. Abschlussgates – erst dann READY

Abschlussbedingungen sind **alle**:

1. Alle 104 Unterkapitel-Dateien sind nicht länger Platzhalter, sondern vollständig ausgearbeitet.
2. Alle 104 Einträge in der Task-Registry haben `INTEGRATED`.
3. Für jedes Kapitel sind unabhängige `PASS`-Reviews samt tatsächlichen Subagenten-Laufnachweisen vorhanden.
4. 43 vorbereitete Diagrammplanungen sind umgesetzt oder nachvollziehbar fachlich begründet abgelehnt; alle verwendeten Diagramme sind mit echten Fakten-IDs belegbar.
5. Kataloge sind gegen ihren tatsächlichen Code-Sollbestand vollständig abgeglichen (nicht nur Stichprobe).
6. Terminologie, Identitäten, Engine-/Lizenzabgrenzung, Timingregeln und API-Verträge sind über alle Kapitel konsistent.
7. Links, Markdown-Struktur, Navigation, Codebelege und Referenzen sind geprüft; Mermaid-Syntax und nach Möglichkeit Rendering kontrolliert.
8. Kein kritisches offenes Reviewer-Finding; wesentliche Lücken und Unsicherheiten sind ausgewiesen.
9. `python tools/workflow_cli.py validate` und die ergänzenden Gesamtchecks sind erfolgreich.
10. Der Abschlussreport dokumentiert den Git-SHA, die Abdeckungszahlen, Tests, Katalog-Diffs, Review-Historie, offenen Nichtblockern und eine priorisierte Liste für einen **separaten** externen ROOT-Validierungslauf.

Erst nach bestandenem internem Gesamtgate melde exakt **`HANDBUCH_READY_FOR_ROOT_REVIEW`** und lege den Abschlussbericht unter `workflow/reports/` ab. **Die externe ROOT-Abnahme wird danach separat durchgeführt, nicht innerhalb dieses Laufs.**

## 9. Grenzen

Schreibe **ausschließlich** in den Dokumentationsarbeitsplatz. Verändere weder Produktcode noch alte aktive Legacy-STT-/Voice-STT-Dokumentation, keine historischen Archive, keine rechtlichen Attributionen. Kein Git-Merge, Push, Release, Deployment oder Entfernen der alten Dokumentation. Fehlende Implementierung als Gap melden, nicht im Produkt „nebenbei“ reparieren.

Setze `BLOCKED` nur für reale, von dir nicht selbst lösbare äußere Hindernisse. Prüfe bei lokal lösbaren Hindernissen zuerst Alternativen. Wenn Tool-/Modelllimits oder Sitzungsgrenzen die Arbeit unterbrechen, speichere den Fortschritt und melde den exakten Wiederaufnahmepunkt. **Keine fingierten Statuswerte oder Testergebnisse.**

**Beginne jetzt:** Registry und Quelle prüfen, die 103 offenen Kapitel planen, delegieren, unabhängig prüfen und bis zur internen Gesamtabnahme abarbeiten. Starte nicht erneut den bereits freigegebenen Pilot.
