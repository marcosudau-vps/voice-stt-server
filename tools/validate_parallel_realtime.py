"""Validate WebSocket realtime/final output while the HTTP API is busy."""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
import numpy as np
import websockets

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api_fastapi_server.protocol import encode_audio_packet
from api_fastapi_server.server import decode_audio_float32


SAMPLE_RATE = 16000


def http_transcription(base_url, audio_path, language="de", api_key=None):
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
    with audio_path.open("rb") as audio:
        response = httpx.post(
            base_url.rstrip("/") + "/v1/audio/transcriptions",
            data={"model": "whisper-1", "language": language},
            files={"file": (audio_path.name, audio, "audio/wav")},
            headers=headers,
            timeout=180.0,
        )
    response.raise_for_status()
    return response.json()["text"]


def set_wake_word_for_test(base_url, admin_api_key, enabled, snapshot=None):
    """Disable wake-word gating for the test or restore its previous settings."""
    headers = {"X-VoiceSTT-Admin-Key": admin_api_key}
    endpoint = base_url.rstrip("/") + "/api/wake-word"
    if enabled:
        payload = {
            "enabled": True,
            "backend": snapshot["backend"],
            "words": snapshot["words"],
            "sensitivity": snapshot["sensitivity"],
            "timeout": snapshot["timeout"],
            "bufferDuration": snapshot["bufferDuration"],
            "followupWindow": snapshot["followupWindow"],
            "openwakewordModelPaths": snapshot["openwakewordModelPaths"],
        }
        response = httpx.put(endpoint, headers=headers, json=payload, timeout=30.0)
        response.raise_for_status()
        return snapshot
    response = httpx.get(endpoint, headers=headers, timeout=30.0)
    response.raise_for_status()
    snapshot = response.json()
    if snapshot.get("enabled"):
        response = httpx.put(
            endpoint, headers=headers, json={"enabled": False}, timeout=30.0
        )
        response.raise_for_status()
    return snapshot


async def validate(base_url, audio_path, timeout, language="de", api_key=None):
    parsed = urlparse(base_url)
    websocket_scheme = "wss" if parsed.scheme == "https" else "ws"
    websocket_url = f"{websocket_scheme}://{parsed.netloc}/ws/transcribe"
    messages = []
    final_event = asyncio.Event()

    async with websockets.connect(
        websocket_url,
        max_size=2**22,
        open_timeout=timeout,
    ) as websocket:
        async def receive_messages():
            async for raw in websocket:
                message = json.loads(raw)
                messages.append(message)
                if message.get("type") == "final" and message.get("text", "").strip():
                    final_event.set()

        receiver = asyncio.create_task(receive_messages())
        await websocket.send(json.dumps({"type": "start"}))

        source = decode_audio_float32(audio_path.read_bytes())
        audio = np.concatenate([
            np.zeros(int(0.6 * SAMPLE_RATE), dtype=np.float32),
            source,
            np.zeros(int(1.5 * SAMPLE_RATE), dtype=np.float32),
        ])
        pcm = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
        chunk_frames = 512
        http_task = None
        started = time.monotonic()
        for offset in range(0, len(pcm), chunk_frames):
            chunk = pcm[offset:offset + chunk_frames]
            packet = encode_audio_packet(
                {
                    "sampleRate": SAMPLE_RATE,
                    "channels": 1,
                    "format": "pcm_s16le",
                    "frames": len(chunk),
                },
                chunk.tobytes(),
            )
            await websocket.send(packet)
            if http_task is None and offset >= int(0.8 * SAMPLE_RATE):
                http_task = asyncio.create_task(asyncio.to_thread(
                    http_transcription, base_url, audio_path, language, api_key
                ))
            await asyncio.sleep(len(chunk) / SAMPLE_RATE)

        await asyncio.wait_for(final_event.wait(), timeout=timeout)
        http_text = await asyncio.wait_for(http_task, timeout=timeout)
        await websocket.send(json.dumps({"type": "stop"}))
        await websocket.close()
        await receiver

    realtime = [message for message in messages if message.get("type") == "realtime" and message.get("text")]
    finals = [message for message in messages if message.get("type") == "final" and message.get("text")]
    if not realtime:
        raise RuntimeError("No non-empty realtime WebSocket response received")
    if not finals:
        raise RuntimeError("No non-empty final WebSocket response received")
    return {
        "elapsedSeconds": round(time.monotonic() - started, 3),
        "httpText": http_text,
        "realtimeTexts": [message["text"] for message in realtime],
        "finalTexts": [message["text"] for message in finals],
        "messageTypes": [message.get("type") for message in messages],
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--language", default="de")
    parser.add_argument("--api-key", default=os.getenv("VOICESTT_API_KEY"))
    parser.add_argument(
        "--temporarily-disable-wake-word",
        action="store_true",
        help="Deaktiviert das Weckwort mit dem Admin-Key nur für die Testdauer.",
    )
    parser.add_argument(
        "--admin-api-key", default=os.getenv("VOICESTT_ADMIN_API_KEY")
    )
    args = parser.parse_args(argv)
    wake_word_snapshot = None
    try:
        if args.temporarily_disable_wake_word:
            if not args.admin_api_key:
                parser.error("--admin-api-key ist für die temporäre Deaktivierung erforderlich")
            wake_word_snapshot = set_wake_word_for_test(
                args.base_url, args.admin_api_key, False
            )
        print(json.dumps(
            asyncio.run(validate(
                args.base_url, args.audio, args.timeout, args.language, args.api_key
            )),
            ensure_ascii=False, indent=2,
        ))
    finally:
        if wake_word_snapshot and wake_word_snapshot.get("enabled"):
            set_wake_word_for_test(
                args.base_url, args.admin_api_key, True, wake_word_snapshot
            )


if __name__ == "__main__":
    main()
