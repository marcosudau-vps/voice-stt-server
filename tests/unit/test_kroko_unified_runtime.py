"""Unified Kroko runtime continuation (AP-KR-020): authority, bootstrap,
supervisor and server license gate.

Every license decision below is proven against synthetic infrastructure
only (scripted verifiers, fake payload roots, synthetic child processes).
No test here performs a live license check, loads a native Kroko runtime or
treats a simulated answer as productive proof. The product default verifier
(:class:`UnqualifiedLicenseVerifier`) must never grant anything.
"""

import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from VoiceSTT.kroko import bootstrap as kroko_bootstrap
from VoiceSTT.kroko import license_runtime as kroko_license
from VoiceSTT.kroko import supervisor as kroko_supervisor


KROKO_ENV_KEYS = (
    "KROKO_API_KEY",
    "KROKO_ONNX_KEY",
    "VOICESTT_KROKO_ONNX_KEY",
    "KROKO_KEY",
    "VOICESTT_KROKO_PAYLOAD_ROOT",
    "VOICESTT_KROKO_PRO_CANDIDATE",
)

PRO_ID = "kroko-de-pro-64-l"
PRO_FILE = "Kroko-DE-Pro-64-L-Streaming-001.data"
COMMUNITY_FILE = "Kroko-DE-Community-64-L-Streaming-001.data"


def isolated_env(extra=None):
    """Copies os.environ without any Kroko key/payload variables."""
    overlay = {key: value for key, value in os.environ.items()
               if key not in KROKO_ENV_KEYS}
    if extra:
        overlay.update(extra)
    return mock.patch.dict(os.environ, overlay, clear=True)


class ScriptedVerifier(kroko_license.LicenseVerifier):
    """Test-only license authority. NEVER productive proof infrastructure."""

    def __init__(self, verdict):
        self._verdict = verdict
        self.requests = []

    def verify(self, request):
        self.requests.append(request)
        return self._verdict


class ManualClock:
    def __init__(self):
        self.now = 1000.0
        self._lock = threading.Lock()

    def __call__(self):
        with self._lock:
            return self.now

    def advance(self, seconds):
        with self._lock:
            self.now += seconds


