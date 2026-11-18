# AP-SRV-070 — W3 — Installed-Artifact Report

**Datum:** 2026-08-30
**Teilblock:** W3-05 — Installed-Distribution Wake Smoke

---

## 0. Umgebung

Docker war in dieser Sitzung nicht nutzbar (siehe Packaging-Report §0).
Fallback gemäß der im Prompt vorgesehenen Ausweichoption: eine temporäre,
nach dem Lauf vollständig gelöschte venv (`install_venv`), außerhalb des
Worktrees (`%TEMP%\...\scratchpad\install_venv`).

```
python -m venv install_venv
install_venv\Scripts\python -m pip install "voicestt-2.0.0-py3-none-any.whl[server,openwakeword]"
```

Installiert (Auszug, vollständig in
`evidence_artifacts/2026-08-30_W3_install_venv_pip_freeze.txt`):
`voicestt==2.0.0`, `fastapi==0.141.1`, `onnxruntime==1.29.0`,
`openwakeword==0.6.0`, `torch==2.13.0`, `torchaudio==2.11.0`.

`pip check`: **„No broken requirements found."**

Der Smoke lief aus `C:\Windows\Temp` (keinerlei VoiceSTT-/api_fastapi_server-
Quellcode in diesem Verzeichnis oder darüber erreichbar) mit
`SMOKE_FORBIDDEN_SOURCE_PATH` explizit auf den Worktree-Pfad gesetzt, damit
das Smoke-Skript selbst hart prüft, dass `VoiceSTT` **nicht** aus dem
Source-Checkout importiert wurde.

Vollständige Rohdaten: `evidence_artifacts/2026-08-30_W3_installed_artifact_smoke.json`.

## 1. Ergebnis: alle 14 Prompt-Punkte

Gesamtergebnis des Smoke-Skripts: **`"ok": true`, `"errors": []`** — jeder
Einzel-Check `ok: true`.

| # | Prompt-Anforderung | Ergebnis |
|---|---|---|
| 1 | Package importieren | `VoiceSTT` erfolgreich importiert aus `...install_venv\Lib\site-packages\VoiceSTT\__init__.py` — **nicht** aus dem Worktree |
| 2 | Produktversion lesen | `VoiceSTT.get_version()` = `2.0.0`; `importlib.metadata.version("voicestt")` = `2.0.0` — identisch |
| 3 | `default_asset_root()`/`importlib.resources` zeigt in installierte Distribution | `...install_venv\Lib\site-packages\VoiceSTT\assets\wakeword_models` bestätigt, Verzeichnis existiert |
| 4 | `models.json` laden | Lädt und validiert vollständig über `wakeword_catalog.load_snapshot()` |
| 5 | Manifestrevision korrekt | `catalogRevision = 2` |
| 6 | 25 öffentliche Wake Words | `len(snapshot.entries) == 25` bestätigt |
| 7 | ONNX/TFLite-Artefakte für alle manifestierten Einträge | alle 25 Einträge deklarieren `onnx` **und** `tflite` |
| 8 | Pipeline beider Backends | `pipeline.backends == {onnx, tflite}`, Dateien für beide Backends auf der Platte vorhanden |
| 9 | `silero_vad.onnx` vorhanden | vorhanden, 1 807 522 Bytes (identisch zur in W2-C2 dokumentierten Byte-Größe) |
| 10 | Hash/Byte-Integrität | 54 manifestierte Dateien (50 Classifier + 4 Pipeline) SHA-256- und größenexakt gegen `models.json` geprüft — alle bestanden |
| 11 | keine unmanifestierten historischen Zusatzmodelle im Wheel | `installedFileCount = 56`, keiner der 6 verbotenen Dateinamen (`Jarvis.onnx`, `jarvis_v1.onnx`, `hey_jarvis_v0.1.onnx` + `.tflite`) vorhanden |
| 12 | `/api/v2/wake-words` aus installierter Serverdistribution | Über `TestClient(create_app())`: `protocolVersion=2`, `catalogRevision=2`, 25 `wakeWords` |
| 13 | ausgewähltes Wake Word unter verfügbarem Backend initialisierbar | ONNX-Backend real verfügbar (`onnxruntime` installiert); Wake Word `alexa` real per `admit_selection` unter `onnx` zugelassen und `InferenceSession` erfolgreich erstellt. TFLite korrekt als `runtime_unavailable` gemeldet (kein `tflite-runtime` installiert) — **kein** falsches „available" |
| 14 | keine Runtime-Downloads | Siehe §2 unten — statisch bewiesen, nicht operational über `--network none` erzwungen (Docker-Ausfall) |

Zusätzlich (über die 14 Punkte hinaus, aus Symmetrie zur Version-Authority
geprüft): `app.version` der installierten FastAPI-App (`create_app().version`)
== `2.0.0`, identisch zu `VoiceSTT.get_version()`.

## 2. Punkt 14 — „keine Runtime-Downloads" ohne Docker-Netzwerktrennung

Der Prompt bevorzugt eine operationale Erzwingung (Container ohne Netzwerk).
Da Docker in dieser Sitzung ausfiel, stützt sich dieser Nachweis stattdessen
auf zwei unabhängige, aber schwächere Belege:

1. **Statisch:** `tests/unit/test_wakeword_asset_integrity.py::NoRuntimeDownloadTests`
   beweist per AST-Analyse, dass `VoiceSTT/core/wakeword_catalog.py` (der
   Modul, das `default_asset_root()` und `load_snapshot()` implementiert)
   keinen netzwerkfähigen Import enthält (`requests`, `httpx`, `urllib.request`,
   `aiohttp`, `socket`, `http.client`).
2. **Operational (schwächer als Netzwerktrennung, aber real):** jeder der 13
   übrigen Smoke-Checks — inklusive Manifest-Laden, Hash-Prüfung und
   realer ONNX-Modellinitialisierung — griff ausschließlich auf Dateien
   unter dem lokal installierten `assets/wakeword_models`-Verzeichnis zu und
   ist erfolgreich durchgelaufen, ohne dass irgendein Netzwerkaufruf im
   Code-Pfad vorgesehen ist.

Das Smoke-Skript meldet diesen Punkt ehrlich als
`"operationallyEnforced": false` mit Begründung, statt einen nicht
erbrachten Nachweis stillschweigend als bestanden auszuweisen.

**Offener Punkt für einen späteren, gezielten Nachlauf:** sobald Docker in
dieser Umgebung wieder funktioniert, sollte dieser einzelne Punkt (14) mit
`docker run --network none` nachgeholt werden, um die operationale
Netzwerktrennung tatsächlich zu erzwingen statt nur statisch zu belegen.
Kein Blocker für W3 selbst — kein anderer W3-Gate hängt davon ab.

## 3. Entry Points (installierte Distribution)

| Befehl | Ergebnis |
|---|---|
| `stt-server --help` | druckt vollständige `argparse`-Usage, Exit ohne Fehler |
| `stt --help` | druckt vollständige `argparse`-Usage, Exit ohne Fehler |
| `stt-install-kroko --help` | druckt vollständige `argparse`-Usage inkl. Beschreibungstext, Exit ohne Fehler |

Alle drei Konsolen-Skripte aus `entry_points.txt` real aus der installierten
Distribution ausführbar (nicht nur als String in der Metadaten-Datei).

## 4. Calibration Status

**EVIDENCE_BLOCKED / calibration pending** — unverändert. Dieser Lauf hat
keine reale Wake-Audio-Kalibrierung durchgeführt oder erfunden; die reale
ONNX-Initialisierung in Punkt 13 ist Modell-Ladbarkeit, keine
Audio-Kalibrierung.
