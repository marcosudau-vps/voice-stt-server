# AP-KR-020 – Unified Kroko Runtime: Runtime-, Lizenz- und Modellintegration

## Auftrag

Implementiere die serverseitige Runtime- und Lizenzintegration für die gemeinsame Kroko-Architektur des Voice-STT-Servers V2.

Grundlage sind die Ergebnisse von AP-KR-010 aus Pull Request #11.

Dieses Arbeitspaket implementiert die Laufzeitarchitektur. Die endgültige öffentliche Paketierung, der Release-Candidate-Umbau und die Veröffentlichung sind Gegenstand von AP-KR-030.

Arbeite eigenständig innerhalb dieser Grenzen. Triff erforderliche technische Detailentscheidungen anhand der dokumentierten Evidenz und sichere sie durch Tests ab. Verdecke keine ungelösten Voraussetzungen durch Mocks oder Annahmen.

## 1. Repository und Branches

Repository:
`https://github.com/marcosudau-vps/voice-stt-server`

Integrationsbranch:

`feat/v2-unified-kroko`

Neuer Arbeitsbranch:

`feat/v2-unified-kroko-ap020`

PR-Ziel:

`feat/v2-unified-kroko`

Geschützter übergeordneter V2-Branch:

`feat/einheitliche-triggerarchitektur-distributed`

Prüfe vor Beginn, ob PR #11 vollständig abgenommen und in den Integrationsbranch übernommen wurde.

Beginne ausschließlich vom aktuellen abgenommenen Integrationscommit. Fehlt diese Voraussetzung, keine produktiven Änderungen durchführen und den Blocker berichten. Nicht eigenständig PR #11 mergen.

Keine direkten Änderungen am geschützten V2-Branch.

## 2. Pflichtlektüre

Lies zuerst:

- `AGENTS.md`
- `docs/.archiv/README.md`
- `build/BUILD.md`
- `docs/release-process.md`
- `docs/testing.md`

Danach vollständig:

- `docs/.archiv/kroko_unified_runtime_v2/2026-10-22_GESAMTPLAN.md`
- `docs/.archiv/kroko_unified_runtime_v2/AP-KR-010/2026-10-22_ERGEBNISBERICHT.md`
- `docs/.archiv/kroko_unified_runtime_v2/AP-KR-010/2026-10-22_ARCHITEKTURENTSCHEIDUNG.md`
- `docs/.archiv/kroko_unified_runtime_v2/AP-KR-010/2026-10-22_RISIKEN.md`
- `docs/.archiv/kroko_unified_runtime_v2/AP-KR-010/2026-10-22_UEBERGABE.md`
- `docs/.archiv/kroko_unified_runtime_v2/AP-KR-010/2026-10-22_SOLL_IST.md`

Die dokumentierten Ergebnisse von AP-KR-010 sind die technische Ausgangsbasis. Keine Wiederholung der allgemeinen Machbarkeitsuntersuchung.

Bewahre die ursprünglichen AP-010-Dokumente als historische Evidenz unverändert auf.

## 3. Verbindliche Runtime-Logik

Die Auswahl ergibt sich ausschließlich aus:

- API-Key vorhanden
- Community erzwungen
- Lizenzprüfung erfolgreich

Formel:

`pro_enabled = api_key_present and not force_community and license_validation_successful`

Wenn Pro freigeschaltet ist, wird die Pro-Runtime für Community- und berechtigte Pro-Modelle verwendet.

Andernfalls wird Community verwendet und Pro-Modelle sind nicht auswählbar.

`pro_enabled` und `active_engine` dürfen nicht als redundante persistente Zustandswerte geführt werden.

Ein vorübergehender Prüf-/Lifecycle-Zustand ist erlaubt und notwendig.

Bei fehlendem Key oder erzwungener Community:

- Keine Pro-Initialisierung.
- Keine Lizenzprüfung.
- Status NOT_CHECKED.
- Community-Runtime.

