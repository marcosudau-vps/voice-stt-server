# AP-SRV-070 / W5-R01 - Gate Index

Status: PASS / FAIL / BLOCKED / N/A (mit Begruendung).

## Context / governance

| Gate | Status | Kurzbeweis | Evidence | Command/Test | Result |
|---|---|---|---|---|---|
| W5P-G01 | PASS | `origin/feat/einheitliche-triggerarchitektur-distributed` = `e5f76bf1e4fd28e68624f30140fcf8ec6876db96`, Tree `f3eb03728dd1d0a4d57855a6154430b7142c8995`, exakt wie im Prompt gefordert | `Evidence/00_Preflight/01_remote_fetch_verify.txt` | `git fetch origin`; `git rev-parse origin/...` (+`^{tree}`) | Exit 0, exakte Uebereinstimmung |
| W5P-G02 | PASS | Dedizierter Worktree frisch angelegt (`work/ap-srv-070-w5-r01`), HEAD/Tree = Start-Commit/-Tree, `git status` sauber vor Implementierungsbeginn | `Evidence/00_Preflight/02_worktree_identity.txt`, `03_tool_versions.txt` | `git worktree add -b work/ap-srv-070-w5-r01 <pfad> e5f76bf1...` | Exit 0 |
| W5P-G03 | **FAIL** | Plan-Datei wurde inhaltlich vollstaendig, aber nicht vor dem ersten Implementierungsschritt geschrieben (siehe `04_DEVIATIONS.md` AW-01) | `docs/.archiv/einheitliche_triggerarchitektur/AP-SRV-070/2026-09-06_W5_R01_PLAN.md`, `04_DEVIATIONS.md` | Zeitliche Reihenfolge der Implementierung dieses Runs | Prozessverstoss, kein Inhaltsproblem |
| W5P-G04 | PASS | `VERSION` = `2.0.0` unveraendert; kein Schritt in diesem Run schreibt `VERSION` (nur `prepare-next-version --apply`, das in diesem Run nie gegen die echte `VERSION` ausgefuehrt wurde) | `Evidence/03_Version_Release_Notes/01_release_notes_and_version_check.txt` | `cat VERSION`; `python release.py preflight` | `VERSION=2.0.0`, `version_matches_expected: PASS` |
| W5P-G05 | PASS | Kein PyPI-/GHCR-/Docker-Hub-Publish, kein Git-Tag, kein GitHub-Release, kein Push in diesem Run; `release.py publish` gibt nachweislich keinen Subprocess-/Netzwerkaufruf ab | `Evidence/09_Git_Final/`, `tests/unit/test_release_cli.py::PublishNeverPerformsAWriteTests` | `python release.py publish`; `git log`/`git status` vor/nach | Exit 3, keine Netz-/Git-Mutation |

## Release tool

