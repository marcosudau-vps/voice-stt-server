from types import SimpleNamespace
from unittest.mock import patch

from VoiceSTT import install_kroko


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