Bei vorhandenem Key und nicht erzwungener Community:

- Pro-Initialisierung/Validierung versuchen.
- Erst nach bestätigter Berechtigung Pro freigeben.
- Bei fehlgeschlagener Prüfung sicher Community starten.
- Keine alten Pro-Berechtigungen restaurieren.

Der bestehende Key-Vertrag einschließlich `KROKO_API_KEY` bleibt erhalten.

## 4. Arbeitsschritt A – Lizenzvalidierung abschließend klären

Dies ist der kritischste offene Punkt aus AP-KR-010.

Der bestehende Kroko-Build führt Lizenzprüfungen erst beim Laden lizenzpflichtiger Modelle aus. Ein Import oder das Laden eines Community-Modells bestätigt keine Pro-Lizenz.

Untersuche gezielt eine robuste Implementierung, die den gewünschten Ablauf unterstützt:

API-Key hinterlegt → Lizenz prüfen → bei Erfolg Pro freigeben.

Dabei darf ein vorhandenes Community-Standardmodell nicht heimlich durch ein anderes Modell ersetzt werden.

Prüfe in dieser Reihenfolge:

1. Vorhandene unterstützte Kroko-Schnittstelle zur Lizenzvalidierung.
2. Minimal erforderliche native Status-/Validierungsschnittstelle, sofern zulässig und robust implementierbar.
3. Isolierte, kurzlebige Prüfprozessgeneration, sofern deren Lizenz- und Modellsemantik nachweislich geeignet ist.

Eine native Schnittstellenerweiterung muss explizit versioniert, fingerprintgebunden und für AP-KR-030 als neuer Buildinput dokumentiert werden.

Keine eigenständige Nachimplementierung des Kroko-Lizenzprotokolls. Keine Interpretation unstrukturierter Konsolenausgaben als verbindlicher Lizenzstatus.

Unterscheide:

- gültige Lizenz,
- autoritativ ungültige Lizenz,
- Netzwerk-/Timeout-/Technikfehler,
- abgelaufene oder widerrufene Lizenz,
- modellbezogene Berechtigungen.

Fehlende Nachweisbarkeit muss zu CHECK_FAILED statt zu einer erfundenen erfolgreichen oder negativen Prüfung führen.

Falls diese Voraussetzung technisch nicht belastbar gelöst werden kann, dokumentiere einen klaren Blocker. Implementiere keine scheinbar fertige Pro-Freischaltung.

## 5. Arbeitsschritt B – Zentrale Lizenzautorität

Implementiere eine serverweite, flüchtige Lizenzstatusverwaltung.

Statuswerte:

- NOT_CHECKED
- CHECKING
- VALID
- INVALID
- CHECK_FAILED

Die Validierung ist gebunden an:

- aktuelle Konfigurationsgeneration,
- opake Credential-Revision,
- verwendete Pro-Komponentenidentität,
- bestätigte Modellberechtigungen,
- Gültigkeitsgrenze beziehungsweise unterstützte Aktualitätsprüfung,
- Lebenszustand des zuständigen Prozesses.

Bei Änderung von Key, Force-Community, Runtime-Komponente oder relevanter Modellberechtigung wird der alte Nachweis atomar ungültig.

Verspätete Prüfergebnisse dürfen keinen bereits widerrufenen Zustand wieder freigeben.

Speichere keine API-Keys, Keyhashes, Entschlüsselungswerte oder Lizenzantworten in Events, Statusantworten oder Logdateien.

Persistente Serverabsicht und flüchtigen Lizenzstatus strikt trennen.

## 6. Arbeitsschritt C – Sicherer Runtime-Bootstrap

Implementiere die Auswahl der Kroko-Runtime vor jedem nativen Import.

Nutze die in AP-KR-010 empfohlene Trennung privater nativer Payload-Verzeichnisse.

Bis AP-KR-030 darf mit explizit bereitgestellten, qualifizierten privaten Testpayloads gearbeitet werden.

