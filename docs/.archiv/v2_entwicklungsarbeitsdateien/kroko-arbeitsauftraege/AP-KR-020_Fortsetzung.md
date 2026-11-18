# AP-KR-020 – Fortsetzung der Unified-Kroko-Runtimeintegration

## Auftrag

Setze das bestehende AP-KR-020 substanziell fort. Nutze die bereits getroffenen Architekturentscheidungen und die neu gewonnenen Erkenntnisse zur Kroko-Lizenzprüfung.

Ziel ist eine tatsächlich implementierte, möglichst vollständig qualifizierte gemeinsame Community-/Pro-Runtime. Die noch offenen Fragen zur Lizenzschnittstelle sollen gezielt geklärt werden, dürfen aber die davon unabhängige, bereits beschlossene Implementierungsarbeit nicht unnötig blockieren.

Arbeite systematisch, quellenbasiert und mit klarer Trennung zwischen nachgewiesener Funktionalität, implementierter aber noch nicht real qualifizierter Funktionalität und tatsächlich ungelösten Voraussetzungen.

## Repository und bestehender Entwicklungsstand

Repository:

`P:\GithubRepos\marcosudau-vps\voice-stt-server`

Integrationsbranch:

`feat/v2-unified-kroko`

Bestehender AP-020-Branch:

`feat/v2-unified-kroko-ap020`

Bestehender Draft-PR:

<https://github.com/marcosudau-vps/voice-stt-server/pull/12>

Letzter bekannter AP-020-HEAD:

`b6e5f11dbd6415648de3a309bbeddc9fa2ae4723`

Abgenommener AP-010-Integrationsstand:

`acdffc7042357cb8ae5e47961e42b78a25bd902c`

Unabhängiger Modellkatalog:

<https://github.com/marcosudau-vps/voice-stt-server/pull/13>

Letzter bekannter Katalog-HEAD:

`58a85b7df0e414bff59b66789748077c0f7ff559`

PR #13 hat bereits erfolgreiche Windows-/Linux-CI, ist aber zum Zeitpunkt der Auftragserstellung noch nicht gemergt.

Prüfe die tatsächlichen Stände zu Beginn. PR #13 niemals eigenmächtig mergen. Falls seine Übernahme noch nicht erfolgt ist, darf AP-020 unabhängig davon weiterentwickelt werden.

Bestehende Branchhistorie nicht unnötig umschreiben. Keine eigenmächtigen Merges, Releases oder Deployments.

## Verbindliche Pflichtlektüre

Lies zuerst:

- `AGENTS.md`
- `build/BUILD.md`
- `docs/.archiv/kroko_unified_runtime_v2/2026-10-22_GESAMTPLAN.md`
- `docs/.archiv/kroko_unified_runtime_v2/AP-KR-010/2026-10-22_ARCHITEKTURENTSCHEIDUNG.md`
- `docs/.archiv/kroko_unified_runtime_v2/AP-KR-010/2026-10-22_UEBERGABE.md`
- `docs/.archiv/kroko_unified_runtime_v2/AP-KR-020/2026-10-22_SCHNITTSTELLEN_LIFECYCLE.md`
- `docs/.archiv/kroko_unified_runtime_v2/AP-KR-020/2026-10-22_SOLL_IST.md`
- `docs/.archiv/kroko_unified_runtime_v2/AP-KR-020/2026-10-22_UEBERGABE_AP030.md`

Nutze die vorhandenen Erkenntnisse und Testergebnisse. Keine umfangreiche Wiederholung bereits abgeschlossener AP-010-Experimente.

## 1. Neue Evidenz zur Lizenzprüfung berücksichtigen

Seit dem bisherigen AP-020-Abschlussbericht wurde ein unabhängiger Python-WebSocket-Test erfolgreich durchgeführt.

Mit einem echten On-Premise-Lizenzschlüssel und der konkreten Pro-Modell-UUID

`c529370f-77c7-4348-b5dc-2e9fcda1a568`

wurde eine positive Antwort erhalten.

Die bereinigten Ergebnisse:

