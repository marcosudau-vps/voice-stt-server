# AP-SRV-070 / W4B - Soll-/Ist-Vergleich

## Ergebnis

W4B ist im vorgesehenen Scope vollstaendig umgesetzt. Die gemeinsame
serverautoritative STT-Modellverwaltung deckt Faster-Whisper und Kroko ab;
Wake-Word-Assets, Kroko-Native-Builds und W4C-Containerwiring blieben
unveraendert ausserhalb des Arbeitspakets.

## Plan gegen verifizierten Stand

| Planpunkt | Ist-Stand | Nachweis |
| --- | --- | --- |
| Produktfakten und Betreiberabsicht trennen | Vollstaendig. Unveraenderliche `ProductModel`-Eintraege und separat gelesener `OperatorIntent` verhindern das Ueberschreiben von Laufzeit-, Lizenz- und Inhaltsfakten durch Konfiguration. | `VoiceSTT_server/stt_model_management.py`; Autoritaets- und Konfigurationstests |
| Gemeinsame Discovery und billige Validierung | Vollstaendig. Alle konfigurierten Quellen werden vor dem persistenten Default-Store durchsucht; `.part`-Inhalte bleiben unsichtbar; `DISCOVERED`, `VALIDATED` und `LOAD_VERIFIED` sind getrennt. | Discovery-/Precedence-/Staging-Tests |
| Deterministische Recovery und `MINIMUM_READY` | Vollstaendig. Explizite Defaults gehen priorisierten Fallbacks vor, Gleichstaende werden nach stabiler ID aufgeloest, Kandidaten ohne Prioritaet sind kein generischer Fallback und ein Modell kann beide Rollen decken. | Recovery-, Tie-Break-, Rollen- und Stop-Tests |
| Hierarchische Auto-Download-Semantik | Vollstaendig. Global, Engine und Modell werden exakt per OR ausgewertet; harte Produkt-, Rechte-, Laufzeit- und Lizenzgates bleiben unabhaengig bindend. | OR-/Veto-/Eligibility-Tests |
| Verifizierte atomare Bereitstellung | Vollstaendig. Eindeutiges `.part`-Staging, Source-/Groessen-/SHA-256-Pruefung, atomare Aktivierung und zielbezogene Sperren verhindern Teilpublikation und Writer-Races. Schreibgeschuetzte Quellen bleiben lesbar; die Runtime-Wurzel ist Fallbackziel. | Integritaets-, Replacement-, Read-only- und Concurrency-Tests |
| Transaktionaler Refresh und Last-Known-Good | Vollstaendig. Kandidaten-Snapshots werden vor Publikation aufgebaut; fehlgeschlagene Refresh-, Provisioning- oder Scheduler-Aktivierung stellt den vorherigen guten Stand wieder her. | LKG-, Refresh- und Lifecycle-Tests |
| Server-/Engine-Integration | Vollstaendig. Die Service-Registry ist eine Sicht auf dieselbe Modellautoritaet; Engines erhalten ausschliesslich aufgeloeste lokale Pfade. Engine-eigene Netzbereitstellung wurde entfernt. | API-/Scheduler-/Resolver-/Engine-Tests und statischer Callgraph-Check |
| Readiness und Administration | Vollstaendig. STT-`NOT_READY` bleibt eine fachliche Readiness-Aussage; Health und authentifizierte Modell-Admin-Endpunkte bleiben verfuegbar und geben pfadfreie beziehungsweise administrative Diagnostik aus. | Administrierbarkeits- und Health-Tests |
| Kroko Community/Pro-Grenze | Vollstaendig. Modell und Native-Runtime bleiben getrennt; Pro erfordert passende Runtime und Lizenzvoraussetzung, waehrend Secretwerte redigiert werden. W4B ruft keinen Native-Build auf. | Pro-/Secret-/Static-Boundary-Tests |
| Dokumentation und Konfiguration | Vollstaendig. Konservative Defaults, bestehende Settings-/YAML-/CLI-Autoritaet und eine eigene Betriebsdokumentation erklaeren Store, Recovery, Provisioning, LKG und Statusfluss. | `config.yaml`, `docs/stt-model-management.md`, Querverweise |

## Verifikation

- Gezielte W4B- und betroffene Bestands-Suites: bestanden.
- Finale Full Unit Regression: `1478 passed, 14 skipped, 974 subtests passed`,
  `0 failed` in 588,68 Sekunden.
- `python -m compileall -q VoiceSTT VoiceSTT_server api_fastapi_server tests/unit`:
  bestanden.
- `git diff --check`: bestanden.
- Scope-/Artefakt-/Secret-/Download-/Native-Build-Pruefung: bestanden.

## Abweichungen

Es bestehen keine materiellen Abweichungen vom W4B-Plan. Daher ist keine
separate Abweichungsdatei erforderlich. AP-SRV-070 bleibt im Gesamtregister
`In Umsetzung`, weil W4C ausdruecklich nicht Bestandteil dieses Laufs ist.
