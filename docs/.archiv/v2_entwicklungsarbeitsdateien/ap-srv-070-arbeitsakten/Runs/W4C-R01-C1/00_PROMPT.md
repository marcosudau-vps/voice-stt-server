# AP-SRV-070 / W4C — Narrow Correction / Evidence Requalification
## W4C-R01-C1 — Sonnet 5

### Run-Metadaten

- **Modell:** Anthropic Sonnet 5
- **Session:** BESTEHENDE W4C-R01-SESSION WEITERVERWENDEN
- **Session-/Arbeitsordner:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w4c`
- **Bestehende W4C-R01-Akte:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4C-R01`
- **Neue Korrekturakte:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4C-R01-C1`
- **Prompt-Quelle:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prompts\2026-09-06_AP-SRV-070_W4C_R01_C1_SONNET5.md`
- **Erwarteter lokaler W4C-R01-Final-Commit:** `e5f76bf1e4fd28e68624f30140fcf8ec6876db96`
- **Distributed muss weiterhin auf dem W4C-Startstand bleiben:** `fa3c9dc887b0d3930ac0e201b93a4803c308082f`

Dieser Lauf ist **kein neuer W4C-Implementierungsrun**.

Er dient ausschließlich dazu, zwei Root-Review-Findings aus W4C-R01 durch eng begrenzte zusätzliche Evidence zu klären und die W4C-R01-Dokumentation entsprechend zu korrigieren.

## WICHTIGE GIT-GOVERNANCE

`feat/einheitliche-triggerarchitektur-distributed` darf **NICHT** gepusht oder verändert werden.

Der Push auf Distributed erfolgt erst **nach extern vergebenem Root PASS** durch den Koordinator.

Daher in diesem Lauf:

- kein Push auf Distributed;
- kein Force-Push;
- kein Merge;
- kein Rebase veröffentlichter Historie;
- kein Canonical-/main-Update;
- kein neuer Source-Commit, solange die unten beschriebenen Evidence-Probes PASS sind.

Wenn für einen PASS eine Sourceänderung erforderlich wäre: **STOP** und `NOT READY FOR ROOT REVIEW` melden. Keine Codekorrektur eigenmächtig durchführen.

---

# 1. Neue Korrekturakte anlegen

Lege an:

`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4C-R01-C1`

Minimalstruktur:

```text
W4C-R01-C1\
├── 00_PROMPT.md
├── 01_CORRECTION_CONTEXT.md
├── 02_CORRECTION_REPORT.md
├── 03_UPDATED_GATE_STATUS.md
├── 04_FINAL_REPORT.md
└── Evidence\
    ├── 01_Managed_Model_Store_Persistence\
    ├── 02_Graceful_Shutdown\
    └── 03_Git_State\
```

Kopiere diesen Prompt byteidentisch nach:

`W4C-R01-C1\00_PROMPT.md`

Dokumentiere SHA256 von Prompt-Quelle und Prompt-Kopie in `01_CORRECTION_CONTEXT.md`.

Die ursprüngliche Akte `W4C-R01` bleibt erhalten und wird nicht ersetzt.

---

# 2. Ausgangszustand verifizieren

Im bestehenden Workspace:

`P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w4c`

prüfen und dokumentieren:

```text
git status --porcelain
git branch --show-current
git rev-parse HEAD
git rev-parse HEAD^{tree}
git log -1 --oneline
git fetch origin
git rev-parse origin/feat/einheitliche-triggerarchitektur-distributed
```

Erwartung:

- Workspace clean;
- lokaler HEAD ist der bereits erzeugte W4C-R01-Final-Commit
  `e5f76bf1e4fd28e68624f30140fcf8ec6876db96`;
- Remote Distributed ist weiterhin
  `fa3c9dc887b0d3930ac0e201b93a4803c308082f`.

Wenn einer dieser Punkte nicht stimmt: STOP und dokumentieren.

---

# 3. Finding A — G22 Managed Model Store Persistence wirklich nachweisen

Im Root Review wurde G22 zu schwach belegt.

Ein Marker nur direkt unter `/var/lib/voicestt` reicht nicht aus.

