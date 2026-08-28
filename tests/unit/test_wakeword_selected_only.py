"""AP-SRV-060: selected-only initialisation and the structured candidate path.

These tests assert the *actual loader arguments*: a session must hand
OpenWakeWord exactly the classifiers it was admitted for, plus the shared
pipeline models the catalog owns - nothing else, in particular not the rest of
the bundled build.
"""

import tempfile
import types
import unittest
from pathlib import Path

from VoiceSTT.core import wakeword as wakeword_module
from VoiceSTT.core.wakeword_catalog import WakeWordCatalogAuthority

from .wake_catalog_support import build_bundle


ENTRIES = (
    ("hey_jarvis", "Hey Jarvis", ("jarvis",), "jarvis_v2.onnx"),
    ("alexa", "Alexa", (), "alexa.onnx"),
    ("hey_mycroft", "Hey Mycroft", (), "hey_mycroft.onnx"),
    ("hey_rona", "Hey Rona", ("rona",), "hey_rona.onnx"),
)


class FakeOpenWakeWordModel:
    """Records exactly what the production code asked the backend to load."""

    last_kwargs = None

    def __init__(self, **kwargs):
        FakeOpenWakeWordModel.last_kwargs = dict(kwargs)
        self.models = {
            Path(path).stem: object()
            for path in kwargs.get("wakeword_models", ())
        }
        self.model_inputs = {key: 16 for key in self.models}
        self.prediction_buffer = {key: [0.0] for key in self.models}

    def predict(self, _pcm):
        return {key: values[-1] for key, values in self.prediction_buffer.items()}


def fake_loader():
    return types.SimpleNamespace(), FakeOpenWakeWordModel


class Recorder:
    """The minimal recorder surface ``setup_wakeword_detection`` touches."""

    def __init__(self):
        self.use_wake_words = True
        self.debug_mode = False
        self.sample_rate = 16000
        self.wakeword_backend = ""
        self.wake_words_list = []
        self.wake_words_sensitivity = 0.5
        self.wake_words_sensitivities = []
        self.owwModel = None
        self.oww_n_models = 0


class SelectedOnlyLoaderTests(unittest.TestCase):
    def setUp(self):
        FakeOpenWakeWordModel.last_kwargs = None
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.root = build_bundle(Path(self._tempdir.name) / "bundle", ENTRIES)
        self.authority = WakeWordCatalogAuthority(
            asset_root=self.root, artifact_prober=lambda path: None
        )

    def _setup(self, requested):
        selection, errors = self.authority.resolve_human_selection(requested)
        self.assertEqual(errors, ())
        recorder = Recorder()
        wakeword_module.setup_wakeword_detection(
            recorder,
            "openwakeword",
            ",".join(selection.wake_word_ids),
            0.5,
            None,
            "onnx",
            load_openwakeword_modules=fake_loader,
            wake_word_selection=selection,
        )
        return recorder, selection

    def test_only_the_selected_classifiers_reach_the_loader(self):
        recorder, _selection = self._setup(["hey_jarvis"])
        kwargs = FakeOpenWakeWordModel.last_kwargs
        self.assertEqual(
            [Path(path).name for path in kwargs["wakeword_models"]],
            ["jarvis_v2.onnx"],
        )
        self.assertEqual(recorder.oww_n_models, 1)
        # The rest of the bundled build is not loaded at all.
        self.assertEqual(len(recorder.owwModel.models), 1)

    def test_three_selected_classifiers_load_exactly_three_models(self):
        recorder, _selection = self._setup(["hey_jarvis", "alexa", "hey_rona"])
        kwargs = FakeOpenWakeWordModel.last_kwargs
        self.assertEqual(
            sorted(Path(path).name for path in kwargs["wakeword_models"]),
            ["alexa.onnx", "hey_rona.onnx", "jarvis_v2.onnx"],
        )
        self.assertEqual(recorder.oww_n_models, 3)

    def test_the_shared_pipeline_models_are_passed_once_per_instance(self):
        self._setup(["hey_jarvis", "alexa"])
        kwargs = FakeOpenWakeWordModel.last_kwargs
        self.assertEqual(
            Path(kwargs["melspec_model_path"]).name, "melspectrogram.onnx"
        )
        self.assertEqual(
            Path(kwargs["embedding_model_path"]).name, "embedding_model.onnx"
        )
        self.assertEqual(kwargs["inference_framework"], "onnx")

    def test_an_alias_selection_loads_the_canonical_artifact(self):
        self._setup(["jarvis"])
        kwargs = FakeOpenWakeWordModel.last_kwargs
        self.assertEqual(
            [Path(path).name for path in kwargs["wakeword_models"]],
            ["jarvis_v2.onnx"],
        )

    def test_the_selection_binds_canonical_ids_and_measured_frames(self):
        recorder, _selection = self._setup(["hey_jarvis", "alexa"])
        self.assertEqual(
            recorder.wake_word_model_key_to_id,
            {"jarvis_v2": "hey_jarvis", "alexa": "alexa"},
        )
        self.assertEqual(
            set(recorder.wake_word_input_frames), {"jarvis_v2", "alexa"}
        )


