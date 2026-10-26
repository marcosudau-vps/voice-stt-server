# PR #15 – Soll-/Ist-Vergleich der Abschlusskorrektur (26.10.2026)

Vergleich der [Planung](2026-10-26_PLAN_ABSCHLUSSKORREKTUR.md) mit dem
umgesetzten Code. Stand: Arbeitsbranch
`work/kroko-v2-selective-improvements-20261025`, Basis `4f000fd2`. Die
SHA des Umsetzungscommits und die CI-Läufe stehen im
[Abschlussnachtrag](2026-10-26_ABSCHLUSSNACHTRAG.md) und in der PR-Beschreibung.
Die Akten `01`–`08` bleiben unverändert.

Legende: **vollständig** / **teilweise** / **nicht umgesetzt**.

## Befundmatrix: SOLL → Code → Test → IST

| ID | Soll (neue Bewertung) | Code | Deterministischer Test | Realnachweis | IST |
| --- | --- | --- | --- | --- | --- |
| P0-01 | Verspäteter Worker bindet nie alten Key/Force | `security/kroko.py`: `prepare`/`run`/`current_decision`/`bind_intent`; `server.py`: `_kroko_policy_lock` | `test_late_answer_cannot_restore_old_key_or_force`, `test_late_answer_for_old_key_leaves_new_key_checkable`, `test_service_policy_read_and_bind_cannot_interleave` (alter Worker tatsächlich zurückgehalten) | – | vollständig |
| P0-02 | Force/Key-Entzug sperren neue Pro-Aufträge sofort und synchron; Python-Freigabe ≠ nativer Kontext; Neustart ehrlich | `apply_kroko_force_change`, `_kroko_pro_revocation` in `_submit_scheduler_job`, Hook liest Live-Force, `krokoRuntime` | `test_force_patch_blocks_pro_jobs_before_background_reconcile` (Reconcile-Thread blockiert), `test_key_removal_blocks_pro_jobs_immediately`, `test_force_patch_switches_pro_to_community_through_one_native_instance`, `…with_active_sessions_defers_instead_of_hot_swapping`, `test_key_rotation_after_native_pro_requires_restart_without_fake_grant` | N4: `force_community_locked` → sofort abgewiesen; `force_community_done` → Community, `nativeProContextActive: true` | vollständig |
| P1-03 | Prüfung auch aus Community-Konfiguration; Auswahl ≠ Aktivierung | `_kroko_license_target`, `STTModelManager.local_license_candidates` | `test_community_config_with_key_checks_local_pro_candidate`, `…without_key_or_with_force_makes_no_external_check`, `test_without_local_pro_model_the_state_is_honestly_not_checked` | N4: `community_start` mit Community-Config → Lizenz `VALID` | vollständig |
| P1-04 | Kein Mehrmodell-Entitlement; Schutzguard: eine native Kroko-Identität; Final/Realtime teilen; Abweisung vor dem Native-Load | `VoiceSTT/kroko/native_guard.py`; Engine-Konstruktor, `_probe_stt_model`, `_new_scheduler`, `_kroko_assert_switch_possible`, `enforce_kroko_single_identity` | `test_enforce_rejects_two_different_kroko_models_and_shares_one`, `test_final_and_realtime_share_one_kroko_instance`, `test_scheduler_creation_refuses_two_kroko_identities_before_native_load`, `test_probe_refuses_other_pro_identity_before_native_load`, `test_probe_never_loads_a_second_instance_next_to_a_live_one`, vier `test_engine_*`, `test_guard_rules_table` | N3: ein Pro-Recognizer für Final **und** Realtime (reale Transkription) | vollständig |
| P1-05 | Prüfung und Admission: dieselbe tatsächliche Pfadautorität | `STTModelManager.locate_local_path`/`resolve_license_uuid`; `_eligible(…, candidate_path)`; Lizenzziel über den Manager | `test_license_check_and_eligibility_use_engine_model_dir_only` (ohne globale Root, nur Engine-`model_dir`) | N4 verwendet ausschließlich `model_dir` | vollständig |
| P1-06 | Nach Hintergrundprüfung Berechtigung/Snapshot/Status automatisch und generationssicher; Community↔Pro live nur, wo sicher; sonst Neustart/Zurückstellung | `reconcile_kroko_models`, `_kroko_quiesced_manager_refresh`, `kroko_runtime_status`, `refresh_stt_models(license_check=…)` | `test_background_check_promotes_pro_only_after_reconcile`, `test_busy_server_defers_community_to_pro_transition`, `test_switch_to_other_pro_model_is_refused_and_keeps_the_instance`, `test_same_pro_model_can_be_reloaded_after_unload`, `test_native_pro_context_keeps_entitlement_without_a_provider_recheck`, `test_pro_again_after_force_release_uses_the_native_context` | N4: Community → Pro → Community → Pro über `switch_models`, Force-Patch und Reconcile, jeweils mit realer Transkription | vollständig |
| Schutzfall | Key-Rotation bei initialisiertem Pro-Singleton ⇒ Neustart, keine Freigabe | Guard `key_context_change_requires_restart`, Gate-Entscheidung ohne Netz | `test_key_rotation_after_native_pro_requires_restart_without_fake_grant`, `test_engine_refuses_rekeyed_pro_context_and_keyless_pro` | – | vollständig |

## Weitere Planpunkte

| Planpunkt | IST |
| --- | --- |
| Dokumentation (`server-authentication`, `kroko-onnx`, `stt-model-management`, `configuration`, `fastapi-server`, `module-map`, `testing`) | vollständig; Wechselmatrix (funktioniert / nur nach Neustart / gesperrt) in `kroko-onnx.md` |
| Keine Änderung am V2-Wire-Vertrag, keine neue Persistenz, keine neue Prozessarchitektur | eingehalten (`krokoRuntime` ist ein additives Feld der Admin-Management-Antwort, nicht der V2-Wire-Verträge) |
| Keine Pro-A→B-Experimente | eingehalten; ausschließlich durch den Guard und Fake-Tests abgedeckt |
| Opt-in-Realtests | `tests/unit/test_kroko_native_integration.py` (+ `kroko_native_child.py`) |
| Linux-Realtests | **NOT_RUN** (nur Windows verfügbar) |
| Echter Mehrsitzungs-/Last-Test der Umschaltung unter aktiven Sessions | **NOT_RUN**; die Zurückstellung bei aktiver Arbeit ist deterministisch getestet |

## Abweichungen

Siehe [Abweichungsdatei](2026-10-26_ABWEICHUNGEN.md).
