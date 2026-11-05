# 08 – Authentisierung, Zugriffskontrolle und Kroko

`api_fastapi_server/security/service.py` bündelt **vier getrennte**
Mechanismen in `SecurityService`. Der Moduldocstring stellt ausdrücklich klar,
dass sie nicht austauschbar sind:

| Mechanismus | Klasse | Schützt |
| --- | --- | --- |
| Admin-Schlüssel | `AdminGate` (`security/admin.py`) | Verwaltungsrouten (Seite 06) |
| OpenAI-Bearer | `OpenAIGate` (`security/openai.py`) | `/v1/*` |
| Log-Tokens | `LogTokenAuthority` + `LogGate` (`security/logs.py`) | `/api/logs/*`, `/ws/logs` |
| Kroko-Produktlizenz | `KrokoLicenseGate` (`security/kroko.py`) | Zulassung von Kroko-**Pro**-Modellen |

Die Transkriptions-WebSockets `/ws/transcribe` und `/ws/v2` haben **keine**
eigene Authentisierung; Begrenzung erfolgt dort über `max_sessions` und
`max_active_speakers`. (Eine Netzwerk-/Proxy-Absicherung ist im Code nicht
enthalten.)

## 1. Admin-Schlüssel

- Quelle: `admin_api_key` (CLI `--admin-api-key`) oder `VOICESTT_ADMIN_API_KEY`
  (zur Laufzeit gelesen). In YAML verboten; wird nicht in `runtime.json`
  übernommen und aus `public_dict()` entfernt.
- Vergleich mit `secrets.compare_digest`.
- Akzeptierte Header: `X-VoiceSTT-Admin-Key`, `Authorization: Bearer …`,
  `X-Admin-Key`.
- **Ohne** Schlüssel: nur Loopback-Clients (`127.0.0.1`, `::1`, `localhost`,
  `testclient`) dürfen verwalten, andere erhalten `403` mit Hinweis auf
  `VOICESTT_ADMIN_API_KEY`.
- `GET /api/config` meldet `adminAuthRequired`.

Hinweis: Hinter einem Reverse-Proxy auf demselben Host sieht der Server
`127.0.0.1` als Client; ob das gewollt ist, muss der Betrieb entscheiden – der
Code wertet keine Forwarded-Header in `AdminGate` aus.

## 2. OpenAI-kompatibler Schlüssel

- Quelle: `openai_api_key` (CLI `--openai-api-key`) oder `VOICESTT_API_KEY`.
- Nur `Authorization: Bearer <key>` mit exakter Übereinstimmung
  (String-Vergleich). Fehlschlag → `401`, Audit-Event
  `authentication.failed` mit `reason: "invalid_api_key"`.
- Ohne Schlüssel sind `/v1/*` offen. Abschalten mit `--disable-openai-api`
  (dann `404`).

## 3. Log-Zugriff

- Bei jeder Transkriptionssitzung erzeugt `create_log_access` ein Token
  (`uuid4().hex` doppelt, 64 Hex-Zeichen), gebunden an die `sessionId`,
  gültig 24 h, nur im Speicher (`LogTokenAuthority`).
- HTTP: Admin-Schlüssel → Admin-Scope (alle Sitzungen/Kanäle); ohne
  konfigurierten Admin-Schlüssel auch Loopback → Admin-Scope; sonst Token →
  nur eigene Sitzung, nur Kanäle `audit`, `performance`, `transcription`.
- WebSocket: wie HTTP, aber **ohne** impliziten Loopback-Admin.

## 4. Kroko – Schlüssel, Lizenz, Native-Laufzeit

### Effektiver Schlüssel

`effective_recognizer_key(options)` (`VoiceSTT/kroko/credentials.py`):

1. `options["recognizer"]["key"]`, falls vorhanden (auch leer – dann ohne Key),
2. sonst `options["key"]`,
3. sonst die erste gesetzte Umgebungsvariable aus `KROKO_API_KEY`,
   `KROKO_ONNX_KEY`, `VOICESTT_KROKO_ONNX_KEY`, `KROKO_KEY`.

Die Optionen kommen aus `transcription_engine_options` /
`realtime_transcription_engine_options` bzw.
`stt_engine_settings.kroko_onnx.engine_options` (`resolved_engine_options`,
`server.py:1300`). Schlüsselwerte werden in Logs, `runtime.json` und
öffentlichen Ausgaben entfernt (`redact_kroko_credentials`,
`VoiceSTT_server/credential_redaction.py`).

### Modellbezogene Pro-Berechtigung

`KrokoLicenseGate.decide(model_uuid, ...)` ist netzwerkfrei und liefert:

| `tier` | `reason` | Bedingung |
| --- | --- | --- |
| `pro` | `license_valid` | frische, an genau diese Modell-UUID gebundene `VALID`-Prüfung |
| `checking` | `check_in_progress` | Prüfung für dieses Modell läuft |
| `community` | `no_key` | kein Schlüssel |
| `community` | `force_community` | `kroko.forceCommunity = true` |
| `community` | letzter Prüfgrund, `check_required: true` | sonst |

Die Netzwerkprüfung (`check_onprem_license`, `VoiceSTT/kroko/license_api.py`)
öffnet eine WebSocket-Verbindung zum Kroko-Lizenzserver für **ein** Modell,
akzeptiert nur eine typisierte positive Antwort mit Frische
(`remaining_seconds`, `offline_timeout`) und begrenzt die Gültigkeit auf
höchstens 60 s. Ergebnisse: `NOT_CHECKED`, `VALID`, `INVALID`,
`CHECK_FAILED`. Sie läuft nur explizit (z. B. `POST
/api/kroko/license/refresh`) oder im Lebenszyklus, nie als Startnebenwirkung
und nie im Eventloop. Generationstokens verhindern, dass eine späte Antwort
eine neuere Schlüssel-/Modusentscheidung überschreibt.

