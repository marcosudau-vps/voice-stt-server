# Agentenauftrag: PR #15 – Qualifikation zur endgültigen Abnahme

## 0. Rolle und Verbindlichkeit

Du bist **ausführender Entwicklungs-, Test- und Dokumentationsagent**.

Du bist ausdrücklich **nicht** damit beauftragt, die Architektur selbstständig neu zu entwerfen, den Funktionsumfang zu erweitern oder neue Arbeitspakete zu planen.

Die nachstehenden Architekturentscheidungen, Abnahmeziele, Prüffälle, Pfade und Grenzen sind verbindlich.

**Ziel:** Bereite Pull Request #15 so vor, dass er nach Abschluss deiner Arbeiten einem unabhängigen Reviewer zur endgültigen technischen Abnahme vorgelegt werden kann.

Das Ergebnis muss nachvollziehbar, reproduzierbar, vollständig dokumentiert und durch tatsächliche Testnachweise gestützt sein.

## 1. Verbindlicher Repositorykontext

**Repository:** `marcosudau-vps/voice-stt-server`

**Pull Request:** https://github.com/marcosudau-vps/voice-stt-server/pull/15

**Arbeitsbranch:** `work/kroko-v2-selective-improvements-20261025`

**Zielbranch:** `feat/v2-unified-kroko`

**Letzter vor diesem Auftrag bestätigter PR-HEAD:** `e65c33ce1bdff16a8327fda86954e81bb1d9a275`

**Zu diesem HEAD erfolgreiche CI:** https://github.com/marcosudau-vps/voice-stt-server/actions/runs/40180053129

Vor der Arbeit sind der aktuelle HEAD, der Zielbranch, ein sauberer lokaler Working Tree und der tatsächliche PR-Status zu verifizieren. Abweichungen dokumentieren; fremde Commits oder ungesicherte Änderungen niemals überschreiben.

Alle Änderungen erfolgen ausschließlich auf dem genannten Arbeitsbranch von PR #15.

Verboten sind:

- Merge, Rebase oder Force-Push.
- Änderungen an PR #12 oder PR #14.
- Änderungen an `main` oder `feat/v2-unified-kroko`.
- Automatische Markierung als „Ready for Review“.
- Produktive Deployments, Releases oder Tags.
- Echte Kroko-Lizenzserverkontakte oder Pro-Modellaktivierungen.
- Eigenmächtige Architektur- oder API-Erweiterungen.

PR #15 bleibt bis zur unabhängigen Abnahme im Draft-Status.

## 2. Zwingend zuerst lesen

Lies vor jeder Änderung vollständig:

- `AGENTS.md`
- `docs/.archiv/README.md`
- `docs/.archiv/kroko_v2_selective_improvements/2026-10-25_PLAN.md`
- `docs/.archiv/kroko_v2_selective_improvements/2026-10-25_UMSETZUNGSVERGLEICH.md`
- `docs/.archiv/server_modularization_20261025/2026-10-25_PLAN.md`
- `docs/.archiv/server_modularization_20261025/2026-10-25_UMSETZUNGSVERGLEICH.md`
- `docs/architecture/server-modularization-roadmap.md`
- `docs/configuration.md`
- `docs/kroko-onnx.md`
- `docs/testing.md`
- `build/BUILD.md`

Lies außerdem den vollständigen aktuellen PR-Diff gegen `feat/v2-unified-kroko` und nicht nur die PR-Beschreibung.

Historische Planungen und frühere Prüfberichte dürfen nicht nachträglich so umgeschrieben werden, als seien neue Erkenntnisse schon damals bekannt gewesen.

## 3. Arbeitsakte – zwingende Anlage

Lege im Repository den folgenden festen Arbeitsordner an:

`docs/.archiv/pr15_final_abnahmevorbereitung/`

Die folgenden Dateien sind Pflicht. Ersetze in ihren Dateinamen `YYYY-MM-DD` durch das tatsächliche Erstellungsdatum. Die übrigen Dateinamensbestandteile sind verbindlich.