class LicenseAuthorityTruthTableTests(unittest.TestCase):
    def make_authority(self, **kwargs):
        clock = ManualClock()
        authority = kroko_license.LicenseRuntimeAuthority(
            time_fn=clock, **kwargs)
        return authority, clock

    def note(self, authority, *, key=True, force=False, revision="k:abc",
             identity="id-1"):
        return authority.note_intent(
            key_present=key, force_community=force,
            credential_revision=revision, runtime_identity=identity)

    # -- cold start ------------------------------------------------------

    def test_initial_state_is_not_checked_and_never_pro(self):
        authority, _ = self.make_authority()
        self.assertEqual(authority.status,
                         kroko_license.LicenseStatus.NOT_CHECKED)
        self.assertFalse(authority.pro_enabled_global())
        self.assertFalse(authority.pro_enabled_for(PRO_ID))
        snapshot = authority.public_snapshot()
        self.assertEqual(snapshot["status"], "NOT_CHECKED")
        self.assertFalse(snapshot["proEnabled"])
        self.assertEqual(snapshot["validatedModelIds"], [])

    def test_snapshot_never_carries_secret_material(self):
        authority, _ = self.make_authority()
        secret = "sk-live-abcdef123456"
        self.note(authority, revision="k:deadbeef")
        accepted, _ = authority.begin_check()
        self.assertTrue(accepted)
        self.assertTrue(authority.record_success(
            (PRO_ID,), max_age_seconds=10.0))
        snapshot = authority.public_snapshot()
        text = repr(snapshot)
        self.assertNotIn(secret, text)
        self.assertNotIn("abcdef", text)
        for forbidden in ("password", "allowed", "error_message"):
            self.assertNotIn(forbidden, text)

    # -- no key / force community -----------------------------------------

    def test_no_key_means_no_check_and_no_pro(self):
        authority, _ = self.make_authority()
        self.note(authority, key=False)
        accepted, reason = authority.begin_check()
        self.assertFalse(accepted)
        self.assertEqual(reason, kroko_license.REASON_NO_KEY)
        self.assertEqual(authority.status,
                         kroko_license.LicenseStatus.NOT_CHECKED)
        self.assertFalse(authority.pro_enabled_for(PRO_ID))

    def test_force_community_suppresses_any_check(self):
        authority, _ = self.make_authority()
        self.note(authority, key=True, force=True)
        accepted, reason = authority.begin_check()
        self.assertFalse(accepted)
        self.assertEqual(reason, kroko_license.REASON_FORCE_COMMUNITY)

    # -- granted entitlement, model scoped ---------------------------------

    def test_granted_proof_enables_exactly_the_confirmed_model(self):
        authority, clock = self.make_authority()
        self.note(authority, key=True)
        verifier = ScriptedVerifier(kroko_license.LicenseVerdict(
            outcome="granted", validated_model_ids=(PRO_ID,),
            max_age_seconds=30.0, reason_code=kroko_license.REASON_OK))
        self.assertEqual(authority.run_check(verifier, (PRO_ID,)),
                         kroko_license.LicenseStatus.VALID)
        self.assertTrue(authority.pro_enabled_for(PRO_ID))
        self.assertFalse(authority.pro_enabled_for("kroko-de-pro-32-m"))
        self.assertFalse(authority.pro_enabled_for(""))
        self.assertFalse(authority.pro_enabled_for(None))
        self.assertTrue(authority.pro_enabled_global())
        self.assertEqual(len(verifier.requests), 1)
        self.assertEqual(verifier.requests[0].credential_revision, "k:abc")

    def test_grant_requires_checking_state_and_nonempty_ids(self):
        authority, _ = self.make_authority()
        self.note(authority, key=True)
        self.assertFalse(authority.record_success((PRO_ID,)))
        self.assertFalse(authority.record_success(()))
        authority.begin_check()
        self.assertFalse(authority.record_success((), max_age_seconds=5.0))
        self.assertEqual(authority.status,
                         kroko_license.LicenseStatus.CHECKING)

    def test_granted_proof_honors_shorter_backend_ttl(self):
        authority, clock = self.make_authority()
        self.note(authority, key=True)
        authority.begin_check()
        self.assertTrue(authority.record_success(
            (PRO_ID,), max_age_seconds=10.0))
        self.assertEqual(authority.public_snapshot()["maxProofAgeSeconds"], 10.0)
        clock.advance(11.0)
        self.assertFalse(authority.pro_enabled_for(PRO_ID))
        self.assertEqual(authority.status,
                         kroko_license.LicenseStatus.CHECK_FAILED)
        self.assertEqual(
            authority.public_snapshot()["reasonCode"],
            kroko_license.REASON_PROOF_EXPIRED)

    def test_backend_ttl_cannot_exceed_authority_bound(self):
        authority, _ = self.make_authority(max_proof_age_seconds=60.0)
        self.note(authority, key=True)
        authority.begin_check()
        self.assertFalse(authority.record_success(
            (PRO_ID,), max_age_seconds=3600.0))
        self.assertFalse(authority.record_success(
            (PRO_ID,), max_age_seconds=0.0))
        self.assertEqual(authority.status,
                         kroko_license.LicenseStatus.CHECKING)

    # -- rejection sticks, failure is retryable ----------------------------

    def test_rejection_is_authoritative_until_intent_changes(self):
        authority, _ = self.make_authority()
        self.note(authority, key=True)
        verifier = ScriptedVerifier(kroko_license.LicenseVerdict(
            outcome="rejected",
            reason_code=kroko_license.REASON_LICENSE_REJECTED))
        self.assertEqual(authority.run_check(verifier),
                         kroko_license.LicenseStatus.INVALID)
        self.assertFalse(authority.pro_enabled_for(PRO_ID))
        accepted, _ = authority.begin_check()
        self.assertFalse(accepted)
        changed = self.note(authority, revision="k:rotated")
        self.assertTrue(changed)
        self.assertEqual(authority.status,
                         kroko_license.LicenseStatus.NOT_CHECKED)
        accepted, _ = authority.begin_check()
        self.assertTrue(accepted)

    def test_unreachable_is_fail_closed_but_retryable(self):
        authority, _ = self.make_authority()
        self.note(authority, key=True)
        verifier = ScriptedVerifier(kroko_license.LicenseVerdict(
            outcome="unreachable",
            reason_code=kroko_license.REASON_LICENSE_UNREACHABLE))
        self.assertEqual(authority.run_check(verifier),
                         kroko_license.LicenseStatus.CHECK_FAILED)
        self.assertFalse(authority.pro_enabled_for(PRO_ID))
        accepted, _ = authority.begin_check()
        self.assertTrue(accepted)
        self.assertTrue(authority.record_rejection())
        self.assertEqual(authority.status,
                         kroko_license.LicenseStatus.INVALID)

    def test_unqualified_product_default_never_grants(self):
        authority, _ = self.make_authority()
        self.note(authority, key=True)
        status = authority.run_check(
            kroko_license.UnqualifiedLicenseVerifier(), (PRO_ID,))
        self.assertEqual(status, kroko_license.LicenseStatus.CHECK_FAILED)
        self.assertEqual(
            authority.public_snapshot()["reasonCode"],
            kroko_license.REASON_NO_QUALIFIED_VERIFIER)

    # -- generation binding -------------------------------------------------

    def test_intent_change_bumps_generation_and_discards_proof(self):
        authority, _ = self.make_authority()
        self.note(authority, key=True)
        authority.begin_check()
        authority.record_success((PRO_ID,), max_age_seconds=60.0)
        generation = authority.generation
        self.assertTrue(authority.pro_enabled_for(PRO_ID))
        changed = self.note(authority, force=True)
        self.assertTrue(changed)
        self.assertEqual(authority.generation, generation + 1)
        self.assertFalse(authority.pro_enabled_for(PRO_ID))
        self.assertEqual(
            authority.public_snapshot()["reasonCode"],
            kroko_license.REASON_INTENT_CHANGED)

    def test_identical_intent_does_not_bump_generation(self):
        authority, _ = self.make_authority()
        self.assertTrue(self.note(authority, key=True))
        generation = authority.generation
        self.assertFalse(self.note(authority, key=True))
        self.assertEqual(authority.generation, generation)

    def test_stale_generation_verdict_is_discarded(self):
        authority, clock = self.make_authority()
        self.note(authority, key=True)
        first = authority.generation
        seen = {}

        class RacingVerifier(kroko_license.LicenseVerifier):
            def verify(self, request):
                seen["generation"] = request.generation
                authority.note_intent(
                    key_present=True, force_community=False,
                    credential_revision="k:changed",
                    runtime_identity="id-1")
                return kroko_license.LicenseVerdict(
                    outcome="granted", validated_model_ids=(PRO_ID,),
                    max_age_seconds=60.0)

        status = authority.run_check(RacingVerifier(), (PRO_ID,))
        self.assertEqual(seen["generation"], first)
        self.assertNotEqual(authority.status,
                            kroko_license.LicenseStatus.VALID)
        self.assertEqual(
            authority.public_snapshot()["reasonCode"],
            kroko_license.REASON_INTENT_CHANGED)

    def test_running_loss_downgrades_valid_to_check_failed(self):
        authority, _ = self.make_authority()
        self.note(authority, key=True)
        authority.begin_check()
        authority.record_success((PRO_ID,), max_age_seconds=60.0)
        self.assertTrue(authority.record_failure("heartbeat_lost"))
        self.assertEqual(authority.status,
                         kroko_license.LicenseStatus.CHECK_FAILED)
        self.assertFalse(authority.pro_enabled_for(PRO_ID))

    # -- credential revision -------------------------------------------------

    def test_credential_revision_is_one_way_and_rotation_sensitive(self):
        first = kroko_license.derive_credential_revision("key-one")
        second = kroko_license.derive_credential_revision("key-two")
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("k:"))
        self.assertNotIn("key-one", first)
        self.assertEqual(kroko_license.derive_credential_revision(""), "none")
        self.assertEqual(kroko_license.derive_credential_revision(None), "none")

    def test_config_fingerprint_ignores_key_material_by_construction(self):
        plain = {"keyPresent": True, "credentialRevision": "k:abc",
                 "models": [PRO_ID]}
        changed = {"keyPresent": True, "credentialRevision": "k:rotated",
                   "models": [PRO_ID]}
        self.assertEqual(kroko_license.config_fingerprint(plain),
                         kroko_license.config_fingerprint(dict(plain)))
        self.assertNotEqual(kroko_license.config_fingerprint(plain),
                            kroko_license.config_fingerprint(changed))