- `allowed: True`
- `remaining_seconds: 86400`
- `max_connections: 2`
- `offline_timeout: 60`
- `report_interval: 15`
- `expirable: False`
- `password_present: True`

Das belegt die technische Möglichkeit einer modellbezogenen Prüfung ohne zuvor gestarteten Recognizer.

Es belegt nicht:

- Eine pauschale Berechtigung für alle Pro-Modelle.
- Eine modellunabhängige Keyvalidierung.
- Eine dauerhaft gültige Lizenzfreigabe.
- Eine garantierte Widerrufserkennung.
- Einen offiziell dokumentierten öffentlichen Drittanbieter-API-Vertrag.

Analysiere anhand des gepinnten Upstream-Commits

`8657e655192623b98d7708e742a72987f953d3a2`

die vorhandene Lizenzimplementierung und das reale Antwortverhalten.

Insbesondere:

- Übereinstimmung von Portal-UUID und nativer Modellheader-ID.
- Verbindung zwischen Lizenzprüfung und Modellaktivierung.
- Auswirkungen paralleler Verbindungen und Reporter.
- Statusaktualität, Offlineverhalten und Wiederholungsregeln.
- Modellbezogene statt globale Berechtigungen.
- Differenzierung von Ablehnung, Netzwerkfehler, Ablauf und Widerruf.
- Sicherer Umgang mit Lizenzpasswörtern und Secrets.

Weder unbekannte Anbietersemantik erfinden noch interne Protokollfelder ungeprüft als stabilen Produktvertrag behandeln.

Keine weiteren Live-Lizenzservertests ohne ausdrücklich freigegebenen Testumfang.

## 2. Technisch tragfähige Lizenzintegration entscheiden

Vergleiche gezielt:

A. Eine schmale, versionierte Ergänzung des bestehenden nativen Lizenzclients.

B. Eine isolierte modellbezogene Lizenzprüfung mit eigener, ausdrücklich geprüfter Lebensdauer und Statusbindung.

C. Soweit sinnvoll, die Nutzung des bestehenden nativen Lizenzmechanismus innerhalb der späteren Besitzerprozessgeneration.

Bewerte insbesondere Singletonverhalten, Thread-Sicherheit, Modellrechte, Reporter, Offlinefristen und spätere Widerrufe.

Wähle die technisch am besten begründbare Variante.

Falls der externe Anbieter keine vollständige Statussemantik garantiert, beschreibe die konkrete Nachweisgrenze und eine konservative fail-closed Umsetzung. Keine stillschweigend unbeschränkt gültigen Lizenzfreigaben.

Die Produktentscheidung lautet weiterhin:

`pro_enabled = api_key_present AND NOT force_community AND license_validation_successful`

Aktive Runtime und `pro_enabled` werden abgeleitet und niemals redundant persistiert.

## 3. Lizenzunabhängige Runtimekomponenten implementieren

Wichtig: Auch wenn die Lizenzschnittstelle noch nicht vollständig qualifiziert ist, sollen unabhängig davon festgelegte technische Komponenten tatsächlich entwickelt werden.

Dazu gehören, soweit anhand der AP-010-Architektur eindeutig umsetzbar:

- Kalter Bootstrap vor sämtlichen nativen Kroko-Imports.
- Auswahl exakt eines privaten Native-Payloadroots.
- Erkennung fremder oder bereits geladener inkompatibler Native-Runtimes.
- Ein nativeimportfreier Launcher beziehungsweise Supervisor.
- Genau eine aktive Native-Besitzerprozessgeneration.
- Kontrolliertes Beenden mit bestätigtem Prozessende.
- Neuer Prozess bei Runtime-, Key- und berechtigungsrelevantem Modellwechsel.
- Startdeadline und begrenztes Retry-/Backoff-Verhalten.
- Technisch sicherer Community-Fallback.
- Generationgebundene Invalidierung alter Status- und Jobmeldungen.

Verwende in automatisierten Tests synthetische Lizenzautoritäten und Prozessfixtures, um Zustandsübergänge und Fehlerfälle deterministisch zu prüfen.

