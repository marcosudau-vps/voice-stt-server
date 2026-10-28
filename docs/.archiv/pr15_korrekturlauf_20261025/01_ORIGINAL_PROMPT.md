# Agentenauftrag – PR #15: Vollständiger Korrekturlauf

## 0. Auftrag und Rolle

Du bist ausschließlich der ausführende Entwicklungs-, Integrations-, Test- und Dokumentationsagent.

Dein Auftrag ist, **Pull Request #15 in einem zusammenhängenden Korrekturlauf** anhand des vorliegenden Reviews zu berichtigen und erneut für eine unabhängige Endabnahme vorzubereiten.

Die Architekturentscheidungen und Prüfziele dieses Auftrags sind verbindlich. Entwickle keine alternative Produktarchitektur, erweitere nicht eigenmächtig den Funktionsumfang und verschiebe festgelegte Anforderungen nicht stillschweigend in spätere Arbeitspakete.

Die bestehende Implementierung ist die Grundlage. Bereits korrekt implementierte Komponenten sind zu erhalten und gezielt zu vervollständigen.

### Verbindlicher Review

https://github.com/marcosudau-vps/voice-stt-server/pull/15#issuecomment-6401918956

Alle darin genannten Befunde H-01 bis H-08, D-01 bis D-05 sowie M-01 bis M-03 sind im Korrekturlauf nachzuverfolgen. Der aktualisierte Review ist maßgeblich; frühere positive Gesamtfreigaben sind überholt.

## 1. Repository und Arbeitsgrenzen

**Repository:** `marcosudau-vps/voice-stt-server`

**Pull Request:** https://github.com/marcosudau-vps/voice-stt-server/pull/15

**Arbeitsbranch:** `work/kroko-v2-selective-improvements-20261025`

**Zielbranch:** `feat/v2-unified-kroko`

**Bei Auftragserstellung bekannter HEAD:** `15d7a89f49bf157cb3b2eb70c2255e001e3cf983`

Prüfe zunächst den tatsächlichen aktuellen HEAD und den Git-Status.

Arbeite ausschließlich auf dem existierenden Branch von PR #15.

Nicht erlaubt sind:

- Merge, Rebase oder Force-Push.
- Änderungen an PR #12 oder PR #14.
- Änderungen am Zielbranch oder an `main`.
- Änderungen an nativen Kroko-Buildinputs oder Fingerprints.
- Änderungen am bestehenden V2-WebSocket-Wire-Vertrag.
- Eigenmächtige Erweiterung des Persistenzschemas um Secrets.
- Deployment oder Neustart des produktiven VPS-Dienstes.
- Markierung von PR #15 als „Ready for Review“.
- Eigenständige technische Abnahme oder Mergefreigabe.

## 2. Verbindliche Zielanforderung

Die zentrale Security-Komponente muss vier voneinander getrennte Bereiche koordinieren:

1. Admin-Authentifizierung.
2. OpenAI-API-Authentifizierung.
3. Sitzungstoken und Berechtigungen für Logzugriffe.
4. Kroko-Pro-Lizenzprüfung und deren Integration in die Pro-Freigabe.

Die ersten drei Bereiche sind im vorhandenen PR bereits umgesetzt und müssen kompatibel bleiben.

**Der vierte Bereich ist funktional zu vervollständigen.**

### Gewünschter automatischer Ablauf

Bei Serverinitialisierung und bei einer unterstützten Änderung des effektiv verwendeten Kroko-Keys wird der Berechtigungszustand automatisch neu ermittelt.

Die Entscheidungslogik lautet:

```text
Kein API-Key vorhanden
    → Community

Community ausdrücklich erzwungen
    → Community

API-Key vorhanden und Community nicht erzwungen
    → Lizenzprüfung

Lizenz gültig
    → Pro freigegeben

Lizenz ungültig oder Prüfung fehlgeschlagen
    → Community
```

`pro_enabled` ist dabei ein **abgeleiteter Laufzeitzustand**, keine eigenständig persistierte Benutzeroption.

Eine gültige Pro-Lizenz soll gemäß der festgelegten Produktlogik die Auswahl der Pro-Modelle freigeben.

Die tatsächliche Modellverfügbarkeit, lokale Provisionierung und Kompatibilität mit der installierten nativen Runtime sind weiterhin gesonderte technische Voraussetzungen.

