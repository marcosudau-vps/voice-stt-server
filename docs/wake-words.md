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
`artifact_missing`, `artifact_integrity_mismatch`, `artifact_unloadable`,
`pipeline_unavailable`, `runtime_unavailable`, `backend_unavailable`,
`no_common_backend`. Audio, triggers and wake detection stay locked until the
admission succeeded, and no partial session, no `sessionId` and no recorder
exist for a refused one.

After a successful admission **only the selected classifiers** are handed to
OpenWakeWord. Other models contained in the build cost neither RAM nor session
startup time. The two shared pipeline models (melspectrogram, embedding) belong
to the catalog and are passed once per session model instance, as the real
OpenWakeWord API requires.

### Catalog loadability

Availability is resolved by the catalog authority, at the initial load and at
every `POST /api/v2/wake-words/refresh`. A model is never `available: true`
merely because a file exists next to the manifest. Each refresh validates, for
every declared entry:

1. manifest/schema validity;
2. canonical ids, display names, aliases and their collisions;
3. the declared artifact integrity (`sha256`/`bytes`), where the manifest
   carries it;
4. **both** declared artifact formats;
5. runtime/provider availability per backend;
6. the shared OpenWakeWord pipeline assets of that backend;
7. a **real probe load** of every declared classifier artifact;
8. the resulting per-backend health;
9. one atomic, complete candidate snapshot;
10. last-known-good on any refresh failure.

Probing may instantiate a model briefly and release it again. That does not
weaken selected-only runtime loading: selected-only means that a *running*
session keeps only its actually selected classifiers in the live engine.

A model that cannot be loaded does **not** disappear from the public catalog.
It stays queryable with `available: false`, a machine-readable
`unavailableReason` and its per-backend `backends` block; only genuinely
available ids appear in `availableWakeWordIds`. No local paths, secrets or
loader internals are ever published.

### Dual inference backend

Every wake-word model of this build is meant to exist as `.onnx` **and**
`.tflite`. There is no per-model mixture inside one live engine: a session
runs **one** upstream `openwakeword.Model` and therefore exactly one common
inference backend for all of its selected wake words.

`wakeWord.inferenceBackend` (server, admin) selects the policy:

| value | Windows | Linux |
| --- | --- | --- |
| `auto` | ONNX preferred, TFLite/LiteRT as the common fallback | TFLite/LiteRT preferred, ONNX as the common fallback |
| `onnx` | ONNX only | ONNX only |
| `tflite` | TFLite/LiteRT only | TFLite/LiteRT only |

The fallback is always for the **whole** selection, never per model. An
explicitly requested backend never switches silently: if it is not healthy for
the full selection the session is rejected with `reason: backend_unavailable`.
Under `auto`, a selection whose models are individually healthy but share no
single backend is rejected with `reason: no_common_backend`.

A missing inference runtime is an unhealthy backend
(`reason: runtime_unavailable`), never a passed probe. Runtimes are deployment
dependencies; nothing is installed in the request path.

## Detection, latch and events

### What "1 wake word = 1 `wakeword.detected`" means

It is an **exactly-once eventing** rule for one spoken wake-word utterance. It
never meant that a single score frame is already a wake word. OpenWakeWord
emits a score per selected classifier on every prediction frame, and a spoken
wake word produces a whole *run* of frames above the threshold; those frames
are one logical hit and produce at most one domain event.

Earlier formulations in the C1/C2 documentation - "no multi-chunk rule", "no
5-of-10 hits", "an additional multi-chunk rule only with evidence" - read the
rule the other way round. They are withdrawn and replaced by the model below.

### Prediction frames, not recorder chunks

Detection works on real OpenWakeWord **prediction frames**, not on arbitrary
recorder or transport chunks. Upstream buffers audio internally and advances one
prediction per 1280 samples (80 ms at 16 kHz); a shorter chunk re-appends the
previous score. A recorder that delivers 20 ms or 40 ms therefore feeds several
chunks into the engine before exactly one new prediction frame - and one single
step of the hit tracker - comes out. A repeated or cached score is never counted
twice.

### The hit model

Two configurable, shared criteria:

| setting | meaning |
| --- | --- |
| `wakeWord.sensitivity` | the score threshold |
| `wakeWord.minConsecutivePredictionFrames` | how many consecutive prediction frames must reach that threshold |

