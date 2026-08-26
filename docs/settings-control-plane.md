# Settings-Control-Plane (AP-SRV-050)

Diese Datei beschreibt die mit AP-SRV-050 vorgelegte zentrale
Settings-Control-Plane des Servers: Registry, Revision/Transaktion, Apply
Policies, Persistenz, REST-v2-Oberfläche und den Session-Patch-Port, den der
spätere SRV-040-Wirehandler für `session_settings.patch` aufruft.

Ergänzend gilt der technische Contract-Freeze der einheitlichen
Triggerarchitektur (Abschnitt Settings-Control-Plane) sowie die
Bediendokumentation in [`docs/fastapi-server.md`](fastapi-server.md).

## 1. Zweck und Abgrenzung

Die Control Plane ist die **eine wiederverwendbare Settingsarchitektur** des
Servers. Sie definiert für jede serververwaltete Einstellung zentral:

```text
key, scope, auth, type, constraints, defaultValue,
requestedValue, effectiveValue, applyPolicy
```

Sie erfindet keine zweite Persistenzschicht. Werte und der monotone
`settingsRevision` liegen in derselben bestehenden Laufzeit-JSON-Datei, die der
vorhandene `RuntimeConfigStore` bereits atomar verwaltet. Bestehende Mechanismen
(`ServerSettings`, `coerce_setting_value`, `persist_settings`, Admin-Key-Prüfung)
werden über einen schmalen Port wiederverwendet statt dupliziert.

Nicht in diesem Paket:

- vollständiger v2-WebSocketlayer (AP-SRV-040);
- Wake-Word-Detection-/Katalogarbeit (AP-SRV-060);
- Client-UI/Credential Manager (AP-CLI-030);
- Vollmigration fachfremder Altsettings und Legacyabbau (AP-SRV-070).

### Scopes

- `session` – pro Session anpassbar, Sessionrecht;
- `server` – serverweit, Admin-Key;
- `client_local` – ausdrücklich keine Serverpersistenz (nur Metadaten des
  Vertrags; der Server behauptet darüber keine Autorität).

### Apply Policies

- `live` – wirkt sofort für neue Admissions;
- `next_activation` – wirkt für die nächste Activation; eine laufende
  Activation behält ihren eingefrorenen Snapshot;
- `next_session` – wirkt erst auf neu aufgebaute Sessions;
- `server_restart` – wirkt erst nach Serverneustart (nie als live dargestellt).

## 2. Registry und Ownership

Die Registry lebt unter `api_fastapi_server/settings_control/` und ist die
einzige Quelle für Keynamen. Es gibt keine zweite lose Liste von Settingkeys im
Server.

Verbindliche Schlüssel (Contract-Freeze, Abschnitt Timervertrag):

| Key | Typ | Default | Bereich | Bereich | Apply |
|---|:--:|--:|--:|:--:|---|
| `activation.initialSpeechTimeoutMs` | int | 15000 | 100–3600000 | Session | `next_activation` |
| `activation.followupTimeoutMs` | int | 3000 | 100–60000 | Session | `next_activation` |
| `activation.segmentWatchdogInitialMs` | int | 600000 | 60000–3600000 | Session | `next_activation` |
| `activation.segmentWatchdogRefreshMs` | int | 180000 | 30000–600000 | Session | `next_activation` |
| `activation.segmentWatchdogWarningMs` | int | 30000 | ab 5000, kleiner als wirksame Frist | Session | `next_activation` |
| `activation.closingRecoveryTimeoutMs` | int | 5000 | 1000–30000 | Session | `next_activation` |

Weitere Schlüssel:

- `wakeWord.sensitivity` – float 0.0–1.0, Default 0.5, `next_activation`;
- `wakeWord.selection` – Liste kanonischer IDs, `next_session`
  (Admission/Detection bleibt AP-SRV-060);
- `runtimeSuppression.manual` / `runtimeSuppression.wakeWord` – bool, `live`,
  Sessionrecht;
- `wakeWord.globalDisabledIds` – serverweite Disableliste, Admin-Key,
  `next_session`.

Die öffentliche API verwendet **Millisekunden**. Wo die interne
Serverkonfiguration Sekunden nutzt (`ActivationController`), konvertiert der
`ActivationSettingsProvider` zentral und exakt; es entsteht keine Float-Drift
auf Schema/Response.

## 3. Requested vs. Effective

Die Control Plane führt beide Werte getrennt:

- `requestedValue` – letzter bestätigter Wunsch;
- `effectiveValue` – was die nächste Activation beziehungsweise der nächste
  Sessionaufbau tatsächlich sieht.

