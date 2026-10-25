# PR #15 – Testevidenz (25.10.2026, Stand: Zwischenbericht)

Commit-SHA (final): `3dad5ba4dbe5dc057f720771bcaa121a8e87f09b` (Ausgangs-HEAD vor Akte: `e65c33ce1bdff16a8327fda86954e81bb1d9a275`).
Umgebung: Windows, CPython im Projekt-venv, `pytest`, keine echten Kroko-Netzverbindungen,
keine Pro-Modellaktivierung. Optionale Golden-/Perf-Tests ohne Env-Opt-in → Skip = NOT_RUN.

## 1. Pflichtbefehle (Auftrag §9)

| Befehl | Ergebnis |
| --- | --- |
| `python -m pytest -q tests/unit/test_openai_compatible_endpoint.py tests/unit/test_server_security_modularization.py tests/unit/test_kroko_selective_improvements.py tests/unit/test_kroko_artifact_store.py tests/unit/test_kroko_onnx_engine.py tests/unit/test_realtime_streaming_transcription.py tests/unit/test_fastapi_server_multi_user_asr_integration.py` | **180 passed, 3 skipped, 8 subtests passed** in 98 s |
| `python -m pytest -q tests/unit` | **2260 passed, 15 skipped, 1330 subtests passed** in 862 s (Hintergrundlauf mit Dateiprotokoll; nur DeprecationWarning aus `websockets.legacy`, kein Fehler) |
| `python -m compileall -q api_fastapi_server VoiceSTT/kroko` | Erfolgreich (Exit True, keine Fehlerausgabe) |
| `git diff --check` | Erfolgreich (keine Whitespace-Fehler) |

## 2. Zusätzliche Regression (Log/Event/WS/Security)

`tests/unit/test_fastapi_server_protocol.py + test_fastapi_server_multi_user.py + test_server_operations.py + test_browser_client_contract.py`:
**125 passed, 24 subtests passed** in 80 s. Deckt HTTP-/WS-Logberechtigungen,
Kanal-/Filter-/Replay-/Cursor-Regeln, Protokollgrenzen und Browser-Client-Vertrag ab.

## 3. Positiv-/Negativfälle (Auszug)

- OpenAI: `/v1/models` enthält `whisper-1`; alle 6 Antwortformate je 200; SSE delta→done;
  Override nur bei `model=whisper-1` sonst 400; unbekannt 404; nicht geladen 409; Bearer 401→200.
- Security: Admin-Präzedenz + 401/WWW-Authenticate + lokal-only ohne Key + remote 403 + Env-live;
  OpenAI optional/strikt + Audit; Logtoken 24h/Expiry-Boundary/Sessionbindung/HTTP-vs-WS;
  Kroko kein Auto-Check, fremdes Modell/stale → CHECK_FAILED, force_community ohne Netz.
- Kroko: Env-Priorität (4 Vars), `""`-Suppress, Engine-Parität bis Recognizer-kwargs;
  Lizenz gültig/TTL-Cap 60, 7× fail-closed, kein Secret-Leak, `close()` in finally;
  Status Rotation/Stale/Modellbindung/TTL; Fallback deterministisch, kein Laden/kein Settings-Eingriff.
- Lifespan/Race: `stop()` nach Startup-Fehler (Mock-Test); Race-Test mit `r1_returned`-Garantie,
  Dreifach-Guard, kein falsch-grün durch Modellfehler.

## 4. Race-Wiederholungen (§8, ≥30 gefordert)

`RealtimeWorkerOverlapRaceTests::test_blocked_r1_inference_released_after_r2_start`,
30 sequenzielle Einzelläufe (pytest-repeat nicht installiert, daher Schleife):
**30/30 passed** (je Lauf 1 passed, 4,4–7,8 s). Der initiale `--count`-Versuch scheiterte
erwartbar an fehlendem Plugin und zählt nicht als Testfehlschlag.

## 5. CI-Links (unveränderlich)

- Ausgangs-CI auf `e65c33c`: https://github.com/marcosudau-vps/voice-stt-server/actions/runs/40180053129 (success, pull_request).
- Finale CI auf finalem Commit: nach Push abwarten, Ubuntu+Windows verifizieren, Links nachtragen.
  Ausstehend/abgebrochen zählt nicht als Erfolg.

## 6. Fehlschläge/Korrekturen

Keine echten Testfehlschläge während dieser Abnahmevorbereitung.
`--count`-Flag im Race-Loop war nicht verfügbar (pytest-repeat fehlt) → auf 30× Einzelläufe umgestellt.
Volle Suite überschritt 120-s-Tool-Timeout → Hintergrundlauf mit Dateiprotokoll.