Per selected wake word one contiguous run is tracked independently:

```text
score >= threshold        -> the run grows
below before the minimum  -> run discarded, counter reset, no hit, no event
minimum reached           -> the candidate is QUALIFIED (not yet the decision)
first frame below after
qualification             -> FINALIZED; its trailing edge closes the run
```

With a threshold of `0.70` and a minimum of `10` frames, the sequence

```text
0.73 0.78 0.81 0.85 0.88 0.90 0.91 0.89 0.86 0.83 0.79 0.75 0.71 0.62
```

is **one** contiguous hit - not 13 triggers and not 13 events.

### Multi-wake-word arbitration

Several wake words may be selected at once. The primary rule is
first-come-first-served: **the first qualified hit that finalizes wins.** If
both `alexa` and `alexander` qualify but the `alexa` run drops below the
threshold first, `alexa` wins. There is no artificial waiting period, no
"prefer the longer word" and no retrospective peak-score contest.

Only a theoretical tie - several qualified candidates finalizing in the *same*
prediction frame - needs a deterministic chain:

1. the earlier qualification wins;
2. on an equal qualification, the earlier run start wins;
3. on a full tie, the lexicographically smallest canonical id wins.

Once the winner is determined, exactly that hit is offered and every other
candidate of that decision is discarded.

### Raw observations versus accepted detections

- a **raw candidate/score** carries the canonical id, the raw score, its frame
  and sample position - it is diagnostics and never a domain event;
- an **accepted detection** carries the canonical id, the peak score of its hit
  region, the `activationId` that this very hit opened and the audio boundary
  it established.

A finalized hit becomes an activation only through the normal, source-neutral
activation admission:

```text
prediction frames -> hit region -> wake admission -> activation
```

Only if that admission succeeds does the server latch the detection, adopt the
accepted `activationId` and mint exactly one logical `wakeword.detected`. If
the activation is locked, suppressed or otherwise refused, there is **no**
event, no latch, no second activation and no source merge. A wake word spoken
during an open activation has no trigger, finish, cancel or refresh effect; its
audio is ordinary activation audio.

The latch is released at the safe input close of the same activation - not at
VAD end, not at segment end, not when a final inference starts or ends, and not
when a cooldown expires.

### Exactly-once eventing

Minting the logical event and delivering it are two separate steps:

| step | property |
| --- | --- |
| logical mint | exactly once per accepted hit, in-memory, cannot fail on a network, idempotent per `activationId` |
| transport delivery | explicitly fallible; may succeed, fail, or be picked up by the existing resync/replay/close semantics |

A transport failure therefore never leaves an accepted hit with zero logical
events, and a retry never produces a duplicate. There is no second event
authority.

### One attempt, one settings revision

Every value one wake attempt uses - `settingsRevision`, `sensitivity`,
`minConsecutivePredictionFrames`, `detectorGain`, `cooldownMs`, `preRollMs` -
is frozen as one snapshot at the prediction frame that starts a new run while
no other run is active. That snapshot governs the score comparison, the frame
counter, qualification, finalization, the pre-roll, the cooldown decision, the
accepted detection and the activation's effective settings. A patch landing
mid-utterance applies to the *next* attempt; a run that breaks before
qualification is discarded and the next one picks up the current revision.

### Cooldown

`wakeWord.cooldownMs` is an explicitly configured operator pause after an
accepted hit. It is **not** the grouping of one hit region - the tracker does
that without any timer - and it deliberately keeps running past the safe input
close, which is what an operator asked for. Its default is `0`.

The recorder additionally does not run the detector at all while a hit is
latched (FIND-011).

## Audio boundary and pre-roll

The transcript must not contain the wake word, and the first user word must not
be cut. The anchor is the **operational audio zero point**, a deliberate
server-side product definition.

The zero point is **not**:

- the first prediction frame above the threshold;
- the frame at which the minimum run length was reached;
- the end of a classifier receptive field;
- an externally annotated "true" phonemic wake-word end.

It **is** the **Trailing Edge** of the winning qualified hit region: the
transition from the last prediction frame with `score >= sensitivity` to the
first one below it.

