# CI-Korrektur Settings – Auftrag 03 (drei Tests in test_protocol_v2_settings.py)

Datum (lokal): 2026-10-25 01:15 +02:00 – entspricht UTC 2026-10-24 23:15
Branch: work/v2-stt-model-management-integration
HEAD vor Fix: b4dcc6023dd54375f8c227ab09d351cdaceb4c50 (== Remote-HEAD, verifiziert)
Referenz-CI: https://github.com/marcosudau-vps/voice-stt-server/actions/runs/40138230679
Schritt: `Run fast unit/guard/packaging/release-tool test suite` (Linux + Windows)

## 1. Ausgangsbefund (alle drei lokal reproduziert, vor Fix)

- `RestSettingsV2Tests::test_schema_is_deterministic_and_complete`: Registry enthaelt
  zusaetzlich `stt.autoDownload.enabled` und `stt.autoDownload.selectedModelIds`
  (AssertionError: Items in the first set but not the second).
- `PersistenceFailureRestTests::test_rest_server_patch_persistence_failure_returns_500_internal_error`: 200 statt 500.
- `PersistenceFailureRestTests::test_rest_persistence_failure_does_not_advance_settings_revision`: Revision 1 statt 0.

## 2. Tatsaechliche Fehlerursache (Aufrufpfad verifiziert)

`PATCH /api/v2/settings/server` (api_fastapi_server/server.py:9172) →
`VoiceSTTService.patch_server_settings` (:7826) →
`ServerSettingsState.patch_server` (settings_control.py:1254) →
`self._persist(next_overlay, next_revision)` (:1363) mit
`_persist = VoiceSTTService._persist_settings_control` (server.py:7795) →
`RuntimeConfigStore.save_server_configuration(settings, allowed_names, overlay, revision)`
(operations.py:471).

Die Tests mockten `service.config_store.save_settings_control` (alte 2-arg-Methode),
die auf diesem Pfad nicht mehr aufgerufen wird – der Mock traf ins Leere, die
Persistenz lief (No-op bei Pfad None) erfolgreich durch. Produktionscode ist korrekt:
`patch_server` baut Next-State als Kopien, persistiert VOR jeder Live-Mutation und
gibt bei Ausnahme `internal_error` ohne Revisions-/RAM-Aenderung zurueck
(settings_control.py:1351-1381); der REST-Layer mappt `internal_error` auf HTTP 500
(server.py:9197-9202). Kein Produktfehler, reiner Testvertragsabgleich.

## 3. Geaenderte Datei (einzige)

- `tests/unit/test_protocol_v2_settings.py` (+52/-7):
  - Schema-Test: exakter Keysatz um genau `stt.autoDownload.enabled` und
    `stt.autoDownload.selectedModelIds` ergaenzt; Sortier- und Vollstaendigkeitsassertion
    erhalten; zusaetzlich Registry-Metadaten fuer beide Keys geprüft
    (scope=server, auth=admin, Typ bool/string_list, Defaults false/[], applyPolicy=live).
  - Beide Persistenztests injizieren `OSError('disk full')` jetzt am tatsaechlich
    verwendeten Einsprung `save_server_configuration(settings, allowed_names, overlay, revision)`.
  - Verstaerkt: Fehlerantwort weiter 500/`internal_error`/`accepted=false`/`persistence_failed`,
    ohne Exception-Details/Secrets; Revision bleibt 0, requested/effective bleiben 3000;
    nach Wiederherstellung fuehrt ein normaler Patch genau auf Revision 1.
- Kein Produktionscode geaendert. Keine Aenderung an protocol_v2/schema.py,
  Kroko-/Native-Dateien, Fingerprints, Downloadberechtigungen, PR #12/#13, Zielbranch.

## 4. Pruefergebnisse (Windows CPython 3.12.10, real ausgefuehrt)

- 3 Zieltests: 3 passed (3.27 s).
- `tests/unit/test_protocol_v2_settings.py` vollstaendig: 41 passed (35.07 s).
- Fokussiert: `test_stt_management_v2.py` + `test_settings_runtime_persistence.py` +
  `test_settings_control_plane.py`: 101 passed (5.77 s).
- `test_stt_lazy_connection.py` ohne den separaten Timeout-Test: 5 passed, 1 deselected.
- `python -m compileall -q api_fastapi_server VoiceSTT_server voice_stt_server`: ok.
- `git diff --check`: sauber.
- Volle `tests/unit`-Suite (ohne test_stt_lazy_connection.py): 2401 passed,
  15 skipped, 1326 subtests passed (736.06 s). Separater Windows-Lazy-Timeout-Test
  bewusst NOT_RUN (eigener Folgeauftrag).
