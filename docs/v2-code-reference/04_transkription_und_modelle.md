# 04 – Transkription und Modelle

## 1. Zwei Inferenz-Lanes: Final und Realtime

Jede Sitzung erzeugt zwei Arten von Inferenzjobs (`InferenceJob.kind`):

| Lane | Zweck | Engine-Einstellung | Modell-Einstellung |
| --- | --- | --- | --- |
| `final` | Endgültiger Text eines abgeschlossenen Segments | `transcription_engine` (Default `faster_whisper`) | `model` (Default `small`) |
| `realtime` | Zwischenstände während des Sprechens | `realtime_transcription_engine` (Default `kroko_onnx`) | `realtime_model` (Default `Kroko-DE-Community-64-L-Streaming-001.data`) |

Ist Engine und Modell beider Lanes gleich, setzt `enforce_cpu_model_policy`
`use_main_model_for_realtime = True` (`server.py:8768`); der Scheduler läuft
dann im Modus `low-memory-one-model` mit nur einer Queue, sonst im Modus
`balanced-main-plus-realtime` (`InferenceScheduler.snapshot`, `server.py:2214`).

### Fairness und Gegendruck (`FairInferenceQueue`, `server.py:1780`)

- Sitzungen werden reihum bedient (`_ordered_sessions`).
- **Final-Jobs** stehen je Sitzung in einer Deque. Abgelehnt, wenn die
  Sitzungsdeque `max_final_queue_depth_per_session` (8) erreicht oder die
  globale Tiefe `max_global_inference_queue_depth` (64) erreicht ist.
- **Realtime-Jobs**: höchstens **einer** pro Sitzung. Ein neuer Job ersetzt
  den wartenden (`coalesced`, Zähler `coalescedRealtime`). Abgelaufene Jobs
  (`deadline_at` überschritten, gesteuert über `max_realtime_queue_age_ms`)
  werden beim Abholen verworfen (`staleRealtimeDropped`).
- Final-Jobs haben beim Abholen Vorrang vor dem Realtime-Slot derselben Sitzung.

Kennzahlen sind in `GET /api/metrics` und `GET /health` unter `scheduler`
sichtbar (beobachtet: Felder `queued`, `sessions`, `perSession`,
`coalescedRealtime`, `staleRealtimeDropped`, `rejectedJobs` je Queue sowie
`ready`, `healthy`, `completedJobs`, `failedJobs`, `busyRatio`, `queueDelay`,
`inferenceDuration`, `totalLatency` je Worker).

### Realtime-Text

`--realtime-callback update` (Default) liefert rohe Zwischenstände;
`stabilized` schaltet den Recorder-Callback auf
`on_realtime_transcription_stabilized` um (`server.py:2769ff.`). Die
Stabilisierung selbst implementiert `VoiceSTT/core/realtime_text_stabilizer.py`
(`RealtimeTextStabilizer`); sie liefert u. a. `stableText`, `stableDelta`,
`unstableText`, `committedStableText`. Ein optionaler akustischer
Grenzdetektor (`RealtimeSpeechBoundaryDetector`, 10-ms-Log-Energie-Hüllkurve,
heuristisch) wird mit `--realtime-use-syllable-boundaries` aktiviert.

## 2. Engines

V2 unterstützt **genau zwei** Transkriptions-Engines.
`VoiceSTT/transcription_engines/factory.py` registriert in
`ENGINE_CLASS_PATHS` ausschließlich:

| Engine-Kennung | Klasse | Modul |
| --- | --- | --- |
| `faster_whisper` | `FasterWhisperEngine` | `VoiceSTT/transcription_engines/faster_whisper_engine.py` |
| `kroko_onnx` | `KrokoOnnxEngine` | `VoiceSTT/transcription_engines/kroko_onnx_engine.py` |

Regeln:

- Namen werden nur normalisiert (Kleinschreibung, `-` → `_`); es gibt
  **keine** Aliase mehr (`kroko`, `banafo_kroko` wurden entfernt).
- `get_supported_transcription_engines()` liefert `["faster_whisper",
  "kroko_onnx"]`; `GET /api/config` und das V1-`hello` geben genau diese
  Liste als `supportedEngines` aus.
- Jeder andere Name führt in `create_transcription_engine` zu
  `UnsupportedTranscriptionEngineError` mit dem Text
  „Unsupported transcription engine '<name>'. Supported engines:
  faster_whisper, kroko_onnx“.
- Serverseitig prüft `enforce_supported_engines` (aufgerufen von
  `enforce_cpu_model_policy`) beide Lanes **vor** jedem Engine-Import:
  beim Start (`create_app`), bei `POST /api/config/validate` und bei
  `PUT /api/models/active` (dort `400`).