Die finale öffentliche Paketstruktur ist noch nicht herzustellen.

Anforderungen:

- genau eine native Runtime pro Besitzerprozess,
- keine globalen Dateikollisionen,
- eindeutige Provenienzprüfung,
- keine Auswahl fremder ausführbarer Runtimepfade durch Clients,
- Konflikterkennung bei bereits importierten Kroko-/Sherpa-Modulen,
- kein Versuch zum Entladen nativer Extensions im laufenden Prozess.

Berücksichtige Server-CLI, Modulstart, Containerstart und direkte Recorder-/Legacy-Einstiege.

Die existierende V2-Initialisierung darf nicht vor der Runtime-Auswahl versehentlich einen Kroko-Recognizer erzeugen.

## 7. Arbeitsschritt D – Prozesswechsel und Fallback

Implementiere einen möglichst kleinen, robusten Lifecycle-Mechanismus.

Der native Besitzerprozess wird bei einem erforderlichen Runtime- oder Keywechsel vollständig ersetzt.

Ein leichter Supervisor/Launcher darf selbst keine Kroko-Runtime importieren.

Anforderungen:

- definierte Startupfrist,
- kontrolliertes Stoppen,
- bestätigtes Prozessende vor einer neuen Generation,
- korrektes Erfassen nativer Exits,
- Community-Fallback nach fehlgeschlagenem Pro-Start,
- Retrybudget und Backoff,
- kein unendlicher Crashloop,
- Readiness erst nach erfolgreicher Initialisierung,
- keine parallelen aktiven Kroko-Runtimes.

Eine kurze Serverunterbrechung beim Wechsel ist zulässig.

Das bestehende V2-Reconnectverhalten und die Terminal-/Sessionsemantik müssen erhalten bleiben.

Laufende oder verspätete Jobs, Events und Modellladeergebnisse müssen generationgebunden behandelt werden.

Ein nativer Exit darf nicht als gewöhnliche Pythonexception vorausgesetzt werden.

Kein zusätzlicher permanenter ASR-Worker, solange dieser nicht zwingend erforderlich ist.

## 8. Arbeitsschritt E – Modellverfügbarkeit

Passe insbesondere an:

- `VoiceSTT/kroko/models.py`
- `VoiceSTT/transcription_engines/kroko_onnx_engine.py`
- `VoiceSTT/transcription_engines/model_resolver.py`
- `VoiceSTT_server/stt_model_management.py`
- `api_fastapi_server/server.py`

Sowie weitere tatsächlich betroffene Komponenten.

Ersetze die bisherige exakte Free-/Pro-Variantenübereinstimmung durch die neue Kompatibilitätslogik:

Community-Runtime:

- Community-Modelle zulässig.
- Pro-Modelle gesperrt.

Pro-Runtime:

- Community-Modelle zulässig.
- Nur bestätigte berechtigte Pro-Modelle zulässig.

Verfügbarkeit, physische Modellinstallation, Integritätsprüfung und Lizenzberechtigung sind unterschiedliche Eigenschaften.

Eine lokal vorhandene Pro-Datei ist kein Lizenznachweis.

Stelle sicher, dass nicht auswählbare Pro-Modelle auch serverseitig nicht durch direkt gesendete Modell-IDs aktiviert werden können.

Bewahre Modellmanifest, SHA-/Größen-/Quellenprüfungen, atomare Provisionierung und das Verbot impliziter Downloads.

Passe Recovery-/Last-Known-Good-Logik so an, dass alte Pro-Berechtigungen nicht wiederhergestellt werden.

Final und Realtime müssen dieselbe Runtime-Autorität verwenden. Bestehende Einschränkungen hinsichtlich mehrerer nativer Pro-Recognizer bleiben verbindlich.

## 9. Arbeitsschritt F – Settings, Secrets und Statusprojektion

Integriere eine serverseitige Einstellung zum expliziten Erzwingen der Community-Runtime.

