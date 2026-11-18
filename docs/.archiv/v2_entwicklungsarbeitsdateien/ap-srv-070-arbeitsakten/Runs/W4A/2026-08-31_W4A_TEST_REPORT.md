# AP-SRV-070 — W4A — Test Report

**Datum:** 2026-08-31

---

## 1. Neue W4A-Tests

| Datei | Tests | Fokus |
|---|---|---|
| `tests/unit/test_kroko_fingerprint.py` | 25 | Fingerprint-Stabilität, vollständige Abdeckung buildwirksamer Inputs + Gegenbeweis, Upstream-Pin, Guard über beide deklarierten Revisionen |
| `tests/unit/test_kroko_artifact_store.py` | 30 | Wheel-Introspektion, Store/Reuse, Free-/Pro-Trennung, Integritätsablehnungen, atomarer Ersatz, Reuse-/Force-Flow, Secret-Leakage |
| `tests/unit/test_kroko_model_authority.py` | 29 | Manifest, Lizenzgrenze, Hash-/Größen-/Variantenprüfung, Download-Policy, Modell-Lokalisierung |

**Summe neu: 84 Tests.**

Geändert: `tests/unit/test_kroko_onnx_engine.py` von 27 auf 29 Tests
(siehe §3 — Vertragsänderung beim Modell-Download).

Alle Kroko-Suiten zusammen (inkl. der bestehenden
`test_kroko_onnx_engine.py` und `test_install_kroko_cpu.py`):

```
113 passed, 1 skipped, 45 subtests passed
```

## 2. Abdeckung der W4A-09-Anforderungen (1–18)

| # | Anforderung | Nachweis |
|---|---|---|
| 1 | Fingerprint bei identischen Inputs stabil | `FingerprintStabilityTests` (3 Tests, inkl. Key-Order-Unabhängigkeit) |
| 2 | Normale VoiceSTT-Datei ändert Fingerprint NICHT | `test_computing_a_fingerprint_reads_no_source_file` (patcht `builtins.open`, erwartet **null** Dateizugriffe) + `test_ordinary_voicestt_changes_leave_the_fingerprint_identical` |
| 3 | Produktversion allein ändert Fingerprint NICHT | `test_product_version_is_not_part_of_the_fingerprint`; `resolve_version()` liefert nachweislich den Override, Fingerprint bleibt gleich |
| 4 | Kroko-Upstream-Revision ändert Fingerprint | `test_upstream_revision_changes_the_fingerprint` + Fall 1/2 der Abdeckungsmatrix |
| 5 | Free/Pro ändert Fingerprint **und** Namespace | `test_variant_changes_the_fingerprint`, `test_free_and_pro_use_separate_namespaces` |
| 6 | Python-ABI/Plattform/Architektur ändern Fingerprint | drei eigene Tests + Fälle 4–7 der Abdeckungsmatrix |
| 7 | Erster Free-Build erzeugt verifiziertes Artifact | `test_storing_a_wheel_produces_a_verified_artifact`, `test_first_build_compiles_and_stores` |
| 8 | Zweiter identischer Free-Lauf kompiliert nicht erneut | `test_second_identical_run_does_not_compile_again` (Builder-Aufrufzähler bleibt `["free"]`) |
| 9 | Free-Artifact nach zwischenzeitlichem Pro-Lauf wiederverwendbar | `test_free_artifact_is_reused_after_an_intervening_pro_build` |
| 10 | Pro und Free nicht verwechselbar | `VariantConfusionTests` (3), `VariantCompatibilityTests` (4), plus reale Negativprobe an der installierten Runtime |
| 11 | Force-Rebuild ruft Builder real erneut auf | `test_force_rebuild_really_invokes_the_builder` (Zähler `["free","free"]`) |
| 12 | Fehlgeschlagener Force-Rebuild zerstört kein gutes Artifact | `test_failed_force_rebuild_keeps_the_existing_artifact`, `test_failed_store_keeps_the_previous_good_artifact` |
| 13 | Falsches/korruptes Artifact wird abgelehnt | `IntegrityRejectionTests` (6) + `test_corrupt_archive_is_reported_not_guessed` |
| 14 | SHA/Metadaten/ABI-Tags werden geprüft | `test_incompatible_abi_tag_is_rejected`, `test_tampered_wheel_bytes_are_rejected`, `test_mismatched_stored_inputs_are_rejected` |
| 15 | Modellmanifest erkennt Hash-/Variant-Mismatch | `IntegrityVerificationTests` (5), `VariantCompatibilityTests` (4) |
| 16 | Offline-Modus startet keinen versteckten Download | `DownloadPolicyTests` (4) + `test_no_model_download_happens_without_an_explicit_opt_in` (Engine-Ebene, `_download_file` darf nicht aufgerufen werden) |
| 17 | Kein Secret in Artifact/Metadaten/Logs/Evidence | `SecretLeakageTests` (3) + operativer Scan |
| 18 | `git diff --check` sauber | Exit 0 |