Es darf keine positive Freigabe aus dem bloßen Vorhandensein eines Schlüssels abgeleitet werden.

## 3. Vorbereitende Codeprüfung

Lies zunächst vollständig:

```text
AGENTS.md

docs/.archiv/README.md

docs/.archiv/kroko_unified_runtime_v2/
    2026-10-22_GESAMTPLAN.md

docs/.archiv/kroko_unified_runtime_v2/AP-KR-010/
    2026-10-22_ARCHITEKTURENTSCHEIDUNG.md
    2026-10-22_UEBERGABE.md

docs/.archiv/kroko_v2_selective_improvements/
    2026-10-25_PLAN.md
    2026-10-25_UMSETZUNGSVERGLEICH.md

docs/.archiv/server_modularization_20261025/
    2026-10-25_PLAN.md
    2026-10-25_UMSETZUNGSVERGLEICH.md

docs/architecture/server-modularization-roadmap.md
docs/server-authentication.md
docs/openai-http-api.md
docs/stt-model-management.md
docs/kroko-onnx.md
docs/configuration.md
docs/testing.md

build/BUILD.md
```

Lies außerdem den vollständigen aktuellen PR-Diff.

Erstelle vor der Implementierung eine Soll-/Ist-Matrix zu sämtlichen Reviewbefunden.

### Maßgebliche Codebereiche

```text
api_fastapi_server/security/
    __init__.py
    service.py
    admin.py
    openai.py
    logs.py
    kroko.py

api_fastapi_server/server.py
api_fastapi_server/settings_control.py
api_fastapi_server/openai_routes.py

VoiceSTT/kroko/
    credentials.py
    license_api.py
    license_state.py
    models.py

VoiceSTT/assets/kroko/models.json

VoiceSTT_server/stt_model_management.py
VoiceSTT_server/openai_compat.py

VoiceSTT/transcription_engines/
    kroko_onnx_engine.py
```

Die vorhandene `SecurityService`-Struktur ist zu behalten.

## 4. Implementierung A – Automatischer Lizenz-Lifecycle

### A1. Zentrale Authority

Verwende den vorhandenen `SecurityService` und `KrokoLicenseGate`.

Es darf keinen zweiten, konkurrierenden Lizenzzustand im `VoiceSTTService`, Modellmanager oder Router geben.

`KrokoLicenseState` bleibt die zentrale flüchtige Statuskomponente. Erweiterungen müssen über nachvollziehbare, kleine Schnittstellen erfolgen.

### A2. Automatische Prüfung

Implementiere die automatische Prüfung an den tatsächlich relevanten Lebenszyklusstellen:

- Serverinitialisierung.
- Unterstützte Änderung des effektiven Kroko-Keys.
- Änderung des Force-Community-Modus.
- Explizit ausgelöste erneute Prüfung nach einem Fehler oder Ablauf.

Die Prüfung muss vor einer positiven Pro-Freigabe stattfinden.

Keine Lizenzserveranfrage, wenn kein Key vorhanden ist oder Community erzwungen wird.

Verhindere unnötige Doppelprüfungen beim selben unveränderten Schlüssel und unveränderten Berechtigungszustand.

Synchroner Netzwerk-I/O darf nicht den ASGI-Eventloop blockieren.

### A3. Effektiver Key

Benutze ausschließlich die bestehende Authority:

`VoiceSTT.kroko.credentials.effective_recognizer_key`

Die bereits vorhandene Priorität einschließlich `recognizer.key` bleibt unverändert.

Ein explizit leerer verschachtelter Key darf nicht versehentlich durch einen Umgebungs-Key ersetzt werden.

Berücksichtige Änderungen über die bestehenden unterstützten Konfigurations- und Modellverwaltungswege.

Eine Änderung der Prozessumgebung außerhalb des laufenden Prozesses ist kein automatisch eintreffendes Ereignis. Dokumentiere deshalb die tatsächlichen Wege, über die ein Key-Wechsel erkannt wird, beziehungsweise einen notwendigen Neustart.

### A4. Force Community

Ergänze einen serverweiten booleschen Betreiberwunsch `force_community` in der bestehenden Settings-Authority.

Verwende dafür die vorhandenen serverseitigen Konfigurations- und Persistenzmechanismen.

Keine Session-lokale Schatteneinstellung.

