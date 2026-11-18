# ROOT_REVIEW_READY – 02.03 Activation

Stand: 2026-11-06 · Alle vier ROOT-Korrekturbefunde + §3.3-Zusatz sind korrigiert, unabhängig am Originalcode verifiziert und per Review abgenommen.

## Geprüfter Quellcommit

`a8993c5c68042d996eab680d84a5b138a214bb5d` (feat/v2-release-cleanup). Spiegel-HEAD vor und nach der Korrektur verifiziert (`git rev-parse HEAD`, Arbeitsbaum sauber). Research, Writer und beide Review-Runden liefen gegen denselben Stand. Kein Branch-Wechsel, kein Fetch in bestehende Repos, kein Produktcode angerührt.

## Eingesetzte Subagenten (getrennt, mit Session-IDs)

| Rolle | Agent / Modell | Session | Ergebnis |
|---|---|---|---|
| Orchestrator | doc-orchestrator / Muse Spark 1.3 | diese Session | Koordination, Artefaktsicherung, Registry, Tests |
| Researcher | doc-researcher / DeepSeek V4.1 Flash | ses_e4d4e0c01ffeS8kadbpcIr5xF5 | ROOT-01..04 + §3.3 am Code BESTÄTIGT, Soll-Aussagen, 10 neue Fakten-IDs |
| Writer | doc-writer / DeepSeek V4.1 Flash | ses_e4d47646affeF2i3Nw3z0je1A1 | Kapitel korrigiert + 10 R-Fakten geliefert |
| Reviewer (Re-Review) | doc-reviewer / Muse Spark 1.3 | ses_e4d40ee29ffe1j1gRz7rvdEspS | PASS, alle ROOT-Findings CLOSED, 2 minor non-blocking Findings |
| Reviewer (Fokus-Recheck) | doc-reviewer / Muse Spark 1.3 | ses_e4d3e6529ffexicbNkYUem85Sa | PASS, beide Minors CLOSED |

Keine Selbstabnahme: Der Reviewer prüfte jede Aussage am Originalcode, nicht nur gegen Akte/Bericht.

## Änderungen (Kapitel + Nachweise)

- **ROOT-01 (V1-Timings):** Drei-Wege-Darstellung V1-Legacy (kein Controller, Werte wirkungslos trotz `hello.activationConfig`) / V1-Controlled (Query→Konstruktor, sitzungsstabil, keine Policy) / V2 (Registry-Latch, keine Query). Falschbehauptung „nur Defaults" in §3.12, §5.1, §6.5 beseitigt. Neue Fakten R-01, R-02.
- **ROOT-02 (Replay-Garantie):** Falschaussage „nach Disconnect dieselbe commandId → alte Wahrheit, nie zweite Activation" ersetzt durch sitzungsgebundene Idempotenz (`commandHistory: session`, Clear nur in `close()`), neue Session nach Disconnect (frische UUID), Resync-Empfehlung, `clientRunId`-Klarstellung. Neue Fakten R-03, R-03b.
- **ROOT-03 (V2-source):** Gefährliche Migrationsanweisung ersetzt: V2-`activate` verlangt `source: "manual"` (fehlend/`wake_word` → `invalid_payload` ohne Effekt); V2-Controls verbieten `source`; `wake_word` nur serverintern; V1-Abgrenzung (`invalid_source`). Neue Fakten R-04, R-04b, R-04c.
- **ROOT-04 (Controller-Existenz):** Geltungsbereich kontrollierter Modus vorangestellt (§1, §2); Legacy-Pfad dokumentiert (kein Controller, Recorder-Policy `legacy`, Follow-up-Fenster Default 0.0=aus, synthetische IDs, Zeitwerte wirkungslos). Universelle „pro Sitzung"-Pauschale beseitigt. Neue Fakten R-05, R-06.
- **§3.3-Zusatz:** `controlled_activation_disabled`/`session_closed`/`stream_not_started` getrennt von `audio_unavailable`; V2-Projektion (erste drei → `internal_error`); §6.1-Tabelle um 3 Zeilen erweitert. Neue Fakten-ID R-07.
- **2 Minor-Fixes:** terminale `closing_input --> [*]`-Kante (A-37) + Erläuterungssatz; Warnfenster-Tabellenzelle um Kreuzregel-Verweis ergänzt.
- **Faktenakte** `workflow/research/02.03.json`: 66 A-Fakten + 10 R-Fakten = 76, `correction_round: 2`, pretty-printed (einzeiliges Format behinderte Subagenten-Reader – kontrolliert umformatiert, Inhalt unverändert übernommen).

## Nachweise und Tests

- Review-Nachtrag Runde 3 in `workflow/reviews/02.03.md` (Runden 1–2 unverändert erhalten, kein stillschweigendes Überschreiben).
- `python -m unittest tests.unit.test_server_activation_controller tests.unit.test_server_activation_commands tests.unit.test_recorder_activation_control` im Quellspiegel → **101 Tests, OK**.
- Diagramm-/ID-Check: 2 mermaid-Blöcke (stateDiagram-v2, sequenceDiagram), 50 Kanten, 39 zitierte Fakten-IDs – alle gegen die Akte auflösbar, keine unbekannten IDs.
- `python tools/workflow_cli.py validate` → **VALIDIERUNG OK** (104 Kapitel / 9 Bereiche / 43 Diagramm-Notizen).
- `python tools/workflow_cli.py status` → PLANNED=103, INTEGRATED=1; alle anderen Kapitel unangetastet.
- Unabhängiges Endurteil: **PASS** (Re-Review) + **PASS** (Fokus-Recheck) gegen Commit `a8993c5c…`.

## Registry-Hinweis

`02.03` bleibt gemäß ROOT-Vorgabe auf **INTEGRATED** (intern angenommen; externe ROOT-Freigabe mit diesem Bericht beantragt). Erfasst: neuer PASS-Vermerk + Abnahme-Evidenz via `workflow_cli.py review`, `correction_round: 2` (kontrolliert ergänzt, CLI besitzt dafür kein Flag – dokumentiert, kein Status-Bypass). Status-Historie: INTEGRATED wurde für die Korrektur nicht verlassen; alle Änderungen sind über Review-Nachtrag, Faktenakte und diesen Bericht belegt.

## Verbleibende Punkte

- Keine offenen Findings: ROOT-01..04, §3.3-Zusatz und beide Minor-Findings sind CLOSED.
- Frühere nicht-blockierende Hinweise (Pilot-Runde 2: §3.3-Formulierung) sind durch die ROOT-Korrektur (§3.3-Neufassung, R-07) gegenstandslos.
- Bekannte Nicht-Blocker aus der Akte (UNKNOWN): kein Test für „v2-activate ohne source" (gleicher Codepfad wie belegter `wake_word`-Fall); Cross-Session-Replay-Isolation nur code-, nicht test-belegt; im Kapitel als Grenzen ausgewiesen.
- Keine Folgekapitel gestartet, kein Merge/Push/Release, keine Produktcode- oder Bestandsdoku-Änderungen.
