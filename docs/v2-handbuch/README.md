# Voice-STT-Server V2 – Handbuch (104 Unterkapitel, intern abgenommen)

> Handbuchstand: alle 104 Kapitel intern recherchiert, unabhängig geprüft (PASS) und integriert (Commit `a8993c5c68042d996eab680d84a5b138a214bb5d`); externe ROOT-Endabnahme am 12.11.2026 erfolgreich (ROOT_PASS). Navigation mit allen 104 Kapiteln – Links unverändert.

## 01 – Einstieg und Systemverständnis

- [01.01 Produktüberblick](01-grundlagen/01.01-produktueberblick.md)
- [01.02 Architekturübersicht](01-grundlagen/01.02-architekturuebersicht.md)
- [01.03 Komponenten und Schichten](01-grundlagen/01.03-komponenten-und-schichten.md)
- [01.04 Gesamter Datenfluss](01-grundlagen/01.04-gesamter-datenfluss.md)
- [01.05 Betriebs- und Funktionsmodi](01-grundlagen/01.05-betriebs-und-funktionsmodi.md)
- [01.06 Serverweite und sitzungsbezogene Ressourcen](01-grundlagen/01.06-serverweite-und-sitzungsbezogene-ressourcen.md)
- [01.07 Identitäten](01-grundlagen/01.07-identitaeten.md)
- [01.08 Technische Grenzen](01-grundlagen/01.08-technische-grenzen.md)
- [01.09 Architekturdiagramme](01-grundlagen/01.09-architekturdiagramme.md)

## 02 – Funktionsweise und interne Abläufe

- [02.01 Session-Management](02-funktionsweise/02.01-session-management.md)
- [02.02 Audioverarbeitung](02-funktionsweise/02.02-audioverarbeitung.md)
- [02.03 Activation](02-funktionsweise/02.03-activation.md)
- [02.04 Wake-Word](02-funktionsweise/02.04-wake-word.md)
- [02.05 Transcription](02-funktionsweise/02.05-transcription.md)
- [02.06 Engines](02-funktionsweise/02.06-engines.md)
- [02.07 Modelle und Modellverwaltung](02-funktionsweise/02.07-modelle-und-modellverwaltung.md)
- [02.08 Scheduler und Nebenläufigkeit](02-funktionsweise/02.08-scheduler-und-nebenlaeufigkeit.md)

## 03 – Einstellungen und Konfigurationssystem

- [03.01 Konfigurationsarchitektur](03-konfiguration/03.01-konfigurationsarchitektur.md)
- [03.02 Scopes](03-konfiguration/03.02-scopes.md)
- [03.03 Benennungskonventionen](03-konfiguration/03.03-benennungskonventionen.md)
- [03.04 Datentypen und Validierung](03-konfiguration/03.04-datentypen-und-validierung.md)
- [03.05 Quellen und Prioritäten](03-konfiguration/03.05-quellen-und-prioritaeten.md)
- [03.06 Server-Einstellungen](03-konfiguration/03.06-server-einstellungen.md)
- [03.07 Session-Einstellungen](03-konfiguration/03.07-session-einstellungen.md)
- [03.08 Runtime-Änderungen](03-konfiguration/03.08-runtime-aenderungen.md)
- [03.09 Wirksamkeitszeitpunkt](03-konfiguration/03.09-wirksamkeitszeitpunkt.md)
- [03.10 Persistenz](03-konfiguration/03.10-persistenz.md)
- [03.11 Secrets](03-konfiguration/03.11-secrets.md)
- [03.12 Abhängigkeiten](03-konfiguration/03.12-abhaengigkeiten.md)
- [03.13 Konfigurationsbeispiele](03-konfiguration/03.13-konfigurationsbeispiele.md)

## 04 – Schnittstellen und Client-Integration

- [04.01 Schnittstellenübersicht](04-schnittstellen/04.01-schnittstellenuebersicht.md)
- [04.02 HTTP-Grundlagen](04-schnittstellen/04.02-http-grundlagen.md)
- [04.03 WebSocket V2](04-schnittstellen/04.03-websocket-v2.md)
- [04.04 Commands/Acknowledgements](04-schnittstellen/04.04-commands-acknowledgements.md)
- [04.05 Audiotransport](04-schnittstellen/04.05-audiotransport.md)
- [04.06 Eventtransport](04-schnittstellen/04.06-eventtransport.md)
- [04.07 Snapshot/Synchronisierung](04-schnittstellen/04.07-snapshot-synchronisierung.md)
- [04.08 Reconnect](04-schnittstellen/04.08-reconnect.md)
- [04.09 Client-Zustandsmodell](04-schnittstellen/04.09-client-zustandsmodell.md)
- [04.10 OpenAI-kompatible API](04-schnittstellen/04.10-openai-kompatible-api.md)
- [04.11 Logzugriff](04-schnittstellen/04.11-logzugriff.md)
- [04.12 Legacy V1](04-schnittstellen/04.12-legacy-v1.md)
- [04.13 Integrationsbeispiele](04-schnittstellen/04.13-integrationsbeispiele.md)

## 05 – Administration, Sicherheit und Berechtigungen

