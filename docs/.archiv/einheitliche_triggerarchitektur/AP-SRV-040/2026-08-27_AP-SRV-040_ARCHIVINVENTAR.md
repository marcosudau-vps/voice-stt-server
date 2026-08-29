# AP-SRV-040 – Archiv-Inventar

**Datum:** 2026-08-27

**Status:** Archivvollständige kanonische Paketakte.

---

## Akten (Top-Level)

| Datei | Rolle | Status |
|---|---|---|
| `2026-08-27_K1_BIS_K4_ENTSCHEIDUNGEN.md` | verbindliche AP040-Entscheidungen | Original (aus Root-reviewed C3 übernommen) |
| `2026-08-27_PLAN.md` | Gesamtplanung | Original (aus C3 übernommen) |
| `2026-08-27_README.md` | Aktions-Übersicht | Original (aus C3 übernommen) |
| `2026-08-27_AP-SRV-040_ABNAHME.md` | Root-Abnahme | Nachträglich erstellt (kanonischer Abschluss) |
| `2026-08-27_AP-SRV-040_UMSETZUNGSVERGLEICH.md` | Datierter Soll-/Ist-Vergleich | Nachträglich erstellt (kanonischer Abschluss) |
| `2026-08-27_AP-SRV-040_VERTRAGSINTERPRETATIONEN.md` | Vertragsinterpretationen (Nachvollziehbarkeit) | Nachträglich erstellt (kanonischer Abschluss) |
| `2026-08-27_AP-SRV-040_ARCHIVINVENTAR.md` | Diese Datei | Nachträglich erstellt (kanonischer Abschluss) |

## Run 01 – Implementierung

| Datei | Rolle | Source/Provenienz | SHA-256 |
|---|---|---|---|
| `runs/01_IMPLEMENTATION/2026-08-27_PROMPT.md` | Auftragsherkunft/Normative Quellen | Original (aus C3 übernommen) | – |
| `runs/01_IMPLEMENTATION/2026-08-27_AP-SRV-040_CANONICAL_CLAUDE_PROMPT.md` | tatsächlich ausgeführter Originalauftrag | byteidentisch aus `_workflow-tools/AP-SRV-040/AUFTRAGSPAKET_ORIGINAL` | `1517755A702A9BF03AA5ABC34002ED453A4EC07934D9B96DEB7046791627CBFE` |
| `runs/01_IMPLEMENTATION/2026-08-27_AP-SRV-040_ROOT_UNBLOCK_FOLLOWUP.md` | tatsächlich ausgeführter Folgeauftrag (Root-Unblock) | byteidentisch aus `_workflow-tools/AP-SRV-040/AUFTRAGSPAKET_ORIGINAL` | `9CD79467BC79330051E87F159FE0EBFCED91C105A2BB6386C34A3D8227FCBEF5` |
| `runs/01_IMPLEMENTATION/2026-08-27_REPORT.md` | Implementierungsreport | Original (aus C3 übernommen) | – |
| `runs/01_IMPLEMENTATION/evidence/2026-08-27_README.md` | Testevidence Run 01 | Original (aus C3 übernommen) | – |

## Run 02 – C2 Root Correction

| Datei | Rolle | Source/Provenienz | SHA-256 |
|---|---|---|---|
| `runs/02_ROOT_CORRECTION/2026-08-27_PROMPT.md` | tatsächlich ausgeführter C2-Korrekturprompt | byteidentisch aus C3-Stand `runs/01_IMPLEMENTATION/AP-SRV-040_ROOT_CORRECTION_C2.md` | `2A74A26BEADA12F4D3929703FC013F2895C87CF7B10684B89DEB7EB0D9601E0F` |
| `runs/02_ROOT_CORRECTION/2026-08-27_REPORT.md` | C2-Report | Original (aus C3 übernommen) | – |
| `runs/02_ROOT_CORRECTION/evidence/2026-08-27_README.md` | C2-Evidence | Original (aus C3 übernommen) | – |

## Run 03 – C3 Root Correction

| Datei | Rolle | Source/Provenienz | SHA-256 |
|---|---|---|---|
| `runs/03_ROOT_CORRECTION/2026-08-27_PROMPT.md` | tatsächlich ausgeführter C3-Codex-Fixprompt | byteidentisch aus `_workflow-tools/AP-SRV-040/AUFTRAGSPAKET_ORIGINAL/AP-SRV-040_C3_FOCUSED.md` | `B0CCCE56920A6BB9D33C38EED010594C1611A914FB6F77C7289681B7082AD343` |
| `runs/03_ROOT_CORRECTION/2026-08-27_REPORT.md` | C3-Report | Nachträglich erstellt (kanonischer Abschluss) | – |
| `runs/03_ROOT_CORRECTION/evidence/2026-08-27_README.md` | C3-Evidence | Nachträglich erstellt (kanonischer Abschluss) | – |

## Candidate/Teststatus über alle Runs

```text
C1: 49a251fa69601494940185e08d360074de2b41e3 (Tree e1461a756da318d0ff979a2b03d38c1f01063fc1)
C2: 5e0361b3279eed311556e3cb42414f264e8c731e (Tree ebc4f1dde2d808b01ef064219ac2b1df9d2533e9, Parent C1)
C3: 6f73a4e347be51d02005e81a0c6be546f036deef (Tree 6d36c2639a199c5bdd10a2c8dc1899d8261caee6)

Final:
779 passed, 14 skipped, 448 subtests passed
C3 event ordering: 20/20 PASS
git diff --check: PASS
pytest exit 0
```

## Zusätzliche Aussagen

```text
01_IMPLEMENTATION.zip wurde bewusst NICHT committed.
Keine Binärartefakte im Git.
Alle byteidentisch kopierten Promptdateien sind als SHA-256 in diesem
Inventar ausgewiesen.
```