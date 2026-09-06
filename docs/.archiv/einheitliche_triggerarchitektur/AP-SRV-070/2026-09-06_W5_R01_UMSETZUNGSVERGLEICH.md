# AP-SRV-070 / W5-R01 - Soll-/Ist-Vergleich

Gegenpruefung gegen `2026-09-06_W5_R01_PLAN.md` und den Prompt
`_workflow-tools/AP-SRV-070/Prompts/2026-09-06_AP-SRV-070_W5_R01_SONNET5.md`.
Vollstaendige Evidenz in `_workflow-tools/AP-SRV-070/Runs/W5-R01/`.

## Release-Orchestrator

| Planpunkt | Status | Ist |
|---|---|---|
| Kanonischer `release.py`-Einstiegspunkt, keine zweite Release-Authority | Vollstaendig | `release.py` (duenner Wrapper) + `release_tooling/cli.py`; keine zweite Version-/Image-Namensauthority (Reuse von `VoiceSTT._version`, `tools.build_production.IMAGE_NAMES`) |
| Rein lesender Preflight, aendert `VERSION` nicht | Vollstaendig | `release_tooling/preflight.py`; `python release.py preflight` laesst `VERSION`/Git/Release-State unveraendert (siehe `Evidence/00_Preflight`, `Evidence/02_Release_State_Safety`) |
| Eine Engine fuer Dry-Run und echte Publikation | Vollstaendig | `release_tooling/engine.py:run_engine()` - `dry-run` und `publish` rufen dieselbe Funktion mit demselben Adapter-Bundle auf, nur `ExecutionMode` unterscheidet sich; `publish()` eines Adapters wird strukturell nie im `DRY_RUN`-Modus aufgerufen (`tests/unit/test_release_engine.py::DryRunNeverWritesTests`) |
| Echte, W6-faehige Publikationsadapter | Vollstaendig | `release_tooling/adapters.py`: PyPI (Twine), GHCR/Docker Hub (`docker tag`/`push`), Git-Tag (`git tag`/`push`), GitHub Release (`gh release create`) - kein Adapter liest/speichert je einen Credential-Wert, jedes Werkzeug liest seinen eigenen Umgebungsvertrag; 31 gezielte Tests in `tests/unit/test_release_adapters.py` |
| Nicht-secret-haltiger resumable Release-State | Vollstaendig | `release_tooling/state.py`; `assert_no_secrets()` vor jedem Schreiben; `tests/unit/test_release_state.py` |
| Feste W6-Publikationsreihenfolge erzwungen | Vollstaendig | `release_tooling/engine.py:STEP_DEFINITIONS` (Daten) + `release_tooling/state.py:advance()` (nur `+1` oder Idempotenz erlaubt) |
| Tag-Barriere vor externer Verifikation | Vollstaendig | `state.assert_tag_allowed()`, zusaetzlich defensiv direkt in `GitTagAdapter.publish()`; getestet fuer jeden Zwischenzustand und per direktem Adapteraufruf |
| GitHub-Release-Barriere vor Tag | Vollstaendig | `state.assert_github_release_allowed()`, zusaetzlich defensiv direkt in `GitHubReleaseAdapter.publish()`; getestet |
| Konfliktfaelle schlagen hart fehl | Vollstaendig | Jeder Adapter raist `ConflictError` bei abweichender Remote-Identitaet (PyPI-Datei-Hash, Registry-Digest, Tag-Commit, Release-Tag) - rein lesend, mit injizierten Fakes getestet, kein echter Netzwerkaufruf in Tests |
| Resume nach Teilausfall (PyPI/GHCR/Docker Hub/Tag/Release) | Vollstaendig | `tests/unit/test_release_engine.py::ResumeAfterPartialSuccessTests` deckt jeden der sechs im Korrekturprompt genannten Ausfallpunkte einzeln ab |
| Reconciliation bei verlorenem lokalem State nach erfolgreicher Remote-Operation | Vollstaendig | Derselbe lesende `verify()`-vor-`publish()`-Schritt reconciled automatisch - kein Sonderfallcode noetig; `StaleLocalStateReconciliationTests` |
| Kein verschwendeter Versionsstand nach Teilausfall | Vollstaendig | `state.ensure_same_version()`/`ensure_same_identity()`; State-Datei ist pro Version fixiert, kein automatischer Versionswechsel moeglich |
| `release.py publish` | Vollstaendig implementiert, in diesem Run nie real ausgefuehrt | Fuehrt `engine.run_engine()` im `ExecutionMode.REAL` aus; verlangt `--manifest` und `--yes` sowie einen bestandenen Preflight, bevor auch nur ein Adapter konstruiert wird; W5-R01-C1 belegt die Korrektheit ausschliesslich ueber injizierte Fake-Adapter, nie ueber einen echten Schreibvorgang |
| `prepare-next-version` getrennt von aktuellem Publish-Pfad | Vollstaendig | Ohne `--apply` rein lesend; nur mit `--apply` (nie in diesem Run gegen die echte `VERSION` ausgefuehrt) schreibt es |

## RC-Manifest

| Planpunkt | Status | Ist |
|---|---|---|
| Ein kanonisches RC-Manifest-Format | Vollstaendig | `release_tooling/rc_manifest.py`: `candidateId`, `productVersion`, `sourceCommit`/`sourceTree`, `wheel`/`sdist` (Datei+SHA-256), `kroko.free`/`kroko.pro` (Fingerprint+Artefakt-SHA-256), `images.free`/`images.pro` (Tag+ImageId), `oci.version`/`oci.revision`, `qualification.*`, `releaseReadiness` |
| Keine Secrets im Manifest | Vollstaendig | `assert_no_secrets()` Teil von `validate_rc_manifest()`; getestet |
| Manifest bindet W6 an W5-qualifizierte Identitaeten | Vollstaendig (Format); Befuellung mit echten Kroko-/Image-Identitaeten ist W5-R02 | `build_rc_manifest()`/`load_rc_manifest()`/`write_rc_manifest()`; CLI `release.py manifest build/validate` |

