# AP-SRV-070 — W1B IMPLEMENTATION REPORT

**Datum:** 2026-08-29/30
**Teilblock:** W1B — Wake-Word / Loader / Config / Runtime Legacy Cut
**Arbeitsbranch:** `work/AP-SRV-070`
**Worktree:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070`
**Parent (Distributed, W1A):** `24f3a6e0d321fe02ce3b5aef681380b500db1b81`

---

## 1. Ausgangslage

Vor Beginn der Arbeit wurden alle Vorbedingungen aus Prompt §Authorities/
Git-Worktree geprüft:

| Prüfung | Erwartet | Gefunden | Ergebnis |
|---|---|---|---|
| Remote Distributed (`github`, live) | `24f3a6e0d321fe02ce3b5aef681380b500db1b81` | identisch | PASS |
| Lokaler HEAD | `24f3a6e…` | identisch | PASS |
| Worktree `workspaces/ap-srv-070` | clean | `git status --porcelain` leer | PASS |
| Canonical-Workspace | unverändert, clean | `c82923fc…`, leer | PASS |

Eine Randbeobachtung: `git ls-remote origin …` (der lokale Pfad-Remote
`P:\GithubRepos\marcosudau-vps\voice-stt-server\main`) lieferte für
`feat/einheitliche-triggerarchitektur-distributed` einen veralteten Wert
(`325e55c…`, AP-SRV-030-Ära). Ursache: dieser lokale Remote hat selbst einen
Remote namens `origin` (das echte GitHub), und `refs/remotes/origin/…` dort
ist ein seit längerem nicht aktualisierter Cache-Ref, keine echte Kopie des
Distributed-Branches. Die tatsächliche Autorität ist der `github`-Remote
(`https://github.com/marcosudau-vps/voice-stt-server.git`), gegen den `git
ls-remote` live abgefragt wurde und der exakt `24f3a6e…` zeigte — konsistent
mit dem lokalen Branch und mit W1A_STATE §2. Kein Stop-Gate hat gegriffen;
die Beobachtung wird hier nur für zukünftige Läufe festgehalten, damit sie
nicht erneut als scheinbare Diskrepanz auftaucht.

Der bestehende Worktree/Branch wurde weiterverwendet; kein neuer Worktree
angelegt.

---

## 2. Umgesetzte W0-Position: W1-04 — Wake Catalog Migration (S07, S08)

### 2.1 Altarchitektur und Nutzer

`VoiceSTT/core/openwakeword_catalog.py::OpenWakeWordCatalog` — eigenständiger
Legacy-Scanner (Verzeichnis-Scan, beliebiger Manifestpfad, `default_model`-
Feld) — wurde von zwei Stellen genutzt:

- `VoiceSTT_server/operations.py::WakeWordRegistry`
- `VoiceSTT/core/wakeword.py::_resolve_openwakeword_paths`

### 2.2 `WakeWordRegistry` (`VoiceSTT_server/operations.py`)

Vollständig umgestellt auf die eine kanonische
`VoiceSTT.core.wakeword_catalog.WakeWordCatalogAuthority`. `server.py`
konstruiert jetzt genau eine Authority-Instanz (`self.wakeword_catalog`) und
übergibt sie an `WakeWordRegistry`, statt eine zweite, redundante
Katalog-Instanz aufzubauen — vorher liefen zwei parallele
Wake-Word-Systeme im selben Serverprozess, jetzt ist es die eine
serverweite Authority aus AP-SRV-060.

Kein bloßes Import-Umbenennen: Rückgabeform und Auflösungslogik sind neu
implementiert, weil die alte und die neue Katalogarchitektur unterschiedliche
Semantik haben (siehe Scope-Trace §4 zum abgeschafften Default). Die externe
Methodensignatur wurde dort angepasst, wo `configured_paths` bedeutungslos
wurde (kanonischer Katalog hat einen festen, konfigurierbaren Asset-Root,
keinen Pfad pro Aufruf) — alle sechs Aufrufstellen in `server.py` wurden
entsprechend angepasst (`session_capabilities`, `GET /api/wake-word`,
`PUT /api/wake-word`, `resolve_session_wake_word_config`,
`_apply_openwakeword_manifest_default` — Letztere komplett entfernt, siehe
§2.4).

Auflösung bleibt **pro angefragter ID unabhängig** (nicht die atomare
"eine gemeinsame Selektion"-Regel der v2-Wire-Admission `admit_selection`):
ein Aufrufer bekommt weiterhin exakt zurückgemeldet, welche der angefragten
IDs fehlschlugen. Das entspricht dem alten Vertrag und ist bewusst nicht auf
`admit_selection`/`resolve_human_selection` umgestellt, deren Alles-oder-
nichts-Semantik für diesen Utility-Anwendungsfall eine Verhaltensänderung
gewesen wäre.

### 2.3 `_resolve_openwakeword_paths` (`VoiceSTT/core/wakeword.py`)

Migriert auf `wakeword_catalog.load_snapshot()` (zustandsloser Modul-Aufruf,
keine Server-Instanz nötig — siehe §2.5 zur Standalone-Erreichbarkeit).
Verhalten:

- Explizite Klassifikatordateien (`.onnx`/`.tflite` in `model_paths`) werden
  weiterhin unverändert direkt verwendet, ohne Katalog-Lookup.
- Namen/IDs in `wake_words` werden gegen den kanonischen Katalog aufgelöst
  (`snapshot.resolve()` + `snapshot.get()` + `entry.artifact_for()`).
- Die Pipeline-Modelle (Melspectrogram/Embedding) kommen jetzt **immer** aus
  dem einen kanonischen Manifest, nie mehr aus einem Verzeichnis-Scan neben
  dem Klassifikator — das ist keine Verhaltenslockerung, sondern folgt
  direkt aus `WakeWordPipeline`s eigenem Vertrag ("catalog-owned, not
  per-classifier").

### 2.4 Entfernter impliziter Default

`_apply_openwakeword_manifest_default()` (Serverstart) und der
`model_catalog`-Fallback-Zweig in `resolve_session_wake_word_config`
(v1-Session ohne auflösbares Wake Word) wurden vollständig entfernt. Details
und Design-Entscheidung in Scope-Trace §4. Beide Stellen fallen jetzt auf
bereits vorhandene, bereits im Code vorgesehene Fehlerpfade zurück
(`wake_word_default_unavailable`, `wake_word_fallback_unavailable`) — kein
neuer Fehlercode wurde eingeführt.

### 2.5 Standalone-CLI-Reachability (`stt_server.py`)

W0 hatte nur `operations.py` und `wakeword.py` als Nutzer identifiziert, aber
nicht geprüft, ob `wakeword.py`s Legacy-Pfad außerhalb des FastAPI-Servers
erreichbar ist. Er ist: `VoiceSTT_server/stt_server.py` ist ein eigenständiger
CLI-Entry-Point ohne jede Anbindung an eine `WakeWordCatalogAuthority`-
Instanz. Deshalb wurde `_resolve_openwakeword_paths` bewusst so migriert,
dass es den Katalog-Snapshot selbst lädt (`load_snapshot()`), statt eine vom
Server bereitgestellte Instanz zu verlangen. Damit bleibt der Legacy-Pfad für
diesen und jeden anderen Nicht-Server-Aufrufer funktionsfähig.

### 2.6 Löschung

`VoiceSTT/core/openwakeword_catalog.py` gelöscht, nachdem beide Nutzer
migriert waren und eine erneute repo-weite Suche keine verbliebenen Importe
mehr zeigte (Scope-Trace §5).

---

## 3. Zusätzliche Bereinigung: stale Config-Mirror

`VoiceSTT/assets/wakeword_models/models.json` enthielt einen
`openwakeword_models`-Abschnitt, den `tools/sync_wakeword_assets.py` selbst
als "nur ein Legacyspiegel … bis AP-SRV-070" dokumentierte — ein direkter,
im Code stehender Hinweis, dass genau dieser Lauf ihn abbauen soll. Entfernt
aus dem Generator (`build_manifest()`) und aus der committeten Manifestdatei
(präzise Textentfernung, kein vollständiges JSON-Reserialisieren, um keinen
unnötigen Format-Diff zu erzeugen — siehe Diff-Hygiene im Testreport §4).

---

## 4. SRV-060-Invarianten

Keine der in Prompt §2 aufgezählten Invarianten wurde berührt. Betroffene
Dateien dieses Laufs beschränken sich auf `WakeWordRegistry`,
`wakeword.py`s Legacy-Resolver und die zwei v1-Konfigurationsstellen in
`server.py`; `activation.py`, `wake_detection.py`, `wake_backend.py`,
`wakeword_catalog.py` (die kanonische Authority selbst) und
`protocol_v2/*` sind in diesem Commit nicht enthalten (siehe Dateiliste
§6 und `git status --porcelain` vor dem Commit).

---

## 5. Geschützte Kompatibilitätsanker (`KEEP_REQUIRED`)

| S-ID | Anker | Status nach W1B |
|---|---|---|
| S09 | `activation_config.mode == "legacy"` | unverändert, nicht berührt |
| S10 | `_compat_final_context` | unverändert, nicht berührt |
| S11 | `_start_wakeword_followup_window` | unverändert, nicht berührt — trotz Wake-Namens bewusst kein Remove-Kandidat |
| S12 | `_trigger_ack` | unverändert, nicht berührt |
| S13 | v2→v1-Bridge (`_apply_activation_command`) | unverändert, nicht berührt |

---

## 6. Geänderte Dateien

| Datei | Art |
|---|---|
| `VoiceSTT/core/openwakeword_catalog.py` | **gelöscht** |
| `VoiceSTT/core/wakeword.py` | Legacy-Resolver auf kanonischen Katalog umgestellt |
| `VoiceSTT_server/operations.py` | `WakeWordRegistry` neu implementiert (Adapter über `WakeWordCatalogAuthority`) |
| `api_fastapi_server/server.py` | Konstruktionsreihenfolge (eine Authority-Instanz), impliziter Default entfernt, 6 Aufrufstellen angepasst |
| `VoiceSTT/assets/wakeword_models/models.json` | Legacy-Manifestspiegel entfernt |
| `tools/sync_wakeword_assets.py` | Generierung des Legacyspiegels entfernt |
| `docs/wake-words.md` | Vertragskorrektur (Legacy-Pfad-Abschnitt) |
| `docs/client-development/09-betriebsmodi-und-serverkonfiguration.md` | Vertragskorrektur (Default-Regeln, Manifestbeschreibung) |
| `docs/fastapi-server.md` | Vertragskorrektur (`GET /api/wake-word`-Beschreibung) |
| `docs/einheitliche-triggerarchitektur.md` | §14.11 aktualisiert |
| `tests/unit/test_server_operations.py` | Wake-Registry-Tests auf kanonischen Katalog umgeschrieben, RED-FIRST-Test für abgeschafften Default ergänzt |
| `tests/unit/test_wakeword.py` | Legacy-Resolver-Tests auf kanonischen Katalog umgeschrieben |
| `tests/unit/test_fastapi_server_protocol.py` | Fixture und 4 Tests umgeschrieben (Default-Abschaffung, Registry-Konstruktion) |
| `tests/unit/test_fastapi_server_multi_user.py` | 1 Test umgeschrieben, 1 neuer End-to-End-Ablehnungstest |
| `tests/unit/test_openai_compatible_endpoint.py` | Assertion von index-basiert auf mengenbasiert korrigiert (echter Bundled-Katalog statt Fake-Override) |

Keine Packaging-, Docker- oder Release-Automation-Änderungen. Keine
Client-Produktcode-Änderungen. Keine W2-Doku-Reorganisation.