- [05.01 Sicherheitsarchitektur](05-administration/05.01-sicherheitsarchitektur.md)
- [05.02 Serverzugriff](05-administration/05.02-serverzugriff.md)
- [05.03 Admin-Authentifizierung](05-administration/05.03-admin-authentifizierung.md)
- [05.04 Session-Zugriff](05-administration/05.04-session-zugriff.md)
- [05.05 Log-Authentifizierung](05-administration/05.05-log-authentifizierung.md)
- [05.06 OpenAI-API-Authentifizierung](05-administration/05.06-openai-api-authentifizierung.md)
- [05.07 Kroko-Lizenzierung](05-administration/05.07-kroko-lizenzierung.md)
- [05.08 Native-Guard](05-administration/05.08-native-guard.md)
- [05.09 Schutz von Daten/Secrets](05-administration/05.09-schutz-von-daten-secrets.md)
- [05.10 Fehler-/Zugriffsantworten](05-administration/05.10-fehler-zugriffsantworten.md)
- [05.11 Sicherheitsrelevante Betriebsregeln](05-administration/05.11-sicherheitsrelevante-betriebsregeln.md)

## 06 – Installation, Betrieb und Diagnose

- [06.01 Systemvoraussetzungen](06-betrieb/06.01-systemvoraussetzungen.md)
- [06.02 Installationskonzept](06-betrieb/06.02-installationskonzept.md)
- [06.03 Windows-Installation](06-betrieb/06.03-windows-installation.md)
- [06.04 Linux-Installation](06-betrieb/06.04-linux-installation.md)
- [06.05 Docker-Betrieb](06-betrieb/06.05-docker-betrieb.md)
- [06.06 Ersteinrichtung](06-betrieb/06.06-ersteinrichtung.md)
- [06.07 Serverstart/-stopp](06-betrieb/06.07-serverstart-stopp.md)
- [06.08 Datenhaltung](06-betrieb/06.08-datenhaltung.md)
- [06.09 Logging](06-betrieb/06.09-logging.md)
- [06.10 Monitoring und Metriken](06-betrieb/06.10-monitoring-und-metriken.md)
- [06.11 Performance/Ressourcen](06-betrieb/06.11-performance-ressourcen.md)
- [06.12 Fehlerdiagnose](06-betrieb/06.12-fehlerdiagnose.md)
- [06.13 Wartung](06-betrieb/06.13-wartung.md)
- [06.14 Datensicherung](06-betrieb/06.14-datensicherung.md)
- [06.15 Betriebsszenarien](06-betrieb/06.15-betriebsszenarien.md)

## 07 – Entwicklung, Tests, Build und Release

- [07.01 Entwicklungsumgebung](07-entwicklung/07.01-entwicklungsumgebung.md)
- [07.02 Repository-Architektur](07-entwicklung/07.02-repository-architektur.md)
- [07.03 Technische Schnittstellen](07-entwicklung/07.03-technische-schnittstellen.md)
- [07.04 Erweiterungspunkte](07-entwicklung/07.04-erweiterungspunkte.md)
- [07.05 Testarchitektur](07-entwicklung/07.05-testarchitektur.md)
- [07.06 Testverfahren](07-entwicklung/07.06-testverfahren.md)
- [07.07 Packaging](07-entwicklung/07.07-packaging.md)
- [07.08 Native-Kroko-Build](07-entwicklung/07.08-native-kroko-build.md)
- [07.09 CI](07-entwicklung/07.09-ci.md)
- [07.10 Release Candidate](07-entwicklung/07.10-release-candidate.md)
- [07.11 Veröffentlichung](07-entwicklung/07.11-veroeffentlichung.md)
- [07.12 Buildketten-Sicherheit](07-entwicklung/07.12-buildketten-sicherheit.md)
- [07.13 Änderungs-/Kompatibilitätsregeln](07-entwicklung/07.13-aenderungs-kompatibilitaetsregeln.md)

## 08 – Kataloge und technische Referenzen

- [08.01 Event-Katalog](08-referenzen/08.01-event-katalog.md)
- [08.02 Command-Katalog](08-referenzen/08.02-command-katalog.md)
- [08.03 Settings-Katalog](08-referenzen/08.03-settings-katalog.md)
- [08.04 API-Endpunkt-Katalog](08-referenzen/08.04-api-endpunkt-katalog.md)
- [08.05 Zustands-/Phasenkatalog](08-referenzen/08.05-zustands-phasenkatalog.md)
- [08.06 Timing-Katalog](08-referenzen/08.06-timing-katalog.md)
- [08.07 Modell-Katalog-Referenz](08-referenzen/08.07-modell-katalog-referenz.md)
- [08.08 Engine-Referenz](08-referenzen/08.08-engine-referenz.md)
- [08.09 Fehlerkatalog](08-referenzen/08.09-fehlerkatalog.md)
- [08.10 WebSocket-Schema-Referenz](08-referenzen/08.10-websocket-schema-referenz.md)
- [08.11 Logging-Katalog](08-referenzen/08.11-logging-katalog.md)
- [08.12 CLI-/Env-Katalog](08-referenzen/08.12-cli-env-katalog.md)
- [08.13 Daten-/Persistenzschema](08-referenzen/08.13-daten-persistenzschema.md)
- [08.14 Metrik-Katalog](08-referenzen/08.14-metrik-katalog.md)

## 09 – Anhänge und Kompatibilität

- [09.01 Glossar](09-anhaenge/09.01-glossar.md)
- [09.02 Abkürzungen](09-anhaenge/09.02-abkuerzungen.md)
- [09.03 V1-/V2-Unterschiede](09-anhaenge/09.03-v1-v2-unterschiede.md)
- [09.04 Client-Migration](09-anhaenge/09.04-client-migration.md)
- [09.05 Kompatibilitätsverträge](09-anhaenge/09.05-kompatibilitaetsvertraege.md)
- [09.06 Beispielszenarien](09-anhaenge/09.06-beispielszenarien.md)
- [09.07 Quellen/Verifikation](09-anhaenge/09.07-quellen-verifikation.md)
- [09.08 Dokumentationsstand](09-anhaenge/09.08-dokumentationsstand.md)
