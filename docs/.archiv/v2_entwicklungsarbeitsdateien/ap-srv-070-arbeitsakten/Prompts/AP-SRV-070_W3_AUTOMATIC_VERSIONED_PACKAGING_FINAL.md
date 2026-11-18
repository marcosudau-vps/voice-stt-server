# AP-SRV-070 — W3
# Python Packaging + Automatic Version Authority + Installed-Artifact Qualification

## Auftrag

Finalisiere die Python-Distribution des Servers und etabliere eine einzige,
automatisierbare Produktversions-Authority.

W3 ist die Packaging-/Versionierungsgrundlage für den späteren Releasepfad.
Es veröffentlicht noch nichts nach PyPI und erzeugt keinen endgültigen
Release-Tag.

Die Release-Bedienung soll später dem bereits etablierten Muster folgen:

- `python release.py` -> PATCH
- `python release.py --minor` -> MINOR
- `python release.py --major` -> MAJOR
- optionaler Dry-Run ohne Mutation
- keine manuelle Versionspflege durch den Benutzer
- keine Versionsnummer wird allein durch einen fehlgeschlagenen Preflight verbraucht
- ein nach Tag teilweise fehlgeschlagener Release wird unter derselben Version wieder aufgenommen

W3 implementiert die dafür nötige technische Versions-/Packaging-Authority,
aber NICHT den vollständigen W5/W6-Publish-State-Machine-Workflow.

## Startbedingungen

W2 inklusive W2-C1 und W2-C2 ist Root-geprüft PASS.

Distributed HEAD:
`759cac09038c5a7f8c383eba98b934365bdc9eba`

Distributed TREE:
`744fd3fefdecfbfdc94ff4abdbcc7415a8093be8`

Canonical:
`c82923fc6ce889b4dfbbde1f9877b8b76481a1e8`

Nur starten wenn:

- Remote `github/feat/einheitliche-triggerarchitektur-distributed`
  exakt auf `759cac09038c5a7f8c383eba98b934365bdc9eba` steht
- Worktree clean
- Canonical unverändert und clean
- W2-C2 STATE meldet W3 ready = JA

Sonst:
STATUS: BLOCKED

## Git / Worktree

Bestehenden Worktree weiterverwenden:

`P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070`

Branch:
`work/AP-SRV-070`

Keinen neuen Worktree.
Kein Amend bestehender Runs.
Kein Force-Push.
Canonical bleibt unverändert.

Keine neue persistente lokale venv anlegen.

Für isolierte Install-Smokes bevorzugt:
- disposable Python-Container
- oder eine andere vollständig temporäre, nach dem Test verworfene Umgebung

Nicht das Source-Checkout auf `sys.path` als Install-Smoke verwenden.

# W3-01 — Versionsinventar und eine Authority

Vor Implementierung repo-weit alle produktrelevanten Versionsquellen finden.

Mindestens prüfen:

- `setup.py`
- Package-`__version__` / Versionmodule
- Server-/Protocol-Identity
- Health/Handshake/API-Versionprojektion
- Docker-/OCI-Versionswerte, soweit bereits vorhanden
- Doku
- Release-/Build-Skripte
- Git Tags / vorhandene Releases soweit lokal/remote prüfbar

Bekannter W0-Befund:
`setup.py` enthält aktuell `current_version = "1.0.2"` und war nicht konsistent
mit der bereits etablierten V2-Serveridentität.

Diese Inkonsistenz muss verschwinden.

## Ziel

Es gibt genau EINE technische Produktversions-Authority.

Empfohlene Form:
eine kleine source-controlled `VERSION`-Authority plus ein gemeinsamer
Python-Resolver, den Packaging und Runtime verwenden.

Wichtig:

- `setup.py` enthält keine eigenständig gepflegte Versionskonstante mehr.
- Runtime-/Handshake-/Health-Version wird nicht separat hardcodiert.
- Package Metadata und Runtime-Identity lesen dieselbe Authority.
- Ein Release-Candidate muss die Version explizit injizieren können, OHNE
  vor dem Tag dauerhaft mehrere Dateien umzuschreiben.