Die Einstellung ist persistente Serverabsicht, kein Sessionwert.

Verwende die bestehende Settings-Control-Plane mit:

- Revisionen,
- requested/effective-Semantik,
- Persist-before-commit,
- Admin-Autorisierung,
- Restart-Semantik.

API-Keys bleiben im bestehenden geschützten Konfigurations-/Secretpfad und dürfen nicht über öffentliche Settingspatches verfügbar werden.

Admin-Unlock und Pro-Lizenzfreigabe sind unabhängig.

Stelle den verbundenen Clients eine konsistente, redigierte Statusprojektion bereit.

Bevorzuge vorhandene kompatible Server-Statusflächen. Zusätzliche öffentliche HTTP-Felder müssen ausdrücklich dokumentiert und getestet werden.

Keine inkompatiblen Änderungen an bestehenden V2-Wire-Envelopes, Handshake-, Ack-, Event-, Segment- oder Activation-Verträgen.

## 10. Arbeitsschritt G – Identität und Provenienz

Unterscheide:

- unveränderliche Produkt-/Buildidentität,
- installierte Kroko-Komponenten,
- flüchtigen Lizenzstatus,
- abgeleitete Runtime-Auswahl,
- aktuell freigegebene Modelle.

Die installierte Distribution darf nicht mehr automatisch mit der aktiven Kroko-Runtime gleichgesetzt werden.

Bewahre bestehende öffentliche Identitätsfelder und deren Semantik, soweit dies ohne falsche Aussage möglich ist.

Neue Komponenten- und Nativeprovenienz muss später vom Packaging AP-KR-030 vollständig geliefert werden können.

Keine Lizenzinformationen in Source-Commit, Serverversion oder Buildmetadaten kodieren.

## 11. Tests und Regressionen

Implementiere gezielte Tests für:

- Kein Key → Community.
- Community erzwungen → Community, keine Lizenzprüfung.
- Key vorhanden → Pro-Prüfung.
- Gültige Pro-Lizenz → Pro.
- Ungültige Lizenz → Community.
- Timeout/Netzwerkproblem → CHECK_FAILED und Community.
- Pro-Komponente fehlt → Community.
- Pro-Modell fehlt → keine falsche Freischaltung.
- Community-Modell unter Pro.
- Modellberechtigungen und verweigerte Pro-Modell-IDs.
- Keyänderung während einer Prüfung.
- Änderung von force_community während einer Prüfung.
- Verspätete Statusmeldungen alter Prozessgenerationen.
- Nativer Prozessabbruch.
- Prozessneustart und Recovery.
- Bereits laufende Sessions und Jobs.
- Client-Reconnect und unveränderte V2-Vertragsvektoren.
- Secret-Redaktion und Settingsrevisionen.

Trenne Mocks, synthetische Tests und echte native Lizenztests klar voneinander.

Keine gültige Lizenz simulieren und anschließend behaupten, die echte Pro-Lizenzintegration sei qualifiziert.

Echte Lizenztests nur mit ausdrücklich autorisierter Testumgebung. Keine Secrets suchen, erfinden, ausgeben oder committen.

Führe die vollständige relevante Unit-/Contractsuite und die vorhandenen Packaging-/Kompatibilitätstests soweit möglich aus.

### Bekannter CI-Befund aus AP-KR-010

CI-Run:
`https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39807618416`

Windows-Unit-Test:

`tests/unit/test_realtime_streaming_transcription.py::RealtimeWorkerOverlapRaceTests::test_blocked_r1_inference_released_after_r2_start`

Im lokalen `BlockingModel.transcribe()` wird `self.assertTrue()` aufgerufen, obwohl die Hilfsklasse diese Methode nicht besitzt.

Untersuche diesen Befund und korrigiere die Testimplementierung minimal, ohne den eigentlichen Realtime-Produktvertrag abzuschwächen. Erhalte die beabsichtigte Race-Assertion und sorge für deterministische Synchronisation. Dokumentiere Ursache und Regression gesondert.

