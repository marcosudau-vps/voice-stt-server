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
| `kroko.py` – `KrokoLicenseGate` | **Expliziter** Adapter für modellbezogene externe On-Premise-Lizenzprüfung | Von `SecurityService` verfügbar; kein automatischer produktiver Aufruf |

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
vierteilige Produktentscheidung über dem flüchtigen `KrokoLicenseState`
(`VoiceSTT/kroko/license_state.py`):

```text
Kein API-Key vorhanden      → Community (keine Netzwerkanfrage)
Community erzwungen          → Community (keine Netzwerkanfrage)
Key vorhanden, nicht erzw.   → modellbezogene Lizenzprüfung
Prüfung gültig (VALID)       → Pro für genau dieses Modell freigegeben
ungültig / Fehler / Ablauf   → Community (fail-closed)
```

**Eingänge.** Effektiver Key ausschließlich aus
`VoiceSTT.kroko.credentials.effective_recognizer_key` (Priorität:
`recognizer.key` – auch leer suppressiv – vor Top-Level-`key` vor den vier
Umgebungsvariablen `KROKO_API_KEY`, `KROKO_ONNX_KEY`, `VOICESTT_KROKO_ONNX_KEY`,
`KROKO_KEY`). Betreiberintent `kroko.forceCommunity` aus der
Settings-Control-Plane (serverweit, Admin, live, persistiert als Absicht).
Technische Modell-UUID aus dem lokalen `.data`-Dateiheader
(`VoiceSTT.kroko.models.license_uuid_for`) – dieselbe Identität, die die
native Runtime ihrer eigenen Lizenzprüfung übergibt.

**Prüfungszeitpunkte.** Serverinitialisierung (vor der ersten Modell-Admission),
`POST /api/models/refresh`, `PUT /api/models/active` (gegen die Kandidaten-Settings),
`PATCH /api/v2/settings/server` bei `kroko.forceCommunity`-Änderung
(Hintergrund-Thread, nie Event-Loop-blockierend) sowie explizit über
`POST /api/kroko/license/refresh` (Admin; wendet eine frische Pro-Freigabe über
den transaktionalen Model-Refresh an). Unveränderter Schlüssel + frischer
Nachweis lösen keine Doppelprüfung aus. Umgebungsänderungen außerhalb des
Prozesses erfordern einen Neustart.

**Zustandswechsel.** Key-/Force-Wechsel invalidieren per Generation sofort;
verspätete und überlappende Antworten gelten nur für die aktuelle Generation;
negative Antworten, Timeouts und Transportfehler geben nie frei; abgelaufene
Nachweise verfallen zu `CHECK_FAILED`. `pro_enabled` ist abgeleitet und
flüchtig – persistiert werden nur `forceCommunity` und Modellabsicht, niemals
Keys, Status oder Freigaben. Neustart beginnt bei `NOT_CHECKED`.

**Integration mit dem Modellmanager.** `STTModelManager` bleibt alleinige
Modell-Authority (Verfügbarkeit, Auswahl, Last-Known-Good, Provisionierung).
Er erhält nur eine lesende `license_policy`-Funktion: kommerzielle
Kroko-Produkte sind in `_eligible`/`candidate_eligible` genau dann zulässig,
wenn für die UUID der tatsächlich vorliegenden Datei ein frischer Nachweis
besteht; ohne Policy gilt das Legacy-Verhalten. Die LKG-Wiederherstellung
filtert entfallene Pro-Rollen heraus. Community-Modelle sind auf Free- **und**
Pro-Installationen zulässig (die native Lizenzprüfung wird für sie nicht
konsultiert); kommerzielle Modelle zusätzlich nur bei passender installierter
Runtime-Variante. `public_snapshot()` trägt `"scope": "model"` – eine
Berechtigung für Modell A beweist nichts für Modell B; Enforcement nutzt
ausschließlich `pro_enabled_for(uuid)`.

**Fehlerfälle und Grenzen.** Echte Pro-Modellrechte, Anbieter-Connection-Limits,
Nutzungsreports und Widerruf sind separat zu qualifizieren; der native
Free-/Pro-Build wird durch einen Key nicht ersetzt (Buildauthority:
[BUILD.md](../build/BUILD.md)). Status-, Fehler- und Auditpfade sind
secret-redigiert (keine Keys, keine Key-URLs in Logs/Antworten/Evidenz).
Echte Lizenzserver-Integrationstests sind Opt-in
(`VOICESTT_KROKO_LIVE_TESTS=1`); siehe [Testing](testing.md).

## Nicht-Ziele und Regressionstests

Die Refaktorierung erweitert keine Admin-, OpenAI-, Log- oder V2-WebSocket-Rechte und fügt keine neue persistierte Credentials-Datenbank hinzu. Die automatische Kroko-Lizenzprüfung (§4) ist Produkt-Entitlement mit eigenem Lifecycle: Sie startet an Initialisierung, Modell-Refresh/-Switch, Force-Community-Änderung und explizitem Recheck, niemals aus bloßem Key-Besitz, und verändert keine nativen Kroko-Payloads.

```bash
python -m pytest -q tests/unit/test_server_security_modularization.py tests/unit/test_openai_compatible_endpoint.py tests/unit/test_server_operations.py
```

Die Tests verwenden synthetische Keys bzw. Fake-Lizenztransporte. Eine grüne CI qualifiziert die implementierten Auth- und Fehlerverträge, **nicht** die echte Kroko-Pro-Lizenz. Siehe [Testing](testing.md), [Modulübersicht](module-map.md) und [Modularisierungsfahrplan](architecture/server-modularization-roadmap.md).
