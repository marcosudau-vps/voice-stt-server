# AP-SRV-070 — W1B-C1 CORRECTION REPORT

**Datum:** 2026-08-30
**Teilblock:** W1B-C1 — Root Correction: Legacy Wake Catalog muss per-Backend-Health respektieren
**Arbeitsbranch:** `work/AP-SRV-070`
**Worktree:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070`
**Parent (W1B):** `a7a37460a1e0997ea7856b96fb766699612a47cf`

---

## 1. Ausgangslage

Vor Beginn der Arbeit wurden alle Vorbedingungen aus Prompt "Git / Worktree"
geprüft:

| Prüfung | Erwartet | Gefunden | Ergebnis |
|---|---|---|---|
| Lokaler HEAD | `a7a37460a1e0997ea7856b96fb766699612a47cf` | identisch | PASS |
| Remote Distributed (`github`, live) | `a7a3746…` | identisch | PASS |
| Worktree | clean | `git status --porcelain` leer | PASS |
| Canonical | `c82923fc6ce889b4dfbbde1f9877b8b76481a1e8` | identisch, clean | PASS |

Kein Stop-Gate hat gegriffen. Bestehender Worktree/Branch weiterverwendet,
kein neuer Worktree, kein Amend des W1B-Commits.

---

## 2. ROOT FINDING F1 — per-Backend-Health

### Defekt (bestätigt)

`VoiceSTT_server/operations.py::WakeWordRegistry.openwakeword_models()`
filterte nur auf `entry.available` (kanonisch definiert als "mindestens ein
Backend ist gesund") und die bloße Deklaration eines Artefakts für das
angefragte Backend (`entry.artifact_for(preferred) is not None`) — nicht auf
die tatsächliche Gesundheit *dieses* Backends. Bei einem Eintrag mit
gesundem TFLite und ungesundem ONNX (Probe fehlgeschlagen) lieferte
`openwakeword_models("onnx")` den Eintrag trotzdem samt ONNX-Pfad.

`resolve_openwakeword()` prüfte den gewünschten Backend bereits korrekt
gegen `entry.healthy_backends` — Listing und Resolution waren inkonsistent,
exakt wie im Root-Review beschrieben.

Zusätzlich betroffen (nicht im Root-Finding explizit benannt, aber derselbe
Defekt): `_entry_dict()`s `availableFormats` und `paths` enthielten alle
*deklarierten* Backends (`entry.declared_backends`), nicht nur die
*gesunden* — sichtbar sowohl über `openwakeword_models()` als auch über
`resolve_openwakeword()`, da beide dieselbe Hilfsfunktion nutzen.

### Korrektur

Zwei minimale Änderungen in `WakeWordRegistry`:

1. `openwakeword_models()`: Filter von `if not entry.available` auf
   `if preferred not in entry.healthy_backends` geändert.
2. `_entry_dict()`: `availableFormats` und `paths` bauen jetzt aus
   `entry.healthy_backends` statt `entry.declared_backends`.

Keine Änderung an `resolve_openwakeword()`s eigenem Gate (war bereits
korrekt), keine Änderung an `WakeWordCatalogAuthority`/`models.json`-Schema,
kein v2-Public-Payload berührt — beide Punkte aus Prompt-Soll 8 eingehalten.

### RED-FIRST-Nachweis

Neuer Test `test_wakeword_registry_listing_honors_the_requested_backend_health`
in `tests/unit/test_server_operations.py`, gebaut mit
`tests/unit/wake_catalog_support.py::build_authority` (keine Fake-Authority)
und einem Dual-Backend-Bundle (ONNX-Prober schlägt deterministisch fehl,
TFLite-Prober besteht).

Vor der Implementierung gegen den unveränderten `a7a3746`-Stand ausgeführt:

```
FAILED tests/unit/test_server_operations.py::test_wakeword_registry_listing_honors_the_requested_backend_health
AssertionError: assert [{'id': 'hey_jarvis', ..., 'availableFormats': ['onnx', 'tflite'], ...}] == []
```

— der Test beweist exakt den beschriebenen Defekt: der ONNX-Eintrag wurde
trotz fehlgeschlagener Probe gelistet. Nach der Implementierung: GREEN
(Testreport §1).

---

## 3. ROOT FINDING F2 — stale Doku

`docs/fastapi-server.md` beschrieb `--openwakeword-model-paths` weiterhin
als "classifier paths, a model directory, or a `models.json` path" — W1B
hat Directory-/beliebigen-Manifest-Scan bereits entfernt.

Korrigiert:

- Tabellenzeile auf das reale Verhalten: explizite `.onnx`/`.tflite`-Pfade
  als Direktpfad-Override, sonst Katalogauflösung über die eine kanonische
  Wake-Word-Authority, kein Verzeichnis-Scan, kein beliebiger
  `models.json`-Pfad.
- Das direkt darunterliegende CLI-Beispiel (`--openwakeword-model-paths
  /models/openwakeword/models.json`) demonstrierte exakt dasselbe jetzt
  falsche Verhalten und wäre nach der Tabellenkorrektur ein sofortiger
  Widerspruch innerhalb derselben Doku-Datei gewesen; die jetzt ungültige
  Zeile wurde entfernt, das Beispiel funktioniert unverändert über
  `--wake-words hey_jarvis` (Katalogauflösung).

Keine W2-Doku-Reorganisation. `docs/session-wakeword-erweiterung.md` sowie
Docker-/Compose-Referenzen auf `VOICESTT_OPENWAKEWORD_MODEL_ROOT` bewusst
nicht angefasst (W2/W4-Scope, bereits in W1B-Evidence dokumentiert).

---

## 4. W1B-Invarianten

Unverändert erhalten — keine Berührung von `activation.py`,
`wake_detection.py`, `wake_backend.py`, `wakeword_catalog.py`
(die kanonische Authority selbst) oder `protocol_v2/*`:

- genau eine kanonische Wake-Word-Authority
- kein impliziter Default
- selected-only v2
- kein Runtime-Download
- `KEEP_REQUIRED` S09–S13 unangetastet
- Calibration `EVIDENCE_BLOCKED / calibration pending`

---

## 5. Geänderte Dateien

| Datei | Art |
|---|---|
| `VoiceSTT_server/operations.py` | `openwakeword_models()`-Gate und `_entry_dict()`-Projektion auf `healthy_backends` korrigiert |
| `tests/unit/test_server_operations.py` | RED→GREEN-Test für den Backend-Health-Defekt ergänzt |
| `docs/fastapi-server.md` | `--openwakeword-model-paths`-Tabellenzeile und CLI-Beispiel korrigiert |

Keine Packaging-, Docker-, Versions-, Release-Automation- oder
Client-Code-Änderungen. Kein fachlich unabhängiger Wake-Lifecycle-Seam
berührt.
