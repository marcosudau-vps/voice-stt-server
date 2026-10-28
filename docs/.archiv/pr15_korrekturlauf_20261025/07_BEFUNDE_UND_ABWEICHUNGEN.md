# Korrekturlauf PR #15 – Befunde und Abweichungen (25.10.2026)

Keine stillschweigende Herabstufung; alte Akte 06 (`pr15_final_abnahmevorbereitung`)
bleibt historisch, Widersprüche werden hier aufgelöst.

## Reviewbefunde → Status

| Befund | Schwere | Status | Nachweis |
| --- | --- | --- | --- |
| H-01 Scope-Baseline | hoch | GESCHLOSSEN | Diese Akte (03–08) als produktweite Soll/Ist-Matrix; alte Akten unverändert |
| H-02 Auto-Prüfung | hoch | GESCHLOSSEN | `KrokoLicenseGate.evaluate/refresh` + Service-Hooks (Init/Refresh/Switch/PATCH/Admin-Route); D1-Tests + R1 live |
| H-03 Key-/Force-Pfad | hoch | GESCHLOSSEN | `kroko.forceCommunity`-Key + Re-Eval-Flow + Neustart-Doku; D1-Tests |
| H-04 Modell-Integration | hoch | GESCHLOSSEN | `license_policy` in `_eligible`/`candidate_eligible`, Policy vor erstem Refresh; D1 + R3 |
| H-05 UUID-Zuordnung | hoch | GESCHLOSSEN | Header-UUID (`read_model_uuid`/`license_uuid_for`), echt belegt, keine Erfindung; D1 + R1 |
| H-06 Runtime-Variante | hoch | GESCHLOSSEN | Community-unter-Pro geöffnet (nativ belegt), Pro strikt + Entitlement; R3/R3b echt; kein Hot-Swap/Supervisor |
| H-07 Lifecycle produktiv | hoch | GESCHLOSSEN | Generationen-Invalidierung, Admission-Gate, LKG-Filter, Ablauf; D1 + R4 |
| H-08 Tests | hoch | GESCHLOSSEN | 23 D1-Tests über echte Kette + R1–R4/R3b live; alter Auto-Check-Negativtest weiter grün (Gate konstruiert ohne Calls) |
| D-01 IST/SOLL | hoch | GESCHLOSSEN | Alle Fachseiten mit Status/Lifecycle aktualisiert |
| D-02 2026-Seite | mittel | GESCHLOSSEN | Historisch-Box, Inhalt unverändert |
| D-03 alte Traceability | hoch | AUFGEHOBEN DURCH SUPERSESSION | Alte 03/06/07/08 unverändert lesbar; diese Akte erklärt ausdrücklich, dass PR15-ARCH-02-PASS nur den verkürzten Scope maß und die Auto-Anforderung bis zu diesem Lauf offen war |
| D-04 Security-Referenz | mittel | GESCHLOSSEN | §4 neu mit Tabelle/Fluss/Grenzen |
| D-05 Key-Semantik | mittel | GESCHLOSSEN | configuration.md-Betreiberabschnitt |
| M-01 Snapshot-Scope | mittel | GESCHLOSSEN | `"scope": "model"`, Enforcement via `pro_enabled_for`; Test |
| M-02 Async/Dedup | mittel | GESCHLOSSEN | Daemon-Threads + Skip-wenn-frisch + pro-UUID-In-Flight; Recognizer unberührt |
| M-03 Request-ID | niedrig | GESCHLOSSEN | Header auf Auth-Fehler + gezielter 401-Assertionstest |
| M-03 Alias-500 | niedrig | GEPRÜFT/KEIN MANGEL | Betreiber-Fehlkonfiguration → 500 korrekt |
| M-03 Host-Dedup | niedrig | GESCHLOSSEN | Import aus `admin.py`; Identitäts-Test |
| M-03 Pruning | niedrig | GESCHLOSSEN | Sweep ab 1024 in `validate()`; Test |
| M-03 Stop-Maskierung | niedrig | GESCHLOSSEN | Lifespan loggt statt zu maskieren; Test mit doppeltem Fehler |

## Offene Restpunkte

- Anbieter-Limits/Reports/Widerruf: bewusst NOT_RUN (Folgeauftrag, dokumentiert).
- Pro-Wheel-Build installierte die Pro-Runtime in diese Dev-Umgebung (außerhalb
  des Repos); CI-Umgebungen bleiben unberührt (Upstream-Free). Lokale
  Vollsuite läuft damit gegen Pro-Runtime (Fakes-basierte Vertragstests
  unberührt; Golden opt-in).
