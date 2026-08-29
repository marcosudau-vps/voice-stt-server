# AP-SRV-040 – Vertragsinterpretationen

**Datum:** 2026-08-27

**Status:** Keine offene materielle Planabweichung.

Diese Akte dient ausschließlich der Nachvollziehbarkeit. Die fünf bereits
dokumentierten AP040-Festlegungen sind **Contract-Interpretationen** und
**nicht** als Planabweichung zu werten:

1. `closing_input` ist kein eigenes Wire-Event; es wird per Snapshot sichtbar.
2. `transcription.cancelled` existiert nicht im Frozen-Katalog; die Projektion
   behandelt es als `discarded` mit reason.
3. Ein nicht-kanonischer `commandId` erhält kein Ack.
4. Ein unbekannter Nachrichtentyp erhält kein Ack.
5. Weitere im Run-01-Report §10 dokumentierte Interpretationen.

Diese Festlegungen sind im Run-01-Report als vertragskonform dokumentiert und
wurden von Root im Rahmen der AP-SRV-040-Abnahme akzeptiert.

Ergebnis:

```text
Keine offene materielle Planabweichung.
```
Eine eigene `ABWEICHUNGEN.md` ist daher nicht erforderlich.