# AP-SRV-070 / W4A-C4 — Phase 2: Implementierungsbericht

## 1. Geänderte Dateien

Die Änderungen beschränken sich exakt auf die im Prompt autorisierten Source- und Testdateien:

1. `VoiceSTT/kroko/buildinputs.py`:
   - `PATCH_SET_REVISION`: von `2` auf `3` angehoben.
   - `BUILDER_REVISION`: unverändert auf `4`.
   - Neue source-controlled xwin-Konstanten deklariert:
     - `WINDOWS_XWIN_MANIFEST_URL`, `WINDOWS_XWIN_MANIFEST_CACHE_NAME`, `WINDOWS_XWIN_MANIFEST_BYTES`, `WINDOWS_XWIN_MANIFEST_SHA256`
     - `WINDOWS_XWIN_PACKAGE_MANIFEST_URL`, `WINDOWS_XWIN_PACKAGE_MANIFEST_CACHE_KEY`, `WINDOWS_XWIN_PACKAGE_MANIFEST_CACHE_NAME`, `WINDOWS_XWIN_PACKAGE_MANIFEST_BYTES`, `WINDOWS_XWIN_PACKAGE_MANIFEST_SHA256`
     - `WINDOWS_XWIN_SDK_VERSION`, `WINDOWS_XWIN_CRT_VERSION`
   - `windows_toolchain_declaration()` um die Manifest-, SDK- und CRT-Authority erweitert.
   - Konstanten in `__all__` exportiert.
2. `VoiceSTT/install_kroko.py`:
   - `_pinned_windows_dockerfile_edits()` um den Edit `"xwin manifest authority and splat"` erweitert:
     - Legt `/tmp/.xwin-cache/dl` an.
     - Lädt Channel Manifest herunter, prüft Bytezahl (`91833`) und SHA-256 (`4c81e9...`).
     - Lädt Package Manifest (`.vsman`) herunter, prüft Bytezahl (`17955171`) und den tatsächlichen SHA-256 (`3891c3...`).
     - Ruft `xwin` mit expliziten Parametern `--cache-dir /tmp/.xwin-cache`, `--manifest /tmp/.xwin-cache/dl/manifest_17.json`, `--sdk-version 10.0.26100`, `--crt-version 14.44.17.14`, `--arch x86_64 splat --output /opt/xwin` auf.
     - Beseitigt jeden ungesicherten/floating `latest`-Fallback.
3. `VoiceSTT/kroko/artifacts.py`:
   - `KrokoArtifactStore.lookup()` für Finding N stabilisiert:
     - Gesunder Hit (`record is not None` ohne verbliebene Backups) bleibt vollständig lock-frei (0 Locks genommen).
     - Aufruf mit `recover=False` (innerhalb von `store()`) nimmt keinen rekursiven Lock.
     - Jeder scheinbare MISS sowie der Fall von verbliebenen Backups werden unter `with self._slot_lock(variant, fingerprint):` via `_recover_slot_locked()` und anschließendem `_verify_slot_dir()` stabilisiert.
4. `tests/unit/test_fastapi_server_multi_user.py`:
   - Test-Helper `_inside_retention_timestamp(now)` eingeführt.
   - In `test_admin_replay_reports_retention_gap` das erhalten bleibende Event `retention-transcription-session-b` von der statischen August-2026-Angabe auf `_inside_retention_timestamp(datetime.now(timezone.utc))` umgestellt.
   - Test `test_inside_retention_timestamp_fixture_is_future_proof` ergänzt (prüft Kalenderdaten `2026-09-01` und `2036-09-01`).
5. `tests/unit/test_kroko_artifact_store.py`:
   - `test_healthy_slot_never_takes_the_recovery_lock` erweitert um Assertion `slot_lock.assert_not_called()`.
   - Deterministischen Concurrency-Test `test_concurrent_lookup_during_store_swap_never_returns_miss` ergänzt (belegt alle 11 Phasen des Reader/Writer-Interleavings via Synchronisations-Events).
6. `tests/unit/test_kroko_fingerprint.py`:
   - `EXPECTED_PATCH_SOURCE_DIGEST` auf `'70d8bacbe95c358e532db9ce1b6127d2aa575ff7724b90464a5aec71b7387c80'` für `PATCH_SET_REVISION = 3` aktualisiert.
   - vc_redist-Rolling-URL-Prüfung in `test_generated_windows_build_closes_the_mutable_image_inputs` auf `aka.ms/vs/17/release/vc_redist` präzisiert.
   - Testklasse `RootFindingLMWindowsToolchainAuthorityTests` mit Tests 10.1 bis 10.5 ergänzt.

## 2. Finding L: Konkrete Lösung