Keine neue Credentials-Datenbank.

Die Force-Einstellung darf persistiert werden; Lizenzstatus und abgeleitetes `pro_enabled` dürfen es nicht.

Erhalte die bestehenden Admin-Berechtigungsregeln.

### A5. Zustands- und Nebenläufigkeitsschutz

Prüfe und implementiere:

- Keywechsel invalidiert alte Nachweise sofort.
- Keyentfernung invalidiert Pro-Freigabe sofort.
- Force Community invalidiert Pro-Freigabe sofort.
- Verspätete Prüfantworten dürfen keine Freigabe wiederherstellen.
- Überlappende Prüfungen dürfen sich nicht gegenseitig falsch bestätigen.
- Negative Antworten, Timeouts und Transportfehler führen zu keiner Pro-Freigabe.
- Ablauf eines Nachweises darf nicht unbemerkt einen dauerhaft gültigen Zustand hinterlassen.
- Erneute Prüfung muss möglich sein, ohne einen veralteten Status wiederzuverwenden.

Der bestehende generationsgebundene Statusmechanismus ist möglichst weiterzuverwenden.

## 5. Implementierung B – Modellfreigabe

Die bisherige isolierte Lizenzprüfung muss tatsächlich mit dem vorhandenen `STTModelManager` zusammenarbeiten.

### B1. Modell-Authority erhalten

`VoiceSTT_server/stt_model_management.py` bleibt alleinige Authority für Modellverfügbarkeit, Auswahl, Last-Known-Good, Provisionierung und Modell-Lifecycle.

Die Security-Komponente liefert ausschließlich den Berechtigungszustand.

Eine zweite Modellregistrierung innerhalb von `SecurityService` ist untersagt.

### B2. Pro-Freigabe integrieren

Pro-Modelle dürfen über den automatischen Berechtigungsweg nur bei gültigem, aktuellem Lizenzstatus ausgewählt und geladen werden.

Prüfe und sichere beide Pfade:

- `_eligible`
- `candidate_eligible`

Berücksichtige außerdem tatsächliche Modell-Load-Probes, Refresh, Recovery, Modellwechsel, Final- und Realtime-Lane sowie den vorhandenen Last-Known-Good-Mechanismus.

Verhindere, dass ein Pro-Modell vor der Berechtigungsentscheidung versehentlich bereits durch den Modellmanager geladen wird.

Eine erfolgreiche Lizenzprüfung soll die vorgesehenen Pro-Modelle freischalten. Der tatsächliche Modellladevorgang darf trotzdem nicht auf ein fehlendes, beschädigtes oder zur installierten Runtime inkompatibles Modell zugreifen.

### B3. Modellidentifikation

Prüfe, wie die Lizenzprüfung die konkrete vom Lizenzdienst erwartete Modell-UUID erhält.

Die vorhandenen Produktmodell-IDs, Modellnamen und technischen Modellidentitäten sind sauber zu unterscheiden.

Nutze eine tatsächlich nachweisbare Zuordnung aus den vorhandenen technischen Modellinformationen beziehungsweise der realen Integration.

Keine erfundenen Modell-UUIDs.

Ergänze erforderliche Zuordnungen ausschließlich in der zuständigen Kroko-Modell-Authority.

### B4. Installierte Runtime

Die bestehende Produktarchitektur verwendet zwei vollständige alternative Distributionen:

- `voice-stt-server`
- `voice-stt-server-pro`

Diese bestehende Build- und Paketarchitektur bleibt erhalten.

Die automatische Lizenzentscheidung darf nicht fälschlich behaupten, dass ein bereits installierter Free-Native-Build allein durch einen Key zu einer Pro-Runtime geworden sei.

Implementiere die automatische Pro-Freigabe innerhalb der tatsächlich verfügbaren und passenden Runtime.

Community-Fallbacks müssen mit dieser Runtime technisch kompatibel sein.

Prüfe insbesondere die bisherigen strikten Variantenregeln in `models.py` und `STTModelManager`.

Wo eine Community-Nutzung mit installierter Pro-Runtime technisch unterstützt wird, muss die Modell-Eligibility das korrekt abbilden. Belege das durch echte Modelltests.

Wo die Native-Runtime einen gewünschten Wechsel nicht unterstützt, darf der Agent keinen gefährlichen Hot-Swap oder eigenständigen Prozess-Supervisor erfinden.

