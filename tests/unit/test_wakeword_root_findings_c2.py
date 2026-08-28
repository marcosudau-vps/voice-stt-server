"""AP-SRV-060 C2: regression tests for the Root findings F1-F10.

Every test in this file was written RED-first against the C1 semantics: it
reproduces the defect Root described before the fix and pins the corrected
behaviour afterwards. The RED/GREEN matrix is in
``docs/.archiv/.../runs/02_ROOT_CORRECTION/2026-08-28_REPORT.md``.

AP-SRV-060 C3 kept every one of these findings closed but replaced three
mechanisms they were originally written against, so the affected cases were
re-expressed here against the corrected contract:

* detection works on contiguous hit regions of prediction frames rather than
  per-chunk raw candidates, so the F2/F6/F7 cases drive
  :meth:`WakeDetectionEvaluator.observe_scores` and hand the admission a
  finalized :class:`~VoiceSTT.core.wake_detection.WakeHit`;
* the audio boundary rests on the defined operational zero point instead of an
  estimated wake end (F4);
* loadability is resolved per backend at catalog load and refresh instead of
  per selection at admission time (F3).

The historical C1/C2 run artifacts under ``docs/.archiv/`` are untouched.
"""

import json
import tempfile
import threading
import types
import unittest
from pathlib import Path

from api_fastapi_server import settings_control as sc
from api_fastapi_server.protocol_v2 import ports, schema
from api_fastapi_server.wake_admission import WakeAdmissionCoordinator
from VoiceSTT.core import wake_audio_boundary as boundary_module
from VoiceSTT.core.wake_detection import (
    RawWakeCandidate,
    WakeAttemptPolicy,
    WakeDetectionEvaluator,
    WakeHit,
    WakeRuntimePolicy,
)
from VoiceSTT.core.wakeword_catalog import WakeWordCatalogAuthority

from .test_protocol_v2_e2e import V2Session, hello_message
from .test_protocol_v2_settings import build_admin_app
from .test_server_controlled_e2e import GateAwareRecorder, TestClient, build_app
from .wake_catalog_support import FakeCatalogService, build_bundle


BUNDLED_WAKE_WORD = "hey_jarvis"
ADMIN_HEADERS = {"x-admin-key": "test-admin-secret"}

ENTRIES = (
    ("hey_jarvis", "Hey Jarvis", ("jarvis",), "jarvis_v2.onnx"),
    ("alexa", "Alexa", (), "alexa.onnx"),
)


def wake_hello(ids=(BUNDLED_WAKE_WORD,), **kwargs):
    return hello_message(manual=True, wake_word=True, wake_word_ids=ids, **kwargs)


def candidate(identifier=BUNDLED_WAKE_WORD, score=0.91, generation=0,
              sample_position=32000, model_key=None):
    """One raw observation. Diagnostics only, never a domain event."""
    return RawWakeCandidate(
        canonical_wake_word_id=identifier,
        raw_score=score,
        frame_index=1,
        sample_position=sample_position,
        detector_generation=generation,
        model_key=model_key or identifier,
    )


def wake_hit(identifier=BUNDLED_WAKE_WORD, score=0.91, *, zero_point=32000,
             policy=None):
    """One finalized hit region, as the C3 tracker hands it to the admission."""
    return WakeHit(
        canonical_wake_word_id=identifier,
        peak_score=score,
        start_frame_index=0,
        start_sample=1280,
        qualification_frame_index=0,
        qualification_sample=1280,
        finalization_frame_index=1,
        operational_zero_point_sample=zero_point,
        prediction_frame_count=1,
        policy=policy or WakeAttemptPolicy(sensitivity=0.5),
    )


class Utterances:
    """Drives whole spoken wake words through one evaluator.

    One utterance is a run of prediction frames at or above the threshold
    followed by one frame below it - exactly the contiguous hit region the C3
    tracker groups into a single logical detection.
    """

    def __init__(self, evaluator, identifier=BUNDLED_WAKE_WORD):
        self.evaluator = evaluator
        self.identifier = identifier
        self.end_sample = 0

    def speak(self, score=0.91, frames=1, identifier=None):
        wake_word_id = identifier or self.identifier
        finalized = None
        for value in [score] * frames + [0.0]:
            self.end_sample += 1280
            offered = self.evaluator.observe_scores(
                {wake_word_id: value}, end_sample=self.end_sample
            )
            finalized = offered or finalized
        return finalized


class BundleTestCase(unittest.TestCase):
    def setUp(self):
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.tmp = Path(self._tempdir.name)

    def authority(self, entries=ENTRIES, **kwargs):
        root = build_bundle(self.tmp / "bundle", entries)
        kwargs.setdefault("artifact_prober", lambda path: None)
        return WakeWordCatalogAuthority(asset_root=root, **kwargs), root


# -- F1: the v2 wire admits canonical ids only ---------------------------------