Eine synthetische Lizenzautorität ist ausschließlich Testinfrastruktur und darf niemals als produktiver erfolgreicher Lizenznachweis wirken.

Unvollständige Lizenzintegration muss produktiv fail-closed bleiben.

Vermeide ungenutzte Gerüste und spekulative Abstraktionen. Implementiere nur Teile, die bereits durch den abgenommenen Architekturvertrag hinreichend bestimmt sind.

## 4. Runtime-, Modell- und Settingsintegration

Integriere die nachweisbar umsetzbaren Bestandteile in die vorhandene Serverarchitektur:

- Zentrale flüchtige Lizenz- und Runtimeautorität.
- Generation und opake Credentialrevision.
- Konkrete Modellberechtigungen.
- Community bei fehlendem Key oder erzwungenem Communitymodus.
- Pro nur bei aktueller positiver Berechtigung.
- Bestehende Settings-Control-Plane und Secretverwaltung.
- Serverweiten `force_community`-Zustand.
- Konsistente finale und Realtime-Modellwahl.
- Schutz vor alten Job-, Session- und Readinessergebnissen.
- Redigierte Statusprojektion ohne Lizenzgeheimnisse.

Keine Änderung am V2-Wire-Protokoll ohne ausdrückliche bestehende Spezifikation.

Community-Modelle dürfen auch unter der aktiven Pro-Runtime verwendet werden, soweit technische Kompatibilität nachgewiesen ist. Daraus darf keine Pro-Lizenzgültigkeit abgeleitet werden.

Der Community-only-Default darf nicht heimlich durch ein Pro-Prüfmodell ersetzt werden.

## 5. Schnittstelle zur vorbereiteten AP-KR-030-Paketierung

Es existiert bereits eine lokale Vorimplementierung:

`P:\GithubRepos\marcosudau-vps\voice-stt-server-ap030-lab`

Sie enthält die vorbereitete Trennung von Community-Basisdistribution und optionalem Pro-Payloadaddon.

Nutze ihre dokumentierten Verträge lesend, soweit erforderlich.

Die bestehende LAB-Arbeit darf nicht überschrieben, umstrukturiert oder erneut implementiert werden.

AP-020 muss präzise liefern, welche Bootstrap-, Native-API-, Komponentenidentitäts- und Supervisor-Verträge die spätere offizielle Übernahme benötigt.

Falls eine native Schnittstellenergänzung notwendig wird, sind Patchrevision, Native-Provenienz, Fingerprints und Plattformartefakte entsprechend den bestehenden Buildregeln zu aktualisieren.

## 6. Verbindliche V2-Folgearbeit: automatischer Modelldownload

Der dynamische Kroko-Modellkatalog und automatische Modelldownload gehören ausdrücklich zum geplanten V2-Release.

Die eigentliche Downloadimplementierung ist nicht Bestandteil dieses AP-020, sondern wird in einem separaten Folgearbeitspaket vorgesehen:

**AP-KR-025 – Dynamischer Modellbezug und automatische Provisionierung**

Geplante Reihenfolge:

AP-KR-020 → AP-KR-025 → offizielles AP-KR-030 → V2-Releasequalifikation.

AP-KR-025 soll auf dem bereits entwickelten Katalog aus PR #13 aufbauen und insbesondere abdecken:

- Automatische Auswahl und Beschaffung von Kroko-Modellen.
- Verwendung vorhandener vertrauenswürdiger Modellmetadaten.
- Untersuchung eines direkten, möglichst On-Premise-Key-basierten Live-Katalogzugangs.
- Nutzung des vorhandenen bereinigten Katalogs, falls kein unabhängiger Live-Zugang nachgewiesen werden kann.
- Direkte Downloadquellen und sichere Redirectbehandlung.
- Explicit-Opt-in beziehungsweise ausdrücklich gewollte Modellinstallation.
- Autoritative SHA-256-/Größenprüfung und sichere atomare Provisionierung.
- Unterscheidung zwischen Anbieterredistributierung, Betreiberdownload und Lizenzberechtigung.
- Keine ungeprüfte Freischaltung zusätzlicher Modelle.
- Vollständige Integration in bestehende Modellverwaltung und Tests.

