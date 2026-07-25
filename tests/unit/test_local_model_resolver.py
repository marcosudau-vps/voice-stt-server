import os
from pathlib import Path

import pytest

from VoiceSTT.transcription_engines.base import TranscriptionEngineError
from VoiceSTT.transcription_engines.model_resolver import (
    resolve_faster_whisper_model,
    resolve_kroko_model,
)


def make_ctranslate2_model(path: Path):
    path.mkdir(parents=True)
    (path / "config.json").write_text("{}", encoding="utf-8")
    (path / "model.bin").write_bytes(b"model")


def test_resolves_flat_central_faster_whisper_layout(tmp_path):
    model = tmp_path / "models--Systran--faster-whisper-tiny"
    make_ctranslate2_model(model)
    assert resolve_faster_whisper_model(
        "tiny", options={"model_root": str(tmp_path), "local_files_only": True}
    ) == str(model.resolve())


def test_resolves_huggingface_snapshot_layout(tmp_path):
    snapshot = tmp_path / "models--Systran--faster-whisper-tiny.en" / "snapshots" / "abc"
    make_ctranslate2_model(snapshot)
    assert resolve_faster_whisper_model(
        "tiny.en", options={"model_root": str(tmp_path), "local_files_only": True}
    ) == str(snapshot.resolve())


def test_offline_faster_whisper_never_falls_back_to_download(tmp_path):
    with pytest.raises(TranscriptionEngineError, match="Offline model mode"):
        resolve_faster_whisper_model(
            "missing", options={"model_root": str(tmp_path), "local_files_only": True}
        )


def test_resolves_kroko_from_dedicated_root(tmp_path):
    model = tmp_path / "Kroko-DE-Community-64-L-Streaming-001.data"
    model.write_bytes(b"model")
    assert resolve_kroko_model(
        model.name, options={"model_root": str(tmp_path), "local_files_only": True}
    ) == str(model.resolve())


def test_offline_kroko_never_falls_back_to_download(tmp_path):
    with pytest.raises(TranscriptionEngineError, match="Offline model mode"):
        resolve_kroko_model(
            "missing.data", options={"model_root": str(tmp_path), "local_files_only": True}
        )
