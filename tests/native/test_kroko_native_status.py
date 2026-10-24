"""Opt-in native C++ tests. Synthetic replies, never a live license qualification."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from VoiceSTT.kroko.buildinputs import KROKO_UPSTREAM_REVISION
from VoiceSTT.kroko.native_status_patch import patch_native_license_status
from VoiceSTT.install_kroko import patch_license_quiet_env


@pytest.fixture
def patched(tmp_path):
    configured = os.environ.get("VOICESTT_KROKO_NATIVE_SOURCE")
    if not configured or not shutil.which("g++"):
        pytest.skip("NOT_RUN: pinned source checkout and g++ required")
    root = Path(configured)
    def git(*args):
        return subprocess.check_output(["git", "-c", "safe.directory=" + str(root), "-C", str(root), *args])
    assert git("rev-parse", "HEAD").decode().strip() == KROKO_UPSTREAM_REVISION
    for relative in ("sherpa-onnx/csrc/license.h", "sherpa-onnx/csrc/online-transducer-model.cc",
                     "sherpa-onnx/python/csrc/sherpa-onnx.cc", "sherpa-onnx/csrc/njson.hpp"):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(git("show", KROKO_UPSTREAM_REVISION + ":" + relative))
    patch_native_license_status(tmp_path)
    patch_license_quiet_env(tmp_path)
    expected = {file: file.read_bytes() for file in tmp_path.rglob("*") if file.is_file()}
    patch_native_license_status(tmp_path)
    patch_license_quiet_env(tmp_path)
    assert all(file.read_bytes() == content for file, content in expected.items())
    return tmp_path


def compile_and_run(root, source, *, pro=False):
    path = root / "harness.cc"
    path.write_text(source, encoding="utf-8")
    command = ["g++", "-std=c++17", "-pthread", "-I" + str(root), str(path),
               "-lssl", "-lcrypto", "-o", str(root / "harness")]
    if pro:
        command.insert(1, "-DKROKO_LICENSE=1")
    subprocess.run(command, check=True, capture_output=True)
    return subprocess.check_output([str(root / "harness")], timeout=30).decode()


def test_actual_native_snapshot_with_concurrent_synthetic_replies(patched):
    harness = Path(__file__).with_name("kroko_status_harness.cc").read_text(encoding="utf-8-sig")
    assert "PASS native V1" in compile_and_run(patched, harness, pro=True)


@pytest.mark.parametrize("pro", [False, True])
def test_actual_export_without_activation_is_never_positive(patched, pro):
    source = (patched / "sherpa-onnx/csrc/online-transducer-model.cc").read_text()
    start = source.index("std::string KrokoLicenseStatusV1()")
    end = source.index("\n}", start) + 2
    # Compile the actual generated export, outside the unbuilt ONNX graph.
    harness = ('#include "sherpa-onnx/csrc/license.h"\n#include <cassert>\n'
               'namespace sherpa_onnx {\n' + source[start:end] + '\n}\n'
               'int main() { auto j = json::parse(sherpa_onnx::KrokoLicenseStatusV1());'
               'assert(j["schemaVersion"] == 1); assert(j["outcome"] == "unreachable"); }')
    compile_and_run(patched, harness, pro=pro)