In W4A-C3 wählte xwin 0.6.5 die Versionen des Windows SDK und der MSVC CRT implizit aus dem Live-Microsoft-Channel aus. In Phase 2 wurde diese Lücke vollständig geschlossen:
- Das Microsoft Channel Manifest wurde auf die exakte C3-Version gepinnt (`manifest_17.json`, 91833 Bytes, SHA-256 `4c81e902fb7fe2acea779b828e6dc548fe0bbb693df50eda0224263c16686bdd`).
- Das Microsoft Package Manifest (`.vsman`) wurde auf die exakte C3-Version gepinnt (`pkg_manifest_bd98dd01efa4195cb1c11030da63b9e4a3bcec7bc406799a9db80339d6dabd79.vsman`, 17955171 Bytes, tatsächlicher Datei-SHA-256 `3891c3018a07338b3880cbb28088bb22ef7762eb9206523655b2e3972b9d527e`).
- Windows SDK Version wurde fest auf `10.0.26100` gepinnt.
- MSVC CRT Version wurde fest auf `14.44.17.14` gepinnt.
- Alle diese Werte sind Teil von `windows_toolchain_declaration()` und fließen direkt in `inputs.toolchain.authority` und den Kroko-Fingerprint ein.

## 3. Package-Manifest-Sonderfall

Im Channel Manifest ist für das Package Manifest ein Hash im URL-/Cache-Key-Namen (`bd98dd01efa4195cb1c11030da63b9e4a3bcec7bc406799a9db80339d6dabd79`) enthalten, welcher laut xwin-Quellcode nicht dem tatsächlichen Dateiinhalt entspricht (xwin 0.6.5 lädt es intern ausdrücklich mit `checksum=None`).
VoiceSTT verlässt sich daher nicht auf xwin, sondern verifiziert die Datei im Dockerfile explizit vor dem xwin-Aufruf:
- Bytezahl-Prüfung: `test "$(stat -c %s ...)" = "17955171"`
- SHA-256-Prüfung der tatsächlichen Datei: `echo "3891c3018a07338b3880cbb28088bb22ef7762eb9206523655b2e3972b9d527e  ..." | sha256sum -c -`
Erst nach erfolgreicher Verifikation liest xwin das Manifest aus dem Cache.

## 4. Finding M: Dependency Closure

Alle 12 CMake-Dependencies sowie die xwin-Toolchain-Komponenten sind entweder durch `FetchContent_Declare` mit `URL_HASH SHA256=...` im gepinnten Upstream oder durch VoiceSTT-Authority mit Content-Hashes abgesichert. Es verbleiben **0 offene Build-Dependencies**.

## 5. Finding N: Konkrete Lösung (Lookup Race)

Der TOCTOU-Race zwischen Reader (`lookup()`) und Writer (`store()`) wurde ohne Performance-Einbuße behoben:
1. Normaler gesunder Hit: `record is not None and not self.replaced_backups(...)` gibt sofort lock-frei zurück.
2. Miss-Pfad: Sieht der Reader initial keinen gültigen Slot, nimmt er `with self._slot_lock:`. Wurde der Slot gerade von einem Writer geswappt (`final -> backup`), wartet der Reader am Lock, bis der Writer `staging -> final` vollendet und Backups aufgeräumt hat. Danach revalidiert der Reader unter dem Lock und findet den gültigen neuen Slot (HIT statt MISS).
3. Backups: Verbliebene Backups neben einem validen Slot werden unter dem Lock sicher bereinigt.

## 6. Retention-Testkorrektur

In `tests/unit/test_fastapi_server_multi_user.py` wurde der Event-Timestamp für `session-b` von der statischen Angabe `"2026-08-02T00:00:00.000Z"` auf die relative Hilfsfunktion `_inside_retention_timestamp(datetime.now(timezone.utc))` (genau 1 Tag vor Testzeitpunkt) umgestellt. Damit bleibt das Event an jedem Kalenderdatum stabil innerhalb des 30-Tage-Fensters, ohne Produktcode zu verändern.

## 7. Revisionen und Guard-Surface

- `PATCH_SET_REVISION`:
  - Vorher: `2`
  - Nachher: `3`
- `BUILDER_REVISION`:
  - Vorher: `4`
  - Nachher: `4` (unverändert, da die Builder-Infrastruktur / Source-Authority aus C3 nicht verändert wurde)
- Guard-Surface:
  - `EXPECTED_PATCH_SOURCE_DIGEST`:
    - Vorher: `17cbc1dd927d74fc10477579a9475920d0ebfa7df8ddb777d92344aa07e183b5`
    - Nachher: `70d8bacbe95c358e532db9ce1b6127d2aa575ff7724b90464a5aec71b7387c80`
  - `EXPECTED_BUILDER_SOURCE_DIGEST`:
    - Vorher: `4df7ea655259e01e9e1443212d427c9f82c9b98738a0ce0853402923e502b705`
    - Nachher: `4df7ea655259e01e9e1443212d427c9f82c9b98738a0ce0853402923e502b705` (unverändert)

## 8. Verbotene Aktionen eingehalten

- Kein nativer Kroko-Build gestartet.
- Kein Docker-Build gestartet.
- Kein Download gegen das Netz ausgeführt.
- Keine Full Regression gestartet.
- Keine Artifact-Requalification gestartet.
- Kein Commit erstellt.
- Kein Push durchgeführt.
