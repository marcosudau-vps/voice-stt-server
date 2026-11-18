# AP-SRV-070 / W5-R01 - Implementation Report

## Aenderungstabelle

| Area | Files | Before | Change | Why | Gate |
|---|---|---|---|---|---|
| Release-Orchestrator | `release.py` | existierte nicht | Duenner CLI-Wrapper um `release_tooling.cli:main` | Ein kanonischer, oeffentlicher Release-Einstiegspunkt (Prompt Abschnitt 6) | W5P-G06 |
| Release-Tooling-Kern | `release_tooling/__init__.py`, `errors.py` | existierte nicht | Paketdoku + Fehlerhierarchie (`ReleaseError`, `ManifestError`, `StateError`, `OrderError`, `ConflictError`, `SecretDetectedError`) | Eine Stelle fuer alle Fehlermodi, damit Aufrufer sie unterscheiden koennen | W5P-G06 |
| Secret-Redaction | `release_tooling/redaction.py` | existierte nicht | `assert_no_secrets()`, `looks_like_secret_key_name()`, `redact_text()` mit Marker-/Muster-basierter Erkennung | State/Manifest/Logs duerfen nie Secrets enthalten (Abschnitt 7, 14) | W5P-G14 |
| Git-Identitaet | `release_tooling/gitinfo.py` | existierte nicht | Rein lesende `resolve_identity()`/`local_tag_commit()` | Exakte Commit-/Tree-/Sauberkeitspruefung fuer Preflight/State | W5P-G04, G13 |
| Konfiguration | `release_tooling/config.py` | existierte nicht | Reuse von `VoiceSTT._version.DISTRIBUTION_NAME` und `tools.build_production.IMAGE_NAMES`; GHCR/Docker-Hub-Repo-Wurzeln nur ueber Env-Var, kein Default | Keine zweite Versions-/Image-Namensauthority; keine erfundene Registry-Angabe | W5P-G06, Abschnitt 13 |
| RC-Manifest | `release_tooling/rc_manifest.py` | existierte nicht | Schema, Validierung, `build_rc_manifest()`/`load_rc_manifest()`/`write_rc_manifest()` | Kanonisches, secret-freies RC-Manifest fuer W5-R02/W6 (Abschnitt 12) | W5P-G23, G24 |
| Release-State | `release_tooling/state.py` | existierte nicht | `ReleaseState`, `STATE_ORDER`, `advance()`, `assert_tag_allowed()`/`assert_github_release_allowed()`, persistente Lade-/Speicherfunktionen | Resumable, monoton geordneter, secret-freier State (Abschnitt 7) | W5P-G08-G15 |
| Remote-Konfliktpruefung | `release_tooling/remote_checks.py` | existierte nicht | `check_pypi_release()`, `check_registry_image()`, injizierbare Fetcher/Runner | Sicheres, testbares Konflikt-Fail-Closed ohne echten Netzwerkaufruf in Tests (Abschnitt 8) | W5P-G12 |
| Feste Pipeline / Dry-Run | `release_tooling/pipeline.py` | existierte nicht | `PIPELINE_STEPS` (Daten), `plan_from()`, `dry_run()` | Feste W6-Reihenfolge als Daten statt verstreuter Logik; strukturell side-effect-freier Dry-Run | W5P-G08, G09 |
| Preflight | `release_tooling/preflight.py` | existierte nicht | `run_preflight()` mit 18 Einzelchecks (Version, Release Notes, Git, Tag, Manifest, Tools, Registry, Credentials, State-Konflikt) | Rein lesende Freigabepruefung (Abschnitt 9) | W5P-G07 |
| CLI | `release_tooling/cli.py` | existierte nicht | `preflight`/`dry-run`/`status`/`manifest validate`/`manifest build`/`prepare-next-version`/`publish` | Eine Bedienoberflaeche fuer alle Release-Operationen | W5P-G06-G09 |
| CI | `.github/workflows/ci.yml` | existierte nicht | Public-CI: Wheel-/Sdist-Build, `twine check`, Wheel-Install-Smoke, Unit-Suite auf Windows + Ubuntu 24.04 / Python 3.12 | Verbindliche CI (Abschnitt 10) | W5P-G16-G22 |
| Release Notes | `RELEASE_NOTES.md` | `## Unreleased` enthielt alles AP-SRV-070-Material | Neuer `## 2.0.0`-Abschnitt (konsolidiert das bisherige Material plus W5-Eintrag), frischer leerer `## Unreleased` daran anschliessend | Finale 2.0.0-Release-Notes vor RC-Freeze (Abschnitt 13) | W5P-G25 |
| Doku | `build/BUILD.md` | Abschnitt "Versions- und Releasepflege" beschrieb nur das kuenftige Konzept | Neue Unterabschnitte: Release-Orchestrator, RC-Manifest, kein verschwendeter Versionsstand, Freigabeprozess, GitHub-Actions-CI | Oeffentliche Autoritaet muss den tatsaechlichen W5/W6-Vertrag beschreiben (Abschnitt 14) | W5P-G26 |
| `.gitignore` | `.gitignore` | keine Regel fuer Release-State | `/release_state/` ergaenzt | Release-State ist kein Git-Artefakt (Abschnitt 7) | W5P-G13 |
| Tests | `tests/unit/test_release_*.py` (7 Dateien) | existierten nicht | 91 Tests + 11 subTests fuer Redaction/State/RC-Manifest/Pipeline/Remote-Checks/Preflight/CLI | Gezielte, hermetische Tests ohne echten Netzwerk-/Subprocess-Aufruf (Abschnitt 17) | W5P-G28 |
| Archiv | `docs/.archiv/einheitliche_triggerarchitektur/AP-SRV-070/2026-09-06_W5_R01_PLAN.md`, `..._UMSETZUNGSVERGLEICH.md` | existierten nicht | Plan + Soll-/Ist-Vergleich | Verbindlicher Archivprozess (`AGENTS.md`, `docs/.archiv/README.md`) | W5P-G03, G27 |

