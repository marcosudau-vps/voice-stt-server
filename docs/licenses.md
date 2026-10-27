# License Notes

Last researched: 2026-10-27 (Kroko V2); other engine notes retain their earlier scope.

VoiceSTT itself is released under the MIT license. Optional transcription,
VAD, and wake-word engines pull in their own packages, model weights, service
terms, and model cards. Those upstream terms can change independently from this
repository.

This page is a practical summary, not legal advice. Before shipping a product,
redistributing model files, bundling wheels, or offering hosted transcription,
review the upstream license files and terms for the exact package, model,
revision, API, and distribution path you use.

The unified V2 product `voice-stt-server` embeds the Pro-capable Kroko runtime.
Technical build procedures are in [build/BUILD.md](../build/BUILD.md#community-und-pro).
Product wheels retain one package owner and carry Kroko and dependency notices
in their product `.dist-info/licenses/`, including original nested notices.
Pinned supplemental notices repair the historical Windows omission without
changing native compilation inputs. Keys and model files are never bundled.

## Unified V2 release gate

**Public release approval: BLOCKED.** Technical success does not establish
permission to distribute the complete Pro-capable product. The reviewed gate
is [build/kroko-redistribution.json](../build/kroko-redistribution.json), copied
into schema-3 candidates as `redistributionApproval`. Preflight and the real
release engine reject unverified approval before creating tags or publishing.
Technical qualification does not change that approval.

| Evidence | Verified scope | Still required |
| --- | --- | --- |
| [Pinned Kroko source LICENSE](https://github.com/kroko-ai/kroko-onnx/blob/8657e655192623b98d7708e742a72987f953d3a2/LICENSE) | Apache-2.0 source text at the compiled upstream revision | Explicit rights/contract assessment for redistribution of this Pro-capable binary product and any non-source components |
| Bundled upstream/dependency notices | Byte counts, source URLs and SHA-256 in [sources.json](../VoiceSTT/assets/kroko/licenses/sources.json); product gate verifies all indexed files on both platforms | Confirm exact linked dependency inventory, transitive obligations and Windows Microsoft runtime redistribution terms against final artifacts |
| Pro model entitlement | Technical permission for one model UUID and key context | Does not grant model/runtime redistribution rights |

The notice bundle covers Kroko/sherpa-onnx, ONNX Runtime 1.17.1 and its third-party
notices, OpenSSL, WebSocket++, Asio, pybind11, Kaldi components, OpenFST and
transitive source notices, including Asio’s full Boost license, cppjieba/limonp,
Eigen license/readme texts and simple-sentencepiece. ONNX Runtime LICENSE and
ThirdPartyNotices were compared byte-for-byte with the actual verified Linux
dependency payload. Source URLs and license texts are evidence for those
components, not an assertion that all binary/product redistribution rights are
settled. Linux system-library notices also belong to the container base; Python
dependencies keep their own installed metadata/notices. The final Linux/Windows
wheel inspections and native test results are recorded in the
[dated qualification record](.archiv/kroko_v2_finalization/2026-10-27_ABSCHLUSS_SOLL_IST.md).

**Artifact finding, 2026-10-22 (AP-KR-010).** The above describes the intended
redistribution contract. In the actual RC 39405176300, both Linux product wheels
carry `KROKO-ONNX-LICENSE`; both Windows product wheels only carry the VoiceSTT
license. Complete upstream and dependency notices must therefore be an explicit
gate for the planned component packaging. The
[investigation](.archiv/kroko_unified_runtime_v2/AP-KR-010/2026-10-22_ERGEBNISBERICHT.md)
records exact artifact hashes and limitations; it grants no new redistribution rights.

Only Faster-Whisper and Kroko-ONNX are supported production engines. The other
engine families listed below still have adapters in the source tree, but they
are internal/experimental, are not installed by the public distributions, and
are not redistributed by this project - their notes are kept here because the
adapters exist, not because the engines are shipped.

## Important Limits

- "Commercial use" below means the cited upstream license or model card does
  not obviously prohibit commercial use. It does not cover privacy, consent,
  biometrics, export controls, trademarks, data-processing agreements, or
  platform-specific terms.
- Runtime code and model weights can have different licenses.
- Hosted APIs and model hubs can add access terms even when the model weights
  are open-licensed.
- If you redistribute binaries, wheels, model files, or Docker images, preserve
  upstream copyright notices and license texts.
- For Hugging Face models, verify the license on the exact model repository and
  revision you download. Derived, converted, quantized, or ONNX/GGUF versions
  may carry the upstream model license plus additional notices.

## ASR Engine Summary

| VoiceSTT engine | Runtime / package license | Default or typical model license | Commercial-use note |
| --- | --- | --- | --- |
| `faster_whisper` | [`faster-whisper`](https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE) is MIT. Its inference runtime, [CTranslate2](https://github.com/OpenNMT/CTranslate2), is MIT. | OpenAI Whisper code and model assets are published in the [`openai/whisper`](https://github.com/openai/whisper/blob/main/LICENSE) repository under MIT. | Generally permissive, subject to preserving MIT notices when redistributing. |
| `whisper_cpp` | [`whisper.cpp`](https://github.com/ggml-org/whisper.cpp) is MIT. VoiceSTT uses the `pywhispercpp` package, so check that package metadata before redistributing wheels. | Uses OpenAI Whisper-family model files; check whether you use original OpenAI files or third-party conversions. | Generally permissive for original Whisper assets, but converted model files should be checked individually. |
| `openai_whisper` | [`openai-whisper`](https://github.com/openai/whisper/blob/main/LICENSE) is MIT. | OpenAI Whisper assets in the same repository are MIT. | Generally permissive, subject to MIT notice preservation. |
| `sherpa_onnx_moonshine`, `sherpa_onnx_parakeet` | [`sherpa-onnx`](https://github.com/k2-fsa/sherpa-onnx) is Apache-2.0. ONNX Runtime is MIT. | The model bundle determines the model license. For common upstream families, Useful Sensors Moonshine Streaming is MIT and NVIDIA Parakeet is CC-BY-4.0. | Keep the license and attribution files that ship with the selected sherpa-onnx model bundle. Do not assume every bundle has the same terms. |
| `kroko_onnx` | [`kroko-onnx`](https://github.com/kroko-ai/kroko-onnx) is Apache-2.0. | Kroko's docs describe Community models as CC-BY-SA and Commercial/OEM models as separately licensed. | Community models require the stated attribution/share-alike duties. Kroko documents a permanent free key for strictly non-commercial Pro use, a temporary trial key, and separate Commercial/OEM licensing for professional production. Pro license validation sends the key, machine fingerprint and usage duration to Kroko's license server. |
| `parakeet` | NVIDIA NeMo source is Apache-2.0, while NVIDIA notes that some NeMo Framework containers and deployment artifacts have separate NVIDIA product terms. | The default `nvidia/parakeet-tdt-0.6b-v3` model card lists CC-BY-4.0 and says the model is ready for commercial/non-commercial use. | CC-BY-4.0 requires attribution. Review NVIDIA container/product terms if deploying through NIM, Riva, NeMo containers, or other NVIDIA services. |
| `omnilingual_asr` | Meta's `omnilingual-asr` package and model suite are documented as Apache-2.0. | The Meta Omnilingual ASR code and models are Apache-2.0; Meta documents the accompanying corpus as CC-BY-4.0. | The model license is permissive. If you use or redistribute corpus data, handle the corpus license separately. |
| `moonshine`, `moonshine_streaming` | Uses Hugging Face Transformers in VoiceSTT; check the installed Transformers version and any model custom code. | The default `UsefulSensors/moonshine-streaming-medium` model card lists MIT. | English Moonshine Streaming weights are permissive. Non-default Moonshine variants may differ, so check the exact model card. |
| `granite_speech`, `granite` | Uses Hugging Face Transformers in VoiceSTT. | The default `ibm-granite/granite-speech-4.1-2b` model card lists Apache-2.0; IBM's Granite docs describe Granite Speech as Apache-2.0. | Generally permissive. Preserve Apache-2.0 notices when redistributing. |
| `qwen3_asr`, `qwen_asr` | Uses the `qwen-asr` package and, optionally, vLLM. Check those package licenses for redistribution. | The default `Qwen/Qwen3-ASR-1.7B` model card lists Apache-2.0. | Generally permissive for the default model. vLLM, Docker, ModelScope, or hosted serving paths may add their own terms. |
| `cohere_transcribe`, `cohere` | Uses Hugging Face Transformers and model-specific code from the model repository. | The default `CohereLabs/cohere-transcribe-03-2026` model card lists Apache-2.0 and describes the model as an open-source release. | Generally permissive for the model card license. If access is gated or served through a provider, follow that provider's access terms too. |
| `openai_api` | Placeholder engine in this repository; not wired as a local ASR backend. | N/A. | If implemented later, usage would be governed by OpenAI API/service terms, not an open-source model license. |

## VAD And Wake-Word Dependencies

| Component | Upstream terms | Practical note |
| --- | --- | --- |
| WebRTC VAD via `webrtcvad-wheels` | PyPI lists MIT. | Permissive wrapper; preserve notices if redistributing. |
| Silero VAD | [`silero-vad`](https://github.com/snakers4/silero-vad/blob/master/LICENSE) is MIT. | Permissive for the packaged VAD assets, subject to MIT notices. |
| OpenWakeWord | OpenWakeWord is documented as Apache-2.0. | Permissive wake-word path. Verify any third-party wake-word model you add. |
| Porcupine / Picovoice | Picovoice publishes separate service and SDK terms. | Treat Porcupine as a provider-licensed dependency. Free trials or free plans may not cover all commercial deployment scenarios. |

## Source Links Checked

- VoiceSTT package metadata: `setup.py`
- Faster Whisper: `https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE`
- CTranslate2: `https://github.com/OpenNMT/CTranslate2`
- OpenAI Whisper: `https://github.com/openai/whisper/blob/main/LICENSE`
- whisper.cpp: `https://github.com/ggml-org/whisper.cpp`
- sherpa-onnx: `https://github.com/k2-fsa/sherpa-onnx`
- ONNX Runtime: `https://github.com/microsoft/onnxruntime`
- kroko-onnx: `https://github.com/kroko-ai/kroko-onnx`
- Kroko on-premise model/license docs: `https://docs.kroko.ai/on-premise`
- NVIDIA NeMo: `https://github.com/NVIDIA/NeMo`
- NVIDIA NeMo Framework license notes: `https://docs.nvidia.com/nemo-framework/user-guide/25.11/overview.html`
- NVIDIA Parakeet model card: `https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3`
- Meta Omnilingual ASR: `https://github.com/facebookresearch/omnilingual-asr`
- Meta Omnilingual ASR blog: `https://ai.meta.com/blog/omnilingual-asr-advancing-automatic-speech-recognition`
- Useful Sensors Moonshine Streaming Medium model card: `https://huggingface.co/UsefulSensors/moonshine-streaming-medium`
- IBM Granite Speech model card: `https://huggingface.co/ibm-granite/granite-speech-4.1-2b`
- IBM Granite Speech docs: `https://www.ibm.com/granite/docs/models/speech`
- Qwen3-ASR model card: `https://huggingface.co/Qwen/Qwen3-ASR-1.7B`
- Cohere Transcribe model card: `https://huggingface.co/CohereLabs/cohere-transcribe-03-2026`
- webrtcvad-wheels PyPI metadata: `https://pypi.org/project/webrtcvad-wheels`
- Silero VAD license: `https://github.com/snakers4/silero-vad/blob/master/LICENSE`
- OpenWakeWord project page: `https://openwakeword.com`
- Picovoice terms: `https://picovoice.ai/docs/terms-of-use`
