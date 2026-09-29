# V2-Segment-Activation-Korrelation – Soll-/Ist-Vergleich (29.09.2026)

**Datum:** 29.09.2026
**Geprüfter Stand:** Branch `fix/v2-segment-correlation`, Commit
`a57dc1cef888821e1cd4853245d1c0bde3ae0be8` plus Review-Nachbesserung
Erstzuordnung (ungepusht zum Prüfzeitpunkt, danach PR #3-Update).
**PR:** #3 (`fix/v2-segment-correlation` →
`feat/einheitliche-triggerarchitektur-distributed`), Status OPEN, CI zuvor grün.
**Art:** Nachtrag zu bereits erfolgter Implementierung; keine Umschreibung
historischer Dateien.

## Planpunkt → Ist

1. Drei Publikationsstellen mit expliziten Context-Feldern → **umgesetzt**:
   `_on_recording_start` (`recording_context`), `_on_recording_stop`
   (`ended_context`), `_on_transcription_start` (`transcription_context`);
   jeweils `activationId`/`activationSequence`/`segmentSequence`/`requestId`,
   sonst Legacy-Fallback.
2. Projektor-Härtung Überschreibschutz + Diagnose → **umgesetzt**:
   erste Zuordnung autoritativ, Widerspruchszähler
   (`_segment_mismatches`/`segment_mismatches()`).
3. Review-Härtung Erstzuordnung (keine fremde Vordergrund-Activation) →
   **umgesetzt**: `_remember_segment()` speichert nur bei expliziter
   Payload-`activationId`; neuer Test
   `test_first_mapping_never_adopts_foreign_foreground_activation`.
4. Kein Fallback mit erfundener Activation → **umgesetzt**:
   `_segment_fields()` ohne Remember nur bei `segmentSequence` +
   Payload-`activationId`, sonst `None`.
5. Regressionstests A/B/C → **umgesetzt und grün**:
   - `SegmentActivationCorrelationV2Tests` (Overlap, Recording/Accepted/Final
     teilen A1+Sequence),
   - `SegmentActivationCorrelationInvariantTests` (3 Tests inkl. Erstzuordnung),
   - `SegmentActivationCorrelationNoRegressionTests` (Normalbetrieb).
   - Suites: `test_protocol_v2_contract`/`test_protocol_v2_state_version`/
     `test_server_segment_ledger` 108 passed/1 skipped;
     `test_protocol_v2_e2e`-Ausschnitt + `test_server_controlled_e2e`-Ausschnitt
     + `test_docs_surface` 32 passed.
6. Fachdokumentation aktualisiert → **umgesetzt**: `03`, `04`,
   `einheitliche-triggerarchitektur.md` (Unveränderlichkeit über Overlap,
   explizite Context-Felder, Projektor-Autorität, `segment_mismatches()`).
   Links unberührt (keine neuen Links), Beispiele/Schema unverändert.
7. Archiv/Abgrenzung → **eingehalten**: `docs/.archiv/**` historisch
   unverändert, nur dieser neue Aktionsordner ergänzt; `legacy-v1/**` als V1
   belassen; keine neue Protokollreferenz; keine Contract-Vektoren.

## Verifizierung

- Neue Fix-Tests grün; Gegenprobe ohne Fix (Stash) zeigte zuvor FAILED mit
  falscher A2.
- Keine Änderungen außerhalb: `server.py` (3 Methoden), `events.py`
  (Projektor), 3 Testdateien, 3 aktive Dokudateien, dieser Archivordner.

## Ergebnis

Soll vollständig erfüllt; keine offenen Planpunkte. Materielle Abweichungen:
keine (siehe `2026-09-29_ABWEICHUNGEN.md`).
