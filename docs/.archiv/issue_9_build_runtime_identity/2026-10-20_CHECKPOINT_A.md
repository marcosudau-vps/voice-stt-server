# Checkpoint A: Runtime-/API-Implementierung

Ausgang: `e761b97334f263a6c51e84314bf3688599b84169`.
Dieser Checkpoint ist durch den Commit versioniert, der diese Datei einfuehrt;
kein separater Auftrag, kein Gesamtabschluss und keine Eigenabnahme.

## Umsetzung

Gemeinsame immutable Appidentitaet fuer OpenAPI, Info, Settings und V2
(Annahme/Snapshot/Refusals); keine Aenderung an Wireformaten oder an
isolierten expliziten Testidentitaeten. Dockercommit im Runtime-Stage
gebunden. Paketbesitz aus installierten Metadaten, nicht Image-/Keyname;
native Variante nur aus bestehender leichter Provenienz. Fehlender Commit
bleibt unknown; ungueltiger expliziter Commit erzeugt redigierten Fehler.
Vorhandene Hubkennung und no-store, keine Modellabfrage durch Info.
Keine neue Pflichtressource in A. F02/F03 sind hier noch nicht geschlossen.

## Ausgefuehrte direkte Pruefungen

Windows, CPython 3.12, pytest 9.1.1:

```text
python -m pytest -q tests/unit/test_server_info.py
  tests/unit/test_version_authority.py
  tests/unit/test_production_docker_contract.py
  tests/unit/test_protocol_v2_contract.py
  tests/unit/test_protocol_v1_v2_boundary.py --tb=short
154 passed, 1 skipped, 71 subtests passed (43.51s), Exit 0

python -m pytest -q tests/unit/test_server_info.py
  tests/unit/test_protocol_v2_e2e.py tests/unit/test_protocol_v2_settings.py
  tests/unit/test_fastapi_server_multi_user.py --tb=short
190 passed, 22 subtests passed (169.52s), Exit 0
```

Erster Skip: optionaler Vergleich mit externer Planoriginaldatei.
Die volle schnelle Suite wird zusaetzlich auf einem separaten unveraenderlichen
Checkpointcheckout ausgefuehrt; ihr abschliessendes Ergebnis gehoert in den
Soll-/Ist-Bericht. Der erste im veraenderlichen Worktree gestartete Gesamtlauf
ist kein sauber commitgebundener Baselinebeleg; die Baseline wird deshalb
getrennt auf exakt e761b973 wiederholt.

Logs liegen im Sitzungsartefaktbereich, nicht in Git.
Echte generische Free-/Pro-Docker-/Proxypruefung: **NOT_RUN**; Docker Desktop
ist manuell pausiert. Native-/Imagebindung daher **NOT_PROVEN**, nicht PASS.
Die direkte HTTP-/Wirepruefung verwendet den echten App-/Protokollpfad mit
isolierten Scheduler-/Recorderfixtures, keine echten ASRmodelle.

## Status und Fortsetzung

Runtime-/API-Regressionen PASS im beschriebenen Scope, vollstaendige
A-Qualifikation wegen Docker und unabhaengiger Pruefung offen.
B wird gemaess zusammenhaengendem Auftrag ohne erneute Freigabe umgesetzt;
dies hebt keine offene A-Pflicht auf und behauptet keinen A+B-Abschluss.
