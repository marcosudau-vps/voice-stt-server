"""Send concurrent real-audio requests to the OpenAI-compatible endpoint."""

import argparse
import concurrent.futures
import json
from pathlib import Path

import httpx


def post_request(base_url, audio_path, model, language="de", response_format="json", stream=False):
    data = {
        "model": model,
        "response_format": response_format,
        "language": language,
        "temperature": "0",
        "threshold": "0.5",
        "stream": str(stream).lower(),
    }
    if response_format == "verbose_json":
        data["timestamp_granularities[]"] = "word"
    with audio_path.open("rb") as audio:
        response = httpx.post(
            base_url.rstrip("/") + "/v1/audio/transcriptions",
            data=data,
            files={"file": (audio_path.name, audio, "audio/wav")},
            timeout=180.0,
        )
    response.raise_for_status()
    if stream:
        events = []
        for line in response.text.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
        done = next(event for event in reversed(events) if event.get("type") == "transcript.text.done")
        return {"model": model, "stream": True, "text": done["text"], "events": events}
    if response_format in {"json", "verbose_json", "diarized_json"}:
        payload = response.json()
        return {"model": model, "stream": False, "text": payload["text"], "payload": payload}
    return {"model": model, "stream": False, "text": response.text, "payload": response.text}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--main-model", default="whisper-1")
    parser.add_argument("--realtime-model", default="fast")
    parser.add_argument("--language", default="de")
    args = parser.parse_args(argv)

    requests = [
        (args.main_model, "verbose_json", False),
        (args.main_model, "json", True),
        (args.realtime_model, "json", False),
        (args.realtime_model, "srt", False),
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(requests)) as executor:
        futures = [
            executor.submit(post_request, args.base_url, args.audio, model, args.language, response_format, stream)
            for model, response_format, stream in requests
        ]
        results = [future.result() for future in futures]

    for result in results:
        if not result["text"].strip():
            raise RuntimeError(f"Empty transcription response for {result['model']}")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
