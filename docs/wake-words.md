# Wake Words

The `AudioToTextRecorder` library supports Porcupine and OpenWakeWord to wait
for a wake word before recording the following speech. The FastAPI server's
current admin, browser, and session contracts deliberately publish only
OpenWakeWord.

Install the OpenWakeWord extra:

```bash
python -m pip install "VoiceSTT[openwakeword]"
```

For the library-level Porcupine backend instead:

```bash
python -m pip install "VoiceSTT[porcupine]"
```

```python
from VoiceSTT import AudioToTextRecorder

recorder = AudioToTextRecorder(
    wakeword_backend="pvporcupine",
    wake_words="jarvis",
)
```

If `wake_words` is set without an explicit backend, the recorder selects
Porcupine for backward compatibility. This Porcupine path is a library feature;
it is not selectable through the current FastAPI session or admin contract.

## Bundled build catalog (protocol v2, AP-SRV-060)

The server ships its Wake Word models **inside the package**. There is no
runtime download on any path.

```text
VoiceSTT/assets/wakeword_models/
  models.json            canonical catalog manifest (v2 authority)
  melspectrogram.onnx    shared pipeline model
  embedding_model.onnx   shared pipeline model
  <classifier>.onnx      26 wake-word classifiers
```

`setup.py` and `MANIFEST.in` carry these assets into wheel and sdist, so a
package installed on Windows or on Ubuntu resolves them through
`importlib.resources` - never through a guessed path. A deployment that ships
the bundle elsewhere can point the server at it with:

```bash
VOICESTT_WAKEWORD_ASSET_ROOT=/opt/voicestt/wakeword_models
```

Only ONNX artifacts are bundled, so the v2 catalog resolves ONNX. The bundle is
regenerated reproducibly from an upstream model directory with:

```bash
python tools/sync_wakeword_assets.py --source S:/MODELS/openwakeword/resources/models/all_models
```

`--check` verifies the committed bundle against that source without writing.

### `models.json` is the authority

The manifest - not the directory listing - decides what this build offers. A
file that merely lies next to the manifest is reported as a diagnostic and
never becomes public build capability.

```json
{
  "manifestVersion": 2,
  "catalogRevision": 1,
  "pipeline": {
    "onnx": {
      "melspectrogram": {"file": "melspectrogram.onnx", "sha256": "...", "bytes": 1087958},
      "embedding": {"file": "embedding_model.onnx", "sha256": "...", "bytes": 1326578}
    }
  },
  "wakeWords": [
    {
      "id": "hey_jarvis",
      "displayName": "Hey Jarvis",
      "aliases": ["jarvis"],
      "artifactVersion": "1",
      "artifacts": {
        "onnx": {"file": "jarvis_v2.onnx", "sha256": "...", "bytes": 208134}
      }
    }
  ]
}
```

`artifactVersion` is the bundle revision of that artifact and is raised when
its bytes are replaced; `sha256` records the verifiable byte identity.

A manifest that fails validation - a schema error, a missing field, a
non-canonical id or an id/alias collision - is refused as a whole. The running
catalog then keeps its last known good state.

### IDs, display names, aliases and normalisation

Every wake word has one canonical, lower-case snake-case id.

**The v2 wire carries canonical ids only.** `requestedSession.wakeWordIds` is
not a place for aliases or display names: a value that is not already a
canonical id rejects the whole session with `reason: not_canonical`. A UI
resolves what the user typed against `GET /api/v2/wake-words` and then sends
the `id`.

The tolerant resolver below therefore serves **human configuration only** -
`wakeWord.selection` in the settings control plane, config files and admin
input. It is exactly one resolver, which

1. Unicode-normalises (NFKC),
2. trims the outside,
3. compares case-insensitively (casefold),
4. folds every run of `_`, `-`, `.` and whitespace into a single `_`,
5. matches only against canonical ids, display names and **explicit** aliases.

All of these therefore resolve to the same wake word:

```text
hey_jarvis   Hey Jarvis   HEY-JARVIS   hey.jarvis   hey__jarvis
```

The frozen contract forbids heuristically dropping "Hey". `jarvis` resolves to
`hey_jarvis` **only** because the manifest lists `jarvis` as an explicit alias,
and **only in configuration** - the same value on the wire is rejected. A wake
word without an alias has no short form. After normalisation, ids, display
names and aliases must be collision-free; a collision is a catalog error and is
never resolved by ordering, file name or best match.

### Global disable

`wakeWord.globalDisabledIds` (server scope, `X-Admin-Key`, AP-SRV-050) removes
entries from availability without removing them from the catalog. They stay
visible as `available: false` with `unavailableReason: globally_disabled`, and
a session that selects one is refused.

### Public catalog API

```text
GET /api/v2/wake-words
```