`next_activation`-Änderungen sind bestätigt/requested, ändern aber eine
**laufende Activation nicht**. `next_session` und `server_restart` werden nie
als live dargestellt; die Seams `realize_next_session()` beziehungsweise
`realize_after_restart()` ziehen sie beim jeweiligen Aufbau nach.

## 4. Revision und atomare Patches

`settingsRevision` ist serverautoritativ und monoton. Jede bestätigte
Änderung erhöht sie **genau einmal** pro logischer Transaktion. Ein Patch
erwartet `baseSettingsRevision` und `changes`:

- Basis trifft nicht die aktuelle Revision → `settings_revision_conflict`;
- irgendein Feld ungültig → ganzer Patch abgelehnt (`settings_rejected`)
  mit feldbezogenen, maschinenlesbaren Fehlern (`field`, `code`, `message`);
- kein Teilanwenden, keine teilweise Persistenz, keine
  Revisionsänderung derselben abgelehnten Transaktion.

Cross-Field-Regel: `activation.segmentWatchdogWarningMs` muss kleiner sein als
jede der beiden wirksamen Watchdog-Fristen (Initial und Refresh). Ein
C1-Breitbereich von 0.01–3600 ist damit kein gültiger Endvertrag.

## 5. Persistenz

`RuntimeSettingsStore` (Subklasse des bestehenden `RuntimeConfigStore`)
persistiert das Serverdefault-Overlay und `settingsRevision` als additive
Top-Level-Felder **derselben** `runtime.json`. Das bestehende `settings`-Feld
der Service-Persistenz bleibt unberührt; Schreiben erfolgen atomar via
`os.replace`. Es gibt keine zweite JSON-Datei und keine Datenbank.

## 6. REST-v2-Oberfläche

| Endpunkt | Auth | Bedeutung |
|---|---|---|
| `GET /api/v2/settings/schema` | öffentlich | vollständiges Schema, keine Secrets |
| `GET /api/v2/settings/server` | öffentlich | nicht geheime Requested/Effective-Werte der Serverdefaults |
| `PATCH /api/v2/settings/server` | `X-VoiceSTT-Admin-Key` / Bearer | atomarer Patch mit Revisionprüfung |

`GET /api/v2/settings/server` liefert für jeden Key `scope`, `auth`, `type`,
`constraints`, `requestedValue`, `effectiveValue` und `applyPolicy`.
Geheime Werte erscheinen nie – in Schema, Read-, Patch- oder Fehlerantwort,
Event oder Log (`"redacted": true`).

`PATCH /api/v2/settings/server` reicht den bestehenden Admin-Key-Guard des
Servers durch. Rückmeldungen: `200` (applied/no_change), `409`
(settings_revision_conflict), `422` (settings_rejected mit Feldfehlern).

## 7. Session-Patch-Port für SRV-040

`SessionSettingsState.apply_patch(...)` ist die domainseitige Operation für
`session_settings.patch`. Sie ist parserfrei und liefert ein strukturiertes
`:class:PatchResult`, das SRV-040 direkt in `command.ack` projizieren kann
(`accepted`, `result`, `settingsRevision`, `changedKeys`, `effectiveSettings`,
`errors`). Sessions teilen denselben globalen Revisionsstrom; konkurrierende
Patches auf derselben Base entscheiden deterministisch, genau einer gewinnt.

## 8. Schnittstelle zu SRV-030

`ActivationSettingsProvider` ist der schmale Port, der die sechs
Activation-Timings beim Start einer Activation latency. Seine
`SessionActivationSettingsProvider`-Implementierung konvertiert die
Millisekundenwerte exakt in die Sekundenwerte des `ActivationController`.
Die tatsächliche Abnahme in den Controller-Konstruktor bleibt der finalen
SRV-030-Korrektur vorbehalten (Markierung im Bericht:
`REQUIRES_FINAL_SRV_030_BINDING`).

## 9. Module

| Modul | Verantwortung |
|---|---|
| `settings_control/registry.py` | Keydefinitionen, Scopes, Apply Policies, Schema |
| `settings_control/validation.py` | Koerzion, Bereichs-, Typ- und Cross-Field-Validierung |
| `settings_control/control_plane.py` | Revision, Serverdefaults, Server-Patch-Transaktion |
| `settings_control/session.py` | Session-Zustand und `session_settings.patch` |
| `settings_control/provider.py` | Activations-Port und ms→s-Konversion |
| `settings_control/store.py` | `RuntimeSettingsStore` auf `RuntimeConfigStore` |
| `settings_control/rest.py` | Thin REST-v2-Router (fastapi lazy importiert) |
| `settings_control/metadata.py` | Serverversion/Commit (best effort) |