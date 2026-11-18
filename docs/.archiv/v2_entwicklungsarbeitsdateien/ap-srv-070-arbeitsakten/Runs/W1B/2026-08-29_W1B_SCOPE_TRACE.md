# AP-SRV-070 — W1B SCOPE TRACE

**Datum:** 2026-08-29/30
**Teilblock:** W1B — Wake-Word / Loader / Config / Runtime Legacy Cut
**Scope Authority:** `Prep/W0/2026-08-29_W0_DELTA_REVALIDATION.md`,
`Prep/W0/2026-08-29_W0_SCOPE_MATRIX.md`,
`Prep/W0/2026-08-29_W0_EXECUTION_BACKLOG.md` (Status: `VALIDATED / SCOPE_FROZEN`),
`Runs/W1A/2026-08-29_W1A_STATE.md` §5-6,
`Prompts/AP-SRV-070_W1B_WAKE_RUNTIME_LEGACY_CUT_RECREATED.md`
**Arbeitsbranch:** `work/AP-SRV-070`
**Worktree:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070`

---

## 1. W1-04 gegenüber W0-Block W1

| W0-ID | Titel | W1B | Begründung |
|---|---|---|---|
| W1-04 (S07, S08) | Wake Catalog Migration | **umgesetzt** | erste, in W1A explizit zurückgestellte Position |

W1A hatte W1-04 bewusst ausgeklammert (Begründung: keine technische
Abhängigkeit der Boundary-Tests). W1B holt genau diese Position nach und geht
gemäß Prompt §3 zusätzlich gezielt Wake-spezifische Altpfade an, die über die
reine Katalogmigration hinausreichen (Manifestspiegel, impliziter Default).

---

## 2. Scope-Matrix-Positionen im W1B-Zielbereich

| S-ID | Klassifikation | Gegenstand | Behandlung in W1B |
|---|---|---|---|
| S07 | `MIGRATE_BEFORE_REMOVE` | `VoiceSTT/core/openwakeword_catalog.py` | **migriert, dann gelöscht** — keine verbliebene Referenz irgendwo im Repo |
| S08 | `MIGRATE_BEFORE_REMOVE` | `VoiceSTT_server/operations.py::WakeWordRegistry` | **umgestellt** auf `WakeWordCatalogAuthority` (dieselbe Instanz wie `service.wakeword_catalog`) |
| S09 | `KEEP_REQUIRED` | `activation_config.mode == "legacy"` | **unverändert** (nicht berührt) |
| S10 | `KEEP_REQUIRED` | `_compat_final_context` | **unverändert** (nicht berührt) |
| S11 | `KEEP_REQUIRED` | `_start_wakeword_followup_window` | **unverändert** — trotz Wake-Namen bewusst nicht als Remove-Kandidat behandelt |
| S12 | `KEEP_REQUIRED` | `_trigger_ack` | **unverändert** (nicht berührt) |
| S13 | `KEEP_REQUIRED` | v2→v1-Bridge `_apply_activation_command` | **unverändert** (nicht berührt) |
| S14 | `OUT_OF_SCOPE` | `AudioToTextRecorderClient` | **nicht angefasst** |
| S17–S32 | diverse | Doku-Reorganisation, Packaging, Docker, Release | **nicht in W1B** (W2–W6) |

---

## 3. Zusätzliche Wake-spezifische Altpfade (Prompt §3)

Nach Abschluss der W1-04-Migration wurde gezielt nach weiteren Wake-Pfaden
gesucht, die den kanonischen `models.json`-Katalog umgehen:

| Fund | Klassifikation | Behandlung |
|---|---|---|
| `openwakeword_models`-Manifestspiegel in `VoiceSTT/assets/wakeword_models/models.json` und dessen Erzeugung in `tools/sync_wakeword_assets.py` | stale Config-Mirror, vom `sync`-Tool selbst als "nur Legacyspiegel … bis AP-SRV-070" dokumentiert | **entfernt** aus Manifest und Generator |
| `_apply_openwakeword_manifest_default()` (Serverstart, `server.py`) | impliziter Default-Fallback, abhängig vom jetzt gelöschten `default_model`-Konzept | **entfernt** (0 verbliebene Aufrufer) |
| `model_catalog`-Fallback-Zweig in `resolve_session_wake_word_config` | derselbe implizite Default, für den v1-Session-Fallback bei unbekanntem Wake Word | **entfernt**; fällt jetzt auf den bereits vorhandenen `wake_word_fallback_unavailable`/`wake_word_default_unavailable`-Fehlerpfad zurück (kein neuer Code, bestehender Vertrag) |
| `VOICESTT_OPENWAKEWORD_MODEL_ROOT` / Verzeichnis-Scan / beliebiger Manifestpfad in `configured_paths` | obsoleter Runtime-Resolution-Pfad der alten `OpenWakeWordCatalog`-Klasse | **entfernt** — ersetzt durch die eine kanonische `VOICESTT_WAKEWORD_ASSET_ROOT` |

**Nicht entfernt (bewusst):**

- `openwakeword_model_paths` als expliziter Direktpfad-Override (Operator
  gibt exakte `.onnx`/`.tflite`-Dateien an) — bleibt bestehen, wird von
  `_resolve_openwakeword_paths` weiterhin unterstützt; ist keine
  Katalog-Umgehung im W0-Sinn, sondern eine eigenständige, orthogonale
  Fähigkeit ohne Katalogbezug.
- `wake_word_buffer_duration` (pauschale Legacy-Einstellung) — nicht Teil
  dieser Migration, in `docs/einheitliche-triggerarchitektur.md` §14.11
  explizit als weiterhin bestehende Legacykompatibilität dokumentiert.
- `_start_wakeword_followup_window` — S11, `KEEP_REQUIRED`.

---

## 4. Design-Entscheidung: impliziter Manifest-Default

Der alte `OpenWakeWordCatalog` unterstützte ein `default_model`-Feld; der
kanonische `WakeWordCatalogAuthority`/`models.json`-Vertrag kennt dieses
Konzept nicht (selected-only, kein Default laut `wakeword.py`-Docstring vor
W1B). Diese Diskrepanz betrifft reale Produktionspfade (Serverstart,
v1-Session-Fallback) und wurde dem Auftraggeber vorgelegt, da weder das
Erfinden einer neuen Auswahlregel noch eine Erweiterung des eingefrorenen
Manifest-Schemas ohne separate Freigabe zulässig ist (Prompt §2: "Keine neue
Wake-Word-Architektur entwerfen"; Projektregel: keine Erweiterung
eingefrorener Verträge in einem Umsetzungslauf).

**Entscheidung (vom Auftraggeber bestätigt):** Der implizite Default wird
ersatzlos abgeschafft. Eine Aktivierung ohne auflösbares Wake Word wird
abgelehnt statt ein Modell zu erraten — konsistent mit der bereits am
v2-Pfad etablierten "selected-only, no default fallback"-Philosophie.

---

## 5. Runtime-Reachability-Beweis vor Löschung

Vor der Löschung von `openwakeword_catalog.py` wurden alle Importe
repo-weit gesucht (`grep -R "openwakeword_catalog\|OpenWakeWordCatalog"`):

- `VoiceSTT_server/operations.py::WakeWordRegistry` — migriert.
- `VoiceSTT/core/wakeword.py::_resolve_openwakeword_paths` — migriert.

Zusätzlich wurde geprüft, ob `wakeword.py`s Legacy-Pfad außerhalb des
FastAPI-Servers erreichbar ist — eine Prüfung, die W0 nicht vorgenommen
hatte. Ergebnis: `VoiceSTT_server/stt_server.py` (eigenständiger CLI-Entry-
Point, besitzt `main()`/`__main__`) ruft `setup_wakeword_detection` ohne
`wake_word_selection` auf und hängt damit direkt am migrierten Legacy-Pfad.
Deshalb wurde `_resolve_openwakeword_paths` bewusst **nicht** auf eine
zwingend vom Server bereitgestellte `WakeWordCatalogAuthority`-Instanz
umgestellt, sondern lädt den Snapshot eigenständig
(`wakeword_catalog.load_snapshot()`), damit der Legacy-Pfad für
Nicht-Server-Aufrufer funktionsfähig bleibt.

Nach der Löschung erneute repo-weite Suche: keine Treffer außer den eigenen
Docstring-Erwähnungen des retirierten Namens in `operations.py`/`wakeword.py`
und den historischen `docs/.archiv/**`-Akten.

---

## 6. Nicht angefasst

- **S17–S32** — Doku-Reorganisation, Repo-Hygiene, Packaging, Docker, Release
  (W2–W6).
- **`docs/.archiv/**`** und **`docs/session-wakeword-erweiterung.md`** —
  Letzteres ist laut W0 (S20) expliziter W2-Archivkandidat; enthält
  weiterhin eine veraltete `default_model`-Beschreibung, die W2 mitbereinigt.
- **`Dockerfile`, `docker-compose.yml`, `build/vps/docker-compose.yml`** —
  enthalten ebenfalls veraltete `VOICESTT_OPENWAKEWORD_MODEL_ROOT`-Referenzen,
  ausdrücklich `OUT_OF_SCOPE` für W1B (Prompt §4).
- **`VoiceSTT/audio_recorder_client.py` (`AudioToTextRecorderClient`)** — S14,
  `OUT_OF_SCOPE`.
