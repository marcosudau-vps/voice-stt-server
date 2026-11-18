# AP-SRV-070 — W1B TEST REPORT

**Datum:** 2026-08-29/30
**Teilblock:** W1B — Wake-Word / Loader / Config / Runtime Legacy Cut
**Commit:** `a7a37460a1e0997ea7856b96fb766699612a47cf`
**Umgebung:** Windows 11, CPython 3.12, pytest, gleiche Umgebung wie W1A
**Aufrufmuster:** `python -m pytest -q --basetemp=<isolierte Temp>` (der in
W1A §3 dokumentierte `%LOCALAPPDATA%\Temp\pytest-of-marco`-`PermissionError`
besteht weiterhin unverändert in dieser Umgebung; alle Läufe wurden deshalb
mit explizitem `--basetemp` außerhalb dieses Pfades ausgeführt)

---

## 1. Gezielte Tests (Prompt §6)

| Suite | Ergebnis |
|---|---|
| `test_server_operations.py` (WakeWordRegistry) | 24 passed |
| `test_wakeword.py` (Legacy-Resolver) | 10 passed |
| `test_fastapi_server_protocol.py` | 32 passed, 11 subtests |
| `test_fastapi_server_multi_user.py` | 53 passed, 6 subtests |
| `test_openai_compatible_endpoint.py` | 20 passed |
| `test_wakeword_catalog.py`, `test_wakeword_catalog_api.py`, `test_wakeword_selected_only.py`, `test_wakeword_root_findings_c2.py`, `test_wakeword_root_findings_c3.py`, `test_wakeword_session_e2e.py`, `test_server_command_timer_e2e.py`, `test_audio_recorder_boundaries.py`, `test_audio_recorder_public_api.py` (gemeinsam) | 279 passed, 248 subtests |

Alle explizit in Prompt §6 genannten Suiten (`test_wakeword_catalog*`,
`test_wakeword_root_findings_*`, `test_wakeword_session_e2e`,
`test_server_operations`) sind darin enthalten und grün.

---

## 2. RED-FIRST-Nachweis (Prompt §6)

Prompt §6 verlangt RED-FIRST, wo ein echter Defekt oder alter Vertrag
existiert, und verbietet künstliche RED-Tests für bereits korrektes
Verhalten. Die abgeschaffte Default-Semantik ist der einzige echte
Verhaltensunterschied dieses Laufs; er wurde in fünf Tests bewiesen, deren
Vorgänger-Version auf der W1A-Baseline (Default aktiv) noch grün gewesen
wäre und auf dem W1B-Arbeitsstand ohne die Implementierungsänderung rot
gewesen wäre (die Tests wurden erst nach der Implementierung geschrieben, da
sie exakt die neue, gewünschte Ablehnung beweisen sollen, nicht eine
vorherige Zwischenstufe):

| Test | Beweist |
|---|---|
| `test_wakeword_registry_resolve_without_ids_returns_nothing` | `WakeWordRegistry.resolve_openwakeword(None, …)` liefert `([], [])`, kein Default |
| `test_service_does_not_guess_a_default_wakeword_at_startup` | `VoiceSTTService.__init__` mit `wakeword_backend="openwakeword"` und leeren `wake_words` bleibt ohne Wake Word |
| `test_session_wake_word_true_without_words_or_baseline_is_rejected` | v1-Sessionauflösung ohne Wörter/Baseline wirft `wake_word_default_unavailable` |
| `test_session_wake_word_true_resolves_named_manifest_models` (Fallback-Teil) | unbekanntes Wake Word ohne Server-Fallback wirft jetzt `wake_word_fallback_unavailable` statt still ein Ersatzmodell zu wählen |
| `test_websocket_rejects_wakeword_enabled_without_words_or_baseline` | End-to-End über echten `/ws/transcribe`-Handshake: sichtbare `error`-Nachricht (`where: session_config`, `code: wake_word_default_unavailable`) gefolgt von Close `1008` |

Alle übrigen geänderten/neuen Tests (Katalogauflösung nach ID, Alias,
Groß-/Kleinschreibung, `availableFormats`, explizite Klassifikatordateien,
Fehlerbehandlung bei unbekannter ID) beschreiben Verhalten, das nach der
Migration unmittelbar korrekt sein musste, damit die Suite überhaupt läuft
— dafür wurden keine künstlichen RED-Zwischenstände erzeugt, sondern direkt
gegen den kanonischen Katalog verifiziert.

---

## 3. Vollständige Regression

Gesamte Unit-Suite (`tests/unit`):

```
1200 passed, 14 skipped, 778 subtests passed in 600.99s (0:10:00)
```

Vergleich zur W1A-Baseline (`1195 passed, 14 skipped, 778 subtests, 0
failed`): 5 zusätzliche Tests (netto: 2 neue Registry-Tests, 1 neuer
Ablehnungstest im Protocol-File, 1 neuer End-to-End-Test, minus 1 entfernter
`default_openwakeword`-Test), dieselbe Skip-Zahl, 0 failed. Die Skips sind
dieselben Umgebungs-Skips wie in W1A (nicht installierte optionale
Engine-/Backend-Abhängigkeiten), keine Ausblendung von W1B-Verhalten.

---

## 4. Diff-Hygiene

- `git diff --check` vor dem Commit: kein Fehler (keine Konfliktmarker,
  keine Whitespace-Fehler).
- `VoiceSTT/assets/wakeword_models/models.json` wurde bewusst per präziser
  Textentfernung statt vollständigem JSON-Reserialisieren geändert, nachdem
  ein erster Versuch (`json.load`/`json.dump`-Roundtrip) unbeabsichtigt
  ~18 kompakte `"aliases": ["…"]`-Einzeiler auf mehrzeilige Arrays
  umformatiert hätte. Der erste Versuch wurde verworfen
  (`git checkout --`), die endgültige Änderung ist minimal: 2 Zeilen
  geändert/entfernt für die Beschreibung, ein zusammenhängender Block für
  den `openwakeword_models`-Abschnitt entfernt — `2 insertions(+), 66
  deletions(-)`, keine Format-Nebenwirkungen auf unveränderte Einträge.
- `git status --porcelain` nach dem Commit: leer.

---

## 5. Kalibrierung

Unverändert gegenüber dem Stand vor W1B: **EVIDENCE_BLOCKED / calibration
pending**. W1B hat keine neue reale Wake-Audio-Kalibrierung durchgeführt
und gibt keine synthetische oder indirekte Evidenz als reale Kalibrierung
aus. Die Reachability- und Ladbarkeitsprüfungen in diesem Lauf (echte
ONNX-Probes gegen die gebündelten Klassifikatoren, siehe
`test_websocket_resolves_named_wakeword_and_reports_tuning_fallback` und
`test_wakeword_session_e2e.py`) sind Katalog-/Backend-Nachweise, keine
Erkennungs-/Audio-Kalibrierung.

---

## 6. Nicht ausgeführt (bewusst, gehört nicht in W1B)

- Wheel-/sdist-Build und Isolated-Install-Smoke (W3).
- Docker-Build, Compose-Start und Healthcheck (W4).
- Vollständige Release-Regression als Gate (W5), Release Freeze (W6).

Prompt §8 schließt Packaging-, Docker- und Release-Prüfungen für W1B
ausdrücklich aus.