Der technische Zustand muss in diesem Fall korrekt und ohne vorgetäuschte Bereitschaft dargestellt werden.

## 6. Implementierung C – Weitere Reviewbefunde

Bearbeite die Befunde aus dem verlinkten Review vollständig.

Besonders zu berücksichtigen:

- `KrokoLicenseState.public_snapshot()` darf keine globale Freigabe vortäuschen, wenn nur ein eingeschränkter Zustand nachgewiesen wurde.
- Bestehende Secret-Redaktion muss bei allen neuen Status-, Fehler- und Auditpfaden wirken.
- Lizenzprüfung und Native-Recognizer dürfen nicht durch unnötige wiederholte Initialisierungen belastet werden.
- Fehlende oder nicht ladbare Community-Modelle dürfen keine falsche Ready-Meldung erzeugen.
- Native Fehler dürfen nicht in eine unberechtigte Pro-Freigabe münden.
- Die bisherigen kleineren OpenAI-, Logtoken- und Lifespan-Befunde sind gegen den realen Vertrag nochmals zu prüfen und, wo reproduzierbar und risikoarm, minimal zu beheben.

Keine allgemeinen Refactorings.

Keine größere Zerlegung der Serverdatei über die hier benötigten Komponenten hinaus.

## 7. Tests – zwei getrennte Ebenen

Die Implementierung darf erst als vollständig geprüft gelten, wenn sowohl deterministische Tests als auch eine reale Lizenzserver-Integration geprüft wurden.

### D1. Deterministische Tests

Ergänze gezielte Unit- und Integrationstests für folgende Zustandsmatrix:

| Ausgangslage | Erwartung |
| --- | --- |
| Kein Key | Community, keine Lizenzserveranfrage |
| Community erzwungen | Community, keine Lizenzserveranfrage |
| Key vorhanden, gültige Prüfantwort | Gültiger Pro-Status |
| Key vorhanden, negative Prüfantwort | Keine Pro-Freigabe |
| Timeout oder Netzwerkfehler | Keine Pro-Freigabe |
| Key geändert | Alte Freigabe unmittelbar ungültig |
| Key entfernt | Community-Zustand |
| Force Community aktiviert | Pro-Freigabe unmittelbar ungültig |
| Force Community aufgehoben, Key vorhanden | Neue Prüfung entsprechend Zustandslage |
| Positive Antwort einer alten Generation | Verwerfen |
| Zwei parallele Prüfungen | Nur das aktuelle Ergebnis gilt |
| Frischefrist abgelaufen | Keine Verwendung alter Freigabe |
| Pro-Modell lokal nicht vorhanden | Kein erfolgreicher Modellstart |
| Falsche installierte Runtime | Kein Pro-Modellstart |
| Gültige Lizenz und verfügbares Pro-Modell | Korrekte Modellfreigabe |
| Negativer Status während Modellwechsel | Kein unberechtigter neuer Pro-Job |
| Serverneustart | Kein persistierter positiver Lizenzstatus |

Tests müssen den Weg durch die tatsächlichen Komponenten prüfen, nicht nur isolierte Hilfsfunktionen.

Insbesondere gehören dazu:

`SecurityService → KrokoLicenseGate → KrokoLicenseState → VoiceSTTService → STTModelManager`

Verwende Fake-Transporte, injizierte Uhren und deterministische Scheduler-/Modell-Fakes, wo sie für Wiederholbarkeit notwendig sind.

### D2. Reale Lizenzserver-Integration

**Echte Lizenzserverkontakte sind ausdrücklich Bestandteil dieses Auftrags.**

Ziel ist nachzuweisen, dass die implementierte Prüfung mit der realen technischen Schnittstelle funktioniert.

Verwende einen vorhandenen gültigen Kroko-Pro-Key aus der dafür verfügbaren sicheren Testkonfiguration.

Der Key darf ausschließlich zur Laufzeit aus einer bereits vorgesehenen Secretquelle beziehungsweise Umgebungsvariable gelesen werden.

Keine Klartextschlüssel in:

- Quellcode.
- Testdateien.
- Git-Historie.
- Terminalausgaben und CI-Logs.
- Fehlermeldungen.
- Arbeitsakte.
- PR-Kommentaren.

