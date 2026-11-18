# AP-SRV-070 — W2-C2 — Generator Correction Report

**Datum:** 2026-08-30
**Teilblock:** W2-C2 — Root Correction: canonical wake asset generator
reproduces the shipped dual-backend contract
**Status:** `COMPLETED`

---

## 1. Vorbedingungen (vor Mutation geprüft)

| Prüfung | Erwartung | Ist | Ergebnis |
|---|---|---|---|
| Worktree-HEAD | `07b5bc081862c9ce78c22c668d88b0710ee215e6` | identisch | ✅ |
| Worktree-TREE | `5e146147b6a2169c2b1c30836e8d7735b344eed1` | identisch | ✅ |
| Remote Distributed (`github/feat/einheitliche-triggerarchitektur-distributed`) | `07b5bc081862c9ce78c22c668d88b0710ee215e6` | identisch | ✅ |
| Worktree clean | `git status --porcelain` leer | leer | ✅ |
| Canonical (`voice-stt-server/workspaces/einheitliche-triggerarchitektur`) | `c82923fc6ce889b4dfbbde1f9877b8b76481a1e8` | identisch | ✅ |
| Canonical-Workspace clean | `git status --porcelain` leer | leer | ✅ |

Hinweis zur Canonical-Workspace-Identifikation: "Canonical" bezeichnet in
diesem Auftrag **nicht** `voice-stt-server/main` (das lokale
Hauptcheckout, HEAD `13c1629…`, unabhängige Historie), sondern
`voice-stt-server/workspaces/einheitliche-triggerarchitektur` — bestätigt
durch `AP-SRV-070_W0_DELTA_REVALIDATION.md` und alle bisherigen
W1A/W1B/W1B-C1/W2/W2-C1-STATE-Dateien, die durchgehend denselben SHA
`c82923fc…` als Canonical referenzieren. Kein Stop-Gate hat gegriffen; kein
neuer Worktree wurde angelegt.

Zusätzlich verifiziert: `origin` (lokaler Pfad-Remote auf
`voice-stt-server/main`) ist ein unabhängiger, unrelated Remote (nicht
Ancestor der `--source`-Historie); der für dieses Gate relevante Remote ist
`github`. `github/feat/einheitliche-triggerarchitektur-distributed` stand
vor Mutation exakt auf `07b5bc0…`.

---

## 2. Root Finding F1 — Generator kann Dual-Backend-Bundle nicht reproduzieren

### 2.1 Ausgangszustand (vor Korrektur)

`tools/sync_wakeword_assets.py` (Stand vor diesem Lauf):

- `BUNDLED_FRAMEWORK = "onnx"` — liest ausschließlich
  `openwakeword_models.onnx_models`
- erzeugt nur `"pipeline": {"onnx": {...}}`
- schreibt `"catalogRevision": 1` fest (Konstante im Code)
- kennt `tflite_models` und `silero_vad_onnx` nicht

Committetes Ist-Bundle (`VoiceSTT/assets/wakeword_models/models.json`,
unverändert von diesem Lauf):

- 25 Wake Words, je mit `artifacts.onnx` UND `artifacts.tflite`
- `"pipeline": {"onnx": {...}, "tflite": {...}}`
- `"catalogRevision": 2`
- kein Verweis auf `silero_vad.onnx` (siehe F2)

Baseline-Lauf vor Korrektur:

```
python tools/sync_wakeword_assets.py --source S:/MODELS/openwakeword/resources/models/all_models --check
```

Ergebnis: `models.json differs`, **Exit 1** — reproduziert exakt den in
W2-C1 dokumentierten bekannten Fehler.

### 2.2 Reale Upstream-Struktur (vor Implementierung verifiziert, nicht vermutet)

Quelle: `S:\MODELS\openwakeword\resources\models\all_models\models.json`
(Stand dieses Laufs, Datei-Zeitstempel 2026-08-28 18:50).

```json
{
  "openwakeword_models": {
    "path": ".",
    "default_model": "alexa",
    "pipeline_models": {
      "embedding_model_onnx": "embedding_model.onnx",
      "melspectrogram_onnx": "melspectrogram.onnx",
      "embedding_model_tflite": "embedding_model.tflite",
      "melspectrogram_tflite": "melspectrogram.tflite",
      "silero_vad_onnx": "silero_vad.onnx"
    },
    "onnx_models": { "...25 Einträge..." },
    "tflite_models": { "...25 Einträge, identische Schlüssel wie onnx_models..." }
  }
}
```