class CommunityFallbackTests(unittest.TestCase):
    def test_real_manifest_prefers_requested_community_model(self):
        from VoiceSTT.kroko import models as kroko_models
        manifest = kroko_models.load_manifest()
        entry = kroko_license.community_fallback_model(
            manifest, COMMUNITY_FILE)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.filename, COMMUNITY_FILE)

    def test_real_manifest_falls_back_within_language(self):
        from VoiceSTT.kroko import models as kroko_models
        manifest = kroko_models.load_manifest()
        entry = kroko_license.community_fallback_model(
            manifest, "Kroko-DE-Pro-64-L-Streaming-001.data")
        self.assertIsNotNone(entry)
        self.assertEqual(
            entry.requires_runtime_variant.strip().lower(), "free")
        self.assertIn("-DE-", entry.filename)

    def test_no_free_entry_means_no_fallback(self):
        pro_only = SimpleNamespace(
            get=lambda value: None,
            entries=(SimpleNamespace(filename="Kroko-DE-Pro-1-M-Streaming-001.data",
                                     requires_runtime_variant="pro"),),
        )
        self.assertIsNone(
            kroko_license.community_fallback_model(pro_only, "anything"))
        self.assertIsNone(kroko_license.community_fallback_model(None, "x"))


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        kroko_bootstrap.reset_selection_for_tests()

    def tearDown(self):
        kroko_bootstrap.reset_selection_for_tests()

    def make_root(self, base, markers=("kroko_onnx/__init__.py",)):
        root = Path(base) / "payload"
        for marker in markers:
            target = root / marker
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# synthetic payload marker\n",
                              encoding="utf-8")
        return root

    def test_cold_select_pins_exactly_one_root_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_root(tmp)
            modules = {}
            path = ["other"]
            record = kroko_bootstrap.cold_select(
                root, _modules=modules, _path=path,
                _find_spec=lambda name: None)
            self.assertEqual(record.root, str(root.resolve()))
            self.assertEqual(path[0], str(root.resolve()))
            self.assertEqual(path.count(str(root.resolve())), 1)
            again = kroko_bootstrap.cold_select(
                root, _modules=modules, _path=path,
                _find_spec=lambda name: None)
            self.assertEqual(again, record)

    def test_payload_is_never_imported_by_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_root(tmp, ("kroko_onnx/__init__.py",))
            modules = {}
            kroko_bootstrap.cold_select(
                root, _modules=modules, _path=[],
                _find_spec=lambda name: None)
            self.assertNotIn("kroko_onnx", modules)
            self.assertNotIn("kroko_onnx", sys.modules)

    def test_already_loaded_native_runtime_is_a_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_root(tmp)
            modules = {"kroko_onnx": object()}
            with self.assertRaises(kroko_bootstrap.BootstrapConflictError):
                kroko_bootstrap.cold_select(
                    root, _modules=modules, _path=[],
                    _find_spec=lambda name: None)

    def test_foreign_global_provider_is_a_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_root(tmp)
            with self.assertRaises(kroko_bootstrap.BootstrapConflictError):
                kroko_bootstrap.cold_select(
                    root, _modules={}, _path=[],
                    _find_spec=lambda name: object()
                    if name == "sherpa_onnx" else None)

    def test_missing_marker_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "payload"
            root.mkdir()
            with self.assertRaises(FileNotFoundError):
                kroko_bootstrap.cold_select(
                    root, _modules={}, _path=[],
                    _find_spec=lambda name: None)

    def test_second_different_root_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = self.make_root(tmp + "-a")
            second = self.make_root(tmp + "-b")
            kroko_bootstrap.cold_select(
                first, _modules={}, _path=[],
                _find_spec=lambda name: None)
            with self.assertRaises(kroko_bootstrap.BootstrapConflictError):
                kroko_bootstrap.cold_select(
                    second, _modules={}, _path=[],
                    _find_spec=lambda name: None)

    def test_env_absent_is_a_verified_noop(self):
        with isolated_env():
            path_before = list(sys.path)
            self.assertIsNone(
                kroko_bootstrap.ensure_bootstrap_from_env(
                    _modules={}, _path=list(sys.path),
                    _find_spec=lambda name: None))
            self.assertEqual(list(sys.path), path_before)
            self.assertIsNone(kroko_bootstrap.selection_status())


