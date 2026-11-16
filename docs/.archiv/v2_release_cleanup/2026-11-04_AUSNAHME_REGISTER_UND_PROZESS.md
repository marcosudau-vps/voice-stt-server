# Ausnahme vom Register- und Mehr-PR-Prozess

Datum: 2026-11-04
Aktion: V2 Pre-Release-Cleanup + unabhängige Code-Dokumentation
Aktionsordner: `docs/.archiv/v2_release_cleanup/`

## Registereintrag

Die Projektregeln (`AGENTS.md`, Abschnitt „Größere Änderungsaktionen“)
verlangen einen Eintrag im zentralen Register `docs/.archiv/README.md`. Der
Benutzerauftrag vom 2026-11-04 verbietet ausdrücklich jede Änderung an
bestehenden Markdown-Dateien, ausdrücklich einschließlich der Archiv-
`README.md`. Der Registereintrag wird deshalb **nicht** vorgenommen.

Diese Datei ersetzt den Registereintrag für die Dauer dieser Aktion. Sie ist
eine bewusste, durch den Benutzer verfügte Ausnahme und keine stillschweigende
Abweichung. Eine Nachregistrierung bleibt der unabhängigen Abnahme bzw. einer
späteren, ausdrücklich freigegebenen Archivpflege vorbehalten.

Registerdaten (zur späteren Übernahme):

| Feld | Wert |
| --- | --- |
| Aktion | V2 Pre-Release-Cleanup + V2-Code-Referenz |
| Ordner | `docs/.archiv/v2_release_cleanup/` |
| Branch | `feat/v2-release-cleanup` |
| Basis | `feat/einheitliche-triggerarchitektur-distributed` @ `4f30c0f` |
| Status | In Umsetzung → nach Einreichung `REVIEW_READY`, **nicht** `Abgeschlossen` |

## Prozessabweichungen gegenüber dem historischen Cleanup-Plan (29.10.2026)

1. **Ein Branch, ein Draft-PR** statt getrennter AP-Branches und AP-PRs.
2. **Kein Stopp nach AP-CLN-000**; keine menschlichen Zwischenfreigaben je AP.
3. **AP-CLN-030 ersetzt:** Bestehende Handbücher werden nicht überarbeitet,
   stattdessen entsteht `docs/v2-code-reference/` neu und ausschließlich aus
   Code, Konfiguration und Tests (AP-DOC-V2-100).
4. **Keine vorgezogenen externen Reviews.** Die abschließende unabhängige
   Prüfung, der Merge und jede Veröffentlichung bleiben ausstehend.

Fachliche Sicherheitsgrenzen des Originalplans (keine Protokoll-, Lizenz-,
Native-, Release-Gate- oder Security-Änderungen) gelten unverändert.