Verifiziert:

- `onnx_models`: 25 Einträge
- `tflite_models`: 25 Einträge
- `set(onnx_models.keys()) == set(tflite_models.keys())`: **wahr** — jedes
  öffentlich manifestierte Wake Word hat upstream ein vollständiges
  ONNX/TFLite-Paar
- `pipeline_models` enthält sowohl die ONNX- als auch die TFLite-Variante
  von `melspectrogram`/`embedding_model`, zusätzlich `silero_vad_onnx`
- Upstream-Verzeichnis enthält physisch weitere, vom Quellmanifest **nicht
  referenzierte** Dateien (`Jarvis.onnx`, `jarvis_v1.onnx`,
  `hey_jarvis_v0.1.onnx` + zugehörige `.tflite`, `wake_word_hey_rona.onnx`,
  ein Legacy-`generate_models_json.ps1`) — bewusst außerhalb des
  Generator-Vertrags, wie schon in AP-SRV-060 dokumentiert (siehe §4).

### 2.3 Mapping-Dokumentation (Vorgabe des Prompts)

| Kategorie | Quelle | Ziel |
|---|---|---|
| ONNX classifier | `openwakeword_models.onnx_models[<raw_id>]` | `wakeWords[].artifacts.onnx` |
| TFLite classifier | `openwakeword_models.tflite_models[<raw_id>]` | `wakeWords[].artifacts.tflite` |
| ONNX pipeline | `pipeline_models.{melspectrogram_onnx,embedding_model_onnx}` | `pipeline.onnx.{melspectrogram,embedding}` |
| TFLite pipeline | `pipeline_models.{melspectrogram_tflite,embedding_model_tflite}` | `pipeline.tflite.{melspectrogram,embedding}` |
| VAD/Auxiliary | `pipeline_models.silero_vad_onnx` | Sync-/Check-Dateiliste (kein Manifestfeld, siehe F2) |

Der Wake-Word-Identifier ist in beiden Frameworks derselbe Rohschlüssel
(z. B. `"Hey_Alfred"` in `onnx_models` UND `tflite_models`); die Zuordnung
erfolgt über `canonical_id()`, nicht über eine Heuristik oder eine
angenommene Dateinamenskonvention.

### 2.4 Korrektur

`tools/sync_wakeword_assets.py`:

- `BUNDLED_FRAMEWORK = "onnx"` → `BUNDLED_FRAMEWORKS = ("onnx", "tflite")`
- `build_manifest()` liest jetzt `onnx_models` UND `tflite_models`, indiziert
  beide über `canonical_id()`, und **verlangt** für jede resultierende ID ein
  vollständiges Paar. Fehlt ein Backend für einen Eintrag, wirft die
  Funktion `SystemExit` mit der betroffenen ID und dem fehlenden Backend —
  kein stilles Downgrade auf ein einzelnes Backend (Prompt-Vorgabe F1
  wörtlich umgesetzt; durch Test abgesichert, siehe Test-Report).
- Pipeline-Erzeugung läuft jetzt über beide Frameworks in einer Schleife und
  erzeugt `"pipeline": {"onnx": {...}, "tflite": {...}}`.
- `catalogRevision`: hardcodierte `1` ersetzt durch die neue
  Modulkonstante `CATALOG_REVISION = 2` — eine source-controlled
  Generator-Konstante, die **nicht** aus der vorher generierten Zieldatei
  gelesen wird (siehe eigener Test `test_catalog_revision_does_not_read_the_previously_generated_target`,
  der `TARGET` bewusst auf ein Verzeichnis mit einem *anderen*
  `catalogRevision`-Wert zeigen lässt und beweist, dass die Ausgabe davon
  unbeeinflusst bleibt).
- Keine zweite Generatorimplementierung: ausschließlich
  `tools/sync_wakeword_assets.py` wurde geändert, keine neue Datei mit
  Generator-Logik angelegt.
- Keine `openwakeword_models`-Legacyausgabe: strukturell geprüft (Test
  `test_no_legacy_v1_fields`), dass weder `default_model` noch
  `openwakeword_models` im erzeugten Manifest-Objekt vorkommen (nicht nur im
  gerenderten Text — die `description` erwähnt den String
  `'openwakeword_models'` legitim als Prosa, dazu unten mehr).

