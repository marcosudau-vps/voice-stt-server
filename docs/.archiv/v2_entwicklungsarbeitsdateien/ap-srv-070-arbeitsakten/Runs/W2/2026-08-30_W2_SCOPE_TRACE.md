# AP-SRV-070 — W2 SCOPE TRACE

**Datum:** 2026-08-30
**Teilblock:** W2 — Product Surface / Documentation / Repository Hygiene
**Scope Authority:** `Prep/W0/2026-08-29_W0_DELTA_REVALIDATION.md`,
`Prep/W0/2026-08-29_W0_SCOPE_MATRIX.md`,
`Prep/W0/2026-08-29_W0_EXECUTION_BACKLOG.md`,
`Runs/W1A/…STATE.md` §5, `Runs/W1B/…STATE.md` §7,
`Runs/W1B-C1/2026-08-30_W1B_C1_STATE.md` §9 (W2 ready = JA),
`Prompts/AP-SRV-070_W2_PRODUCT_SURFACE_HYGIENE_UPDATED.md`

---

## 1. W0-Scope-Matrix-Positionen im W2-Zielbereich

| S-ID | Klassifikation | Gegenstand | Behandlung in W2 |
|---|---|---|---|
| S17 | `CONFIRMED_REMOVE` | `Planning/logging-fixes-implementierungsplan.md` | **archiviert** nach `docs/.archiv/logging-fixes/` |
| S18 | `CONFIRMED_REMOVE` | `api_fastapi_server/MULTI_USER_IMPLEMENTATION_GUIDE.md` | **archiviert** nach `docs/.archiv/multi-user-design/` |
| S19 | `CONFIRMED_REMOVE` | `docs/stt-server-specification.md` | **archiviert** nach `docs/.archiv/desktop-client-spec/` |
| S20 | `MIGRATE_BEFORE_REMOVE` | `docs/session-wakeword-erweiterung.md` | **archiviert** nach `docs/.archiv/session-wakeword/`; Fachvertrag bereits vollständig in `docs/wake-words.md` und `docs/client-development/09-…md` — keine Migration nötig, siehe Documentation Report §4 |
| S21 | `CONFIRMED_REMOVE` | `tests/suh_mahn_thuh.onnx`, `tests/suh_man_tuh.onnx`, `tests/samanta.tflite` | **entfernt** nach Referenzprüfung, siehe Hygiene Report |
| S22 | `CONFIRMED_REMOVE` | Redundante Batchskripte | **teilweise entfernt**: `app_browserclient/start_server.bat` und `app_talk_with_llm/start.bat` entfernt; `app_talk_with_llm/install_cpu.bat` **bewusst behalten** (aktiv referenziert in `app_talk_with_llm/README.MD`) — Abweichung von der W0-Pauschalklassifikation, begründet in Hygiene Report §2 |
| S23 | `MIGRATE_BEFORE_REMOVE` | `README.md` | **aktualisiert**: Protokoll v2, Activation Lifecycle, Settings Plane, Wake-Word-Katalog v2 ergänzt |
| S24 | `MIGRATE_BEFORE_REMOVE` | `docs/fastapi-server.md` | **aktualisiert**: neue Abschnitte „Protocol v2" und „Settings v2", v1 explizit als Legacy markiert |
| S25 | `MIGRATE_BEFORE_REMOVE` | `docs/einheitliche-triggerarchitektur.md`, `docs/module-map.md`, `docs/configuration.md`, `docs/api-compatibility.md` | **auditiert und korrigiert** (`configuration.md` ohne Befund) |

## 2. Zusätzlich gefundene und behandelte Positionen (über W0 hinaus)

Diese Funde stammen aus der eigenen repo-weiten Prüfung in W2, nicht aus der
ursprünglichen W0-Matrix. Sie sind sachlich derselben Kategorie (S25 /
Sprach-Terminologie-Inkonsistenzen, Prompt-Befund 5) zuzurechnen und wurden
im selben Umfang wie die W0-benannten Positionen behandelt:

1. Neun weitere Stellen mit der stale Zeitform „…bis AP-SRV-070" bzw.
   „Legacyabbau ist AP-SRV-070" in `docs/einheitliche-triggerarchitektur.md`
   (6), `docs/api-compatibility.md` (1), `docs/wake-words.md` (1),
   `docs/client-development/08-protokollabgrenzung.md` (1) sowie zwei
   Quellcode-Docstrings/-Kommentare (`protocol_v2/schema.py`,
   `protocol_v2/__init__.py`, `server.py` zwei Stellen).
2. Ein interner Widerspruch in `docs/einheitliche-triggerarchitektur.md`
   selbst (§14.8 sagte „entfällt mit AP-SRV-070", §14.11/14.12 sagten bereits
   korrekt „bleibt Legacykompatibilität") — durch dieselbe Korrektur behoben.
3. Zwei weitere `default_model`-Falschaussagen in
   `docs/client-development/09-betriebsmodi-und-serverkonfiguration.md`
   (Zeilen 304-305, 377 vor Korrektur), zusätzlich zu den bereits im Prompt
   als Befund 6 genannten Stellen in `docs/session-wakeword-erweiterung.md`.
4. Vier aktive inbound-Links auf das nun archivierte
   `docs/session-wakeword-erweiterung.md` (`README.md`, `docs/README.md`,
   `docs/client-development/README.md`, `VoiceSTT_server/README.md`) —
   Folgeanpassung der S20-Archivierung, ohne die wären vier tote Links
   entstanden.
5. `VoiceSTT/assets/wakeword_models/generate_models_json.ps1` — Befund
   dokumentiert, **nicht** verändert (nicht im W2-05-Mandat, siehe
   Documentation Report §5).

## 3. Nicht angefasst (bestätigt außerhalb Scope)

- **Docker-/Compose-Dateien** (`Dockerfile`, `docker-compose.yml`,
  `build/vps/docker-compose.yml`): `VOICESTT_OPENWAKEWORD_MODEL_ROOT`-Referenzen
  laut Prompt ausdrücklich `OUT_OF_SCOPE` für W2 (W4-Deployment-Cut).
- **Packaging/Wheel/Release** (S26–S32): unverändert, Zielblöcke W3/W5/W6.
- **`docs/.archiv/**`-Bestandsdateien**: keine inhaltliche Änderung; nur vier
  neue Dateien per `git mv` hinzugefügt, keine bestehende Archiv-Datei
  editiert.
- **`docs/.archiv/README.md`-Register**: bewusst nicht um neue Zeilen für die
  vier W2-Archivierungen erweitert — Begründung in Documentation Report §4.
- **Wake-Word-Bundle-Assets** (`VoiceSTT/assets/wakeword_models/**`):
  unverändert.
- **`VoiceSTT/audio_recorder_client.py`** (S14, `OUT_OF_SCOPE`): nicht
  angefasst.
- **Runtime-/Vertragsverhalten**: keine einzige Änderung an tatsächlichem
  Server-, Protokoll- oder Wake-Word-Verhalten. Alle Quellcode-Änderungen
  (`server.py`, `protocol_v2/schema.py`, `protocol_v2/__init__.py`)
  beschränken sich auf Docstring-/Kommentartext; keine ausführbare
  Codezeile geändert (per `git diff` und `py_compile` verifiziert).

## 4. Historische Evidence

Kein bestehendes Dokument unter `docs/.archiv/**` wurde inhaltlich verändert.
Die vier neu archivierten Dokumente wurden unverändert per `git mv`
verschoben (kein nachträgliches „Modernisieren" historischer Aussagen).
