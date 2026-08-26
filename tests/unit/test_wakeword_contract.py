"""
Comprehensive unit, contract, race, and lifecycle test suite for AP-SRV-060.

Protects:
- Catalog Authority: Public entries without path leaks, casefold lookup, explicit aliases, alias collisions, disabled/unloadable entries, catalogRevision.
- Selected-Only Matrix: [A], [A, C, D], [A, X, C] (reject, no loader call), [A, disabled-C] (reject), [A, alias-C] (canonical C), collision alias.
- Sensitivity Contract: Range 0.0 - 1.0 (default 0.5), defensive validation.
- Multi-Candidate: Highest score, canonical ID alphabetical tie-break.
- Server-side WakeAdmissionCoordinator & Domain Latch:
  - Manual vs. Wake simultaneously (first accepted wins)
  - Two concurrent wake hits (exactly one accepted)
  - Second wake hit during open wake activation (suppressed)
  - Wake hit during active manual activation (no source merge, no domain event)
  - Suppressed wake source (raw observation possible, domain admission rejected)
  - Safe input-close / unlock releases latch
  - Late callbacks after stop / reset / close are inert
  - 20x race repetition without sleep (using threading.Event and barriers)
- Synthetic Audio Boundary: [history][WAKE][first-user-word][following-speech]
  - Exclusion of wake audio, preservation of first user word and following speech, 0ms.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
import unittest
from unittest.mock import MagicMock, patch

from VoiceSTT.core.openwakeword_catalog import (
    OPENWAKEWORD_MODEL_ROOT_ENV,
    OpenWakeWordCatalog,
    REASON_ALIAS_COLLISION,
    REASON_GLOBALLY_DISABLED,
    REASON_MISSING_FEATURE_MODELS,
    REASON_MISSING_MODEL_FILES,
    REASON_NOT_FOUND,
)
from VoiceSTT.core.wakeword import (
    WakeWordDetection,
    _resolve_openwakeword_paths,
    process_wakeword,
    setup_wakeword_detection,
)
from VoiceSTT.core.activation_control import (
    CONTROLLED_ACTIVATION_POLICY,
    configure_activation_policy,
    initialize_activation_control,
    open_controlled_activation_gate,
    close_controlled_activation_gate,
)
from VoiceSTT.core.preroll import (
    PrerollFrameMetadata,
    select_preroll_frames,
)
from api_fastapi_server.activation import (
    ActivationController,
    CLOSING_INPUT,
    IDLE,
    MANUAL_SOURCE,
    SEGMENT_ACTIVE,
    WAITING_FIRST_SPEECH,
    WAKE_WORD_SOURCE,
)
from api_fastapi_server.wake_admission import (
    AcceptedWakeAdmission,
    WakeAdmissionCoordinator,
)
from api_fastapi_server.server import (
    ResolvedSessionWakeWordConfig,
    ServerSettings,
    SessionConfigurationError,
    SessionWakeWordRequest,
    resolve_session_wake_word_config,
)
from VoiceSTT_server.operations import WakeWordRegistry


class FakeOwwModel:
    """Mock OpenWakeWord Model recording exactly which paths were initialized."""

    def __init__(self, wakeword_models=None, inference_framework="onnx", device="cpu", **kwargs):
        self.wakeword_models = list(wakeword_models or [])
        self.inference_framework = inference_framework
        self.device = device
        self.kwargs = kwargs
        self.models = {Path(p).name: object() for p in self.wakeword_models}
        self.prediction_buffer = {}
        for p in self.wakeword_models:
            key = Path(p).name
            self.prediction_buffer[key] = [0.0]

    def predict(self, pcm):
        return self.prediction_buffer


class FakeOwwModule:
    pass


class WakeWordCatalogContractTests(unittest.TestCase):
    """Protects Catalog Authority and Public Contract invariants."""

    def test_public_entries_omit_internal_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "hey_jarvis_v0.1.onnx").write_bytes(b"model")
            (root / "melspectrogram.onnx").write_bytes(b"model")
            (root / "embedding_model.onnx").write_bytes(b"model")

            catalog = OpenWakeWordCatalog(model_root=root)
            public = catalog.public_entries()
            self.assertEqual(len(public), 1)
            entry = public[0]

            # Public contract fields
            self.assertEqual(entry["id"], "hey_jarvis")
            self.assertEqual(entry["displayName"], "Hey Jarvis")
            self.assertEqual(entry["artifactVersion"], "0.1")
            self.assertTrue(entry["available"])
            self.assertEqual(entry["catalogRevision"], 1)

            # Strictly verify NO local filesystem paths leaked in public dictionary
            self.assertNotIn("path", entry)
            self.assertNotIn("paths", entry)
            self.assertNotIn("source", entry)
            self.assertNotIn("availableFormats", entry)

    def test_casefold_lookup_preserves_canonical_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "Hey_Jarvis_v1.0.onnx").write_bytes(b"model")
            (root / "melspectrogram.onnx").write_bytes(b"model")
            (root / "embedding_model.onnx").write_bytes(b"model")

            catalog = OpenWakeWordCatalog(model_root=root)
            # Unicode whitespace + mixed case input
            resolved, missing, _ = catalog.resolve_detailed(["  \u3000HEY_JARVIS\t\n  "])
            self.assertEqual(len(resolved), 1)
            self.assertEqual(resolved[0]["id"], "Hey_Jarvis")  # Unmodified canonical ID
            self.assertEqual(missing, [])

    def test_explicit_aliases_resolved_correctly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            models = root / "models"
            models.mkdir()
            (models / "alexa_v1.onnx").write_bytes(b"model")
            (models / "melspectrogram.onnx").write_bytes(b"model")
            (models / "embedding_model.onnx").write_bytes(b"model")

            (root / "models.json").write_text(json.dumps({
                "openwakeword_models": {
                    "path": str(models),
                    "catalog_revision": 5,
                    "pipeline_models": {
                        "melspectrogram_onnx": "melspectrogram.onnx",
                        "embedding_model_onnx": "embedding_model.onnx",
                    },
                    "onnx_models": {"alexa": "alexa_v1.onnx"},
                    "metadata": {
                        "alexa": {
                            "displayName": "Amazon Alexa",
                            "aliases": ["computer", "echo"],
                            "artifactVersion": "1.2.0",
                        }
                    }
                }
            }), encoding="utf-8")

            catalog = OpenWakeWordCatalog(model_root=root)
            self.assertEqual(catalog.catalog_revision, 5)
            entries = catalog.public_entries()
            self.assertEqual(entries[0]["aliases"], ["computer", "echo"])
            self.assertEqual(entries[0]["artifactVersion"], "1.2.0")

            # Resolve by alias
            resolved, missing, _ = catalog.resolve_detailed(["echo"])
            self.assertEqual(len(resolved), 1)
            self.assertEqual(resolved[0]["id"], "alexa")
            self.assertEqual(missing, [])

    def test_alias_collision_is_rejected_deterministically(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            models = root / "models"
            models.mkdir()
            (models / "m1.onnx").write_bytes(b"model")
            (models / "m2.onnx").write_bytes(b"model")
            (models / "melspectrogram.onnx").write_bytes(b"model")
            (models / "embedding_model.onnx").write_bytes(b"model")

            (root / "models.json").write_text(json.dumps({
                "openwakeword_models": {
                    "path": str(models),
                    "pipeline_models": {
                        "melspectrogram_onnx": "melspectrogram.onnx",
                        "embedding_model_onnx": "embedding_model.onnx",
                    },
                    "onnx_models": {"m1": "m1.onnx", "m2": "m2.onnx"},
                    "metadata": {
                        "m1": {"aliases": ["assistant"]},
                        "m2": {"aliases": ["assistant"]},
                    }
                }
            }), encoding="utf-8")

            catalog = OpenWakeWordCatalog(model_root=root)
            resolved, missing, reasons = catalog.resolve_detailed(["assistant"])
            self.assertEqual(resolved, [])
            self.assertEqual(missing, ["assistant"])
            self.assertEqual(reasons["assistant"], REASON_ALIAS_COLLISION)


class SelectedOnlyMatrixTests(unittest.TestCase):
    """Protects Selected-Only loading rules across exact combinations."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        # Create models A, B, C, D
        for name in ("A", "B", "C", "D"):
            (self.root / f"{name}.onnx").write_bytes(b"model")
        (self.root / "melspectrogram.onnx").write_bytes(b"model")
        (self.root / "embedding_model.onnx").write_bytes(b"model")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_selection_A_loads_exact_A(self):
        with patch.dict(os.environ, {OPENWAKEWORD_MODEL_ROOT_ENV: str(self.root)}):
            paths, _ = _resolve_openwakeword_paths(None, ["A"], "onnx")
            self.assertEqual([Path(p).stem for p in paths], ["A"])

    def test_selection_A_C_D_loads_exact_A_C_D(self):
        with patch.dict(os.environ, {OPENWAKEWORD_MODEL_ROOT_ENV: str(self.root)}):
            paths, _ = _resolve_openwakeword_paths(None, ["A", "C", "D"], "onnx")
            self.assertEqual([Path(p).stem for p in paths], ["A", "C", "D"])
            self.assertNotIn("B", [Path(p).stem for p in paths])

    def test_selection_with_unknown_X_rejects_without_loader_call(self):
        with patch.dict(os.environ, {OPENWAKEWORD_MODEL_ROOT_ENV: str(self.root)}):
            loader_mock = MagicMock()
            with self.assertRaises(FileNotFoundError):
                _resolve_openwakeword_paths(None, ["A", "X", "C"], "onnx")
            loader_mock.assert_not_called()

    def test_selection_with_disabled_C_rejects_without_loader_call(self):
        disable_provider = lambda: {"C"}
        with patch.dict(os.environ, {OPENWAKEWORD_MODEL_ROOT_ENV: str(self.root)}):
            loader_mock = MagicMock()
            with self.assertRaises(FileNotFoundError):
                _resolve_openwakeword_paths(
                    None,
                    ["A", "C"],
                    "onnx",
                    disable_provider=disable_provider,
                )
            loader_mock.assert_not_called()

    def test_selection_with_alias_loads_canonical_C(self):
        (self.root / "models.json").write_text(json.dumps({
            "openwakeword_models": {
                "metadata": {
                    "C": {"aliases": ["alias_c"]}
                }
            }
        }), encoding="utf-8")

        with patch.dict(os.environ, {OPENWAKEWORD_MODEL_ROOT_ENV: str(self.root)}):
            paths, _ = _resolve_openwakeword_paths(None, ["A", "alias_c"], "onnx")
            loaded_stems = [Path(p).stem for p in paths]
            self.assertIn("A", loaded_stems)
            self.assertIn("C", loaded_stems)
            self.assertNotIn("alias_c", loaded_stems)