### 2.5 Serialisierungsauthority (notwendige Zusatzkorrektur)

Nach der reinen Dual-Backend-Korrektur blieb `--check` weiterhin bei
`models.json differs`, obwohl der Dateninhalt inhaltlich bereits
übereinstimmte. Ursache, per Byte-Diff isoliert: das committete
`models.json` rendert Skalar-Arrays (`"aliases"`) **kompakt einzeilig**
(`"aliases": ["alfred"]`), während `json.dumps(..., indent=2)` jedes
Array-Element auf eine eigene Zeile setzt. Das committete Manifest wurde
also nie durch reines `json.dumps(indent=2)` erzeugt.

Lösung: eine dedizierte `render_manifest()`-Funktion, die wie
`indent=2` einrückt, aber Arrays aus ausschließlich skalaren Werten
(`str`/`int`/`float`/`bool`/`None`) einzeilig rendert und Arrays aus
Objekten (`wakeWords` selbst) normal mehrzeilig expandiert. Das ist die im
Prompt geforderte "bewusst festgelegte Serialisierungsauthority" — explizit
im Code dokumentiert, nicht implizit von einer Bibliotheksvoreinstellung
abhängig.

Mit dieser Funktion ist das frisch generierte Manifest **byte-identisch**
zum committeten Git-Blob (siehe §3, Scratch-Reproduction Proof).

---

## 3. Root Finding F2 — silero_vad.onnx Provenienz und Verwaltung

### 3.1 Herkunftsnachweis (nicht erfunden, belastbar geprüft)

1. **Woher stammt `silero_vad.onnx`?**
   Aus derselben `--source`-Authority wie alle anderen Assets:
   `S:\MODELS\openwakeword\resources\models\all_models\silero_vad.onnx`,
   referenziert im Quellmanifest unter
   `openwakeword_models.pipeline_models.silero_vad_onnx`.

2. **Ist es eine produktiv erforderliche Wake-/OpenWakeWord-Ressource?**
   Ja. Es ist exakt die Datei, die die Upstream-Bibliothek `openwakeword`
   für ihr optionales VAD-Gating (`openwakeword.VAD`, aktiviert über
   `Model(vad_threshold=...)`) standardmäßig aus ihrem **eigenen**
   Package-Verzeichnis lädt
   (`site-packages/openwakeword/resources/models/silero_vad.onnx`).
   Byte-für-Byte-Vergleich (SHA-256
   `a35ebf52fd3ce5f1469b2a36158dba761bc47b973ea3382b3186ca15b1f5af28`,
   1 807 522 Bytes) bestätigt: committete Bundle-Datei, `--source`-Datei und
   die im installierten `openwakeword`-Package mitgelieferte Datei sind
   identisch. `VoiceSTT/core/openwakeword_engine.py` reicht
   `vad_threshold` an genau diesen Upstream-`Model`-Konstruktor durch
   (`api_fastapi_server` → `OpenWakeWordEngine.__init__` →
   `loader_kwargs["vad_threshold"]`).

3. **Welche Upstream-/Source-Authority besitzt es?**
   Dieselbe `--source`-Authority wie der gesamte übrige Wake-Bestand — kein
   getrenntes, zusätzliches Quellsystem.

4. **Kann es aus derselben `--source`-Authority deterministisch bezogen
   werden?** Ja — über `pipeline_models.silero_vad_onnx`.

Historische Einordnung: In AP-SRV-060 (Erstimplementierung) wurde
`silero_vad.onnx` **bewusst nicht** gebündelt
(`docs/.archiv/.../01_IMPLEMENTATION/evidence/2026-08-27_README.md`:
„`silero_vad.onnx` (kein Wake-Word-Artefakt)“ explizit als **nicht**
übernommen dokumentiert). Die Datei wurde erst später, mit Commit
`abf8e6207d0019018f55ce4dcf57f81328c4cb5a`
(`fix: complete tflite asset manifest and packaging`, 2026-08-28, Teil der
bereits vor W2-C1 committeten Historie) zusammen mit den TFLite-Artefakten
und der `catalogRevision`-Anhebung auf `2` physisch dem Bundle-Verzeichnis
hinzugefügt — aber **ohne** Anbindung an Manifest oder Generator. Das ist
exakt der in F2 beschriebene Root-Zustand: eine physisch ausgelieferte,
aber unverwaltete Zusatzressource. `setup.py`s `package_data`-Glob
(`assets/wakeword_models/*.onnx`) nimmt sie unabhängig vom Generator ins
Wheel/Sdist auf — das Bundle liefert sie also faktisch bereits produktiv
aus, ohne dass ein Werkzeug ihre Integrität deterministisch prüft.

