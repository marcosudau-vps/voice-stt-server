# V2-Segment-Activation-Korrelation – Abweichungen (29.09.2026)

**Datum:** 29.09.2026
**Bezug:** `2026-09-29_PLAN_NACHTRAG.md`, PR #3.

## Materielle Abweichungen

Keine. Die Umsetzung folgt dem (nachträglich dokumentierten) Plan.

## Hinweis (keine Abweichung, bewusste Ergänzung)

- Review-Folgehärtung Erstzuordnung (`_remember_segment()` speichert nur bei
  expliziter Payload-`activationId`, Test
  `test_first_mapping_never_adopts_foreign_foreground_activation`):
  gezielte Absicherung des im Review benannten Fallbacks innerhalb derselben
  PR, kein Planwechsel. Grund: Auch die erste Beobachtung darf keine fremde
  Vordergrund-Activation als autoritativ übernehmen. Auswirkung: strengere,
  weiterhin suite-verträgliche Projektor-Semantik. Status: umgesetzt und getestet.
- Ursprünglich vorgesehene allgemeine Dokumentationskorrekturen außerhalb des
  Fix-Umfangs wurden laut Vorgabe nicht als Abnahmekriterium für PR #3
  behandelt und sind hier nicht enthalten.

## Status

Kein Handlungsbedarf.
