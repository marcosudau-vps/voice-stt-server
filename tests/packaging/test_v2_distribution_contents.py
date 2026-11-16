"""Real wheel/sdist contents after the V2 engine cleanup.

Builds the development distribution once with ``python -m build`` and
inspects the actual archives (not just ``setup.py``): engine modules, drafts,
removed files, ``Provides-Extra`` and ``Requires-Dist``.
"""

from __future__ import annotations

import email
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_MODULE_STEMS = (
    "parakeet_engine", "whisper_cpp_engine", "openai_api_engine", "openai_whisper_engine",
    "sherpa_onnx_engine", "cohere_transcribe_engine", "funasr_engine", "granite_speech_engine",
    "hf_transformers_engines", "moonshine_engine", "omnilingual_asr_engine", "qwen3_asr_engine",
)
FORBIDDEN_EXTRAS = (
    "whisper-cpp", "whispercpp", "openai-whisper", "sherpa-onnx", "sherpa", "omnilingual",
    "omnilingual-asr", "meta-omnilingual-asr", "transformers", "moonshine", "granite",
    "cohere", "qwen", "qwen3-asr", "parakeet",
)
FORBIDDEN_REQUIREMENTS = (
    "pywhispercpp", "openai-whisper", "sherpa-onnx", "nemo-toolkit", "nemo_toolkit",
    "omnilingual-asr", "qwen-asr", "transformers", "funasr", "torchaudio",
)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("v2-dist")
    result = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--sdist", "--outdir", str(out), str(REPO_ROOT)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-4000:]
    wheel = next(out.glob("*.whl"))
    sdist = next(out.glob("*.tar.gz"))
    return wheel, sdist


def _wheel_metadata(wheel):
    with zipfile.ZipFile(wheel) as archive:
        name = next(n for n in archive.namelist() if n.endswith(".dist-info/METADATA"))
        return email.message_from_string(archive.read(name).decode("utf-8"))


def test_the_wheel_ships_exactly_two_engine_modules(built):
    wheel, _sdist = built
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
    engines = sorted(
        n.rsplit("/", 1)[1] for n in names
        if n.startswith("VoiceSTT/transcription_engines/") and "_engine" in n.rsplit("/", 1)[1]
    )
    assert engines == ["faster_whisper_engine.py", "kroko_onnx_engine.py"]
    for stem in FORBIDDEN_MODULE_STEMS:
        assert not any(stem in n for n in names), stem
    assert not any(n.startswith("engineering/") for n in names)
    assert not any(n.endswith((".pyc", ".pyo")) or "__pycache__" in n for n in names)


def test_the_sdist_contains_no_draft_and_no_removed_engine(built):
    _wheel, sdist = built
    with tarfile.open(sdist) as archive:
        names = archive.getnames()
    assert not any("/engineering/" in n for n in names)
    for stem in FORBIDDEN_MODULE_STEMS:
        assert not any(stem in n for n in names), stem
    assert any(n.endswith("VoiceSTT/transcription_engines/kroko_onnx_engine.py") for n in names)
    assert any(n.endswith("VoiceSTT/transcription_engines/faster_whisper_engine.py") for n in names)


def test_wheel_metadata_offers_no_unsupported_engine_extra(built):
    wheel, _sdist = built
    message = _wheel_metadata(wheel)
    extras = set(message.get_all("Provides-Extra") or [])
    for extra in FORBIDDEN_EXTRAS:
        assert extra not in extras, extra
    assert {"faster-whisper", "recommended", "server", "openwakeword"} <= extras


def test_wheel_metadata_requires_no_engine_only_dependency(built):
    wheel, _sdist = built
    requirements = [r.lower() for r in (_wheel_metadata(wheel).get_all("Requires-Dist") or [])]
    for package in FORBIDDEN_REQUIREMENTS:
        assert not any(r.startswith(package) for r in requirements), package
    assert any(r.startswith("torch") for r in requirements), "torch stays a CPU runtime dependency"
