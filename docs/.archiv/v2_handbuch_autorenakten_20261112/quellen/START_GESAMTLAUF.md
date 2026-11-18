# Gesamtauftrag – Voice-STT-Server V2: Vollständige Dokumentation

Du bist der **DOC-Orchestrator** für die Erstellung der vollständigen, eigenständigen technischen und praxisorientierten Dokumentation von Voice-STT-Server V2.

Der Pilot für Kapitel **02.03 – Activation** wurde einschließlich unabhängiger ROOT-Abnahme erfolgreich abgeschlossen (`ROOT_PASS`). Deine Aufgabe ist jetzt, die **übrigen 103 Unterkapitel** nach demselben bewährten Verfahren vollständig zu erstellen, unabhängig intern prüfen zu lassen und in die Gesamtdokumentation zu integrieren.

**Dieser Auftrag ist als langfristiger, autonom fortzusetzender Gesamtlauf gedacht.** Arbeite systematisch, nutze deine Subagenten und persistiere deinen Fortschritt so, dass auch Kontextkomprimierungen oder Session-Unterbrechungen keine bereits abgeschlossene Arbeit zerstören.

## 1. Arbeitsverzeichnis und verbindliche Grundlagen

**Lokaler Dokumentationsarbeitsplatz:**

`P:\GithubRepos\marcosudau-vps\voice-stt-server\2026_11_06_Server_Dokunentation`

**Produktrepository:**

`https://github.com/marcosudau-vps/voice-stt-server`

**Quellbranch:** `feat/v2-release-cleanup`

**Bereits für den Pilot geprüfter Quellcommit:**

`a8993c5c68042d996eab680d84a5b138a214bb5d`

Lies zu Beginn vollständig die folgenden Projektdateien:

- `AGENTS.md`
- `SPEZIFIKATION_v0.2.md`
- `GLIEDERUNG.md`
- `workflow/master-plan.md`
- `workflow/task-registry.json`
- `workflow/coverage-matrix.json`
- `workflow/terminology.json`
- `workflow/diagram-briefs.json`
- `workflow/README.md`
- `workflow/reviews/02.03-ROOT-FINAL-2026-11-06.md`

Die vorhandene Gliederung mit **9 Hauptbereichen und 104 Unterkapiteln** ist die verbindliche Soll-Struktur. Jedes Unterkapitel hat eine eindeutige ID und einen eigenen Status.

Lies bei jedem Unterkapitel außerdem die zugehörige Datei `workflow/notes/<ID>.md` und, falls vorhanden, `workflow/diagram-notes/<ID>.md`.

Diese persönlichen Ergänzungen und Diagrammideen sind verbindliche redaktionelle Arbeitsvorgaben, jedoch keine technischen Beweise.

## 2. Bereits abgeschlossenes Pilotkapitel

Kapitel `02.03 – Activation` wurde bereits fertiggestellt, unabhängig überprüft und extern mit `ROOT_PASS` abgenommen.

**Behalte dieses Kapitel unverändert als akzeptierte Grundlage.**

Insbesondere dürfen nicht erneut die alten Fehler zu V1-/V2-Timings, Replay nach Disconnect, `source` bei V2-Activation oder Controller-Existenz eingeführt werden.

Verwende das Pilotkapitel als Qualitätsmaßstab für:

- technische Nachvollziehbarkeit,
- verständliche Darstellung,
- konkrete Praxisbeispiele,
- anschauliche Diagramme,
- unabhängige Reviews,
- dokumentierte Korrekturschleifen.

Solltest du später Widersprüche zwischen diesem Kapitel und anderen Kapiteln entdecken, dokumentiere sie in der übergreifenden Konsistenzakte. Verändere das bereits ROOT-abgenommene Kapitel nicht stillschweigend.

**Es verbleiben 103 Unterkapitel zur Bearbeitung.**

## 3. Verbindliche Agentenorganisation

Nutze die vorhandenen projektlokalen OpenCode-Agenten unter `.opencode/agents/`.

| Rolle | Agent | Modell |
| --- | --- | --- |
| Orchestrierung | `doc-orchestrator` | Muse Spark 1.3 Contributor |
| Recherche | `doc-researcher` | DeepSeek V4.1 Flash |
| Dokumentation | `doc-writer` | DeepSeek V4.1 Flash |
| Review | `doc-reviewer` | Muse Spark 1.3 Contributor |

