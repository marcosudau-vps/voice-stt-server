# AP-SRV-030 – Archiv-Inventar

**Datum:** 2026-08-27

**Status:** Archivvollständige kanonische Paketakte.

---

## Akten-/Run-Dateien

| Datei | Rolle | Original vs. Provenienznachweis |
|---|---|---|
| `2026-08-25_PLAN.md` | Paketvertrag / Plan | Original (aus Execution-Source übernommen) |
| `2026-08-25_README.md` | Akten-Übersicht | Original (aus Execution-Source übernommen) |
| `ABNAHME.md` | Root-Abnahme | Original (aus Execution-Source übernommen; Root-Abnahme für AP-SRV-030) |
| `2026-08-27_AP-SRV-030_UMSETZUNGSVERGLEICH.md` | Datierter Soll-/Ist-Vergleich | Nachträglich erstellt (kanonischer Abschluss) |
| `2026-08-27_AP-SRV-030_ARCHIVINVENTAR.md` | Diese Datei | Nachträglich erstellt (kanonischer Abschluss) |
| `runs/01_IMPLEMENTATION/2026-08-25_PROMPT.md` | Originalauftrag Run 01 | Original (aus Execution-Source übernommen) |
| `runs/01_IMPLEMENTATION/2026-08-25_REPORT.md` | Implementierungsreport Run 01 | Original (aus Execution-Source übernommen) |
| `runs/01_IMPLEMENTATION/evidence/2026-08-25_README.md` | Testevidence Run 01 | Original (aus Execution-Source übernommen) |
| `runs/02_ROOT_CORRECTION/2026-08-25_REPORT.md` | C2-Korrekturreport | Original (aus Execution-Source übernommen) |
| `runs/02_ROOT_CORRECTION/evidence/2026-08-25_README.md` | Evidence C2 | Original (aus Execution-Source übernommen) |
| `runs/02_ROOT_CORRECTION/2026-08-27_PROMPT.md` | Tatsächlich ausgeführter Root-Correction-Prompt (C2, „EXECUTOR PACKAGE – AP-SRV-030 C2“) | Provenienznachweis, byteidentisch kopiert (nicht redigiert) |
| `runs/03_ROOT_VALIDATION/2026-08-27_REPORT.md` | C3-/CI-Validierungsprovenienz | Nachträglich erstellt (kanonischer Abschluss), reine Provenienz |
| `runs/03_ROOT_VALIDATION/evidence/2026-08-27_README.md` | Evidence C3-Provenienz | Nachträglich erstellt (kanonischer Abschluss) |
| `runs/03_ROOT_VALIDATION/2026-08-27_PROMPT.md` | Tatsächlich ausgeführter C3-Agentprompt (C3-Debug-/Validierungsrunde) | Provenienznachweis, byteidentisch kopiert (nicht redigiert) |

## SHA-256 der byteidentisch kopierten Originalprompts

```text
runs/02_ROOT_CORRECTION/2026-08-27_PROMPT.md
D1797C55693932B41FD178FD34F5D368ABC2D5371377E12B9B655E16BB3351D5

runs/03_ROOT_VALIDATION/2026-08-27_PROMPT.md
DA2E747B821DB1E008DB49CC0FD82483B923AAD3AAC65C95D96E861DA5A7053D
```

Quellen (nicht Teil des Git-Committes):

```text
P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\einheitliche-triggerarchitektur-distributed\docs\.archiv\einheitliche_triggerarchitektur\AP-SRV-030\runs\02_ROOT_CORRECTION\2026-08-25_PROMPT.md
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-030_C3_DEBUG_AGENT\AP-SRV-030_C3_DEBUG_PROMPT.md
```

## Externe CI-/Artifact-Referenzen

```text
GitHub Actions Run:   33028252444
Job:                  98374548213
CI payload:           18f16db87e1b133c42ae9169d8ffc1446adeb847
C3 validation candidate: 1d9a4b26ce04de54c25b7e3afad7f7a96809ec91
C3 validation tree:      a61584db3397f388e3039f69082d5befce025b68
C2 reconstructed in CI:  692caae2ccb62009b0879dc2966e56217f6c1368
required C2 tree:         e6ea688730ac3845d734348878834da87c3caba1
C1→C2 diff SHA256:        2516fb49451db5cf2e172b8eab26842ac5efc72fa4bb3543abf10dcf13f3b9dd
C3 payload SHA256:        88dc1045530ea752b8230eba3dc1343f9e672c51a9dd331b655ac2b8e2c06210
Artifact:                 AP-SRV-030-C3-validation-evidence
Artifact-ID:              9629327610
ZIP SHA256:               15e9257a4009899409099e3211af632595ec00c11d6033ce66790188fb1bb784
```

## Klare Aussage zu Binärartefakten

```text
Keine Binärartefakte im Git.
Dieses Archiv enthält ausschließlich Markdown-Dokumente als Text.
Keine ZIP-/Binär-/Log-/Modell-/Wheel-Dateien wurden committed.
```

Der `01_IMPLEMENTATION.zip`-Scope betrifft die AP-SRV-040-Akte und wurde
dort bewusst nicht committed (siehe AP-SRV-040-Archivinventar).