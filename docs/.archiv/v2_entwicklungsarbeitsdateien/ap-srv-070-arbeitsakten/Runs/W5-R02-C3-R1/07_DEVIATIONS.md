# AP-SRV-070 / W5-R02-C3-R1 — Deviations

Keine bekannten W5-R02-C3-R1-Abweichungen vom Auftrag.

Alle 39 Pflicht-Gates sind erfüllt, der Plan und der Semantik-Review lagen vor
der ersten getrackten Änderung vor, der R1-Branch wurde direkt vom
Remote-Binding-Commit `7f1ad1f...` erzeugt und der abgelehnte C3-Commit
`d60936c...` ist weder Vorfahre noch Grundlage.

Drei Punkte werden nach Abschnitt 20 des Prompts festgehalten, weil sie für die
Bewertung und für Folgeläufe relevant sind. Keiner davon ist eine Abweichung
vom Auftrag.

## B1: Die C3-Schlussfolgerung wird ausdrücklich revidiert

W5-R02-C3 hat den Übergang `degraded -> ready` durch einen erfolgreichen Read
als legitime Produkt-Recovery gewertet. `03_SEMANTIC_AUTHORITY_REVIEW.md`
entscheidet das aus aktueller Authority, bestehenden Tests, der
Architekturinvariante und reproduzierbarem Verhalten dagegen. C3s *Beobachtung*
(der Hänger entstand, weil der Store sich wieder als `ready` meldete) bleibt
sachlich richtig und wird übernommen; C3s *Bewertung* dieses Übergangs war
falsch. Root Review lag hier richtig.

Konsequenz: R1 strukturiert nicht nur Tests um, sondern korrigiert das
Zustandsmodell. Damit entfällt die Ursache des Hängers und nicht nur sein
Symptom.

## B2: Produktverhalten ändert sich (bewusst, Branch B)

Vor der Korrektur meldete der kanonische Store nach einem einzigen
erfolgreichen Read wieder `ready`, obwohl Writes weiterhin fehlschlugen.
Danach bleibt er `degraded`, bis ein Append tatsächlich committet.

Sichtbare Folgen im Mischzustand READ=ok / WRITE=kaputt:

- `/ws/logs` antwortet `log.error(event_store_unavailable)` und schliesst 1011,
  statt einen scheinbar gesunden Stream zu liefern;
- `hello.logAccess.available` und `replayAvailable` bleiben `false`;
- `/health` meldet `ok: false`;
- `/api/logs/*` antwortet `503`;
- der Kontrollframe `store_recovered` wird nicht mehr fälschlich gesendet.

Die Verfügbarkeit wird dadurch ausschliesslich **strenger**: kein Zustand, der
vorher `degraded` war, wird unter dem neuen Modell `ready`. Ein
Lesefehler bleibt weiterhin durch einen erfolgreichen Read heilbar; das ist
direkt getestet. Die Änderung ist in `docs/structured-logging.md` dokumentiert,
wie Abschnitt 17 des Prompts es verlangt.

## B3: Windows-Umgebung — pytest-Basetemp nicht lesbar (vorbestehend)

Auf dieser Maschine ist das pytest-Standardverzeichnis
`C:\Users\user\AppData\Local\Temp\pytest-of-marco` für dieses Konto nicht
lesbar (`PermissionError: [WinError 5]`). Dadurch brechen alle
`tmp_path`-basierten Tests in `tests/unit/test_server_operations.py` bereits im
Setup ab.

Nachweis, dass das vorbestehend und umgebungsbedingt ist: derselbe
Dateilauf aus dem unveränderten W5-R02-C1-Workspace, der auf dem
Binding-Commit `7f1ad1f...` mit leerem `git status` steht, auf derselben
Maschine:

- Standard-Basetemp: `3 passed, 22 errors`
- schreibbares `--basetemp`: `25 passed, 0 errors`

Die Windows-Läufe dieses Runs übergeben daher ein explizites `--basetemp`.
Weder eine Testdatei noch Produktcode noch eine committete Konfiguration wurde
dafür geändert; es ist ausschliesslich ein Pfad des Testrunners. GitHub Actions
ist davon nicht betroffen, da es weder auf dieser Maschine noch unter diesem
Konto läuft. Evidence: `Evidence/08_Windows_Regression/01_windows_regression.txt`.

## Prozessdokumentation nach `docs/.archiv/README.md`

`AGENTS.md` verlangt den Archivprozess vor grösseren Änderungen an Architektur,
öffentlichen Protokollen oder APIs, persistierten Datenformaten,
Sicherheitsgrenzen, Deploymentstruktur oder modulübergreifendem Verhalten.
W5-R02-C3-R1 ändert die Semantik eines internen Health-Bits innerhalb des
bestehenden Canonical-Store-Modells. Öffentliche Protokollformen, Datenformate,
Cursor-Semantik und Endpunktverträge bleiben unverändert; verändert wird
ausschliesslich, *wann* der bereits vorhandene `event_store_unavailable`-Pfad
greift, und zwar in Richtung der bereits dokumentierten Garantie. Die aktuelle
Fachdokumentation wird wie gefordert mitgeführt. Ein eigener Archiv-Aktionsordner
wird daher nicht angelegt — konsistent mit W5-R02-C1 bis C3. Sollte Root Review
das anders bewerten, ist das in einem Folgelauf nachzuholen.

## Secret-Grenze

`P:\GithubRepos\marcosudau-vps\voice-stt-server\secrets\voice-stt.env` liegt
ausserhalb aller Worktrees, wurde für diesen Lauf nicht benötigt und zu keinem
Zeitpunkt gelesen, ausgegeben, kopiert, gehasht, geladen oder archiviert.

## Abgelehnter C3-Workspace

`...\workspaces\ap-srv-070-w5-r02-c3` wurde ausschliesslich lesend verwendet und
steht nach diesem Lauf unverändert auf `d60936c...` mit leerem
`git status --porcelain`. Der Commit wurde weder gemergt noch gecherry-picked
noch als Basis verwendet; `git merge-base --is-ancestor` belegt das in der
Preflight-Evidence.
