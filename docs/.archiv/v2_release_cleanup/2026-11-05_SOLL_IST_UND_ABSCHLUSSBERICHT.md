# Soll/Ist-Prüfung und Abschlussbericht – V2 Pre-Release-Cleanup + V2-Code-Referenz

Datum: 2026-11-05
Repository: `marcosudau-vps/voice-stt-server`
Basis: `feat/einheitliche-triggerarchitektur-distributed` @ `4f30c0fda9da6470333cad996c13865c31e6474e` (beim Start per `git fetch` verifiziert, keine Abweichung zum Auftrag)
Arbeitsbranch: `feat/v2-release-cleanup`
Geprüfter Code-/Doku-Stand erster Lauf: `c2b2d7d`. **Finaler Stand nach dem
Abschlussauftrag (zweiter Lauf): siehe „Teil 2“ am Ende dieser Datei.** Die
Abschnitte 1–6 dokumentieren den ersten Lauf und bleiben als Historie stehen.
Draft-PR: https://github.com/marcosudau-vps/voice-stt-server/pull/18
Review-Status: `REVIEW_READY` (eingereicht). **Kein** `ROOT_PASS`, **keine** Freigabe, **kein** Merge, **keine** Veröffentlichung.

## 1. Soll/Ist je Arbeitspaket

| AP | Soll | Ist | Status |
| --- | --- | --- | --- |
| CLN-000 | Baseline, Cross-References, Risiko, Mapping, Testmatrix, geschützte Doku | `2026-11-04_AP-CLN-000_BASELINE_UND_MATRIX.md`, Blob-Liste `2026-11-04_GESCHUETZTE_DOKUMENTATION_BASELINE.tsv` (259 Dateien) | COMPLETE |
| CLN-010 | Engineering-Konsolidierung unter `engineering/`, nur wo Verträge erhalten bleiben | Alle Kandidaten geprüft; **kein** Move sicher möglich (Begründung je Ordner in `2026-11-05_AP-CLN-010-020_ENTSCHEIDUNGEN.md`). Stattdessen Regressionsnetz `tests/unit/test_engineering_path_contract.py` (14 Tests / 39 Subtests) für Workflow-Skriptpfade, Root-Einstiege, Console-Scripts, Release-Autoritätspfade, Dockerfile-`COPY`, Compose-Kontext, `MANIFEST.in` | PARTIAL – Zielstruktur nicht erreicht, bewusst `NICHT_SICHER`/`NACH_V2` |
| CLN-020 | Beispiele nach `examples/`, Altlasten mit Beleg entfernen | `examples/` ist in `.gitignore` ausgeschlossen; alle `app_*` haben Test-/Packaging-/Doku-Bindungen → `NACH_V2`. Keine getrackten Altlasten gefunden → nichts gelöscht | PARTIAL – geprüft, keine sichere Maßnahme |
| CLN-030 | Alt-Doku unverändert, technische Pfade funktionsfähig | Da nichts verschoben wurde, entstehen **keine** neuen Pfad-/Doku-Divergenzen. Alle 259 geschützten Dateien Blob-identisch (Abschnitt 3) | COMPLETE |
| DOC-V2-100 | Eigenständige, code-abgeleitete V2-Referenz (13 Seiten) | `docs/v2-code-reference/` mit README + 12 Fachseiten, jede mit „Primäre Quellen“; mechanischer Abdeckungstest `tests/unit/test_v2_code_reference.py` | COMPLETE (mit dokumentierten Teil-Lücken, Seite 12) |
| CLN-040 | Regression, Sicherheitsprüfung, Bericht, PR | dieser Bericht, Tests Abschnitt 4, PR #18 | COMPLETE (Restpunkte Abschnitt 6) |

## 2. Alt→Neu-Matrix (final)

Keine Verschiebung durchgeführt. Vollständige Matrix mit Begründung:
`2026-11-05_AP-CLN-010-020_ENTSCHEIDUNGEN.md`.