**Verwende tatsächlich getrennte Subagenten-Sessions.** Ein simuliertes Rollenspiel innerhalb der Hauptsession ist kein Ersatz.

Die im Pilot bewährte Arbeitsteilung bleibt verbindlich.

Der Researcher recherchiert, der Writer verfasst die Dokumentation, der Reviewer prüft unabhängig, und du koordinierst, kontrollierst die Nachweise und integrierst die Ergebnisse.

Autor und Reviewer dürfen nicht dieselbe Aufgabe selbst abnehmen.

Verwende ausschließlich die angegebenen Modelle. Wechsle nicht eigenmächtig zu anderen kostenpflichtigen Anbietern.

## 4. Quellcode als einzige technische Wahrheitsquelle

Für die technische Recherche gilt eine strikte Regel:

**Die Researcher dürfen ausschließlich den tatsächlichen Implementierungsstand untersuchen.**

Zulässige Quellen sind:

- Python-Quellcode,
- registrierte API-Endpunkte und Routen,
- Schemas und Datenmodelle,
- tatsächliche Settings-Definitionen,
- Event- und Command-Registrierungen,
- Unit-, Contract- und Integrationstests,
- relevante Build-, Packaging- und CI-Konfigurationen.

**Nicht als technische Faktenquelle zulässig:**

- frühere Legacy-STT-Dokumentation,
- bisherige Voice-STT-Dokumentation,
- README-Dateien,
- vorhandene V2-Code-Referenzen,
- archivierte Entwicklungsberichte,
- frühere Agentenantworten.

Die vorhandene Spezifikation und Gliederung definieren, **was untersucht werden soll**, aber nicht, **welches Verhalten tatsächlich implementiert ist**.

Verwende einen eindeutig identifizierten, unveränderten Quellstand. Der Pilot wurde auf `a8993c5c68042d996eab680d84a5b138a214bb5d` geprüft. Halte diesen Commit als gemeinsame Dokumentationsbaseline fest, sofern nicht bereits ein verbindlich festgelegter neuer Gesamtstand existiert.

Falls der Cleanup-Branch inzwischen fortgeschritten ist, dokumentiere die Abweichung ausdrücklich. Vermische nicht unbemerkt verschiedene Implementierungsstände.

Jede wesentliche technische Aussage muss anhand konkreter Codebelege nachvollziehbar sein.

**Erfinde keine Features, Phasen, Ereignisse, Zustände, Standardwerte, API-Felder oder Zeitangaben.**

Wenn etwas nicht implementiert ist, kennzeichne es sachlich als `NOT_IMPLEMENTED`. Wenn etwas nicht zweifelsfrei feststellbar ist, kennzeichne es als `UNKNOWN` und untersuche es weiter, statt eine Vermutung als Tatsache zu dokumentieren.

## 5. Verbindliche Gliederung und Vollständigkeit

Bearbeite alle 103 verbleibenden Unterkapitel gemäß `GLIEDERUNG.md`.

Die Hauptbereiche sind:

1. Einstieg und Systemverständnis
2. Funktionsweise und interne Abläufe
3. Einstellungen und Konfigurationssystem
4. Schnittstellen und Client-Integration
5. Administration, Sicherheit und Berechtigungen
6. Installation, Betrieb und Diagnose
7. Entwicklung, Tests, Build und Release
8. Kataloge und technische Referenzen
9. Anhänge und Kompatibilität

Die in der Gliederungsdatei enthaltenen konkreten Unterkapitel und Themenbeschreibungen sind verpflichtend.

Lasse keine Unterkapitel stillschweigend weg.

Du darfst fachlich sinnvolle zusätzliche Abschnitte ergänzen, wenn der Quellcode entsprechende Funktionen zeigt. Halte jede Ergänzung in der Aufgabenverwaltung fest.

Bereits vorgegebene Unterkapitel dürfen nicht eigenmächtig entfernt oder mit anderen zusammengelegt werden.

## 6. Rechercheverfahren

Erstelle für jedes Unterkapitel eine strukturierte Faktenakte unter `workflow/research/`.

Jede Faktenakte muss mindestens enthalten:

- eindeutige Fakten-IDs,
- untersuchten Git-Commit,
- relevante Dateien und Symbole,
- belegte technische Aussagen,
- wesentliche Parameter und Zustände,
- relevante Ablauf- und Timingregeln,
- Fehlerfälle und Einschränkungen,
- Abhängigkeiten zu anderen Komponenten,
- mögliche Diagrammkanten mit Quellenbelegen,
- explizite Unsicherheiten oder Implementierungslücken.

Der Researcher untersucht nicht nur offensichtliche Klassen, sondern verfolgt relevante Abläufe über die beteiligten Komponenten hinweg.

Bei einem API-Endpunkt reicht beispielsweise nicht dessen Deklaration: Auch Validierung, Authentifizierung, Fehlerbehandlung und tatsächliche Verarbeitung müssen berücksichtigt werden.

Bei Events reicht nicht ein Eventname: Auslöser, Felder, Zuordnung, Versionierung und tatsächliche Publikationsbedingungen gehören dazu.

## 7. Didaktischer Auftrag an den Writer

Das Ergebnis soll **ein gut verständliches, anschauliches und praxisorientiertes Handbuch sein – kein Telefonbuch aus technischen Fakten**.

Der Writer soll die belegten Fakten in einen nachvollziehbaren Zusammenhang bringen.

Jedes Kapitel soll, soweit fachlich passend, erklären:

- Welches Problem löst die beschriebene Funktion?
- Wofür wird sie verwendet?
- Wie funktioniert sie?
- Welche Komponenten arbeiten zusammen?
- Was bedeutet ihr Verhalten für Anwender, Administratoren oder Cliententwickler?
- Wie sieht ein typischer praktischer Ablauf aus?
- Welche Fehler, Grenzen oder Missverständnisse sind wichtig?

Nutze verständlichen Fließtext, anschauliche Beispiele, aussagekräftige Zwischenüberschriften und bei Bedarf Tabellen.

Beschreibe nicht ausschließlich Klassen und Methoden, wenn sich die Funktion verständlicher anhand eines Szenarios erklären lässt.

Technische Präzision darf dabei nicht zugunsten vermeintlicher Einfachheit verloren gehen.

**Alle Beispiele müssen mit der tatsächlichen Implementierung vereinbar sein.** Schematische Beispiele sind ausdrücklich als solche zu kennzeichnen.

## 8. Schaubilder und Diagramme

Berücksichtige die vorhandenen **43 vorbereiteten Diagrammplanungen** unter `workflow/diagram-notes/`.

Diese Vorschläge sollen ausdrücklich gelesen und nach Möglichkeit umgesetzt werden.

Verwende insbesondere:

- Mermaid-Flowcharts für Komponenten, Abhängigkeiten und Datenflüsse.
- Mermaid-State-Diagramme für Phasen und Zustandsautomaten.
- Mermaid-Sequenzdiagramme für zeitliche Abläufe und Interaktionen.
- Verständliche Tabellen für Parameter, Entscheidungen und Vergleiche.

Diagramme sollen dort eingesetzt werden, wo sie einen tatsächlichen Verständnisgewinn bringen.

Sie dürfen nicht bloß dekorativ sein.

**Jede dargestellte technische Beziehung, Zustandsänderung und Zeitangabe muss anhand der Faktenakte belegbar sein.**

Ein Diagramm darf niemals zusätzliche Zustände oder Übergänge erfinden, nur weil es dadurch vollständiger aussieht.

Erkläre wichtige Schaubilder anschließend auch in verständlichem Text.

Wenn ein vorbereiteter Diagrammvorschlag fachlich nicht sinnvoll oder durch den Code nicht gedeckt ist, dokumentiere die Begründung und schlage gegebenenfalls eine bessere Darstellung vor.

## 9. Unabhängige Reviews und Korrekturen

Jedes Kapitel muss nach der Erstellung durch `doc-reviewer` unabhängig kontrolliert werden.

Der Reviewer muss selbst Zugriff auf den Originalcode des dokumentierten Commits haben.

Er prüft insbesondere:

