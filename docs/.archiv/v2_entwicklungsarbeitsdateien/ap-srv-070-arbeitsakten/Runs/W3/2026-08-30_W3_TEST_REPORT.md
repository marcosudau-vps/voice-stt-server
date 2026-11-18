# AP-SRV-070 — W3 — Test Report

**Datum:** 2026-08-30

---

## 1. Neue W3-Tests

| Datei | Tests | Fokus |
|---|---|---|
| `tests/unit/test_version_authority.py` | 31 | SemVer-Validierung, Bump-Semantik (`patch`/`minor`/`major` inkl. Reset-Regeln), `resolve_bump_kind`-Exklusivität, `VERSION`-Datei, Override-Auflösung inkl. ungültigem Override, Setup/Package/Runtime/Handshake-Konsistenz, keine zweite hartkodierte Version in `identity.py`/`setup.py`, FastAPI-App-Version |
| `tests/unit/test_wakeword_package_resources.py` | 8 | Manifest-abgeleitete Dateiliste, Ausschluss der 6 historischen Varianten, fehlende Datei löst `FileNotFoundError` aus |
| `tests/unit/test_wakeword_asset_integrity.py` | 6 (54 Subtests) | 25 Dual-Backend-Paare + 4 Pipeline-Assets + VAD-Asset Hash/Byte-genau gegen `models.json`, kein netzwerkfähiger Import in `wakeword_catalog.py` |

**Summe neu: 45 Tests** (31 + 8 + 6), davon 54 zusätzliche Subtests —
deckt sich exakt mit der Differenz der vollständigen Suite (§3).

Alle 45 einzeln und in Kombination grün:

```
tests/unit/test_version_authority.py (31 passed)
tests/unit/test_wakeword_package_resources.py (8 passed)
tests/unit/test_wakeword_asset_integrity.py (6 passed, 54 subtests passed)
```

## 2. Regression — vor W3 (Baseline)

Vollständige Suite (`pytest`, `testpaths = tests/unit`), unmittelbar nach
Abschluss der Implementierung, vor jeder W3-Änderung, als Referenz:

```
1221 passed, 14 skipped, 778 subtests passed in 670.65s (0:11:10)
```

## 3. Regression — nach W3 (vollständige Suite)

```
1266 passed, 14 skipped, 860 subtests passed in 585.97s (0:09:45)
```

- **+45 Tests** (`1266 - 1221`), **+82 Subtests** (`860 - 778`) — exakt die
  drei neuen W3-Testdateien (31 + 8 + 6 = 45 Top-Level-Tests).
- **0 neue Fehlschläge, 0 neue Skips.** `14 skipped` unverändert zur Baseline.
- Kein bestehender Test musste wegen der Versions-/Packaging-Änderungen
  angepasst werden — `identity.server_version()` blieb für alle
  Konsumenten API-kompatibel (gleiche Signatur, gleicher Rückgabewert für
  den unveränderten Baseline-Fall).

## 4. Gezielte Suiten (vor der vollständigen Regression, zur schnellen Rückkopplung)

| Suite | Ergebnis |
|---|---|
| `test_protocol_v2_contract.py`, `test_protocol_v2_e2e.py`, `test_protocol_v1_v2_boundary.py`, `test_sync_wakeword_assets.py` | 169 passed, 1 skipped, 72 subtests passed |
| `test_server_operations.py` | 25 passed |

(Ein einzelner `PermissionError` beim ersten Lauf von
`test_server_operations.py` war eine Windows-Temp-Verzeichnis-Berechtigung
außerhalb des Testcodes, nicht durch W3 verursacht — mit `--basetemp` auf
ein beschreibbares Scratch-Verzeichnis reproduzierte sich der W2-C2-Referenzwert
„25 passed" exakt.)

## 5. `git diff --check`

```
git diff --check
```
→ Exit 0, keine Whitespace-Fehler.

## 6. Worktree nach Tests

`git status --porcelain` zeigt ausschließlich das beabsichtigte
W3-Änderungsset (siehe STATE-Dokument); keine Test- oder Build-Artefakte
(`dist/`, `build/lib`, `*.egg-info`, `.pytest_cache`) sind getrackt oder
ungewollt gestaged.

## 7. Nicht Teil der schnellen Suite

Die eigentlichen Build-/Install-Smoke-Schritte (Wheel-/Sdist-Bau,
`twine check`, Installed-Artifact-Smoke) sind **keine** `pytest`-Tests in
`tests/unit/` — sie folgen der bestehenden Projektkonvention
(`tests/install_extras_matrix.py` ist aus demselben Grund ebenfalls nicht
in `tests/unit/`): sie sind langsam, brauchen eine echte Distribution und
sind kein Teil der schnellen Abnahme-Suite. Ihre Ergebnisse stehen im
Packaging- bzw. Installed-Artifact-Report; die zugehörigen Skripte liegen
unter `Runs/W3/evidence_artifacts/`.
