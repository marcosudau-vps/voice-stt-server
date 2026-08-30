"""AP-SRV-070 W3-08 - bundled wake-word asset integrity, from the source tree.

Complements ``tests/unit/test_sync_wakeword_assets.py`` (which proves the
*generator* reproduces the shipped bundle from the external upstream source)
and the installed-artifact smoke (which proves the same facts from a real
``pip install``). These tests assert the committed bundle's own internal
consistency directly, with no dependency on the external ``--source``
authority or on a real package installation.
"""

import ast
import hashlib
import json
import pathlib
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
ASSET_DIR = REPO_ROOT / "VoiceSTT" / "assets" / "wakeword_models"


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ManifestIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(
            (ASSET_DIR / "models.json").read_text(encoding="utf-8")
        )

    def test_manifest_version_and_catalog_revision(self):
        self.assertEqual(self.manifest["manifestVersion"], 2)
        self.assertGreaterEqual(self.manifest["catalogRevision"], 1)

    def test_25_dual_backend_classifier_pairs_present_with_matching_hashes(self):
        self.assertEqual(len(self.manifest["wakeWords"]), 25)
        for entry in self.manifest["wakeWords"]:
            for backend in ("onnx", "tflite"):
                artifact = entry["artifacts"][backend]
                path = ASSET_DIR / artifact["file"]
                with self.subTest(id=entry["id"], backend=backend):
                    self.assertTrue(path.is_file(), f"missing {path}")
                    self.assertEqual(path.stat().st_size, artifact["bytes"])
                    self.assertEqual(_sha256(path), artifact["sha256"])

    def test_4_pipeline_assets_present_with_matching_hashes(self):
        checked = 0
        for framework, roles in self.manifest["pipeline"].items():
            for role, spec in roles.items():
                path = ASSET_DIR / spec["file"]
                with self.subTest(framework=framework, role=role):
                    self.assertTrue(path.is_file(), f"missing {path}")
                    self.assertEqual(path.stat().st_size, spec["bytes"])
                    self.assertEqual(_sha256(path), spec["sha256"])
                checked += 1
        self.assertEqual(checked, 4)

    def test_vad_auxiliary_asset_present(self):
        from wakeword_package_resources import AUXILIARY_ASSET_FILENAMES

        self.assertEqual(AUXILIARY_ASSET_FILENAMES, ("silero_vad.onnx",))
        path = ASSET_DIR / "silero_vad.onnx"
        self.assertTrue(path.is_file(), f"missing {path}")
        self.assertGreater(path.stat().st_size, 0)


class NoRuntimeDownloadTests(unittest.TestCase):
    """The catalog module must never be able to reach the network."""

    NETWORK_MODULES = {
        "requests", "httpx", "urllib.request", "aiohttp", "socket", "http.client",
    }

    def _imported_top_level_modules(self, path: pathlib.Path):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        return imported

    def test_wakeword_catalog_module_imports_no_network_client(self):
        path = REPO_ROOT / "VoiceSTT" / "core" / "wakeword_catalog.py"
        imported = self._imported_top_level_modules(path)
        overlap = imported & self.NETWORK_MODULES
        self.assertFalse(overlap, f"unexpected network-capable import(s): {overlap}")

    def test_default_asset_root_never_downloads(self):
        # default_asset_root() only resolves a local path (importlib.resources
        # or an env override); it must succeed with networking irrelevant.
        from VoiceSTT.core import wakeword_catalog

        root = wakeword_catalog.default_asset_root()
        self.assertTrue(pathlib.Path(root).is_dir())


if __name__ == "__main__":
    unittest.main()
