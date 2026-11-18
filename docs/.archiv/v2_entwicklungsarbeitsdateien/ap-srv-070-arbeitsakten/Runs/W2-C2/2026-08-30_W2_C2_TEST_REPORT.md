# AP-SRV-070 — W2-C2 — Test Report

**Datum:** 2026-08-30
**Umgebung:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070`
(Branch `work/AP-SRV-070`), Python 3.12.10 (`C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe`)

---

## 1. Neue/erweiterte Unit-Tests für `tools/sync_wakeword_assets.py`

Neue Datei: `tests/unit/test_sync_wakeword_assets.py` (vorher existierte
**keine** dedizierte Testdatei für dieses Werkzeug).

```
python -m pytest tests/unit/test_sync_wakeword_assets.py -v
```

**Ergebnis: 20 passed, 0 failed** (0.94 s)

| Testklasse | Testfälle | Abdeckt |
|---|---|---|
| `BuildManifestDualBackendTests` | 9 | Dual-Backend-Manifestgeneration; fehlendes ONNX/TFLite-Paar → deterministischer `SystemExit` (beide Richtungen); `catalogRevision` als Generator-Konstante, nachweislich unabhängig vom vorher generierten Ziel; keine Legacy-Felder (strukturell, nicht textuell); Sortierung nach kanonischer ID; doppelte kanonische ID nach Normalisierung → Fehler |
| `AuxiliaryVadAssetTests` | 3 | VAD-Asset wird für Sync/Check erfasst; keine neue Manifest-Semantik dadurch; fehlender Upstream-Schlüssel → deterministischer `SystemExit` (kein `KeyError`) |
| `RenderManifestFormattingTests` | 2 | Serialisierungsauthority: Skalar-Arrays einzeilig, Objekt-Arrays weiterhin expandiert |
| `CheckModeTests` | 5 | `--check` gegen leeres Ziel → Exit 1; `--check` schreibt nichts; Sync→Check-Rundlauf → Exit 0; `--check` erkennt manipuliertes Artefakt; `--check` erkennt fehlendes Artefakt |
| `RealCommittedBundleIntegrationTest` | 1 | `--check` gegen den echten committeten Bundle-Stand mit der echten `--source`-Autorität (`S:/MODELS/...`) — **nicht** geskippt in dieser Umgebung, lief real und bestand |

### 1.1 Von RED nach GREEN — der zentrale Regressionsfall

`test_missing_tflite_pair_is_a_deterministic_error_not_a_degrade` und die
Spiegelfassung für ONNX bilden exakt das im Prompt geforderte Verhalten ab
("Wenn der Upstream für einen als Dual-Backend erwarteten öffentlichen
Eintrag nur ein Format liefert: nicht still degradieren; klarer
Generator-/Sync-Fehler."). Vor der Korrektur hätte der alte
Single-Backend-Generator diesen Fall stillschweigend ignoriert (er kannte
`tflite_models` gar nicht); jetzt erzwingt `build_manifest()` einen
`SystemExit` mit der betroffenen ID und dem fehlenden Backend im Text.

Ein Zwischenschritt deckte während der Testentwicklung einen echten Bug in
der ersten Implementierung der VAD-Fehlerbehandlung auf: ein fehlender
Upstream-Schlüssel für das Auxiliary-Asset führte ursprünglich zu einem
unbehandelten `KeyError` statt zum geforderten deterministischen
`SystemExit`. Der Test
`test_missing_vad_asset_upstream_is_a_deterministic_error` fing das auf;
der Generator wurde entsprechend korrigiert (expliziter
Schlüssel-Existenz-Check vor dem Zugriff).

---

## 2. Relevante Wake-Suiten aus W2-C1 erneut ausgeführt

```
python -m pytest \
  tests/unit/test_sync_wakeword_assets.py \
  tests/unit/test_wake_admission.py \
  tests/unit/test_wake_audio_boundary.py \
  tests/unit/test_wake_detection.py \
  tests/unit/test_wakeword.py \
  tests/unit/test_wakeword_catalog.py \
  tests/unit/test_wakeword_catalog_api.py \
  tests/unit/test_wakeword_recording_path.py \
  tests/unit/test_wakeword_root_findings_c2.py \
  tests/unit/test_wakeword_root_findings_c3.py \
  tests/unit/test_wakeword_selected_only.py \
  tests/unit/test_wakeword_session_e2e.py \
  -q