- Normaler Benutzer editiert die Version nie manuell.

Ein sinnvoller Resolver darf deshalb einen expliziten, validierten
Build-/Release-Version-Override akzeptieren und sonst auf die
source-controlled Authority zurückfallen.

Der Override:
- muss SemVer validieren
- darf nicht still auf ungültige Werte zurückfallen
- muss für Wheel, sdist und installierte Runtime identisch gelten

Keine Versionsableitung aus Commit-Message-Konventionen.

## Baseline-Migration

W3 ist KEIN neuer Release-Bump.

Ermittle den aktuell tatsächlich beabsichtigten Produktversionsstand aus den
bestehenden Version-/Identity-Verträgen und der Release-Historie.

Wenn die etablierte aktuelle V2-Produktidentity eindeutig den Baselinewert
vorgibt, migriere diesen Wert in die eine Authority.

Falls mehrere gleichberechtigte Quellen widersprüchlich bleiben und sich die
richtige Baseline nicht aus Projekt-/Git-/Evidence-Vertrag bestimmen lässt:

STATUS: BLOCKED

Nicht willkürlich eine neue Major-/Minor-/Patch-Version erfinden.

# W3-02 — Release-Bump-Semantik vorbereiten

Die deterministische SemVer-Logik soll automatisiert testbar sein.

Späterer UX-Vertrag:

Patch:
`python release.py`

Minor:
`python release.py --minor`

Major:
`python release.py --major`

Regeln:

- PATCH: patch + 1
- MINOR: minor + 1, patch = 0
- MAJOR: major + 1, minor = 0, patch = 0
- `--minor` und `--major` gegenseitig exklusiv
- ohne Flag PATCH
- keine automatische Major-/Minor-Erkennung aus Committext

W3 darf bereits die wiederverwendbare SemVer-/Version-Utility implementieren,
wenn das die eine Authority sauber macht.

Die vollständige mutierende `release.py`-State-Machine und externe Publikation
gehören weiterhin W5/W6.

# W3-03 — Packaging modernisieren und deterministisch machen

Baue eine belastbare wheel+sdist-Distribution.

Hard-Gates:

- wheel baut
- sdist baut
- Metadaten valide
- `twine check` oder gleichwertiges PyPI-Metadaten-Gate grün
- Version in wheel/sdist entspricht der injizierten/aufgelösten Authority
- installierte Distribution meldet exakt dieselbe Version
- Entry Points funktionieren aus installierter Distribution
- Source-Checkout ist für diese Smokes nicht importierbar/bevorzugt

Noch KEIN PyPI-Publish.

# W3-04 — Wake-Asset Packaging als hartes Produktgate

W2-C2 hat die kanonische Wake-Bundle-Authority reproduzierbar gemacht.

Vor Packaging-Hard-Gate ausführen:

`python tools/sync_wakeword_assets.py --source <belegte SOURCE> --check`

muss Exit 0 liefern, sofern die bekannte Source auf der ausführenden Maschine
verfügbar ist.

Wenn die externe Maintenance-Source in einer CI-/isolierten Buildumgebung
nicht verfügbar ist:
- Bundle-internal integrity/manifest checks müssen trotzdem ausführbar sein
- nicht zur Laufzeit herunterladen
- Source-unavailable sauber als nicht ausführbarer Maintenance-Check dokumentieren

## Wheel/Sdist müssen enthalten

- `VoiceSTT/assets/wakeword_models/models.json`
- alle 25 manifestierten ONNX-Classifier
- alle 25 manifestierten TFLite-Classifier
- ONNX melspectrogram + embedding pipeline
- TFLite melspectrogram + embedding pipeline
- `silero_vad.onnx`
- benötigte sonstige tatsächlich paketgebundene Produktressourcen
- FastAPI static resources

## Keine Glob-Leakage als Packaging-Authority

Im Source-Bundle existieren historisch zusätzliche, nicht öffentlich
manifestierte Wake-Artefakte/Varianten.