## Architekturerklaerungen

### Release-CLI

`release.py` ist absichtlich ein duenner Wrapper (fuegt nur `sys.path` um
das Repository-Root und ruft `release_tooling.cli.main()` auf). Die
gesamte Logik lebt in `release_tooling/`, damit es genau eine Release-
Authority gibt und die CLI-Datei selbst nie zu einer zweiten Implementierung
wird. Jeder Unterbefehl ist eigenstaendig testbar (`cli.build_parser()`
liefert einen echten `argparse.ArgumentParser`, den die Tests direkt
pruefen).

### State-/Resume-Modell

`release_tooling.state.STATE_ORDER` ist die einzige Stelle, die die neun
Zustaende (`PREPARED` .. `COMPLETE`) auflistet. `advance()` erlaubt
ausschliesslich den direkt naechsten Zustand oder eine Wiederholung des
aktuellen (Idempotenz) - jeder andere Sprung ist ein `OrderError`. Die
beiden Barrieren `assert_tag_allowed()`/`assert_github_release_allowed()`
sind duenne Wrapper um denselben Index-Vergleich, sodass es strukturell
unmoeglich ist, sie unabhaengig von der Kernreihenfolge zu pflegen und
dabei auseinanderlaufen zu lassen.

### Versionserhalt

`release_tooling` fuehrt keine eigene Versionslogik: `config.py` importiert
`VoiceSTT._version.DISTRIBUTION_NAME`, `preflight.py`/`cli.py` importieren
`read_version_file()`/`resolve_bump_kind()`/`bump()` direkt aus
`VoiceSTT._version`. Kein Pfad in `release_tooling` schreibt `VERSION`
ausser `cli._cmd_prepare_next_version()`, und selbst dort nur hinter dem
expliziten `--apply`-Flag - der aktuelle Publikationspfad
(`preflight`/`dry-run`/`status`/`publish`) beruehrt `VERSION` nie.

### Publikationsreihenfolge

`release_tooling.pipeline.PIPELINE_STEPS` ist ein Tupel von
`(von_zustand, zu_zustand, beschreibung)`-Tripeln in exakt der im Prompt
(Abschnitt 1.4) vorgegebenen Reihenfolge. Ein Modul-Level-`assert` prueft
beim Import, dass diese Liste mit `STATE_ORDER` uebereinstimmt - eine
Abweichung waere ein sofortiger Importfehler, nicht ein stiller Bug.
`dry_run()` nimmt ausschliesslich eine `ReleaseState`-Instanz entgegen
(keinen Runner, keinen Fetcher), kann also strukturell keinen Schreib-
/Netzwerkaufruf ausloesen.

