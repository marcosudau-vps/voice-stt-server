# Selektive Kroko-V2-Verbesserungen – Soll/Ist vor unabhängiger PR-Abnahme

Datum: 25.10.2026; Basis `feat/v2-unified-kroko` / `d8d6efc`;
Entnahme aus Draft-PR #14, ohne dessen Merge oder Mutation.

| Planpunkt | IST | Nachweisstatus |
| --- | --- | --- |
| Race-Testfix | Korrigierter Test aus PR #14 selektiv übernommen, verspätetes R1-Ergebnis wird ausdrücklich abgewartet | CODEANALYSE; CI ausstehend |
| FastAPI-Lifespan | `service.stop()` über `finally`, Regressionstest mit fehlschlagendem Start | CODEANALYSE; CI ausstehend |
| Effektiver Kroko-Key | Ein zentraler Resolver berücksichtigt Engine- und verschachtelte Recognizer-Optionen sowie Umgebungspriorität | CODEANALYSE; CI ausstehend |
| On-Premise-Lizenz-API | Explizite modell-UUID-bezogene WebSocket-Prüffunktion, fail-closed, keine automatische Verbindung | SYNTHETISCHE TESTS DEFINIERT; echte Providerqualifikation NICHT AUSGEFÜHRT |
| Flüchtiger Lizenzzustand | Separater Status mit Keyrotation, Fristablauf, Modellscope und stale-generation-Abwehr | SYNTHETISCHE TESTS DEFINIERT; nicht produktiv integriert |
| Community-Fallback | Reine deterministische Manifest-Auswahlfunktion, keine Runtime-/Einstellungsänderung | CODEANALYSE; CI ausstehend |

## Beibehaltener Produktvertrag

`STTModelManager` bleibt alleinige Modell- und Last-Known-Good-Authority.
Das bestehende V2-Transportformat, die installierte Free-/Pro-Buildvariante,
CLI, HTTP-Routen, Native-Buildinputs und Release-Fingerprints bleiben unverändert.
Kein Owner-Supervisor, kein Native-Status-Patch, kein automatisch freigeschaltetes
Pro-Modell, keine echten Lizenzkontakte.

## Offene Prüfung

- GitHub Actions auf dem neuen PR für Linux und Windows; nach Lauf Ergebnis
  in einer neuen datierten Ergänzung/PR dokumentieren.
- Qualifizierte echte On-Premise-Lizenztests mit erlaubtem Testzugang,
  modellbezogenem Anspruch, Nutzungsreporting, Connection-Limits und
  Revocation/Refresh sind **NOT_RUN**.
- Integration der API-Prüfung in laufende Serverberechtigungen,
  Force-Community-Settings und automatische Modell-Fallbacks bleibt ein
  **separat abzusichernder Folgeauftrag**.
- Private Dual-Payload-Bootstrap und Scheduler-Probe-Reuse sind nicht Bestandteil
  dieser selektiven Korrektur, weil sie eigene Runtime-/Callback-Lifecycle-
  Verträge brauchen.

Der Status ist vor unabhängiger Abnahme ausdrücklich **Prüfung offen**.
