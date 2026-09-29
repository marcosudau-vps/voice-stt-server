# V2-Segment-Activation-Korrelation – Plan (Nachtrag, 29.09.2026)

**Status dieses Dokuments:** Nachträgliche Dokumentation einer bereits
erfolgten Implementierung (PR #3, Branch `fix/v2-segment-correlation`).
Keine rückwirkende Umschreibung historischer Auditdateien; dieser Nachtrag
kennzeichnet transparent den bereits umgesetzten Stand inklusive
Review-Folgehärtung.

**Datum:** 29.09.2026
**Ausgangsstand:** `70c46235bd74ad464626ed39b3c1e42df57ab9b0`
(`origin/feat/einheitliche-triggerarchitektur-distributed`)
**Zielbranch:** `fix/v2-segment-correlation` → PR #3 gegen
`feat/einheitliche-triggerarchitektur-distributed` (Stack-Basis für
`fix/v2-realtime-identity`)

## Ausgangslage

VoiceSTT lässt eine neue Activation zu, sobald die Eingabe der älteren sicher
geschlossen ist; deren Final-Transkription kann im Hintergrund weiterlaufen.
`_on_transcription_start()` besaß den korrekten unveränderlichen
`SegmentContext`, gab dessen Korrelationsfelder beim
`_publish_timeline_event("transcription_started", …)` aber nicht mit.
`_publish_timeline_event()` füllte sie via `_activation_correlation()` aus dem
aktuellen Vordergrund auf, `EventProjector._remember_segment()` übernahm die
falsche Zuordnung.

## Ziele

1. Die drei Timeline-Publikationen `recording_started`, `recording_ended`,
   `transcription_started` tragen ausdrücklich die Felder des zugehörigen
   `SegmentContext` (`activationId`, `activationSequence`, `segmentSequence`,
   `requestId`); Context vor Verlassen der Synchronisationsgrenze lokal sichern.
2. Erste bestätigte `(segmentId, activationId, segmentSequence)` im
   `EventProjector` bleibt autoritativ; spätere Widersprüche werden nicht
   übernommen, sondern diagnostizierbar gezählt (`segment_mismatches()`).
3. Review-Folgehärtung: Auch die erstmalige Segmentzuordnung übernimmt keine
   fremde Vordergrund-Activation als autoritative Identität (nur explizite
   Payload-Activation bestätigt); ohne hinreichende Segmentidentität kein Event
   mit erfundener Activation.
4. Regressionstests: Background-Overlap (A1/S1+S2, S2-Transkription verzögert
   nach A2), Projektor-Invariante (später Überschreibversuch, fehlende
   Identität, erstmalige Fremd-Übernahme), Normalbetrieb (Aufnahme/Ende/Final,
   zwei serielle Segmente).
5. Aktive Fachdokumentation (V2-Kurzreferenz, Chronologie, Triggerarchitektur)
   auf denselben Stand bringen; historische Audits unverändert lassen.

## Nicht-Ziele

- Keine Änderung an `ActivationController`, V2-Wire-Schema, Command-Namen/
  Result-Codes, Realtime-Worker, Recovery/Close-Mechanik, Scheduler,
  V1-Verhalten oder `SegmentContext`-Schema.
- Keine neue Identitätsdatenbank, kein neues Ledger, keine neue
  Protokollreferenz, keine Contract-Vektor-Änderung.
- Keine nebenbei gefundenen Probleme beheben; keine kosmetischen Refactorings.
- PRs nicht selbst mergen.

## Entscheidungen

- Explizite Felder gewinnen in `_publish_timeline_event()` über die
  Vordergrund-Korrelation; Legacy-Fallback bei tatsächlich fehlendem Context
  bleibt erhalten.
- Projektor-Diagnose als In-Memory-Zähler, kein persistentes Audit-Event.
- Dokumentations-Nachtrag statt Vorab-Planung, da Implementierung (PR #3,
  CI grün) bereits vorlag; Review-Hinweis wird als gezielte Härtung im selben
  PR ergänzt.

## Betroffene Bereiche

- `api_fastapi_server/server.py` (3 Publikationsstellen)
- `api_fastapi_server/protocol_v2/events.py` (Projektor + Diagnose)
- `tests/unit/test_protocol_v2_races.py`, `test_protocol_v2_e2e.py`,
  `test_server_controlled_e2e.py`
- `docs/client-development/03-server-events-kurzreferenz.md`,
  `04-server-events-katalog-und-chronologie.md`,
  `docs/einheitliche-triggerarchitektur.md`

## Umsetzungsschritte (bereits erfolgt, hier dokumentiert)

1. Reproduktionstests zuerst (Fehlernachweis), dann Fix.
2. Review-Härtung Erstzuordnung + Test.
3. Bestandssuiten (V2-E2E/Races, Controlled-E2E, Ledger, Contract, Docs).
4. Commit/Push auf `fix/v2-segment-correlation` (PR #3 aktualisiert).

## Abnahmekriterien

- Verzögerte Transkription referenziert unter keiner getesteten
  Overlap-Reihenfolge die neuere Activation.
- Projektor ersetzt keine bestätigte Zuordnung und erfindet keine Activation.
- Alle genannten Bestandssuiten grün; PR #3 offen und nur mit Fix-Änderungen.
