# AP-KR-020 Fortsetzung – Implementierung (Nachtrag 23.10.2026)

Implementiert auf Branch `feat/v2-unified-kroko-ap020` gegen Basis `b6e5f11`.
Diese Datei beschreibt den tatsächlich implementierten Stand; sie ersetzt
keine historische Akte.

## 1. Neue produktive Module (`VoiceSTT/kroko/`)

- **`license_runtime.py`** – zentrale, flüchtige Lizenz-/Runtimeautorität
  (`LicenseRuntimeAuthority`, thread-safe): Zustände `NOT_CHECKED`,
  `CHECKING`, `VALID`, `CHECK_FAILED`, `INVALID`; Generation, opake
  Credentialrevision (einwegiger Key-Fingerprint `k:<hex16>`, niemals das
  Keymaterial), Payloadidentität, bestätigte Modell-IDs, Nachweisalter mit
  konservativer Obergrenze (60 s). Entscheidungen
  `pro_enabled_for(model_id)` / `pro_enabled_global()` exakt nach der
  Produktformel, modellrechtsscharf. Verifizierer-Schnittstelle
  (`LicenseVerifier`, `UnqualifiedLicenseVerifier` als fail-closed
  Produktdefault). Redaktierte Statusprojektion (`public_snapshot`,
  keine Secrets/Rohdaten). Keine Netzwerk-, keine Native-, keine
  Persistenzpfade. Community-Fallback-Helfer (`community_fallback_model`,
  deterministisch, manifestgebunden, ohne Netzwerk).
- **`bootstrap.py`** – kalter Bootstrap vor sämtlichen nativen Imports:
  exakt ein privater Payloadroot an `sys.path[0]` (plus Windows-DLL-Pfad),
  Marker-Verifikation, Ablehnung bereits geladener oder fremder globaler
  nativer Runtimes als Konflikt, Idempotenz für dieselbe Wurzel,
  Verweigerung einer zweiten Wurzel im selben Prozess. Selbst
  nativeimportfrei (nur `sys.modules` + `find_spec`). Über
  `VOICESTT_KROKO_PAYLOAD_ROOT` opt-in; ohne Variable verifizierter No-op
  (bestehende Single-Runtime-Installationen laufen unverändert).
- **`supervisor.py`** – Besitzerprozessaufsicht: genau eine aktive
  Generation, Terminierung der alten Generation mit bestätigtem Exit vor
  Start der neuen, Startdeadline, begrenztes Retry/Backoff je
  Konfigurationsgeneration (kein Crashloop bei unverändertem Stand),
  Verwerfung generationfremder Readiness-/Status-/Jobergebnisse
  (`accept_event`). Nativeimportfrei und secretfrei; Kinder melden die
  Generation über `VOICESTT_KROKO_OWNER_GENERATION`. Fingerprint über
  secretfreie Konfiguration (`config_fingerprint`).
- **`__init__.py`** – Paketvertrag ergänzt; die Schlüsselregel bleibt:
  Das Paket sieht niemals Keymaterial, nur opake Fingerprints.

## 2. Serverintegration (`api_fastapi_server/server.py`, HTTP-Adminfläche)

- `ServerSettings.kroko_force_community: bool = False` als
  `ACTIVE_RUNTIME_SETTINGS` + `BOOL_SETTINGS` (live schaltbar, persistiert
  als Serverabsicht; abgeleitete Runtime/`pro_enabled` werden nirgends
  persistiert). Keyänderungen bleiben `startup_only` und wirken über die
  Prozessgrenze.
- `VoiceSTTService` besitzt die volatile `kroko_license`-Autorität und
  bindet sie bei Start, Modellwechsel und Force-Wechsel neu
  (`_refresh_kroko_intent`): jede Änderung verwirft atomar den alten
  Nachweis (Generation bump).
- Fail-closed Lizenzgate in `_switch_models_locked`
  (`_enforce_kroko_license_gate`, vor jeder Modellzustandsänderung):
  Community passiert, Pro nur mit aktuellem `VALID`-Nachweis für genau
  diese manifestierte ID; unmanifestierte Modelle bleiben als auditierte
  Operator-Overrides möglich, werden aber niemals `VALID`.
- Startup-Community-Fallback (`_enforce_kroko_startup_models`): ohne
  aktuellen Nachweis wird die In-memory-Konfiguration deterministisch auf
  das manifestierte Community-Modell zurückgeführt (nur für manifestiertes
  Pro; Operator-Intent auf Disk unverändert), mit redaktierten
  Audit-Ereignissen (`kroko.pro_refused_community_fallback`,
  `kroko.unmanaged_model_selected`).
- `model_lifecycle_status()` projiziert `"license": public_snapshot()`
  (redaktiert, HTTP-Adminfläche). V2-Session-Wire (`ready`,
  `sessionCapabilities`, `settings.changed`) unverändert.
- `create_app()` ruft den kalten Bootstrap vor Engine-Imports auf
  (No-op ohne `VOICESTT_KROKO_PAYLOAD_ROOT`).

## 3. Verträge für die vorbereitete AP-KR-030-Paketierung

Die LAB-Arbeit (`voice-stt-server-ap030-lab`, lesend genutzt, nicht
verändert) verlangte von AP-020 Bootstrap-, Native-API-,
Komponentenidentitäts- und Supervisor-Verträge. Geliefert:

- Bootstrap-Vertrag: `bootstrap.cold_select` (Semantik s. o.) als
  ersetzender offizieller Vertrag für `cold_select`-LAB-Platzhalter.
- Supervisor-Vertrag: `supervisor.OwnerSupervisor` (eine Generation,
  Deadline, Retry-Budget, bestätigter Exit, `accept_event`) als ersetzender
  Vertrag für den fehlenden LAB-Supervisor.
- Lizenz-/Statusvertrag:
  `license_runtime.public_snapshot`-Schema (Felder `status`, `generation`,
  `proEnabled`, `validatedModelIds`, `keyPresent`, `forceCommunity`,
  `credentialRevision`, `runtimeIdentity`, `reasonCode`,
  `proofAgeSeconds`, `maxProofAgeSeconds`).
- Native-API: **keine Ergänzung in dieser Fortsetzung** (Entscheidung A
  als Folgeauftrag); `PATCH_SET_REVISION`, Fingerprints und Buildinputs
  unverändert, keine neue Nativeprovenienz erforderlich.
- Komponentenidentität: interim `payload:<root>` /
  `unmanaged-global-runtime` als `runtimeIdentity`; offizielle
  AP-030-Komponentenidentität bleibt Folgearbeit (LAB-Schema
  `LOCAL_NOT_QUALIFIED` wird nicht übernommen oder umgedeutet).

## 4. AP-KR-025-Integration offengehalten

Kein zweiter Modellkatalog, kein Downloader implementiert. Das Lizenzgate
schlüsselt ausschließlich über den bestehenden
`VoiceSTT/kroko/models.py`-Manifest (`id`/Dateiname); kataloggelieferte
Einträge (PR #13, `catalog.py`) werden übernommen, sobald gemergt, ohne
diesen Pfad zu ändern. Die fehlende Abbildung Portal-UUID → manifestierte
ID ist als offene Voraussetzung in der Übergabe festgehalten.
