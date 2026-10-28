# Kroko-ONNX

`kroko_onnx` uses the embedded
[kroko-ai/kroko-onnx](https://github.com/kroko-ai/kroko-onnx) runtime with
Kroko/Banafo streaming `.data` models. The adapter is lazy-loaded, so normal
developer checkouts and mock tests need no native import. The public V2 product
`voice-stt-server` already includes the Pro-capable runtime.

Build and licensing procedures are centralized in
[`build/BUILD.md`](../build/BUILD.md#kroko-im-detail). This engine page
describes runtime configuration and tests; if a command here conflicts with
the central build guide, the build guide is authoritative.

## Engine Names

- `kroko_onnx`
- `kroko`
- `banafo_kroko`

Hyphenated CLI forms such as `kroko-onnx` and `banafo-kroko` are accepted by
the generic engine-name normalization.

## Install

Install `voice-stt-server` on CPython 3.12 Linux x86-64 or Windows AMD64.
The wheel already contains Kroko; operators need no separate native build.
Community models work without a license key. Pro models require valid permission
for the actual model UUID. `runtime_variant=pro` and key presence do not establish
native capability; installed product/native provenance does.

Contributor-only native build procedures remain in
[build/BUILD.md](../build/BUILD.md#kroko-im-detail). They are not an additional
public product. [Redistribution approval](licenses.md#unified-v2-release-gate)
remains separate from technical license checks.

### Pinned builder inputs

The Windows cross-build image is defined by source-controlled pins in
`VoiceSTT/kroko/buildinputs.py`: the base image manifest digest, one immutable
Ubuntu archive snapshot for every apt package, exact versions for the Python
packaging tools, and a version plus SHA-256 for every downloaded binary
(CMake, xwin, the Windows CPython target, the VC++ redistributable, OpenSSL
and openfst). Those same values are what the build fingerprint records as its
Windows toolchain authority, so a build cannot use a toolchain the fingerprint
does not describe.

This has one practical consequence for operators: **a pinned source that
disappears fails the build on purpose.** The builder never falls back to a
different version, because that would change the produced runtime while the
fingerprint - and therefore the cached artifact - stayed the same. Update the
affected constant in `VoiceSTT/kroko/buildinputs.py` deliberately, together
with its SHA-256; that moves the fingerprint and forces exactly one new
qualified build.

Windows requirements:

- Python 3.12 x64
- Git
- Docker Desktop running with the WSL2 backend

If the default builder cache is not writable, use a project-local work
directory:

```powershell
stt-install-kroko --build --variant free --work-dir .\kroko-builder-work
```

If the default builder cache is not writable and `--work-dir` is not set, the
helper falls back to `.\kroko-builder-work` automatically and prints the path it
selected.

Linux requirements:

- Git
- CMake
- A working C/C++ build toolchain
- OpenSSL development headers and libraries (`libssl-dev` on Ubuntu)

The Linux fingerprint records the effective OpenSSL development identity:
resolution source (system stack or explicit `--openssl-root-dir` /
`OPENSSL_ROOT_DIR`), version, concrete header/library paths and their hashes.
A missing development stack fails before compilation with an actionable
message. zlib is not added as a separate fingerprint field: the current Kroko
Linux build does not consume a separately selected zlib development input, so
recording an ambient zlib version would create false cache misses rather than
describe the produced runtime.

Linux output wheels are retagged consistently in both places required by the
wheel format: the filename and the internal `.dist-info/WHEEL` metadata carry
`1free` or `1pro`. The RECORD hash/size for the changed metadata is regenerated
before the result is atomically published. Free and Pro wheels therefore
coexist in separate artifact-store namespaces and cannot overwrite each other.

Verified artifact slots are retained for 30 days by default. Configure this
with `--artifact-retention-days` or
`VOICESTT_KROKO_ARTIFACT_RETENTION_DAYS`; `0` disables cleanup. Cleanup is
best-effort and never removes the current fingerprint, the newest verified
last-known-good slot, the other runtime variant, or a slot whose artifact lock
is held.

After the builder finishes, download a public Community model:

```powershell
New-Item -ItemType Directory -Path test-model-cache\kroko-onnx -Force
python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='Banafo/Kroko-ASR', filename='Kroko-EN-Community-64-L-Streaming-001.data', local_dir='test-model-cache/kroko-onnx')"
```

Use `--variant pro` when you need licensed Pro models:

```bash
stt-install-kroko --build --variant pro
```

The `free` variant is for public Community models. The `pro` variant is for
licensed Pro/private models and may need network access for Kroko's license
check.

At server runtime the variant is selected independently from credentials. The
precedence is `stt_engine_settings.kroko_onnx.runtime_variant`, then the final
Kroko engine option, then the realtime Kroko engine option, then
`VOICESTT_KROKO_VARIANT`, and finally `free`. A Kroko API key is only a runtime
credential; its presence never selects Pro and never changes model eligibility.

## Models

Kroko models are described by the model authority in
`VoiceSTT/assets/kroko/models.json` (AP-SRV-070 W4A). It pins each known
model's identity, SHA-256, byte size, license class and the Kroko runtime
variant (`free`/`pro`) it requires. The manifest ships metadata only - **no
Kroko model file is bundled** in Git, in the wheel/sdist or in an image.

The [offline model catalog](kroko-model-catalog.md) adds typed discovery,
filtering and download planning for cleaned provider metadata. Catalog
visibility and a download URL do not grant model rights or verify bytes.
The existing twelve-model manifest remains the integrity authority.

### Why models are provisioned rather than shipped

The upstream redistribution grant is not unambiguous: the Hugging Face model
card declares `license: other` with `license_name: test` and links a `LICENSE`
file that is empty upstream, while the README prose calls the Community models
CC-BY-SA. An empty license file with a placeholder name is not a dependable
basis for redistribution, so every Community entry carries
`redistributionStatus: POLICY_REQUIRED` and nothing is redistributed. The
recorded evidence lives in the manifest's `licensePolicy` block; once upstream
publishes a clear license, the status can be raised to `ALLOWED`.

### Provisioning

Point `VOICESTT_KROKO_MODEL_ROOT` at the directory holding your `.data` files.
A normal server start **never downloads a model on its own** - production has
to be deterministic (W4A-08). A download is an explicit action:

```powershell
$env:VOICESTT_KROKO_ALLOW_MODEL_DOWNLOAD = "1"   # or engine_options auto_download_model=True
```

Set `VOICESTT_KROKO_VERIFY_MODEL_HASH=1` to re-verify manifested models by
SHA-256 at start-up; provisioning always verifies by hash, while the runtime
path checks existence, size and variant by default so start-up stays fast.

Bare Kroko filenames are cached under `~/.cache/voicestt/kroko-onnx` unless
`download_root` points somewhere else.

You can also pre-download models into a project-local ignored cache:

```powershell
New-Item -ItemType Directory -Path test-model-cache\kroko-onnx -Force
python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='Banafo/Kroko-ASR', filename='Kroko-EN-Community-64-L-Streaming-001.data', local_dir='test-model-cache/kroko-onnx')"
```

The `kroko-builder` extra installs `huggingface_hub` for this download command.
If you installed VoiceSTT without that extra, install it first:

```powershell
python -m pip install huggingface_hub
```

Pro/private models are not assumed to be public. Pass an existing `.data` path,
`model_download_url`, or explicit Hugging Face repo/token options. Pass Pro keys
through environment/config or CLI options only; do not commit keys.

## Python Usage

```python
from VoiceSTT import AudioToTextRecorder

recorder = AudioToTextRecorder(
    transcription_engine="kroko_onnx",
    model="Kroko-EN-Community-64-L-Streaming-001.data",
    device="cpu",
    language="en",
    transcription_engine_options={
        "provider": "cpu",
        "num_threads": 2,
    },
)
```

For realtime previews, Kroko uses a persistent native stream and receives only
new audio frames. Final transcription still uses one full-utterance call.

```python
recorder = AudioToTextRecorder(
    transcription_engine="kroko_onnx",
    model="Kroko-EN-Community-128-L-Streaming-001.data",
    enable_realtime_transcription=True,
    realtime_transcription_engine="kroko_onnx",
    realtime_model_type="Kroko-EN-Pro-16-L-Streaming-001.data",
    realtime_transcription_engine_options={
        "provider": "cpu",
        "num_threads": 4,
        "key": "...",
        "suppress_native_output": True,
    },
)
```

`Pro-16-L` is the fastest measured partial-cadence option when Pro access is
available. Kroko model names encode native streaming cadence as
`number * 20 ms`, so `16` is about `320 ms`, `32` is about `640 ms`, and `64`
is about `1280 ms`. Feeding smaller chunks does not force Kroko to emit
partials faster; it only avoids extra scheduling and buffer latency.

## Options

| Option | Meaning |
| --- | --- |
| `model_path` | Explicit `.data` model file. Overrides `model`. |
| `model_dir` | Directory containing a single `.data` file, or the default English Community filename. |
| `model_filename` | File name to use inside `model_dir`. |
| `auto_download_model` / `download_model` | Download missing public Community model files. Defaults to `True`. |
| `model_download_url` | Direct download URL for a missing `.data` file. Useful for Pro/private models. |
| `model_repo_id`, `model_revision`, `hf_token` | Optional Hugging Face download settings. |
| `key` | License key for Pro models. |
| `referralcode` | Optional Kroko referral code. |
| `provider` | `cpu`, `cuda`, or `coreml`. Defaults from `device`. |
| `num_threads` | Runtime thread count. Defaults to `1`. |
| `sample_rate` | Kroko recognizer sample rate. Defaults to `16000`. |
| `feature_dim` | Feature dimension. Defaults to `80`. |
| `decoding_method` | `greedy_search` or `modified_beam_search`. |
| `max_active_paths` | Beam paths for modified beam search. |
| `hotwords_file`, `hotwords_score` | Optional hotword biasing inputs. |
| `blank_penalty` | Blank-symbol penalty during decoding. |
| `enable_endpoint_detection` | Enables Kroko endpoint detection. |
| `rule1_min_trailing_silence`, `rule2_min_trailing_silence`, `rule3_min_utterance_length` | Endpoint rule values. |
| `tail_padding_seconds` / `finalization_padding_seconds` | Final silence padding before one-shot decoding. Defaults to `auto`, inferred from model cadence plus a small margin. |
| `suppress_native_output` | Redirect Kroko native stdout/stderr during recognizer calls and set `KROKO_ONNX_SUPPRESS_LICENSE_OUTPUT=1`. Aliases: `suppress_output`, `quiet`, `silent`. |
| `recognizer` | Extra dictionary merged into `OnlineRecognizer.from_transducer(...)`. |

`suppress_native_output` is a Python-side mitigation plus an environment flag.
Reliable suppression of asynchronous Pro license refresh messages such as
`Remaining seconds updated: ...` requires a Kroko wheel built with VoiceSTT's
native patch. Older/unpatched Kroko wheels may still print background license
messages.

## Selektive V2-Verbesserungen (25.10.2026) und automatischer Lifecycle (Korrekturlauf)

Der V2-Entwicklungszweig verwendet weiterhin die direkte Kroko-Anbindung.
Der Owner-/Supervisor-Prozess sowie der native Statuspatch aus Draft-PR #14
sind **nicht** Teil dieser Implementierung.

Die Key-Auflösung für `OnlineRecognizer.from_transducer` liegt zentral in
`VoiceSTT.kroko.credentials.effective_recognizer_key`. Sie berücksichtigt
auch `recognizer.key` als letzten nativen Override und ist damit für eine
API-Lizenzprüfung dieselbe Quelle wie für den Recognizer.

`VoiceSTT.kroko.license_api.check_onprem_license` stellt eine **explizite**
modellbezogene Prüffunktion für den On-Premise-WebSocket-Lizenzdienst zur
Verfügung. Sie ist weder die gehostete Transkriptions-API noch löst sie von
sich aus etwas aus: Aufrufer ist der `KrokoLicenseGate` der Security-Komponente.
Der Lizenzdienst verlangt ein Key-/Modell-UUID-Paar; ein positives Ergebnis
für ein Modell berechtigt nicht zu anderen Modellen. Die technische UUID
stammt aus dem Header der lokal vorliegenden `.data`-Datei
(`VoiceSTT.kroko.models.license_uuid_for`) – derselben Quelle, die die native
Runtime ihrer eigenen Prüfung übergibt. Fehlt Datei oder UUID, bleibt der
Pfad fail-closed.

Der Server wertet die Richtlinie automatisch aus: bei Initialisierung (vor der
ersten Modell-Admission), bei `POST /api/models/refresh`, bei
`PUT /api/models/active` (gegen die Kandidaten-Settings, da Engine-Optionen
dort zur Laufzeit wechseln können), bei Änderung von `kroko.forceCommunity`
und explizit über `POST /api/kroko/license/refresh` (Admin). Die Prüfung ist
**nicht** davon abhängig, dass bereits ein Pro-Modell als Standard gewählt ist:
mit gültigem Key und einem lokal vorhandenen Pro-Modell wird die
Auswahlberechtigung auch aus einer Community-Konfiguration heraus geprüft
(Aktivierung bleibt davon getrennt). Ohne Key oder mit Force Community findet
keine Netzwerkanfrage statt; Prüfungen laufen begrenzt (Standard 5 s,
Admin-Route bis 60 s) und außerhalb des ASGI-Eventloops.
`VoiceSTT.kroko.license_state.KrokoLicenseState` hält den flüchtigen,
modellgebundenen Prüfstatus ohne Secret oder Persistenz (Scope `model`,
TTL ≤ 60 s, Generationenbindung); `pro_enabled` ist daraus abgeleitet.
`VoiceSTT.kroko.models.community_fallback_model` wählt deterministisch
einen geeigneten Community-*Kandidaten*, überprüft aber weder dessen lokale
Verfügbarkeit noch die Ladbarkeit. Diese Verantwortung bleibt beim
`STTModelManager`. Details zum Berechtigungs-Lifecycle:
[Server-Authentifizierung](server-authentication.md#4-kroko-on-premise-modelllizenz--produkt-entitlement-kein-api-login).

Betreiber setzen `kroko.forceCommunity` (serverweit, Admin, live,
persistierte Absicht) für reinen Community-Betrieb. Lizenzstatus und
`pro_enabled` werden nie persistiert; ein Neustart beginnt bei `NOT_CHECKED`.
Ein Key allein – ohne positive Prüfung – schaltet nichts frei; ein Key ersetzt
insbesondere keinen Pro-Build (`KROKO_VARIANT=pro`, siehe
[Buildreferenz](../build/BUILD.md)). Nicht qualifiziert bleiben vor allem
Anbieter-Connection-Limits, Nutzungsreports und Widerrufssemantik.
Echte Lizenzserver- und Native-Integrationstests sind Opt-in
(`VOICESTT_KROKO_LIVE_TESTS=1`, `VOICESTT_KROKO_NATIVE_TESTS=1`), siehe
[Testing](testing.md).

## Modell- und Lizenzwechsel im laufenden Prozess

Die folgenden Aussagen beruhen auf Messungen der Kroko-ONNX-1.12.9-Pro-Runtime
(isolierte Prozesse) und sind der verbindliche Betriebsvertrag dieses Servers.
Sie werden vor dem nativen Laden durchgesetzt
(`VoiceSTT/kroko/native_guard.py`; Load-Probe, Refresh, Recovery,
Scheduler-Erstellung und Engine-Konstruktor), nicht erst durch den Absturz.

**Betriebsgrenze.** Ein Voice-STT-Prozess betreibt höchstens **eine** native
Kroko-Modellinstanz zur gleichen Zeit. Final und Realtime verwenden bei Kroko
dasselbe Modell mit gemeinsamer Instanz (`use_main_model_for_realtime`); zwei
verschiedene Kroko-Modelle in den Lanes werden bei der Konfiguration abgewiesen
(`ValueError`), ein Zweitladen vor dem Laden mit `concurrent_native_identity`.

| Vorgang | Verhalten |
| --- | --- |
| Community-Modell ohne Key auf der Pro-Runtime | funktioniert (nachgewiesen, auch ohne Netz unter Linux) |
| Community → Pro (Key gültig, Prüfung `VALID`) | **live möglich im Leerlauf**: der Server gibt die einzige Instanz über den regulären Entlade-Pfad frei, prüft und lädt Pro. Bei aktiven Sessions/Transkriptionen **zurückgestellt** (`modelRefreshPending`) |
| Pro → Community (Force Community, Key-Entzug, negative Prüfung) | neue Pro-Aufträge sofort gesperrt; der Wechsel auf Community ist im Leerlauf live möglich, sonst zurückgestellt. Der **native Pro-Lizenzkontext bleibt** bis zum Neustart bestehen (`nativeProContextActive`) – es gibt keine Aussage „ohne Netz“ |
| Dasselbe Pro-Modell erneut laden (Idle-Unload/Reload, Force aus → an) | funktioniert mit Patch-Set 5 auf Linux und Windows real nachgewiesen, inklusive regulaerem Prozessende; der fruehere Linux-Shutdownfehler ist korrigiert. Kein nativer Reset-Vertrag |
| Pro-Modell A → anderes Pro-Modell B | **nur nach Neustart**; `pro_identity_change_requires_restart`, `PUT /api/models/active` bleibt unverändert und lässt die laufende Instanz geladen |
| Neuer/rotierter Key bei bereits initialisiertem Pro-Kontext | **nur nach Neustart**; keine neue Freigabe, `key_context_change_requires_restart` |
| Pro-Modell ohne Key | **gesperrt** (`pro_requires_key`; nativ nur eine bis zu 300 s lange Lizenzwarteschleife) |
| Zwei Kroko-Modelle oder eine zweite Instanz gleichzeitig | **gesperrt** (`concurrent_native_identity`) |
| Native-Entwicklerbuild wechseln | nur durch Austausch des Builds und Neustart; das oeffentliche Produkt ist immer Pro-faehig (ein Key ersetzt keinen Pro-Build) |

Bestätigter nativer Kontext: Der Lizenzdienst lehnt eine zusätzliche externe
Prüfung ab, solange der native Pro-Reporter desselben Keys im Prozess lebt
(isolierter Test, 26.10.2026). Für dasselbe Pro-Modell und denselben Key gilt
daher die bestätigte native Ladung als Nachweis (`licenseSource:
"native_context"`); sie ersetzt keine Freigabe für andere Modelle oder Keys und
wird von Force Community immer überstimmt. Dadurch kann eine abgelehnte
Zweitprüfung ein laufendes Pro-Modell nicht herabstufen, und ein Wechsel
Pro → Community → dasselbe Pro funktioniert ohne zweite Provider-Verbindung.

`GET /api/models/management` enthält neben `krokoLicense` das Feld
`krokoRuntime` (keine Secrets), das fünf getrennte Aussagen trägt:
installierte Variante (`installedVariant`), Lizenzberechtigung
(`licenseEntitled`, `licenseSource`, `licenseModelUuid`, `forceCommunity`), gewünschte Modelle
(`desiredModels`), tatsächlich aktive Kroko-Modelle (`activeKrokoModels`,
`activeProPresent`) sowie Neustartbedarf (`restartRequired`, `restartReason`)
zusammen mit `nativeProContextActive`, `liveNativeInstances`,
`proAdmissionRevoked`, `modelRefreshPending` und `lastReconcile`. Eine
erfolgreiche Lizenzprüfung ändert nur die Berechtigung; `activeKrokoModels`
wechselt erst, wenn der Scheduler das Modell wirklich trägt.

## FastAPI Example

```powershell
$model = "test-model-cache\kroko-onnx\Kroko-EN-Community-64-L-Streaming-001.data"
python api_fastapi_server\server.py `
  --host 0.0.0.0 `
  --port 8010 `
  --engine kroko_onnx `
  --model $model `
  --realtime-engine kroko_onnx `
  --realtime-model $model `
  --device cpu `
  --language en `
  --engine-options '{"provider":"cpu","num_threads":2}' `
  --realtime-engine-options '{"provider":"cpu","num_threads":1}'
```

## Tests

Fast contract tests use fake Kroko runtime objects and do not require the
optional dependency:

```powershell
python -m unittest -v tests.unit.test_kroko_onnx_engine
```

Opt-in real Community smoke test:

```powershell
$env:VOICESTT_RUN_KROKO_ONNX = "1"
$env:VOICESTT_KROKO_ONNX_MODEL = "test-model-cache\kroko-onnx\Kroko-EN-Community-64-L-Streaming-001.data"
$env:VOICESTT_KROKO_ONNX_PROVIDER = "cpu"
$env:VOICESTT_KROKO_ONNX_NUM_THREADS = "1"
python -m unittest -v tests.unit.test_kroko_onnx_engine.KrokoOnnxGoldenTranscriptionTests
```

Pip-only users usually do not have the repository's `tests.unit` package. For a
standalone install smoke test, use the Kroko test script from the same branch or
tag as the docs you are reading:
[tests/realtimestt_kroko_test.py](../tests/realtimestt_kroko_test.py).

Run the repository script in init-only mode:

```powershell
python -m pip install rich
python .\tests\realtimestt_kroko_test.py --model "test-model-cache\kroko-onnx\Kroko-EN-Community-64-L-Streaming-001.data" --realtime-model "test-model-cache\kroko-onnx\Kroko-EN-Community-64-L-Streaming-001.data" --provider cpu --no-keyboard --init-only
```

This script constructs `AudioToTextRecorder`, so it needs both Kroko-ONNX and a
working recorder VAD backend in the same environment. The install command above
includes `silero-onnx-cpu` for that reason.

`KROKO_API_KEY`, `KROKO_ONNX_KEY`, `VOICESTT_KROKO_ONNX_KEY`, or `KROKO_KEY`
may be used for licensed Pro-only checks. Keep those values out of committed
files, shell logs, and generated reports.

## Troubleshooting

- Missing dependency errors mean `kroko_onnx` is not importable in the active
  environment. Install Kroko-ONNX in that same environment.
- Missing model errors name the exact `.data` file path VoiceSTT tried.
- Free Kroko wheels cannot load Pro `.data` models; the native error can look
  like a payload parsing or block-size mismatch.
- A key alone does not turn a Free wheel into a Pro runtime. Rebuild with
  `stt-install-kroko --build --variant pro` or Docker
  `KROKO_VARIANT=pro` as documented in the central build guide.
- The validated VPS runtime must share one Pro-16 recognizer between final and
  realtime; see [`build/vps`](../build/vps/README.md). The server enforces this
  for every Kroko model: a second native instance, a second Kroko model or a
  Pro model change inside one process is refused before the native load (see
  *Modell- und Lizenzwechsel im laufenden Prozess*). The adapter API itself
  still allows several independent recognizer objects outside the server.
- CUDA runs require both CUDA-capable hardware and a Kroko-ONNX build with CUDA
  provider support.
- On Windows, prefer the helper's `cross-platform-builds` wheel workflow over a
  direct native source build.