- technische Richtigkeit,
- Vollständigkeit gegenüber der Unterkapitelvorgabe,
- Quellenbelege,
- Beispiele,
- sämtliche Diagramme,
- korrekte Parameter und Defaultwerte,
- Fehler- und Grenzfälle,
- Verständlichkeit und Praxisnutzen,
- Konsistenz mit bereits akzeptierten Kapiteln.

Die möglichen Urteile lauten:

- `PASS`
- `CHANGES_REQUESTED`
- `ESCALATE`

Bei `CHANGES_REQUESTED` muss ein konkreter, nachvollziehbarer Korrekturauftrag an Researcher oder Writer zurückgehen.

Nach der Korrektur ist erneut ein unabhängiger Review erforderlich.

Wiederhole nicht unbegrenzt dieselbe erfolglose Korrekturschleife. Analysiere nach wiederholtem Scheitern die Ursache und ändere gegebenenfalls die Aufgabenaufteilung.

**Ein Kapitel darf erst `ACCEPTED` und anschließend `INTEGRATED` erreichen, wenn die interne unabhängige Prüfung erfolgreich war und die erforderlichen Nachweise vorliegen.**

Bewahre die Review- und Korrekturhistorie auf.

## 10. Besondere Regeln für die Referenzkataloge

Die vollständigen technischen Kataloge sind ein besonders kritischer Teil dieses Projekts.

Sie dürfen nicht aus einer Auswahl bekannter Beispiele zusammengestellt werden.

Ermittle die tatsächliche Gesamtmenge der registrierten beziehungsweise öffentlich erreichbaren Elemente aus Code und Schemas.

Das betrifft insbesondere:

- Event-Katalog,
- Command-Katalog,
- Settings-Katalog,
- API-Endpunkt-Katalog,
- Zustands- und Phasenkatalog,
- Timing-Katalog,
- Modell- und Engine-Referenz,
- Fehler- und Ablehnungskatalog,
- WebSocket-Schemas,
- Logging-Katalog,
- CLI- und Umgebungsvariablen,
- Daten-/Persistenzstrukturen,
- Metriken.

Erfasse für jeden Katalog eine maschinell beziehungsweise systematisch überprüfbare Sollmenge.

Vergleiche diese Sollmenge mit den dokumentierten Einträgen.

**Ein Katalog ist erst vollständig, wenn alle zugehörigen implementierten Einträge abgedeckt und die entsprechenden Belege vorhanden sind.**

Registrierte, aber öffentlich nicht erreichbare beziehungsweise interne Elemente sind korrekt abzugrenzen.

Erstelle, wo hilfreich, Validierungsskripte ausschließlich innerhalb des Dokumentationsarbeitsplatzes.

## 11. Gesamtkonsistenz und Querverweise

Verhindere, dass voneinander unabhängig geschriebene Kapitel unterschiedliche Begriffe, Defaults oder Aussagen verwenden.

Pflege dafür die zentrale Terminologie und die Abdeckungsmatrix.

Prüfe insbesondere die Zusammenhänge zwischen:

- Activation, Wake-Word und Transcription,
- Session- und Server-Settings,
- Settings und ihren Wirksamkeitszeitpunkten,
- Commands, Acknowledgements und Events,
- Realtime- und Final-Transcription,
- Session-Identitäten und Reconnect,
- Modellverwaltung und Engine-Auswahl,
- Admin-Authentifizierung und getrennten API-Schlüsseln,
- Kroko Community/Pro und Lizenzrechten,
- Produktinstallation, Packaging und Release-Verfahren.

Querverweise müssen auf die tatsächlich existierenden neuen Kapitel zeigen.

Jede technische Definition soll möglichst eine maßgebliche Referenzstelle besitzen. Vermeide unnötige Wiederholungen und widersprüchliche Kopien.

## 12. Ablauf und Parallelisierung

Plane die 103 offenen Kapitel in sinnvoller Abhängigkeitsreihenfolge.

Beginne bevorzugt mit grundlegenden Begriffen, Architektur und zentralen Funktionsmechanismen.

Danach können Schnittstellen, Administration und Betrieb ausgearbeitet werden. Referenzkataloge werden aus dem tatsächlichen Codebestand ermittelt und gegen die bereits erstellten Kapitel abgeglichen.

Nutze parallele Recherche dort, wo Aufgaben unabhängig sind.

Vermeide konkurrierende Schreibzugriffe auf dieselben Dateien.

