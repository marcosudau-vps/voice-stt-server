# AP-SRV-070 — W2
# Product Surface / Documentation / Repository Hygiene

## Auftrag

Finalisiere nach abgeschlossenem W1A/W1B/W1B-C1 die aktive Produktoberfläche
des Servers: README, technische Dokumentation und Repository-Hygiene.

W2 ist KEIN weiterer Runtime-Architekturblock. Der Runtime-/Legacy-Cut ist
abgeschlossen. W2 darf fachliche Verträge nur dort korrigieren, wo aktive
Dokumentation nach W1A/W1B objektiv stale ist.

## Authorities

W0:
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prep\W0\

W1A:
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W1A\

W1B:
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W1B\

W1B-C1:
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W1B-C1\

Pflichtlektüre:
- W0 DELTA_REVALIDATION
- W0 SCOPE_MATRIX
- W0 EXECUTION_BACKLOG
- W1A STATE + SCOPE_TRACE
- W1B STATE + SCOPE_TRACE
- W1B-C1 STATE

Aktuelle verbindliche Ausgangsbasis:

Distributed HEAD:
0e191a915d46bc4afcd88ab52049bfc075979cc7

Distributed TREE:
3e56a7d281ef5bf6f265a30c893d43b7f204058d

Canonical:
c82923fc6ce889b4dfbbde1f9877b8b76481a1e8

Nur starten wenn:
- Remote `github/feat/einheitliche-triggerarchitektur-distributed`
  == `0e191a915d46bc4afcd88ab52049bfc075979cc7`
- Worktree clean
- Canonical unverändert und clean
- W1B-C1 meldet W2 ready = JA

Sonst:
STATUS: BLOCKED

## Git / Worktree

Bestehenden AP-SRV-070-Worktree weiterverwenden:

P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070

Branch:
work/AP-SRV-070

Keinen neuen Worktree anlegen.
Kein Amend bestehender W1-Commits.
Kein Force-Push.

# W2-01 — README / Product Surface

README auf den tatsächlichen V2-Produktstand bringen.

Mindestens korrekt vermitteln:
- Zweck des VoiceSTT-Servers
- unterstützte Haupt-ASR-Engines auf aktuellem Stand
- FastAPI/Server-Nutzung
- Protocol v2 als aktueller Integrationspfad
- Legacy/v1 nur soweit real unterstützt
- server-authoritative Activation Lifecycle
- Settings Plane
- Wake Words / kanonischer Katalog
- installierbare Distribution / Packaging-Hinweis nur soweit vor W3 belastbar
- Links auf aktive vertiefende Doku
- keine historischen Projekt-/Agenten-/AP-Interna als Produkttext

Keine Release-/PyPI-Versprechen vorziehen, die W3/W6 erst herstellen.

# W2-02 — docs/fastapi-server.md

Auf aktuellen Produktvertrag bringen.

Mindestens prüfen/korrigieren:
- `/ws/v2`
- v1 `/ws/transcribe` korrekt als Legacy/Kompatibilität einordnen
- GET `/api/v2/wake-words`
- POST `/api/v2/wake-words/refresh`
- Settings-v2-Oberflächen
- serverVersion / serverCommit / supportedProtocolVersions
- Request-/Response-Beispiele
- Session-/Activation-Lifecycle
- aktuelle Wake-Word-Asset-Authority
- selected-only / kein impliziter Wake-Word-Default
- `VOICESTT_WAKEWORD_ASSET_ROOT`
- kein alter Directory-/beliebiger Manifest-Scan

W1B-C1 hat `--openwakeword-model-paths` bereits unmittelbar korrigiert.
Nicht wieder auf alte Semantik zurückdrehen.

# W2-03 — aktive technische Dokumentation bereinigen

