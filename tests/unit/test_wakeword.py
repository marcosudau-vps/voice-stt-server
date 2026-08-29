import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch


try:
    from VoiceSTT.core import wakeword
    from VoiceSTT.core import wakeword_catalog as wakeword_catalog_module
    from .wake_catalog_support import build_bundle
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
            with patch.dict(
                os.environ,
                {wakeword_catalog_module.WAKEWORD_ASSET_ROOT_ENV: temp_dir},
            ):
                with self.assertRaisesRegex(FileNotFoundError, "offline mode"):
                    wakeword._resolve_openwakeword_paths(None, "hey_jarvis")

    def test_openwakeword_resolver_returns_classifier_and_feature_paths(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = build_bundle(
                Path(temp_dir),
                [("hey_jarvis", "Hey Jarvis", ("jarvis",), "hey_jarvis.onnx")],
            )
            with patch.dict(
                os.environ,
                {wakeword_catalog_module.WAKEWORD_ASSET_ROOT_ENV: str(root)},
            ):
                models, features = wakeword._resolve_openwakeword_paths(None, "hey_jarvis")
        self.assertEqual([Path(value).name for value in models], ["hey_jarvis.onnx"])
        self.assertEqual(Path(features["melspec_model_path"]).name, "melspectrogram.onnx")
        self.assertEqual(Path(features["embedding_model_path"]).name, "embedding_model.onnx")

    def test_openwakeword_resolver_resolves_alias_and_rejects_unknown_id(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = build_bundle(
                Path(temp_dir),
                [("hey_jarvis", "Hey Jarvis", ("jarvis",), "jarvis_v2.onnx")],
            )
            with patch.dict(
                os.environ,
                {wakeword_catalog_module.WAKEWORD_ASSET_ROOT_ENV: str(root)},
            ):
                classifiers, features = wakeword._resolve_openwakeword_paths(
                    None,
                    "JARVIS",
                    "onnx",
                )
                with self.assertRaisesRegex(FileNotFoundError, "offline mode"):
                    wakeword._resolve_openwakeword_paths(None, "not_a_real_wake_word")

        self.assertEqual(Path(classifiers[0]).name, "jarvis_v2.onnx")
        self.assertEqual(Path(features["melspec_model_path"]).name, "melspectrogram.onnx")
        self.assertEqual(
            Path(features["embedding_model_path"]).name,
            "embedding_model.onnx",
        )

    def test_openwakeword_resolver_accepts_explicit_classifier_file(self):
        """AP-SRV-070: an explicit classifier path bypasses catalog lookup
        for the classifier itself, but the shared pipeline models still come
        from the one canonical manifest (never a directory-sibling scan)."""
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = build_bundle(
                Path(temp_dir),
                [("alexa", "Alexa", (), "alexa.onnx")],
            )
            explicit_classifier = root / "custom_wake.onnx"
            explicit_classifier.write_bytes(b"model")
            with patch.dict(
                os.environ,
                {wakeword_catalog_module.WAKEWORD_ASSET_ROOT_ENV: str(root)},
            ):
                classifiers, features = wakeword._resolve_openwakeword_paths(
                    str(explicit_classifier),
                    "",
                    "onnx",
                )

        self.assertEqual(Path(classifiers[0]).name, "custom_wake.onnx")
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