class SupervisorTests(unittest.TestCase):
    def test_happy_path_starts_and_confirms_clean_exit(self):
        supervisor = kroko_supervisor.OwnerSupervisor(max_attempts=3)
        spec = kroko_supervisor.OwnerSpec(
            argv=[sys.executable, "-c",
                  "import time; time.sleep(30)"],
            start_deadline_seconds=15.0)
        handle = supervisor.start(
            spec, config={"runtime": "free", "revision": "k:none"},
            wait_ready=lambda deadline: True)
        self.assertEqual(handle.generation, 1)
        self.assertTrue(supervisor.is_current(1))
        self.assertEqual(supervisor.accept_event(1, {"ready": True}),
                         {"ready": True})
        exit_code = supervisor.stop(graceful_seconds=5.0)
        # terminate() on Windows yields 1, on Linux -SIGTERM; decisive is
        # that the exit was observed and confirmed, not the code itself.
        self.assertIsNotNone(exit_code)
        self.assertEqual(supervisor.last_exit_code, exit_code)

    def test_start_deadline_kills_and_confirms_candidate(self):
        supervisor = kroko_supervisor.OwnerSupervisor(max_attempts=3)
        spec = kroko_supervisor.OwnerSpec(
            argv=[sys.executable, "-c",
                  "import time; time.sleep(60)"],
            start_deadline_seconds=5.0,
            graceful_shutdown_seconds=5.0)
        with self.assertRaises(kroko_supervisor.StartDeadlineExceeded):
            supervisor.start(
                spec, config={"runtime": "free"},
                wait_ready=lambda deadline: False)
        self.assertIsNotNone(supervisor.last_exit_code)
        self.assertFalse(supervisor.is_current(1))

    def test_early_exit_counts_as_missed_deadline(self):
        supervisor = kroko_supervisor.OwnerSupervisor(max_attempts=3)
        spec = kroko_supervisor.OwnerSpec(
            argv=[sys.executable, "-c", "raise SystemExit(3)"],
            start_deadline_seconds=15.0)

        def slow_ready(deadline):
            import time as time_module
            time_module.sleep(2.0)
            return True

        with self.assertRaises(kroko_supervisor.StartDeadlineExceeded):
            supervisor.start(
                spec, config={"runtime": "free"},
                wait_ready=slow_ready)

    def test_retry_budget_is_bounded_per_configuration(self):
        calls = []

        class NeverReady:
            def __init__(self, *args, **kwargs):
                calls.append(True)
                self.returncode = None

            def poll(self):
                return None

            def terminate(self):
                self.returncode = -15

            def kill(self):
                self.returncode = -9

            def wait(self, timeout=None):
                return self.returncode

        sleeps = []
        supervisor = kroko_supervisor.OwnerSupervisor(
            max_attempts=2, backoff_base_seconds=1.0,
            sleep_fn=sleeps.append,
            popen_factory=NeverReady)
        spec = kroko_supervisor.OwnerSpec(argv=["owner"],
                                          start_deadline_seconds=5.0)
        config = {"runtime": "pro", "revision": "k:abc"}
        with self.assertRaises(kroko_supervisor.StartDeadlineExceeded):
            supervisor.start(spec, config=config,
                             wait_ready=lambda deadline: False)
        with self.assertRaises(kroko_supervisor.StartDeadlineExceeded):
            supervisor.start(spec, config=config,
                             wait_ready=lambda deadline: False)
        with self.assertRaises(kroko_supervisor.RetryBudgetExhausted):
            supervisor.start(spec, config=config,
                             wait_ready=lambda deadline: False)
        self.assertEqual(len(calls), 2)
        self.assertEqual(sleeps, [1.0])
        changed = dict(config, revision="k:rotated")
        with self.assertRaises(kroko_supervisor.StartDeadlineExceeded):
            supervisor.start(spec, config=changed,
                             wait_ready=lambda deadline: False)
        self.assertEqual(len(calls), 3)

    def test_stale_generation_results_are_discarded(self):
        supervisor = kroko_supervisor.OwnerSupervisor(max_attempts=3)
        spec = kroko_supervisor.OwnerSpec(
            argv=[sys.executable, "-c",
                  "import time; time.sleep(30)"],
            start_deadline_seconds=15.0)
        first = supervisor.start(
            spec, config={"runtime": "free", "n": 1},
            wait_ready=lambda deadline: True)
        second = supervisor.start(
            spec, config={"runtime": "free", "n": 2},
            wait_ready=lambda deadline: True)
        self.assertNotEqual(first.generation, second.generation)
        self.assertIsNone(supervisor.accept_event(first.generation, "late"))
        self.assertEqual(supervisor.accept_event(second.generation, "fresh"),
                         "fresh")
        supervisor.stop()

    def test_status_projection_carries_no_secrets(self):
        supervisor = kroko_supervisor.OwnerSupervisor(max_attempts=3)
        status = supervisor.status()
        self.assertEqual(
            sorted(status),
            ["attemptsForConfig", "generation", "lastExitCode",
             "maxAttempts", "running"])
        self.assertNotIn("KROKO", repr(status))


