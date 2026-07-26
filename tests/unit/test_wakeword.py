import unittest
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch


try:
    from VoiceSTT.core import wakeword
except ModuleNotFoundError as exc:
    wakeword = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


class WakeWordTests(unittest.TestCase):
    def setUp(self):
        if wakeword is None:
            self.skipTest(f"wakeword import failed: {IMPORT_ERROR}")

    def test_bare_wake_words_default_to_porcupine(self):
        self.assertEqual(
            wakeword._normalize_wakeword_backend("", "jarvis"),
            "pvporcupine",
        )

    def test_no_wake_words_keep_backend_empty(self):
        self.assertEqual(
            wakeword._normalize_wakeword_backend("", ""),
            "",
        )

    def test_openwakeword_backend_normalizes_hyphen(self):
        self.assertEqual(
            wakeword._normalize_wakeword_backend("open-wakeword", ""),
            "open_wakeword",
        )

    def test_porcupine_missing_dependency_mentions_extra(self):
        with patch(
            "VoiceSTT.core.wakeword.import_module",
            side_effect=ModuleNotFoundError("No module named 'pvporcupine'"),
        ):
            with self.assertRaisesRegex(ModuleNotFoundError, r"VoiceSTT\[porcupine\]"):
                wakeword._load_porcupine_module()

    def test_openwakeword_missing_dependency_mentions_extra(self):
        with patch(
            "VoiceSTT.core.wakeword.import_module",
            side_effect=ModuleNotFoundError("No module named 'openwakeword'"),
        ):
            with self.assertRaisesRegex(ModuleNotFoundError, r"VoiceSTT\[openwakeword\]"):
                wakeword._load_openwakeword_modules()

    def test_openwakeword_offline_resolver_requires_local_assets(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            with patch.dict(os.environ, {wakeword.OPENWAKEWORD_MODEL_ROOT_ENV: temp_dir}):
                with self.assertRaisesRegex(FileNotFoundError, "offline mode"):
                    wakeword._resolve_openwakeword_paths(None, "hey_jarvis")

    def test_openwakeword_resolver_returns_classifier_and_feature_paths(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            for name in ("hey_jarvis_v0.1.onnx", "melspectrogram.onnx", "embedding_model.onnx"):
                (root / name).write_bytes(b"model")
            with patch.dict(os.environ, {wakeword.OPENWAKEWORD_MODEL_ROOT_ENV: temp_dir}):
                models, features = wakeword._resolve_openwakeword_paths(None, "hey_jarvis")
        self.assertEqual([Path(value).name for value in models], ["hey_jarvis_v0.1.onnx"])
        self.assertEqual(Path(features["melspec_model_path"]).name, "melspectrogram.onnx")
        self.assertEqual(Path(features["embedding_model_path"]).name, "embedding_model.onnx")

    def test_openwakeword_resolver_uses_models_json_pipeline_mapping(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            models = root / "all_models"
            models.mkdir()
            for filename in (
                "jarvis_v2.onnx",
                "mel.custom.onnx",
                "embedding.custom.onnx",
            ):
                (models / filename).write_bytes(b"model")
            (root / "models.json").write_text(json.dumps({
                "openwakeword_models": {
                    "path": str(models),
                    "default_model": "hey_jarvis",
                    "pipeline_models": {
                        "melspectrogram_onnx": "mel.custom.onnx",
                        "embedding_model_onnx": "embedding.custom.onnx",
                    },
                    "onnx_models": {
                        "hey_jarvis": "jarvis_v2.onnx",
                    },
                    "tflite_models": {},
                }
            }), encoding="utf-8")
            with patch.dict(
                os.environ,
                {wakeword.OPENWAKEWORD_MODEL_ROOT_ENV: str(root)},
            ):
                classifiers, features = wakeword._resolve_openwakeword_paths(
                    None,
                    "hey_jarvis",
                    "onnx",
                )

        self.assertEqual(Path(classifiers[0]).name, "jarvis_v2.onnx")
        self.assertEqual(Path(features["melspec_model_path"]).name, "mel.custom.onnx")
        self.assertEqual(
            Path(features["embedding_model_path"]).name,
            "embedding.custom.onnx",
        )

    def test_openwakeword_resolver_accepts_models_json_as_configured_path(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            models = root / "models"
            models.mkdir()
            for filename in (
                "alexa.onnx",
                "melspectrogram.onnx",
                "embedding_model.onnx",
            ):
                (models / filename).write_bytes(b"model")
            manifest = root / "models.json"
            manifest.write_text(json.dumps({
                "openwakeword_models": {
                    "path": str(models),
                    "default_model": "alexa",
                    "pipeline_models": {
                        "melspectrogram_onnx": "melspectrogram.onnx",
                        "embedding_model_onnx": "embedding_model.onnx",
                    },
                    "onnx_models": {"alexa": "alexa.onnx"},
                    "tflite_models": {},
                }
            }), encoding="utf-8")
            classifiers, features = wakeword._resolve_openwakeword_paths(
                str(manifest),
                "",
                "onnx",
            )

        self.assertEqual(Path(classifiers[0]).name, "alexa.onnx")
        self.assertEqual(
            Path(features["melspec_model_path"]).name,
            "melspectrogram.onnx",
        )

    def test_openwakeword_setup_never_calls_download_models(self):
        class FakeUtils:
            def download_models(self):
                raise AssertionError("runtime download must never be called")

        class FakeOpenWakeWord:
            utils = FakeUtils()

        class FakeModel:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                self.models = {"wake": object()}

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            classifier = root / "wake.onnx"
            for path in (classifier, root / "melspectrogram.onnx", root / "embedding_model.onnx"):
                path.write_bytes(b"model")
            recorder = type("Recorder", (), {"use_wake_words": True})()
            wakeword.setup_wakeword_detection(
                recorder,
                "openwakeword",
                "wake",
                0.5,
                str(classifier),
                "onnx",
                load_openwakeword_modules=lambda: (FakeOpenWakeWord(), FakeModel),
            )
        self.assertEqual(recorder.owwModel.kwargs["device"], "cpu")


if __name__ == "__main__":
    unittest.main()
