# Diagramm-Abgleich ROOT-003 (2026-11-12)

Auftrag: Korrekturauftrag ROOT-003 – 43 Diagrammplanungen vs. tatsächliche Mermaid-Blöcke.

## Zählung (Code: Blockzählung ` ```mermaid ` je Entwurf)

- 42 IDEA-Kapitel: 77 Mermaid-Blöcke (Summe Einzelnachweis unten)
- 13 NOT_REQUESTED-Kapitel mit freiwilligen Diagrammen: 27 Blöcke
  (03.03:2, 03.04:4, 03.06:3, 03.07:3, 03.10:2, 03.11:4, 03.12:2, 04.01:1, 04.02:1, 04.05:1, 04.11:2, 04.12:1, 04.13:1)
- Pilot 02.03 (VERIFIED): 2 Blöcke
- Summe: 77 + 27 + 2 = 106 (stimmt mit ROOT-Feststellung überein)

## Entscheidung

1. Alle 43 Planungen (42 IDEA + 1 VERIFIED) sind umgesetzt: Jedes Brief-Kapitel enthält ≥1 Mermaid-Block; jede Kante ist in der Faktenakte belegt und im unabhängigen Review (Runde 1 + ROOT-002-Nachreview) verifiziert. Status der 42 IDEA-Kapitel wird kontrolliert auf VERIFIED gesetzt (Registry, siehe Änderung unten). Danach: 43/43 VERIFIED, 61 NOT_REQUESTED.
2. Die 27 Blöcke in 13 NOT_REQUESTED-Kapiteln sind freiwillige Zusatzdiagramme (kein Brief). Sie werden NICHT gelöscht (Auftrag: nicht grundlos löschen). Sie bleiben NOT_REQUESTED (kein Brief zu verifizieren), sind aber je im Kapitel-Review mitgeprüft; Zählung hier dokumentiert.
3. Die Behauptung „NOT_REQUESTED ohne Mermaid (0 Mismatches)" im internen Abschlussbericht war falsch und wird hiermit berichtigt (siehe Korrekturabschlussbericht ROOT).

## Einzelnachweis IDEA-Kapitel (Blöcke je Entwurf)

01.02:1, 01.03:1, 01.04:2, 01.05:3, 01.06:1, 01.07:1, 01.09:3, 02.01:3, 02.02:3, 02.04:3, 02.05:3, 02.06:2, 02.07:4, 02.08:4, 03.01:3, 03.02:2, 03.05:2, 03.08:3, 03.09:3, 04.03:1, 04.04:1, 04.06:1, 04.07:2, 04.08:3, 04.09:1, 04.10:2, 05.01:2, 05.03:1, 05.05:1, 05.07:2, 05.08:2, 06.05:1, 06.07:1, 06.10:1, 07.08:1, 07.10:1, 07.11:1, 08.05:1, 08.06:1, 09.03:1, 09.04:1, 09.06:1 (Summe 77).

## Registry-Änderung

- 42× `diagram_status`: IDEA → VERIFIED (kontrolliert, nur dieses Feld; Titel/Pfade/States unberührt).
- Danach `workflow_cli.py refresh` + `validate` (43 Briefs, keine fehlenden Dateien).