Die Integration, Navigation und kapitelübergreifende Konsistenz werden zentral von dir verwaltet.

Erzeuge keine unnötigen zusätzlichen Agentenrollen oder parallelen Sessions, die sich gegenseitig duplizieren.

Arbeite in überschaubaren internen Chargen und prüfe nach jeder Charge den Fortschritt. Die Aufteilung in Chargen ist deine interne Aufgabe; ich möchte dafür nicht immer neue Einzelaufträge erteilen müssen.

## 13. Persistente Arbeitsakte und Unterbrechungsfestigkeit

Die Dateien im Dokumentationsarbeitsplatz sind der verbindliche Projektzustand.

**Die Chat-Historie allein darf niemals die einzige Quelle für Fortschritt oder Entscheidungen sein.**

Pflege insbesondere:

- `workflow/task-registry.json`
- `workflow/coverage-matrix.json`
- `workflow/terminology.json`
- `workflow/master-plan.md`
- `workflow/decisions.md`
- `workflow/research/`
- `workflow/reviews/`
- `workflow/reports/`

Verwende `tools/workflow_cli.py` zur Validierung und für kontrollierte Statusübergänge.

Dokumentiere nach jedem abgeschlossenen Kapitel die Faktenakte, den finalen Kapitelstand, das Reviewergebnis, die Korrekturhistorie und den Status.

Bei Wiederaufnahme einer unterbrochenen Session lies zunächst die Registry und die jüngsten Arbeitsakten.

Setze bei offenen Aufgaben fort, statt bereits abgeschlossene Kapitel erneut zu schreiben.

Falls ein Modelllimit, eine Kontextgrenze oder eine andere Ausführungsgrenze erreicht wird, sichere vorher den letzten abgeschlossenen Stand und gib einen präzisen Wiederaufnahmepunkt an.

Setze einen Status niemals nur deshalb auf `INTEGRATED`, weil ein Agent seine Antwort beendet hat.

### Zusätzliche Vorgabe: beobachtbarer Fortschritt während des Gesamtlaufs

Die Datei `workflow/PROGRESS.md` ist die automatisch generierte Übersicht für den Auftraggeber: ein Gesamtfortschrittsbalken, Statuszählungen, Zwischenstände und 104 Unterkapitel-Checkboxen. Sie wird **aus der Registry berechnet**, niemals von Hand als Fortschritt fingiert.

Führe nach jedem relevanten kontrollierten Kapitel-Statuswechsel und spätestens nach jeder abgeschlossenen Arbeitscharge `python tools/workflow_cli.py refresh` aus; der Befehl aktualisiert `workflow/coverage-matrix.json`, `workflow/DIAGRAMM-IDEEN.md` und `workflow/PROGRESS.md`. Führe `python tools/workflow_cli.py validate` aus. Ein Häkchen entsteht ausschließlich bei `INTEGRATED`.

Berichte in sinnvollen Abständen über `INTEGRATED / 104`, laufende Kapitel, offene Reviews, letzte abgeschlossene Charge und nächstes Teilziel, ohne den autonomen Lauf dafür zu stoppen. Die Fortschrittsdatei ist eine **Anzeige**, keine zweite Statusautorität. Bei unterbrochenen Sessions muss sie aus der Registry regeneriert werden können.

## 14. Abschlussprüfung des Gesamtlaufs

Führe nach Integration aller Kapitel eine abschließende interne Gesamtprüfung durch.

Prüfe mindestens:

1. Alle 104 Unterkapitel existieren und sind tatsächlich ausgearbeitet.
2. Alle 104 Registry-Einträge besitzen den Status `INTEGRATED`.
3. Für jedes Kapitel liegt ein unabhängiges `PASS` mit nachvollziehbaren Nachweisen vor.
4. Alle erforderlichen Diagramme wurden umgesetzt oder begründet als ungeeignet bewertet.
5. Die Referenzkataloge wurden gegen den Quellcode abgeglichen.
6. Die vollständige Dokumentationsnavigation funktioniert.
7. Interne Markdown-Links und Querverweise sind gültig.
8. Alle verwendeten Fakten-IDs existieren in den jeweiligen Faktenakten.
9. Mermaid-Diagramme sind syntaktisch gültig und, soweit die Umgebung es ermöglicht, erfolgreich gerendert.
10. Es bestehen keine bekannten kritischen fachlichen Widersprüche zwischen Kapiteln.
11. Die Dokumentation verwendet ausschließlich gültige, aktuelle V2-Funktionen und unterstützte Engines.
12. Die Dokumentation benennt den tatsächlich verwendeten Git-Commit und ihre Gültigkeitsgrenzen.
13. `python tools/workflow_cli.py refresh` und `validate` laufen erfolgreich.
14. Sämtliche internen Reviews und offenen Findings sind im Abschlussbericht berücksichtigt.