| Gate | Status | Kurzbeweis | Evidence | Command/Test | Result |
|---|---|---|---|---|---|
| W5P-G06 | PASS | `release.py --help` listet alle Subcommands, keine zweite Release-Authority (delegiert vollstaendig an `release_tooling.cli`) | `Evidence/01_Release_Tooling/01_cli_help.txt` | `python release.py --help` | Exit 0 |
| W5P-G07 | PASS | `preflight` operiert auf `VERSION=2.0.0` ohne es zu aendern; `version_matches_expected: PASS` bei unveraendertem `VERSION` | `Evidence/03_Version_Release_Notes/01_release_notes_and_version_check.txt` | `python release.py preflight` | PASS-Check, `VERSION` danach unveraendert |
| W5P-G08 | PASS | `dry-run` meldet die volle geplante Reihenfolge; Funktion nimmt strukturell keinen Runner/Fetcher entgegen (kann nichts ausfuehren); `sideEffectFree: true` | `Evidence/02_Release_State_Safety/01_dry_run_no_side_effects.txt`, `tests/unit/test_release_pipeline.py::DryRunSideEffectFreedomTests` | `python release.py dry-run`; pytest | Exit 0, PASS |
| W5P-G09 | PASS | Feste Reihenfolge als Daten in `PIPELINE_STEPS`, deckungsgleich mit `STATE_ORDER`; `advance()` erlaubt nur `+1` oder Idempotenz | `tests/unit/test_release_pipeline.py::FixedOrderTests`, `tests/unit/test_release_state.py::StateOrderTests` | pytest | PASS |
| W5P-G10 | PASS | `assert_tag_allowed()` wirft `OrderError` fuer jeden Zwischenzustand vor `EXTERNAL_VERIFIED` | `tests/unit/test_release_state.py::TagAndReleaseBarrierTests::test_tag_blocked_before_external_verification` | pytest | PASS |
| W5P-G11 | PASS | `ensure_same_version()` verweigert Fortsetzung unter anderer Version; Resume-Test durchlaeuft jeden Zwischenzustand mit identischer Version | `tests/unit/test_release_state.py::VersionAndIdentityImmutabilityTests`, `PersistenceTests::test_save_then_load_round_trips` | pytest | PASS |
| W5P-G12 | PASS | `check_pypi_release`/`check_registry_image` werfen `ConflictError` bei abweichendem Hash/Digest, geben `MATCH` bei identischem und `ABSENT` bei fehlendem Artefakt zurueck | `tests/unit/test_release_remote_checks.py` | pytest | PASS |
| W5P-G13 | PASS | `ReleaseState` bindet `sourceCommit`, `sourceTree`, `wheel`, `sdist`, `freeImage`, `proImage`; `ensure_same_identity()` verweigert Resume bei jeder Abweichung | `tests/unit/test_release_state.py::VersionAndIdentityImmutabilityTests::test_ensure_same_identity_rejects_a_mismatched_wheel_hash` | pytest | PASS |
| W5P-G14 | PASS | `assert_no_secrets()` in `to_json_dict()`/`validate_rc_manifest()`; Redaction-Modul erkennt bekannte Credential-Formen; Credential-Praesenz nur als Boolean | `tests/unit/test_release_redaction.py`, `tests/unit/test_release_preflight.py::RegistryAndCredentialCheckTests::test_credential_presence_never_leaks_the_value` | pytest | PASS |
| W5P-G15 | PASS | `advance()` ist idempotent bei Wiederholung desselben Ziels; `save_state()`/`load_state()` schreiben atomar (tmp+replace) und liefern bei Korruption `StateError` statt stillem Datenverlust | `tests/unit/test_release_state.py::PersistenceTests` | pytest | PASS |

## GitHub Actions / package

| Gate | Status | Kurzbeweis | Evidence | Command/Test | Result |
|---|---|---|---|---|---|
| W5P-G16 | PASS | `.github/workflows/ci.yml` existiert, YAML valide | `Evidence/04_GitHub_Actions/01_workflow_static_validation.txt` | `python -c "import yaml; ..."` | Exit 0 |
| W5P-G17 | PASS | Matrix `[ubuntu-24.04, windows-latest]`, `PYTHON_VERSION: "3.12"` | `Evidence/04_GitHub_Actions/01_workflow_static_validation.txt` | statische Assertion | PASS |
| W5P-G18 | PASS | `python -m build` + `python -m twine check dist/*` lokal real ausgefuehrt, beide Artefakte PASSED | `Evidence/05_Package_Qualification/01_wheel_sdist_build_and_twine_check.txt` | `python -m build --outdir dist`; `python -m twine check dist/*` | Exit 0, `PASSED`/`PASSED` |
| W5P-G19 | PASS | Isolierte venv installiert `<wheel>[recommended,server]` (nicht `-e`); `VoiceSTT` wird nachweislich aus `site-packages`, nicht aus dem Checkout, aufgeloest | `Evidence/05_Package_Qualification/02_installed_wheel_smoke.txt` | `pip install <wheel>[...]`; Import-Check aus TEMP-Verzeichnis | Exit 0 |
| W5P-G20 | PASS | `pip check` sauber; `resolve_version()` == installierte Metadaten-Version; alle 4 Console-Scripts vorhanden; alle gepr. Assets (warmup audio, Kroko-Manifest, Browserclient, Wake-Word-Assets) vorhanden | `Evidence/05_Package_Qualification/02_installed_wheel_smoke.txt` | s.o. | Exit 0 |
| W5P-G21 | PASS | `python -m pytest -q tests/unit` (voll, inkl. `test_release_*.py`) PASS | `Evidence/07_Tests/01_full_unit_suite.txt` | `python -m pytest -q tests/unit` | siehe Evidence fuer exakte Zahlen |
| W5P-G22 | PASS | Kein `twine upload`/`docker push`/`git push`/`git tag`/`gh release create`/Kroko-Secret-Referenz im Workflow-Text (statischer Negativ-Scan) | `Evidence/04_GitHub_Actions/01_workflow_static_validation.txt` | statischer Text-Scan | keine Treffer |

## RC tooling / metadata