Keine pauschalen Skips oder Abschwächungen von Assertions.

## 12. Dokumentation

Nutze:

`docs/.archiv/kroko_unified_runtime_v2/AP-KR-020/`

Registriere AP-KR-020 vor produktiven Änderungen gemäß den Repository-Regeln.

Erstelle datierte:

- Implementierungsplanung,
- Schnittstellen- und Lifecycle-Verträge,
- Test- und Evidenzbericht,
- Soll-/Ist-Vergleich,
- Abweichungsakte bei materiellen Abweichungen,
- Übergabe an AP-KR-030.

Aktualisiere die relevante aktuelle Runtime-/Settings-/Modelldokumentation.

Bewahre AP-KR-010 als unveränderte historische Untersuchungsakte.

## 13. Abnahmebedingungen

AP-KR-020 ist vollständig umgesetzt, wenn:

1. Die zentrale Runtime-Entscheidungslogik implementiert ist.
2. Die Lizenzautorität korrekt und generationgebunden funktioniert.
3. Pro nur nach belastbarem Lizenznachweis freigeschaltet wird.
4. Community ohne Key und ohne Pro-Runtime funktioniert.
5. Native Prozesswechsel und Fallback zuverlässig sind.
6. Modellfreigaben serverseitig konsistent durchgesetzt werden.
7. Kein redundanter persistenter Engine-/Freischaltstatus existiert.
8. Settings, Secretverwaltung und Statusprojektion funktionieren.
9. Bestehende V2-Contracts erhalten bleiben.
10. Die relevanten Tests erfolgreich sind.
11. Der bekannte Windows-Testbefund korrigiert und gezielt geprüft ist.
12. Die Übergabe an AP-KR-030 die noch nötigen Packaging-/Buildanpassungen vollständig beschreibt.

Falls mangels autorisierter Lizenzumgebung echte Pro-Tests fehlen, darf das Arbeitspaket höchstens als bedingt qualifiziert gemeldet werden.

Kann der erforderliche Lizenzvalidierungsvertrag nicht robust implementiert werden, melde einen technischen Blocker statt eines unberechtigten COMPLETE.

## 14. Grenzen

- Kein öffentlicher Release oder Deployment.
- Keine Veröffentlichung in PyPI, Docker Hub oder GHCR.
- Keine produktiven Änderungen am VPS.
- Kein Wechsel auf ein anderes Kroko-Upstream-Release ohne begründete Freigabe.
- Keine unautorisierten Lizenzserverexperimente.
- Keine Abschwächung nativer Herkunfts-/Integritätsprüfungen.
- Keine Änderungen an historischen Abnahmeakten.
- Kein Umbau der öffentlichen Release-Pipeline.
- Keine inkompatiblen Client-V2-Protokolländerungen.
- Kein Merge ohne Benutzerfreigabe.
- AP-KR-030 nicht selbstständig beginnen.

## 15. Abschluss und Pull Request

Erstelle einen Pull Request:

`feat/v2-unified-kroko-ap020` → `feat/v2-unified-kroko`

Liefere im abschließenden Chatbericht:

1. Status COMPLETE / CONDITIONAL / BLOCKED.
2. Ausgangscommit und Implementierungscommit.
3. Verwendete technische Lösung.
4. Lizenzprüfungsmechanismus und Nachweisqualität.
5. Runtime-Bootstrap und Prozesswechsel.
6. Modellfreigabe und Statusprojektion.
7. Änderungen an Settings und Secrets.
8. Testergebnisse einschließlich echter/synthetischer Trennung.
9. Bekannte Einschränkungen und verbleibende Risiken.
10. Konkrete Übergabe an AP-KR-030.
11. PR-Link.

Beende die Arbeit mit REVIEW_READY beziehungsweise dokumentiertem Blocker.

Kein eigenständiger Merge, kein Release, kein Deployment und kein Beginn von AP-KR-030.