```

**Ergebnis: 311 passed, 314 subtests passed, 0 failed** (157.00 s)

Alle in W2-C1 dokumentierten Wake-Suiten (`test_wakeword_catalog.py`,
`test_wakeword_catalog_api.py`, `test_wakeword.py`,
`test_wakeword_selected_only.py`, `test_wake_admission.py`,
`test_wake_detection.py`, `test_wake_audio_boundary.py`) sind hier
enthalten, zusätzlich die weiteren im aktuellen Repo vorhandenen
Wake-/Catalog-Suiten (`test_wakeword_recording_path.py`,
`test_wakeword_root_findings_c2.py`, `test_wakeword_root_findings_c3.py`,
`test_wakeword_session_e2e.py`) sowie die neue
`test_sync_wakeword_assets.py`. Keine Regression durch die
Generator-Änderung — erwartbar, da kein Laufzeit-/Domänenmodul verändert
wurde, nur das reine Build-Werkzeug.

---

## 3. `test_server_operations.py`

```
python -m pytest tests/unit/test_server_operations.py -q
```

**Ergebnis: 25 passed** — deckungsgleich mit der in W2-C1 dokumentierten
Baseline ("25 passed, 0 failed").

**Umgebungsbefund (nicht codebedingt):** Ein direkter Lauf ohne
`--basetemp`-Override schlug mit
`PermissionError: [WinError 5] Zugriff verweigert:
'C:\Users\user\AppData\Local\Temp\pytest-of-marco'` in 22 von 25 Fällen
fehl — ein vorbestehendes, durch Windows-ACLs blockiertes Pytest-Basistemp-
Verzeichnis auf dieser Maschine, reproduzierbar auch nach Abschluss aller
anderen Testläufe dieser Sitzung und unabhängig von den hier vorgenommenen
Code-Änderungen (betrifft ausschließlich `tmp_path`-Fixture-Aufräumlogik in
`_pytest.pathlib`, nicht den Testinhalt selbst). Mit einem expliziten
`--basetemp` außerhalb des blockierten Verzeichnisses lief die Suite
sauber durch:

```
python -m pytest tests/unit/test_server_operations.py -q --basetemp=<scratchpad>/pytest_basetemp
```

→ **25 passed**, 0 failed, 0 errors.

---

## 4. `git diff --check`

```
git diff --check              # unstaged, vor Commit
git diff --cached --check     # staged, vor Commit
```

Beide: **Exit 0**, keine Whitespace-/Konfliktmarker-Fehler.

---

## 5. Volle Unit-Suite

Nicht ausgeführt — nicht erforderlich laut Prompt ("Volle Unit-Suite ist
nur dann zwingend, wenn Runtime-/Domänencode verändert werden muss. Das
sollte für diesen Auftrag nicht nötig sein."). Diese Korrektur hat
ausschließlich `tools/sync_wakeword_assets.py` (Build-Werkzeug, kein
Laufzeitcode), eine neue Testdatei und eine Dokumentationszeile geändert.

---

## 6. Zusammenfassung

| Gate | Ergebnis |
|---|---|
| Neue Unit-Tests `test_sync_wakeword_assets.py` | 20 passed |
| Alle relevanten Wake-/Catalog-Suiten (12 Dateien) | 311 passed, 314 subtests passed |
| `test_server_operations.py` | 25 passed (mit `--basetemp`-Workaround für ein umgebungsbedingtes, codeunabhängiges Temp-Verzeichnis-Problem) |
| `git diff --check` (unstaged) | Exit 0 |
| `git diff --cached --check` | Exit 0 |
| `python tools/sync_wakeword_assets.py --source S:/MODELS/openwakeword/resources/models/all_models --check` | **Exit 0** (Hard-Gate erfüllt) |
