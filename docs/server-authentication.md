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

## 4. Kroko-On-Premise-Modelllizenz – ausdrücklich kein API-Login

`KrokoLicenseGate.check_model(model_uuid, options=..., force_community=..., connect=...)` delegiert auf `VoiceSTT/kroko/credentials.py`, `license_api.py` und `license_state.py`. Eine Prüfung ist nur bei **explizitem** Aufruf möglich; weder die Security-Service-Konstruktion noch der Serverstart startet automatisch eine Lizenzabfrage.

Positive synthetische Ergebnisse bleiben an die konkret geprüfte Modell-UUID und eine begrenzte Frische gebunden; Key-Wechsel, Force Community, Ablauf und veraltete Prüfgenerationen entwerten die Freigabe. Das ist derzeit **kein** qualifizierter produktiver Pro-Entitlement-Vertrag, keine automatische Modellfreischaltung, keine Runtime-Auswahl und keine Berechtigung für andere Modell-UUIDs. Echte Anbieter-/Widerrufs-/Connection-Limits-/Reporting-Tests bleiben separat. Der native Free-/Pro-Build wird durch einen Key nicht ersetzt; Buildauthority: [BUILD.md](../build/BUILD.md).

## Nicht-Ziele und Regressionstests

Die Refaktorierung erweitert keine Admin-, OpenAI-, Log- oder V2-WebSocket-Rechte, fügt keine neue persistierte Credentials-Datenbank hinzu und verändert keine nativen Kroko-Payloads.

```bash
python -m pytest -q tests/unit/test_server_security_modularization.py tests/unit/test_openai_compatible_endpoint.py tests/unit/test_server_operations.py
```

Die Tests verwenden synthetische Keys bzw. Fake-Lizenztransporte. Eine grüne CI qualifiziert die implementierten Auth- und Fehlerverträge, **nicht** die echte Kroko-Pro-Lizenz. Siehe [Testing](testing.md), [Modulübersicht](module-map.md) und [Modularisierungsfahrplan](architecture/server-modularization-roadmap.md).
