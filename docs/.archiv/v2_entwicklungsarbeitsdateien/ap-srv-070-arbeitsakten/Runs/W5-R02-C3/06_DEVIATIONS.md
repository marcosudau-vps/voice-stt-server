# AP-SRV-070 / W5-R02-C3 — Deviations

Keine bekannten W5-R02-C3-Abweichungen.

Alle 32 Pflicht-Gates sind erfüllt, der Plan lag vor der ersten getrackten
Änderung vor, und der Umsetzungsumfang entspricht exakt dem geplanten
RC-A-Pfad (eine einzige Testdatei, keine Produktionsänderung).

Zwei unerwartete Befunde traten während der Diagnose auf. Beide sind keine
Abweichungen vom Auftrag — sie wurden innerhalb des Auftrags gefunden,
belegt und aufgelöst —, werden hier aber nach Abschnitt 21 des Prompts
festgehalten, weil sie für nachfolgende Läufe relevant sind.

## B1: Die C2-Deutung des faulthandler-Dumps war nicht tragfähig

W5-R02-C2 schloss aus dem Fehlen eines `/ws/logs`-Frames im Thread-Dump auf
einen verlorenen Wakeup in der `starlette.testclient`/`anyio`-Portal-Schicht.
Diese Deutung ist widerlegt: eine suspendierte Coroutine erscheint
grundsätzlich in keinem faulthandler-Dump. Der Handler wartete korrekt in
`await websocket.receive_text()` auf einen `subscribe`-Frame, den der Test
niemals sendet. C2 hatte diesen Punkt selbst ausdrücklich als "reasoned
inference, not a proven root cause" gekennzeichnet; C3 hat ihn geprüft und
korrigiert, statt ihn zu übernehmen.

Beleg: `03_ROOT_CAUSE_REPORT.md` §3.3, `Evidence/03_Harness_Control_Matrix/02_control1c_hang_faulthandler_stack.txt`.
Auswirkung: keine auf das Ergebnis von C2 — dessen Ordering-Korrektur bleibt
gültig und wird unverändert übernommen. Korrekturlauf erforderlich: nein.

## B2: `faulthandler.dump_traceback_later(exit=True)` beendet auf diesem
CPython-Build mit Status 0

Ein Watchdog-Abbruch liefert hier Exit-Code 0, nicht 1. Ein Messaufbau, der
allein am Exit-Code klassifiziert, hätte Hänger als bestandene Läufe gezählt.

Beleg und Gegenmaßnahme: `Evidence/03_Harness_Control_Matrix/01_control_matrix_results.txt`
(Abschnitt "NOTE ON CLASSIFICATION"). Der Treiber wertet einen Versuch nur
dann als PASS, wenn der abschließende `"result": "PASS"`-Datensatz vorliegt,
kein faulthandler-Timeout-Banner erschien und der Exit-Code 0 ist. Die erste
control1b-Kampagne wurde unter dem korrigierten Klassifikator wiederholt und
zusätzlich unabhängig nachgeprüft (0 von 100 Logs mit Timeout-Banner, 100 von
100 mit abschließendem PASS-Datensatz).

Die Pflicht-Stresskampagnen nach Abschnitt 18 sind von dieser Frage nicht
betroffen: sie laufen über `pytest` unter `timeout --signal=ABRT`, wo ein
Hänger sowohl am Rückgabecode als auch am `Fatal Python error: Aborted` im
Log erkannt wird — beide Kriterien werden ausgewertet.

Auswirkung: keine auf die berichteten Ergebnisse. Korrekturlauf erforderlich:
nein.

## Prozessdokumentation nach `docs/.archiv/README.md`

Die Regel aus `AGENTS.md` greift für Änderungen an Architektur, öffentlichen
Protokollen oder APIs, persistierten Datenformaten, Sicherheitsgrenzen,
Deploymentstruktur oder modulübergreifendem Verhalten. W5-R02-C3 ändert
ausschließlich eine Unit-Testdatei; kein Produktverhalten, kein Protokoll,
kein Datenformat und keine öffentliche Schnittstelle wird berührt. Ein
Archiv-Aktionsordner wird daher nicht angelegt — konsistent mit der
Handhabung in W5-R02-C1 und W5-R02-C2.

## Secret-Grenze

Die Betreiber-Secret-Datei
`P:\GithubRepos\marcosudau-vps\voice-stt-server\secrets\voice-stt.env` liegt
ausserhalb aller Worktrees, wurde für diesen Lauf nicht benötigt und zu keinem
Zeitpunkt gelesen, ausgegeben, kopiert, gehasht oder in die Umgebung geladen.

## C2-Workspace

`...\workspaces\ap-srv-070-w5-r02-c2` wurde ausschliesslich lesend verwendet
(`git status --porcelain`, `git rev-parse`, `git diff`, `sha256sum`). Es wurde
dort nichts verändert und nichts committet. Die dortige unkommittierte
Teilkorrektur ist unangetastet und liegt zusätzlich wortgleich als Evidence
unter `Evidence/01_C2_Evidence_Review/01_c2_uncommitted_diff.txt`.