Beide Engines sind in Modellverwaltung (`FasterWhisperAdapter`,
`KrokoAdapter`) und CPU-Speicherrichtlinie (`model_size_rank`) eingebunden.

**Nicht Teil des Produkts:** Fünf frühere Adapter liegen nur noch als
nicht paketierte Entwürfe unter `engineering/drafts/transcription_engines/`
(kein `__init__.py`, per `prune engineering` aus sdist ausgeschlossen, nicht
in `find_packages`). Sieben weitere wurden entfernt. Diese Grenze prüft
`tests/unit/test_v2_engine_boundary.py`; die gebauten Archive prüft
`tests/packaging/test_v2_distribution_contents.py`.

## 3. CPU-Modellrichtlinie

`enforce_cpu_model_policy` (`server.py:8768`) mit `model_size_rank`
(`server.py:8735`):

- Kroko-Modelle: Rang 2. faster-whisper: `tiny`/`base` 1, `small` 2,
  `medium` und das originale `large-v3-turbo` 3, andere `large` 4.
- Gilt nur, wenn zwei verschiedene Modelle geladen werden
  (`use_main_model_for_realtime = False`) und `model_memory_policy_enabled`
  aktiv ist.
- Abgelehnt wird, wenn ein Rang > 3 vorkommt oder mehr Modelle mit Rang ≥ 3
  geladen würden als erlaubt (2 mit `allow_two_medium_models`, sonst 1).
- Zusätzlich `enforce_kroko_single_identity`: Final und Realtime dürfen nicht
  zwei **verschiedene** Kroko-Modelle verwenden; dasselbe Modell wird geteilt
  (`api_fastapi_server/kroko_runtime.py`).

## 4. Modellverwaltung (`VoiceSTT_server/stt_model_management.py`)

### Produktautorität

`default_product_authority()` baut die bekannten Modelle aus festen Fakten:

- 11 faster-whisper-IDs (`faster-whisper-tiny` … `faster-whisper-large-v3-turbo`),
  `rights_status = LOCAL_ONLY_UNPINNED`, `provisioning_allowed = False`.
- 12 Kroko-Einträge aus `VoiceSTT/assets/kroko/models.json`:
  4 Community-Modelle (`kroko-{de,en}-community-{64,128}-l`,
  `redistributionStatus = POLICY_REQUIRED`, Laufzeitvariante `free`) und
  8 Pro-Modelle (`kroko-de-pro-{16,32,64,128}-{m,l}`, `PROHIBITED`,
  Laufzeitvariante `pro`).
- Wiederherstellungs-Prioritäten: `faster-whisper-tiny` 300,
  `faster-whisper-small` 200, `kroko-de-community-64-l` 100.

**Beobachtet:** Mit dem ausgelieferten Manifest ist für **keines** der 23
Modelle `provisioning_allowed` wahr (lokal ausgewertet). Automatischer Download
(`stt_auto_download_enabled`) kann daher derzeit nichts installieren; ein
Versuch erzeugt die Diagnose `result: "blocked_ineligible"`
(`STTModelManager._provision`). Modelle müssen lokal bereitgestellt werden.

### Suchwurzeln (`discovery_roots`)

Je Engine in dieser Reihenfolge, Duplikate entfernt:

1. `stt_engine_settings.<engine>.custom_paths` (oder `paths`)
2. `VOICESTT_FASTER_WHISPER_MODEL_ROOT` bzw. `VOICESTT_KROKO_MODEL_ROOT`
3. `<runtime_root>/models/stt/fasterwhisper` bzw. `.../kroko_asr`

### Zustände

Kandidaten: `DISCOVERED` → `VALIDATED` → `LOAD_VERIFIED`. Gesamtbereitschaft:
`MINIMUM_READY`, sobald für beide Rollen `final` und `realtime` ein aktiver
Kandidat existiert, sonst `NOT_READY` (`REQUIRED_ROLES`, Zeile 873f.). Öffentlich
als `state` ∈ `ready_complete`, `ready_optional_provisioning`,
`ready_optional_errors` bzw. nicht bereit, plus `minimumReady`, `active`,
`candidates` (`ModelSnapshot.public_dict`).

### Operator-Intent

`OperatorIntent.from_settings` liest `stt_auto_download_enabled`,
`stt_engine_settings` (je Engine `enabled`, `auto_download_enabled`,
`custom_paths`, optional `provisioning_target`) und `stt_model_settings`
(je Modell-ID `enabled`, `auto_download_enabled`, `recovery_priority`).
Beispiel aus der Root-`config.yaml`:

```yaml
stt_engine_settings:
  faster_whisper: {enabled: true, auto_download_enabled: false, custom_paths: []}
  kroko_onnx: {enabled: true, runtime_variant: free, auto_download_enabled: false, custom_paths: []}
```

### Provisionierung (falls freigegeben)

`AtomicModelProvisioner` installiert nur Dateien mit fester `sha256`, `bytes`
und Quelle; `ProductModel.__post_init__` verweigert provisionierbare Modelle
ohne diese Angaben und Dateinamen mit Pfadanteilen.

## 5. Modell-Lebenszyklus und -Wechsel (HTTP, Admin)

| Aktion | Route | Verhalten |
| --- | --- | --- |
| Status | `GET /api/models`, `GET /api/models/active`, `GET /api/models/lifecycle`, `GET /api/models/management` | Katalog ohne Dateipfade, aktive Modelle, Leerlaufstatus |
| Laden/Entladen | `POST /api/models/load`, `POST /api/models/unload` | per `asyncio.to_thread`; Fehler `500` bzw. `409` |
| Wechseln | `PUT /api/models/active` | erlaubte Felder: `model`, `realtime_model`, `transcription_engine`, `realtime_transcription_engine`, `use_main_model_for_realtime`, `language`, `transcription_engine_options`, `realtime_transcription_engine_options`; andere → `400` |
| Lebenszyklus | `PUT /api/models/lifecycle` | `automaticUnloadEnabled`, `idleTimeoutSeconds` (≥ 1), `memoryPolicyEnabled`, `allowTwoMediumModels` (bzw. snake_case) |
| Refresh | `POST /api/models/refresh` | Neuaufbau des Modellsnapshots; Fehler `409` |

Ein Wechsel ohne explizites `use_main_model_for_realtime` setzt dieses auf
`False` und prüft danach die CPU- und Kroko-Regeln erneut
(`_switch_models_locked`, `server.py:8076`). Hinweis: Der Route-Handler mappt
`RuntimeError` mit dem Text „keine WebSocket-Sitzungen“ auf `409`; ein solcher
Text wird im Produktionscode derzeit nirgends erzeugt, daher endet ein
`RuntimeError` beim Wechsel faktisch mit `500`.

Leerlauf-Entladung: `model_idle_unload_enabled` (Default an),
`model_idle_timeout_seconds` (Default 3600). Beobachtet in `/health`:
`models.state`, `automaticUnloadEnabled`, `idleTimeoutSeconds`,
`idleSecondsRemaining`, `mediumEquivalentLimit`, `active`.

## Primäre Quellen

- [`VoiceSTT/transcription_engines/factory.py`](../../VoiceSTT/transcription_engines/factory.py) – `ENGINE_CLASS_PATHS`, `create_transcription_engine`
- [`VoiceSTT_server/stt_model_management.py`](../../VoiceSTT_server/stt_model_management.py) – `ProductModel`, `default_product_authority`, `STTModelManager`, `AtomicModelProvisioner`
- [`api_fastapi_server/server.py`](../../api_fastapi_server/server.py) – `FairInferenceQueue`, `InferenceScheduler`, `model_size_rank`, `enforce_cpu_model_policy`, `switch_models`
- [`api_fastapi_server/kroko_runtime.py`](../../api_fastapi_server/kroko_runtime.py) – `enforce_kroko_single_identity`
- [`VoiceSTT/kroko/models.py`](../../VoiceSTT/kroko/models.py), [`VoiceSTT/assets/kroko/models.json`](../../VoiceSTT/assets/kroko/models.json)
- [`VoiceSTT/core/realtime_text_stabilizer.py`](../../VoiceSTT/core/realtime_text_stabilizer.py), [`VoiceSTT/core/realtime_boundary_detector.py`](../../VoiceSTT/core/realtime_boundary_detector.py)
- Tests: [`tests/unit/test_stt_model_management.py`](../../tests/unit/test_stt_model_management.py), [`tests/unit/test_kroko_model_authority.py`](../../tests/unit/test_kroko_model_authority.py), [`tests/unit/test_fastapi_server_multi_user.py`](../../tests/unit/test_fastapi_server_multi_user.py), [`tests/unit/test_realtime_text_stabilizer.py`](../../tests/unit/test_realtime_text_stabilizer.py), [`tests/unit/test_faster_whisper_engine.py`](../../tests/unit/test_faster_whisper_engine.py), [`tests/unit/test_kroko_onnx_engine.py`](../../tests/unit/test_kroko_onnx_engine.py), [`tests/unit/test_v2_engine_boundary.py`](../../tests/unit/test_v2_engine_boundary.py), [`tests/unit/test_local_model_resolver.py`](../../tests/unit/test_local_model_resolver.py)
