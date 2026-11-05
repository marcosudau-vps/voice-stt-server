# 10 – Build, CI und Release-Technik

Diese Seite beschreibt die **technische** Verdrahtung. Sie ist keine
Release-Freigabe; der Veröffentlichungsweg ist im Code an eine verifizierte
Weiterverteilungsfreigabe gebunden, die derzeit `BLOCKED` ist (Abschnitt 5).

## 1. Versions- und Identitätsautorität

- Produktversion: Datei `VERSION` (Inhalt `2.0.0`), aufgelöst über
  `VoiceSTT._version.resolve_version()`; `setup.py` und
  `voice_stt_server.get_version()` nutzen dieselbe Funktion.
- Build-Identität: `build_identity_support.capture_identity` schreibt beim
  Wheel-/sdist-Bau eine Identität (Quellbaum, Dirty-Flag, Datum,
  Distributionsname); `VoiceSTT._build_identity` validiert sie zur Laufzeit.
  `/api/v2/info` meldet `identityStatus` (`incomplete` im Quell-Checkout).
- `VOICESTT_SERVER_COMMIT` muss – wenn gesetzt und validiert – ein voller
  Git-SHA in Kleinbuchstaben sein (`VoiceSTT/_build_identity.py:47`).

## 2. Wheel und Container

| Schritt | Werkzeug | Ergebnis |
| --- | --- | --- |
| Entwickler-Wheel | `python -m build --outdir dist` | `voicestt-<v>-*.whl` + sdist (CI) |
| Öffentliches Produkt-Wheel | `tools/build_distribution.py pro --kroko-wheel … --out-dir …` | `voice-stt-server`-Wheel mit eingebetteter Kroko-Laufzeit |
| Produktionsimage | `tools/build_production.py {pro,all}` | Wheel → Kroko-Artefakt auflösen → Docker-Image (`linux/amd64`) |
| Kroko-Native | `build/kroko-builder.Dockerfile`, `stt-install-kroko` | natives Kroko-Wheel; Fingerprint über `VoiceSTT/kroko/buildinputs.py` + `fingerprint.py` |

Hinweise aus dem Code:

- `tools/build_production.py` akzeptiert als Ziel nur `pro` oder `all`
  (`SUPPORTED_VARIANTS = ("pro",)`); der Kommentar in `docker-compose.yml`
  nennt noch `free`. Maßgeblich ist die CLI.
- `--dist-dir` muss das `dist/` des Repositorys sein, weil das Dockerfile
  daraus kopiert.
- Das Basis-Image ist zweimal gepinnt (Dockerfile und
  `PRODUCTION_BASE_IMAGE_DIGEST` in `tools/build_production.py`);
  `tests/unit/test_production_docker_contract.py` prüft Gleichstand.
- Wake-Word-Assets: Das Paket enthält genau die Dateien aus dem Manifest
  (`wakeword_package_resources.bundled_package_data_files`), nicht per Glob.

## 3. CI (`.github/workflows/ci.yml`)

Auslöser: `pull_request`, `push` auf `main`, `feat/**`, `work/**`,
`workflow_dispatch`. Rechte: `contents: read`. Veröffentlicht nichts.

Matrix `ubuntu-24.04` und `windows-latest`, Python 3.12:

1. Wheel + sdist bauen, `twine check`.
2. Frische venv, **nicht-editierbare** Installation des Wheels mit
   `[recommended,server]`, `pip check`, Import- und Versionsprüfung
   (`VoiceSTT_server`, `voice_stt_server`, `resolve_version()`),
   Existenz aller fünf Console-Scripts, Paket-Assets (`warmup_audio.wav`,
   `kroko/models.json`, `static/index.html`, Wake-Word-Modelle).
3. Editierbare Dev-Installation + `requirements-dev.txt`, `pip check`.
4. `python -m pytest -q tests/unit tests/compatibility`.
5. `python -m pytest -q tests/packaging`.
6. `git diff --check`.

Alle Actions sind auf volle Commit-SHAs gepinnt; das prüft
`tests/unit/test_release_workflows.py`.

## 4. Release-Candidate (`.github/workflows/release-candidate.yml`)

Nur `workflow_dispatch` (Eingabe `qualification_context`). Jobs:

| Job | Runner | Wesentliche Schritte |
| --- | --- | --- |
| `candidate-linux` | ubuntu-24.04 | Fingerprints auflösen (`tools/release_candidate.py --print-fingerprints`), Kroko-Pro-Artefakt wiederherstellen, Login **nur** zu privatem GHCR-Staging (`packages: write`), Linux-Kandidat bauen, installierte Identitäten qualifizieren (`tools/qualify_build_identity.py`), Artefakte hochladen |
| `build-windows` | ubuntu-24.04 | Windows-Wheels per Cross-Build, Identitäten prüfen |
| `candidate-windows` | windows-latest | Windows-Kandidat installieren und qualifizieren |
| `candidate` | ubuntu-24.04 | RC-Manifest bauen (`python release.py manifest build`), validieren, „keine öffentliche Release-Schreiboperation“ nachweisen, Paket-Smoketest aller Plattform-Wheels, Qualifikation (`python release.py manifest qualify`) |

