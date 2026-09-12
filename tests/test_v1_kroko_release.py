from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v1_kroko_release as kr  # noqa: E402


def _fake_artifact(tmp_path: Path, variant: str):
    tmp_path.mkdir(parents=True, exist_ok=True)
    wheel = tmp_path / f"kroko_onnx-1.12.9-1{variant}-cp312-cp312-linux_x86_64.whl"
    wheel.write_bytes(("wheel-" + variant).encode("ascii"))
    manifest = {
        **kr.fingerprint_payload(variant),
        "fingerprint": kr.fingerprint_for(variant),
        "wheel": {
            "filename": wheel.name,
            "sha256": kr.sha256_file(wheel),
            "bytes": wheel.stat().st_size,
        },
    }
    (tmp_path / "artifact.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return wheel


def test_upstream_is_immutable_commit_not_branch():
    assert kr.UPSTREAM_REPO == "https://github.com/kroko-ai/kroko-onnx.git"
    assert len(kr.UPSTREAM_REVISION) == 40
    int(kr.UPSTREAM_REVISION, 16)
    assert kr.UPSTREAM_REVISION != "cross-platform-builds"


def test_free_and_pro_cache_identities_cannot_cross():
    assert kr.fingerprint_for("free") != kr.fingerprint_for("pro")
    assert kr.fingerprint_payload("free")["variant"] == "free"
    assert kr.fingerprint_payload("pro")["variant"] == "pro"


def test_fingerprint_binds_v1_installer_and_builder_dockerfile():
    payload = kr.fingerprint_payload("free")
    assert payload["v1InstallerSha256"] == kr.sha256_file(ROOT / "VoiceSTT" / "install_kroko.py")
    assert payload["builderDockerfileSha256"] == kr.sha256_file(
        ROOT / "build" / "v1-kroko-builder.Dockerfile"
    )


def test_cached_artifact_is_hash_verified(tmp_path):
    wheel = _fake_artifact(tmp_path, "free")
    verified = kr.verify_artifact("free", tmp_path)
    assert verified["variant"] == "free"

    wheel.write_bytes(b"tampered")
    with pytest.raises(kr.ReleaseKrokoError, match="hash mismatch"):
        kr.verify_artifact("free", tmp_path)


def test_cached_free_artifact_cannot_be_used_as_pro(tmp_path):
    _fake_artifact(tmp_path, "free")
    with pytest.raises(kr.ReleaseKrokoError, match="mismatch"):
        kr.verify_artifact("pro", tmp_path)


def test_runtime_key_is_explicitly_rejected_as_build_input(monkeypatch, tmp_path):
    monkeypatch.setenv(kr.RUNTIME_CREDENTIAL_ENV, "must-not-enter-build")
    with pytest.raises(kr.ReleaseKrokoError, match="runtime credential"):
        kr._build_inside_release_builder("free", tmp_path)


def test_release_builder_is_pinned_and_keeps_v1_surface_only():
    text = (ROOT / "build" / "v1-kroko-builder.Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.12-slim-bookworm@sha256:" in text
    assert "VoiceSTT/install_kroko.py" in text
    assert "VoiceSTT/kroko/" not in text
    assert "build/vps" not in text
    assert "KROKO_API_KEY" not in text
