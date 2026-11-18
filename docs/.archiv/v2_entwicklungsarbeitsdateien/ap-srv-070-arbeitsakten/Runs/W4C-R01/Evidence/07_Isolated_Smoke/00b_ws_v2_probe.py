"""AP-SRV-070 W4C isolated smoke: minimal /ws/v2 handshake probe.

Not part of the product; a throwaway evidence-gathering script run against
the isolated smoke container. Sends a minimal, spec-valid `hello` envelope
(manual trigger only, no wake word) and reports whether the server answered
with `hello.accepted`.
"""
import asyncio
import json
import sys
import uuid

import websockets


async def main(url: str) -> int:
    hello = {
        "type": "hello",
        "supportedProtocolVersions": [2],
        "clientVersion": "w4c-smoke-probe",
        "clientCommit": "0" * 40,
        "clientRunId": str(uuid.uuid4()),
        "requestedSession": {
            "trigger": {"manual": True, "wakeWord": False},
            "wakeWordIds": [],
        },
        "runtimeSuppression": {"manual": False, "wakeWord": False},
    }
    async with websockets.connect(url, open_timeout=10) as ws:
        await ws.send(json.dumps(hello))
        raw = await asyncio.wait_for(ws.recv(), timeout=10)
        payload = json.loads(raw)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload.get("type") == "hello.accepted" else 1


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:8010/ws/v2"
    raise SystemExit(asyncio.run(main(url)))