## GitHub Actions CI

| Planpunkt | Status | Ist |
|---|---|---|
| Oeffentlicher CI-Workflow | Vollstaendig | `.github/workflows/ci.yml` |
| Pull Request / Push / `workflow_dispatch`, kein Release-Trigger | Vollstaendig | Statisch verifiziert (`Evidence/04_GitHub_Actions/01_workflow_static_validation.txt`) |
| Windows + Ubuntu 24.04, Python 3.12 | Vollstaendig | Matrix `[ubuntu-24.04, windows-latest]`, `PYTHON_VERSION: "3.12"` |
| Wheel/Sdist-Build, `twine check` | Vollstaendig | Workflow-Schritte; lokal aequivalent ausgefuehrt (`Evidence/05_Package_Qualification/01_...txt`) |
| Installation aus gebautem Wheel, nicht editable | Vollstaendig | Isolierte venv, `pip install <wheel>[recommended,server]`; lokal aequivalent ausgefuehrt und verifiziert, dass `VoiceSTT` aus `site-packages` aufgeloest wird (`Evidence/05_Package_Qualification/02_...txt`) |
| `pip check`, Import/Version, Console-Scripts, Assets | Vollstaendig | Alle vier Pruefungen als eigene CI-Schritte; lokal real ausgefuehrt |
| Unit-/Guard-/Release-Tool-Suite | Vollstaendig | `python -m pytest -q tests/unit` als CI-Schritt; lokal vollstaendig ausgefuehrt (`Evidence/07_Tests/`) |
| Kein Kroko-Pro-Secret, kein nativer Kroko-Build, keine Publikation | Vollstaendig | Statisch verifiziert (keine der verbotenen Aktionen/Secrets im Workflow-Text) |
| Workflow real auf GitHub gruen | Nicht anwendbar in W5-R01 (Prompt-Vorgabe) | Workflow existiert remote erst nach Push/Freigabe; Prompt Abschnitt 10.3 verlangt fuer W5-R01 nur statische Validierung + aequivalente lokale Ausfuehrung - beides erbracht |

## Release Notes / Dokumentation

| Planpunkt | Status | Ist |
|---|---|---|
| Finaler `2.0.0`-Abschnitt in `RELEASE_NOTES.md` | Vollstaendig | `## 2.0.0` konsolidiert das bisherige `Unreleased`-Material (kein Materialverlust); kein erfundenes Datum, da Public-Release-Zeitpunkt erst W6 gehoert |
| Frischer `Unreleased`-Abschnitt erhalten | Vollstaendig | Leerer `## Unreleased` direkt ueber `## 2.0.0` |
| `build/BUILD.md` beschreibt W5/W6-Split, `release.py`, RC-Manifest, feste Reihenfolge, spaeten Tag, CI, Windows+Ubuntu-24.04 | Vollstaendig | Abschnitt "Versions- und Releasepflege" erweitert (siehe `Evidence/03_Version_Release_Notes/02_...txt`) |

## Tests

| Planpunkt | Status | Ist |
|---|---|---|
| Gezielte Release-Tool-Unit-Tests | Vollstaendig | 157 gezielte Tests (plus 11 `subTest`-Faelle) in `tests/unit/test_release_*.py`, alle PASS - inklusive der Engine-/Adapter-Suiten aus der W5-R01-C1-Korrektur (Resume-, Reconciliation-, Konflikt- und Secret-Redaction-Szenarien) |
| Volle Suite `python -m pytest -q tests/unit` | Vollstaendig | Siehe `Evidence/07_Tests/` fuer exakte Zahlen |
| `git diff --check` | Vollstaendig | Siehe `Evidence/09_Git_Final/` |

## Archivprozess

| Planpunkt | Status | Ist |
|---|---|---|
| Plan vor Implementierung angelegt | **Nicht eingehalten - vom Koordinator als AW-01 akzeptiert** | Plan wurde inhaltlich vollstaendig, aber prozessual nicht vor dem ersten Implementierungsschritt geschrieben. Der Koordinator hat dies nach Root Review von W5-R01 explizit als `AW-01 - Coordinator Waiver` akzeptiert: kein verbleibender Produkt-/Release-Blocker, Historie wird nicht rueckwirkend umgeschrieben, ab W5-R02/W6 gilt wieder die volle Prozessreihenfolge |
| Soll-/Ist-Vergleich nach Umsetzung | Vollstaendig | Dieses Dokument |
| Abweichungsdokument bei materieller Abweichung | Vollstaendig | `04_DEVIATIONS.md` |

## Nicht-Ziele (bestaetigt eingehalten)

- Kein PyPI-/GHCR-/Docker-Hub-Publish, kein Git-Tag, kein GitHub-Release,
  kein Push, kein Merge nach `main` - siehe `Evidence/09_Git_Final/`.
- `VERSION` unveraendert `2.0.0`.
- Kein Redesign von Trigger/Protokoll v2/Settings/Wake-Word/STT-Model-
  Management/Kroko-Authority/W4C-Docker-Architektur/Client.
- Keine Aenderung an `build/vps/*` oder privaten VPS-Werten.