Mindestens auditieren:
- docs/einheitliche-triggerarchitektur.md
- docs/module-map.md
- docs/configuration.md
- docs/api-compatibility.md
- docs/wake-words.md
- docs/client-development/**
- weitere aktive W0-Kandidaten

Bekannte Befunde:
1. `activation_command.py` -> real `activation_commands.py`
2. tote/veraltete `ARCHITECTURE.md`-Referenz prüfen
3. persönliche/absolute Pfade wie `D:/Projekte/STT/...` entfernen/neutralisieren
4. Sprach-/Terminologie-Inkonsistenzen bereinigen
5. Formulierung, v1 behalte kompakte IDs "bis AP-SRV-070", schärfen:
   kompakte v1-IDs bleiben bestehen; KEINE ID-Migration implementieren.
6. `docs/session-wakeword-erweiterung.md` enthält stale `default_model`-
   Beschreibung; Dokument ist ohnehin Archivkandidat.

# W2-04 — historische Dokumente archivieren

W0-Kandidaten nach Inhalt prüfen und unter bestehender Archivkonvention
archivieren, insbesondere:
- Planning/logging-fixes-implementierungsplan.md
- api_fastapi_server/MULTI_USER_IMPLEMENTATION_GUIDE.md
- docs/stt-server-specification.md
- docs/session-wakeword-erweiterung.md bzw. historische Teile

Vor Archivierung:
- prüfen, ob noch gültige Produktinformation nur dort existiert
- gültige Information ggf. in aktive Doku migrieren
- historische Aussage im Archiv nicht nachträglich modernisieren

# W2-05 — Repository Hygiene

Nach Referenzprüfung entfernen, sofern weiterhin unreferenziert:
- tests/suh_mahn_thuh.onnx
- tests/suh_man_tuh.onnx
- tests/samanta.tflite
- app_browserclient/start_server.bat
- app_talk_with_llm/start.bat
- app_talk_with_llm/install_cpu.bat

Vor Löschung:
- repo-weite Referenzsuche
- aktive Doku/CI/Skripte prüfen
- nur bei belegter Obsoleszenz entfernen

Keine produktiven Wake-Word-Bundle-Assets löschen.

# Wake-Word-Dokumentationsvertrag

Aktive Wake-Doku muss eindeutig sagen:
- `VoiceSTT/assets/wakeword_models/models.json` ist kanonische Manifestquelle
- keine parallele `openwakeword_catalog.py`-Authority
- kein `openwakeword_models`-Legacyspiegel
- kein impliziter Manifest-Default
- v2 selected-only
- ONNX/TFLite per-backend Health
- nur gesunde Backends als verfügbar darstellen
- Pipeline-Assets katalog-owned
- kein Runtime-Download
- explizite classifier paths bleiben als Direktpfad möglich, soweit implementiert
- `VOICESTT_WAKEWORD_ASSET_ROOT` ist Bundle-Override
- Calibration: `EVIDENCE_BLOCKED / calibration pending`

Nicht in W2 lösen:
Docker-/Compose-Referenzen auf `VOICESTT_OPENWAKEWORD_MODEL_ROOT`
gehören zum W4-Deployment-Cut, sofern sie Runtime-Dateien betreffen.
Docker-Code nicht ändern.

# Produkt-/Repo-Hygiene-Hard-Gates

Aktive Produktoberfläche darf keine:
- Agenten-/Prompt-/Worktree-Instruktionen
- AP-/Root-Workflow-Interna als Benutzeranleitung
- WIP/PREP-Markierungen
- persönliche absolute Pfade
- offensichtlichen toten API-Namen
- widersprüchlichen Versionsangaben
- veraltete Wake-Default-Semantik
- falsche Runtime-Download-Aussagen

enthalten.

Historische Archive dürfen historische Begriffe enthalten, wenn klar archiviert.

# Validierung

Mindestens:
1. interne Markdown-Links/Referenzen prüfen
2. repo-weite Suche nach bekannten stale Namen/Pfaden
3. Referenzprüfung aller gelöschten Dateien
4. betroffene Dokumentations-/Contract-Tests
5. relevante Wake-/Protocol-Tests, falls Beispiele maschinell validiert werden
6. `git diff --check`
7. `git status --porcelain`
8. Scope-Prüfung: keine Packaging-/Docker-/Release-Implementierung

Keine Runtime-Änderungen nur um Doku "schöner" zu machen.

# Commit / Distributed

Bei vollständigem PASS genau EIN Agentenrun-Commit.

Subject:
docs(server): finalize product surface and repository hygiene

Danach:
- SHA/TREE erfassen
- Worktree clean
- Canonical unverändert
- Remote Distributed vor Push noch `0e191a9...`

Distributed ausschließlich Fast-Forward:
feat/einheitliche-triggerarchitektur-distributed

Kein Force.
W2 SHA ist Basis für W3.

# Evidence

Unter:
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W2\

mindestens:
- 2026-08-30_W2_DOCUMENTATION_REPORT.md
- 2026-08-30_W2_HYGIENE_REPORT.md
- 2026-08-30_W2_SCOPE_TRACE.md
- 2026-08-30_W2_STATE.md

STATE:
- Parent `0e191a9...`
- W2 SHA/TREE
- Distributed before/after
- Canonical unchanged
- aktive Doku geändert
- archivierte Dokumente
- entfernte Dateien
- bewusst behaltene Kandidaten + Begründung
- Link-/Referenzchecks
- Tests/Checks
- Calibration Status
- W3 readiness

# Stop-Gates

STATUS: BLOCKED wenn:
- Distributed nicht auf W1B-C1 HEAD steht
- Worktree dirty/unexpected
- Canonical verändert
- historische Evidence ohne sichere Migration zerstört würde
- ein Löschkandidat noch aktiv referenziert wird
- Produktdoku nicht eindeutig auf aktuellen Runtimevertrag gebracht werden kann
- Packaging/Docker/Release-Scope nötig wäre, um W2 abzuschließen
- Tests/Checks rot
- Force-Push nötig

## Rückgabe

Schreib alle Evidence-Dateien nach:
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W2\

Schick mir alle Dateien aus diesem Ordner.
