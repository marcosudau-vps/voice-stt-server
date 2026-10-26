# PR #15 – Ausgangslage und Plan (25.10.2026)

## 1. Ausgangsstand (verifiziert)

- Repository: `marcosudau-vps/voice-stt-server`
- Arbeitsbranch: `work/kroko-v2-selective-improvements-20261025`
- Zielbranch: `feat/v2-unified-kroko`
- Ausgangs-HEAD: `e65c33ce1bdff16a8327fda86954e81bb1d9a275`
  (`test: verify extracted OpenAI routes through real HTTP dispatch, not FastAPI router internals`)
- PR-Status: OPEN, Draft, base `feat/v2-unified-kroko`, head `e65c33c` — verifiziert via `gh pr view 15`.
- Ausgangs-CI: Run `40180053129` (pull_request, Branch) — `completed/success` am 25.10.2026.
- Working Tree: zu Beginn verschmutzt durch `install_windows_cpu.ps1`-Änderung aus `main`-Kontext;
  per `git restore` bereinigt → `nothing to commit, working tree clean` auf Arbeitsbranch.
- Fremde Commits: keine angetastet; kein Merge/Rebase/Force-Push.

## 2. PR-Diff gegen Zielbranch (Kurzfassung)

26 Dateien, +2008/−715. Inhalt:
- Neu: `api_fastapi_server/openai_routes.py` (615 Zeilen, reiner HTTP/SSE-Adapter),
  `api_fastapi_server/security/` (6 Dateien), `VoiceSTT/kroko/{credentials,license_api,license_state,models}.py`,
  Roadmap `docs/architecture/server-modularization-roadmap.md`,
  Archiv-Plan/Vergleich beider Aktionen, Tests
  `test_kroko_selective_improvements.py` (198), `test_server_security_modularization.py` (194).
- Reduziert: `api_fastapi_server/server.py` (−722, Kompositionswurzel + Delegation).
- Angepasst: `kroko_onnx_engine.py` (+10/−, nutzt zentralen Key-Resolver),
  `test_kroko_artifact_store.py` (+35/−), `test_realtime_streaming_transcription.py` (+27/−),
  Fachdocs `configuration.md`, `kroko-onnx.md`, `testing.md`, Archivregister (+2).

## 3. Dokumentationslage zu Beginn

Gelesen: AGENTS.md, Archiv-README, beide 25.10.2026-Pläne und Umsetzungsvergleiche,
Roadmap, configuration.md, kroko-onnx.md, testing.md, build/BUILD.md, vollständiger PR-Diff.
Historische „CI ausstehend"-Vermerke bleiben unverändert; neue Evidenz kommt nur in diese Akte.
Bekannter Fehler: Archiv-README ordnet „Selektive Kroko-V2-Verbesserungen" PR #14 zu —
Korrektur auf Implementierungs-PR #15 / Referenz-PR #14 ist beauftragt.

## 4. Feste Prüfschritte

1. Akte anlegen, Aktion in `docs/.archiv/README.md` registrieren (Status „Prüfung offen").
2. Prüfaufträge A (OpenAI), B (Security), C (Kroko), D (Lifespan/Race) anhand Code + Tests verifizieren.
3. Pflicht-Testbefehle ausführen (7 Dateien, volle Suite, compileall, diff-check),
   zusätzlich Log-/Event-/WS-/Security-Regressionen; Race-Test ≥30 Wiederholungen.
4. Dokumentationsabgleich mit genau einer beauftragten Korrektur + Konsistenzprüfung.
5. Nur bei konkretem reproduzierbarem Invariantenbruch minimal fixen (Befund→Test→Fix→Re-Run);
   sonst keine Codeänderung.
6. Traceability-Matrix mit allen 20 IDs belegen.
7. Committen/pushen, finale CI (Ubuntu+Windows) abwarten, PR-Beschreibung ergänzen,
   Abschlusskommentar mit Original-Prompt + Evidenz + Abschlussbericht, Draft belassen.

## 5. Abnahmekriterien (für REVIEW_READY)

Alle Prüfpunkte abgearbeitet; keine kritischen/hohen Befunde offen; Regressionen behoben;
Pflicht- und Regressionstests grün; finale CI auf finalem HEAD unter Windows+Ubuntu grün;
Docs entsprechen PR-Stand; Akte vollständig/verlinkt; keine Scope-Verletzung;
PR zeigt weiter auf `feat/v2-unified-kroko`, bleibt Draft und ungemergt.
Sonst Status BLOCKED.
