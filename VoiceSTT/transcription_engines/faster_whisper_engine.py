"""
Adapts faster-whisper models to the transcription engine interface.
"""

from importlib import import_module

from .base import (
    BaseTranscriptionEngine,
    TranscriptionEngineError,
    TranscriptionInfo,
    TranscriptionResult,
)
from .model_resolver import resolve_faster_whisper_model


def _load_faster_whisper():
    """
    Loads faster-whisper and its optional batched inference pipeline.
    """
    try:
        faster_whisper = import_module("faster_whisper")
    except ModuleNotFoundError as exc:
        raise TranscriptionEngineError(
            "The 'faster_whisper' transcription engine requires the optional "
            "'faster-whisper' package. Install it with "
            "'pip install \"VoiceSTT[faster-whisper]\"' or select a "
            "different transcription engine."
        ) from exc

    return faster_whisper, faster_whisper.BatchedInferencePipeline


class FasterWhisperEngine(BaseTranscriptionEngine):
    """
    Transcribes audio with faster-whisper.
    """

    engine_name = "faster_whisper"

    def __init__(self, config):
        """
        Initializes the faster-whisper model.
        """
        super().__init__(config)
        faster_whisper, batched_inference_pipeline = _load_faster_whisper()
        options = dict(self.config.engine_options or {})
        model_path = resolve_faster_whisper_model(
            self.config.model,
            self.config.download_root,
            options,
        )
        model_kwargs = {}
        for name in ("cpu_threads", "num_workers"):
            if name in options:
                model_kwargs[name] = int(options[name])
        model = faster_whisper.WhisperModel(
            model_size_or_path=model_path,
            device=self.config.device,
            compute_type=self.config.compute_type,
            device_index=self.config.gpu_device_index,
            download_root=self.config.download_root,
            **model_kwargs,
        )
        if self.config.batch_size > 0:
            model = batched_inference_pipeline(model=model)
        self.model = model

    def transcribe(self, audio, language=None, use_prompt=True):
        """
        Transcribes audio and returns normalized faster-whisper output.
        """
        audio = self._normalize_audio(audio)
        kwargs = {
            "language": language if language else None,
            "beam_size": self.config.beam_size,
            "initial_prompt": self._get_prompt(use_prompt),
            "suppress_tokens": self.config.suppress_tokens,
            "vad_filter": self.config.vad_filter,
        }
        if self.config.batch_size > 0:
            kwargs["batch_size"] = self.config.batch_size

        return self._transcribe(audio, kwargs)

    def transcribe_with_options(self, audio, language=None, use_prompt=True, options=None):
        """Transcribe with request-scoped OpenAI-compatible options."""

        audio = self._normalize_audio(audio)
        options = dict(options or {})
        timestamp_granularities = set(options.get("timestamp_granularities") or [])
        kwargs = {
            "language": language if language else None,
            "beam_size": self.config.beam_size,
            "initial_prompt": options.get("prompt") or self._get_prompt(use_prompt),
            "suppress_tokens": self.config.suppress_tokens,
            "vad_filter": self.config.vad_filter,
            "temperature": float(options.get("temperature", 0.0)),
            "word_timestamps": "word" in timestamp_granularities,
        }
        threshold = options.get("threshold")
        if threshold is not None and self.config.vad_filter:
            kwargs["vad_parameters"] = {"threshold": float(threshold)}
        if self.config.batch_size > 0:
            kwargs["batch_size"] = self.config.batch_size
        return self._transcribe(audio, kwargs, options.get("stream_callback"))

    def _transcribe(self, audio, kwargs, stream_callback=None):
        segments, info = self.model.transcribe(audio, **kwargs)
        segment_details = []
        text_parts = []
        for index, segment in enumerate(segments):
            segment_text = str(segment.text or "")
            text_parts.append(segment_text)
            words = []
            for word in getattr(segment, "words", None) or []:
                words.append({
                    "word": str(getattr(word, "word", "")),
                    "start": float(getattr(word, "start", 0.0)),
                    "end": float(getattr(word, "end", 0.0)),
                    "probability": float(getattr(word, "probability", 0.0)),
                })
            detail = {
                "id": int(getattr(segment, "id", index)),
                "seek": int(getattr(segment, "seek", 0)),
                "start": float(getattr(segment, "start", 0.0)),
                "end": float(getattr(segment, "end", 0.0)),
                "text": segment_text,
                "tokens": list(getattr(segment, "tokens", []) or []),
                "temperature": float(getattr(segment, "temperature", 0.0)),
                "avg_logprob": float(getattr(segment, "avg_logprob", 0.0)),
                "compression_ratio": float(getattr(segment, "compression_ratio", 0.0)),
                "no_speech_prob": float(getattr(segment, "no_speech_prob", 0.0)),
                "words": words,
            }
            segment_details.append(detail)
            if stream_callback is not None and segment_text:
                stream_callback(segment_text, detail)
        text = " ".join(part.strip() for part in text_parts if part.strip()).strip()
        return TranscriptionResult(
            text=text,
            info=TranscriptionInfo(
                language=getattr(info, "language", None),
                language_probability=getattr(info, "language_probability", 0.0),
            ),
            details={
                "duration": float(getattr(info, "duration", 0.0)),
                "duration_after_vad": float(getattr(info, "duration_after_vad", 0.0)),
                "segments": segment_details,
                "words": [word for segment in segment_details for word in segment["words"]],
            },
        )
