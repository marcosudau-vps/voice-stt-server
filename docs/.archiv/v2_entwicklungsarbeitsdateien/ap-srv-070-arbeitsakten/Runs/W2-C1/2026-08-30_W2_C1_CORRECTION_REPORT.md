# AP-SRV-070 — W2-C1 CORRECTION REPORT

**Datum:** 2026-08-30
**Teilblock:** W2-C1 — Root Correction: Remove stale duplicate Wake Manifest Generator
**Prompt-Datei:** `_workflow-tools/AP-SRV-070/Prompts/AP-SRV-070_W2_C1_REMOVE_STALE_WAKE_GENERATOR.md`
**Parent:** `efdebc36a6cb7877197545032db074fdda43fad9` (W2)

---

## 1. Ausgangslage geprüft

Vor jeder Mutation geprüft und bestätigt:

| Bedingung | Ergebnis |
|---|---|
| Worktree-HEAD == `efdebc36a6cb7877197545032db074fdda43fad9` | ✅ bestätigt |
| Remote `github/feat/einheitliche-triggerarchitektur-distributed` == `efdebc36a6cb7877197545032db074fdda43fad9` | ✅ bestätigt |
| Worktree clean | ✅ `git status --porcelain` leer |
| Canonical == `c82923fc6ce889b4dfbbde1f9877b8b76481a1e8` | ✅ bestätigt |
| Canonical-Workspace clean | ✅ `git status --porcelain` leer |

Kein Stop-Gate hat gegriffen. Derselbe bestehende Worktree/Branch wurde
weiterverwendet, kein neuer Worktree angelegt.

## 2. Erneute Reachability-Prüfung F1

Repo-weite Suche nach exakt `generate_models_json.ps1` (case-insensitiv),
sowie gezielt nach den Prüfpunkten des Prompts:

| Prüfpunkt | Ergebnis |
|---|---|
| Exakter Dateiname, repo-weit | **1 Treffer**, ausschließlich unter `docs/.archiv/einheitliche_triggerarchitektur/AP-SRV-060/runs/01_IMPLEMENTATION/evidence/2026-08-27_README.md:91` |
| PowerShell-Aufrufe (`.ps1`-Inventar: alle 4 verbleibenden Skripte geprüft) | keiner der drei anderen `.ps1`-Dateien (`activate_venv_install_reqs.ps1`, `install_windows_cpu.ps1`, `tools/verify_session_wakeword.ps1`) ruft die Datei auf |
| Aktive Markdown-Doku (außerhalb `.archiv`) | keine Erwähnung |
| CI/Workflow-Dateien | kein `.github`-Verzeichnis im Repository vorhanden — keine GitHub Actions |
| Build-/Release-Skripte | `setup.py` geprüft: `package_data`-Globs (`assets/wakeword_models/models.json`, `*.onnx`, `*.tflite`) greifen dateiendungsbasiert, referenzieren das Skript nicht |
| `.bat`-Dateien | keine Erwähnung |
| Python-Tools | keine Erwähnung, kein `subprocess`/`os.system`-Aufruf irgendwo im Repo |
| Docker/Compose | `Dockerfile`, `docker-compose*.yml` geprüft: keine Erwähnung |
| GitHub Actions | entfällt (kein `.github`) |