Hinzugefügte Dateien (`git diff --name-status 4f30c0f..c2b2d7d`, ausschließlich `A`):

- `docs/.archiv/v2_release_cleanup/` – 4 Dateien (+ dieser Bericht)
- `docs/v2-code-reference/` – 13 Dateien
- `tests/unit/test_engineering_path_contract.py`
- `tests/unit/test_v2_code_reference.py`

Laufzeit-/Build-/CI-Dateien geändert: **keine**.

## 3. Nachweis unveränderter Alt-Dokumentation

Befehl (Ergebnis `protected_fail=0 count=259`):

```bash
while IFS=$'\t' read -r blob path; do
  [ "$(git rev-parse "HEAD:$path")" = "$blob" ] || echo "CHANGED $path"
done < docs/.archiv/v2_release_cleanup/2026-11-04_GESCHUETZTE_DOKUMENTATION_BASELINE.tsv
```

Zusätzlich: `git diff --name-status 4f30c0f..HEAD -- '*.md' '*.MD' '*.rst'`
zeigt ausschließlich `A`-Einträge unter `docs/v2-code-reference/` und
`docs/.archiv/v2_release_cleanup/`. `AGENTS.md`,
`docs/.archiv/README.md`, `build/BUILD.md`, `build/vps/*.md` sowie die drei
HTML-Dateien (`VoiceSTT_server/index.html`,
`api_fastapi_server/static/index.html`, `app_browserclient/index.html`) sind
unverändert.

Alt-Dokumentation nachweislich unverändert: **JA**.

## 4. Tests und Prüfungen

Umgebung lokal: Linux, Python 3.12 (venv), CPU-Torch, `portaudio19-dev`,
keine Modelldateien, kein Netzwerkzugriff auf Produktionssysteme.

| Prüfung | Befehl | SHA | Ergebnis |
| --- | --- | --- | --- |
| Gesamtsuite (Basis + Pfadtest) | `python -m pytest -q -p no:cacheprovider tests/unit tests/compatibility` | `0a15520` + Pfadtest | PASS – 2341 passed, 24 skipped, 1362 subtests, 9:31 min |
| Gesamtsuite final | wie oben | `c2b2d7d` | siehe Abschnitt 4a |
| Packaging | `python -m pytest -q -p no:cacheprovider tests/packaging` | `c2b2d7d` | siehe Abschnitt 4a |
| Neue Tests + Doku-Oberfläche | `pytest tests/unit/test_v2_code_reference.py tests/unit/test_docs_surface.py tests/unit/test_engineering_path_contract.py` | `c2b2d7d` | PASS – 53 passed, 121 subtests |
| Server-Smoke ohne Modelle | `voice-stt-server --host 127.0.0.1 --port 8765 --data-root <tmp> --no-model-warmup` | `0a15520` (Code identisch zu `c2b2d7d`) | PASS – `/api/v2/info`, `/health` (`ready:false`), `/api/v2/wake-words`, `/api/v2/settings/server`, `/v1/models` antworten; `PATCH /api/config` von Loopback `200` |
| CLI | `voice-stt-server --help`, `python release.py --help`, `python tools/build_production.py --help` | – | PASS |
| Release-Preflight | `python release.py preflight` | `0a15520` | erwartetes FAIL (Exit 1): `git_clean_tree` (damals unversionierte Testdatei) und `dockerhub_repo_configured` (lokal nicht konfiguriert); keine Schreiboperation. Siehe 4a für den Lauf auf sauberem Baum |
| Release-`dry-run` | – | – | NOT_RUN – Standard-Adapter fragen externe Registries/PyPI lesend ab; ausgelassen gemäß Auftrag (keine externen Calls). Abgedeckt durch `tests/unit/test_release_pipeline.py`/`test_release_engine.py` mit Fake-Adaptern (in der Gesamtsuite PASS) |
| Docker-Build | – | – | NOT_RUN – benötigt vorab gebautes Wheel + Kroko-Artefakt; nur Vertragstests (`test_production_docker_contract.py`, PASS) |
| GitHub-CI Linux | Workflow `CI` | `721c13b` | alle Schritte `success` inkl. Unit-, Packaging-Tests und `git diff --check` (Job am Ende durch Concurrency als `cancelled` markiert) – Run https://github.com/marcosudau-vps/voice-stt-server/actions/runs/41938928706 |
| GitHub-CI final | Workflow `CI` | `c2b2d7d` / Bericht-Commit | siehe Abschnitt 4a |

