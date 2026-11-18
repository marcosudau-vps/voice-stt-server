# AP-SRV-070 — W1B
# Wake-Word / Loader / Config / Runtime Legacy Cut

## Auftrag

Bereinige ausschließlich die verbliebenen Wake-Word-spezifischen Legacy- und
Kompatibilitätspfade nach AP-SRV-060 und W1A.

W1B soll die durch SRV-060 etablierte kanonische Wake-Word-Architektur
konsolidieren, insbesondere den alten Katalogpfad auf den kanonischen
`WakeWordCatalog` migrieren und danach nachweislich obsolete Altpfade entfernen.

Keine neue Wake-Word-Architektur entwerfen.

---

## Authorities

W0:
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prep\W0\

W1A Evidence:
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W1A\

Pflichtlektüre:
- 2026-08-29_W0_DELTA_REVALIDATION.md
- 2026-08-29_W0_SCOPE_MATRIX.md
- 2026-08-29_W0_EXECUTION_BACKLOG.md
- 2026-08-29_W1A_STATE.md
- 2026-08-29_W1A_SCOPE_TRACE.md

W0 ist `VALIDATED / SCOPE_FROZEN`.

W1A ist abgeschlossen auf:

SHA:
24f3a6e0d321fe02ce3b5aef681380b500db1b81

TREE:
ef239305e55220f8104633abbcad3dcdff1de926

W1B darf nur starten, wenn:
- Remote Distributed HEAD exakt auf diesem W1A-SHA steht
- der vorhandene AP-SRV-070-Worktree clean ist
- Canonical unverändert ist
- keine unerwarteten lokalen Änderungen vorliegen

Sonst:
STATUS: BLOCKED

---

## Git / Worktree

Bestehenden Branch und Worktree weiterverwenden.

Branch:
work/AP-SRV-070

Worktree:
P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070

Keinen neuen Worktree anlegen.

Canonical bleibt unverändert:

c82923fc6ce889b4dfbbde1f9877b8b76481a1e8

Permanent Distributed:
feat/einheitliche-triggerarchitektur-distributed

Vor jeder Mutation:
- `git status` clean
- HEAD == W1A SHA
- Remote Distributed == W1A SHA
- Canonical unverändert

---

# 1. Primärposition W1-04 — Wake Catalog Migration

W0 hat folgende Altarchitektur identifiziert:

Alt:
VoiceSTT/core/openwakeword_catalog.py

Aktuelle bekannte Nutzer:
- VoiceSTT_server/operations.py::WakeWordRegistry
- VoiceSTT/core/wakeword.py

Kanonische Authority:
VoiceSTT/core/wakeword_catalog.py
bzw. der dort etablierte `WakeWordCatalog`.

Verbindlicher Ablauf:

1. Alle direkten und indirekten Nutzer von `openwakeword_catalog.py` ermitteln.
2. Verhalten und Verträge der Altaufrufer vollständig verstehen.
3. Auf den kanonischen `WakeWordCatalog` migrieren.
4. Tests anpassen/ergänzen.
5. Erst wenn keine Runtime-Reachability mehr besteht:
   `openwakeword_catalog.py` löschen.
6. Nach Löschung erneut repo-weit nach Altimports/-symbolen suchen.

Kein bloßes Import-Renaming, wenn sich Semantik oder Return-Strukturen
unterscheiden.

---

# 2. SRV-060 ist normative Wake-Word-Authority

Folgende Architektur darf W1B nicht aufweichen oder neu erfinden:

- OpenWakeWord Assets lokal gebündelt
- models.json als kanonische Asset-/Katalogbasis
- ONNX + TFLite Backendpfade
- kein Runtime-Download für die produktive Wake-Word-Architektur
- server-authoritative Wake-Lifecycle
- atomare Admission
- selected-only Initialisierung
- Sensitivity / minConsecutivePredictionFrames
- server-authoritative cooldown
- server-authoritative pre-roll
- exactly-one Detection
- safe boundary
- paralleles WW-Tracking
- first qualified region to close wins
- deterministic tie-break
- cached score != new prediction frame
- Backendwahl gemäß SRV-060
- globalDisabledIds
- Settings-Snapshot/Event-Konsistenz

Falls eine geplante Legacy-Entfernung einen dieser Verträge gefährdet:
NICHT entfernen.
STATUS: BLOCKED mit genauer Begründung.

---

# 3. Wake-spezifische Legacy-/Runtime-Bereinigung

Nach der W1-04-Migration gezielt nach verbliebenen Wake-spezifischen Altpfaden
suchen, aber nur entfernen, wenn ihre Obsoleszenz gegenüber W0/SRV-060
nachweisbar ist.

Prüffelder:

- alte Loader
- doppelte Katalog-/Modellauflösung
- obsolete Runtime-Download-Pfade
- alte Detection-/Trigger-Brücken
- stale Config-Mirrors
- veraltete Resource-Resolution
- doppelte Backendauswahl
- Altpfade, die den kanonischen models.json-Katalog umgehen

Für jeden Remove-Kandidaten mindestens prüfen:

1. Symbol-/Pfadsuche
2. direkte Caller
3. indirekte Registrierung/Dispatch
4. Reflection/dynamische Imports
5. Side Effects
6. Tests
7. Docs/Config

Nur nach beweisbarer Nichterreichbarkeit löschen.