Für die Testevidenz dürfen keine vollständigen URLs mit eingebettetem Key ausgegeben werden.

#### Verpflichtende Realtests

**R1 – Positive Lizenzprüfung**

Mit gültigem Key und tatsächlich bekanntem, geeignetem Kroko-Pro-Modell eine echte Prüfung ausführen.

Verifizieren:

- Verbindung erfolgreich.
- Technische Modellkennung korrekt.
- Antwort korrekt verarbeitet.
- Positiver Status richtig übernommen.
- Ressourcen ordentlich freigegeben.
- Keine Secrets ausgegeben.

**R2 – Negative Lizenzprüfung**

Mit einem gezielt ungültigen Test-Key einen negativen Fall prüfen.

Die Testfrequenz begrenzen, um unnötige Verbindungen und wiederholte Fehlversuche zu vermeiden.

Verifizieren, dass keine Pro-Freigabe entsteht.

**R3 – Reale Modellintegration**

Mit der vorhandenen Pro-fähigen Test-Runtime und einem lokal verfügbaren Pro-Modell den vollständigen Weg prüfen:

Key → Lizenzprüfung → Freigabe → Modellverwaltung → tatsächlicher Modellstart.

Nach erfolgreichem Laden einen kleinen deterministischen Audio-Smoke-Test ausführen, sofern ein geeignetes lokales Test-Audio vorhanden ist.

**R4 – Berechtigungsänderung**

Nach realer positiver Prüfung den Wechsel zu Force Community beziehungsweise das Entfernen des Keys testen.

Dabei darf kein weiterer Pro-Zugriff mit der zuvor gültigen Freigabe möglich sein.

Nicht erforderlich ist dafür ein wiederholter echter Lizenzserverkontakt, wenn der serverinterne Übergang deterministisch nachweisbar ist.

#### Sicherheit und Ausführung

Echte Tests ausschließlich in einer isolierten Testausführung durchführen. Den produktiven Server nicht stoppen, neu starten oder in seiner Konfiguration verändern.

Verwende einen separaten Prozess, um den nativen Kroko-Zustand sauber zu isolieren.

Keine parallelen realen Pro-Recognizer starten.

Für die positiven und negativen Lizenztests eine geringe, begründete Anzahl tatsächlicher Anfragen vorsehen. Keine unkontrollierten Wiederholungsschleifen.

Die Tests sollen standardmäßig nicht durch jede gewöhnliche CI-Ausführung einen Lizenzserverkontakt auslösen. Verwende einen expliziten Opt-in-Testmodus, beispielsweise `VOICESTT_KROKO_LIVE_TESTS=1`.

Liegt kein gültiger Key oder kein passendes Pro-Modell in der Testumgebung vor, darf der Agent keinen erfolgreichen Realtest behaupten. Er muss dann die konkrete technische Voraussetzung und den Status `NOT_RUN/BLOCKED` dokumentieren.

Für alle ausgeführten Realtests sind Zeitpunkt, Testumgebung, bereinigter Befund, Ergebnis, Anzahl der externen Verbindungen und verwendete Modellkennung ohne Secrets festzuhalten.

## 8. Bestehende Regressionstests

Mindestens diese Dateien einbeziehen:

```text
tests/unit/test_kroko_selective_improvements.py
tests/unit/test_server_security_modularization.py
tests/unit/test_kroko_artifact_store.py
tests/unit/test_kroko_onnx_engine.py
tests/unit/test_openai_compatible_endpoint.py
tests/unit/test_realtime_streaming_transcription.py
tests/unit/test_fastapi_server_multi_user_asr_integration.py
```

Zusätzlich die bestehenden Tests für:

- `STTModelManager`.
- Server-Konfiguration und Persistenz.
- Settings-Control-Plane.
- Modellwechsel, Load und Unload.
- Modell-Registry und Fallback.
- Admin-Berechtigungen.
- Log-HTTP und Log-WebSocket.
- Session-Isolation.
- Secrets und Redaction.
- Build- und Paketidentität.

Nach den gezielten Tests die vollständige Unit-/Contract-Suite ausführen.

Bei Abschluss:

```bash
python -m pytest -q tests/unit
python -m compileall -q api_fastapi_server VoiceSTT/kroko VoiceSTT_server
git diff --check
```

