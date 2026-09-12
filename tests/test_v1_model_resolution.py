from pathlib import Path

import pytest

from VoiceSTT.transcription_engines.base import TranscriptionEngineError
from VoiceSTT.transcription_engines import model_resolver


def _local_ctranslate2_model(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "config.json").write_text("{}", encoding="utf-8")
    (path / "model.bin").write_bytes(b"v1-test")
    return path


def test_faster_whisper_missing_model_never_downloads_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv(model_resolver.FASTER_WHISPER_AUTO_DOWNLOAD_ENV, raising=False)
    monkeypatch.delenv(model_resolver.OFFLINE_MODELS_ENV, raising=False)
    monkeypatch.setenv(model_resolver.FASTER_WHISPER_ROOT_ENV, str(tmp_path))

    with pytest.raises(TranscriptionEngineError, match="disabled by default"):
        model_resolver.resolve_faster_whisper_model("small")


def test_faster_whisper_explicit_download_uses_reviewed_registry(monkeypatch, tmp_path):
    monkeypatch.setenv(model_resolver.FASTER_WHISPER_ROOT_ENV, str(tmp_path))

    resolved = model_resolver.resolve_faster_whisper_model(
        "large_turbo",
        options={"auto_download_model": True},
    )

    assert resolved == model_resolver.FASTER_WHISPER_MODEL_REGISTRY["large_turbo"]


def test_faster_whisper_explicit_download_rejects_unreviewed_model(monkeypatch, tmp_path):
    monkeypatch.setenv(model_resolver.FASTER_WHISPER_ROOT_ENV, str(tmp_path))

    with pytest.raises(TranscriptionEngineError, match="only accepts reviewed aliases"):
        model_resolver.resolve_faster_whisper_model(
            "vendor/arbitrary-model",
            options={"auto_download_model": True},
        )


def test_faster_whisper_local_absolute_model_is_always_allowed(tmp_path):
    model = _local_ctranslate2_model(tmp_path / "custom-model")

    assert model_resolver.resolve_faster_whisper_model(str(model)) == str(model.resolve())


def test_kroko_pro_missing_model_fails_with_provisioning_guidance(monkeypatch, tmp_path):
    monkeypatch.setenv(model_resolver.KROKO_VARIANT_ENV, "pro")
    monkeypatch.setenv(model_resolver.KROKO_ROOT_ENV, str(tmp_path))
    monkeypatch.delenv(model_resolver.OFFLINE_MODELS_ENV, raising=False)

    with pytest.raises(TranscriptionEngineError) as exc_info:
        model_resolver.resolve_kroko_model("Kroko-DE-Pro-64-L-Streaming-001.data")

    message = str(exc_info.value)
    assert "never downloaded automatically" in message
    assert model_resolver.KROKO_ROOT_ENV in message
    assert "KROKO_API_KEY" in message
    assert "https://kroko.ai/" in message


def test_kroko_pro_accepts_explicit_local_model(monkeypatch, tmp_path):
    monkeypatch.setenv(model_resolver.KROKO_VARIANT_ENV, "pro")
    model = tmp_path / "Kroko-DE-Pro-64-L-Streaming-001.data"
    model.write_bytes(b"licensed-test-model")

    assert model_resolver.resolve_kroko_model(str(model)) == str(model.resolve())
