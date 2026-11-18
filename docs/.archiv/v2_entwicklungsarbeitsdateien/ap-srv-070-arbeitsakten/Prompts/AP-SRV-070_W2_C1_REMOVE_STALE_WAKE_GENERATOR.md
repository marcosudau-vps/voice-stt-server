# AP-SRV-070 — W2-C1
# Root Correction — Remove stale duplicate Wake Manifest Generator

## Ausgangslage

W2 wurde als ein Run-Commit veröffentlicht:

Parent:
0e191a915d46bc4afcd88ab52049bfc075979cc7

W2:
efdebc36a6cb7877197545032db074fdda43fad9

W2 TREE:
dcb987279e89331ba9a86f6c77e121c45e6eb1f1

Der W2-Run ist in Dokumentation, Archivierung und Repository-Hygiene weitgehend
sauber. Im W2-Audit wurde jedoch ein aktiver, redundanter Generator gefunden,
der außerhalb des ursprünglichen Löschkandidaten-Sets lag:

VoiceSTT/assets/wakeword_models/generate_models_json.ps1

Dieser Befund muss vor W3 geschlossen werden.

## Git / Worktree

Bestehenden AP-SRV-070-Worktree weiterverwenden:

P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070

Branch:
work/AP-SRV-070

Vor Mutation zwingend prüfen:

- HEAD == `efdebc36a6cb7877197545032db074fdda43fad9`
- Remote `github/feat/einheitliche-triggerarchitektur-distributed`
  == `efdebc36a6cb7877197545032db074fdda43fad9`
- Worktree clean
- Canonical weiterhin
  `c82923fc6ce889b4dfbbde1f9877b8b76481a1e8`
- Canonical-Workspace clean

Sonst:
STATUS: BLOCKED

Kein neuer Worktree.
Kein Amend.
Kein Force-Push.

# ROOT FINDING F1 — stale duplicate manifest generator

## Defekt

`VoiceSTT/assets/wakeword_models/generate_models_json.ps1` ist eine zweite,
eigenständige Manifest-Generatorimplementierung neben der kanonischen Authority:

`tools/sync_wakeword_assets.py`

Der PowerShell-Generator enthält weiterhin die durch W1B bewusst entfernte
Legacy-Semantik:

- `default_model`
- `openwakeword_models`
- Legacy-Mirror für v1
- Beschreibung „... bis AP-SRV-070“

Damit kann das Skript die kanonische `models.json` wieder in einen alten
Vertragszustand zurückschreiben.

Das ist vor W3 unzulässig, weil W3 Packaging/Distribution die Wake-Assets als
harte Produktressource qualifizieren soll. Es darf nicht zwei konkurrierende
Generator-Authorities geben.

## Verbindliche Zielentscheidung

Die eine kanonische Manifest-/Asset-Generator-Authority bleibt:

`tools/sync_wakeword_assets.py`

Der redundante PowerShell-Generator soll **gelöscht** werden, sofern die bereits
in W2 dokumentierte repo-weite Referenzprüfung bestätigt wird.

Keine zweite aktualisierte Generatorimplementierung pflegen.

Nur falls eine neue Prüfung wider Erwarten eine echte aktive, notwendige
Verwendung des PowerShell-Dateinamens nachweist:
- STATUS: BLOCKED
- nicht eigenmächtig eine zweite Generatorlogik modernisieren
- genaue Referenz dokumentieren

Nicht als Alternative einen zweiten vollwertigen Generator erhalten.

# Prüfung vor Löschung

Erneut repo-weit prüfen:

- exakter Dateiname `generate_models_json.ps1`
- mögliche PowerShell-Aufrufe
- aktive Markdown-Doku
- CI/Workflow-Dateien
- Build-/Release-Skripte
- `.bat`/`.ps1`
- Python-Tools
- Docker/Compose
- GitHub Actions

Historische `docs/.archiv/**`-Erwähnungen sind keine aktive Runtime-Abhängigkeit,
müssen aber dokumentiert werden, falls vorhanden.

Wenn keine aktive Verwendung:
Datei löschen.

# Nachweis der kanonischen Authority

Nach Löschung prüfen und dokumentieren:

1. `tools/sync_wakeword_assets.py` ist die einzige aktive Generator-Authority
   für die kanonische Wake-Asset-Manifestdatei.
2. Das aktuelle `models.json` enthält KEIN:
   - `default_model`
   - `openwakeword_models`
3. Der kanonische Generator erzeugt diese Felder ebenfalls nicht.
4. Keine aktive Quelle behauptet mehr, ein solcher Legacyspiegel werde bis
   AP-SRV-070 geführt.
5. Der aktuelle Bundle-Vertrag aus W1B/W1B-C1 bleibt unverändert:
   - eine Manifestquelle
   - kein impliziter Default
   - selected-only v2
   - per-backend Health
   - kein Runtime-Download

Wenn sinnvoll und ohne Assets unnötig neu zu formatieren:
- deterministischen Generator-/Manifest-Consistency-Check ausführen.
- Keine unbeabsichtigte Komplett-Neuserialisierung von `models.json` committen.

# W2-Abschlussprüfung

Zusätzlich kontrollieren:

- `app_talk_with_llm/install_cpu.bat` bleibt unangetastet; die W2-Evidence hat
  seine aktive Kompatibilitätsverwendung nachvollziehbar belegt.
- Keine nachträgliche Änderung historischer Archivdokumente.
- Keine W3-Packaging-Arbeit vorziehen.
- Keine Docker-/Compose-Änderung.
- Keine Release-Automation.
- `git diff --check`
- `git status --porcelain`

Da die Korrektur nur eine tote redundante Generatorquelle entfernt, ist keine
vollständige 12-Minuten-Unit-Suite zwingend, sofern keinerlei Python-/Runtimecode
geändert wird.

Mindestens:
- relevante Wake-Manifest-/Catalog-Tests
- Asset-/Generator-bezogene Tests, sofern vorhanden
- `git diff --check`

Wenn ausführbarer Code jenseits der Löschung geändert werden müsste:
volle relevante Regression entsprechend erweitern.

Calibration bleibt:
`EVIDENCE_BLOCKED / calibration pending`

# Commit / Distributed

Bei erfüllten Implementierungs-/Test-Gates genau EIN neuer Korrektur-Commit.

Parent:
`efdebc36a6cb7877197545032db074fdda43fad9`

Subject:
`chore(wakeword): remove stale manifest generator`

Danach:

- SHA/TREE erfassen
- Worktree clean
- Canonical unverändert
- Remote Distributed vor Push noch `efdebc3...`

Distributed ausschließlich per Fast-Forward aktualisieren:

`feat/einheitliche-triggerarchitektur-distributed`

Kein Force.
W2-Originalcommit nicht verändern/amenden.

# Evidence

Unter:

P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W2-C1\

mindestens:

- `2026-08-30_W2_C1_CORRECTION_REPORT.md`
- `2026-08-30_W2_C1_STATE.md`

STATE muss enthalten:

- Parent `efdebc3...`
- C1 SHA/TREE
- erneuter Reachability-/Referenznachweis
- Löschentscheidung
- kanonische Generator-Authority
- Manifest-Consistency-Nachweis
- Tests/Checks
- Distributed before/after
- Canonical unchanged
- Calibration Status
- W3 readiness

## Abschluss

Lege die Evidence vollständig unter

P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W2-C1\

ab und beende den Lauf mit einer kurzen Zusammenfassung sowie dem Hinweis,
dass der Evidence-Ordner fertig ist.
