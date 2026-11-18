# AP-SRV-070 — W1B-C1 TEST REPORT

**Datum:** 2026-08-30
**Teilblock:** W1B-C1 — Root Correction: Legacy Wake Catalog Backend Health
**Commit:** `0e191a915d46bc4afcd88ab52049bfc075979cc7`
**Umgebung:** Windows 11, CPython 3.12, pytest, gleiche Umgebung wie W1A/W1B
**Aufrufmuster:** `python -m pytest -q --basetemp=<isolierte Temp>`

---

## 1. RED-FIRST-Nachweis

Test: `test_server_operations.py::test_wakeword_registry_listing_honors_the_requested_backend_health`

Dual-Backend-Bundle über `wake_catalog_support.build_authority` (ONNX-Prober
schlägt deterministisch fehl, TFLite-Prober besteht), ein Eintrag
(`hey_jarvis`) mit beiden Backends deklariert.

| Stand | Ergebnis |
|---|---|
| `a7a3746` (vor Korrektur) | **FAIL** — `openwakeword_models("onnx")` liefert den Eintrag mit `availableFormats: ["onnx", "tflite"]`, obwohl die ONNX-Probe fehlschlägt |
| Nach Korrektur | **PASS** |

Beweisumfang (alle im selben Test):

- `openwakeword_models("onnx")` liefert den Eintrag **nicht**.
- `openwakeword_models("tflite")` liefert ihn, mit `availableFormats ==
  ["tflite"]` und `paths` nur für `tflite`.
- `resolve_openwakeword(["hey_jarvis"], "onnx")` meldet ihn als `missing`.
- `resolve_openwakeword(["hey_jarvis"], "tflite")` löst ihn auf.

---

## 2. Gezielte Regressionssuiten (Prompt "Regressionsprüfung")

| Suite | Ergebnis |
|---|---|
| `test_server_operations.py` (inkl. neuem Test) | 25 passed |
| `test_wakeword_catalog.py`, `test_wakeword_catalog_api.py`, `test_wakeword_root_findings_c2.py`, `test_wakeword_root_findings_c3.py`, `test_fastapi_server_protocol.py`, `test_fastapi_server_multi_user.py`, `test_wakeword_session_e2e.py` (gemeinsam) | 291 passed, 233 subtests |

Alle im Prompt namentlich genannten Suiten sind darin enthalten und grün.

---

## 3. Vollständige Regression

```
1201 passed, 14 skipped, 778 subtests passed in 711.06s (0:11:51)
```

Vergleich zur W1B-Baseline (`1200 passed, 14 skipped, 778 subtests, 0
failed`): +1 (der neue RED→GREEN-Test), gleiche Skip-Zahl, 0 failed. Die
Skips sind dieselben Umgebungs-Skips wie in W1A/W1B (nicht installierte
optionale Engine-/Backend-Abhängigkeiten).

---

## 4. Repo-weite Reachability-Suche

`grep -R "openwakeword_catalog\|OpenWakeWordCatalog" **/*.py` nach der
Korrektur: ausschließlich die zwei bereits aus W1B bekannten
Docstring-Erwähnungen des retirierten Namens in `operations.py` und
`wakeword.py` (Erklärung, was migriert wurde), keine Importe. Unverändert
gegenüber dem W1B-Stand.

---

## 5. Diff-Hygiene

- `git diff --check` vor dem Commit: kein Fehler.
- `git status --porcelain` nach dem Commit: leer.
- Diff-Umfang: `3 files changed, 44 insertions(+), 5 deletions(-)` — exakt
  der im Prompt erlaubte Scope (minimale Registry-Korrektur, direkt
  zugehöriger Test, eine Doku-Stelle samt ihrem unmittelbar widersprechenden
  Beispiel).

---

## 6. Kalibrierung

Unverändert: **EVIDENCE_BLOCKED / calibration pending**. Dieser Lauf hat
ausschließlich Katalog-/Backend-Health-Nachweise erbracht (deterministische
Fake-Prober), keine reale Wake-Audio-Kalibrierung.