```text
docs/.archiv/pr15_final_abnahmevorbereitung/
├── YYYY-MM-DD_01_ORIGINAL_PROMPT.md
├── YYYY-MM-DD_02_AUSGANGSLAGE_UND_PLAN.md
├── YYYY-MM-DD_03_PR_SCOPE_UND_TRACEABILITY.md
├── YYYY-MM-DD_04_TEST_EVIDENZ.md
├── YYYY-MM-DD_05_DOKUMENTATIONSPRUEFUNG.md
├── YYYY-MM-DD_06_BEFUNDE_UND_ABWEICHUNGEN.md
└── YYYY-MM-DD_07_ABSCHLUSSBERICHT.md
```

### Anforderungen an die Akte

**01_ORIGINAL_PROMPT**

Enthält diesen vollständigen Agentenauftrag wortgetreu und unverändert. Keine Zusammenfassung, keine nachträgliche Anpassung.

**02_AUSGANGSLAGE_UND_PLAN**

Enthält Ausgangs-HEAD, Zielbranch, PR-Status, Ausgangs-CI, vorhandene Dokumentationslage, feste Prüfschritte und Abnahmekriterien. Vor produktiven Änderungen erstellen und die Aktion in `docs/.archiv/README.md` registrieren.

**03_PR_SCOPE_UND_TRACEABILITY**

Enthält eine vollständige Matrix:

`Anforderung → bestehende Implementierung → betroffene Dateien/Symbole → zugehörige Tests → Verifikationsstatus → offene Risiken`.

**04_TEST_EVIDENZ**

Enthält tatsächlich ausgeführte Befehle, Umgebung, Commit-SHA, Testergebnisse, geprüfte Positiv-/Negativfälle und unveränderliche CI-Links. Echte Fehlschläge und nachfolgende Korrekturen müssen unterscheidbar bleiben.

**05_DOKUMENTATIONSPRUEFUNG**

Enthält eine Dokumentenmatrix mit gefundenen Abweichungen, durchgeführten Korrekturen, Linkprüfung und ausdrücklich unverändert gelassenen historischen Dokumenten.

**06_BEFUNDE_UND_ABWEICHUNGEN**

Enthält sämtliche Feststellungen mit Schweregrad, Beleg, fachlicher Auswirkung, Entscheidung, Korrektur und Verifikationsnachweis. Auch bewusst zurückgestellte Befunde dokumentieren. Bei keinen materiellen Abweichungen ausdrücklich „Keine materiellen Abweichungen festgestellt“ vermerken.

**07_ABSCHLUSSBERICHT**

Enthält den vollständigen Soll-/Ist-Abgleich, die finale Änderungsübersicht, den letzten Commit, die finale CI, verbleibende Risiken und einen der beiden Status:

- `REVIEW_READY`
- `BLOCKED`

`REVIEW_READY` bedeutet nur, dass die unabhängige Abnahme beginnen kann, **nicht**, dass diese schon erfolgreich stattgefunden hat.

Alle Akten bleiben Bestandteil von PR #15.

## 4. Verbindliche Architekturgrenzen

Die folgenden Entscheidungen sind nicht erneut zur Disposition zu stellen.

### 4.1 OpenAI

`api_fastapi_server/openai_routes.py` ist ausschließlich HTTP-/SSE-Adapter.

Die fachliche Inferenzkoordination verbleibt im bestehenden Service.

Insbesondere bleiben dort:

- `model_catalog`
- `resolve_openai_model`
- `transcribe_openai`
- `complete_pending_api_transcription`
- Scheduler- und Pending-Result-Verwaltung

Keine duplizierten Implementierungen und keine Rückimporte von `api_fastapi_server.server` in den Router.

### 4.2 Security

`api_fastapi_server/security/SecurityService` ist die gemeinsame Schnittstelle für vier fachlich getrennte Mechanismen:

1. Admin-Zugang
2. OpenAI-Bearer-Zugang
3. Logzugriff und Sitzungstokens
4. Kroko-On-Premise-Lizenzadapter

Diese Berechtigungsarten sind **nicht austauschbar**.

Ein Kroko-Lizenznachweis verleiht keine administrativen Rechte. Ein Admin-Key ersetzt keine Kroko-Pro-Lizenz.

### 4.3 Kroko

Die vorhandenen Bausteine dürfen geprüft und eng begrenzt gehärtet werden, aber nicht eigenmächtig in die produktive Runtime- oder Modellsteuerung integriert werden.

Es findet keine automatische Pro-Freischaltung statt.

Es wird keine neue allgemeine Semantik eingeführt, nach der eine positive Prüfung einer Modell-UUID automatisch alle Pro-Modelle freischaltet.