Publicly readable, no key required:

```json
{
  "protocolVersion": 2,
  "catalogRevision": 1,
  "wakeWords": [
    {
      "id": "hey_jarvis",
      "displayName": "Hey Jarvis",
      "aliases": ["jarvis"],
      "artifactVersion": "1",
      "available": true,
      "catalogRevision": 1
    }
  ]
}
```

Every entry carries the `catalogRevision` of the snapshot it came from, so an
entry can never be paired with the wrong top-level revision. An unavailable
entry additionally carries `unavailableReason` (`globally_disabled`,
`artifact_missing` or `pipeline_unavailable`). The payload never contains
filesystem paths, source markers or internal artifact maps.

`catalogRevision` is separate from `settingsRevision` and rises only when the
publicly visible catalog actually changed.

### Catalog hot refresh

```text
POST /api/v2/wake-words/refresh
```

Behind the same `X-Admin-Key` guard as the v2 server settings. The refresh
reads the manifest and artifacts again, builds a complete candidate, validates
schema, ids, aliases, collisions and files, and swaps atomically only on total
success. On any failure the last known good catalog stays in place unchanged
and the response reports `ok: false` with a reason (HTTP 422).

`catalogRevision` rises only on a visible change, and **every** such change -
a new or removed id, a renamed display name, a new alias, a new
`artifactVersion` - emits `wakeword.availability_changed` on every live v2
session with the new revision and the current `availableWakeWordIds`. The event
is the catalog-change seam of the frozen contract, so it is deliberately
broader than its name. A refresh never touches an already admitted session or
the models it has initialised - it takes effect for new session admissions.

The whole refresh, including the projection of the global disable list, happens
as one atomic catalog operation, and the HTTP response is rendered from exactly
the snapshot that operation committed.

## Session admission and selected-only initialisation

A v2 session declares its wake words in the `hello` handshake:

```json
"requestedSession": {
  "trigger": {"manual": true, "wakeWord": true},
  "wakeWordIds": ["hey_jarvis"]
}
```

Admission is **atomic**. A single non-canonical, unknown, globally disabled,
missing or unloadable id rejects the whole selection with `session.rejected`;
there is no partial load, no default fallback and no silent removal. Before a
session is accepted the server really loads-probes exactly the selected
classifiers and the shared pipeline models with the inference runtime, so a
file that exists but is corrupt is refused *before* `hello.accepted` rather
than crashing the session build later. Every problematic id is named:

```json
{
  "field": "requestedSession.wakeWordIds",
  "code": "wake_word_unavailable",
  "reason": "unknown",
  "message": "...",
  "wakeWordId": "does_not_exist"
}
```

`reason` is one of `not_canonical`, `unknown`, `globally_disabled`,
`artifact_missing`, `artifact_unloadable`, `pipeline_unavailable`. Audio,
triggers and wake detection stay locked until the admission succeeded, and no
partial session, no `sessionId` and no recorder exist for a refused one.

After a successful admission **only the selected classifiers** are handed to
OpenWakeWord. Other models contained in the build cost neither RAM nor session
startup time. The two shared pipeline models (melspectrogram, embedding) belong
to the catalog and are passed once per session model instance, as the real
OpenWakeWord API requires.

## Detection, latch and events

Raw detector observations and accepted detections are strictly separated:

- a **raw candidate** carries the canonical id, the raw score, its frame and
  sample position and the detector generation - it is diagnostics and never a
  domain event;
- an **accepted detection** carries the canonical id, the score, the
  `activationId` that this very hit opened and the audio boundary it
  established.

Several models above the threshold in the same chunk: the highest valid score
wins; on an exact tie the lexicographically smallest canonical id wins.

A candidate becomes an activation only through the normal, source-neutral
activation admission:

```text
raw candidate -> detection evaluation -> wake admission -> activation
```

Only if that admission succeeds does the server latch the detection, adopt the
accepted `activationId` and publish exactly one `wakeword.detected`. If the
activation is locked, suppressed or otherwise refused, there is **no** event, no
latch, no second activation and no source merge. A wake word spoken during an
open activation has no trigger, finish, cancel or refresh effect; its audio is
ordinary activation audio.

The latch is released at the safe input close of the same activation - not at
VAD end, not at segment end, not when a final inference starts or ends, and not
when a cooldown expires.

### Duplicates, de-duplication and cooldown (FIND-011)

One spoken wake word produces exactly one detection. Two things guarantee that:

- the recorder no longer runs the detector for the following chunks while a hit
  is latched;
- an implicit **de-duplication window** covers the *measured* receptive field of
  the models actually selected, so the same acoustic hit is not offered twice.