class ServerLicenseGateTests(unittest.TestCase):
    """Server-side gate behavior without booting a full service."""
    def setUp(self):
        import api_fastapi_server.server as server_module
        self.server_module = server_module

    def make_stub(self, **settings_overrides):
        settings = self.server_module.ServerSettings()
        settings.transcription_engine = "kroko_onnx"
        settings.realtime_transcription_engine = "kroko_onnx"
        settings.model = COMMUNITY_FILE
        settings.realtime_model = COMMUNITY_FILE
        settings.use_main_model_for_realtime = False
        for name, value in settings_overrides.items():
            setattr(settings, name, value)
        stub = SimpleNamespace(
            settings=settings,
            kroko_license=kroko_license.LicenseRuntimeAuthority(),
            _kroko_manifest=None,
            _kroko_operator_models={},
        )
        service = self.server_module.VoiceSTTService
        import types as types_module
        stub._kroko_options_key = service._kroko_options_key
        for name in ("_kroko_effective_key",
                     "_kroko_runtime_identity",
                     "_kroko_manifest_cached", "_kroko_lane_models",
                     "_kroko_pro_entries", "_enforce_kroko_license_gate",
                     "_refresh_kroko_intent", "_can_start_native_candidate"):
            setattr(stub, name, types_module.MethodType(
                getattr(service, name), stub))
        return stub

    def gate(self, stub, candidate=None):
        return self.server_module.VoiceSTTService._enforce_kroko_license_gate(
            stub, candidate if candidate is not None else stub.settings)

    def intent(self, stub, reason="test"):
        return self.server_module.VoiceSTTService._refresh_kroko_intent(
            stub, reason=reason)

    def test_community_selection_passes_without_any_proof(self):
        stub = self.make_stub()
        with isolated_env():
            self.intent(stub)
            self.gate(stub)

    def test_unmanifested_kroko_model_stays_possible_but_labelled(self):
        stub = self.make_stub(model="Kroko-DE-Custom-64-L-Streaming-001.data",
                              realtime_model=COMMUNITY_FILE)
        with isolated_env():
            self.intent(stub)
            # No confirmable right, hence never VALID — but, consistent with
            # the model authority, possible as an explicitly labelled
            # operator override (audited, never silently blessed).
            unmanaged = self.gate(stub)
            self.assertEqual(len(unmanaged), 1)
            self.assertEqual(unmanaged[0]["lane"], "final")
            self.assertFalse(
                stub.kroko_license.pro_enabled_for(
                    "Kroko-DE-Custom-64-L-Streaming-001.data"))

    def test_pro_model_without_valid_proof_is_refused(self):
        stub = self.make_stub(model=PRO_FILE)
        with isolated_env():
            self.intent(stub)
            self.assertFalse(
                stub.kroko_license.pro_enabled_for(PRO_ID))
            with self.assertRaises(ValueError) as raised:
                self.gate(stub)
            self.assertIn("Lizenzberechtigung", str(raised.exception))
            self.assertNotIn("KROKO", str(raised.exception))

    def test_pro_model_with_current_proof_passes_exactly_that_id(self):
        stub = self.make_stub(model=PRO_FILE)
        stub.settings.transcription_engine_options = {"key": "test-key"}
        with isolated_env():
            self.intent(stub)
            stub.kroko_license.begin_check()
            stub.kroko_license.record_success((PRO_ID,), max_age_seconds=60.0)
            self.gate(stub)
            other = self.server_module.replace(stub.settings)
            other.model = "Kroko-DE-Pro-32-M-Streaming-001.data"
            with self.assertRaises(ValueError):
                self.gate(stub, other)

    def test_force_community_blocks_even_valid_proof(self):
        stub = self.make_stub(model=PRO_FILE, kroko_force_community=True)
        with isolated_env():
            self.intent(stub)
            with self.assertRaises(ValueError):
                self.gate(stub)

    def test_non_kroko_lanes_are_out_of_scope(self):
        stub = self.make_stub()
        stub.settings.transcription_engine = "faster_whisper"
        stub.settings.realtime_transcription_engine = "faster_whisper"
        stub.settings.model = "small"
        stub.settings.realtime_model = "tiny"
        with isolated_env():
            self.intent(stub)
            self.gate(stub)

    def test_key_rotation_bumps_generation_and_kills_proof(self):
        stub = self.make_stub(model=PRO_FILE)
        stub.settings.transcription_engine_options = {"key": "first-key"}
        with isolated_env():
            self.intent(stub)
            first = stub.kroko_license.generation
            self.assertTrue(stub.kroko_license.begin_check()[0])
            self.assertTrue(stub.kroko_license.record_success(
                (PRO_ID,), max_age_seconds=60.0))
            self.gate(stub)
            stub.settings.transcription_engine_options = {"key": "second-key"}
            self.intent(stub)
            self.assertEqual(stub.kroko_license.generation, first + 1)
            with self.assertRaises(ValueError):
                self.gate(stub)

    def test_startup_fallback_downgrades_unentitled_pro_to_community(self):
        import api_fastapi_server.server as server_module
        stub = self.make_stub(model=PRO_FILE)
        with isolated_env():
            self.intent(stub)
            refreshed = []

            class FakeSnapshot:
                minimum_ready = True
                active = {}

            class FakeManager:
                def __init__(self):
                    self.intent = None

                def refresh(self):
                    refreshed.append(True)
                    return FakeSnapshot()

            stub.stt_model_manager = FakeManager()
            stub._apply_stt_model_snapshot = lambda snapshot: True
            server_module.VoiceSTTService._enforce_kroko_startup_models(stub)
            self.assertEqual(stub.settings.model, COMMUNITY_FILE)
            self.assertTrue(refreshed)
            self.assertTrue(stub._kroko_startup_notes)

    def test_effective_key_never_leaves_a_copy_in_the_authority(self):
        stub = self.make_stub()
        secret = "top-secret-key-value"
        stub.settings.transcription_engine_options = {"key": secret}
        with isolated_env():
            self.intent(stub)
            snapshot = stub.kroko_license.public_snapshot()
            self.assertTrue(snapshot["keyPresent"])
            self.assertNotIn(secret, repr(snapshot))
            self.assertTrue(snapshot["credentialRevision"].startswith("k:"))
            self.assertEqual(len(snapshot["credentialRevision"]), 18)