class F1WireCanonicalityTests(BundleTestCase):
    """RED against C1: the wire admitted aliases and display names."""

    def test_the_wire_admission_accepts_only_canonical_ids(self):
        authority, _root = self.authority()
        port = ports.WakeWordPort(FakeCatalogService(authority))

        selection, errors = port.resolve_selection(["hey_jarvis"])
        self.assertEqual(errors, [])
        self.assertEqual(selection.wake_word_ids, ("hey_jarvis",))

        for wire_value in ("jarvis", "Hey Jarvis", "HEY-JARVIS", "hey.jarvis",
                           "HEY_JARVIS", "does_not_exist"):
            with self.subTest(wire_value=wire_value):
                selection, errors = port.resolve_selection([wire_value])
                self.assertIsNone(selection)
                self.assertEqual(len(errors), 1)
                self.assertEqual(errors[0]["code"], "wake_word_unavailable")
                self.assertEqual(errors[0]["wakeWordId"], wire_value)

    def test_a_wire_alias_is_reported_as_not_canonical(self):
        authority, _root = self.authority()
        port = ports.WakeWordPort(FakeCatalogService(authority))
        _selection, errors = port.resolve_selection(["jarvis"])
        self.assertEqual(errors[0]["reason"], "not_canonical")
        _selection, errors = port.resolve_selection(["nope"])
        self.assertEqual(errors[0]["reason"], "unknown")

    def test_one_non_canonical_id_rejects_the_whole_selection(self):
        authority, _root = self.authority()
        port = ports.WakeWordPort(FakeCatalogService(authority))
        selection, errors = port.resolve_selection(["hey_jarvis", "jarvis"])
        self.assertIsNone(selection)
        self.assertEqual([error["wakeWordId"] for error in errors], ["jarvis"])

    def test_the_human_resolver_still_accepts_explicit_aliases(self):
        """The tolerant resolver stays intact for human configuration."""
        authority, _root = self.authority()
        self.assertEqual(authority.resolve("jarvis"), "hey_jarvis")
        self.assertEqual(authority.resolve("Hey Jarvis"), "hey_jarvis")
        self.assertEqual(authority.resolve("HEY-JARVIS"), "hey_jarvis")
        selection, errors = authority.resolve_human_selection(["jarvis"])
        self.assertEqual(errors, ())
        self.assertEqual(selection.wake_word_ids, ("hey_jarvis",))