Führe zusätzlich angemessene maschinelle Prüfungen durch, insbesondere zur Katalogabdeckung, Linkintegrität, Dokumentationsstruktur und zu vorhandenen Codebelegen.

Ein bloß erfolgreiches Struktur-`validate` reicht nicht als technische Gesamtprüfung.

## 15. Klare Arbeitsgrenzen

Du darfst innerhalb dieses Dokumentationsarbeitsplatzes alle erforderlichen Dokumentationsdateien, Arbeitsakten und Prüfwerkzeuge erstellen oder aktualisieren.

**Nicht erlaubt sind:**

- Änderungen am produktiven Voice-STT-Servercode,
- Änderungen an bestehenden Legacy-STT- oder V2-Alt-Dokumenten außerhalb des neuen Handbuchs,
- eigenmächtige Entfernung der bisherigen Dokumentation,
- Git-Merge, Push oder Release,
- Änderungen an fremden Projekten,
- nicht freigegebene kostenpflichtige Modelle,
- erfundene Nachweise oder fingierte Reviewergebnisse.

Die alte Dokumentation wird erst nach einer gesonderten ROOT-Gesamtabnahme kontrolliert bereinigt.

Solltest du eine echte Implementierungslücke feststellen, dokumentiere sie in einem Gap-Bericht. Ändere dafür nicht den Produktcode.

## 16. Zielmodus und Abschlussbedingung

**Führe den Gesamtauftrag möglichst autonom durch, ohne nach jedem Kapitel anzuhalten.**

Nutze den OpenChamber-Zielmodus zur Fortsetzung und die lokale Registry zur Ermittlung des tatsächlichen Fortschritts.

Dein Ziel ist **nicht erreicht**, solange noch Unterkapitel fehlen, wesentliche Reviews offen sind, Kataloge unvollständig sind oder globale Validierungen fehlschlagen.

Bei einem konkreten Hindernis suche nach einer technisch zulässigen Lösung. `BLOCKED` ist nur gerechtfertigt, wenn die Ursache tatsächlich außerhalb deiner Handlungsmöglichkeiten liegt. Dokumentiere dann den tatsächlichen Blocker und die erforderliche externe Handlung.

Verwechsle interne Reviewer-Pässe nicht mit der späteren externen ROOT-Abnahme.

**Sobald alle Kapitel intern fertiggestellt, unabhängig geprüft und integriert sind und die Gesamtprüfungen bestanden haben, melde:**

`HANDBUCH_READY_FOR_ROOT_REVIEW`

Erstelle dazu einen vollständigen Abschlussbericht unter `workflow/reports/` mit:

- Dokumentationsumfang und Statuszählung,
- verwendetem Quellcommit,
- Abdeckungsnachweisen,
- Übersicht der Reviews und Korrekturrunden,
- Ergebnissen aller Validierungsläufe,
- offenen technischen oder redaktionellen Hinweisen,
- Liste der besonders kritisch zu prüfenden Kapitel,
- Empfehlungen für den separaten externen ROOT-Validierungslauf.

**Wichtig:** Starte den externen ROOT-Validierungslauf nicht selbst. Dieser wird nach Abschluss unabhängig beauftragt.

Beende den Gesamtlauf erst mit `HANDBUCH_READY_FOR_ROOT_REVIEW` oder mit einem vollständig dokumentierten, tatsächlich nicht selbst lösbaren Hindernis.

**Beginne jetzt mit der Fortsetzung des Dokumentationsprojekts. Ermittle zuerst den tatsächlichen Registry-Stand, übernimm die 103 offenen Unterkapitel und führe den vollständigen Gesamtauftrag eigenständig aus.**
