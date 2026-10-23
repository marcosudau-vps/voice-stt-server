# AP-KR-020 Fortsetzung – Soll/Ist (Nachtrag 23.10.2026)

Gesamtstatus der Fortsetzung: **CONDITIONAL**.
Die lizenzunabhängigen Runtimekomponenten sind implementiert und synthetisch
qualifiziert; die produktive Lizenzfreischaltung bleibt ohne qualifizierten
Backend und ohne autorisierte Realtests fail-closed auf Community.
Kein REVIEW_READY, kein BLOCKED mehr für die implementierten Anteile.

## Abgleich gegen die zwölf Abnahmekriterien (Stand 22.10.2026)

| Nr. / Soll | Tatsächlicher Stand 23.10.2026 |
| --- | --- |
| 1. Zentrale Runtimeentscheidung | Implementiert: `LicenseRuntimeAuthority` (flüchtig), kalter `bootstrap`, `OwnerSupervisor`, Serververdrahtung. |
| 2. Generationgebundene Lizenzautorität | Implementiert: Generation, opake Credentialrevision, Payloadidentität, TTL; Intentwechsel verwirft atomar. |
| 3. Pro nur nach belastbarem Nachweis | Mechanismus implementiert und fail-closed (`UnqualifiedLicenseVerifier` vergibt nichts); echter Nachweisweg bleibt Folgeauftrag A. |
| 4. Community ohne Key/Pro-Komponente | Implementiert: Startup-Fallback auf manifestiertes Community-Modell, No-op-Bootstrap ohne Payloadroot. |
| 5. Native Prozesswechsel und Fallback | Supervisor implementiert und synthetisch geprüft; ASGI-Besitzerübergabe im Deployment nicht qualifiziert (CONDITIONAL-Anteil). |
| 6. Konsistente serverseitige Modellfreigaben | Implementiert: Gate in `switch_models`, exakte Modell-ID-Bindung, Verweigerung unmanifestierter Modelle. |
| 7. Kein redundanter persistenter Enginezustand | Erfüllt: nur `kroko_force_community` + gewünschte Modelle persistiert; Runtime/`pro_enabled`/`VALID` nirgends persistiert. |
| 8. Settings, Secrets, Statusprojektion | Implementiert: `kroko_force_community` (live, redaktiert), Key-Fingerprints statt Keys, `"license"`-Projektion in `model_lifecycle_status`. |
| 9. Bestehende V2-Contracts | Unverändert: kein Wire-Feld geändert; betroffene Suiten grün (s. Testevidenz). |
| 10. Relevante Tests erfolgreich | 43 neue Fälle grün; betroffene Bestandssuiten grün; volle Unit-Suite s. Testevidenz-Nachtrag. |
| 11. Windows-Testbefund | Unverändert aus 22.10.2026 übernommen (R1-Rückkehrnachweis, deterministische Synchronisation). |
| 12. Übergabe an AP-030 | Geliefert: Bootstrap-, Supervisor-, Lizenzstatus-Verträge (s. Implementierungsnachtrag); native Ergänzung als Folgeauftrag. |

## Was CONDITIONAL statt REVIEW_READY begründet

1. Kein qualifizierter Lizenzverifikations-Backend (Folgeauftrag A) und keine autorisierte Lizenztestumgebung: produktiv ist `VALID` unerreichbar, Pro damit faktisch gesperrt. Das ist beabsichtigtes fail-closed Verhalten, aber kein freigegebener Pro-Betrieb.
2. Die Besitzerprozessübergabe des laufenden ASGI-Dienstes ist als Modul qualifiziert, nicht als Deployment (kein Live-Neustart-, Reconnect- und Lastnachweis).
3. `INVALID`-Semantik (Ablehnung vs. Ablauf vs. Widerruf) ist gegen den echten Anbieter nicht bewiesen; der Typunterschied bleibt im Verifizierer-Interface vorgesehen, nicht belegt.
4. Portal-UUID → manifestierte Modell-ID ist unbestätigt (Übergabe an AP-KR-025).

## Nicht mehr BLOCKED

Der technische Schnittstellenblocker (Arbeitsschritt A) ist durch die
Variantenentscheidung C + spezifiziertes Folge-A geschlossen: Es gibt einen
implementierten, belastbaren Mechanismus für Key → Prüfung → aktuelle
Pro-/Modellfreigabe, dessen produktive Backend-Instanziierung
autorisierungs- und qualifikationspflichtig bleibt. Das ist eine
CONDITIONAL-, keine BLOCKED-Lage.
