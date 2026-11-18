"""AP-SRV-070 W5-R02-C3 Control 5 - real ASGI / real network degraded probe.

Untracked diagnostic. It deliberately uses NO TestClient: the real VoiceSTT app
is served by a real Uvicorn server on an ephemeral loopback port and driven by a
real WebSocket client (`websockets`, an existing project dependency - nothing new
is installed). Its only job is to answer, outside the in-process test harness:

    while the canonical event store is degraded, does a new /ws/logs connection
    receive log.error(event_store_unavailable) and then close with 1011,
    without hanging?

Usage: python c3_network_probe.py [--watchdog SECONDS]
Exit 0 = PASS, 1 = FAIL, watchdog abort = hang.
"""

from __future__ import annotations

import argparse
import asyncio
import faulthandler
import json
import os
import socket
import sys
import tempfile
import threading
import time

SRC = os.environ.get("C3_SRC", "/home/marco/w5r02c3-native-src")
sys.path.insert(0, SRC)

import uvicorn  # noqa: E402
from websockets.exceptions import ConnectionClosed  # noqa: E402
from websockets.sync.client import connect as ws_connect  # noqa: E402

from api_fastapi_server.server import ServerSettings, create_app  # noqa: E402

sys.path.insert(0, os.path.join(SRC, "tests", "unit"))
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "_c3_testmod", os.path.join(SRC, "tests", "unit", "test_fastapi_server_multi_user.py")
)
_T = importlib.util.module_from_spec(_spec)
sys.modules["_c3_testmod"] = _T
_spec.loader.exec_module(_T)


class ProbeFailure(AssertionError):
    pass


def _check(condition, message):
    if not condition:
        raise ProbeFailure(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--watchdog", type=float, default=30.0)
    args = parser.parse_args()
    faulthandler.enable()
    if args.watchdog > 0:
        faulthandler.dump_traceback_later(args.watchdog, exit=True)

    record = {"probe": "control5_real_network"}
    with tempfile.TemporaryDirectory() as temp_dir:
        app = create_app(
            ServerSettings(
                model_warmup=False,
                data_root_path=temp_dir,
                admin_api_key="test-admin-secret",
                request_log_stdout=False,
                performance_log_stdout=False,
            ),
            scheduler_factory=_T.AutoScheduler,
            recorder_factory=_T.FakeRecorder,
        )

        # Bind an ephemeral loopback port ourselves so the port is known before
        # the server starts and nothing else can claim it.
        probe_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe_socket.bind(("127.0.0.1", 0))
        port = probe_socket.getsockname()[1]
        probe_socket.close()
        record["port"] = port

        config = uvicorn.Config(
            app, host="127.0.0.1", port=port, log_level="warning", lifespan="on",
        )
        server = uvicorn.Server(config)
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
            _check(server.started, "uvicorn did not start within 20s")
            _check(accepting, f"uvicorn is not accepting on 127.0.0.1:{port}")

            events = app.state.voicestt_service.events
            record["store_status_at_start"] = events.store_status()

            # Same real failure mechanism the binding test uses.
            events._store.append = lambda event: (_ for _ in ()).throw(
                OSError("simulated outage")
            )
            _check(
                events.emit("system", "outage.not_committed") is None,
                "the deliberately failed emit must return None",
            )
            _check(
                not events.store_available(),
                f"precondition: store must be degraded, got {events.store_status()}",
            )
            record["store_status_before_connect"] = events.store_status()

            url = f"ws://127.0.0.1:{port}/ws/logs"
            record["url"] = url
            opened_at = time.monotonic()
            with ws_connect(url, open_timeout=10, close_timeout=10) as socket_client:
                first = json.loads(socket_client.recv(timeout=10))
                record["first_frame"] = first
                _check(first["type"] == "log.error", f"type={first.get('type')!r}")
                _check(
                    first["code"] == "event_store_unavailable",
                    f"code={first.get('code')!r}",
                )
                try:
                    unexpected = socket_client.recv(timeout=10)
                except ConnectionClosed as closed:
                    code = closed.rcvd.code if closed.rcvd is not None else None
                    record["close_code"] = code
                    _check(code == 1011, f"close code={code}")
                else:
                    raise ProbeFailure(
                        f"expected the server to close 1011, got {unexpected!r}"
                    )
            record["elapsed_seconds"] = round(time.monotonic() - opened_at, 4)
            record["result"] = "PASS"
            print(json.dumps(record, default=str), flush=True)
            return 0
        except ProbeFailure as exc:
            record["result"] = "FAIL"
            record["error"] = str(exc)
            print(json.dumps(record, default=str), flush=True)
            return 1
        finally:
            server.should_exit = True
            thread.join(timeout=15)
            faulthandler.cancel_dump_traceback_later()


if __name__ == "__main__":
    sys.exit(main())