## Ziel

Beweise ausdrücklich, dass die **kanonischen verwalteten Model-Store-Verzeichnisse selbst** den Container-Recreate überleben und unter der Production-Non-Root-Runtime schreibbar sind:

```text
/var/lib/voicestt/models/stt/fasterwhisper
/var/lib/voicestt/models/stt/kroko_asr
```

## Vorgehen

Verwende denselben isolierten/disposablen W4C-Smoke-Pfad wie im Originalrun oder einen äquivalenten neuen isolierten Smoke.

Keine echten großen Modelle provisionieren.

Stattdessen:

1. Container mit dem W4C-Production-Compose starten.
2. Sicherstellen, dass beide kanonischen Managed-Store-Verzeichnisse existieren.
3. Als effektiver Runtime-Benutzer bzw. über einen Probeweg, der dieselben Dateirechte testet, jeweils eine kleine nicht-sensitive Testdatei innerhalb beider Verzeichnisse erzeugen.
4. Dateiinhalte und optional Hashes erfassen.
5. Container vollständig recreaten.
6. Danach prüfen:
   - beide Verzeichnisse existieren weiterhin;
   - beide Testdateien existieren weiterhin;
   - Inhalte/Hashes stimmen;
   - beide Verzeichnisse sind weiterhin schreibbar;
   - Container ist danach wieder healthy.
7. Testdateien nach dem Nachweis sauber entfernen, sofern das den Persistenznachweis nicht verfälscht.

## Evidence

Unter:

`Evidence\01_Managed_Model_Store_Persistence\`

mindestens dokumentieren:

- Compose-/Containeridentität des isolierten Smokes;
- Host-/Volume-/Bind-Zuordnung des persistenten Runtime Roots;
- `id` bzw. Runtime User/UID;
- Pfade beider Managed Stores;
- Probe-Dateinamen;
- Inhalt oder SHA256 vor Recreate;
- Recreate-Kommando;
- Inhalt oder SHA256 nach Recreate;
- Schreibbarkeit nach Recreate;
- Health nach Recreate;
- Exit Codes aller relevanten Probes.

Keine privaten Infrastrukturdetails und keine Modellbinärdateien in die Akte kopieren.

## Gate-Bewertung

G22 darf nur PASS sein, wenn diese direkte Evidence vollständig erfolgreich ist.

Falls einer der beiden Stores nicht persistent oder nicht schreibbar ist:

- G22 = FAIL;
- keine Sourceänderung;
- STOP;
- `NOT READY FOR ROOT REVIEW`.

---

# 4. Finding B — Graceful Shutdown stärker nachweisen

Der bisherige W4C-R01-Nachweis zeigte schnellen Exit nach SIGTERM, aber Exit Code 143 allein ist kein ausreichender Beweis für einen vollständig abgearbeiteten Application-Shutdownpfad.

## Ziel

Beweise, dass SIGTERM den Server erreicht und der Server seinen vorgesehenen Shutdown-Lifecycle sauber abarbeitet.

## Vorgehen

Im isolierten W4C-Smoke:

1. Container starten und healthy werden lassen.
2. Serverlog vor Shutdown abgrenzen/markieren.
3. SIGTERM bzw. den vorgesehenen Docker-Stop auslösen.
4. Zeitstempel unmittelbar vor und nach Stop erfassen.
5. Containerstate/Exitcode erfassen.
6. Server-/Containerlogs des Shutdownfensters sichern.
7. Prüfen, ob die Anwendung erkennbare Shutdown-Lifecycle-Signale ausgibt, z. B. vorhandene projektübliche Meldungen wie:
   - Shutdown initiated
   - Shutting down
   - application shutdown
   - cleanup complete
   - server stopped
   - oder äquivalente bereits vorhandene Lifecycle-Logs.
8. Nachweisen, dass kein Timeout/SIGKILL/OOM nötig war.

Wichtig: Keine neuen Shutdown-Logs oder Codeänderungen nur für den Test hinzufügen.

Wenn die Anwendung heute keinen expliziten Lifecycle-Log schreibt, darf ein anderer eindeutiger vorhandener technischer Nachweis verwendet werden, z. B. dass registrierte Shutdown-/Cleanup-Hooks nachweislich ausgeführt wurden. Dieser Nachweis muss konkret sein.

## Evidence

Unter:

`Evidence\02_Graceful_Shutdown\`

mindestens:

- Start-/Healthstatus;
- Stop/SIGTERM-Kommando;
- Zeitstempel;
- relevante Shutdown-Logs;
- Exitcode;
- `docker inspect` State;
- Stopdauer;
- Nachweis kein SIGKILL/Timeout/OOM;
- konkrete Begründung, warum der Application-Shutdownpfad als ausgeführt gilt.

## Bewertung

Wenn nur erneut „Exit 143 + schneller Exit“ vorliegt, ist das Finding **nicht geschlossen**.

Wenn kein eindeutiger Application-Shutdownnachweis ohne Sourceänderung möglich ist:

- als `BLOCKED` kennzeichnen;
- keine Sourceänderung;
- `NOT READY FOR ROOT REVIEW`;
- konkret beschreiben, welche Information fehlt.

---

# 5. W4C-R01-Dokumentation korrigieren

Die Original-Evidence nicht löschen oder umschreiben.

Stattdessen in der neuen Korrekturakte festhalten, welche ursprünglichen Aussagen präzisiert werden.

`03_UPDATED_GATE_STATUS.md` enthält nur die durch diesen Korrekturlauf betroffenen Gates:

| Gate | Original W4C-R01 | C1 Ergebnis | Finaler Stand | Evidence |
|---|---|---|---|---|

Mindestens:

- G22 Managed Model Store Persistence
- G24/G25/G26 Shutdown-Gates, soweit durch Finding B betroffen

Wenn beide Findings geschlossen sind, darf im Korrekturbericht stehen:

`W4C-R01-C1 EVIDENCE COMPLETE — READY FOR EXTERNAL ROOT REVIEW`

Nicht `ROOT PASS`.

Wenn eines scheitert:

`NOT READY FOR ROOT REVIEW`

---

# 6. Git-State Evidence

Unter:

`Evidence\03_Git_State\`

am Ende dokumentieren:

- lokaler HEAD;
- lokaler Tree;
- `git status --porcelain`;
- Remote Distributed SHA nach erneutem Fetch.

Erwartung:

- lokaler Source-HEAD unverändert `e5f76bf...`;
- Workspace source-clean;
- Remote Distributed unverändert `fa3c9dc...`;
- **kein Push wurde ausgeführt**.

Die externe Evidence-Akte darf natürlich neue Dateien enthalten; sie liegt außerhalb des Source-Repositories und erfordert keinen Source-Commit.

---

# 7. Abschlussbericht

`04_FINAL_REPORT.md` soll kurz sein:

## Status

`READY FOR ROOT REVIEW`

oder

`NOT READY FOR ROOT REVIEW`

## Source State

- Local W4C Final Commit
- Local Tree
- Workspace clean
- Remote Distributed SHA
- ausdrücklich: `Distributed push intentionally NOT performed; push is authorized only after external Root PASS.`

## Finding A — Managed Model Store

- PASS / FAIL / BLOCKED
- ein Satz Ergebnis
- Evidence-Pfad

## Finding B — Graceful Shutdown

- PASS / FAIL / BLOCKED
- ein Satz Ergebnis
- Evidence-Pfad

## Gate Corrections

- G22 final
- G24/G25/G26 final

## Source Changes

Erwartung:

`Keine Sourceänderungen in W4C-R01-C1.`

Falls doch Sourceänderung erforderlich wäre, hätte der Run vorher stoppen müssen.

---

# 8. Stop-Regel

Dieser Run ist absichtlich eng.

Nicht:

- Code refactoren;
- Docker-/Compose-Dateien verändern;
- Tests ändern;
- neuen Source-Commit erzeugen;
- auf Distributed pushen;
- W5/W6 beginnen.

Bei echtem funktionalem Fehler nur sauber belegen und stoppen. Die eigentliche Codekorrektur wird danach separat geplant.
