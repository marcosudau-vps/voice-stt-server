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
    values = {
        kr.fingerprint_for(v, p)
        for v in kr.SUPPORTED_VARIANTS
        for p in kr.SUPPORTED_PLATFORMS
    }
    assert len(values) == 4
    win = kr.fingerprint_payload("pro", "win_amd64")
    assert win["buildMode"] == "windows-docker-cross-wheel"
    linux = kr.fingerprint_payload("pro", "linux_x86_64")
    assert linux["buildMode"] == "linux-bookworm-container-wheel"
    assert win["windowsOpenSsl"] == {
        "package": "openssl-native",
        "version": "3.5.5",
        "url": kr.WINDOWS_OPENSSL_URL,
    }
    assert "windowsOpenSsl" not in kr.fingerprint_payload("pro", "linux_x86_64")


def test_release_text_fingerprint_is_line_ending_independent(tmp_path):
    crlf = tmp_path / "crlf.txt"
    lf = tmp_path / "lf.txt"
    crlf.write_bytes(b"one\r\ntwo\r\n")
    lf.write_bytes(b"one\ntwo\n")
    assert kr.sha256_release_text(crlf) == kr.sha256_release_text(lf)


def test_linux_builder_and_runtime_share_exact_base_image():
    builder = kr.BUILDER_DOCKERFILE.read_text(encoding="utf-8")
    runtime = (kr.ROOT / "build" / "v1-release.Dockerfile").read_text(encoding="utf-8")
    builder_from = next(line for line in builder.splitlines() if line.startswith("FROM "))
    runtime_from = next(line for line in runtime.splitlines() if line.startswith("FROM "))
    assert builder_from == runtime_from
    assert "@sha256:" in builder_from


def test_linux_container_build_uses_pinned_builder_and_restores_ownership(monkeypatch, tmp_path):
    commands = []
    monkeypatch.setattr(kr, "_run", lambda command, cwd=None, env=None: commands.append(command))
    monkeypatch.setattr(kr, "fingerprint_for", lambda variant, platform: "a" * 64)

    kr._build_linux_in_container("pro", tmp_path)

    assert commands[0][:4] == ["docker", "build", "--platform", "linux/amd64"]
    assert str(kr.BUILDER_DOCKERFILE) in commands[0]
    build_run = commands[1]
    assert f"{kr.LINUX_CONTAINER_ENV}=1" in build_run
    assert "--variant" in build_run and "pro" in build_run
    if hasattr(kr.os, "getuid"):
        assert commands[2][commands[2].index("--entrypoint") + 1] == "chown"


def test_windows_openssl_patch_is_pinned_and_has_native_contract(tmp_path):
    dockerfile = tmp_path / "Dockerfile.windows"
    dockerfile.write_text(
        "FROM ubuntu:24.04\n"
        "# Windows-native OpenSSL -- moving upstream block\n"
        "RUN echo obsolete-slproweb\n"
        "ENV OPENSSL_ROOT_DIR=/opt/openssl-win64/app\n"
        "ENV OPENSSL_DIR=/opt/openssl-win64/app\n",
        encoding="utf-8",
    )

    kr._patch_windows_openssl_source(tmp_path)
    text = dockerfile.read_text(encoding="utf-8")

    assert "obsolete-slproweb" not in text
    assert kr.WINDOWS_OPENSSL_URL in text
    assert "openssl-native.3.5.5.nupkg" in text
    assert "libcrypto.lib" in text
    assert "libssl.lib" in text
    assert "libcrypto-3-x64.dll" in text
    assert "libssl-3-x64.dll" in text
    assert "docs/license.txt" in text
    assert "ENV OPENSSL_ROOT_DIR=/opt/openssl-win64/app" in text


def test_windows_output_ownership_patch_reuses_pinned_builder(tmp_path):
    script = tmp_path / "build_windows.sh"
    script.write_text(
        '#!/bin/bash\n    rm -rf "$host_out"\necho done\n', encoding="utf-8"
    )

    kr._patch_windows_output_ownership(tmp_path)
    text = script.read_text(encoding="utf-8")

    assert '--entrypoint chown' in text
    assert '-v "$host_out:/out"' in text
    assert '"$IMAGE" -R "$(id -u):$(id -g)" /out' in text
    assert text.index("--entrypoint chown") < text.index('rm -rf "$host_out"')
    assert text.count('rm -rf "$host_out"') == 1


def test_runtime_key_rejected_before_build(monkeypatch, tmp_path):
    monkeypatch.setenv(kr.RUNTIME_CREDENTIAL_ENV, "secret-must-not-enter-build")
    with pytest.raises(kr.ReleaseKrokoError, match="runtime-only"):
        kr._build("free", "linux_x86_64", tmp_path)


def test_artifact_verification_binds_platform(monkeypatch, tmp_path):
    wheel = tmp_path / "kroko_onnx-1.0-cp312-cp312-linux_x86_64.whl"
    wheel.write_bytes(b"fake")
    monkeypatch.setattr(
        kr,
        "_wheel_tags",
        lambda _p: ["cp312-cp312-linux_x86_64"],
    )
    data = {
        **kr.fingerprint_payload("free", "linux_x86_64"),
        "fingerprint": kr.fingerprint_for("free", "linux_x86_64"),
        "wheel": {
            "filename": wheel.name,
            "sha256": kr.sha256_file(wheel),
            "bytes": wheel.stat().st_size,
            "tags": ["cp312-cp312-linux_x86_64"],
        },
    }
    (tmp_path / "artifact.json").write_text(json.dumps(data))
    assert (
        kr.verify_artifact("free", tmp_path, "linux_x86_64")["platform"]
        == "linux_x86_64"
    )
    with pytest.raises(kr.ReleaseKrokoError):
        kr.verify_artifact("free", tmp_path, "win_amd64")
