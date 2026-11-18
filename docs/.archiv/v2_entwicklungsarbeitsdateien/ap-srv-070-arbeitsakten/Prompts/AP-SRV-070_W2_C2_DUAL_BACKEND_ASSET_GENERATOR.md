# AP-SRV-070 — W2-C2
# Root Correction — Make canonical wake asset generator reproduce the shipped dual-backend contract

## Ausgangslage

W2:
efdebc36a6cb7877197545032db074fdda43fad9

W2-C1:
07b5bc081862c9ce78c22c668d88b0710ee215e6

W2-C1 TREE:
5e146147b6a2169c2b1c30836e8d7735b344eed1

W2-C1 hat den redundanten Legacy-Generator
`VoiceSTT/assets/wakeword_models/generate_models_json.ps1`
korrekt entfernt.

Dabei wurde ein neuer Root-Befund sichtbar:

Die jetzt einzige Generator-Authority

`tools/sync_wakeword_assets.py`

kann das tatsächlich ausgelieferte Wake-Asset-Bundle nicht reproduzieren.

Dieser Befund ist vor W3 zu schließen.

---

## Git / Worktree

Weiterverwenden:

Branch:
work/AP-SRV-070

Worktree:
P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070

Vor Mutation:

- HEAD == `07b5bc081862c9ce78c22c668d88b0710ee215e6`
- Remote Distributed == derselbe SHA
- Worktree clean
- Canonical ==
  `c82923fc6ce889b4dfbbde1f9877b8b76481a1e8`
- Canonical-Workspace clean

Sonst:
STATUS: BLOCKED

Kein neuer Worktree.
Kein Amend.
Kein Force-Push.

---

# ROOT FINDING F1 — canonical generator is not reproducible for shipped bundle

Aktueller Zustand:

`tools/sync_wakeword_assets.py`:

- setzt `BUNDLED_FRAMEWORK = "onnx"`
- liest nur `onnx_models`
- erzeugt nur `pipeline.onnx`
- beschreibt TFLite ausdrücklich als nicht gebündelt
- schreibt `catalogRevision` fest auf `1`

Das tatsächlich committete Produktbundle enthält dagegen:

- ONNX Wake-Classifier
- TFLite Wake-Classifier
- `pipeline.onnx`
- `pipeline.tflite`
- `catalogRevision = 2`

W2-C1 hat deshalb mit dem kanonischen Prüfmodus erhalten:

`models.json differs`

Dieser bekannte Fehler darf nach W2-C2 nicht mehr bestehen.

---

# ROOT FINDING F2 — required auxiliary wake asset authority

Im produktiven Wake-Asset-Verzeichnis liegt zusätzlich:

`silero_vad.onnx`

W3 führt dieses VAD-Asset als Distribution-Hard-Gate.

Der aktuelle Generator verwaltet es nicht.

W2-C2 muss deshalb zunächst den realen fachlichen Vertrag feststellen:

1. Woher stammt `silero_vad.onnx`?
2. Ist es eine produktiv erforderliche Wake-/OpenWakeWord-Ressource?
3. Welche Upstream-/Source-Authority besitzt es?
4. Kann es aus derselben `--source`-Authority deterministisch bezogen werden?

Wenn ja:
- als explizit verwaltetes Auxiliary Asset in die kanonische Sync-/Check-Logik
  aufnehmen.

Wenn es aus einer anderen belegten Authority stammt:
- diese explizit und deterministisch modellieren;
- keinen stillen Directory-Scan einführen.

Nicht einfach ignorieren, solange W3 es als Pflichtasset verteilen soll.

Keine erfundene Herkunft.

Falls die Provenienz nicht belastbar auflösbar ist:
STATUS: BLOCKED mit genauer Evidence.

---

# ROOT FINDING F3 — stale active documentation

`docs/wake-words.md` behauptet aktuell sinngemäß:

`Only ONNX artifacts are bundled, so the v2 catalog resolves ONNX.`

Das ist gegenüber dem tatsächlichen Bundle und dem bereits dokumentierten
`auto`/`onnx`/`tflite`-Vertrag falsch.

Nach erfolgreicher Generator-Korrektur diese aktive Doku minimal auf den
tatsächlichen Dual-Backend-Vertrag korrigieren.

Keine größere W2-Doku-Runde wiederholen.

---

# Verbindlicher Generator-Vertrag

Nach W2-C2 gilt:

## Eine Authority

`tools/sync_wakeword_assets.py`

ist die einzige aktive Generator-/Sync-Authority.

Keine zweite Generatorimplementierung anlegen.

## Dual Backend

Der Generator muss den vom Upstream tatsächlich angebotenen und vom Produkt
freigegebenen ONNX- UND TFLite-Satz deterministisch abbilden.

Für jedes öffentlich manifestierte Wake Word gilt der eingefrorene
SRV-060-Vertrag:

- ONNX und TFLite entsprechend dem tatsächlich freigegebenen Bundle
- keine heuristisch erfundenen IDs/Aliase
- keine impliziten Defaults
- keine `openwakeword_models`-Legacyausgabe
- gemeinsame Pipeline-Ressourcen je Backend
- keine Runtime-Downloads

Wenn der Upstream für einen als Dual-Backend erwarteten öffentlichen Eintrag
nur ein Format liefert:
nicht still degradieren; klarer Generator-/Sync-Fehler.

## Upstream-Struktur zuerst verifizieren

Vor Implementierung die reale lokale Source-Authority prüfen, insbesondere:

