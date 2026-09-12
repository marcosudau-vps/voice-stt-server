from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import v1_kroko_release as kr


def test_upstream_is_immutable_and_windows_path_is_supported():
    assert kr.UPSTREAM_REVISION == "8657e655192623b98d7708e742a72987f953d3a2"
    int(kr.UPSTREAM_REVISION, 16)
    assert set(kr.SUPPORTED_PLATFORMS) == {"linux_x86_64", "win_amd64"}


def test_fingerprints_bind_variant_and_platform():
    values = {kr.fingerprint_for(v, p) for v in kr.SUPPORTED_VARIANTS for p in kr.SUPPORTED_PLATFORMS}
    assert len(values) == 4
    assert kr.fingerprint_payload("pro", "win_amd64")["buildMode"] == "windows-docker-cross-wheel"


def test_runtime_key_rejected_before_build(monkeypatch, tmp_path):
    monkeypatch.setenv(kr.RUNTIME_CREDENTIAL_ENV, "secret-must-not-enter-build")
    with pytest.raises(kr.ReleaseKrokoError, match="runtime-only"):
        kr._build("free", "linux_x86_64", tmp_path)


def test_artifact_verification_binds_platform(monkeypatch, tmp_path):
    wheel = tmp_path / "kroko_onnx-1.0-cp312-cp312-linux_x86_64.whl"
    wheel.write_bytes(b"fake")
    monkeypatch.setattr(kr, "_wheel_tags", lambda _p: ["cp312-cp312-linux_x86_64"])
    data = {
        **kr.fingerprint_payload("free", "linux_x86_64"),
        "fingerprint": kr.fingerprint_for("free", "linux_x86_64"),
        "wheel": {"filename": wheel.name, "sha256": kr.sha256_file(wheel), "bytes": wheel.stat().st_size, "tags": ["cp312-cp312-linux_x86_64"]},
    }
    (tmp_path / "artifact.json").write_text(json.dumps(data))
    assert kr.verify_artifact("free", tmp_path, "linux_x86_64")["platform"] == "linux_x86_64"
    with pytest.raises(kr.ReleaseKrokoError):
        kr.verify_artifact("free", tmp_path, "win_amd64")