Keine nativen Patches, keine Build-Fingerprint-Änderungen und keine neue Lizenzserver-Integration.

### 4.4 V2-Vertrag

Das bestehende V2-Wire-Protokoll, das persistierte Einstellungsformat und die zentralen Modellverwaltungsverträge bleiben unverändert.

## 5. Prüfauftrag A – OpenAI-Modul

Prüfe `api_fastapi_server/openai_routes.py` vollständig gegen die Implementierung im Zielbranch vor dem Refactoring.

Verifiziere die unveränderte Funktion dieser Endpunkte:

- `GET /v1/models`
- `POST /v1/audio/transcriptions`

Prüfe zwingend:

**A1 – Router-Integration**

- Tatsächliche Registrierung beider HTTP-Endpunkte.
- Kein Importzyklus.
- Korrekte Injektion aller Abhängigkeiten.
- Kein doppelter API-Endpunkt.
- Kein zweiter Inferenz-Scheduler.
- Funktion aus einem installierten Wheel, nicht nur aus dem Source-Checkout.

**A2 – Modellrouting**

- `whisper-1` als Alias.
- Explizite Modellangaben.
- Form- und Header-Overrides samt Priorität.
- Korrekte Lane-/Modellauflösung.
- Unzulässige Overrides bleiben abgewiesen.

**A3 – Upload und Antworten**

- Fehlende oder fehlerhafte Dateien.
- Dateigrößenlimit samt HTTP-Status.
- Audiodaten-Decoding.
- Unterstützte Antwortformate einschließlich `json`, `text`, `verbose_json`, `srt`, `vtt` und vorhandener diarisierten Variante.
- Response-Medientypen und Statuscodes.
- Bestehende Fehlerstrukturen.
- Bestehende Request-, Routing- und Modellheader.

**A4 – Streaming**

- Gültige SSE-Nachrichten.
- Erwartete Delta-/Abschlussreihenfolge.
- Finale Transkription.
- Fehlerbehandlung vor und während des Streams.
- Keine verlorenen oder doppelt ausgegebenen Abschlussereignisse.
- Korrekte Thread-/Async-Übergabe.
- Kein offengebliebener Hintergrundjob durch einen regulär beendeten Teststream.

**A5 – Telemetrie**

- Audit-Events bleiben vorhanden.
- Performance-Events bleiben vorhanden.
- Request-ID, Session-ID, Transcription-ID und Client-ID sind korrekt korreliert.
- Fehlerhafte Authentifizierung erzeugt weiterhin die vorgesehenen Audit-Events.
- Keine sensiblen Schlüssel in Logs, Fehlertexten oder Rückgaben.

Teste über echte FastAPI-Testclient-Requests. Interna von FastAPI wie das konkrete Format von `app.routes` sind kein Ersatz für einen HTTP-Vertragstest.

## 6. Prüfauftrag B – Security

Prüfe die folgenden Dateien vollständig:

```text
api_fastapi_server/security/__init__.py
api_fastapi_server/security/service.py
api_fastapi_server/security/admin.py
api_fastapi_server/security/openai.py
api_fastapi_server/security/logs.py
api_fastapi_server/security/kroko.py
```

### B1 – Admin

Verifiziere:

- Gültiger und ungültiger Admin-Key.
- Header `X-VoiceSTT-Admin-Key`.
- Bestehender Bearer-Mechanismus.
- Bestehender Alias `X-Admin-Key`.
- Präzedenz bei gleichzeitig gesetzten Headern.
- `401` samt `WWW-Authenticate` bei ungültigem konfiguriertem Key.
- Ohne konfigurierten Key nur bisher zulässige lokale Adminzugriffe.
- Remote-Zugriff ohne Admin-Key ergibt `403`.
- Änderung von Key/Umgebung führt nicht zu einer unerlaubten Restfreigabe.

### B2 – OpenAI

Verifiziere:

- Verhalten ohne konfigurierten API-Key.
- Verhalten mit gültigem und ungültigem Bearer-Key.
- `401` und bisherige Fehlerstruktur.
- Korrektes Authentifizierungs-Audit.
- Keine Rechteübernahme durch Admin- oder Logtoken.
- Keine Offenlegung des Keys.

### B3 – Logzugriff

Verifiziere:

- Sichere Erzeugung sitzungsgebundener Tokens.
- 24-Stunden-Gültigkeit.
- Gültigkeit genau bis zur vorgesehenen Ablaufgrenze.
- Ablehnung unbekannter und abgelaufener Tokens.
- Ablehnung der Nutzung für eine andere Session.
- Getrennte HTTP- und WebSocket-Berechtigungsregeln.
- Unveränderte Rechte eines gültigen Admin-Keys.
- Kein impliziter Loopback-Admin-Bypass für Log-WebSockets.
- Keine Rechteausweitung durch Kombination unterschiedlicher Auth-Header.
- Unveränderte Kanal-, Filter-, Replay- und Cursorberechtigungen.
- Token bleibt flüchtig; keine unbeabsichtigte Persistenz.

### B4 – Kroko-Security-Adapter

Verifiziere:

- Keine automatische Prüfung bei Instanziierung oder Serverstart.
- Prüfung nur bei ausdrücklichem Aufruf.
- Kein fremdes Modell-Entitlement.
- Ungültige, fehlende oder veraltete Antwort wird nicht positiv übernommen.
- Wechsel des effektiven Keys invalidiert alte Freigaben.
- Force-Community-Zustand verhindert positive Nutzung.
- Technische Fehler werden nicht zu positiven Freigaben.
- Keine Ableitung von Admin- oder OpenAI-Rechten.

Teste erlaubte und verbotene Übergänge. Negative Tests sind hier ausdrücklich verpflichtend.

## 7. Prüfauftrag C – Kroko-Bausteine

Prüfe:

```text
VoiceSTT/kroko/credentials.py
VoiceSTT/kroko/license_api.py
VoiceSTT/kroko/license_state.py
VoiceSTT/kroko/models.py
VoiceSTT/transcription_engines/kroko_onnx_engine.py
```

### C1 – Credential-Auflösung

Verifiziere die bisherige Priorität aller vier Umgebungsvariablen, Engine-Optionen und des verschachtelten `recognizer.key`.

Prüfe ausdrücklich leere, fehlende und überschriebene Schlüssel.

Beweise durch Tests, dass der ausgewählte Wert auch tatsächlich beim Recognizer ankommt.

### C2 – Lizenzprobe

Ausschließlich synthetische WebSocket-Fakes.

Prüfe gültige, abgelehnte, fehlerhaft strukturierte, abgelaufene und unvollständige Antworten sowie Timeout-/Transportfehler.

Die Antwort muss an die konkrete Modell-UUID gebunden sein.

Prüfe Secret-Redaktion und Ressourcenfreigabe.

Keine echten Netzwerkverbindungen.

### C3 – Lizenzstatus

Prüfe:

- Initialzustand.
- Generationenbindung.
- Keyrotation.
- Force Community.
- Modellwechsel.
- Verfall und Frischegrenze.
- Stale Result nach Key- oder Modellwechsel.
- Gleichzeitige oder überlappende Prüfungen.
- Keine positive Berechtigung durch fremde Modell-UUID.

Prüfe darüber hinaus ausdrücklich, dass ein positiver synthetischer Lizenzstatus **nicht automatisch die produktive Pro-Runtime aktiviert**.

### C4 – Community-Fallback

Teste deterministische Modellwahl, Sprachpräferenz und fehlende Kandidaten.

Prüfe, dass die Funktion weder Modelle lädt noch persistierte Benutzereinstellungen ändert.

Prüfe, dass die eigentliche Modellverwaltung weiterhin beim `STTModelManager` verbleibt.

## 8. Prüfauftrag D – Lifespan und Race-Regression

Verifiziere:

- `service.stop()` nach regulärem Shutdown.
- `service.stop()` auch nach Fehler beim Service-Start.
- Keine verdeckten Fehler durch doppelte Cleanup-Aufrufe.
- Der korrigierte Realtime-Race-Test wartet tatsächlich auf das verspätete R1-Ergebnis.
- Das alte Ergebnis wird nach R2 nicht veröffentlicht.
- Der Test kann nicht durch einen im Hintergrund verschluckten Modellfehler falsch positiv bestehen.

Wiederhole relevante Race-Tests mehrfach. Dokumentiere Laufanzahl und Ergebnis. Mindestens 30 Wiederholungen des gezielten deterministischen Race-Tests sind erforderlich.

## 9. Testpflichten

