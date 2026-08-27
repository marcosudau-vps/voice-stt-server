# AP-SRV-040 – Datierter Soll-/Ist-Vergleich

**Datum:** 2026-08-27

**Status:** alle AP040-Ziele **vollständig umgesetzt / PASS**.

---

## Tabellarischer Vergleich

| Ziel | Ist-Stand | Nachweis | Ergebnis |
|---|---|---|---|
| `/ws/v2` separat | eigenständiger v2-Endpunkt | Run 01 Protokoll v2 Suite, E2E | vollständig umgesetzt / PASS |
| handshake-first | Handshake vor Nutzphase, v2-Vertrag | Run 01, Protocol v2 Suite (161/164 passed) | vollständig umgesetzt / PASS |
| `ProtocolSessionState` | zentrale Zustandsmaschine inkl. `advance_state()` | Run 02 (C2) `stateVersion` suite: 21 passed, 105 subtests | vollständig umgesetzt / PASS |
| canonical UUID ownership | Session-/Aktivierungs-UUIDs kanonisch vergeben | Run 01 Report/Evidence | vollständig umgesetzt / PASS |
| strict command envelope | verschärfte Envelope-Validierung | Run 01, Tests | vollständig umgesetzt / PASS |
| single replay authority | genau eine Replay-Autorität | Run 01, Replay-Tests | vollständig umgesetzt / PASS |
| exhaustive result mapping | vollständiges Ergebnismapping | Run 01, Tests | vollständig umgesetzt / PASS |
| event registry/lifecycle funnel | einheitlicher Event-/Lifecycle-Trichter | Run 01/03, `_dispatch_events()`-Seam | vollständig umgesetzt / PASS |
| `input_closed` exactly once | einmalige Versionierung über `__input_closing__` | Run 02 (C2), stateVersion suite | vollständig umgesetzt / PASS |
| `stateVersion` sichtbare Änderungen | jede sichtbare Zustandsänderung erhöht die Version | Run 02 (C2), 10 Pflichtfälle | vollständig umgesetzt / PASS |
| `eventSeq`/`eventId` | monotone Sequenz und Event-ID | Run 03 (C3), Ordering | vollständig umgesetzt / PASS |
| Mint→Sink event ordering | gemeinsame Linearisierung Projektion/Mint bis Sink | Run 03 (C3), 20/20 ordering | vollständig umgesetzt / PASS |
| snapshot / pendingActivations | Snapshot-Handling inkl. pendingActivations | Run 01, Tests | vollständig umgesetzt / PASS |
| v1 isolation | v1-Verhalten unverändert | Regression SRV030/SRV020 grün | vollständig umgesetzt / PASS |
| SRV050/SRV060 ports | vorbereitete Integrationsstellen | Run 01 Plan/Akten | vollständig umgesetzt / PASS |
| contract vectors | Vertragsvektoren gezogen und erfüllt | Protocol v2 Suite, Vektoren | vollständig umgesetzt / PASS |

## Finale Gesamtvalidierung (C3 / Root-Review)

```text
779 passed
14 skipped
448 subtests passed
C3 event ordering: 20/20 PASS
git diff --check:  PASS
Root-Review C2→C3: PASS, keine offenen Code-Findings
```

## Feststellung

```text
AP-SRV-040 vollständig umgesetzt / PASS.
Keine offene materielle Planabweichung.
Die fünf dokumentierten AP040-Festlegungen sind Vertragsinterpretationen,
keine Planabweichungen (siehe VERTRAGSINTERPRETATIONEN).
```