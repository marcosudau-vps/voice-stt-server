import hashlib
import json
import zipfile

import pytest

from tools.v1_wakeword_bundle import PREFIX, verify_wakeword_bundle


def _wheel(path, *, corrupt=False, missing=None):
    classifiers = {f"wake_{index}": f"wake_{index}.onnx" for index in range(14)}
    pipeline = {"embedding_model_onnx": "embedding.onnx", "melspectrogram_onnx": "mel.onnx"}
    filenames = set(classifiers.values()) | set(pipeline.values())
    payload = {filename: filename.encode() for filename in filenames}
    manifest = {
        "openwakeword_models": {
            "default_model": "wake_0",
            "onnx_models": classifiers,
            "pipeline_models": pipeline,
            "sha256": {name: hashlib.sha256(data).hexdigest() for name, data in payload.items()},
        }
    }
    if corrupt:
        payload["wake_0.onnx"] = b"corrupt"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(PREFIX + "models.json", json.dumps(manifest))
        for name, data in payload.items():
            if name != missing:
                archive.writestr(PREFIX + name, data)
    return path


def test_complete_bundle_is_accepted(tmp_path):
    verify_wakeword_bundle(_wheel(tmp_path / "complete.whl"))


@pytest.mark.parametrize("defect", ["corrupt", "missing"])
def test_incomplete_bundle_is_rejected(tmp_path, defect):
    wheel = _wheel(
        tmp_path / "incomplete.whl",
        corrupt=defect == "corrupt",
        missing="wake_1.onnx" if defect == "missing" else None,
    )
    with pytest.raises(ValueError):
        verify_wakeword_bundle(wheel)