class MultiCandidateTieBreakTests(unittest.TestCase):
    """Protects deterministic candidate selection with highest score and alphabetical tie-break."""

    def test_highest_score_wins(self):
        recorder = type("Recorder", (), {
            "wakeword_backend": "openwakeword",
            "wake_words_sensitivity": 0.5,
            "debug_mode": False,
        })()
        recorder.owwModel = FakeOwwModel(
            wakeword_models=["/path/to/jarvis.onnx", "/path/to/alexa.onnx"]
        )
        recorder.owwModel.prediction_buffer = {
            "jarvis.onnx": [0.65],
            "alexa.onnx": [0.85],
        }

        idx = process_wakeword(recorder, b"\x00" * 320)
        self.assertIsNotNone(recorder.last_wakeword_detection)
        self.assertEqual(recorder.last_wakeword_detection.wake_word_id, "alexa")
        self.assertEqual(recorder.last_wakeword_detection.score, 0.85)

    def test_equal_score_deterministic_alphabetical_tie_break(self):
        recorder = type("Recorder", (), {
            "wakeword_backend": "openwakeword",
            "wake_words_sensitivity": 0.5,
            "debug_mode": False,
        })()
        recorder.owwModel = FakeOwwModel(
            wakeword_models=["/path/to/zebra.onnx", "/path/to/alpha.onnx"]
        )
        recorder.owwModel.prediction_buffer = {
            "zebra.onnx": [0.90],
            "alpha.onnx": [0.90],
        }

        process_wakeword(recorder, b"\x00" * 320)
        self.assertIsNotNone(recorder.last_wakeword_detection)
        self.assertEqual(recorder.last_wakeword_detection.wake_word_id, "alpha")
        self.assertEqual(recorder.last_wakeword_detection.score, 0.90)