Die folgenden bestehenden Dateien müssen explizit berücksichtigt werden:

```text
tests/unit/test_openai_compatible_endpoint.py
tests/unit/test_server_security_modularization.py
tests/unit/test_kroko_selective_improvements.py
tests/unit/test_kroko_artifact_store.py
tests/unit/test_kroko_onnx_engine.py
tests/unit/test_realtime_streaming_transcription.py
tests/unit/test_fastapi_server_multi_user_asr_integration.py
```

Ermittle zusätzlich die bestehenden Log-/Event-/WebSocket- und Security-Regressionstests des Repositories und nimm sie in die Prüfabdeckung auf.

Ergänze nur diejenigen Tests, die zum Nachweis der oben ausdrücklich genannten Invarianten fehlen.

**Verboten:**

- Tests löschen, nur damit CI grün wird.
- Assertions abschwächen.
- Sicherheitsprüfungen mocken, obwohl ihr Verhalten Gegenstand des Tests ist.
- Testfehler durch pauschale Skips verstecken.
- Externe Lizenztests als erfolgreich ausgeben, wenn sie nicht gelaufen sind.

Führe mindestens aus:

```bash
python -m pytest -q tests/unit/test_openai_compatible_endpoint.py tests/unit/test_server_security_modularization.py tests/unit/test_kroko_selective_improvements.py tests/unit/test_kroko_artifact_store.py tests/unit/test_kroko_onnx_engine.py tests/unit/test_realtime_streaming_transcription.py tests/unit/test_fastapi_server_multi_user_asr_integration.py

python -m pytest -q tests/unit

python -m compileall -q api_fastapi_server VoiceSTT/kroko

git diff --check
```

Bei fehlenden lokalen optionalen Abhängigkeiten ist der Test als `NOT_RUN` beziehungsweise `BLOCKED` zu dokumentieren, nicht als bestanden.

Nach dem letzten Commit ist die vollständige GitHub-CI für den **finalen Commit-HEAD** auf Ubuntu und Windows zu prüfen.

Ausstehende oder abgebrochene CI-Läufe zählen nicht als erfolgreich.

## 10. Dokumentationsabgleich

Prüfe und aktualisiere, soweit inhaltlich erforderlich:

```text
docs/configuration.md
docs/kroko-onnx.md
docs/testing.md
docs/architecture/server-modularization-roadmap.md
docs/.archiv/README.md
```

Stelle sicher, dass die Dokumentation:

1. Neue Komponenten mit ihrer tatsächlichen Verantwortung beschreibt.
2. Zwischen implementierter Funktion, Hilfsfunktion und nicht integrierter Vorbereitung unterscheidet.
3. Keine automatische Kroko-Pro-Freischaltung behauptet.
4. Keine globale Pro-Lizenzberechtigung aus einer Modell-UUID-Prüfung ableitet.
5. Bestehende API-, Auth- und Logging-Verträge korrekt beschreibt.
6. Den tatsächlichen Teststand und seine Grenzen nennt.
7. Auf die jeweils maßgebliche Architektur- und Buildreferenz verweist.
8. Keine zweite, konkurrierende Konfigurations- oder Build-Wahrheitsquelle erzeugt.

### Konkrete bekannte Dokumentationskorrektur

In `docs/.archiv/README.md` wird die Aktion „Selektive Kroko-V2-Verbesserungen ohne Besitzerprozess“ derzeit fälschlich PR #14 zugeordnet.

Korrigiere die Zuordnung:

- **Implementierungs-PR: #15**
- **Quell-/Referenz-PR: #14**

PR #14 wurde nicht gemergt und darf nicht als umgesetzter PR erscheinen.

### Historische Evidenz

Die bisherigen Dateien vom 25.10.2026 mit dem damaligen Hinweis „CI ausstehend“ sind historische Momentaufnahmen.

Schreibe diese nicht stillschweigend um.

Ergänze stattdessen in der neuen Arbeitsakte die späteren tatsächlichen CI-Ergebnisse und verlinke sie.

Prüfe relative Markdown-Links und alle neu eingeführten Dokumentationsverweise.

## 11. Zulässige Codekorrekturen

Codeänderungen sind nur zulässig, wenn bei der Prüfung ein konkreter, reproduzierbarer Fehler oder eine nachgewiesene Verletzung einer der oben beschriebenen Invarianten festgestellt wird.