Darüber hinaus sind die vollständigen GitHub-CI-Jobs unter Ubuntu und Windows am finalen Commit nachzuweisen.

Testfehler dürfen nicht durch Löschen, Überspringen oder Abschwächen von Tests verborgen werden.

## 9. Dokumentation vollständig aktualisieren

Dies ist ein gleichrangiger Bestandteil des Korrekturauftrags.

Folgende Dokumente müssen mit der abschließenden Implementierung abgeglichen werden:

```text
docs/server-authentication.md
docs/openai-http-api.md
docs/kroko-onnx.md
docs/stt-model-management.md
docs/configuration.md
docs/testing.md
docs/fastapi-server.md
docs/module-map.md
docs/README.md
docs/architecture/server-modularization-roadmap.md
docs/2026-10-22_kroko-unified-runtime-v2.md
README.md
build/BUILD.md
```

### Dokumentationsziele

**Zentrale Security-Komponente**

Die bestehende Modulreferenz muss die vier Prüfbereiche und die vollständig implementierte Kroko-Anbindung erläutern.

Insbesondere:

- Eingänge.
- Effektive Key-Auflösung.
- Prüfungszeitpunkte.
- Zustandswechsel.
- Integration mit dem Modellmanager.
- Fehlerfälle.
- Berechtigungsabgrenzung.
- Test- und Sicherheitsgrenzen.

**Kroko**

Die Kroko-Dokumentation muss die tatsächlich umgesetzte automatische Prüfung, Pro-Freigabe, Force-Community-Option und die Grenzen der installierten Runtime beschreiben.

**OpenAI**

Die eigenständige Dokumentation des OpenAI-Moduls bleibt erhalten.

Prüfe sie auf Korrektheit. Keine erneute Zusammenführung mit `server.py`.

**Modellverwaltung**

Die Modellmanager-Dokumentation muss die tatsächliche Lizenz-Eligibility und die technische Runtime-Kompatibilität verständlich unterscheiden.

**Betrieb und Konfiguration**

Die Dokumentation muss erklären, wie ein Administrator den Kroko-Key sicher bereitstellt, wie eine Änderung wirksam wird, welche Einstellung Force Community auslöst und welche Zustände bei erfolgreicher oder fehlgeschlagener Prüfung entstehen.

**Architekturhistorie**

Alte Architektur- und Planungsdokumente dürfen nicht rückwirkend verfälscht werden.

Stelle aber sicher, dass die aktuelle Dokumentation frühere, inzwischen überholte Entwürfe nicht als heutige Produktarchitektur ausgibt.

Insbesondere bleibt `build/BUILD.md` die maßgebliche Build- und Paketreferenz.

Überprüfe alle neuen relativen Markdown-Links.

## 10. Arbeitsakte

Erstelle eine neue, eigenständige Korrekturakte unter:

`docs/.archiv/pr15_korrekturlauf_20261025/`

Pflichtdateien:

```text
01_ORIGINAL_PROMPT.md
02_AUSGANGSSTAND.md
03_REQUIREMENTS_TRACEABILITY.md
04_IMPLEMENTIERUNG.md
05_TEST_EVIDENZ.md
06_DOKUMENTATIONSABGLEICH.md
07_BEFUNDE_UND_ABWEICHUNGEN.md
08_ABSCHLUSSBERICHT.md
```

### Anforderungen

**01:** Vollständiger, unveränderter Originaltext dieses Agentenauftrags.

**02:** Ausgangs-HEAD, PR-Status, ursprüngliche Anforderungen, festgestellte Abweichungen und bestehende technische Architektur.

**03:** Lückenlose Traceability aller Reviewbefunde auf Implementierung, Tests, Dokumentation und aktuellen Status.

**04:** Tatsächlich vorgenommene Codeänderungen, Begründung und Zuordnung zu Reviewbefunden.

**05:** Vollständige Testevidenz einschließlich realer Lizenzserver-Integration. Positive und negative Testbelege getrennt darstellen.

**06:** Dokumentenmatrix: vorheriger Zustand, notwendige Korrektur, ausgeführte Änderung, Linkprüfung und verbleibende Abweichungen.

**07:** Alle offenen und geschlossenen Befunde mit Schweregrad und konkretem Nachweis. Keine stillschweigende Herabstufung.

**08:** Vollständiger Abschlussbericht mit Soll/Ist-Abgleich, finalem Commit, CI-Links und verbleibenden Risiken.