**Der einzige Treffer** liegt unter `docs/.archiv/**` und ist historisch: Das
Dokument listet `generate_models_json.ps1` explizit unter den beim
AP-SRV-060-Bundle-Aufbau **bewusst nicht übernommenen** Dateien ("Bewusst
**nicht** übernommen: … sowie `generate_models_json.ps1`."). Das bestätigt
zusätzlich, dass das Skript schon zum historischen Zeitpunkt nicht Teil des
kanonischen Workflows war. Keine aktive Runtime-Abhängigkeit gefunden;
gemäß Prompt dokumentiert, kein Stop-Gate.

**Ergebnis:** Keine aktive, notwendige Verwendung nachweisbar. Löschung wie
im Prompt vorgesehen durchgeführt.

## 3. Löschung

```
git rm VoiceSTT/assets/wakeword_models/generate_models_json.ps1
```

Einzige Änderung im Commit: 1 Datei gelöscht, 206 Zeilen entfernt. Keine
weitere Datei berührt.

## 4. Nachweis der kanonischen Authority

1. **`tools/sync_wakeword_assets.py` ist die einzige verbleibende
   Generator-Skriptdatei** für die kanonische Wake-Asset-Manifestdatei; nach
   der Löschung existiert keine zweite Implementierung mehr im Repository.
2. **Aktuelles `models.json` enthält kein `default_model`- und kein
   `openwakeword_models`-Feld** — verifiziert per
   `python -c "import json; print(list(json.load(open(...)).keys()))"`:
   Top-Level-Schlüssel sind ausschließlich `manifestVersion`,
   `catalogRevision`, `generatedBy`, `description`, `pipeline`, `wakeWords`.
   Das Wort „openwakeword_models" kommt nur noch als **Prosa** im
   `description`-Freitext vor (erklärt, dass der frühere Spiegel entfernt
   wurde) — kein tatsächliches JSON-Feld.
3. **Der kanonische Generator erzeugt diese Felder ebenfalls nicht** —
   verifiziert per Quellcodelesung von `tools/sync_wakeword_assets.py::build_manifest()`:
   die zurückgegebene Manifeststruktur enthält ausschließlich
   `manifestVersion`, `catalogRevision`, `generatedBy`, `description`,
   `pipeline`, `wakeWords`. `upstream["openwakeword_models"]` (Zeile 92) ist
   ausschließlich ein **Lesezugriff auf das fremde Upstream-Quellmanifest**
   (`S:/MODELS/openwakeword/resources/models/all_models/models.json`), nicht
   auf die Ausgabe — das Skript spiegelt dieses Upstream-Feld nicht in seine
   eigene, kanonische Ausgabe.
4. **Keine aktive Quelle behauptet mehr, ein Legacyspiegel werde „bis
   AP-SRV-070" geführt** — repo-weite Suche nach `bis AP-SRV-070` (Nachlauf
   zur W2-Korrektur) ergab nach dieser Löschung **null** Treffer außerhalb
   `docs/.archiv/**`. Die einzige verbliebene Quelle dieser Formulierung war
   exakt das jetzt gelöschte Skript (`generate_models_json.ps1:192`).
5. **Bundle-Vertrag aus W1B/W1B-C1 unverändert:** Es wurde in diesem Lauf
   **keine** Zeile in `models.json`, `wakeword_catalog.py`, `operations.py`
   oder einem anderen Runtime-/Domänenmodul geändert. Eine Manifestquelle,
   kein impliziter Default, selected-only v2, per-backend Health, kein
   Runtime-Download bleiben exakt wie in W1B-C1 abgenommen.

## 5. Deterministischer Manifest-Consistency-Check und wichtiger Zusatzbefund

Zur Verifikation wurde `tools/sync_wakeword_assets.py --source
S:/MODELS/openwakeword/resources/models/all_models --check` gegen das
committete Bundle ausgeführt (nur Prüfung, kein Schreibzugriff):

```
models.json differs
```

**Dieser Befund wurde untersucht, statt ihn zu ignorieren.** Ein manueller
Diff der vom Generator tatsächlich erzeugten Struktur gegen das committete
`models.json` (in einem Scratch-Verzeichnis, `models.json` im Repo dabei
nicht verändert) zeigte zwei Ursachen:

1. **`catalogRevision`**: committet `2`, frisch generiert `1`. Der
   Python-Generator schreibt `catalogRevision` immer fest als `1`
   (`tools/sync_wakeword_assets.py:138`); eine tatsächliche
   Revisionserhöhung ist ein bewusster redaktioneller Schritt außerhalb des
   Generators, keine Regression.
