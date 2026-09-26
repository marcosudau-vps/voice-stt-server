"""Keep the V1 wake-word manifest and bundled files in lockstep."""

import hashlib
import json

from VoiceSTT.core.openwakeword_catalog import BUNDLED_OPENWAKEWORD_MODEL_ROOT


def test_bundled_wakewords_match_manifest_and_hashes():
    root = BUNDLED_OPENWAKEWORD_MODEL_ROOT
    manifest = json.loads((root / "models.json").read_text(encoding="utf-8"))[
        "openwakeword_models"
    ]
    classifiers = manifest["onnx_models"]
    pipeline = manifest["pipeline_models"]
    declared_files = set(classifiers.values()) | set(pipeline.values())

    assert len(classifiers) == 14
    assert manifest["default_model"] in classifiers
    assert len(declared_files) == len(classifiers) + len(pipeline)
    assert set(manifest["sha256"]) == declared_files
    assert {path.name for path in root.glob("*.onnx")} == declared_files
    for filename in declared_files:
        assert hashlib.sha256((root / filename).read_bytes()).hexdigest() == manifest[
            "sha256"
        ][filename]