### 4a. Abschlussläufe (erster Lauf, Stand `c2b2d7d`)

| Prüfung | Ergebnis |
| --- | --- |
| `pytest tests/unit tests/compatibility` | PASS – 2350 passed, 24 skipped, 1402 subtests (9:31 min) |
| `pytest tests/packaging` (erster Versuch) | FAIL – 32 failed: lokale venv ohne Modul `build` (Umgebungsfehler, keine Codeursache) |
| `pytest tests/packaging` (nach `pip install build wheel`) | PASS – 33 passed (5:22 min) |
| `python release.py preflight` (sauberer Baum) | Exit 1 – einziges FAIL `dockerhub_repo_configured` (lokal nicht konfiguriert), übrige Checks PASS/WARN |
| GitHub-CI `e423028` PR-Lauf 41940581684 | Ubuntu und Windows SUCCESS |
| GitHub-CI `e423028` Push-Lauf 41940574543 | Ubuntu FAILURE (`No space left on device` beim Installieren der CUDA-Torch-Abhängigkeiten), Windows SUCCESS – Ursache und Behebung siehe Teil 2 |

## 5. Feature-/Quellenmatrix und Abdeckung

Siehe `docs/v2-code-reference/12_feature_und_quellenmatrix.md` (42 Features,
Status getestet/beobachtet/experimentell/blockiert). Mechanisch geprüft:
alle Routen, alle V2-Kommandotypen/Result-Codes/Ereignistypen, alle 19
V2-Settings-Schlüssel, alle registrierten Engine-Namen. Bewusst nicht
vollständig: Feldlisten einzelner V1-Nachrichten (`status`, `timeline`,
`ready`) und die vollständige Parameterliste von `AudioToTextRecorder`.

Während der Code-Analyse festgestellte, **nicht** behobene Auffälligkeiten
(Behebung wäre Verhaltensänderung, außerhalb des Auftrags):

1. `PUT /api/models/active` mappt `RuntimeError` mit dem Text
   „keine WebSocket-Sitzungen“ auf `409`; dieser Text wird im
   Produktionscode nirgends erzeugt → faktisch immer `500`.
2. Kommentar in `docker-compose.yml` nennt `tools/build_production.py
   <free|pro|all>`; die CLI akzeptiert nur `pro|all`.
3. Mit dem ausgelieferten Manifest ist für keines der 23 bekannten Modelle
   Provisionierung erlaubt; `stt_auto_download_enabled` hat derzeit keine
   installierende Wirkung.

## 6. Offene Punkte

| Punkt | Status | Konsequenz |
| --- | --- | --- |
| Engineering-Konsolidierung `engineering/` | NACH_V2 / NICHT_SICHER | benötigt Freigabe für Workflow- und Alt-Doku-Änderungen |
| `app_*` → `examples/` | NACH_V2 | benötigt `.gitignore`-Anpassung und Doku-Pflege |
| Registereintrag `docs/.archiv/README.md` | bewusst nicht erfolgt | siehe `2026-11-04_AUSNAHME_REGISTER_UND_PROZESS.md` |
| Release-`dry-run`, Docker-Build, Release-Candidate-Workflow | NOT_RUN | keine externen Seiteneffekte erlaubt |
| Windows-CI auf finalem SHA | siehe 4a | – |
| Unabhängige Abnahme / Merge | NICHT ERFOLGT | ausstehend |
| V2-Publikation | NICHT ERFOLGT | zusätzlich blockiert durch `build/kroko-redistribution.json: BLOCKED` |
