# W4B Requirement Trace

| Requirement | Implementation | Test / evidence |
| --- | --- | --- |
| One common authority for Faster-Whisper and Kroko | `VoiceSTT_server/stt_model_management.py`: `ProductModel`, adapters, `STTModelManager`; `ManagedModelRegistryView` used by the service | Catalog, API, registry-view, scheduler integration tests |
| Persistent default stores and custom-first discovery | `OperatorIntent`, Faster/Kroko adapters | Default-root, custom precedence, direct Kroko file, all-path tests |
| Read-only discovery and writable target fallback | `AtomicModelProvisioner.choose_target` | Read-only source / runtime fallback test |
| DISCOVERED / VALIDATED / LOAD_VERIFIED | Immutable candidate state and lazy `load_probe` promotion | State, validation and serious-candidate probe tests |
| Product facts separate from operator intent | Frozen `ProductModel`; settings parser accepts only operator fields | Static-fact forgery test |
| Honest immutable provisioning authority | Faster entries stay local-only when hashes are unknown; Kroko catalog uses existing pinned manifest facts | Product-authority honesty and hard-ineligibility tests |
| Global OR engine OR model auto-download | `OperatorIntent.effective_auto_download` | Parametric OR and lower-false tests |
| Defaults then ordered recovery | Manager refresh/recovery: explicit roles, ascending priority, stable-ID tie | Defaults, priority, tie and no-priority tests |
| Local fallback independent of auto-download | Local candidate branch precedes provisioning gate | Local-vs-missing recovery tests |
| MINIMUM_READY and one-model/two-role coverage | Role coverage set and early recovery stop | Dual-role and stop-at-ready tests |
| Optional requested provisioning after readiness | Independent requested-product pass and optional status/errors | Optional success, in-progress and error tests |
| Transactional refresh / LKG | Candidate snapshot publication only on ready success; explicit restore hook for scheduler activation | Failed-refresh, failed-activation and LKG tests |
| Verified atomic provisioning | Unique `.part`, observed source identity, byte/SHA verification, `os.replace`, cleanup | Source/hash/size, replacement, duplicate-cache tests |
| Concurrent refresh/provision safety | Manager refresh lock, service refresh lock, target-specific provisioner locks | Deterministic barrier/event interleaving tests |
| Engines receive only local paths | Faster resolver rejects non-local names; Kroko engine download code removed; service supplies `_resolved_stt_models` | Resolver/engine tests and static hidden-download scan |
| Kroko Pro prerequisites and secret boundary | Variant/license eligibility gates; boolean-only intent; diagnostic redaction | Pro rejection and two secret-redaction tests |
| Administration while NOT_READY | Existing health subsystem includes path-free summary; authenticated model management/refresh endpoints remain live | NOT_READY API/health test |
| Existing settings authority, conservative defaults | `ServerSettings`, YAML and CLI JSON settings; global default false | Settings/YAML parsing tests |
| Documentation | `docs/stt-model-management.md` plus existing admin/config references | Documentation review |
| No native Kroko build / no W4C | No build invocation in W4B call graph; no deployment/container changes | Static scan and scope review |

All contract requirements have an implementation and verification location.