class F1WireEndToEndTests(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()
        if self.app.state.voicestt_service.wakeword_catalog.snapshot() is None:
            self.skipTest("no bundled catalog")

    def _reject_reason(self, wire_id):
        with TestClient(self.app) as client:
            with V2Session(
                client, hello=wake_hello((wire_id,)), expect_accept=False
            ) as session:
                payload = session.drain(schema.SESSION_REJECTED, timeout=15.0)
        return payload

    def test_the_canonical_id_is_accepted(self):
        with TestClient(self.app) as client:
            with V2Session(client, hello=wake_hello()) as session:
                self.assertIsNotNone(session.session_id)

    def test_alias_and_display_name_are_rejected_on_the_wire(self):
        for wire_id in ("jarvis", "Hey Jarvis", "HEY-JARVIS"):
            with self.subTest(wire_id=wire_id):
                payload = self._reject_reason(wire_id)
                self.assertEqual(payload["type"], schema.SESSION_REJECTED)
                errors = payload["errors"]
                self.assertEqual(
                    {error["code"] for error in errors},
                    {"wake_word_unavailable"},
                )
                self.assertEqual(
                    [error["reason"] for error in errors], ["not_canonical"]
                )

    def test_an_unknown_id_is_still_rejected(self):
        payload = self._reject_reason("does_not_exist")
        self.assertEqual([e["reason"] for e in payload["errors"]], ["unknown"])


# -- F2: next_activation wake settings bind to the real runtime -----------------

class F2RuntimeBindingTests(unittest.TestCase):
    """RED against C1: a patch never reached the evaluator or the boundary."""

    def setUp(self):
        self.policies = [WakeRuntimePolicy(
            sensitivity=0.5, cooldown_ms=0, pre_roll_ms=0, settings_revision=0
        )]
        self.evaluator = WakeDetectionEvaluator(
            policy_supplier=lambda: self.policies[-1]
        )
        self.utterances = Utterances(self.evaluator)

    def patch(self, **changes):
        current = self.policies[-1]
        self.policies.append(WakeRuntimePolicy(
            sensitivity=changes.get("sensitivity", current.sensitivity),
            cooldown_ms=changes.get("cooldown_ms", current.cooldown_ms),
            pre_roll_ms=changes.get("pre_roll_ms", current.pre_roll_ms),
            settings_revision=current.settings_revision + 1,
        ))

    def test_a_sensitivity_patch_reaches_the_next_activation(self):
        # A: 0.5 -> a 0.6 utterance finalizes into a hit.
        self.assertIsNotNone(self.utterances.speak(score=0.6))
        # B: 0.9 -> the same 0.6 utterance never reaches the threshold.
        self.patch(sensitivity=0.9)
        self.assertIsNone(self.utterances.speak(score=0.6))
        self.assertEqual(self.evaluator.threshold, 0.9)
        self.assertIsNotNone(self.utterances.speak(score=0.95))

    def test_a_running_activation_keeps_its_latched_policy(self):
        offered = self.utterances.speak(score=0.6)
        self.evaluator.accept(offered, activation_id="act-1")
        latched = self.evaluator.active_policy

        self.patch(sensitivity=0.9, cooldown_ms=1500, pre_roll_ms=250)

        # While the activation runs the latched values stay in force.
        self.assertEqual(self.evaluator.active_policy, latched)
        self.assertEqual(self.evaluator.threshold, 0.5)
        self.assertEqual(self.evaluator.active_policy.pre_roll_ms, 0)

        # The next activation really uses the patched values.
        self.evaluator.release_latch(activation_id="act-1")
        self.assertIsNone(self.utterances.speak(score=0.6))
        self.assertEqual(self.evaluator.threshold, 0.9)
        self.assertEqual(self.evaluator.active_policy.cooldown_ms, 1500)
        self.assertEqual(self.evaluator.active_policy.pre_roll_ms, 250)

    def test_a_pre_roll_patch_changes_the_real_boundary_of_the_next_activation(self):
        offered = self.utterances.speak()
        first = boundary_module.resolve_wake_audio_boundary(
            operational_zero_point_sample=offered.operational_zero_point_sample,
            pre_roll_ms=offered.policy.pre_roll_ms,
            sample_rate=16000,
        )
        self.assertEqual(first.pre_roll_samples, 0)
        self.evaluator.accept(offered, activation_id="act-1")

        self.patch(pre_roll_ms=100)
        self.evaluator.release_latch(activation_id="act-1")

        offered = self.utterances.speak()
        second = boundary_module.resolve_wake_audio_boundary(
            operational_zero_point_sample=offered.operational_zero_point_sample,
            pre_roll_ms=offered.policy.pre_roll_ms,
            sample_rate=16000,
        )
        self.assertEqual(second.pre_roll_samples, 1600)

    def test_a_cooldown_patch_changes_the_real_cooldown_of_the_next_attempt(self):
        self.assertEqual(self.evaluator.cooldown_ms, 0)
        self.patch(cooldown_ms=750)
        self.utterances.speak()
        self.assertEqual(self.evaluator.cooldown_ms, 750)


class F2SessionBindingTests(unittest.TestCase):
    """The same binding, observed through a real v2 session."""

    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()
        if self.app.state.voicestt_service.wakeword_catalog.snapshot() is None:
            self.skipTest("no bundled catalog")

    def _domain(self):
        sessions = self.app.state.voicestt_service.sessions.all()
        self.assertEqual(len(sessions), 1)
        return sessions[0]

    def test_a_session_settings_patch_reaches_the_real_evaluator(self):
        with TestClient(self.app) as client:
            with V2Session(client, hello=wake_hello()) as session:
                domain = self._domain()
                evaluator = domain.recorder.wake_detection_evaluator
                self.assertIsNotNone(evaluator)
                before = evaluator.threshold

                sent = session.command({
                    "type": schema.SESSION_SETTINGS_PATCH,
                    "baseSettingsRevision": 0,
                    "changes": {
                        sc.WAKE_WORD_SENSITIVITY: 0.87,
                        sc.WAKE_WORD_PRE_ROLL_MS: 120,
                        sc.WAKE_WORD_COOLDOWN_MS: 300,
                    },
                })
                ack = session.ack(sent["commandId"])
                self.assertTrue(ack["accepted"], ack)

                # Idle: the very next attempt must use the new values.
                evaluator.observe_scores({BUNDLED_WAKE_WORD: 0.99})
                self.assertNotEqual(evaluator.threshold, before)
                self.assertEqual(evaluator.threshold, 0.87)
                self.assertEqual(evaluator.active_policy.pre_roll_ms, 120)
                self.assertEqual(evaluator.active_policy.cooldown_ms, 300)


# -- F3: unloadable artifacts are refused before hello.accepted ----------------

class F3UnloadableAdmissionTests(BundleTestCase):
    """RED against C1: a corrupt artifact passed admission."""

    def _authority_with_prober(self, bad=()):
        root = build_bundle(self.tmp / "bundle", ENTRIES)
        bad_names = set(bad)

        def prober(path):
            if Path(path).name in bad_names:
                raise RuntimeError("invalid onnx header")

        return WakeWordCatalogAuthority(
            asset_root=root, artifact_prober=prober
        ), root

    def test_an_unloadable_artifact_rejects_the_session(self):
        authority, _root = self._authority_with_prober(bad={"jarvis_v2.onnx"})
        selection, errors = authority.admit_selection(["hey_jarvis"])
        self.assertIsNone(selection)
        self.assertEqual(errors[0].reason, "artifact_unloadable")
        self.assertEqual(errors[0].code, "wake_word_unavailable")
        self.assertEqual(errors[0].wake_word_id, "hey_jarvis")
        self.assertNotIn("invalid onnx header", errors[0].message)

    def test_one_unloadable_of_several_rejects_the_whole_selection(self):
        authority, _root = self._authority_with_prober(bad={"alexa.onnx"})
        selection, errors = authority.admit_selection(["hey_jarvis", "alexa"])
        self.assertIsNone(selection)
        self.assertEqual([e.wake_word_id for e in errors], ["alexa"])

    def test_every_declared_artifact_is_probed_at_catalog_load(self):
        """AP-SRV-060 C3 corrected F3: loadability belongs to load/refresh.

        C2 probed only the *selected* artifacts, at admission time, which left
        the public catalog claiming availability for models nobody had tried to
        load. C3 resolves per-backend health for every declared artifact when
        the catalog is loaded and on every refresh. That does not weaken
        selected-only runtime loading: a running session still keeps only its
        selected classifiers in the live engine.
        """
        root = build_bundle(self.tmp / "bundle", ENTRIES)
        probed = []
        authority = WakeWordCatalogAuthority(
            asset_root=root, artifact_prober=probed.append
        )
        names = sorted(Path(path).name for path in probed)
        self.assertIn("jarvis_v2.onnx", names)
        self.assertIn("alexa.onnx", names)
        selection, errors = authority.admit_selection(["hey_jarvis"])
        self.assertEqual(errors, ())
        self.assertEqual(selection.wake_word_ids, ("hey_jarvis",))
        # Selected-only runtime loading: exactly one classifier is handed to
        # the live engine, whatever the catalog probed.
        self.assertEqual(len(selection.model_paths), 1)

    def test_an_admission_never_reprobes_an_already_resolved_artifact(self):
        root = build_bundle(self.tmp / "bundle", ENTRIES)
        probed = []
        authority = WakeWordCatalogAuthority(
            asset_root=root, artifact_prober=probed.append
        )
        probed.clear()
        for _ in range(5):
            authority.admit_selection(["hey_jarvis"])
        self.assertEqual(probed, [])

    def test_a_real_corrupt_onnx_is_refused_by_the_default_prober(self):
        """The bundle declares no integrity data, so the probe is the gate."""
        root = build_bundle(self.tmp / "bundle", ENTRIES)
        manifest = json.loads((root / "models.json").read_text(encoding="utf-8"))
        for entry in manifest["wakeWords"]:
            entry["artifacts"]["onnx"].pop("sha256", None)
            entry["artifacts"]["onnx"].pop("bytes", None)
        (root / "models.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8", newline="\n"
        )
        (root / "jarvis_v2.onnx").write_bytes(b"this is not an onnx model")
        authority = WakeWordCatalogAuthority(asset_root=root)
        selection, errors = authority.admit_selection(["hey_jarvis"])
        self.assertIsNone(selection)
        self.assertEqual(errors[0].reason, "artifact_unloadable")

    def test_a_tampered_artifact_is_refused_before_the_probe(self):
        """C3 additionally validates the integrity data the manifest declares."""
        root = build_bundle(self.tmp / "bundle", ENTRIES)
        (root / "jarvis_v2.onnx").write_bytes(b"this is not an onnx model")
        authority = WakeWordCatalogAuthority(
            asset_root=root, artifact_prober=lambda path: None
        )
        selection, errors = authority.admit_selection(["hey_jarvis"])
        self.assertIsNone(selection)
        self.assertEqual(errors[0].reason, "artifact_integrity_mismatch")


class F3UnloadableSessionTests(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()
        self.service = self.app.state.voicestt_service
        if self.service.wakeword_catalog.snapshot() is None:
            self.skipTest("no bundled catalog")

    def test_no_session_is_built_when_the_artifact_cannot_load(self):
        catalog = self.service.wakeword_catalog
        catalog.set_artifact_prober(
            lambda path: (_ for _ in ()).throw(RuntimeError("corrupt"))
            if Path(path).name == "jarvis_v2.onnx" else None
        )
        with TestClient(self.app) as client:
            with V2Session(
                client, hello=wake_hello(), expect_accept=False
            ) as session:
                payload = session.drain(schema.SESSION_REJECTED, timeout=15.0)

        self.assertEqual(payload["type"], schema.SESSION_REJECTED)
        self.assertEqual(
            [e["reason"] for e in payload["errors"]], ["artifact_unloadable"]
        )
        self.assertNotIn("sessionId", payload)
        # No half-built session and no recorder for it.
        self.assertEqual(self.service.sessions.all(), [])
        self.assertEqual(GateAwareRecorder.instances, [])


# -- F4: the audio boundary names what it really is ----------------------------

class F4BoundaryHonestyTests(unittest.TestCase):
    """C2 called the wake end an estimate; C3 defined the zero point instead.

    F4's substance - the boundary must not claim more than it knows - is kept.
    What changed is what there is to know: Root defined the operational zero
    point as the trailing edge of the winning qualified hit region, a
    deliberate server-side product decision that does not have to be discovered
    by external audio annotation. What stays open is the *empirical
    calibration* (WW-18/WW-19), and the settings schema still says so.
    """

    def test_the_boundary_names_the_operational_zero_point(self):
        result = boundary_module.resolve_wake_audio_boundary(
            operational_zero_point_sample=32000,
            pre_roll_ms=0,
            sample_rate=16000,
        )
        payload = result.to_dict()
        self.assertEqual(payload["boundaryBasis"], "operational_zero_point")
        self.assertTrue(payload["boundaryDefined"])
        self.assertEqual(payload["operationalZeroPointSample"], 32000)

    def test_no_field_claims_an_estimated_or_annotated_wake_end(self):
        result = boundary_module.resolve_wake_audio_boundary(
            operational_zero_point_sample=32000
        )
        self.assertFalse(hasattr(result, "estimated_wake_end_sample"))
        self.assertFalse(hasattr(result, "wake_end_sample"))
        self.assertTrue(hasattr(result, "operational_zero_point_sample"))
        self.assertNotIn("estimatedWakeEndSample", result.to_dict())


# -- F5: the calibration keys are published as provisional ---------------------

class F5ProvisionalCalibrationTests(unittest.TestCase):
    def test_both_calibration_keys_declare_their_pending_calibration(self):
        registry = sc.build_default_registry()
        for key, trace in ((sc.WAKE_WORD_COOLDOWN_MS, "WW-18"),
                           (sc.WAKE_WORD_PRE_ROLL_MS, "WW-19")):
            with self.subTest(key=key):
                definition = registry.get(key)
                self.assertEqual(
                    definition.constraints["calibration"], "pending"
                )
                self.assertIn(
                    trace, definition.constraints["calibrationTraceabilityIds"]
                )

    def test_the_public_schema_exposes_the_provisional_marker(self):
        app = build_admin_app()
        with TestClient(app) as client:
            payload = client.get("/api/v2/settings/schema").json()
        entries = {item["key"]: item for item in payload["settings"]}
        for key in (sc.WAKE_WORD_COOLDOWN_MS, sc.WAKE_WORD_PRE_ROLL_MS):
            with self.subTest(key=key):
                self.assertEqual(
                    entries[key]["constraints"]["calibration"], "pending"
                )


# -- F6: no implicit blocking window survives the safe input close -------------

class F6RearmTests(unittest.TestCase):
    """RED against C1: ``release_latch`` left ``blocked_until`` in place.

    C2 closed that with an implicit de-duplication window that was cleared at
    the safe input close. C3 removed the implicit window altogether: grouping
    one utterance into a single logical hit is the
    :class:`~VoiceSTT.core.wake_detection.WakeHitTracker`'s job and needs no
    timer, so the only blocking windows left are the latch and the operator's
    own ``wakeWord.cooldownMs``. F6's guarantee therefore holds a fortiori and
    is pinned here in its C3 form.
    """

    def _evaluator(self, cooldown_ms=0, clock=None):
        return WakeDetectionEvaluator(
            policy_supplier=lambda: WakeRuntimePolicy(
                sensitivity=0.5, cooldown_ms=cooldown_ms, pre_roll_ms=0,
                settings_revision=0,
            ),
            clock=clock,
        )

    def test_a_safe_input_close_fully_rearms_the_detector(self):
        evaluator = self._evaluator()
        utterances = Utterances(evaluator)
        offered = utterances.speak()
        evaluator.accept(offered, activation_id="act-1")

        evaluator.release_latch(activation_id="act-1")

        # A clearly separate new utterance must be admissible immediately.
        self.assertIsNotNone(utterances.speak())

    def test_a_refused_hit_leaves_no_implicit_blocking_window(self):
        evaluator = self._evaluator()
        utterances = Utterances(evaluator)
        evaluator.refuse(utterances.speak())
        # The refusal is not a fachliches Ereignis and, with cooldown 0, it
        # blocks nothing: the next utterance is a new hit region.
        self.assertIsNotNone(utterances.speak())

    def test_a_refusal_during_an_activation_is_cleared_by_the_close(self):
        evaluator = self._evaluator()
        utterances = Utterances(evaluator)
        offered = utterances.speak()
        evaluator.accept(offered, activation_id="act-1")
        evaluator.refuse(None)
        evaluator.release_latch(activation_id="act-1")
        self.assertIsNotNone(utterances.speak())

    def test_an_explicitly_configured_cooldown_survives_by_design(self):
        clock = [0.0]
        evaluator = self._evaluator(cooldown_ms=2000, clock=lambda: clock[0])
        utterances = Utterances(evaluator)
        offered = utterances.speak()
        evaluator.accept(offered, activation_id="act-1")
        evaluator.release_latch(activation_id="act-1")

        # The configured cooldown is deliberate post-close semantics ...
        self.assertIsNone(utterances.speak())
        clock[0] += 2.0
        # ... and it expires exactly after the configured duration.
        self.assertIsNotNone(utterances.speak())

    def test_only_the_configured_cooldown_blocks_after_the_close(self):
        clock = [0.0]
        evaluator = self._evaluator(cooldown_ms=10, clock=lambda: clock[0])
        utterances = Utterances(evaluator)
        offered = utterances.speak()
        evaluator.accept(offered, activation_id="act-1")
        evaluator.release_latch(activation_id="act-1")
        clock[0] += 0.011
        # Only the 10 ms configured cooldown may ever apply - there is no
        # implicit receptive-field window left to outlive it.
        self.assertIsNotNone(utterances.speak())


# -- F7: commit/fault boundary --------------------------------------------------

class RecordingController:
    """A minimal activation authority that records its commit point."""

    def __init__(self, *, accept=True, raise_before_commit=False):
        self.accept = accept
        self.raise_before_commit = raise_before_commit
        self.activations = []

    def activate(self):
        if self.raise_before_commit:
            raise RuntimeError("pre-commit failure")
        if not self.accept:
            return None
        activation_id = f"act-{len(self.activations) + 1}"
        self.activations.append(activation_id)
        return activation_id


class F7FaultBoundaryTests(unittest.TestCase):
    """RED against C1: any exception became a refusal, even after commit."""

    def _coordinator(self, activate, publish=None, committed_probe=None):
        evaluator = WakeDetectionEvaluator(
            policy_supplier=lambda: WakeRuntimePolicy(
                sensitivity=0.5, cooldown_ms=0, pre_roll_ms=0,
                settings_revision=0,
            )
        )
        return WakeAdmissionCoordinator(
            evaluator=evaluator, activate=activate, publish=publish,
            committed_probe=committed_probe,
        ), evaluator

    def test_a_raise_after_a_real_commit_is_not_a_refusal(self):
        """Even a callable that raises cannot lose a committed activation."""
        controller = RecordingController()

        def activate(_candidate, _boundary):
            controller.activate()
            raise RuntimeError("crashed after the commit")

        coordinator, evaluator = self._coordinator(
            activate,
            publish=lambda detection: None,
            committed_probe=lambda: (
                controller.activations[-1] if controller.activations else None
            ),
        )
        detection = coordinator.admit(wake_hit())

        self.assertIsNotNone(detection)
        self.assertEqual(detection.activation_id, "act-1")
        self.assertTrue(evaluator.latched)

    def test_a_raise_without_a_commit_stays_a_refusal(self):
        controller = RecordingController(raise_before_commit=True)

        def activate(_candidate, _boundary):
            controller.activate()

        coordinator, evaluator = self._coordinator(
            activate,
            committed_probe=lambda: (
                controller.activations[-1] if controller.activations else None
            ),
        )
        self.assertIsNone(coordinator.admit(wake_hit()))
        self.assertFalse(evaluator.latched)

    def test_a_pre_commit_failure_leaves_no_activation_and_no_latch(self):
        controller = RecordingController(raise_before_commit=True)
        published = []

        def activate(_candidate, _boundary):
            controller.activate()
            raise AssertionError("unreachable")

        coordinator, evaluator = self._coordinator(activate, published.append)
        self.assertIsNone(coordinator.admit(wake_hit()))
        self.assertEqual(controller.activations, [])
        self.assertFalse(evaluator.latched)
        self.assertEqual(published, [])

    def test_a_post_commit_failure_is_never_turned_into_a_refusal(self):
        controller = RecordingController()
        published = []

        def activate(_candidate, _boundary):
            activation_id = controller.activate()
            # Event collection fails *after* the activation was committed.
            return types.SimpleNamespace(
                committed=True, activation_id=activation_id,
                error=RuntimeError("event projection failed"),
            )

        coordinator, evaluator = self._coordinator(activate, published.append)
        detection = coordinator.admit(wake_hit())

        self.assertIsNotNone(detection)
        self.assertEqual(detection.activation_id, "act-1")
        self.assertTrue(evaluator.latched)
        self.assertEqual(len(published), 1)
        self.assertEqual(controller.activations, ["act-1"])

    def test_a_failing_detected_publish_keeps_activation_and_latch(self):
        controller = RecordingController()

        def activate(_candidate, _boundary):
            return types.SimpleNamespace(
                committed=True, activation_id=controller.activate(), error=None
            )

        def publish(_detection):
            raise RuntimeError("transport is gone")

        coordinator, evaluator = self._coordinator(activate, publish)
        detection = coordinator.admit(wake_hit())

        self.assertIsNotNone(detection)
        self.assertTrue(evaluator.latched)
        self.assertEqual(evaluator.latched_activation_id, "act-1")
        self.assertEqual(coordinator.accepted_detection, detection)

    def test_a_refused_admission_stays_a_refusal(self):
        controller = RecordingController(accept=False)
        published = []

        def activate(_candidate, _boundary):
            activation_id = controller.activate()
            return types.SimpleNamespace(
                committed=False, activation_id=activation_id, error=None
            )

        coordinator, evaluator = self._coordinator(activate, published.append)
        self.assertIsNone(coordinator.admit(wake_hit()))
        self.assertFalse(evaluator.latched)
        self.assertEqual(published, [])

    def test_exactly_one_admission_wins_under_a_concurrent_close(self):
        for iteration in range(20):
            with self.subTest(iteration=iteration):
                self._concurrent_close_round()

    def _concurrent_close_round(self):
        controller = RecordingController()
        closed = threading.Event()
        published = []
        lock = threading.Lock()

        def activate(_candidate, _boundary):
            if closed.is_set():
                return types.SimpleNamespace(
                    committed=False, activation_id=None, error=None
                )
            return types.SimpleNamespace(
                committed=True, activation_id=controller.activate(), error=None
            )

        def publish(detection):
            with lock:
                published.append(detection)

        coordinator, evaluator = self._coordinator(activate, publish)

        barrier = threading.Barrier(2)
        results = []

        def admitter():
            barrier.wait(timeout=5)
            with lock:
                results.append(coordinator.admit(wake_hit()))

        def closer():
            barrier.wait(timeout=5)
            closed.set()
            coordinator.release()

        threads = [threading.Thread(target=admitter),
                   threading.Thread(target=closer)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())

        accepted = [item for item in results if item is not None]
        self.assertLessEqual(len(accepted), 1)
        self.assertEqual(len(published), len(accepted))
        self.assertEqual(len(controller.activations), len(accepted))


class F7SessionFaultTests(unittest.TestCase):
    """The same boundary through a real session and a real controller."""

    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()
        if self.app.state.voicestt_service.wakeword_catalog.snapshot() is None:
            self.skipTest("no bundled catalog")

    def _domain(self):
        sessions = self.app.state.voicestt_service.sessions.all()
        self.assertEqual(len(sessions), 1)
        return sessions[0]

    def test_a_failing_event_publish_keeps_the_committed_activation(self):
        with TestClient(self.app) as client:
            with V2Session(client, hello=wake_hello()) as session:
                domain = self._domain()
                domain._wake_detection_epoch = domain._lifecycle_epoch

                original = domain._publish_collected_events

                def exploding(events):
                    raise RuntimeError("publisher is gone")

                domain._publish_collected_events = exploding
                try:
                    detection = domain._on_wakeword_detected(wake_hit())
                finally:
                    domain._publish_collected_events = original

                self.assertIsNotNone(detection)
                snapshot = domain._activation.snapshot()

        # The activation really exists and carries the wake source.
        self.assertEqual(snapshot["activationId"], detection.activation_id)
        self.assertEqual(snapshot["primarySource"], "wake_word")
        self.assertNotEqual(snapshot["phase"], "idle")


# -- F8: every visible catalog change emits the event --------------------------

class F8CatalogEventTests(BundleTestCase):
    """RED against C1: a metadata-only change bumped the revision silently."""

    def setUp(self):
        super().setUp()
        self.events = []
        self.authority, self.root = self.authority_with_events()

    def authority_with_events(self):
        root = build_bundle(self.tmp / "bundle", ENTRIES)
        authority = WakeWordCatalogAuthority(
            asset_root=root,
            artifact_prober=lambda path: None,
            on_catalog_changed=lambda revision, ids, availability_changed: (
                self.events.append((revision, tuple(ids), availability_changed))
            ),
        )
        return authority, root

    def test_a_metadata_only_change_bumps_the_revision_and_emits_one_event(self):
        before = self.authority.catalog_revision
        build_bundle(self.root, (
            ("hey_jarvis", "Hey Jarvis 2", ("jarvis", "jarv"), "jarvis_v2.onnx"),
            ("alexa", "Alexa", (), "alexa.onnx"),
        ))
        result = self.authority.refresh()

        self.assertTrue(result.ok)
        self.assertTrue(result.changed)
        self.assertEqual(result.catalog_revision, before + 1)
        self.assertEqual(len(self.events), 1)
        self.assertEqual(self.events[0][0], before + 1)
        # Availability did not change, but the client still learns the revision.
        self.assertFalse(self.events[0][2])
        self.assertEqual(
            set(self.events[0][1]), set(self.authority.available_ids())
        )

    def test_no_visible_change_emits_nothing(self):
        before = self.authority.catalog_revision
        self.events.clear()
        result = self.authority.refresh()
        self.assertTrue(result.ok)
        self.assertFalse(result.changed)
        self.assertEqual(self.authority.catalog_revision, before)
        self.assertEqual(self.events, [])

    def test_an_availability_change_emits_the_event(self):
        self.events.clear()
        before = self.authority.catalog_revision
        result = self.authority.set_global_disabled(["alexa"])
        self.assertEqual(result.catalog_revision, before + 1)
        self.assertEqual(len(self.events), 1)
        self.assertTrue(self.events[0][2])
        self.assertNotIn("alexa", self.events[0][1])

    def test_a_failed_refresh_emits_nothing_and_keeps_the_revision(self):
        self.events.clear()
        before = self.authority.catalog_revision
        (self.root / "models.json").write_text("{ broken", encoding="utf-8")
        result = self.authority.refresh()
        self.assertFalse(result.ok)
        self.assertEqual(self.authority.catalog_revision, before)
        self.assertEqual(self.events, [])


class F8SessionEventTests(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()
        self.service = self.app.state.voicestt_service
        if self.service.wakeword_catalog.snapshot() is None:
            self.skipTest("no bundled catalog")

    def test_a_metadata_only_change_reaches_a_live_session(self):
        """C1 dropped this event because availability had not changed."""
        with TestClient(self.app) as client:
            with V2Session(client, hello=wake_hello()) as session:
                catalog = self.service.wakeword_catalog
                revision = catalog.catalog_revision + 1
                available = list(catalog.available_ids())
                # Exactly what the authority reports for a metadata-only
                # change: a new revision with unchanged availability.
                self.service._on_wake_word_catalog_changed(
                    revision, available, False
                )
                event = session.drain(
                    schema.EVENT_WAKEWORD_AVAILABILITY_CHANGED, timeout=15.0
                )
        self.assertEqual(event["catalogRevision"], revision)
        self.assertIn(BUNDLED_WAKE_WORD, event["availableWakeWordIds"])


# -- F9: every public entry carries its catalogRevision ------------------------

class F9EntryRevisionTests(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_admin_app()

    def test_every_entry_carries_the_snapshot_revision(self):
        with TestClient(self.app) as client:
            payload = client.get("/api/v2/wake-words").json()
        self.assertTrue(payload["wakeWords"])
        for entry in payload["wakeWords"]:
            with self.subTest(wake_word=entry["id"]):
                self.assertEqual(
                    entry["catalogRevision"], payload["catalogRevision"]
                )

    def test_a_refresh_keeps_top_level_and_entry_revisions_consistent(self):
        with TestClient(self.app) as client:
            revision = client.get("/api/v2/settings/server").json()[
                "settingsRevision"
            ]
            client.patch(
                "/api/v2/settings/server",
                headers=ADMIN_HEADERS,
                json={
                    "baseSettingsRevision": revision,
                    "changes": {sc.WAKE_WORD_GLOBAL_DISABLED: ["alexa"]},
                },
            )
            payload = client.get("/api/v2/wake-words").json()

        self.assertTrue(payload["wakeWords"])
        for entry in payload["wakeWords"]:
            self.assertEqual(
                entry["catalogRevision"], payload["catalogRevision"]
            )

    def test_the_entry_revision_does_not_feed_back_into_the_revision(self):
        """A revision inside an entry must not make every refresh 'visible'."""
        with TestClient(self.app) as client:
            before = client.get("/api/v2/wake-words").json()["catalogRevision"]
            for _ in range(3):
                client.post("/api/v2/wake-words/refresh", headers=ADMIN_HEADERS)
            after = client.get("/api/v2/wake-words").json()["catalogRevision"]
        self.assertEqual(after, before)


# -- F10: one atomic projection per refresh response ---------------------------

class F10AtomicRefreshTests(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_admin_app()
        self.service = self.app.state.voicestt_service

    def test_the_refresh_response_is_one_consistent_projection(self):
        with TestClient(self.app) as client:
            response = client.post(
                "/api/v2/wake-words/refresh", headers=ADMIN_HEADERS
            )
        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["wakeWords"])
        for entry in payload["wakeWords"]:
            self.assertEqual(
                entry["catalogRevision"], payload["catalogRevision"]
            )
        self.assertEqual(
            sorted(payload["availableWakeWordIds"]),
            sorted(e["id"] for e in payload["wakeWords"] if e["available"]),
        )

    def test_refresh_and_global_disable_are_linearised(self):
        for iteration in range(20):
            with self.subTest(iteration=iteration):
                app = build_admin_app()
                service = app.state.voicestt_service
                with TestClient(app) as client:
                    revision = client.get("/api/v2/settings/server").json()[
                        "settingsRevision"
                    ]
                    barrier = threading.Barrier(2)
                    results = {}

                    def refresher():
                        barrier.wait(timeout=10)
                        results["refresh"] = client.post(
                            "/api/v2/wake-words/refresh", headers=ADMIN_HEADERS
                        ).json()

                    def disabler():
                        barrier.wait(timeout=10)
                        results["patch"] = client.patch(
                            "/api/v2/settings/server",
                            headers=ADMIN_HEADERS,
                            json={
                                "baseSettingsRevision": revision,
                                "changes": {
                                    sc.WAKE_WORD_GLOBAL_DISABLED: ["alexa"]
                                },
                            },
                        ).status_code

                    threads = [threading.Thread(target=refresher),
                               threading.Thread(target=disabler)]
                    for thread in threads:
                        thread.start()
                    for thread in threads:
                        thread.join(timeout=10)
                        self.assertFalse(thread.is_alive())

                    final = client.get("/api/v2/wake-words").json()

                # Every response describes one consistent snapshot.
                refresh = results["refresh"]
                for entry in refresh["wakeWords"]:
                    self.assertEqual(
                        entry["catalogRevision"], refresh["catalogRevision"]
                    )
                self.assertEqual(
                    sorted(refresh["availableWakeWordIds"]),
                    sorted(e["id"] for e in refresh["wakeWords"]
                           if e["available"]),
                )
                for entry in final["wakeWords"]:
                    self.assertEqual(
                        entry["catalogRevision"], final["catalogRevision"]
                    )
                # The disable always wins in the end - it is the later state.
                entries = {e["id"]: e for e in final["wakeWords"]}
                self.assertFalse(entries["alexa"]["available"])
                self.assertEqual(
                    entries["alexa"]["unavailableReason"], "globally_disabled"
                )

    def test_refresh_and_catalog_read_never_mix_two_states(self):
        for iteration in range(20):
            with self.subTest(iteration=iteration):
                app = build_admin_app()
                with TestClient(app) as client:
                    barrier = threading.Barrier(2)
                    seen = []

                    def refresher():
                        barrier.wait(timeout=10)
                        client.post(
                            "/api/v2/wake-words/refresh", headers=ADMIN_HEADERS
                        )

                    def reader():
                        barrier.wait(timeout=10)
                        seen.append(client.get("/api/v2/wake-words").json())

                    threads = [threading.Thread(target=refresher),
                               threading.Thread(target=reader)]
                    for thread in threads:
                        thread.start()
                    for thread in threads:
                        thread.join(timeout=10)
                        self.assertFalse(thread.is_alive())

                    payload = seen[0]
                    for entry in payload["wakeWords"]:
                        self.assertEqual(
                            entry["catalogRevision"], payload["catalogRevision"]
                        )

    def test_refresh_and_session_admission_stay_consistent(self):
        app = build_app()
        service = app.state.voicestt_service
        if service.wakeword_catalog.snapshot() is None:
            self.skipTest("no bundled catalog")
        for iteration in range(20):
            with self.subTest(iteration=iteration):
                barrier = threading.Barrier(2)
                outcome = {}

                def refresher():
                    barrier.wait(timeout=10)
                    outcome["refresh"] = service.refresh_wake_word_catalog()

                def admitter():
                    barrier.wait(timeout=10)
                    outcome["admission"] = service.wakeword_catalog.admit_selection(
                        [BUNDLED_WAKE_WORD]
                    )

                threads = [threading.Thread(target=refresher),
                           threading.Thread(target=admitter)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=10)
                    self.assertFalse(thread.is_alive())

                self.assertTrue(outcome["refresh"].ok)
                selection, errors = outcome["admission"]
                self.assertEqual(errors, ())
                self.assertEqual(
                    selection.wake_word_ids, (BUNDLED_WAKE_WORD,)
                )
                self.assertEqual(
                    selection.catalog_revision,
                    service.wakeword_catalog.catalog_revision,
                )

    def test_a_failed_refresh_does_not_disturb_a_concurrent_disable(self):
        app = build_admin_app()
        service = app.state.voicestt_service
        with TestClient(app) as client:
            good = client.get("/api/v2/wake-words").json()
            revision = client.get("/api/v2/settings/server").json()[
                "settingsRevision"
            ]
            service.wakeword_catalog.set_loader_for_tests(
                lambda root: (_ for _ in ()).throw(
                    __import__(
                        "VoiceSTT.core.wakeword_catalog", fromlist=["x"]
                    ).WakeWordManifestError("broken manifest")
                )
            )
            barrier = threading.Barrier(2)
            results = {}

            def refresher():
                barrier.wait(timeout=10)
                results["refresh"] = client.post(
                    "/api/v2/wake-words/refresh", headers=ADMIN_HEADERS
                )

            def disabler():
                barrier.wait(timeout=10)
                results["patch"] = client.patch(
                    "/api/v2/settings/server",
                    headers=ADMIN_HEADERS,
                    json={
                        "baseSettingsRevision": revision,
                        "changes": {sc.WAKE_WORD_GLOBAL_DISABLED: ["alexa"]},
                    },
                )

            threads = [threading.Thread(target=refresher),
                       threading.Thread(target=disabler)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)
                self.assertFalse(thread.is_alive())

            final = client.get("/api/v2/wake-words").json()

        self.assertEqual(results["refresh"].status_code, 422)
        self.assertFalse(results["refresh"].json()["ok"])
        # The failed refresh kept the catalog; the disable still applied.
        entries = {e["id"]: e for e in final["wakeWords"]}
        self.assertEqual(len(final["wakeWords"]), len(good["wakeWords"]))
        self.assertFalse(entries["alexa"]["available"])
        for entry in final["wakeWords"]:
            self.assertEqual(
                entry["catalogRevision"], final["catalogRevision"]
            )


if __name__ == "__main__":
    unittest.main()