OpenWakeWord advances one embedding frame per 1280 samples (80 ms at 16 kHz) and
its embedding model consumes 76 melspectrogram frames (760 ms), so a classifier
with `N` input frames still sees the same utterance for `(N - 1) * 80 + 760` ms.
Across the bundled build that is 1960 ms at minimum and 3400 ms at maximum. No
arbitrary "2 of 3" or "5 hits" rule is applied.

De-duplication and cooldown are **not** the same thing:

| | de-duplication window | `wakeWord.cooldownMs` |
| --- | --- | --- |
| origin | implicit, measured receptive field | explicitly configured |
| purpose | never offer one acoustic hit twice | deliberate operator pause |
| safe input close | **cleared** | kept |

The de-duplication window is cleared at the safe input close of the activation
it guarded. After that close a new, clearly separate utterance is admissible
immediately - the window must never become a hidden second foreground lock. A
configured cooldown is different: it is a deliberate post-close pause and keeps
running, which is exactly what an operator asked for. Its default is `0`.

## Audio boundary and pre-roll

The transcript must not contain the wake word, and the first user word must not
be cut. Five things are kept apart, and only the first two are measured:

| | status |
| --- | --- |
| detection sample | **measured** - where the classifier decided |
| model receptive field | **measured** - what that classifier had in view |
| estimated wake end | **estimated** - currently equated with the detection sample |
| speech start | not derived here at all |
| release boundary | computed from the above |

```text
detectionSample            measured position of the accepted decision
receptiveFieldStartSample  detectionSample - measured receptive field
estimatedWakeEndSample     currently == detectionSample   (estimate)
releaseSample              max(receptiveFieldStartSample,
                               estimatedWakeEndSample - preRollMs)
```

The boundary is anchored to a **real sample position** instead of a configured
duration, which is a genuine improvement over the legacy fixed cut. It is
nevertheless an *estimate*: a classifier cannot decide before the wake word is
over, so its decision point is at or after the acoustic end - but by how much it
lags has not been measured. Every projection says so through `boundaryBasis`
(`detection_sample_estimate`) and `boundaryMeasured` (`false`). Establishing the
real acoustic wake end is WW-19 and needs real positive wake-word recordings;
until then it is **`EVIDENCE_BLOCKED`** and no value here may be read as a
proven acoustic boundary.

With `wakeWord.preRollMs = 0` the transcript starts at the estimated wake end.
A larger pre-roll moves the release back but never past the start of the
classifier's own view.

The legacy `wake_word_buffer_duration` fixed-duration cut still exists for the
v1 recorder path and is removed with AP-SRV-070.

## Session settings

| Key | Scope | Auth | Range | Default | Apply |
| --- | --- | --- | --- | --- | --- |
| `wakeWord.selection` | session | session | ids | `[]` | `next_session` |
| `wakeWord.sensitivity` | session | session | 0.0-1.0 | 0.5 | `next_activation` |
| `wakeWord.cooldownMs` | session | session | 0-3400 | 0 | `next_activation` |
| `wakeWord.preRollMs` | session | session | 0-1960 | 0 | `next_activation` |
| `wakeWord.globalDisabledIds` | server | admin | ids | `[]` | `next_session` |
| `runtimeSuppression.wakeWord` | session | session | bool | `false` | `live` |

`wakeWord.cooldownMs` is an explicitly configured pause **next to** the
implicit de-duplication window, not a replacement for it; `0` means "no
configured cooldown".

**Both keys are published as provisional.** Their schema entries carry
`constraints.calibration: "pending"` and the traceability ids they depend on.
The numeric bounds are measured receptive fields used as input guard rails so a
value cannot be absurd - a receptive field is *not* a calibrated operating
range, and `0` is a neutral default, not a recommendation. The real range and
default require positive wake-word recordings; `WW-18` and `WW-19` are
**`EVIDENCE_BLOCKED`**, and a client must not present these values as a
calibrated contract.

## Legacy path (until AP-SRV-070)

Everything below describes the v1/library path. It stays functional but is no
longer the v2 catalog authority, and it is retired in AP-SRV-070.

## Local model catalog (legacy)

VoiceSTT never downloads Wake Word assets at runtime. It first looks for a
`models.json` beside the configured model directory. Set the search root with:

```bash
VOICESTT_OPENWAKEWORD_MODEL_ROOT=/models/openwakeword
```

Relevant manifest structure:

```json
{
  "openwakeword_models": {
    "path": "/models/openwakeword/all_models",
    "default_model": "alexa",
    "pipeline_models": {
      "embedding_model_onnx": "embedding_model.onnx",
      "melspectrogram_onnx": "melspectrogram.onnx",
      "embedding_model_tflite": "embedding_model.tflite",
      "melspectrogram_tflite": "melspectrogram.tflite"
    },
    "onnx_models": {
      "alexa": "alexa.onnx",
      "hey_jarvis": "jarvis_v2.onnx"
    },
    "tflite_models": {
      "alexa": "alexa.tflite"
    }
  }
}
```

