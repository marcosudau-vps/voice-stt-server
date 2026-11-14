# Server-Authentifizierung – Modulreferenz

**Stand:** 25.10.2026 · **Implementierung:** [`api_fastapi_server/security/`](../api_fastapi_server/security/) · **Einführung:** PR [#15](https://github.com/marcosudau-vps/voice-stt-server/pull/15)

## Architektur und Geltungsbereich

Die früher über `api_fastapi_server/server.py` verteilten Prüfungen für Admin, OpenAI-API und Logs sind seit PR #15 in einer **gemeinsamen, aber fachlich getrennten Security-Komponente** zusammengeführt.

`SecurityService` aus `api_fastapi_server/security/service.py` wird einmal je `VoiceSTTService` instanziiert und stellt delegierende Schnittstellen zur Verfügung. Die Regeln werden in separaten Gate-Komponenten implementiert; es gibt **keine gemeinsame austauschbare Berechtigung**.

| Modul | Authority / Aufgabe | Serverintegration |
| --- | --- | --- |
| `admin.py` – `AdminGate` | Admin-Key, Headerpriorität, lokale Verwaltung ohne Key, 401/403 | `admin_http_error`, Admin-Scope anderer Prüfungen |
| `openai.py` – `OpenAIGate` | Optionaler OpenAI-Bearer-Key und fehlgeschlagene Authentifizierungs-Audits | OpenAI-HTTP-Router über `openai_http_error` |
| `logs.py` – `LogTokenAuthority`, `LogGate` | Flüchtige Sitzungstokens sowie separate HTTP-/WebSocket-Scope-Regeln | `create_log_access`, `validate_log_access`, Log-HTTP- und Log-WS-Routen |
| `kroko.py` – `KrokoLicenseGate` | Modellbezogene externe On-Premise-Lizenzprüfung mit generationsgebundenem Ergebnis (`prepare`/`run`, nur lesende Folgeentscheidung) | Vom `VoiceSTTService` automatisch an Initialisierung, Modell-Refresh/-Switch, Force-Community-Änderung und explizitem Recheck ausgewertet (§4) |

## 1. Administrative API

Konfiguration: `admin_api_key` oder `VOICESTT_ADMIN_API_KEY` (konfigurierter Setting-Wert hat Vorrang).

Für den Admin-Key gelten der Reihe nach `X-VoiceSTT-Admin-Key`, `Authorization: Bearer <admin-key>` und `X-Admin-Key`. Ein vorhandener, aber ungültiger priorisierter Header wird nicht durch einen nachfolgenden gültigen Header ersetzt. Mit konfiguriertem Key ist ein ungültiger oder fehlender Nachweis HTTP 401 samt `WWW-Authenticate: Bearer`.

Ohne konfigurierten Admin-Key ist die bestehende Adminfreigabe ausschließlich für lokale Clienthosts (`127.0.0.1`, `::1`, `localhost`; `testclient` nur im Testkontext) erlaubt. Externe Clients erhalten HTTP 403. Dies ist die vorhandene Quellcode-Policy, keine generelle Empfehlung, einen extern erreichbaren Server ohne Admin-Key zu betreiben.

## 2. OpenAI-kompatible HTTP-API

Konfiguration: `openai_api_key` oder `VOICESTT_API_KEY` (Setting vor Umgebung). Ohne Key bleibt die API offen; bei eingerichtetem Key wird ausschließlich der exakt passende `Authorization: Bearer <openai-api-key>` akzeptiert. Ein ungültiger Key erzeugt HTTP 401 im OpenAI-Fehlerformat und den bestehenden Audit-Event `authentication.failed`.

Der OpenAI-Key verleiht keine Adminrechte. Öffentliche Routen, Modelle, Overrides und SSE: [OpenAI-HTTP-Modul](openai-http-api.md).

## 3. Sitzungsgebundene Logtokens

`LogTokenAuthority` generiert flüchtige zufällige 64-stellige Hex-Tokens mit 24 Stunden Gültigkeit, speichert nur Session-ID und Ablaufzeit in einem In-Memory-Store und weist fremde Sessions oder abgelaufene Tokens ab. Neustart löscht den Store.

- **Log-HTTP:** Admin-Key, lokaler Adminzugriff ohne konfigurierten Admin-Key oder passendes Sessiontoken (z. B. `X-VoiceSTT-Log-Token` beziehungsweise Bearer-Token) werden über getrennte Scopes autorisiert.
- **Log-WebSocket (`/ws/logs`):** Erstes `subscribe`-Objekt enthält `accessToken` und gegebenenfalls `sessionId`. Zulässig sind ein expliziter Admin-Key oder ein zur Sitzung passendes Logtoken. **Kein** impliziter Loopback-Adminzugriff ohne Admin-Key.
- Ein Sitzungstoken wird nicht zum globalen Admin-Token. Kanal-, Filter-, Replay- und Cursorregeln verbleiben bei den bestehenden Routen und Event-Sinks.

Die Log-Authentifizierung ersetzt weder die Berechtigungsregeln von `/ws/v2` noch die der OpenAI-HTTP-API. Der zugrunde liegende Event-Vertrag steht in [Strukturiertes Logging](structured-logging.md).

## 4. Kroko-On-Premise-Modelllizenz – Produkt-Entitlement, kein API-Login

`KrokoLicenseGate` (`api_fastapi_server/security/kroko.py`) koordiniert die
Produktentscheidung über dem flüchtigen `KrokoLicenseState`
(`VoiceSTT/kroko/license_state.py`). Sie ist die **Python-seitige
Lizenzfreigabe**. Sie ist nicht der **native Lizenzkontext** der
Kroko-Pro-Runtime (§4.5); beide werden getrennt geführt und ausgewiesen.

```text
Kein API-Key vorhanden      → Community (keine Netzwerkanfrage)
Community erzwungen          → Community (keine Netzwerkanfrage)
Key vorhanden, nicht erzw.   → modellbezogene Lizenzprüfung
Prüfung gültig (VALID)       → Pro für genau dieses Modell freigegeben
ungültig / Fehler / Ablauf   → Community (fail-closed)
```

### 4.1 Eingänge und Prüfziel

Effektiver Key ausschließlich aus
`VoiceSTT.kroko.credentials.effective_recognizer_key` (Priorität:
`recognizer.key` – auch leer suppressiv – vor Top-Level-`key` vor den vier
Umgebungsvariablen `KROKO_API_KEY`, `KROKO_ONNX_KEY`, `VOICESTT_KROKO_ONNX_KEY`,
`KROKO_KEY`), gelesen aus den Engine-Optionen, die die Kroko-Engine tatsächlich
erhält. Betreiberintent `kroko.forceCommunity` aus der Settings-Control-Plane
(serverweit, Admin, live, persistiert als Absicht).

Die Prüfung adressiert **genau ein** Pro-Modell, in dieser Reihenfolge:

1. ein in Final/Realtime konfiguriertes Pro-Modell,
2. sonst die Pro-Identität, die dieser Prozess bereits nativ initialisiert hat,
3. sonst (gültiger Key, kein Force) ein **lokal vorhandenes** Pro-Modell
   (Sprache des konfigurierten Modells bevorzugt, sonst Manifestreihenfolge).

Punkt 3 macht die automatische Berechtigungsprüfung auch aus einer
**Community-Konfiguration** heraus möglich: Die Berechtigung, ein Pro-Modell
auszuwählen, ist etwas anderes als seine Aktivierung. Die Prüfung lädt nichts
nativ und wechselt kein Modell. Ohne Key oder mit Force Community findet keine
Prüfung statt; fehlt jede lokal verifizierbare Pro-Datei, wird das ehrlich als
`pro_model_not_local` ausgewiesen (nicht geprüft), nicht als Ablehnung.

Die technische Modell-UUID stammt aus dem Header der lokalen `.data`-Datei. Der
**Pfad** dieser Datei wird für die Vorprüfung **und** für die Modell-Admission
von derselben Stelle aufgelöst: `STTModelManager.locate_local_path` – mit den
Roots der Snapshot-Discovery (Engine-`custom_paths`, einschließlich der
Engine-Optionen `model_dir`/`model_path`/`model_root`, Download-Root,
`VOICESTT_KROKO_MODEL_ROOT`, Managed-Root). Eine nur per Engine-Option
konfigurierte Custom-Root genügt; eine globale Umgebungsvariable ist nicht
erforderlich.

### 4.2 Prüfzeitpunkte und Race-Freiheit

Serverinitialisierung (vor der ersten Modell-Admission), `POST /api/models/refresh`,
`PUT /api/models/active` (gegen die Kandidaten-Settings),
`PATCH /api/v2/settings/server` bei `kroko.forceCommunity`-Änderung sowie
explizit über `POST /api/kroko/license/refresh` (Admin). Unveränderter Schlüssel
und frischer Nachweis lösen keine Doppelprüfung aus. Umgebungsänderungen
außerhalb des Prozesses erfordern einen Neustart.

Der aktuelle Betreiberintent (Force, effektiver Key) wird **synchron unter einer
Sperre gelesen und gebunden** (`KrokoLicenseGate.prepare`). Nur der Netzwerkweg
läuft – bei `background=True` – auf einem Daemon-Thread (nie im Event-Loop) und
trägt das Generations-Token, mit dem er gestartet wurde. Ein verspäteter Worker
**bindet nie** einen Intent und kann nur auf genau seine Generation anwenden;
nach Abschluss wird ausschließlich der **aktuelle** Zustand gelesen
(`current_decision`). Ein neuerer Key oder `forceCommunity=true` bleibt dadurch
gegen eine spät eintreffende alte Antwort maßgeblich; ein verworfenes Ergebnis
führt zu keinem Grant und keiner zweiten Netzwerkanfrage.

### 4.3 Force Community und Key-Entzug

Ein bestätigter `kroko.forceCommunity`-Patch entzieht die Python-Freigabe
**synchron, bevor die Antwort zurückkehrt** (`apply_kroko_force_change`). Ab
diesem Moment weist `_submit_scheduler_job` – der einzige Einstieg für
Recorder- und OpenAI-Aufträge – neue Aufträge ab, solange das aktive Modell ein
Pro-Modell ist und Force gesetzt oder der Key entfernt ist
(`proAdmissionRevoked`). Der Modell-Abgleich (Pro → Community) läuft danach
im Hintergrund (§4.4). Dasselbe gilt für das Entfernen des Keys aus den
Engine-Optionen. Ablauf des kurzlebigen Nachweises (≤ 60 s) sperrt keine bereits
laufende Pro-Instanz; er verhindert nur neue Admissions.

### 4.4 Modellabgleich nach einer Lizenzentscheidung

Nach einem Hintergrund-Ergebnis oder einer Force-Änderung stößt der Service einen
**Reconcile** an (`reconcile_kroko_models`): Er nutzt den vorhandenen
transaktionalen Refresh mit Last-Known-Good-Rollback und aktualisiert dadurch
Berechtigung, Registry-Snapshot, aktive Zuordnung und die öffentliche
Statusprojektion in einem Zug. Er schaltet nichts nativ „heiß“ um:

* Ein Kroko-Kandidat wird nie neben einer anderen lebenden Kroko-Instanz geprüft.
  Dieselbe Datei, die gesund läuft, wird nicht noch einmal geladen.
* Sperrt nur die laufende Instanz den Kandidaten und ist der Server im Leerlauf,
  wird sie über den regulären Entlade-Pfad (`unload_models`) freigegeben und der
  Refresh einmal wiederholt; die Aktivierung lädt das neue Modell in den freien
  Slot. Bei aktiven Sessions/Transkriptionen wird zurückgestellt
  (`modelRefreshPending`, `lastReconcile.result = "deferred"`) – niemals erzwungen.
* Eine erfolgreiche Lizenzprüfung allein behauptet **keine** aktive Instanz:
  `activeKrokoModels` zeigt immer das tatsächlich geladene Modell.

`GET /api/models/management` führt dazu `krokoRuntime`, getrennt nach
installierter Variante, Lizenzberechtigung, gewünschten Modellen, tatsächlich
aktiven Modellen, nativem Pro-Kontext und Neustartbedarf (Felder in
[Kroko-ONNX](kroko-onnx.md#modell--und-lizenzwechsel-im-laufenden-prozess)).

### 4.5 Python-Freigabe versus nativer Lizenzkontext

Die getestete Kroko-ONNX-1.12.9-Pro-Runtime besitzt einen prozessweiten
Lizenz-Singleton samt Reporter. Das erfolgreiche Neuladen eines Modells beweist
nicht, dass dieser Kontext zurückgesetzt wurde. Deshalb gilt, unabhängig vom
Python-Status:

* Ein neuer oder rotierter Key wird für einen bereits initialisierten
  Pro-Kontext **nicht** freigegeben: keine neue Prüfung, keine Admission,
  Status `restartRequired` mit `key_context_change_requires_restart`.
* Ein anderes Pro-Modell als das bereits initialisierte ist gesperrt
  (`pro_identity_change_requires_restart`); ein Pro-Modell ohne Key ebenso
  (`pro_requires_key`).
* Pro → Community ist möglich, beendet den nativen Reporter aber nicht;
  `nativeProContextActive` bleibt bis zum Neustart `true`. Der Server macht
  daher keine Aussage „ohne Netz“.
* **Beobachtung (26.10.2026, isolierter Test mit echtem Provider):** Solange
  in einem Prozess ein nativer Pro-Reporter existiert – auch nach dem
  Schließen des Recognizers –, lehnt der Lizenzdienst eine *zusätzliche*
  externe Prüfung desselben Keys für dasselbe Modell ab (`license_rejected`),
  während frische Prüfungen ohne nativen Pro-Kontext `VALID` liefern. Der
  60-s-Nachweis ist dann nicht erneuerbar. Deshalb gilt für **dasselbe**
  Pro-Modell unter **demselben** Key die bestätigte native Ladung als
  Berechtigungsnachweis (`licenseSource: "native_context"`, keine weitere
  Provider-Verbindung); ein anderes Modell, ein anderer Key oder Force Community
  werden davon nie abgedeckt. Die Gültigkeit der Lizenz während des laufenden
  Betriebs bleibt Sache der nativen Runtime.

Diese Regeln setzt `VoiceSTT/kroko/native_guard.py` **vor** dem nativen Laden um
(Load-Probe, Refresh, Recovery, Scheduler-Erstellung, Engine-Konstruktor).

**Fehlerfälle und Grenzen.** Echte Pro-Modellrechte, Anbieter-Connection-Limits,
Nutzungsreports und Widerruf sind separat zu qualifizieren; der native
Free-/Pro-Build wird durch einen Key nicht ersetzt (Buildauthority:
[BUILD.md](../build/BUILD.md)). Status-, Fehler- und Auditpfade sind
secret-redigiert (keine Keys, keine Key-URLs in Logs/Antworten/Evidenz).
Echte Lizenzserver- und Native-Integrationstests sind Opt-in
(`VOICESTT_KROKO_LIVE_TESTS=1`, `VOICESTT_KROKO_NATIVE_TESTS=1`); siehe
[Testing](testing.md).

## Nicht-Ziele und Regressionstests

Die Refaktorierung erweitert keine Admin-, OpenAI-, Log- oder V2-WebSocket-Rechte und fügt keine neue persistierte Credentials-Datenbank hinzu. Die automatische Kroko-Lizenzprüfung (§4) ist Produkt-Entitlement mit eigenem Lifecycle: Sie startet an Initialisierung, Modell-Refresh/-Switch, Force-Community-Änderung und explizitem Recheck – nur mit Key und ohne Force, niemals aus bloßem Key-Besitz –, aktiviert von sich aus kein Modell nativ und verändert keine nativen Kroko-Payloads.

```bash
python -m pytest -q tests/unit/test_server_security_modularization.py tests/unit/test_openai_compatible_endpoint.py tests/unit/test_server_operations.py
```

Die Tests verwenden synthetische Keys bzw. Fake-Lizenztransporte. Eine grüne CI qualifiziert die implementierten Auth- und Fehlerverträge, **nicht** die echte Kroko-Pro-Lizenz. Siehe [Testing](testing.md), [Modulübersicht](module-map.md) und [Modularisierungsfahrplan](architecture/server-modularization-roadmap.md).