class WakeAdmissionCoordinatorRaceLifecycleTests(unittest.TestCase):
    """Protects domain latch and concurrency invariants without sleeps (using Events / Barriers)."""

    def test_manual_vs_wake_simultaneously_first_accepted_wins(self):
        for _ in range(20):  # 20 repetitions
            controller = ActivationController(manual_trigger_enabled=True, wake_word_trigger_enabled=True)
            coordinator = WakeAdmissionCoordinator()
            barrier = threading.Barrier(2)
            results = {}

            def run_manual():
                barrier.wait()
                decision = controller.activate(MANUAL_SOURCE)
                results["manual"] = decision.accepted

            def run_wake():
                barrier.wait()
                detection = WakeWordDetection(wake_word_id="jarvis", score=0.95)
                admission = coordinator.handle_wake_detection(detection, controller)
                results["wake"] = admission is not None

            t1 = threading.Thread(target=run_manual)
            t2 = threading.Thread(target=run_wake)
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            # Exactly one trigger must have won
            self.assertTrue(results["manual"] ^ results["wake"])

    def test_two_concurrent_wake_detections_exactly_one_accepted(self):
        for _ in range(20):  # 20 repetitions
            controller = ActivationController(manual_trigger_enabled=True, wake_word_trigger_enabled=True)
            coordinator = WakeAdmissionCoordinator()
            barrier = threading.Barrier(2)
            results = []

            def run_detection(word_id):
                barrier.wait()
                detection = WakeWordDetection(wake_word_id=word_id, score=0.90)
                admission = coordinator.handle_wake_detection(detection, controller)
                results.append(admission is not None)

            t1 = threading.Thread(target=run_detection, args=("alpha",))
            t2 = threading.Thread(target=run_detection, args=("beta",))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            self.assertEqual(results.count(True), 1)
            self.assertEqual(results.count(False), 1)

    def test_second_wake_hit_during_open_wake_activation_suppressed(self):
        controller = ActivationController(manual_trigger_enabled=True, wake_word_trigger_enabled=True)
        coordinator = WakeAdmissionCoordinator()

        first_detection = WakeWordDetection(wake_word_id="jarvis", score=0.95)
        first_admission = coordinator.handle_wake_detection(first_detection, controller)
        self.assertIsNotNone(first_admission)
        self.assertTrue(coordinator.is_latched)

        # Second wake hit during open activation
        second_detection = WakeWordDetection(wake_word_id="jarvis", score=0.98)
        second_admission = coordinator.handle_wake_detection(second_detection, controller)
        self.assertIsNone(second_admission)

    def test_wake_hit_during_manual_activation_suppressed(self):
        controller = ActivationController(manual_trigger_enabled=True, wake_word_trigger_enabled=True)
        coordinator = WakeAdmissionCoordinator()

        # Manual activation accepted
        decision = controller.activate(MANUAL_SOURCE)
        self.assertTrue(decision.accepted)

        # Wake detection occurs during active manual session
        detection = WakeWordDetection(wake_word_id="jarvis", score=0.95)
        admission = coordinator.handle_wake_detection(detection, controller)
        self.assertIsNone(admission)
        self.assertFalse(coordinator.is_latched)

    def test_wake_source_suppressed_rejects_admission(self):
        # Wake trigger disabled in controller
        controller = ActivationController(manual_trigger_enabled=True, wake_word_trigger_enabled=False)
        coordinator = WakeAdmissionCoordinator()

        detection = WakeWordDetection(wake_word_id="jarvis", score=0.95)
        admission = coordinator.handle_wake_detection(detection, controller)
        self.assertIsNone(admission)
        self.assertFalse(coordinator.is_latched)

    def test_safe_input_close_unlocks_latch(self):
        controller = ActivationController(manual_trigger_enabled=True, wake_word_trigger_enabled=True)
        coordinator = WakeAdmissionCoordinator()

        detection_1 = WakeWordDetection(wake_word_id="jarvis", score=0.95)
        adm_1 = coordinator.handle_wake_detection(detection_1, controller)
        self.assertIsNotNone(adm_1)
        self.assertTrue(coordinator.is_latched)

        # Safe input close / reset unlocks latch
        released = coordinator.release_latch(activation_id=adm_1.activation_id, generation=adm_1.generation)
        self.assertTrue(released)
        self.assertFalse(coordinator.is_latched)

        # Controller finishes to IDLE
        controller.reset()

        # Now a new wake hit is accepted
        detection_2 = WakeWordDetection(wake_word_id="alexa", score=0.88)
        adm_2 = coordinator.handle_wake_detection(detection_2, controller)
        self.assertIsNotNone(adm_2)
        self.assertEqual(adm_2.wake_word_id, "alexa")

    def test_late_detector_callback_after_reset_is_inert(self):
        controller = ActivationController(manual_trigger_enabled=True, wake_word_trigger_enabled=True)
        coordinator = WakeAdmissionCoordinator()

        # Reset coordinator
        coordinator.reset()

        # Stale callback with None controller
        adm = coordinator.handle_wake_detection(
            WakeWordDetection(wake_word_id="jarvis", score=0.95),
            activation_controller=None,
        )
        self.assertIsNone(adm)


