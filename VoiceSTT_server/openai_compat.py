"""OpenAI-compatible request parsing and transcription response formatting."""

import json
import math
from dataclasses import dataclass, field
from pathlib import Path


SUPPORTED_AUDIO_EXTENSIONS = {
    ".flac", ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".ogg", ".wav", ".webm"
}
SUPPORTED_RESPONSE_FORMATS = {"json", "text", "srt", "verbose_json", "vtt", "diarized_json"}
SUPPORTED_TIMESTAMP_GRANULARITIES = {"segment", "word"}


class OpenAIRequestError(ValueError):
    def __init__(self, message, param=None, code=None, status_code=400):
        super().__init__(message)
        self.param = param
        self.code = code
        self.status_code = status_code


@dataclass
class OpenAITranscriptionRequest:
    model: str
    language: str = None
    prompt: str = None
    response_format: str = "json"
    temperature: float = 0.0
    timestamp_granularities: list = field(default_factory=lambda: ["segment"])
    stream: bool = False
    include: list = field(default_factory=list)
    threshold: float = 0.5
    known_speaker_names: list = field(default_factory=list)
    known_speaker_references: list = field(default_factory=list)


def _as_bool(value, name):
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise OpenAIRequestError(f"'{name}' muss ein boolescher Wert sein.", name)


def _as_float(value, name, default, minimum=0.0, maximum=1.0):
    if value in (None, ""):
        return default
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise OpenAIRequestError(f"'{name}' muss eine Zahl sein.", name) from exc
    if result < minimum or result > maximum:
        raise OpenAIRequestError(
            f"'{name}' muss zwischen {minimum:g} und {maximum:g} liegen.", name
        )
    return result


def _form_list(form, name, split_commas=True):
    values = []
    for key in (name, f"{name}[]"):
        try:
            items = form.getlist(key)
        except AttributeError:
            item = form.get(key)
            items = [] if item is None else [item]
        for item in items:
            if item is None:
                continue
            if isinstance(item, str) and item.strip().startswith("["):
                try:
                    decoded = json.loads(item)
                except json.JSONDecodeError:
                    decoded = None
                if isinstance(decoded, list):
                    values.extend(str(value) for value in decoded)
                    continue
            if split_commas:
                values.extend(part.strip() for part in str(item).split(",") if part.strip())
            else:
                values.append(str(item))
    return list(dict.fromkeys(values))


def parse_transcription_form(form):
    model = str(form.get("model") or "").strip()
    if not model:
        raise OpenAIRequestError("Das Feld 'model' ist erforderlich.", "model")

    response_format = str(form.get("response_format") or "json").strip().lower()
    if response_format not in SUPPORTED_RESPONSE_FORMATS:
        raise OpenAIRequestError(
            "'response_format' muss einen dieser Werte haben: " + ", ".join(sorted(SUPPORTED_RESPONSE_FORMATS)),
            "response_format",
        )

    granularities = _form_list(form, "timestamp_granularities") or ["segment"]
    invalid_granularities = set(granularities) - SUPPORTED_TIMESTAMP_GRANULARITIES
    if invalid_granularities:
        raise OpenAIRequestError(
            "Nicht unterstützte Zeitstempelgranularität: " + ", ".join(sorted(invalid_granularities)),
            "timestamp_granularities",
        )
    if granularities != ["segment"] and response_format != "verbose_json":
        raise OpenAIRequestError(
            "'timestamp_granularities' requires response_format='verbose_json'.",
            "timestamp_granularities",
        )

    include = _form_list(form, "include")
    invalid_include = set(include) - {"logprobs"}
    if invalid_include:
        raise OpenAIRequestError(
            "Nicht unterstützter include-Wert: " + ", ".join(sorted(invalid_include)),
            "include",
        )

    names = _form_list(form, "known_speaker_names")
    references = _form_list(form, "known_speaker_references", split_commas=False)
    if len(names) > 4:
        raise OpenAIRequestError("Es werden höchstens 4 bekannte Sprecher unterstützt.", "known_speaker_names")
    if len(names) != len(references):
        raise OpenAIRequestError(
            "'known_speaker_names' und 'known_speaker_references' müssen gleich lang sein.",
            "known_speaker_references",
        )

    return OpenAITranscriptionRequest(
        model=model,
        language=(str(form.get("language")).strip() if form.get("language") else None),
        prompt=(str(form.get("prompt")) if form.get("prompt") else None),
        response_format=response_format,
        temperature=_as_float(form.get("temperature"), "temperature", 0.0),
        timestamp_granularities=granularities,
        stream=_as_bool(form.get("stream"), "stream"),
        include=include,
        threshold=_as_float(form.get("threshold"), "threshold", 0.5),
        known_speaker_names=names,
        known_speaker_references=references,
    )