| Gate | Status | Kurzbeweis | Evidence | Command/Test | Result |
|---|---|---|---|---|---|
| W5P-G23 | PASS | `release_tooling.rc_manifest` implementiert (`build_rc_manifest`/`validate_rc_manifest`/`load_rc_manifest`/`write_rc_manifest`), 12 gezielte Tests PASS | `Evidence/06_RC_Harness/01_rc_manifest_tests.txt` | `python -m pytest -q tests/unit/test_release_rc_manifest.py -v` | 12 passed |
| W5P-G24 | PASS | Manifest bindet `candidateId`, `productVersion`, `sourceCommit`/`sourceTree`, `wheel`/`sdist` (+SHA-256), `kroko.free`/`.pro` (+Artefakt-SHA-256), `images.free`/`.pro` (+ImageId), `oci.*`, `qualification.*`, `releaseReadiness`; `assert_no_secrets()` Teil der Validierung | `release_tooling/rc_manifest.py`, `tests/unit/test_release_rc_manifest.py::BuildAndValidateTests::test_validate_rejects_a_secret_shaped_field` | pytest | PASS |
| W5P-G25 | PASS | `RELEASE_NOTES.md` hat einen `## 2.0.0`-Abschnitt (konsolidiertes `Unreleased`-Material, kein erfundenes Datum), plus frischen leeren `## Unreleased` daran anschliessend | `Evidence/03_Version_Release_Notes/01_release_notes_and_version_check.txt` | `grep '^## ' RELEASE_NOTES.md` | `## Unreleased` / `## 2.0.0` vorhanden |
| W5P-G26 | PASS | `build/BUILD.md` dokumentiert `release.py`, RC-Manifest, feste Reihenfolge, spaeten Tag, "kein verschwendeter Versionsstand", GitHub Actions, Windows+Ubuntu-24.04 | `Evidence/03_Version_Release_Notes/02_build_md_doc_update.txt` | `grep` gegen `build/BUILD.md` | alle Begriffe gefunden |
| W5P-G27 | PASS | Soll-/Ist-Vergleich erstellt, jeder Planpunkt einzeln bewertet, AW-01 als materielle Abweichung dokumentiert | `docs/.archiv/einheitliche_triggerarchitektur/AP-SRV-070/2026-09-06_W5_R01_UMSETZUNGSVERGLEICH.md`, `04_DEVIATIONS.md` | Dokumentenpruefung | vollstaendig |

## Validation

| Gate | Status | Kurzbeweis | Evidence | Command/Test | Result |
|---|---|---|---|---|---|
| W5P-G28 | PASS | Alle gezielten Release-Tool-Tests PASS (91 Tests + 11 subTests, 7 Dateien) | `Evidence/01_Release_Tooling/02_targeted_unit_tests.txt` | `python -m pytest -q tests/unit/test_release_*.py` | 91 passed, 11 subtests passed |
| W5P-G29 | PASS | `python -m build` + `python -m twine check` lokal PASS in echter, isolierter venv (`.venv-install-smoke`) | `Evidence/05_Package_Qualification/01_...txt` | s.o. | PASSED/PASSED |
| W5P-G30 | PASS | Installierter Wheel-Smoke (pip check, Import/Version, Console-Scripts, Assets) PASS ohne Editable-/Source-Rettungsanker, ausgefuehrt aus einem Nicht-Checkout-Verzeichnis | `Evidence/05_Package_Qualification/02_...txt` | s.o. | PASS |
| W5P-G31 | PASS | Voller `python -m pytest -q tests/unit` PASS (Umgebungs-Hinweis zu Sandbox-`TEMP` siehe `04_DEVIATIONS.md`) | `Evidence/07_Tests/01_full_unit_suite.txt` | `python -m pytest -q tests/unit` | siehe Evidence |
| W5P-G32 | PASS | `git diff --check` ohne Whitespace-Fehler | `Evidence/09_Git_Final/` | `git diff --check` | Exit 0 |
| W5P-G33 | PASS | Finale Diff-Review: keine Scope-Ausweitung, keine privaten VPS-/Selfhost-Angaben, keine Publikations-Nebenwirkung; nur die im Plan genannten Bereiche geaendert | `Evidence/09_Git_Final/` | `git status`/`git diff --stat` gegen Plan "Betroffene Bereiche" | keine Abweichung |
| W5P-G34 | PASS | Genau ein finaler lokaler W5-R01-Commit, sauberer Workspace, kein Push | `Evidence/09_Git_Final/` | `git log -1`; `git status`; `git push` NICHT ausgefuehrt | siehe Evidence |

## Zusammenfassung

- PASS: 33
- FAIL: 1 (W5P-G03 - Prozessreihenfolge, siehe `04_DEVIATIONS.md` AW-01)
- BLOCKED: 0
- N/A: 0
