"""AP-SRV-070 W5-R02-C3-R1 — real-network mixed-capability probe.

Untracked diagnostic. No TestClient: the real VoiceSTT app is served by a real
Uvicorn server on an ephemeral loopback port and driven by a real WebSocket
client (`websockets`) and real HTTP requests (`httpx`). Both are already project
dependencies; nothing is installed for this probe.

It establishes the mixed-capability condition through real EventHub/store
operations - `_store.append` raises persistently, reads keep working, and a real
canonical `EventHub.query()` is performed in between - and then records what the
server tells an actual client.

    python r1_network_mixed_probe.py [--expect ready|degraded] [--watchdog N]

With --expect the probe additionally asserts the externally visible /ws/logs
contract and exits 1 on violation, so it can be used as a stress campaign.
Without --expect it only reports what it observed.
"""

from __future__ import annotations

import argparse
import faulthandler
import json
import os
import socket
import sys
import tempfile
import threading
import time

SRC = os.environ.get("R1_SRC", "/home/marco/w5r02c3r1-native-src")
sys.path.insert(0, SRC)

import httpx  # noqa: E402
import uvicorn  # noqa: E402
from websockets.exceptions import ConnectionClosed  # noqa: E402
from websockets.sync.client import connect as ws_connect  # noqa: E402

from api_fastapi_server.server import ServerSettings, create_app  # noqa: E402

import tests.unit.test_fastapi_server_multi_user as _mu_tests  # noqa: E402


class ProbeFailure(AssertionError):
    pass


def _check(condition, message):
    if not condition:
        raise ProbeFailure(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expect", choices=["ready", "degraded"], default=None)
    parser.add_argument("--watchdog", type=float, default=45.0)
    args = parser.parse_args()
    faulthandler.enable()
    if args.watchdog > 0:
        faulthandler.dump_traceback_later(args.watchdog, exit=True)

    record = {"probe": "r1_network_mixed_capability"}
    with tempfile.TemporaryDirectory() as temp_dir:
        app = create_app(
            ServerSettings(
                model_warmup=False,
                data_root_path=temp_dir,
                admin_api_key="test-admin-secret",
                request_log_stdout=False,
                performance_log_stdout=False,
            ),
            scheduler_factory=_mu_tests.AutoScheduler,
            recorder_factory=_mu_tests.FakeRecorder,
        )
        probe_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe_socket.bind(("127.0.0.1", 0))
        port = probe_socket.getsockname()[1]
        probe_socket.close()
        record["port"] = port

        server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=port, log_level="warning", lifespan="on",
        ))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 20.0
            accepting = False
            while time.monotonic() < deadline:
                if server.started:
                    try:
                        with socket.create_connection(("127.0.0.1", port), 1.0):
                            accepting = True
                        break
                    except OSError:
                        pass
                time.sleep(0.02)
            _check(accepting, f"uvicorn is not accepting on 127.0.0.1:{port}")

            service = app.state.voicestt_service
            service.ready_thread.join(timeout=30)
            events = service.events
            record["state_before_outage"] = events.store_status()["state"]

            # WRITE breaks persistently; READ keeps working for the whole window.
            def always_fail(event):
                raise OSError("simulated persistent write outage")
            events._store.append = always_fail

            _check(
                events.emit("system", "outage.first_write") is None,
                "the first write must fail",
            )
            record["state_after_write_failure"] = events.store_status()["state"]

            # A real canonical read through the hub, exactly as the live
            # /ws/logs loop and the history endpoint perform it.
            record["query_row_count"] = len(events.query(limit=1000))
            record["state_after_successful_query"] = events.store_status()["state"]
            record["store_available_after_query"] = events.store_available()

            base = f"http://127.0.0.1:{port}"
            admin = {"X-VoiceSTT-Admin-Key": "test-admin-secret"}
            with httpx.Client(timeout=10.0) as http:
                record["health_ok"] = http.get(f"{base}/health").json()["ok"]
                record["history_status"] = http.get(
                    f"{base}/api/logs/events", headers=admin
                ).status_code

            # The externally visible /ws/logs contract in this exact state.
            frames = []
            close_code = None
            try:
                with ws_connect(
                    f"ws://127.0.0.1:{port}/ws/logs",
                    open_timeout=10, close_timeout=10,
                ) as socket_client:
                    # A degraded store must push log.error unprompted. A store
                    # that considers itself ready sends nothing and waits for a
                    # subscribe frame, so a bounded first-frame wait is what
                    # distinguishes the two - it is a measurement, not a retry.
                    try:
                        first = json.loads(socket_client.recv(timeout=3))
                    except TimeoutError:
                        first = {"type": "__silence__"}
                    frames.append(first.get("type"))
                    record["first_frame"] = first
                    if first.get("type") == "log.error":
                        try:
                            socket_client.recv(timeout=10)
                        except ConnectionClosed as closed:
                            close_code = (
                                closed.rcvd.code if closed.rcvd else None
                            )
                    else:
                        # The server believes it is healthy and is waiting for
                        # a subscribe frame; complete the handshake so the probe
                        # records what such a client actually receives.
                        socket_client.send(json.dumps({
                            "type": "subscribe",
                            "accessToken": "test-admin-secret",
                            "afterCursor": 0,
                        }))
                        for _ in range(3):
                            frames.append(
                                json.loads(socket_client.recv(timeout=10)).get("type")
                            )
            except ConnectionClosed as closed:
                close_code = closed.rcvd.code if closed.rcvd else None
            record["ws_frames"] = frames
            record["ws_close_code"] = close_code

            _check(
                events.emit("system", "outage.second_write") is None,
                "the second write must still fail",
            )
            record["state_after_second_write_failure"] = (
                events.store_status()["state"]
            )
            record["second_failed_event_absent"] = "outage.second_write" not in {
                row["event"] for row in events._store.query(limit=1000)
            }

            if args.expect == "degraded":
                _check(
                    record["state_after_successful_query"] == "degraded",
                    "a successful read must not clear an unresolved write "
                    f"failure; got {record['state_after_successful_query']!r}",
                )
                _check(
                    frames[:1] == ["log.error"],
                    f"expected log.error as the first frame, got {frames!r}",
                )
                _check(
                    record["first_frame"].get("code") == "event_store_unavailable",
                    f"expected event_store_unavailable, got {record['first_frame']!r}",
                )
                _check(close_code == 1011, f"expected close 1011, got {close_code}")
                _check(
                    record["health_ok"] is False,
                    "health must not report ok while canonical writes fail",
                )
            elif args.expect == "ready":
                _check(
                    record["state_after_successful_query"] == "ready",
                    f"expected ready, got {record['state_after_successful_query']!r}",
                )

            record["result"] = "PASS"
            print(json.dumps(record, indent=2, default=str), flush=True)
            return 0
        except ProbeFailure as exc:
            record["result"] = "FAIL"
            record["error"] = str(exc)
            print(json.dumps(record, indent=2, default=str), flush=True)
            return 1
        finally:
            server.should_exit = True
            thread.join(timeout=15)
            faulthandler.cancel_dump_traceback_later()


if __name__ == "__main__":
    sys.exit(main())