2. **Alle TFLite-Artefakte fehlen in der frisch generierten Ausgabe.** Das
   committete `models.json` enthält für jedes Wake-Word sowohl `onnx`- als
   auch `tflite`-Artefakteinträge sowie einen `pipeline.tflite`-Abschnitt;
   im Bundle-Verzeichnis liegen tatsächlich 31 `.onnx`- und 30
   `.tflite`-Dateien. `tools/sync_wakeword_assets.py` bündelt jedoch
   ausschließlich ONNX (`BUNDLED_FRAMEWORK = "onnx"`, mit explizitem
   Kommentar, TFLite werde „deliberately not bundled"). **Der aktuell
   kanonische Python-Generator kann das tatsächlich committete,
   TFLite-haltige Bundle nicht reproduzieren.**

Der Inhalt des soeben gelöschten `generate_models_json.ps1` (vor Löschung
per `git show HEAD:...` geprüft) scannt dagegen sowohl `.onnx`- als auch
`.tflite`-Dateien im lokalen Ordner (Verzeichnis-Scan, nicht
quellbasiert) und erzeugt genau diese Dual-Format-Struktur — inklusive der
Übernahme einer vorhandenen `catalogRevision` aus der bestehenden Datei.
Das legt nahe, dass das jetzt gelöschte Skript (oder ein manueller Prozess
mit derselben Logik) historisch für die TFLite-Erweiterung des Bundles
verantwortlich war, bevor `tools/sync_wakeword_assets.py` als alleinige
Authority etabliert wurde.

**Bewertung und Entscheidung:**
- Dieser Befund ändert **nichts** an der F1-Löschentscheidung: Das gelöschte
  Skript bleibt wegen der reaktivierbaren Legacy-Semantik (`default_model`,
  `openwakeword_models`, Verzeichnis-Scan statt Quellsystem) unzulässig als
  Generator-Authority, unabhängig davon, ob es historisch auch valide
  TFLite-Daten erzeugt hat.
- **`models.json` wurde in diesem Lauf bewusst nicht neu generiert oder
  überschrieben.** Ein Lauf von `sync_wakeword_assets.py` ohne `--check`
  hätte alle 30 TFLite-Artefakteinträge aus dem Manifest entfernt — eine
  unbeabsichtigte, funktionale Regression des Dual-Backend-Vertrags
  (`wakeWord.inferenceBackend`: `auto`/`onnx`/`tflite`), die der Prompt
  ausdrücklich verbietet ("Keine unbeabsichtigte Komplett-Neuserialisierung
  von `models.json` committen").
- Dies ist eine **Kapazitätslücke des Maintenance-Tools**, kein
  Produktdefekt: `setup.py`s `package_data`-Globs
  (`assets/wakeword_models/*.onnx`, `*.tflite`) nehmen beide Formate direkt
  von der Festplatte auf, unabhängig vom Generator-Tool. W3s Hard-Gates
  (Wheel enthält `models.json` und alle Modelle) sind davon **nicht**
  blockiert.
- **Nicht in diesem Lauf behoben** (außerhalb des F1-Mandats; der Prompt
  verbietet ausdrücklich, „eigenmächtig eine zweite Generatorlogik zu
  modernisieren" bzw. „eine zweite aktualisierte Generatorimplementierung zu
  pflegen"): `tools/sync_wakeword_assets.py` müsste in einem eigenen,
  gezielten Folgeauftrag um TFLite-Unterstützung erweitert werden, falls das
  Bundle in Zukunft aus einer neuen Upstream-Quelle resynchronisiert werden
  soll. Zusätzlich enthält `docs/wake-words.md:55` die Aussage „Only ONNX
  artifacts are bundled, so the v2 catalog resolves ONNX." — das ist beim
  tatsächlichen Bundle-Inhalt (31 ONNX + 30 TFLite) sachlich falsch und ein
  weiterer, hier nicht behobener Dokumentationsbefund. Beides wird als
  offener Punkt in `2026-08-30_W2_C1_STATE.md` §11 festgehalten.

## 6. Tests/Checks

Da nur eine unreferenzierte, nicht-ausführbare Skriptdatei entfernt und kein
Python-/Runtime-Code geändert wurde, wurde keine vollständige 12-Minuten-
Unit-Suite verlangt. Ausgeführt wurden die relevanten Wake-Manifest-/
Catalog-Suiten sowie beide `git diff --check`-Varianten; siehe
`2026-08-30_W2_C1_STATE.md` §7 für die vollständigen Ergebnisse.

## 7. W2-Abschlusskontrollen (Prompt-Vorgabe)

| Kontrolle | Ergebnis |
|---|---|
| `app_talk_with_llm/install_cpu.bat` unangetastet | ✅ Datei unverändert vorhanden, nicht Teil dieses Commits |
| Keine nachträgliche Änderung historischer Archivdokumente | ✅ einzige Änderung ist die Löschung von `generate_models_json.ps1`; kein `docs/.archiv/**`-Inhalt berührt |
| Keine W3-Packaging-Arbeit vorgezogen | ✅ `setup.py`, `MANIFEST.in`, Wheel-Build nicht angefasst |
| Keine Docker-/Compose-Änderung | ✅ nicht angefasst |
| Keine Release-Automation | ✅ nicht angefasst |
| `git diff --check` | exit 0 (unstaged und `--cached`) |
| `git status --porcelain` | leer nach Commit und Push |