```text
operationalZeroPointSample  trailing edge of the winning qualified hit
historyStartSample          oldest sample the session still holds
releaseSample               max(historyStartSample,
                                operationalZeroPointSample - preRollMs)
```

`wakeWord.preRollMs = 0` releases the audio exactly at the zero point, so the
wake word is excluded and the following user speech is preserved. A larger
pre-roll moves the release back and is clamped against the audio history that
really still exists - `preRollClamped` says when that happened. No upper bound
is derived from a classifier receptive field.

Every projection carries `boundaryBasis: "operational_zero_point"` and
`boundaryDefined: true`. The zero point itself is therefore defined, not
pending. What is still open is the **empirical calibration** - which threshold,
which minimum run length, which pre-roll, which cooldown, which gain are the
right operating points, and how they behave against false positives and false
negatives. That needs real positive wake-word recordings (WW-18/WW-19) and is
reported as **`EVIDENCE_BLOCKED`**.

The legacy `wake_word_buffer_duration` fixed-duration cut still exists for the
v1 recorder path and is removed with AP-SRV-070.

## Session settings

All wake values live in the one AP-SRV-050 settings plane under the
`wakeWord.*` namespace. There is no second wake-word settings management and no
fifth apply policy.

| Key | Scope | Auth | Range | Default | Apply |
| --- | --- | --- | --- | --- | --- |
| `wakeWord.selection` | session | session | ids | `[]` | `next_session` |
| `wakeWord.sensitivity` | session | session | 0.0-1.0 | 0.5 | `next_activation` |
| `wakeWord.minConsecutivePredictionFrames` | session | session | >= 1 | 1 | `next_activation` |
| `wakeWord.preRollMs` | session | session | >= 0 | 0 | `next_activation` |
| `wakeWord.cooldownMs` | session | session | >= 0 | 0 | `next_activation` |
| `wakeWord.detectorGain` | session | session | 0.0-3.0 | 1.0 | `next_activation` |
| `wakeWord.noiseSuppressionEnabled` | session | session | bool | `false` | `next_session` |
| `wakeWord.vadThreshold` | session | session | 0.0-1.0 | 0.0 | `next_session` |
| `wakeWord.inferenceBackend` | server | admin | `auto`/`onnx`/`tflite` | `auto` | `next_session` |
| `wakeWord.globalDisabledIds` | server | admin | ids | `[]` | `next_session` |
| `runtimeSuppression.wakeWord` | session | session | bool | `false` | `live` |

`wakeWord.minConsecutivePredictionFrames` counts only genuinely new prediction
frames. Its default `1` is a neutral, compatibility-near starting value - it is
**not** a claim that 1 is empirically optimal.

`wakeWord.cooldownMs` is the explicitly configured operator pause after an
accepted hit; it is not the internal grouping of one hit region. Neither it nor
`wakeWord.preRollMs` carries an upper bound derived from a receptive field: the
pre-roll's real limit is the retained audio history, applied as a runtime clamp.

`wakeWord.detectorGain` is applied to a **copy** of the PCM that only the wake
inference sees, with saturating int16 clipping:

```text
Original PCM
├─ unchanged -> recording / STT / audio history
└─ copy -> gain -> OpenWakeWordEngine
```

`wakeWord.vadThreshold` uses the OpenWakeWord-internal VAD gate ahead of the
wake inference; `0.0` disables it. `wakeWord.noiseSuppressionEnabled` uses the
existing OpenWakeWord/Speex support.

**The calibration keys are published as provisional.** Their schema entries
carry `constraints.calibration: "pending"` and the traceability ids they depend
on. `0`/`1`/`1.0` are neutral defaults, not recommendations. The calibrated
operating values require positive wake-word recordings; `WW-18` and `WW-19` are
**`EVIDENCE_BLOCKED`**, and a client must not present these values as a
calibrated contract.

## VAD lifecycle

There is one continuous server-authoritative lifecycle, not two:

```text
outside an activation   wake detector, optionally with its own OpenWakeWord VAD
accepted wake hit       ActivationController takes over
inside an activation    the existing speech/transcription pipeline runs, and
                        the wake source has no direct trigger effect
```

A wake-specific detector-side VAD ahead of the activation is explicitly allowed
and intended. What must never exist is a second, independent activation
pipeline: no client wake state machine next to the server one, and no competing
second trigger lifecycle.

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
