from types import SimpleNamespace
from unittest.mock import patch
import zipfile

import pytest

from VoiceSTT import install_kroko
from VoiceSTT.kroko import artifacts


def _untagged_linux_wheel(root, *, build=None):
    path = root / "kroko_onnx-1.12.9-cp312-cp312-linux_x86_64.whl"
    wheel = (
        "Wheel-Version: 1.0\n"
        "Generator: test\n"
        "Root-Is-Purelib: false\n"
        "Tag: cp312-cp312-linux_x86_64\n"
    )
    if build:
        wheel += "Build: {0}\n".format(build)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("kroko_onnx-1.12.9.dist-info/WHEEL", wheel)
        archive.writestr(
            "kroko_onnx-1.12.9.dist-info/RECORD",
            "kroko_onnx-1.12.9.dist-info/WHEEL,,\n"
            "kroko_onnx-1.12.9.dist-info/RECORD,,\n",
        )
    return path


@pytest.mark.parametrize("variant", ["free", "pro"])
def test_linux_wheel_is_retagged_in_filename_and_internal_metadata(tmp_path, variant):
    source = _untagged_linux_wheel(tmp_path)
    tagged = install_kroko.retag_linux_wheel(source, variant)

    assert tagged.name == (
        "kroko_onnx-1.12.9-1{0}-cp312-cp312-linux_x86_64.whl".format(
            variant
        )
    )
    assert artifacts.read_wheel_metadata(tagged)["build"] == "1" + variant
    assert artifacts.variant_of_wheel(tagged) == variant
    assert not source.exists()
    assert not list(tmp_path.glob("*.part"))

    with zipfile.ZipFile(tagged) as archive:
        record = archive.read(
            "kroko_onnx-1.12.9.dist-info/RECORD"
        ).decode("utf-8")
    assert "dist-info/WHEEL,sha256=" in record


def test_linux_wheel_retag_refuses_free_pro_mismatch(tmp_path):
    source = _untagged_linux_wheel(tmp_path, build="1pro")
    with pytest.raises(install_kroko.KrokoInstallError, match="metadata declares pro"):
        install_kroko.retag_linux_wheel(source, "free")


def test_windows_wheel_selection_remains_variant_tagged(tmp_path):
    wheel_dir = tmp_path / "release_artifacts" / "windows"
    wheel_dir.mkdir(parents=True)
    expected = wheel_dir / "kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64.whl"
    expected.write_bytes(b"wheel")
    assert install_kroko.find_windows_wheel(tmp_path, "free") == expected


def test_linux_kroko_build_forces_cpu_only_cmake_flags(tmp_path):
    args = SimpleNamespace(variant="free", skip_install=True)

    with (
        patch.object(install_kroko, "ensure_program"),
        patch.object(install_kroko, "patch_license_quiet_env"),
        patch.object(install_kroko, "run") as run,
    ):
        install_kroko.install_linux(args, tmp_path)

    environment = run.call_args.kwargs["env"]
    flags = environment["SHERPA_ONNX_CMAKE_ARGS"]
    assert "SHERPA_ONNX_ENABLE_GPU=OFF" in flags
    assert "SHERPA_ONNX_ENABLE_PORTAUDIO=OFF" in flags
    assert "SHERPA_ONNX_ENABLE_WEBSOCKET=ON" in flags
    assert "SHERPA_ONNX_ENABLE_TTS=OFF" in flags
    assert "SHERPA_ONNX_ENABLE_SPEAKER_DIARIZATION=OFF" in flags
    assert "SHERPA_ONNX_ENABLE_BINARY=OFF" in flags
