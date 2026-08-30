"""AP-SRV-070 - the wake-word package-data authority is not a glob.

``setup.py`` used to select ``VoiceSTT/assets/wakeword_models`` package data
with broad ``*.onnx``/``*.tflite`` globs. The source tree also carries
historical, unmanifested wake-word variants (``Jarvis.onnx``, ``jarvis_v1.onnx``,
``hey_jarvis_v0.1.onnx`` and their ``.tflite`` pendants - see the AP-SRV-070
W2-C2 root finding) that a glob would sweep into the public wheel/sdist right
along with the real catalog. These tests pin down that
``wakeword_package_resources.py`` selects exactly the manifested files and
nothing else.
"""

import json
import pathlib
import unittest

from wakeword_package_resources import (
    AUXILIARY_ASSET_FILENAMES,
    bundled_package_data_files,
    manifested_filenames,
)


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
ASSET_DIR = REPO_ROOT / "VoiceSTT" / "assets" / "wakeword_models"

#: Physically present in the source tree but deliberately not manifested
#: (AP-SRV-070 W2-C2). Packaging must never include these just because they
#: share an extension with the real bundle.
KNOWN_UNMANIFESTED_VARIANTS = (
    "Jarvis.onnx", "Jarvis.tflite",
    "jarvis_v1.onnx", "jarvis_v1.tflite",
    "hey_jarvis_v0.1.onnx", "hey_jarvis_v0.1.tflite",
)


class ManifestedFilenamesTests(unittest.TestCase):
    def test_matches_the_real_committed_manifest(self):
        manifest = json.loads(
            (ASSET_DIR / "models.json").read_text(encoding="utf-8")
        )
        expected = set()
        for entry in manifest["wakeWords"]:
            for artifact in entry["artifacts"].values():
                expected.add(artifact["file"])
        for framework in manifest["pipeline"].values():
            for role in framework.values():
                expected.add(role["file"])

        self.assertEqual(set(manifested_filenames(ASSET_DIR / "models.json")), expected)
        # 25 wake words * 2 backends + 2 pipeline roles * 2 backends.
        self.assertEqual(len(expected), 25 * 2 + 2 * 2)

    def test_ignores_files_that_are_not_referenced_by_the_manifest(self, ):
        for name in KNOWN_UNMANIFESTED_VARIANTS:
            with self.subTest(name=name):
                self.assertNotIn(
                    name, manifested_filenames(ASSET_DIR / "models.json")
                )


class BundledPackageDataFilesTests(unittest.TestCase):
    def test_returns_the_exact_deterministic_set(self):
        files = bundled_package_data_files(ASSET_DIR)
        manifest_files = manifested_filenames(ASSET_DIR / "models.json")
        expected = set(manifest_files) | set(AUXILIARY_ASSET_FILENAMES) | {"models.json"}
        self.assertEqual(set(files), expected)
        self.assertEqual(len(files), len(expected), "no duplicates")
        self.assertEqual(files, sorted(files), "deterministic order")

    def test_includes_all_25_dual_backend_classifier_pairs(self):
        files = set(bundled_package_data_files(ASSET_DIR))
        manifest = json.loads((ASSET_DIR / "models.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["wakeWords"]), 25)
        for entry in manifest["wakeWords"]:
            self.assertIn(entry["artifacts"]["onnx"]["file"], files)
            self.assertIn(entry["artifacts"]["tflite"]["file"], files)

    def test_includes_both_pipeline_backends(self):
        files = set(bundled_package_data_files(ASSET_DIR))
        for name in (
            "melspectrogram.onnx", "embedding_model.onnx",
            "melspectrogram.tflite", "embedding_model.tflite",
        ):
            self.assertIn(name, files)

    def test_includes_the_vad_auxiliary_asset(self):
        files = set(bundled_package_data_files(ASSET_DIR))
        self.assertIn("silero_vad.onnx", files)

    def test_excludes_every_known_unmanifested_historical_variant(self):
        files = set(bundled_package_data_files(ASSET_DIR))
        for name in KNOWN_UNMANIFESTED_VARIANTS:
            with self.subTest(name=name):
                self.assertNotIn(name, files)

    def test_raises_when_a_manifested_file_is_missing_on_disk(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            manifest = {
                "wakeWords": [{
                    "id": "ghost",
                    "artifacts": {
                        "onnx": {"file": "ghost.onnx"},
                        "tflite": {"file": "ghost.tflite"},
                    },
                }],
                "pipeline": {},
            }
            (tmp_path / "models.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            with self.assertRaises(FileNotFoundError):
                bundled_package_data_files(tmp_path)


if __name__ == "__main__":
    unittest.main()