The dictionary keys are stable logical Wake Word IDs; the values are local
filenames. Only entries whose files exist are exposed. Pipeline models and
support files such as `silero_vad` are not selectable Wake Words.

The manifest `path` is tried first. If that platform-specific path is not
available in the running container or host, VoiceSTT also checks the configured
model root and the manifest directory. This allows the same generated manifest
to remain usable after a model directory is mounted at a different path.

`openwakeword_model_paths` remains backward compatible. It may contain:

- one or more comma-separated `.onnx` or `.tflite` classifier paths;
- a directory containing models and optionally `models.json`;
- the path to `models.json` itself.

Without a usable manifest, VoiceSTT falls back to scanning local `.onnx` and
`.tflite` files. A manifest is recommended because it provides exact logical
IDs, the default model and pipeline-file mappings.

## Python recorder (legacy)

Direct classifier paths remain supported:

```python
from VoiceSTT import AudioToTextRecorder

if __name__ == "__main__":
    recorder = AudioToTextRecorder(
        wakeword_backend="openwakeword",
        openwakeword_model_paths="/models/openwakeword/alexa.onnx",
        wake_words="alexa",
        wake_words_sensitivity=0.35,
        wake_word_buffer_duration=1.0,
    )
    print(recorder.text())
    recorder.shutdown()
```

Using the manifest:

```python
recorder = AudioToTextRecorder(
    wakeword_backend="openwakeword",
    openwakeword_model_paths="/models/openwakeword/models.json",
    wake_words="hey_jarvis",
)
```

Model IDs are resolved case-insensitively. An empty `wake_words` value selects
`default_model` when the manifest is used.

Supported inference frameworks are `onnx` and `tflite`, selected with
`openwakeword_inference_framework`.

## FastAPI session-local configuration (legacy v1 endpoint)

The v1 WebSocket endpoint resolves Wake Word configuration before creating the
session recorder. It keeps its historical fallback behaviour; the atomic v2
admission described above does **not** use it:

```text
/ws/transcribe?wakeWordEnabled=false
/ws/transcribe?wakeWordEnabled=true
/ws/transcribe?wakeWordEnabled=true&wakeWords=hey_jarvis
```

Clients send logical model IDs, not filesystem paths. The effective result,
fallbacks and available IDs are returned in `hello.sessionConfig` and
`hello.sessionCapabilities`. A session can choose a locally available ONNX or
TensorFlow Lite variant with `wakeWordInferenceFramework=onnx` or
`wakeWordInferenceFramework=tflite`.

See
[Betriebsmodi und sessionlokale Wake-Word-Konfiguration](client-development/09-betriebsmodi-und-serverkonfiguration.md)
for the complete contract.

## Sensitivity and timing

| Parameter | Default | Meaning |
| --- | --- | --- |
| `wake_words_sensitivity` | `0.6` | Detection threshold from `0` to `1`; lower values can increase false positives |
| `wake_word_activation_delay` | `0.0` | Delay before entering Wake Word mode when no initial speech is detected |
| `wake_word_timeout` | `5.0` | Seconds to wait for speech after detection |
| `wake_word_buffer_duration` | `0.1` | Audio removed/buffered around detection |
| `wake_word_followup_window` | server setting | Window in which follow-up speech can continue |

A sensitivity around `0.35` can be a useful starting point for custom models,
but it must be tuned against real microphones and room noise.

## Callbacks

```python
def detected():
    print("wake word detected")


def timeout():
    print("wake word timeout")


recorder = AudioToTextRecorder(
    wakeword_backend="openwakeword",
    openwakeword_model_paths="/models/openwakeword/models.json",
    on_wakeword_detected=detected,
    on_wakeword_timeout=timeout,
)
```

Available callbacks:

- `on_wakeword_detection_start`
- `on_wakeword_detection_end`
- `on_wakeword_detected`
- `on_wakeword_timeout`

## Troubleshooting

- Confirm that the manifest and every referenced classifier/pipeline file are
  readable inside the current host or container.
- Check `default_model` against the logical keys, including spelling.
- Use the admin Wake Word catalog or WebSocket `sessionCapabilities` to see
  which models passed validation.
- Raise sensitivity if false activations are common; lower it if detections are
  consistently missed.
- Increase `wake_word_buffer_duration` if the Wake Word appears in the final
  transcript (legacy path only; the v2 path derives the boundary from the
  accepted detection and needs no such tuning).
- On the v2 path, check `GET /api/v2/wake-words` for `available` and
  `unavailableReason`, and use `POST /api/v2/wake-words/refresh` after changing
  the bundle on disk.
