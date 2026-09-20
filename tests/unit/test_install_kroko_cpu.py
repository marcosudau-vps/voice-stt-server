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


def test_windows_dockerfile_uses_pinned_openssl_nuget(tmp_path):
    dockerfile = tmp_path / "Dockerfile.windows"
    dockerfile.write_text(
        "# Windows-native OpenSSL\n"
        "RUN curl https://slproweb.com/download/Win64OpenSSL.exe\n"
        "ENV OPENSSL_ROOT_DIR=/opt/openssl-win64/app\n"
        "COPY in_windows_container.sh /usr/local/bin/in_windows_container.sh\n"
        "RUN chmod +x /usr/local/bin/in_windows_container.sh\n",
        encoding="utf-8",
    )

    install_kroko.patch_windows_dockerfile(tmp_path)

    patched = dockerfile.read_text(encoding="utf-8")
    assert "slproweb.com" not in patched.lower()
    assert install_kroko.WINDOWS_OPENSSL_URL in patched
    assert "curl unzip" in patched
    assert "libcrypto-3-x64.dll" in patched
    assert "libssl-3-x64.dll" in patched
    assert "innoextract" not in patched
    assert "sed -i 's/\\r$//'" in patched