**Wichtig für die Einordnung:** `VoiceSTT/core/silero_vad.py`s
`find_silero_model_file()` (genutzt vom *server-seitigen*
Silero-VAD-Utterance-Gating, unabhängig von OpenWakeWord) sucht
ausschließlich im installierten `silero_vad`-Pip-Package bzw. im
Torch-Hub-Cache — **nicht** unter
`VoiceSTT/assets/wakeword_models/`. Die dort liegende Kopie wird also
aktuell von keinem Python-Pfad im Repository per explizitem Pfad
konsumiert; sie ist ein reines Build-Asset. Das ändert nichts an ihrer
Provenienz-Legitimität (§3.1, Punkt 2), begrenzt aber den Handlungsbedarf
dieses Laufs: keine Laufzeitverdrahtung, da das Scope diesen Lauf
ausdrücklich auf Generator/Sync beschränkt (kein Wake-Runtime-Redesign).

### 3.2 Verwaltungsentscheidung

`AUXILIARY_ASSETS = {"vad": "silero_vad_onnx"}` in
`tools/sync_wakeword_assets.py`: die Datei wird beim vollen Sync-Lauf
kopiert und bei `--check` byte-genau gegen die Quelle geprüft — exakt wie
jedes andere Bundle-Artefakt (`files`-Dict, dieselbe Kopier-/Prüflogik).

**Bewusst keine neue Manifest-Semantik:** Das committete `models.json`
enthält aktuell **kein** Feld für `silero_vad.onnx`. Eine neue
JSON-Sektion (`"auxiliary": {...}` o. ä.) einzuführen wäre eine
Vertragserweiterung außerhalb des eingefrorenen SRV-060-Manifest-Vertrags
und laut Scope dieses Laufs nicht erlaubt, ohne dass eine solche Erweiterung
"zwingend" nachgewiesen wäre. Da der Datei aktuell auch keine per Pfad
adressierte Laufzeitrolle zukommt (§3.1), gibt es keinen belegten Zwang für
eine Manifesterweiterung — "geprüft/verwaltet" (Hard-Gate-Punkt 7) wird
durch die Sync-/Check-Dateiliste vollständig erfüllt, ohne das
Manifestschema anzufassen. Ein Test (`test_vad_asset_does_not_introduce_new_manifest_semantics`)
sichert das explizit ab.

---

## 4. Root Finding F3 — veraltete aktive Dokumentation

`docs/wake-words.md` behauptete (Zeile 55, vor Korrektur):

> "Only ONNX artifacts are bundled, so the v2 catalog resolves ONNX."

Das widersprach sowohl dem tatsächlichen Bundle-Inhalt als auch dem im
selben Dokument weiter unten beschriebenen `auto`/`onnx`/`tflite`-Vertrag
(`wakeWord.inferenceBackend`). Minimalkorrektur (eine Textstelle, kein
größerer Doku-Durchlauf):

> "Both ONNX and TFLite artifacts are bundled for every publicly manifested
> wake word and pipeline component, so the v2 catalog resolves
> `auto`/`onnx`/`tflite` (see `wakeWord.inferenceBackend` below)."

Keine weiteren Stellen in `docs/wake-words.md` wurden verändert (die
bekannte separate Ungenauigkeit „26 wake-word classifiers" im ASCII-Baum
weiter oben im selben Dokument ist nicht Gegenstand von F3 und wurde nicht
angefasst, um keine größere W2-Doku-Runde auszulösen).

---

## 5. Reproduzierbarkeits-Hard-Gate — Nachweis Punkt für Punkt

1. **`--check` gegen unveränderten committeten Bundle-Stand: Exit 0.**
   ```
   python tools/sync_wakeword_assets.py --source S:/MODELS/openwakeword/resources/models/all_models --check
   ```
   → Exit 0, keine Ausgabe auf stderr.

