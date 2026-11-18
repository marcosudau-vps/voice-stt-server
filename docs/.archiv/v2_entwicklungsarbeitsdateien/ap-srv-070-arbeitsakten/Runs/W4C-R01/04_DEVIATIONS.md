# AP-SRV-070 / W4C-R01 - Abweichungen

## AW-01: Wiederverwendung des bestehenden `test_project_config.py`-Compose-Vertragstests

- **Soll:** "Geschlossene Contract-Assertions nicht abschwaechen" (Abschnitt 16).
- **Ist:** Der bestehende Test
  `test_root_config_is_valid_for_server_and_example_app` pruefte zwei
  Detailwerte des ALTEN Compose-Vertrags (`args.KROKO_VARIANT`,
  `/data`-Mount mit Pflichtwert). Diese Werte wurden auf den neuen,
  dokumentierten W4C-Vertrag angepasst (`args.VOICESTT_KROKO_VARIANT`,
  `/var/lib/voicestt`-Mount mit portablem Default).
- **Ursache:** W4C aendert den Compose-/Dockerfile-Vertrag bewusst und
  dokumentiert (Plan, Entscheidungen C/D/H): Free/Pro ist kein Docker-Build-Arg
  mehr, das die native Kroko-Kompilierung steuert (die entfaellt vollstaendig
  im Production-Image); der persistente Runtime-Root heisst neu
  `/var/lib/voicestt` statt `/data` und ist portabel statt `tools/compose.py`
  zu erzwingen.
- **Auswirkung:** Keine Abschwaechung einer Sicherheits- oder
  Korrektheitsaussage; der Test prueft weiterhin exakt, was der neue,
  oeffentlich dokumentierte Vertrag verspricht - er wurde an den *geaenderten*
  Vertrag angepasst, nicht gelockert.
- **Security-/Release-Relevanz:** Keine.
- **Entscheidung:** Angepasst, im Run-Diff sichtbar
  (`tests/unit/test_project_config.py`).
- **Follow-up:** Keines.
- **Gate-Auswirkung:** Keine; siehe `03_EVIDENCE_INDEX.md`.

## AW-02: `config.yaml` `deployment.image`-Wert umbenannt

- **Soll:** Private/betreiberspezifische Werte in `config.yaml` bleiben in
  diesem Run unangetastet (Abschnitt "Nicht Teil dieses Runs" / Plan
  Nicht-Ziele).
- **Ist:** `deployment.image` wurde von `voicestt-cpu:local` auf
  `voice-stt-server:local` umbenannt.
- **Ursache:** Kein privater Pfad/Domain-Wert, sondern ein reiner
  Image-Tag-Name, der durch die in diesem Run eingefuehrte neue
  Produktidentitaet (`voice-stt-server`/`voice-stt-server-pro`) sonst auf ein
  Image zeigen wuerde, das der neue Production-Build nicht mehr erzeugt - eine
  eindeutig gebrochene Verlinkung im Sinne der in Abschnitt 1/24 explizit
  erlaubten Ausnahme.
- **Auswirkung:** Marcos lokaler `tools/compose.py`-Workflow bleibt
  funktionsfaehig; keine seiner privaten Pfad-/Domain-Werte wurde veraendert.
- **Security-/Release-Relevanz:** Keine.
- **Entscheidung:** Umbenannt, mit Kommentar im Diff begruendet.
- **Follow-up:** Keines.
- **Gate-Auswirkung:** Keine.

## AW-03: Free- und Pro-VoiceSTT-Wheel nicht byteidentisch (nur Cache-Dateien)

- **Soll:** W4C-G29 - Free und Pro enthalten denselben VoiceSTT-Produktstand.
- **Ist:** Free und Pro wurden in diesem Run mit zwei getrennten Aufrufen
  (`python tools/build_production.py free`, danach `... pro`) gebaut. Jeder
  Aufruf baut das VoiceSTT-Wheel neu; die beiden resultierenden
  `voicestt-2.0.0-*.whl` haben unterschiedliche SHA-256
  (`ebe22ea6...` vs. `a6df1d7a...`), weil `python -m build` bei zwei
  getrennten Laeufen unterschiedliche Zip-Metadaten (mtimes) in den
  Wheel-Eintraegen erzeugt.
- **Ursache:** Kein reproduzierbarer Build-Modus (`SOURCE_DATE_EPOCH` o. ae.)
  fuer `python -m build` konfiguriert; PEP-517-Wheels sind ohne das nicht
  byteidentisch bei zwei getrennten Aufrufen desselben Quellstands.
- **Auswirkung:** Per-Datei-SHA-256-Vergleich der in beiden Images
  installierten VoiceSTT-/api_fastapi_server-/VoiceSTT_server-Pakete
  (233 Dateien) zeigt: alle Quelldateien sind byteidentisch; die einzigen
  Abweichungen betreffen 87 automatisch erzeugte `__pycache__/*.pyc`-Dateien
  (Python-Bytecode-Cache, haengt vom eingebetteten Quell-mtime ab). Der
  tatsaechliche VoiceSTT-Produktstand ist damit nachweislich identisch;
  betroffen ist ausschliesslich die aeussere Wheel-Artefakt-Pruefsumme.
- **Security-/Release-Relevanz:** Keine inhaltliche Abweichung; fuer einen
  kanonischen Release-Lauf baut `python tools/build_production.py all` das
  VoiceSTT-Wheel nur einmal und installiert exakt dieses Wheel in beide
  Images, wodurch auch die aeussere Pruefsumme identisch waere.
- **Entscheidung:** Als Erkenntnis dokumentiert; keine Codeaenderung noetig,
  da der Orchestrator fuer `all` bereits das korrekte, deterministische
  Verhalten hat. Empfehlung fuer produktive Releases: immer `all` statt
  getrennter `free`/`pro`-Laeufe verwenden, wenn beide Varianten
  veroeffentlicht werden.
- **Follow-up:** Keines fuer diesen Run.
- **Gate-Auswirkung:** W4C-G29 gilt als erfuellt (Beweis: Evidence/04_Docker_Pro/01_pro_image_build.txt, Datei-Hash-Vergleich).

Weitere materielle Abweichungen werden hier ergaenzt, sobald sie im
Smoke-Verlauf auftreten.
