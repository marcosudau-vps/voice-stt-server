# V2-Realtime-Identitäten – Soll-/Ist-Vergleich (30.09.2026)

**Datum:** 30.09.2026
**Geprüfter Stand:** Branch `fix/v2-realtime-identity` ab `67634572`
(inkl. PR #3 + PR #4), Eigene Commits siehe `git log`.
**Art:** Prüfung des tatsächlich veröffentlichten Stands gegen
`2026-09-30_PLAN.md`.

## Planpunkt → Ist

1. Identität vor Inferenz einfrieren (recording_id, SegmentContext,
   segment_id, Epoche, Startzeiten, Frames; kein Lock während Inferenz) →
   **umgesetzt** in `VoiceSTT/core/realtime.py` (Freeze + Vorher-/Nachher-
   Validierung des Recording-Lebenszyklus).
2. Identität bis Observation mitführen + Pre-Stabilizer-Reject (kein
   `is_recording`-Alleinentscheid; Stabilizer-Semantik erhalten) →
   **umgesetzt** (`_publish_realtime_text` + `observe`-Segmentprüfung
   `wrong-segment`, Callbacks nur für Fremd-/Überholt-Fälle unterdrückt).
3. Sessioncallbacks absichern (strukturiert validiert, kein
   Vordergrund-Fallback; simple an Quelle abgesichert; V1 erhalten; keine
   neuen Wire-Felder) → **umgesetzt** in `server.py`.
4. Projektor-Terminalregel (vor `mint_event`, keine Id/Seq/Lücke,
   Exactly-once unberührt, PR-#3-Korrelation autoritativ) → **umgesetzt** in
   `protocol_v2/events.py` (`_terminal_segments`).
5. Tests A–G deterministisch → **umgesetzt**: Overlap/Stale-Reject,
   Identitätskonsistenz, Interim-nach-Completed/Discarded/Failed,
   Cancel/Sessionabschluss, Normalbetrieb (Outlier/Consensus erhalten),
   PR-#3-Integration (Final-Parallelität, beide Callback-Grenzen).
6. Doku + Archiv → **umgesetzt**: 03/04/05, Triggerarchitektur; Plan,
   Vergleich, Abweichungen; historische Audits unverändert; Links geprüft.

## Verifizierung

- Neue Repro-Tests scheiterten vor dem Fix mit der beschriebenen
  Fehlzuordnung und sind nach dem Fix grün.
- Regressionen: Realtime/Stabilizer, V2-Contract/E2E/Races, Controlled-E2E,
  Multi-User, Docs-Surface (siehe Arbeitsakte).
- Keine Änderungen außerhalb des Auftrags (kein Backpressure, keine Queue,
  kein Scheduler-/Ledger-Redesign, keine Wire-Änderung).