Die aktuelle `setup.py`-Logik verwendet breite:

- `assets/wakeword_models/*.onnx`
- `assets/wakeword_models/*.tflite`

Globs.

W3 muss prüfen, ob dadurch unmanifestierte historische Zusatzmodelle in das
öffentliche Wheel gelangen.

Produktregel:

**Das öffentliche Python-Artefakt darf nur die durch die kanonische
Manifest-/Auxiliary-Authority freigegebenen Wake-Ressourcen enthalten.**

Nicht manifestierte experimentelle/historische Varianten nicht allein wegen
eines Dateiglobs veröffentlichen.

Diese Dateien müssen nicht aus dem Source-Repository gelöscht werden, wenn sie
bewusst als historische/geschützte Assets erhalten bleiben sollen.
Packaging soll sie schlicht nicht als Produktressource exponieren.

Erzeuge für Package Data eine deterministische, authority-basierte Auswahl,
statt einen zweiten manuellen Modellkatalog einzuführen.

# W3-05 — Installed-Distribution Wake Smoke

Aus einer isoliert installierten Distribution, nicht aus Source:

1. Package importieren.
2. Produktversion lesen.
3. `default_asset_root()` / `importlib.resources` zeigt in die installierte Distribution.
4. `models.json` laden.
5. Manifestrevision korrekt.
6. 25 öffentliche Wake Words vorhanden.
7. ONNX/TFLite-Artefakte für alle manifestierten Einträge vorhanden.
8. Pipeline beider Backends vorhanden.
9. `silero_vad.onnx` vorhanden.
10. Hash/Byte-Integrität des Bundles prüfen.
11. Nicht manifestierte historische Zusatzmodelle sind NICHT versehentlich im Wheel enthalten.
12. `/api/v2/wake-words` aus installierter Serverdistribution funktioniert.
13. selected wake word kann unter einem verfügbaren Backend initialisiert werden.
14. keine Runtime-Downloads.

Backend-Runtime-Abhängigkeiten dürfen umgebungsbedingt fehlen.
Dann muss der Katalog den betreffenden Backend korrekt als unavailable melden;
das Asset selbst muss trotzdem vollständig paketiert sein.

Mindestens ein real verfügbarer Backendpfad soll in einer qualifizierten
Testumgebung initialisiert werden.

Keine reale Wake-Audio-Kalibrierung erfinden.

Calibration bleibt:
`EVIDENCE_BLOCKED / calibration pending`

# W3-06 — Server-/Package Identity

Nach W3 müssen mindestens folgende Werte konsistent aus derselben Authority kommen:

- Python Distribution Version
- importierbare Package/Product Version
- Server Version
- Protocol-v2 Handshake `serverVersion`
- Health/API-Identity, soweit vorhanden

`serverCommit` bleibt Commit-Identity und ist nicht mit SemVer zu vermischen.

Tests müssen explizit beweisen, dass ein Build-Version-Override überall
denselben Wert erzeugt und keine alte Hardcodierung übrig bleibt.

# W3-07 — Candidate Build ohne Versionsverbrauch

Implementiere/prüfe den Mechanismus, mit dem später W5/W6 eine Kandidatenversion
zunächst nur berechnet und qualifiziert.

Vor endgültigem Tag darf ein Fehlschlag bei Tests, Build, Metadaten,
Installed-Smoke, Wake-Asset-Gate, Docker, CI oder Credentials/Netzwerk
keine neue Version verbrauchen.

W3-Nachweis mindestens:

- Kandidatenversion kann ohne permanente Source-Mutation erzeugt werden.
- Ein simulierter Build-/Testfehler hinterlässt keinen Tag und keine
  automatisch hochgezählte nächste Version.
- Wiederholung derselben Eingabe berechnet denselben Kandidaten, solange kein
  gültiger Release dazwischen abgeschlossen wurde.

Keine Tags erzeugen.
Keine Releases veröffentlichen.

# W3-08 — Tests

Mindestens automatisierte Tests für:

## Version
- gültige SemVer
- ungültige SemVer
- Patch
- Minor
- Major
- Minor setzt Patch = 0
- Major setzt Minor/Patch = 0
- exklusive Flags/Inputs
- Build-Override
- Setup/Package/Runtime/Handshake Konsistenz
- keine zweite Hardcoded Product-Version

## Packaging
- wheel build
- sdist build
- Metadaten
- genaue Package-Resource-Liste
- keine unmanifestierten Wake-Asset-Leaks
- installed distribution import
- console entry points
- FastAPI import/start smoke
- Wake catalog/API from installed artifact

## Asset integrity
- models.json
- 25 dual-backend classifier pairs
- 4 pipeline assets
- VAD auxiliary asset
- hashes/sizes
- no runtime download

Danach relevante bestehende Regression.

Sofern Packaging-/Identity-Code breite Runtime-Seams berührt:
vollständige Unit-Suite.

Immer:
- `git diff --check`
- finaler Worktree clean nach Commit

# W3-09 — PyPI Preflight

Noch nicht veröffentlichen.

Mindestens:

- Distribution-Name prüfen
- Metadata/README renderbar
- `twine check` oder äquivalent
- Wheel/Sdist Dateinamen korrekt
- Version korrekt
- keine lokalen Pfade
- keine Secrets
- keine Build-/Test-/Agent-Evidence im Artefakt
- keine unerwarteten großen Source-Dateien
- keine unmanifestierten historischen Wake-Artefakte

Falls Netzwerkzugriff verfügbar:
nur reversible/nicht publizierende PyPI-Namens-/Versionsprüfung.

Keine Veröffentlichung.

# Scope

Erlaubt:

- Versionsauthority / Version Resolver
- wiederverwendbare SemVer Utility
- Packaging-Konfiguration
- Packaging-/Version-Tests
- Build-/Smoke-Helfer
- minimale direkt betroffene Packaging/Release-Doku
- Package Resource Authority
- notwendige Entry-Point-/Identity-Anpassungen

Nicht erlaubt:

- PyPI Publish
- Git Tag
- GitHub Release
- GHCR/Docker-Hub Publish
- Production Docker Redesign
- Kroko Artifact Productization
- vollständige Release State Machine
- Client-Arbeit

# Commit / Distributed

Bei erfüllten Implementierungs-, Scope- und Test-Gates genau EIN
Agentenrun-Commit.

Parent:
`759cac09038c5a7f8c383eba98b934365bdc9eba`

Subject:
`build(server): establish automatic versioned distribution`

Danach:

- SHA/TREE erfassen
- Worktree clean
- Canonical unverändert
- Remote Distributed vor Push weiterhin `759cac0...`

Distributed ausschließlich per Fast-Forward:
`feat/einheitliche-triggerarchitektur-distributed`

Kein Force.
Kein Amend alter Runs.

# Evidence

Unter:

`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W3\`

mindestens:

- `2026-08-30_W3_VERSION_AUTHORITY_REPORT.md`
- `2026-08-30_W3_PACKAGING_REPORT.md`
- `2026-08-30_W3_INSTALLED_ARTIFACT_REPORT.md`
- `2026-08-30_W3_TEST_REPORT.md`
- `2026-08-30_W3_STATE.md`

STATE muss enthalten:

- Parent `759cac0...`
- W3 SHA/TREE
- alte Versionsquellen / entfernte Doppelpflege
- neue Version Authority
- Baseline-Version + Herleitung
- Candidate-Version-Mechanismus
- wheel/sdist Namen + SHA256
- Package Resource Inventory
- Nachweis keine unmanifestierten Wake-Asset-Leaks
- installed distribution version
- server/handshake version
- Wake installed-artifact smoke
- PyPI preflight
- Tests
- Calibration Status
- Distributed before/after
- Canonical unchanged
- W4A readiness

## Abschluss

Lege die Evidence vollständig unter

`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W3\`

ab und beende den Lauf mit einer kurzen Zusammenfassung sowie dem Hinweis,
dass der Evidence-Ordner fertig ist.