## 5. Veröffentlichung (`.github/workflows/release-publish.yml`)

Nur `workflow_dispatch` mit `candidate_run_id` und `version`. Top-Level
`permissions: {}`; jeder Job läuft in der GitHub-Umgebung `release`:

| Job | Zustandsübergang |
| --- | --- |
| `tag` | `PREPARED → TAGGED` |
| `pypi` | `TAGGED → PYPI_PUBLISHED` (mit `release.py precheck-pypi`) |
| `registries` | `PYPI_PUBLISHED → EXTERNAL_VERIFIED` |
| `finalize` | `EXTERNAL_VERIFIED → COMPLETE` (Aliase, GitHub-Release) |

Jeder Job ruft `python release.py publish --until <STATE>` auf.

### Release-State-Machine (`release_tooling/state.py`)

```text
PREPARED -> TAGGED -> PYPI_PUBLISHED -> DOCKERHUB_PUBLISHED -> GHCR_PUBLISHED
 -> EXTERNAL_VERIFIED -> ALIASES_PUBLISHED -> GITHUB_RELEASED -> FINAL_VERIFIED -> COMPLETE
```

Aus Zustand `X` ist nur `X` (idempotente Wiederaufnahme) oder der direkte
Nachfolger erlaubt; alles andere ist `OrderError`.

### Harte Gates im Code

- `run_engine` im Modus `REAL` verlangt
  `redistribution_verified(manifest["redistributionApproval"])` **und**
  `releaseReadiness == "QUALIFIED"`; sonst `ManifestError`
  (`release_tooling/engine.py`).
- `build/kroko-redistribution.json` steht auf `"status": "BLOCKED"`.

## 6. Root-Einstieg `release.py`

`release.py` ist eine dünne Fassade auf `release_tooling.cli.main`.
Unterbefehle (beobachtet mit `--help`):

| Befehl | Wirkung laut Code/Help |
| --- | --- |
| `preflight` | nur lesende Prüfungen; laut Docstring kein Netzwerk |
| `dry-run` | geht den echten Ablauf im Modus `DRY_RUN`; persistiert nichts; Standard-Adapter führen aber lesende `verify()`-Abfragen gegen externe Dienste aus |
| `status` | aktueller Release-Zustand |
| `manifest` | RC-Manifest bauen/validieren/qualifizieren |
| `prepare-next-version` | nächste Version berechnen; schreibt nur mit `--apply` |
| `precheck-pypi` | lesender PyPI-Vorabcheck |
| `publish` | echter Lauf; verlangt `--manifest` und `--yes` |

Beobachtet (`python release.py preflight` auf einem lokalen Checkout ohne
Registry-Konfiguration): Exit-Code `1`; u. a. `version_matches_expected`
und `release_notes_prepared` `PASS`, `rc_manifest_complete` `WARN`, fehlende
Registry-/Credential-Konfiguration `FAIL`. Es wurde nichts geschrieben.

## Primäre Quellen

- [`setup.py`](../../setup.py), [`build_identity_support.py`](../../build_identity_support.py), [`wakeword_package_resources.py`](../../wakeword_package_resources.py), [`VERSION`](../../VERSION)
- [`tools/build_production.py`](../../tools/build_production.py), [`tools/build_distribution.py`](../../tools/build_distribution.py), [`tools/release_candidate.py`](../../tools/release_candidate.py), [`tools/qualify_build_identity.py`](../../tools/qualify_build_identity.py)
- [`release.py`](../../release.py), [`release_tooling/cli.py`](../../release_tooling/cli.py), [`release_tooling/state.py`](../../release_tooling/state.py), [`release_tooling/engine.py`](../../release_tooling/engine.py), [`release_tooling/preflight.py`](../../release_tooling/preflight.py), [`release_tooling/config.py`](../../release_tooling/config.py)
- [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml), [`release-candidate.yml`](../../.github/workflows/release-candidate.yml), [`release-publish.yml`](../../.github/workflows/release-publish.yml)
- Tests: [`tests/unit/test_release_workflows.py`](../../tests/unit/test_release_workflows.py), [`tests/unit/test_release_state.py`](../../tests/unit/test_release_state.py), [`tests/unit/test_release_engine.py`](../../tests/unit/test_release_engine.py), [`tests/unit/test_release_preflight.py`](../../tests/unit/test_release_preflight.py), [`tests/unit/test_build_production.py`](../../tests/unit/test_build_production.py), [`tests/unit/test_build_distribution.py`](../../tests/unit/test_build_distribution.py), [`tests/unit/test_unified_product.py`](../../tests/unit/test_unified_product.py), [`tests/unit/test_version_authority.py`](../../tests/unit/test_version_authority.py), [`tests/packaging/test_identity_installation.py`](../../tests/packaging/test_identity_installation.py)