### Force-Community

`kroko.forceCommunity` (Server-Scope, Admin, `live`) entzieht eine
Pro-Freigabe **vor** der HTTP-Antwort und blockiert neue Pro-Jobs sofort; der
Abgleich von Modellen/Scheduler läuft danach in einem Daemon-Thread
(`patch_settings_server_v2`, `service.apply_kroko_force_change`).

### Native-Guard und Neustartpflichten

`KrokoNativeGuard` (`VoiceSTT/kroko/native_guard.py`) setzt die im Docstring
dokumentierten Messbefunde der Native-Laufzeit als harte Vorab-Regeln um:

| Code | Regel |
| --- | --- |
| `concurrent_native_identity` | höchstens eine native Kroko-Instanz; Final und Realtime teilen sie |
| `pro_identity_change_requires_restart` | nach einem Pro-Modell darf nur dasselbe Pro-Modell erneut geladen werden |
| `key_context_change_requires_restart` | ein Pro-Kontext wird nie mit anderem oder entferntem Schlüssel wiederverwendet |
| `pro_requires_key` | Pro-Modell ohne Schlüssel wird nicht geladen |

Community-Modelle werden nie durch Pro-Zustand blockiert. Öffentlicher
Status: `liveNativeInstances`, `nativeProContextActive`,
`nativeProLicenseConfirmed`, `nativeProModelUuid`.

`VoiceSTTService.kroko_runtime_status()` (`server.py:6802`) trennt fünf
Fakten: installierte Variante (`installedVariant`), Lizenzberechtigung
(`licenseEntitled`, `licenseModelUuid`, `licenseSource`), gewünschte Modelle
(`desiredModels`), aktive Modelle (`activeKrokoModels`, `activeProPresent`)
und Neustartbedarf (`restartRequired`, `restartReason`), dazu
`forceCommunity`, `proAdmissionRevoked`, `modelRefreshPending`,
`lastReconcile`.

### Installierte Variante

`installed_kroko_variant()` (`stt_model_management.py:46`) liest die validierte
Build-Identität; im Quell-Checkout ohne Identität ist sie `unknown`
(beobachtet: `/api/v2/info` → `runtime.krokoVariant: null`,
`identityStatus: "incomplete"`). Community-Lizenzklassen (`community`,
`community-unresolved`) laden auf `free`- und `pro`-Laufzeiten.

## 5. Technische Nutzung ≠ Weiterverteilungsrecht

Der Code trennt beides strikt:

- Die **Nutzung** eines Pro-Modells wird zur Laufzeit modellbezogen über
  Schlüssel + Lizenzprüfung entschieden (oben).
- Die **Weiterverteilung** von Modellen ist im Manifest pro Modell kodiert
  (`redistributionStatus`: Community `POLICY_REQUIRED`, Pro `PROHIBITED`).
  `KrokoModelEntry.redistributable` ist nur bei `ALLOWED` wahr – derzeit für
  keinen Eintrag.
- Die **Veröffentlichung** einer Distribution mit eingebetteter
  Pro-Laufzeit verlangt `redistribution_verified(...)`: Status `VERIFIED`,
  passende `upstreamRevision` und nicht-leere `evidenceRef`
  (`engineering/release/config.py:193`). Die kanonische Datei
  `build/kroko-redistribution.json` steht aktuell auf `status: "BLOCKED"`;
  eine echte Veröffentlichung bricht deshalb mit „BLOCKED: Pro runtime
  redistribution rights are not verified“ ab (`engineering/release/engine.py`).

Eine juristische Freigabe lässt sich aus dem Code nicht ableiten.

## Primäre Quellen

- [`api_fastapi_server/security/`](../../api_fastapi_server/security/service.py) – `service.py`, `admin.py`, `openai.py`, `logs.py`, `kroko.py`
- [`VoiceSTT/kroko/credentials.py`](../../VoiceSTT/kroko/credentials.py), [`license_api.py`](../../VoiceSTT/kroko/license_api.py), [`license_state.py`](../../VoiceSTT/kroko/license_state.py), [`native_guard.py`](../../VoiceSTT/kroko/native_guard.py), [`models.py`](../../VoiceSTT/kroko/models.py)
- [`api_fastapi_server/server.py`](../../api_fastapi_server/server.py) – `kroko_runtime_status` (6802), `resolved_engine_options` (1300)
- [`engineering/release/config.py`](../../engineering/release/config.py), [`build/kroko-redistribution.json`](../../build/kroko-redistribution.json)
- Tests: [`tests/unit/test_server_security_modularization.py`](../../tests/unit/test_server_security_modularization.py), [`tests/unit/test_kroko_license_lifecycle.py`](../../tests/unit/test_kroko_license_lifecycle.py), [`tests/unit/test_kroko_live_license.py`](../../tests/unit/test_kroko_live_license.py), [`tests/unit/test_kroko_pr15_final_correction.py`](../../tests/unit/test_kroko_pr15_final_correction.py), [`tests/unit/test_kroko_pr15_b1b2_regression.py`](../../tests/unit/test_kroko_pr15_b1b2_regression.py), [`tests/unit/test_kroko_native_integration.py`](../../tests/unit/test_kroko_native_integration.py), [`tests/unit/test_unified_product.py`](../../tests/unit/test_unified_product.py)