2. **Scratch-Reproduction Proof (bytegleich/semantisch exakt):**
   Frischer Lauf in ein isoliertes Scratch-Zielverzeichnis (außerhalb des
   Repos) erzeugt 55 Artefakte, 33 244 477 Bytes. `models.json` daraus hat
   SHA-256 `f2829a79b4b1849398fa9ea7789befafc4491e16adabe2f1d139ae235f063f3b`
   — identisch zum SHA-256 des committeten Git-Blobs
   (`git show HEAD:VoiceSTT/assets/wakeword_models/models.json`). Die
   einzige beobachtete Rohbyte-Abweichung zur **Arbeitskopie** im Worktree
   ist CRLF vs. LF (Windows-Checkout mit `core.autocrlf=true`,
   `.gitattributes: * text=auto`); nach Zeilenenden-Normalisierung sind
   beide Inhalte identisch, und `--check` selbst ist davon nicht betroffen,
   da `pathlib.Path.read_text()` beim Lesen bereits Universal-Newlines
   anwendet (mit dem echten CLI-Lauf in Punkt 1 verifiziert, nicht nur
   angenommen).

3. **ONNX-Classifier vollständig:** 25/25 Einträge, je mit `artifacts.onnx`.

4. **TFLite-Classifier vollständig:** 25/25 Einträge, je mit
   `artifacts.tflite`.

5. **ONNX-Pipeline vollständig:** `pipeline.onnx.{melspectrogram,embedding}`
   vorhanden und SHA-256-verifiziert.

6. **TFLite-Pipeline vollständig:**
   `pipeline.tflite.{melspectrogram,embedding}` vorhanden und
   SHA-256-verifiziert.

7. **SHA256/Bytes stimmen:** Für alle 55 vom Generator verwalteten Dateien
   (50 Classifier-Artefakte, 4 Pipeline-Artefakte, 1 VAD-Artefakt) per
   Skript verifiziert — keine Abweichung.

8. **VAD-/Auxiliary-Asset deterministisch geprüft/verwaltet:**
   `silero_vad.onnx` ist Teil der `files`-Dateiliste, wird bei `--check`
   byte-geprüft und bei einem vollen Sync-Lauf kopiert (§3.2).

9. **Keine Legacy-Felder:** `default_model` und `openwakeword_models` als
   JSON-Schlüssel strukturell nicht vorhanden (Test
   `test_no_legacy_v1_fields`; die `description`-Prosa erwähnt den String
   `'openwakeword_models'`, ist aber kein Schlüssel und kein Legacy-Feld).

10. **Keine Runtime-Downloads:** Der Generator liest ausschließlich aus dem
    lokalen `--source`-Pfad, keine Netzwerkzugriffe im Code.

11. **`--check` schreibt nichts:** durch `git status --porcelain` nach dem
    finalen `--check`-Lauf bestätigt (leer) sowie durch Unit-Test
    `test_check_writes_nothing` (Zielverzeichnis bleibt leer).

Das committete `models.json` selbst wurde durch diesen Lauf **nicht**
verändert — die Korrektur lag ausschließlich im Generator; kein
Massendiff, keine Reformatierung des Manifests.

---

## 6. Nicht angefasst / bestätigt unverändert

- `VoiceSTT/assets/wakeword_models/models.json` — kein Byte geändert.
- `VoiceSTT/assets/wakeword_models/*.onnx`, `*.tflite`, `silero_vad.onnx` —
  keine Datei geändert oder gelöscht.
- Die vom Quellmanifest nicht referenzierten Duplikate (`Jarvis.onnx`,
  `jarvis_v1.onnx`, `hey_jarvis_v0.1.onnx` + `.tflite`,
  `wake_word_hey_rona.onnx`) — unangetastet, wie schon vor diesem Lauf vom
  Generator nicht verwaltet.
- `setup.py`, `MANIFEST.in`, Docker/Compose, Release-Automation — nicht
  angefasst (Scope-Ausschluss).
- `VoiceSTT/core/wakeword_catalog.py`, `openwakeword_engine.py`,
  `silero_vad.py`, `api_fastapi_server/server.py` — kein Laufzeit-/
  Domänenmodul verändert.
- `docs/wake-words.md` — genau eine Textstelle korrigiert, keine größere
  Doku-Runde.