Der V2-Release soll eine benutzbare automatische Modellinstallation bieten. Umfang und unterstützte Modelle müssen auf tatsächlich nachgewiesenen Integritäts-, Zugriffs- und Rechteverträgen beruhen.

Falls wesentliche Voraussetzungen nicht erfüllbar sind, ist dies ausdrücklich als Releasehindernis beziehungsweise offene Produktentscheidung zu dokumentieren – nicht stillschweigend aus dem V2-Umfang zu streichen.

Implementiere in AP-020 keinen zweiten Modellkatalog und keinen neuen Downloader. Halte jedoch die spätere Integration architektonisch möglich.

## 7. Qualität und Tests

Führe gezielte automatisierte Tests und anschließend die relevanten bestehenden Testsuiten aus.

Besonders zu berücksichtigen:

- Kein Key / Community erzwungen.
- Pro-Berechtigung positiv und negativ.
- Unbekannte oder unzureichend bestätigte Berechtigung.
- Modellberechtigung nur für konkret bestätigte IDs.
- Veraltete Generationsergebnisse.
- Fehlendes Pro-Addon.
- Fataler Native-Exit.
- Timeout und Community-Fallback.
- Wechsel von Key, Modus und Modell.
- Session-/Jobinvalidierung.
- Unveränderte V2-Reconnect- und Terminalverträge.
- Bestehende Modellintegritäts- und Provisionierungsgrenzen.

Kennzeichne strikt, welche Fälle durch synthetische Tests bestätigt sind und welche echte Native-, Lizenz-, Windows-/Linux- oder Clientnachweise benötigen.

Keine grünen Tests oder simulierten Antworten als echten Lizenznachweis ausgeben.

## 8. Dokumentation und Übergabe

Pflege die AP-020-Akte gemäß `AGENTS.md` und den bestehenden Archivregeln.

Dokumentiere:

1. Neue Erkenntnisse gegenüber dem bisherigen BLOCKED-Stand.
2. Technische Entscheidung zur Lizenzschnittstelle.
3. Tatsächlich implementierte Komponenten.
4. Noch fehlende Lizenz- oder Nativeverträge.
5. Reproduzierbare Tests und Nachweise.
6. Benötigte Übergabeinformationen für AP-KR-025 und AP-KR-030.
7. Offene Risiken und Qualifikationsgrenzen.

Historische Originalakten nicht stillschweigend umschreiben; notwendige neue Erkenntnisse als datierte Nachträge dokumentieren.

Nutze weiterhin den bestehenden AP-020-Branch und Draft-PR #12.

Kein eigenständiger Merge, kein Release, kein Deployment und keine Änderung am geschützten V2-Zielbranch.

## Arbeitsprinzip

Die fehlende vollständige Lizenzqualifikation darf nicht zur pauschalen Einstellung sämtlicher Implementierungsarbeit führen.

Arbeite alle technisch ausreichend entschiedenen, unabhängig umsetzbaren Bestandteile ab.

Gleichzeitig darf kein fehlender Lizenznachweis durch Annahmen, unqualifizierte Freigaben oder Fake-Ergebnisse ersetzt werden.

Liefere einen konkreten implementierten Stand und einen nachvollziehbaren Abschlussstatus:

- REVIEW_READY, wenn der Auftrag vollständig umgesetzt und prüfbereit ist.
- CONDITIONAL, wenn wesentliche Implementierungen vorliegen, aber klar benannte Realnachweise noch fehlen.
- BLOCKED, nur für tatsächlich verbleibende technische Voraussetzungen, die eine sichere Fortsetzung konkret verhindern.

Beginne mit der Bestandsprüfung und setze anschließend die bereits entschiedenen Arbeitsschritte praktisch um. Keine erneute breite Machbarkeitsuntersuchung und keine unnötigen Rückfragen für bereits festgelegte Entscheidungen.