Registriere den Korrekturlauf unter `docs/.archiv/README.md`.

Die vorherige Arbeitsakte `docs/.archiv/pr15_final_abnahmevorbereitung/` bleibt als historische Evidenz erhalten.

Widersprüche zur alten Abnahme werden in der neuen Akte ausdrücklich aufgelöst, nicht durch stilles Überschreiben früherer Berichte.

## 11. PR aktualisieren

Nach der vollständigen Umsetzung:

1. Sämtliche zulässigen Änderungen auf dem bestehenden Arbeitsbranch committen.
2. Auf denselben Branch pushen.
3. Finale GitHub-CI auf dem tatsächlichen letzten Commit prüfen.
4. PR-Beschreibung auf den tatsächlichen Funktionsumfang aktualisieren.
5. Die neue Korrekturakte vollständig verlinken.
6. Einen neuen ausführlichen PR-Abschlusskommentar veröffentlichen.

Der Kommentar muss enthalten:

- Ausgangslage und Reviewbezug.
- Alle behobenen Befunde.
- Neue Funktionen.
- Veränderte Dateien.
- Testmatrix.
- Echte Lizenztest-Ergebnisse, redigiert.
- Vollständige CI-Ergebnisse.
- Dokumentationsänderungen.
- Verbleibende technische Einschränkungen.
- Finalen Commit-SHA.
- Links zur vollständigen Arbeitsakte.

Der Original-Agentenauftrag und der vollständige Abschlussbericht müssen direkt im Kommentar enthalten sein; ergänzende Details dürfen auf commitgebundene Dateien verlinken.

Keine Secrets in PR-Beschreibung, Kommentaren oder Arbeitsakte.

## 12. Abschlussbedingungen

Verwende ausschließlich diese Status:

**`REVIEW_READY`**, wenn:

- Die automatische Kroko-Lizenzprüfung tatsächlich integriert ist.
- Keywechsel und Force Community korrekt verarbeitet werden.
- Pro-Freigaben an den tatsächlichen Lizenzzustand gebunden sind.
- Modellmanager und Security-Service konsistent zusammenarbeiten.
- Alle verpflichtenden deterministischen Tests erfolgreich sind.
- Die vorgesehenen realen Integrationstests erfolgreich durchgeführt wurden.
- Keine offenen hohen oder kritischen Befunde bestehen.
- Dokumentation und Code vollständig übereinstimmen.
- Die vollständige GitHub-CI unter Windows und Ubuntu auf dem finalen Commit erfolgreich ist.

**`BLOCKED`**, wenn eines dieser Kriterien nicht erfüllt ist.

Fehlende technische Nachweise dürfen nicht durch synthetische Tests ersetzt werden.

Ein nicht ausführbarer Realtest muss mit genauer Ursache dokumentiert werden.

`REVIEW_READY` bedeutet ausdrücklich nur, dass eine **erneute unabhängige Abnahme** stattfinden kann.

Es ist weder eine selbst erteilte Abnahme noch eine Mergefreigabe.

## 13. Schlussanweisung

Führe diesen Auftrag als einen vollständigen Korrekturlauf durch.

Arbeite alle Reviewbefunde nachvollziehbar ab. Erhalte die vorhandene Architektur und implementiere die fehlende Funktionalität über die bereits geschaffenen Komponenten.

Treffe keine weitreichenden neuen Architekturentscheidungen.

Erfinde keine technischen Nachweise und keine erfolgreiche Testausführung.

Bei einer nicht sicher lösbaren technischen Blockade dokumentiere den exakten Sachverhalt, die bereits geleistete Implementierung und die fehlende Voraussetzung, anstatt eine riskante Umgehung einzubauen.

**PR #15 bleibt Draft, offen und ungemergt.**

Abschließende Rückmeldung:

`REVIEW_READY – PR #15 ist nach vollständigem Korrekturlauf erneut zur unabhängigen Abnahme bereit.`

oder:

`BLOCKED – PR #15 erfüllt noch nicht sämtliche verbindlichen Abnahmekriterien.`
In der folgenden Datei sind Lizenzschlüssel hinterlegt, die du zum Testen verwenden kannst: "S:\VPS_Spiegelverzeichnis\vps\home\marco\selfhost\secrets\kroko.env"