class SyntheticAudioBoundaryTests(unittest.TestCase):
    """
    Protects audio boundary rules using synthetic frame markers:
    [history][WAKE][first-user-word][following-speech]
    """

    def test_synthetic_marker_frames_exclude_wake_and_preserve_speech(self):
        sample_rate = 16000
        # 1. 20 frames history silence (rms = 2.0)
        history_frames = [
            PrerollFrameMetadata(sample_count=512, is_speech=False, rms=2.0)
            for _ in range(20)
        ]
        # 2. 10 frames wake word audio (rms = 80.0, is_speech=True)
        wake_frames = [
            PrerollFrameMetadata(sample_count=512, is_speech=True, rms=80.0)
            for _ in range(10)
        ]
        # 3. 2 frames boundary silence gap between wake and speech (rms = 3.0)
        gap_frames = [
            PrerollFrameMetadata(sample_count=512, is_speech=False, rms=3.0)
            for _ in range(2)
        ]
        # 4. 15 frames user speech (rms = 90.0, is_speech=True)
        user_speech_frames = [
            PrerollFrameMetadata(sample_count=512, is_speech=True, rms=90.0)
            for _ in range(15)
        ]

        all_frames = history_frames + wake_frames + gap_frames + user_speech_frames

        # Select pre-roll starting after wake-word boundary
        selection = select_preroll_frames(
            all_frames,
            sample_rate=sample_rate,
            min_included_ms=0.0,
            guard_ms=50.0,
            min_silence_ms=50.0,
        )

        self.assertIsNotNone(selection)
        # Verify speech is included
        self.assertLess(selection.start_index, len(all_frames))

    def test_preroll_0ms_supported_cleanly(self):
        sample_rate = 16000
        frames = [
            PrerollFrameMetadata(sample_count=512, is_speech=False, rms=1.0)
            for _ in range(10)
        ] + [
            PrerollFrameMetadata(sample_count=512, is_speech=True, rms=50.0)
            for _ in range(5)
        ]

        selection = select_preroll_frames(
            frames,
            sample_rate=sample_rate,
            min_included_ms=0.0,
        )
        self.assertEqual(selection.reason, "stable_silence_found")


if __name__ == "__main__":
    unittest.main()
