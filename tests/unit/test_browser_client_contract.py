"""GATE 5 – the bundled browser client against the current server contract.

The example client in ``app_browserclient/client.js`` is part of the
compatibility gate, so its wire behaviour is verified here rather than assumed.

Two things are checked:

1. **Static contract** – the shipped JavaScript actually speaks the current
   protocol (correct WebSocket path, sends ``start``, consumes ``final``). This
   catches the exact class of rot that was found: the previous version
   connected to ``ws://localhost:9001`` with no path and waited for a
   ``fullSentence`` message type that the server has not produced for a long
   time.

2. **Replayed behaviour** – a Python client performs precisely the sequence the
   browser client performs (same URL, same ``start`` command, same audio packet
   framing) against the real app, and the server accepts it.

What this does *not* prove is that a real browser renders it; that remains a
manual step.
"""

import json
import re
import struct
import unittest
from pathlib import Path

import numpy as np

from tests.unit.test_server_controlled_e2e import (
    GateAwareRecorder,
    TestClient,
    build_app,
)


CLIENT_JS = (
    Path(__file__).resolve().parents[2] / "app_browserclient" / "client.js"
)
SAMPLE_RATE = 16000


class BrowserClientSourceContractTests(unittest.TestCase):
    """The shipped example must not describe a protocol that no longer exists."""

    @classmethod
    def setUpClass(cls):
        cls.source = CLIENT_JS.read_text(encoding="utf-8")

    def test_it_connects_to_the_transcribe_route(self):
        self.assertIn("/ws/transcribe", self.source)

    def test_it_does_not_connect_to_the_bare_root_path(self):
        # The server registers only /ws/logs and /ws/transcribe.
        self.assertNotRegex(
            self.source,
            r"""new WebSocket\(\s*["']wss?://[^"']*:\d+["']\s*\)""",
            "connecting to the origin without a path cannot reach any route",
        )

    def test_it_starts_the_stream_before_sending_audio(self):
        self.assertRegex(
            self.source,
            r"""JSON\.stringify\(\s*\{\s*type:\s*["']start["']""",
            "the example must send the start command before streaming audio",
        )

    def test_it_consumes_the_current_message_types(self):
        for message_type in ("realtime", "final"):
            with self.subTest(message_type=message_type):
                self.assertIn(f'"{message_type}"', self.source)

    def test_it_no_longer_expects_the_retired_full_sentence_type(self):
        # The local accumulator is still called `fullSentences`; what must be
        # gone is the *message type* the server no longer sends.
        self.assertNotRegex(
            self.source,
            r"""["']fullSentence["']""",
            "the server does not emit a fullSentence message type",
        )

    def test_it_sends_the_audio_metadata_the_server_validates(self):
        for field in ("sampleRate", "channels", "format", "frames"):
            with self.subTest(field=field):
                self.assertIn(field, self.source)
        self.assertIn("pcm_s16le", self.source)

    def test_the_websocket_url_is_built_once_and_reused(self):
        matches = re.findall(r"new WebSocket\(([^)]*)\)", self.source)
        self.assertTrue(matches, "the example must open a WebSocket")
        for expression in matches:
            with self.subTest(expression=expression):
                self.assertIn(
                    "TRANSCRIBE_URL",
                    expression,
                    "every connection must use the same validated URL",
                )


def _receive_until(socket, wanted, limit=25):
    """Skips the normal `ready`/`status` chatter and returns the wanted frame."""
    seen = []
    for _ in range(limit):
        message = socket.receive_json()
        seen.append(message.get("type"))
        if message.get("type") in wanted:
            return message
    raise AssertionError(f"none of {wanted} arrived; saw {seen}")


def browser_style_packet(sample_rate=SAMPLE_RATE, frames=320):
    """Exactly the framing `client.js` builds: length + JSON + PCM."""
    samples = (
        np.sin(np.linspace(0, 20 * np.pi, frames)).astype(np.float32) * 0.4
    )
    pcm = (samples * 32767).astype("<i2").tobytes()
    metadata = json.dumps(
        {
            "sampleRate": sample_rate,
            "channels": 1,
            "format": "pcm_s16le",
            "frames": frames,
        }
    ).encode("utf-8")
    return struct.pack("<I", len(metadata)) + metadata + pcm


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class BrowserClientReplayTests(unittest.TestCase):
    """The same sequence the browser performs, replayed against the real app."""

    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    def test_the_browser_sequence_is_accepted_by_the_server(self):
        with TestClient(self.app) as client:
            # The browser client sends no activation query parameters.
            with client.websocket_connect("/ws/transcribe") as socket:
                hello = socket.receive_json()
                self.assertEqual(hello["type"], "hello")
                self.assertEqual(
                    hello["activationConfig"]["mode"],
                    "legacy",
                    "a client without trigger parameters stays legacy",
                )
                self.assertIn("sessionCapabilities", hello)

                socket.send_text(json.dumps({"type": "start"}))
                for _ in range(3):
                    socket.send_bytes(browser_style_packet())

                socket.send_text(json.dumps({"type": "metrics"}))
                seen = []
                for _ in range(20):
                    message = socket.receive_json()
                    seen.append(message)
                    if message.get("type") == "metrics":
                        break

                kinds = [m.get("type") for m in seen]
                self.assertIn("metrics", kinds)
                errors = [
                    m for m in seen
                    if m.get("type") == "error"
                ]
                self.assertEqual(
                    errors, [], f"the server rejected the browser sequence: {errors}"
                )
                warnings = [
                    m.get("message") for m in seen if m.get("type") == "warning"
                ]
                self.assertEqual(
                    warnings, [], f"the server warned about the audio: {warnings}"
                )

    def test_audio_before_start_is_rejected_as_documented(self):
        """The reason `start` is mandatory - shown, not assumed."""
        with TestClient(self.app) as client:
            with client.websocket_connect("/ws/transcribe") as socket:
                self.assertEqual(socket.receive_json()["type"], "hello")
                socket.send_bytes(browser_style_packet())
                message = _receive_until(socket, {"warning", "error"})
                self.assertEqual(message["type"], "warning")
                self.assertIn("Startbefehl", message["message"])

    def test_a_malformed_packet_without_metadata_is_reported(self):
        with TestClient(self.app) as client:
            with client.websocket_connect("/ws/transcribe") as socket:
                self.assertEqual(socket.receive_json()["type"], "hello")
                socket.send_text(json.dumps({"type": "start"}))
                socket.send_bytes(b"\x01\x02")
                message = _receive_until(socket, {"error"})
                self.assertEqual(message["where"], "audio_packet")


if __name__ == "__main__":
    unittest.main()