class CandidateCollectionTests(SelectedOnlyLoaderTests):
    def test_candidates_carry_the_canonical_id_not_the_file_stem(self):
        recorder, _selection = self._setup(["hey_jarvis"])
        recorder.owwModel.prediction_buffer["jarvis_v2"] = [0.11, 0.93]
        candidates = wakeword_module.collect_wake_candidates(
            recorder,
            b"\x00\x00" * 512,
            sample_position=32000,
            frame_index=7,
            detector_generation=3,
        )
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.canonical_wake_word_id, "hey_jarvis")
        self.assertEqual(candidate.model_key, "jarvis_v2")
        self.assertEqual(candidate.raw_score, 0.93)
        self.assertEqual(candidate.frame_index, 7)
        self.assertEqual(candidate.sample_position, 32000 + 512)
        self.assertEqual(candidate.detector_generation, 3)

    def test_an_unmapped_model_key_never_becomes_a_candidate(self):
        recorder, _selection = self._setup(["hey_jarvis"])
        recorder.owwModel.prediction_buffer["stray_model"] = [0.99]
        candidates = wakeword_module.collect_wake_candidates(
            recorder, b"\x00\x00" * 512
        )
        self.assertEqual(
            [item.canonical_wake_word_id for item in candidates], ["hey_jarvis"]
        )

    def test_raw_collection_applies_no_threshold(self):
        recorder, _selection = self._setup(["hey_jarvis", "alexa"])
        recorder.owwModel.prediction_buffer["jarvis_v2"] = [0.01]
        recorder.owwModel.prediction_buffer["alexa"] = [0.02]
        candidates = wakeword_module.collect_wake_candidates(
            recorder, b"\x00\x00" * 512
        )
        self.assertEqual(len(candidates), 2)


class SessionConfigTests(unittest.TestCase):
    """The v2 admission bypasses the v1 name resolution and its fallbacks."""

    def setUp(self):
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        root = build_bundle(Path(self._tempdir.name) / "bundle", ENTRIES)
        self.authority = WakeWordCatalogAuthority(
            asset_root=root, artifact_prober=lambda path: None
        )

    def test_an_admitted_selection_configures_exactly_its_artifacts(self):
        from api_fastapi_server.server import (
            ServerSettings,
            SessionWakeWordRequest,
            resolve_session_wake_word_config,
        )

        selection, errors = self.authority.admit_selection(
            ["hey_jarvis", "alexa"]
        )
        self.assertEqual(errors, ())
        settings, config = resolve_session_wake_word_config(
            ServerSettings(),
            SessionWakeWordRequest(enabled=True, selection=selection),
            registry=None,
        )
        self.assertEqual(settings.wakeword_backend, "openwakeword")
        self.assertEqual(settings.wake_words, "hey_jarvis,alexa")
        self.assertEqual(
            [Path(path).name
             for path in settings.openwakeword_model_paths.split(",")],
            ["jarvis_v2.onnx", "alexa.onnx"],
        )
        self.assertEqual(config.effective_wake_words, ("hey_jarvis", "alexa"))
        self.assertEqual(config.source, "session")
        # Atomic admission: there is no fallback profile in this path.
        self.assertEqual(config.fallbacks, ())
        self.assertIs(config.wake_word_selection, selection)

    def test_the_public_projection_never_leaks_the_selection_object(self):
        from api_fastapi_server.server import (
            ServerSettings,
            SessionWakeWordRequest,
            resolve_session_wake_word_config,
        )

        selection, _errors = self.authority.admit_selection(["alexa"])
        _settings, config = resolve_session_wake_word_config(
            ServerSettings(),
            SessionWakeWordRequest(enabled=True, selection=selection),
            registry=None,
        )
        payload = config.public_dict()
        self.assertNotIn("wake_word_selection", payload)
        self.assertNotIn(".onnx", str(payload))


if __name__ == "__main__":
    unittest.main()