def validate_audio_filename(filename):
    suffix = Path(filename or "audio").suffix.lower()
    if suffix not in SUPPORTED_AUDIO_EXTENSIONS:
        raise OpenAIRequestError(
            "Nicht unterstütztes Audioformat. Unterstützte Formate: "
            + ", ".join(sorted(SUPPORTED_AUDIO_EXTENSIONS)),
            "file",
        )


def openai_error(message, param=None, code=None, error_type="invalid_request_error"):
    return {"error": {"message": str(message), "type": error_type, "param": param, "code": code}}


def _fallback_segments(text, duration):
    return [{
        "id": 0, "seek": 0, "start": 0.0, "end": float(duration), "text": text,
        "tokens": [], "temperature": 0.0, "avg_logprob": 0.0,
        "compression_ratio": 0.0, "no_speech_prob": 0.0, "words": [],
    }] if text else []


def _segments(result, duration):
    details = getattr(result, "details", None) or {}
    return details.get("segments") or _fallback_segments(result.text, duration)


def _words(result):
    details = getattr(result, "details", None) or {}
    return details.get("words") or []


def _usage(duration):
    return {"type": "duration", "seconds": int(math.ceil(max(0.0, duration)))}


def _logprobs(result):
    output = []
    for segment in _segments(result, 0.0):
        logprob = float(segment.get("avg_logprob", 0.0))
        for token in str(segment.get("text", "")).split():
            rendered = token + " "
            output.append({"token": rendered, "logprob": logprob, "bytes": list(rendered.encode("utf-8"))})
    return output


def format_json_response(request, result, duration):
    details = getattr(result, "details", None) or {}
    duration = float(details.get("duration") or duration)
    if request.response_format == "verbose_json":
        payload = {
            "task": "transcribe",
            "language": getattr(getattr(result, "info", None), "language", None) or request.language,
            "duration": duration,
            "text": result.text,
            "segments": _segments(result, duration),
            "usage": _usage(duration),
        }
        if "word" in request.timestamp_granularities:
            payload["words"] = [
                {"word": word["word"], "start": word["start"], "end": word["end"]}
                for word in _words(result)
            ]
        return payload
    if request.response_format == "diarized_json":
        speaker = request.known_speaker_names[0] if request.known_speaker_names else "A"
        return {
            "task": "transcribe", "duration": duration, "text": result.text,
            "segments": [
                {"type": "transcript.text.segment", "id": f"seg_{index:03d}",
                 "start": float(segment.get("start", 0.0)), "end": float(segment.get("end", duration)),
                 "text": str(segment.get("text", "")).strip(), "speaker": speaker}
                for index, segment in enumerate(_segments(result, duration), 1)
            ],
            "usage": _usage(duration),
            "compatibility": {
                "diarization": "single_speaker",
                "reason": "Die konfigurierten lokalen ASR-Engines enthalten kein Diarisierungsmodell.",
            },
        }
    payload = {"text": result.text, "usage": _usage(duration)}
    if "logprobs" in request.include:
        payload["logprobs"] = _logprobs(result)
    return payload


def _timestamp(seconds, separator=","):
    milliseconds = max(0, int(round(float(seconds) * 1000)))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{milliseconds:03d}"


def format_caption_response(request, result, duration):
    segments = _segments(result, duration)
    if request.response_format == "srt":
        blocks = [
            f"{index}\n{_timestamp(segment['start'])} --> {_timestamp(segment['end'])}\n{str(segment['text']).strip()}"
            for index, segment in enumerate(segments, 1)
        ]
        return "\n\n".join(blocks) + ("\n" if blocks else "")
    if request.response_format == "vtt":
        blocks = ["WEBVTT"] + [
            f"{_timestamp(segment['start'], '.')} --> {_timestamp(segment['end'], '.')}\n{str(segment['text']).strip()}"
            for segment in segments
        ]
        return "\n\n".join(blocks) + "\n"
    return result.text


def sse_data(payload):
    return "data: " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n\n"