Keine breit angelegte "Aufräumaktion" außerhalb des Wake-Word-Bereichs.

---

# 4. KEEP_REQUIRED / Nicht anfassen

W1A hat folgende Kompatibilitätsanker geschützt.
W1B darf sie nicht als vermeintlichen Legacy-Code entfernen:

- `activation_config.mode == "legacy"`
- `_compat_final_context`
- `_start_wakeword_followup_window`
- `_trigger_ack`
- v2→v1-Bridge `_apply_activation_command`

Insbesondere `_start_wakeword_followup_window` ist trotz Wake-Namens nicht
automatisch W1B-Remove-Scope.

Außerdem OUT_OF_SCOPE:
- AudioToTextRecorderClient
- allgemeines Protocol-/Session-Redesign
- Packaging / Versionssystem
- Docker / Deployment
- Release-Automation
- große Dokumentationsreorganisation
- Client-Produktcode

---

# 5. Runtime Downloads

Die kanonische produktive Wake-Word-Architektur muss nach W1B vollständig ohne
spontane Runtime-Downloads funktionieren.

Prüfen:
- Catalog
- Backend Initialization
- Asset Resolution
- models.json
- ONNX
- TFLite
- Pipeline Assets
- VAD Asset

Falls alte Downloadpfade ausschließlich historische/optionale Nicht-Produktpfade
sind, nicht blind löschen; zuerst Reachability und aktuellen Vertrag prüfen.

---

# 6. Tests / Adversarial Gates

Mindestens gezielt prüfen:

- WakeWordCatalog
- Catalog aliases
- backend selection
- selected-only initialization
- globalDisabledIds
- settings → wake runtime
- refresh
- `/api/v2/wake-words`
- session wake lifecycle
- wake admission
- cooldown
- pre-roll
- first-qualified-region semantics
- parallel wake words / tie-break
- stale callback / refresh seams
- resource resolution
- no-runtime-download behavior

Bestehende SRV-060 Root-Regressions müssen grün bleiben.

Insbesondere relevante Suiten aus:
- `test_wakeword_catalog*`
- `test_wakeword_root_findings_*`
- `test_wakeword_session_e2e`
- `test_server_operations`
- weitere direkt betroffene Tests

Nach gezielten Tests:
- vollständige relevante Wake-/Operations-/Recorder-Regression
- soweit vertretbar vollständige Unit-Suite
- `git diff --check`

Für echte entfernte/behobene Legacy-Semantik RED-FIRST, wo ein echter Defekt
oder alter Vertrag existiert.

Keine künstlichen RED-Tests für bereits korrektes Verhalten.

---

# 7. Kalibrierung

Falls weiterhin kein echtes positives Wake-Audio vorliegt:

Status bleibt ausdrücklich:

EVIDENCE_BLOCKED / calibration pending

Keine synthetische oder indirekte Evidenz als reale Wake-Kalibrierung ausgeben.

---

# 8. Scope-Hygiene

Vor Commit prüfen:

- keine Packaging-Änderungen
- keine Docker-Änderungen
- keine Release-Automation
- keine W2-Doku-Reorganisation
- keine Client-Änderungen
- keine unnötigen Format-/Whitespace-Großdiffs
- keine lokalen Pfade / Secrets / temporären Artefakte

Nur unmittelbar betroffene aktive Vertragsdoku darf korrigiert werden, wenn sie
durch W1B sonst objektiv falsch würde.

---

# 9. Commit / Distributed

Bei vollständigem PASS:

Genau EIN unveränderlicher Agentenrun-Commit.

Subject:

feat(wakeword): remove legacy runtime paths

Danach erfassen:
- Parent SHA
- Commit SHA
- TREE
- git status
- Remote Distributed before/after
- Canonical SHA

Remote Distributed muss vor Push noch auf W1A stehen.

Push ausschließlich als Fast-Forward auf:

feat/einheitliche-triggerarchitektur-distributed

Kein Force-Push.
Kein Amend eines bereits publizierten Run-Commits.

Canonical bleibt unverändert.

---

# 10. Evidence

Schreibe unter:

P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W1B\

mindestens:

- 2026-08-29_W1B_IMPLEMENTATION_REPORT.md
- 2026-08-29_W1B_TEST_REPORT.md
- 2026-08-29_W1B_SCOPE_TRACE.md
- 2026-08-29_W1B_STATE.md

STATE muss mindestens enthalten:

- Status
- W1A Parent SHA
- W1B SHA/TREE
- W1-04 Ergebnis
- migrierte/entfernte/erhaltene Wake-Pfade
- SRV-060 Invarianten erhalten
- Tests
- Calibration Status
- Distributed before/after
- Canonical unchanged
- W2 readiness

---

# Stop-Gates

STATUS: BLOCKED wenn:

- Distributed nicht auf W1A SHA steht
- Worktree unerwartet dirty ist
- Canonical verändert wurde
- W0/W1A Evidence fehlt oder widersprüchlich ist
- ein Remove-Kandidat noch Runtime-reachable ist
- SRV-060-Vertrag durch die Änderung geschwächt würde
- Asset-/Backendpfade nicht mehr deterministisch sind
- Tests rot sind
- Force-Push notwendig wäre
- Scope in W2/W3/W4 driftet

---

## Rückgabe

Schreibe die Evidence unter:

P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W1B\

Schick mir alle Dateien aus diesem Ordner.
