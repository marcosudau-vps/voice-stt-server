# Korrekturlauf PR #15 – Implementierung (25.10.2026)

`SecurityService`-Struktur behalten; `KrokoLicenseState` zentrale flüchtige
Authority; keine zweite Modellregistrierung; keine nativen Build-/Fingerprint-/
Wire-/Persistenzschema-Änderungen.

## A – Automatischer Lizenz-Lifecycle

- **A4 `kroko.forceCommunity`** (`api_fastapi_server/settings_control.py`):
  neuer Registry-Key, Scope server, Auth admin, Typ bool, Default `false`,
  `APPLY_LIVE`, `has_server_default` (damit Overlay-persistiert, PATCHbar,
  Neustart-restore). Kein Secret, keine Session-Schatteneinstellung.
  → H-03 (Setting), D-05 (Doku).
- **Gate-Lifecycle** (`api_fastapi_server/security/kroko.py`): `decide()`
  (sync, netzfrei: bind → pro/checking/community + `check_required`),
  `refresh()` (skip-wenn-frisch, `check_model` sync oder pro-UUID
  Daemon-Thread mit In-Flight-Menge, `on_result`-Callback feuersicher),
  `check_model()` um `timeout` ergänzt (default 5 s, abwärtskompatibel).
  → H-02, H-07 (Mechanik), M-02.
- **Service-Verdrahtung** (`api_fastapi_server/server.py`):
  `settings_control`/`config_store` vor den Modellmanager gezogen (Policy liest
  persistierten Force-Intent vor erster Admission);
  `refresh_kroko_license_policy()` (nie werfend, fail-closed) an
  `__init__` (sync, vor erstem Refresh), `_refresh_stt_models_locked`,
  `_switch_models_locked` (gegen Kandidaten-Settings – Engine-Optionen/Key
  wechseln dort zur Laufzeit), PATCH-Hook bei Force-Änderung (background);
  neu `POST /api/kroko/license/refresh` (Admin, bounded, wendet frische
  Pro-Freigabe über Model-Refresh an); `krokoLicense`-Snapshot in
  `stt_model_management_status()`. Key-Auflösung ausschließlich
  `effective_recognizer_key` (unverändert); Env-Änderungen brauchen Neustart
  (dokumentiert). → H-02, H-03, H-07, A2/A3/A5.

## B – Modellfreigabe

- **UUID-Mapping** (`VoiceSTT/kroko/models.py`): `read_model_uuid()` (Header-JSON
  der `.data`-Datei, validierte kanonische UUID, offline) und
  `license_uuid_for()` (Manifest → lokale Datei → Header). Keine erfundenen
  UUIDs; ohne Datei/UUID fail-closed. → H-05, B3.
- **Manager-Policy** (`VoiceSTT_server/stt_model_management.py`): optionale
  `license_policy(product, candidate_path)`; kommerzielle Kroko-Produkte nur mit
  frischem modellgebundenem Nachweis in `_eligible`/`candidate_eligible`
  (Diagnose `kroko_license_not_entitled`), LKG-Restore filtert entfallene
  Pro-Rollen (`kroko_license_lkg_filtered`, Readiness neu bewertet). Ohne Policy
  Legacy-Verhalten (alle bestehenden Manager-Tests unverändert grün).
  Community (`community*`-Lizenzklasse) auf Free- **und** Pro-Runtime zulässig
  (nativ belegt, Root-README-konform); `commercial` strikt; Unbekannt legacy.
  → H-04, H-06, H-07, B1/B2/B4.

## C – Weitere Befunde

- **M-01:** `public_snapshot()` + `"scope": "model"`, `proEnabled` nur mit
  gebundener UUID; Enforcement ausschließlich `pro_enabled_for`.
- **M-03:** Auth-Fehler tragen `X-Request-ID` (`openai_routes.py`);
  `LOCAL_ADMIN_HOSTS` einmalig in `admin.py`, `logs.py` importiert;
  Token-Sweep ab 1024 Einträgen in `validate()`; Lifespan-`stop()`-Fehler
  werden geloggt statt Startup-Fehler zu maskieren. Alias-500 geprüft:
  Betreiber-Fehlkonfiguration → 500 korrekt, keine Änderung.
- Keine allgemeinen Refactorings; keine Serverdatei-Zerlegung über Bedarf.

## D – Tests

- Neu `tests/unit/test_kroko_license_lifecycle.py` (23 Tests): Wahrheitstabelle
  über echte Kette Gate→State→Service→Manager (Fakes nur für Transport/Uhr/
  Dateien), Header-UUID-Mapping, Force-Registry, Service-Verdrahtung,
  Lifespan-Maskierung, Pruning/Host-Dedup.
- Neu `tests/unit/test_kroko_live_license.py` (R1–R4, Opt-in
  `VOICESTT_KROKO_LIVE_TESTS=1`, Key nur zur Laufzeit aus Secret-Datei,
  minimale Verbindungszahl, redigierte Evidenz).
