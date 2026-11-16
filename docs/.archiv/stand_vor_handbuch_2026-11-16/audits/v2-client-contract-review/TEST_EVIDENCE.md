# Testevidenz der unabhängigen Prüfung

**Datum:** 2026-09-28 · **Code-Stand:** `f7d2b3ccd07757172a45b371829b04bcedffab4b`
(der Prüfbranch ändert ausschließlich Markdown-Dateien; siehe §5).

## 1. Umgebung

| Aspekt | Wert |
| --- | --- |
| Container | Linux, Python 3.11.15 |
| Virtuelle Umgebung | `python3 -m venv` außerhalb des Repositorys |
| Installiert | `api_fastapi_server/requirements.txt` (fastapi 0.141.1, uvicorn 0.54.0, numpy 2.4.6, scipy 1.17.1, PyYAML, tzdata), pytest 9.1.1, httpx 0.28.1, python-multipart; nachträglich onnxruntime 1.30.0, soundfile 0.14.0, webrtcvad-wheels 2.0.14 |
| Nicht installiert | `torch`, `faster_whisper`, `halo`, `openwakeword` und weitere Teile von `requirements.txt` / Extras `[recommended,server]` (Größe) |
| Abweichung zur CI | CI (`.github/workflows/ci.yml`) installiert `-e ".[recommended,server]"` und `requirements-dev.txt`; `requirements.txt` pinnt numpy 1.26.4 |

Aufruf je Testdatei (Skript, 300–600 s Timeout pro Datei):

```bash
python -m pytest -q -rs -p no:cacheprovider tests/unit/<datei>.py
```

## 2. V2-relevante Suites

| Suite | Ergebnis | Deckt ab |
| --- | --- | --- |
| `tests/unit/test_protocol_v2_contract.py` | 66 passed, 1 skipped, 40 subtests | Vektoren, Envelope, Ack-Projektion, `stateVersion`/`eventSeq`, Snapshot |
| `tests/unit/test_protocol_v2_e2e.py` | 68 passed, 16 subtests | echter `/ws/v2`-Handler: Handshake, Close-Codes, Commands, Replay, Snapshot, Audio vor `hello` |
| `tests/unit/test_protocol_v1_v2_boundary.py` | 15 passed, 16 subtests | V1/V2-Trennung, `extend` auf beiden Transporten |
| `tests/unit/test_protocol_v2_state_version.py` | 21 passed, 105 subtests | `stateVersion`-Regeln |
| `tests/unit/test_protocol_v2_races.py` | 9 passed, 120 subtests | Linearisierung, Replays unter Nebenläufigkeit |
| `tests/unit/test_protocol_v2_settings.py` | 41 passed (mit onnxruntime) | `session_settings.patch`, REST-v2-Settings |
| `tests/unit/test_settings_control_plane.py` | 64 passed | Registry, Timings, Cross-Field |
| `tests/unit/test_wake_admission.py` | 14 passed, 90 subtests | Wake-Admission |
| `tests/unit/test_wakeword_catalog_api.py` | 9 passed, 25 subtests | Katalog-REST |
| `tests/unit/test_wakeword_catalog.py` | 50 passed, 63 subtests (mit onnxruntime) | Katalogautorität |
| `tests/unit/test_wakeword_session_e2e.py` | 15 passed, 10 subtests | Wake-Events über `/ws/v2` |
| `tests/unit/test_wakeword_root_findings_c2.py` | 49 passed, 118 subtests | kanonische Wire-IDs vs. toleranter Resolver |
| `tests/unit/test_browser_client_contract.py` | 10 passed, 7 subtests | V1-Browserframing (identisches Audioformat) |
| `tests/unit/test_server_command_timer_e2e.py`, `test_server_controlled_e2e.py`, `test_server_trigger_contract.py`, `test_server_activation_controller.py`, `test_server_activation_commands.py` | 48 / 34 / 18 / 56 / 22 passed | Domainautoritäten unter V1/V2 |

Der eine Skip in `test_protocol_v2_contract.py` ist
`VOICESTT_PROTOCOL_V2_VECTORS` (Vergleich mit dem Original der Vektoren im
Client-Planungsrepository, hier nicht verfügbar).

**Reproduktion der Audit-Angaben:** 66 passed/1 skipped und 14 passed stimmen.

### Beobachtungen ohne onnxruntime (erster Lauf)

Ohne installierte Wake-Word-Inferenzlaufzeit:

* `test_wakeword_catalog.py`: 1 Test mit 25 fehlschlagenden Subtests (`BundledAssetTests::test_every_bundled_entry_is_available_and_complete` erwartet alle Einträge `available`).
* `test_protocol_v2_settings.py`: 1 Fehler und danach Hänger bis zum 600-s-Timeout.

Mit onnxruntime liefen beide vollständig grün (§2). Beides ist
Umgebungsabhängigkeit; CI installiert die Laufzeit über die Extras.

## 3. Wire-Traces

Zusätzlich zur Suite wurden Abläufe über die echte Route `/ws/v2` mit dem
Referenz-Harness (`tests/unit/test_protocol_v2_e2e.py::V2Session`,
`GateAwareRecorder` aus `test_server_controlled_e2e.py`) aufgezeichnet –
Skripte außerhalb des Repositorys, keine Repo-Änderung:

| Trace | Belegt |
| --- | --- |
| manuell: activate → Audio → Segmentende → finish → Snapshot | Events vor Ack; Ack-`stateVersion` < Eventversionen; `activation.completed` (seq 8) **vor** `activation.input_closed` (seq 9); eventloser `closing_input`-Eintritt; vollständige Settings-Maps |
| cancel | `transcription.discarded` vor `segment.recording_ended`/`transcription.accepted` desselben Segments |
| Fehlerfälle | `not_active`, `invalid_phase`, `activation_locked`, `stale_activation`, `stale_session`, `invalid_payload` (ohne `errors[]`), `settings_revision_conflict`/`settings_rejected` (mit `errors[]`), `settings.changed` ×2 bei einer Transaktion, `trigger_suppressed` (Ack vor Diagnoseevent), kein Ack für nicht kanonische `commandId`/unbekannten Typ, stille Verwerfung eines ungültigen Audioframes, unbekanntes Zusatzfeld bei `activate` toleriert |
| Handshake | `4406` mit `protocol.incompatible`; `4409` für fehlenden Trigger, Alias (`not_canonical`), unbekannte ID (`unknown`); UUIDv1-`clientRunId` angenommen; großgeschriebene → `4400` |
| Wake Word | `activation.started` (seq 1) vor `wakeword.detected` (seq 2), je eigene `stateVersion` |
| Session-Patch `wakeWord.selection` | `"Hey Jarvis"` und `"jarvis"` → `applied`, Rohwert in `requestedSettings`; `"nope"` → `settings_rejected` |
| HTTP | `GET /api/v2/wake-words` Top-Level `{protocolVersion, catalogRevision, wakeWords}`; `GET /api/v2/settings/server` `{protocolVersion, serverCommit, serverVersion, settings, settingsRevision}`; `GET /api/v2/health` → 404 |

## 4. Gesamte Unit-Suite

Alle 84 Dateien unter `tests/unit/` einzeln ausgeführt:

* **71 Dateien grün** (inkl. aller V2-, Wake-, Settings-, Release- und Build-Suites).
* **Nicht ausführbar / umgebungsbedingt rot** (keine Beziehung zu Dokumentation):

| Datei | Ursache |
| --- | --- |
| `test_audio_recorder_boundaries`, `test_audio_recorder_public_api`, `test_fastapi_server_protocol`, `test_recorder_activation_control`, `test_recorder_runtime`, `test_recorder_state_callbacks`, `test_server_operations` | `ModuleNotFoundError: torch` (nach Installation von soundfile) |
| `test_wakeword_recording_path` | `ModuleNotFoundError: halo` |
| `test_openai_compatible_endpoint` | `ModuleNotFoundError: faster_whisper` (10 von 20) |
| `test_kroko_artifact_store` (24), `test_install_kroko_cpu` (1) | erwartet cp312-Wheel-Tags; Umgebung ist cp311 |
| `test_server_segment_ledger` | vor soundfile/webrtcvad rot; danach **19 passed** |
| `test_docs_surface` | während der Arbeit rot wegen noch nicht angelegter Linkziele; Endstand siehe §5 |

## 5. Dokumentationsvalidierung (Endstand)

| Prüfung | Kommando | Ergebnis |
| --- | --- | --- |
| Repository-Linktest | `python -m pytest -q tests/unit/test_docs_surface.py` | 30 passed, 42 subtests |
| Doku-Inhaltstests Wake Words | `python -m pytest -q tests/unit/test_wakeword_root_findings_c3.py` | 83 passed |
| Relative Links **inkl. Anchors** (GitHub-Slug) über alle gepflegten `.md` | eigenes Skript (`linkcheck.py`, außerhalb des Repos) | 0 Probleme; dabei einen vorbestehenden defekten Anchor in `docs/wake-words.md` repariert |
| JSON-Beispiele | eigenes Skript: alle ```` ```json ````-Blöcke in `docs/client-development/`, `docs/audits/v2-client-contract/`, `docs/fastapi-server.md`, `docs/wake-words.md` geparst; `hello` durch `handshake.parse_hello`, konkrete Commands durch `commands.parse_command`, Acks/Events gegen Pflichtfelder und Result-Code-Regeln; alle ID-Beispiele gegen `is_canonical_uuid` | 51 Blöcke, 0 Fehler. Zusätzlich `docs/einheitliche-triggerarchitektur.md` (9 Blöcke): V2-`hello` in §12.2 von Platzhaltern auf gültige Werte umgestellt und gültig; verbleibende Treffer sind abgekürzte IDs (`6f1c...`) in den als Legacy V1 markierten §6/§11 und der Platzhalter `{ ... }` im Persistenzformat §13.5 – keine V2-Wire-Beispiele. Gleiches gilt für die unverändert verschobenen Seiten unter `legacy-v1/`. |
| Audio-Encoder-Beispiel | Python-Encoder aus `02-websocket-protokoll.md` → `api_fastapi_server.protocol.decode_audio_packet` | Roundtrip ok; Metadatenlänge des Beispiels = 67 (`0x43`) wie dokumentiert |
| Markdown-Lint | kein Linter im Repository konfiguriert | nicht ausgeführt |
| Produktcode unverändert | `git diff --stat f7d2b3cc -- . ':(exclude)*.md'` | leer |