Vorgehen:

1. Befund dokumentieren.
2. Reproduzierenden Test hinzufügen oder bestehenden Test gezielt stärken.
3. Minimalen Fix implementieren.
4. Gezielten Test erneut ausführen.
5. Gesamtsuite ausführen.
6. Befund mit Commit, Test und Ergebnis schließen.

Keine großflächigen Refactorings.

Keine neuen Abstraktionsebenen nur aus Stilgründen.

Keine Änderungen am Protokoll, Persistenzschema, nativen Build oder Produkt-Entitlement.

Ist ein notwendiger Fix ohne Architekturentscheidung, Wire-Änderung oder größere neue Implementierung nicht möglich, stoppe diesen Teil und dokumentiere ihn als `BLOCKED`, anstatt einen eigenen Lösungsansatz durchzusetzen.

Dokumentations- und Testergänzungen dürfen unabhängig davon durchgeführt werden.

## 12. Vollständige Traceability

Die Datei `03_PR_SCOPE_UND_TRACEABILITY.md` muss mindestens diese Einträge enthalten:

| ID | Nachzuweisende Fähigkeit |
| --- | --- |
| PR15-OAI-01 | OpenAI-Router korrekt registriert |
| PR15-OAI-02 | Modellrouting und Overrides unverändert |
| PR15-OAI-03 | Upload, Fehler, Antwortformate unverändert |
| PR15-OAI-04 | SSE-Streaming und Async-Verhalten unverändert |
| PR15-OAI-05 | Audit-/Performance-Korrelation unverändert |
| PR15-SEC-01 | Admin-Gate unverändert |
| PR15-SEC-02 | OpenAI-Bearer-Gate unverändert |
| PR15-SEC-03 | Logtoken-Lebenszyklus korrekt |
| PR15-SEC-04 | HTTP-/WS-Logberechtigungen korrekt getrennt |
| PR15-SEC-05 | Kroko-Adapter isoliert und fail-closed |
| PR15-KRO-01 | Effektiver Recognizer-Key korrekt |
| PR15-KRO-02 | Lizenzprobe korrekt und modellgebunden |
| PR15-KRO-03 | Flüchtiger Lizenzstatus gegen Stale-/TTL-Fehler gesichert |
| PR15-KRO-04 | Community-Fallback reine Kandidatenwahl |
| PR15-LIFE-01 | ASGI-Cleanup bei Startup-Fehler |
| PR15-RACE-01 | Realtime-Stale-Result-Test tatsächlich wirksam |
| PR15-ARCH-01 | Keine Importzyklen oder zweite fachliche Authority |
| PR15-ARCH-02 | Keine produktive Pro-Freischaltung/Runtime-Umschaltung |
| PR15-DOC-01 | Fachdokumentation und Archiv konsistent |
| PR15-CI-01 | Vollständige CI auf finalem HEAD erfolgreich |

Jede ID benötigt Implementierungsreferenz, Testbeleg und einen eindeutigen Status.

## 13. Abschlusskriterien

`REVIEW_READY` darf ausschließlich vergeben werden, wenn:

- Alle Prüfpunkte abgearbeitet sind.
- Keine offenen kritischen oder hohen Befunde bestehen.
- Alle bekannten funktionalen Regressionen behoben sind.
- Pflicht- und Regressionstests erfolgreich sind.
- Die vollständige CI auf dem finalen Commit unter Windows und Ubuntu erfolgreich war.
- Die Dokumentation dem tatsächlichen PR-Stand entspricht.
- Die Arbeitsakte vollständig und verlinkt ist.
- Keine Änderung außerhalb des genehmigten Scopes vorgenommen wurde.
- PR #15 weiterhin auf `feat/v2-unified-kroko` zeigt.
- PR #15 weiterhin Draft und nicht gemergt ist.

Andernfalls lautet der Status `BLOCKED`.

Die historische Aktion bleibt im Archivregister auf `Prüfung offen`, solange die unabhängige Abnahme fehlt. Die Arbeitsakte darf bei vollständiger Ausführung als abgeschlossen gekennzeichnet werden, die fachliche PR-Abnahme jedoch nicht.

## 14. PR-Aktualisierung

Nach Abschluss sämtlicher Änderungen und Tests:

### 14.1 Commit und Push

