"""AP-SRV-070 W2-C2: reproducibility tests for tools/sync_wakeword_assets.py.

The canonical generator/sync authority must reproduce the actually shipped
dual-backend (ONNX + TFLite) wake-word bundle from an upstream ``--source``
directory - no silent single-backend degrade, no manifest fields that depend
on the previously generated target, and no legacy v1 fields. These tests
exercise that contract against small, hermetic fake source trees; a separate
integration test at the bottom additionally proves ``--check`` against the
real committed bundle when the real upstream source is reachable.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL_PATH = REPO_ROOT / "tools" / "sync_wakeword_assets.py"

_spec = importlib.util.spec_from_file_location("sync_wakeword_assets", TOOL_PATH)
sync = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync)


def _write(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _build_source(
    tmp_path: Path,
    *,
    onnx_models=None,
    tflite_models=None,
    extra_pipeline_keys=None,
    write_vad=True,
) -> Path:
    """A minimal, hermetic fake upstream ``all_models`` directory."""
    source = tmp_path / "all_models"
    source.mkdir(parents=True, exist_ok=True)

    if onnx_models is None:
        onnx_models = {"alexa": "alexa.onnx", "Hey_Jarvis": "jarvis_v2.onnx"}
    if tflite_models is None:
        tflite_models = {"alexa": "alexa.tflite", "Hey_Jarvis": "jarvis_v2.tflite"}

    pipeline_models = {
        "embedding_model_onnx": "embedding_model.onnx",
        "melspectrogram_onnx": "melspectrogram.onnx",
        "embedding_model_tflite": "embedding_model.tflite",
        "melspectrogram_tflite": "melspectrogram.tflite",
    }
    if write_vad:
        pipeline_models["silero_vad_onnx"] = "silero_vad.onnx"
    if extra_pipeline_keys:
        pipeline_models.update(extra_pipeline_keys)

    manifest = {
        "openwakeword_models": {
            "path": ".",
            "default_model": "alexa",
            "pipeline_models": pipeline_models,
            "onnx_models": onnx_models,
            "tflite_models": tflite_models,
        }
    }
    (source / "models.json").write_text(json.dumps(manifest), encoding="utf-8")

    for filename in set(onnx_models.values()) | set(tflite_models.values()):
        _write(source / filename, filename.encode("utf-8") + b"-bytes")
    _write(source / "embedding_model.onnx", b"embedding-onnx-bytes")
    _write(source / "melspectrogram.onnx", b"melspectrogram-onnx-bytes")
    _write(source / "embedding_model.tflite", b"embedding-tflite-bytes")
    _write(source / "melspectrogram.tflite", b"melspectrogram-tflite-bytes")
    if write_vad:
        _write(source / "silero_vad.onnx", b"silero-vad-bytes")

    return source


class BuildManifestDualBackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_every_wake_word_gets_both_backends(self):
        source = _build_source(self.tmp)
        manifest, _files = sync.build_manifest(source)

        by_id = {entry["id"]: entry for entry in manifest["wakeWords"]}
        self.assertEqual(set(by_id), {"alexa", "hey_jarvis"})
        for entry in by_id.values():
            self.assertEqual(set(entry["artifacts"]), {"onnx", "tflite"})
            for backend_data in entry["artifacts"].values():
                self.assertIn("sha256", backend_data)
                self.assertIn("bytes", backend_data)
                self.assertIn("file", backend_data)

    def test_pipeline_has_both_backends_and_roles(self):
        source = _build_source(self.tmp)
        manifest, _files = sync.build_manifest(source)

        self.assertEqual(set(manifest["pipeline"]), {"onnx", "tflite"})
        for framework_data in manifest["pipeline"].values():
            self.assertEqual(set(framework_data), {"melspectrogram", "embedding"})

    def test_missing_tflite_pair_is_a_deterministic_error_not_a_degrade(self):
        source = _build_source(
            self.tmp,
            onnx_models={"alexa": "alexa.onnx", "Hey_Jarvis": "jarvis_v2.onnx"},
            tflite_models={"alexa": "alexa.tflite"},  # hey_jarvis tflite missing
        )
        with self.assertRaises(SystemExit) as ctx:
            sync.build_manifest(source)
        self.assertIn("hey_jarvis", str(ctx.exception))
        self.assertIn("tflite", str(ctx.exception))

    def test_missing_onnx_pair_is_a_deterministic_error_not_a_degrade(self):
        source = _build_source(
            self.tmp,
            onnx_models={"alexa": "alexa.onnx"},  # hey_jarvis onnx missing
            tflite_models={"alexa": "alexa.tflite", "Hey_Jarvis": "jarvis_v2.tflite"},
        )
        with self.assertRaises(SystemExit) as ctx:
            sync.build_manifest(source)
        self.assertIn("hey_jarvis", str(ctx.exception))
        self.assertIn("onnx", str(ctx.exception))

    def test_catalog_revision_is_the_generator_constant(self):
        source = _build_source(self.tmp)
        manifest, _files = sync.build_manifest(source)
        self.assertEqual(manifest["catalogRevision"], sync.CATALOG_REVISION)

    def test_catalog_revision_does_not_read_the_previously_generated_target(self):
        # build_manifest never touches TARGET at all - point it at a target
        # holding a manifest with a *different* catalogRevision, and confirm
        # the freshly generated manifest is unaffected.
        stale_target = self.tmp / "stale_target"
        stale_target.mkdir()
        (stale_target / "models.json").write_text(
            json.dumps({"catalogRevision": 999}), encoding="utf-8"
        )
        source = _build_source(self.tmp)
        with mock.patch.object(sync, "TARGET", stale_target):
            manifest, _files = sync.build_manifest(source)
        self.assertEqual(manifest["catalogRevision"], sync.CATALOG_REVISION)
        self.assertNotEqual(manifest["catalogRevision"], 999)

    def test_no_legacy_v1_fields(self):
        # Structural check on the parsed manifest, not the rendered text: the
        # human-readable ``description`` legitimately *mentions*
        # 'openwakeword_models' prose (it explains that the v1 legacy mirror
        # was removed), which must not be confused with the legacy JSON key
        # itself reappearing anywhere in the manifest's own structure.
        source = _build_source(self.tmp)
        manifest, _files = sync.build_manifest(source)
        self.assertNotIn("default_model", manifest)
        self.assertNotIn("openwakeword_models", manifest)
        for entry in manifest["wakeWords"]:
            self.assertNotIn("default_model", entry)
            self.assertNotIn("openwakeword_models", entry)

    def test_wake_words_are_ordered_by_canonical_id(self):
        source = _build_source(
            self.tmp,
            onnx_models={"Hey_Jarvis": "jarvis_v2.onnx", "alexa": "alexa.onnx"},
            tflite_models={"Hey_Jarvis": "jarvis_v2.tflite", "alexa": "alexa.tflite"},
        )
        manifest, _files = sync.build_manifest(source)
        self.assertEqual([entry["id"] for entry in manifest["wakeWords"]], ["alexa", "hey_jarvis"])

    def test_duplicate_canonical_id_after_normalization_is_an_error(self):
        source = _build_source(
            self.tmp,
            onnx_models={"Hey Jarvis": "jarvis_v2.onnx", "hey_jarvis": "jarvis_v1.onnx"},
            tflite_models={"Hey Jarvis": "jarvis_v2.tflite", "hey_jarvis": "jarvis_v1.tflite"},
        )
        with self.assertRaises(SystemExit) as ctx:
            sync.build_manifest(source)
        self.assertIn("hey_jarvis", str(ctx.exception))


class AuxiliaryVadAssetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_vad_asset_is_tracked_for_sync_and_check(self):
        source = _build_source(self.tmp, write_vad=True)
        manifest, files = sync.build_manifest(source)
        self.assertIn("silero_vad.onnx", files)
        self.assertEqual(files["silero_vad.onnx"], source / "silero_vad.onnx")

    def test_vad_asset_does_not_introduce_new_manifest_semantics(self):
        # Managed via the sync/check file list only - not a new JSON field,
        # per the frozen SRV-060 manifest contract.
        source = _build_source(self.tmp, write_vad=True)
        manifest, _files = sync.build_manifest(source)
        rendered = sync.render_manifest(manifest)
        self.assertNotIn("vad", rendered.lower())

    def test_missing_vad_asset_upstream_is_a_deterministic_error(self):
        source = _build_source(self.tmp, write_vad=False)
        with self.assertRaises(SystemExit) as ctx:
            sync.build_manifest(source)
        self.assertIn("silero_vad", str(ctx.exception))


class RenderManifestFormattingTests(unittest.TestCase):
    def test_scalar_arrays_render_inline(self):
        rendered = sync.render_manifest({"aliases": ["alfred"], "empty": []})
        self.assertIn('"aliases": ["alfred"]', rendered)
        self.assertIn('"empty": []', rendered)

    def test_object_arrays_still_expand(self):
        rendered = sync.render_manifest({"wakeWords": [{"id": "alexa"}]})
        self.assertIn("[\n", rendered)
        self.assertIn('"id": "alexa"', rendered)


class CheckModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.target = self.tmp / "target"
        self.target.mkdir()

    def _run_main(self, source: Path, *, check: bool):
        argv = ["--source", str(source)]
        if check:
            argv.append("--check")
        with mock.patch.object(sync, "TARGET", self.target):
            return sync.main(argv)

    def test_check_fails_against_an_empty_target(self):
        source = _build_source(self.tmp)
        exit_code = self._run_main(source, check=True)
        self.assertEqual(exit_code, 1)

    def test_check_writes_nothing(self):
        source = _build_source(self.tmp)
        self._run_main(source, check=True)
        self.assertEqual(list(self.target.iterdir()), [])

    def test_sync_then_check_round_trips_to_exit_zero(self):
        source = _build_source(self.tmp)
        sync_exit = self._run_main(source, check=False)
        self.assertEqual(sync_exit, 0)

        check_exit = self._run_main(source, check=True)
        self.assertEqual(check_exit, 0)

    def test_check_detects_a_changed_bundled_artifact(self):
        source = _build_source(self.tmp)
        self._run_main(source, check=False)

        (self.target / "alexa.onnx").write_bytes(b"tampered")

        with mock.patch.object(sync, "TARGET", self.target):
            exit_code = sync.main(["--source", str(source), "--check"])
        self.assertEqual(exit_code, 1)

    def test_check_detects_a_missing_bundled_artifact(self):
        source = _build_source(self.tmp)
        self._run_main(source, check=False)

        (self.target / "silero_vad.onnx").unlink()

        with mock.patch.object(sync, "TARGET", self.target):
            exit_code = sync.main(["--source", str(source), "--check"])
        self.assertEqual(exit_code, 1)


class RealCommittedBundleIntegrationTest(unittest.TestCase):
    """Proves the hard gate against the real repo bundle when the real
    upstream source is reachable in this environment. Skipped, not faked,
    when the ``--source`` authority is unavailable - a fake substitute would
    not prove anything about the real contract."""

    SOURCE = Path("S:/MODELS/openwakeword/resources/models/all_models")

    @unittest.skipUnless(SOURCE.is_dir(), "real upstream --source not reachable in this environment")
    def test_check_passes_against_the_committed_bundle(self):
        exit_code = sync.main(["--source", str(self.SOURCE), "--check"])
        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