## 3. Vertragsänderung: zwei bestehende Tests angepasst

`test_auto_downloads_public_model_under_download_root` und
`test_bare_default_model_downloads_to_voicestt_cache` pinnten das alte
Verhalten fest, dass ein Serverstart Modelle **selbsttätig** herunterlädt.
Genau das verbietet W4A-08 („kein spontaner Modell-Download beim normalen
Serverstart"), also musste dieser Vertrag sich ändern.

Beide Tests wurden auf den expliziten Opt-in-Pfad umgestellt und entsprechend
umbenannt (`test_explicitly_enabled_…`); die Download-Mechanik selbst bleibt
damit vollständig abgedeckt. Zusätzlich wurden zwei neue Tests ergänzt:

- `test_no_model_download_happens_without_an_explicit_opt_in` — ohne Opt-in
  wird `_download_file` **nicht** aufgerufen und es gibt einen klaren Fehler;
- `test_environment_opt_in_allows_a_public_model_download` — mit
  `VOICESTT_KROKO_ALLOW_MODEL_DOWNLOAD=1` funktioniert der Download.

Netto: 27 → 29 Tests in dieser Datei; keine Abdeckung verloren.

## 4. Guard negativ verifiziert (nicht nur „grün gesehen")

Ein Guard, der ausschließlich besteht, beweist nichts. Der Builder-Guard wurde
deshalb in diesem Lauf aktiv gegengeprüft:

1. Simulierte buildwirksame Änderung in `linux_build_env` (zusätzliche
   `SHERPA_ONNX_EXTRA`-Env-Variable).
2. `test_builder_surface_matches_its_declared_revision` schlug erwartungsgemäß
   fehl: `1d379e05…` ≠ `cdb72891…`, mit der Handlungsanweisung
   „bump `BUILDER_REVISION` … and update `EXPECTED_BUILDER_SOURCE_DIGEST`".
3. Änderung zurückgenommen → Guard wieder grün (4 passed).

Dieselbe Mechanik schützt `PATCH_SET_REVISION`.

## 5. Ein während dieses Laufs gefundener und behobener Fehler

`test_corrupt_archive_is_reported_not_guessed` schlug zunächst fehl: bei einem
unlesbaren Archiv fiel `variant_of_wheel()` auf den **Dateinamen** zurück und
hätte ein korruptes `…-1free-…​.whl` als Free-Variante ausgewiesen. Ein
Dateiname ist trivial fälschbar und darf den tatsächlichen Archivinhalt nie
überstimmen. Korrigiert: ein unlesbares Archiv liefert jetzt `None`
(= Variante unbewiesen) und wird damit abgelehnt.

## 6. Regression

| Lauf | Ergebnis |
|---|---|
| W3-Baseline (vor W4A) | `1266 passed, 14 skipped, 860 subtests` |
| W4A, vor Erweiterung des Guards | `1348 passed, 14 skipped, 888 subtests` in 787 s — 0 Fehlschläge |
| W4A final, Lauf 1 | `1352 passed, 1 failed, 14 skipped, 900 subtests` — **ein transienter `MemoryError`**, siehe §6.1 |
| W4A final, Lauf 2 | abgebrochen (Sitzungsende, ~50 % Fortschritt, keine Summary) — **nicht** als Ergebnis gewertet |
| **W4A final, Lauf 3 (Gate)** | **`1352 passed, 14 skipped, 901 subtests passed` in 502 s — 0 Fehlschläge** |

Der Gate-Lauf bestätigt die Analyse aus §6.1: identische Testanzahl (1352) wie
in Lauf 1, diesmal **ohne** Fehlschlag. Zum Startzeitpunkt standen 9,15 GB
freier Arbeitsspeicher zur Verfügung gegenüber 4,73 GB während des
`MemoryError` — der Unterschied lag am Host, nicht am Code.

Netto gegenüber der W3-Baseline: **+86 Tests** (1266 → 1352), +40 Subtests,
keine neuen Skips.

### 6.1 Untersuchung des transienten `MemoryError` (nicht weggewinkt)

Lauf 1 meldete genau einen Fehlschlag:

```
tests/unit/test_protocol_v2_e2e.py::ProtocolV2SnapshotTests::test_snapshot_reports_suppression_combinations
  SUBFAILED(manual=False, wakeWord=True)
  VoiceSTT\core\wakeword_catalog.py:163: MemoryError
```

Der Fehler wurde untersucht, statt als Flake abgetan:

1. **Fundstelle:** `_sha256_of()` in `VoiceSTT/core/wakeword_catalog.py`, in der
   Zeile `handle.read(1024 * 1024)` — also beim Anfordern von **1 MB**. Ein
   `MemoryError` bei einer 1-MB-Allokation ist kein Logikfehler, sondern
   Speichererschöpfung des Prozesses.
2. **Betroffener Code ist nicht W4A-Scope:** Der Stack läuft ausschließlich über
   den Wake-Word-Katalog (`WakeWordCatalogAuthority.__init__` →
   `with_backend_health` → `probe_backend_health` → `_sha256_of`). W4A hat an
   diesem Pfad keine Zeile geändert.
3. **Historie:** Derselbe Test war in der W3-Baseline und im W4A-Lauf vor der
   Guard-Erweiterung grün (0 Fehlschläge in beiden vollständigen Läufen).
4. **Hostzustand zum Zeitpunkt der Messung:** 29,85 GB RAM gesamt, nur
   **4,73 GB frei**, zusätzlich 3,7 GB in „Memory Compression" — der Host stand
   real unter Speicherdruck (parallel laufende WSL2-/Docker-Desktop-,
   Editor- und Browserprozesse).
5. **Gezielte Nachprüfung:** Die betroffene Datei isoliert neu ausgeführt →
   `68 passed, 16 subtests passed`; der konkrete Test einzeln →
   `1 passed, 3 subtests passed`.
6. **Konsequenz:** Vollständiger Suite-Lauf wiederholt (Lauf 2) und als
   Test-Gate gewertet.

Bewertung: umgebungsbedingter, reproduzierbar nicht wiederkehrender Fehlschlag
ohne Bezug zu den W4A-Änderungen. Er wird hier trotzdem vollständig
dokumentiert, weil ein sichtbarer Fehler nicht unerklärt in einem Evidence-Ordner
stehen darf.

## 7. Hygiene

- `git diff --check` → Exit 0.
- Worktree nach dem Commit sauber (siehe STATE).
- Keine Build-/Test-Artefakte getrackt; die temporäre venv und der
  Scratch-Artifact-Store lagen außerhalb des Worktrees und wurden entfernt
  bzw. verbleiben im Session-Scratchpad.
