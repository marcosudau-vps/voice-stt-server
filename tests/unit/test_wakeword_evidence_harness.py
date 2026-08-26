"""
Reproducible evidence and resource measurement harness for AP-SRV-060.

Measures:
- Selected-only model initialization elapsed time (monotonic/perf_counter in ms)
- Process memory footprint delta (before RSS, after RSS, delta RSS, peak RSS) using process_memory_snapshot()
- Loaded canonical model IDs
- Profiles: 1 model, 3 models, expected max count (5 models)
- Artifact versions and inference framework
"""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Dict, List, Optional
import unittest
from unittest.mock import patch

from VoiceSTT.core.openwakeword_catalog import (
    OPENWAKEWORD_MODEL_ROOT_ENV,
    OpenWakeWordCatalog,
)
from VoiceSTT.core.wakeword import (
    _resolve_openwakeword_paths,
    setup_wakeword_detection,
)
from VoiceSTT_server.operations import process_memory_snapshot


@dataclass(frozen=True)
class BenchmarkResult:
    profile: str
    model_count: int
    requested_ids: List[str]
    loaded_ids: List[str]
    initialization_time_ms: float
    memory_before: Dict[str, Any]
    memory_after: Dict[str, Any]
    delta_rss_bytes: int
    framework: str
    artifact_versions: Dict[str, Optional[str]]
    environment_evidence_status: str


class WakeWordEvidenceHarness:
    """Measures wake-word startup time, process memory footprint, and loaded models."""

    def __init__(self, model_root: Path):
        self.model_root = model_root

    def measure_profile(
        self,
        profile_name: str,
        requested_ids: List[str],
        framework: str = "onnx",
        fake_model_factory=None,
    ) -> BenchmarkResult:
        catalog = OpenWakeWordCatalog(model_root=self.model_root)
        catalog_entries = {e["id"]: e for e in catalog.public_entries(framework)}
        art_versions = {
            m_id: catalog_entries.get(m_id, {}).get("artifactVersion")
            for m_id in requested_ids
        }

        mem_before = process_memory_snapshot()
        start_time = time.perf_counter()

        recorder = type(
            "Recorder",
            (),
            {"use_wake_words": True, "wakeword_backend": "openwakeword"},
        )()

        with patch.dict(os.environ, {OPENWAKEWORD_MODEL_ROOT_ENV: str(self.model_root)}):
            setup_wakeword_detection(
                recorder,
                "openwakeword",
                requested_ids,
                0.5,
                None,
                framework,
                load_openwakeword_modules=fake_model_factory,
            )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        mem_after = process_memory_snapshot()

        rss_before = int(mem_before.get("rssBytes", 0) or 0)
        rss_after = int(mem_after.get("rssBytes", 0) or 0)
        delta_rss = rss_after - rss_before

        loaded_ids = list(getattr(recorder, "wake_words_list", []))

        return BenchmarkResult(
            profile=profile_name,
            model_count=len(loaded_ids),
            requested_ids=requested_ids,
            loaded_ids=loaded_ids,
            initialization_time_ms=elapsed_ms,
            memory_before=mem_before,
            memory_after=mem_after,
            delta_rss_bytes=delta_rss,
            framework=framework,
            artifact_versions=art_versions,
            environment_evidence_status="HARNESS_VERIFIED",
        )


class WakeWordResourceEvidenceTests(unittest.TestCase):
    """Protects reproducible evidence harness across 1, 3, and max models."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        # Create model files for max 5 models plus pipeline models
        self.all_models = ["jarvis", "alexa", "samanta", "clover", "oracle"]
        for name in self.all_models:
            (self.root / f"{name}_v1.0.onnx").write_bytes(b"dummy_onnx_model_weights")
        (self.root / "melspectrogram.onnx").write_bytes(b"dummy_mel_pipeline")
        (self.root / "embedding_model.onnx").write_bytes(b"dummy_embedding_pipeline")

        class FakeOwwModel:
            def __init__(self, wakeword_models=None, **kwargs):
                self.models = {Path(p).name: object() for p in (wakeword_models or [])}

        class FakeOwwModule:
            pass

        self.fake_factory = lambda: (FakeOwwModule(), FakeOwwModel)
        self.harness = WakeWordEvidenceHarness(self.root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_single_model_evidence(self):
        result = self.harness.measure_profile(
            "single_model",
            ["jarvis"],
            fake_model_factory=self.fake_factory,
        )
        self.assertEqual(result.model_count, 1)
        self.assertEqual(result.loaded_ids, ["jarvis"])
        self.assertGreater(result.initialization_time_ms, 0.0)
        self.assertEqual(result.framework, "onnx")

    def test_three_models_evidence(self):
        result = self.harness.measure_profile(
            "three_models",
            ["jarvis", "alexa", "samanta"],
            fake_model_factory=self.fake_factory,
        )
        self.assertEqual(result.model_count, 3)
        self.assertEqual(result.loaded_ids, ["jarvis", "alexa", "samanta"])
        self.assertGreater(result.initialization_time_ms, 0.0)
        self.assertEqual(result.framework, "onnx")

    def test_max_models_evidence(self):
        result = self.harness.measure_profile(
            "max_models",
            self.all_models,
            fake_model_factory=self.fake_factory,
        )
        self.assertEqual(result.model_count, 5)
        self.assertEqual(result.loaded_ids, self.all_models)
        self.assertGreater(result.initialization_time_ms, 0.0)
        self.assertEqual(result.framework, "onnx")


if __name__ == "__main__":
    unittest.main()