`S:\MODELS\openwakeword\resources\models\all_models\models.json`

bzw. den tatsächlich per `--source` übergebenen Pfad.

Nicht aus Vermutung codieren.

Dokumentieren:
- ONNX classifier mapping
- TFLite classifier mapping
- ONNX pipeline mapping
- TFLite pipeline mapping
- VAD-/Auxiliary-Asset-Herkunft

## catalogRevision

Der Generator darf für einen reproduzierbaren Neuaufbau nicht vom bereits
generierten Ziel-`models.json` abhängig sein.

`catalogRevision` muss aus einer expliziten, source-controlled Authority kommen,
z. B. einer klar benannten Generator-Konstante oder gleichwertigen
deterministischen Konfiguration.

Für den aktuellen freigegebenen Bundlevertrag muss die erzeugte Revision exakt
dem committed Soll entsprechen.

Kein "lies die alte Zieldatei und übernimm den Wert"-Trick als alleinige
Authority.

---

# Reproduzierbarkeits-Hard-Gate

Der entscheidende Test dieses Laufs:

Von der belegten Source-Authority aus muss

`python tools/sync_wakeword_assets.py --source <SOURCE> --check`

gegen den unveränderten committed Bundle-Stand mit:

EXIT 0

enden.

Kein akzeptiertes `models.json differs`.

Zusätzlich muss bewiesen werden:

1. frisch in ein Scratch-Ziel generiertes `models.json` ist bytegleich oder
   semantisch exakt entsprechend der bewusst festgelegten
   Serialisierungsauthority zum committed Manifest;
2. ONNX-Classifier vollständig;
3. TFLite-Classifier vollständig;
4. ONNX-Pipeline vollständig;
5. TFLite-Pipeline vollständig;
6. SHA256/Bytes stimmen;
7. erforderliches VAD-/Auxiliary-Asset wird deterministisch geprüft/verwaltet;
8. keine Legacy-Felder:
   - `default_model`
   - `openwakeword_models`
9. keine Runtime-Downloads;
10. `--check` schreibt nichts.

Das echte committed `models.json` nur ändern, wenn die Korrektur der
Generator-Authority zwingend eine sachlich richtige, kontrollierte
Manifestkorrektur erfordert.

Keine unnötige Reformatierung oder Massendiffs.

---

# Tests

Mindestens:

- neue/erweiterte Unit-Tests für `tools/sync_wakeword_assets.py`
- Dual-Backend-Manifestgeneration
- fehlendes ONNX/TFLite-Paar -> deterministischer Fehler
- Pipeline beider Backends
- catalogRevision
- Legacy-Felder absent
- `--check` PASS gegen aktuellen Bundle-Stand
- VAD-/Auxiliary-Asset-Vertrag
- relevante Wake Catalog/API/Backend Tests
- `test_server_operations.py`
- `git diff --check`

Da Generatorcode geändert wird, mindestens die gesamten direkt relevanten
Wake-Suiten aus W2-C1 erneut ausführen.

Volle Unit-Suite ist nur dann zwingend, wenn Runtime-/Domänencode verändert
werden muss. Das sollte für diesen Auftrag nicht nötig sein.

---

# Scope

Erlaubt:

- `tools/sync_wakeword_assets.py`
- direkt zugehörige Tests
- minimale Korrektur von `docs/wake-words.md`
- falls zwingend: source-controlled Generator-Metadaten/Policy-Datei
- nur bei belegter Notwendigkeit eine kontrollierte Manifest-Metadatenkorrektur

Nicht erlaubt:

- Packaging/W3
- Docker/Compose
- Kroko
- Release-Automation
- Client
- Wake Runtime Redesign
- neue Manifest-Semantik außerhalb des bestehenden SRV-060-Vertrags

---

# Calibration

Unverändert:

`EVIDENCE_BLOCKED / calibration pending`

Generator-/Asset-Reproduzierbarkeit ist keine reale Wake-Audio-Kalibrierung.

---

# Commit / Distributed

Bei erfüllten Gates genau EIN Korrektur-Commit.

Parent:

`07b5bc081862c9ce78c22c668d88b0710ee215e6`

Subject:

`fix(wakeword): make asset sync reproduce dual backends`

Danach:

- SHA/TREE erfassen
- Worktree clean
- Canonical unverändert
- Remote Distributed vor Push weiterhin `07b5bc0...`

Distributed ausschließlich Fast-Forward:

`feat/einheitliche-triggerarchitektur-distributed`

Kein Force.
Vorherige W2-/C1-Commits nicht verändern.

---

# Evidence

Unter:

P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W2-C2\

mindestens:

- `2026-08-30_W2_C2_GENERATOR_REPORT.md`
- `2026-08-30_W2_C2_TEST_REPORT.md`
- `2026-08-30_W2_C2_STATE.md`

STATE muss enthalten:

- Parent `07b5bc0...`
- C2 SHA/TREE
- reale Upstream-Struktur
- ONNX/TFLite Source Mapping
- VAD-/Auxiliary-Provenienz
- catalogRevision-Authority
- `--check` vor Korrektur
- `--check` nach Korrektur
- Scratch-Reproduction Proof
- Tests
- Distributed before/after
- Canonical unchanged
- Calibration Status
- W3 readiness

## Abschluss

Lege die Evidence vollständig unter

P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W2-C2\

ab und beende den Lauf mit einer kurzen Zusammenfassung sowie dem Hinweis,
dass der Evidence-Ordner fertig ist.