### CI

Der Workflow nutzt durchgehend `shell: bash`, da Windows-Runner Git Bash
mitbringen - das haelt Linux- und Windows-Schritte identisch statt zwei
parallele Skriptsprachen zu pflegen. Er trennt bewusst zwei Sorgen: einen
isolierten Wheel-Install-Smoke (frische venv, `pip install <wheel>[...]`,
Pruefungen aus einem Nicht-Checkout-Verzeichnis) beweist "kein Editable-
Checkout noetig"; die reguläre Unit-/Guard-/Release-Tool-Suite laeuft wie
im bestehenden `build/BUILD.md`-Vorlauf ueber `python -m pytest -q
tests/unit` gegen den Checkout selbst. Beides wurde in diesem Run lokal
real ausgefuehrt (siehe `Evidence/05_Package_Qualification/`,
`Evidence/07_Tests/`), weil der Workflow selbst erst nach Push/Freigabe auf
GitHub existiert (Prompt Abschnitt 10.3).

### Fresh-Install-Strategie fuer das Paket

Die Free-/Pro-Imagenamensauthority (`tools/build_production.py`) bleibt
unveraendert und wird von `release_tooling.config` importiert statt neu
implementiert - genau wie deren eigene Tests importiert `config.py`
`tools/` per `sys.path`-Einfuegung, weil dieses Verzeichnis kein
Package-`__init__.py` hat.

### RC-Manifest

`rc_manifest.build_rc_manifest()` erwartet bereits aufgeloeste Identitaeten
(Wheel-/Sdist-Pfad+Hash, Kroko-Fingerprint+Artefakt-Hash, Image-Tag+ID) und
berechnet nichts selbst nach - es re-implementiert damit weder die
Kroko-Fingerprint-Authority noch die Image-Build-Authority, sondern bindet
nur deren bereits erzeugte Identitaeten in ein gemeinsames, versioniertes
Dokument. `release.py manifest build` liest dafuer zwei bereits vorhandene
`tools/build_production.py`-Build-Manifeste (Free/Pro) ein.

### Release Notes

Der `## 2.0.0`-Abschnitt entstand durch Umbenennung von `## Unreleased` in
`## 2.0.0` (kein Materialverlust) plus einem neuen, kurzen W5-Eintrag ueber
die Release-Infrastruktur selbst; direkt darueber steht ein frischer, leerer
`## Unreleased`-Abschnitt fuer kuenftige Aenderungen. Kein Datum wurde
angehaengt, weil der tatsaechliche oeffentliche Veroeffentlichungszeitpunkt
zu W6 gehoert und ein hier eingetragenes Datum vor der echten
Veroeffentlichung falsch wuerde.

### Handoff an W5-R02

W5-R02 kann ohne weitere Quelltextaenderung: (1) `release.py manifest
build` mit den beiden W5-R02-Build-Manifesten (Free/Pro) aufrufen, um ein
reales RC-Manifest fuer `W5-RC1` zu erzeugen; (2) `release.py preflight
--manifest <pfad>` gegen dieses Manifest ausfuehren; (3) das
`release_tooling.state`-Modell verwenden, um einen Qualifikationslauf als
State-Uebergaenge zu protokollieren, ohne die feste Reihenfolge oder die
Versionsauthority erneut zu implementieren.

### Bewusste Nicht-Aenderungen

- Kein Redesign von Trigger/Protokoll v2/Settings/Wake-Word/STT-Model-
  Management/Kroko-Fingerprint-Authority/W4C-Docker-Architektur/Client.
- Kein neuer Publish-Code fuer PyPI/GHCR/Docker Hub/Git-Tag/GitHub-Release -
  `release.py publish` bleibt in W5 absichtlich ohne echte Schreiblogik.
- Keine Aenderung an `tools/build_production.py`, `Dockerfile`,
  `docker-compose.yml`, `setup.py`-Packaging, `build/vps/*`.
- Kein GHCR-/Docker-Hub-Repository-Name geraten - beide bleiben ueber
  Umgebungsvariablen konfigurierbar und fehlen bewusst als Default.