class LicenseIntentPersistenceTests(unittest.TestCase):
    """Only operator intent persists; derived runtime state never does."""

    def test_force_community_round_trips_through_runtime_config(self):
        import api_fastapi_server.server as server_module
        from VoiceSTT_server.operations import RuntimeConfigStore
        with tempfile.TemporaryDirectory() as tmp:
            store_path = str(Path(tmp) / "runtime.json")
            settings = server_module.ServerSettings()
            settings.runtime_config_path = store_path
            settings.kroko_force_community = True
            store = RuntimeConfigStore(store_path)
            allowed = (
                server_module.ACTIVE_RUNTIME_SETTINGS
                | server_module.NEW_SESSION_RUNTIME_SETTINGS
                | server_module.STARTUP_ONLY_SETTINGS
            ) - {
                "admin_api_key", "data_root_path", "openai_api_key",
                "runtime_config_path", "device", "host", "port"}
            store.save(settings, allowed)
            persisted = store.load()
            self.assertTrue(persisted.get("kroko_force_community") is True)
            # Derived state is not a setting and can never be persisted.
            self.assertNotIn("pro_enabled", persisted)
            self.assertNotIn("proEnabled", persisted)
            for value in persisted.values():
                self.assertNotIn("top-secret", repr(value))


if __name__ == "__main__":
    unittest.main()
