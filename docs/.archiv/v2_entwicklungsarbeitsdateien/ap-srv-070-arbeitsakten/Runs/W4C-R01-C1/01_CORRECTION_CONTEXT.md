# AP-SRV-070 / W4C-R01-C1 - Correction Context

- **Run-ID:** W4C-R01-C1
- **Typ:** Narrow Correction / Evidence Requalification (kein neuer
  Implementierungsrun)
- **Modell:** Anthropic Sonnet 5 (claude-sonnet-5)
- **Session:** bestehende W4C-R01-Session weiterverwendet
- **Workspace:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w4c`
- **Bestehende W4C-R01-Akte:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4C-R01`
  (bleibt unveraendert erhalten)
- **Neue Korrekturakte:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4C-R01-C1`

## Prompt SHA256

- Quelle: `_workflow-tools/AP-SRV-070/Prompts/2026-09-06_AP-SRV-070_W4C_R01_C1_SONNET5.md`
- Kopie: `_workflow-tools/AP-SRV-070/Runs/W4C-R01-C1/00_PROMPT.md`
- SHA256 (beide identisch): `2c06730cef6b090072b5ebf50d41ef896c1201a3e7d7a17462f765a93d0db169`

## Ausgangszustand (verifiziert)

| Pruefung | Erwartet | Tatsaechlich | Ergebnis |
|---|---|---|---|
| `git status --porcelain` | leer (clean) | leer | OK |
| `git branch --show-current` | `work/ap-srv-070-w4c-r01` | `work/ap-srv-070-w4c-r01` | OK |
| `git rev-parse HEAD` | `e5f76bf1e4fd28e68624f30140fcf8ec6876db96` | `e5f76bf1e4fd28e68624f30140fcf8ec6876db96` | OK |
| `git rev-parse HEAD^{tree}` | (aus W4C-R01: `f3eb03728dd1d0a4d57855a6154430b7142c8995`) | `f3eb03728dd1d0a4d57855a6154430b7142c8995` | OK |
| `git log -1 --oneline` | `e5f76bf AP-SRV-070 W4C: production Docker and deployment` | identisch | OK |
| `origin/feat/einheitliche-triggerarchitektur-distributed` | `fa3c9dc887b0d3930ac0e201b93a4803c308082f` | `fa3c9dc887b0d3930ac0e201b93a4803c308082f` | OK |

Alle Vorbedingungen erfuellt - keine STOP-Bedingung aus Abschnitt 2 des
Prompts liegt vor. Der `git fetch origin` brachte zusaetzlich einen fuer
diesen Lauf irrelevanten neuen Branch
(`handoff/AP-SRV-070-W4AB-C1-dirty-20260901-01a05c77`) sichtbar; das betrifft
weder `feat/einheitliche-triggerarchitektur-distributed` noch diesen
Workspace und wird nicht weiter beachtet.

## Bindende Vorgaben dieses Laufs

- Kein Push auf Distributed, kein Force-Push, kein Merge, kein Rebase
  veroeffentlichter Historie, kein Canonical-/`main`-Update.
- Kein neuer Source-Commit, solange die Evidence-Probes PASS sind.
- Waere fuer einen PASS eine Sourceaenderung noetig: STOP und
  `NOT READY FOR ROOT REVIEW`, keine eigenmaechtige Codekorrektur.
- Die Original-W4C-R01-Evidence wird nicht geloescht oder umgeschrieben; nur
  in dieser neuen Akte praezisiert.