- Alle zulässigen Änderungen committen.
- Commit-Konventionen des Repositories einhalten.
- Auf den bestehenden PR-Branch pushen.
- Finalen Commit-SHA erfassen.
- Finale CI abwarten und verifizieren.
- Nach finalem CI-Erfolg keine weiteren Code- oder Dokumentationscommits ohne neue CI erzeugen.

### 14.2 PR-Beschreibung

Aktualisiere die bestehende Beschreibung von PR #15, ohne die bisherige Historie oder Scope-Abgrenzungen zu entfernen.

Ergänze:

- Aktueller Funktionsumfang.
- Tatsächlich abgegrenzte Nicht-Ziele.
- Zusammenfassung der finalen Tests.
- Windows-/Ubuntu-CI mit Links.
- Arbeitsakte und Traceability.
- Offene Risiken und bewusst zurückgestellte Pro-Themen.
- Finalen Status `REVIEW_READY` oder `BLOCKED`.

### 14.3 PR-Abschlusskommentar – verpflichtend

Erstelle **einen neuen, eigenständigen Kommentar direkt unter PR #15**.

Dieser Kommentar soll nicht nur „Agent fertig“ melden, sondern eine lesbare, eigenständig nachvollziehbare Arbeitsakte enthalten.

Vorgeschriebene Struktur:

```text
# PR #15 – Abnahmevorbereitung / Agenten-Arbeitsakte

## Ergebnisstatus
REVIEW_READY oder BLOCKED

## Ausgangsstand
Branch, Ausgangs-HEAD, Zielbranch, Datum

## Original-Agentenauftrag
Vollständiger unveränderter Original-Prompt
(gegebenenfalls eingeklappt über GitHub <details>)

## Umgesetzter Funktionsumfang
Kurze Ist-Beschreibung je Komponente

## Änderungen während der Abnahmevorbereitung
Dateien, Zweck, Commits

## Traceability
Anforderungs-IDs, Implementierung, Teststatus

## Testevidenz
Kommandos, Testzahlen, Negativtests, Race-Läufe,
Linux-/Windows-CI-Links, Commit-SHA

## Dokumentationsabgleich
Geprüfte und aktualisierte Dokumente

## Befunde und offene Risiken
Mit Priorität und Beleg

## Abschlussbericht
Soll/Ist, verbleibende Einschränkungen, nächste Entscheidung

## Vollständige Arbeitsakte im Repository
Permalinks auf sämtliche datierten Arbeitsakten-Dateien
```

Der Kommentar muss insbesondere den **Original-Prompt unverändert**, die wesentliche **Evidenzmatrix** und den **vollständigen Abschlussbericht** direkt enthalten, nicht ausschließlich Verweise.

Die zusätzlich im Repository gespeicherten Akten müssen über commitgebundene Permalinks verlinkt sein.

Falls die GitHub-Kommentarlängenbegrenzung erreicht wird, den Inhalt kompakt formatieren und Wiederholungen vermeiden; keine Testergebnisse oder relevanten Befunde auslassen. Den Original-Prompt und den Abschlussbericht nicht kürzen.

Keine Secrets, Access Tokens, Anbieterantworten mit sensitiven Inhalten oder unnötigen Rohlogs veröffentlichen.

Die im Kommentar genannten Tests müssen nachweislich zum angegebenen finalen Commit gehören.

## 15. Abschließende Rückmeldung

Liefere nach der PR-Aktualisierung eine kompakte Abschlussmeldung mit:

- Ergebnisstatus.
- PR-Link.
- Finalem Commit-SHA.
- CI-Ergebnis für Ubuntu und Windows.
- Anzahl und Art korrigierter Befunde.
- Verbleibenden Risiken.
- Link zum PR-Abschlusskommentar.
- Links zur Arbeitsakte.

**Wichtig:** Kein Merge, kein Ready-for-Review-Umschalten, keine selbst erteilte Abnahme.

Wenn alle Kriterien erfüllt sind, endet dein Auftrag mit:

`REVIEW_READY – PR #15 ist für die unabhängige endgültige Abnahme vorbereitet.`

Bei nicht erfüllten Kriterien:

`BLOCKED – PR #15 ist noch nicht abnahmebereit.`

Arbeite den Auftrag vollständig aus. Triff keine zusätzlichen Architekturentscheidungen und erweitere den Scope nicht eigenmächtig.
