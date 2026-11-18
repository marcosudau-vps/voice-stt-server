"""AP-SRV-070 W5-R02-C3 root-cause control matrix.

Untracked diagnostic. Lives under the external Run/Evidence directory and is
copied to /home/marco/c3-diag/ for execution against the native Ubuntu copy of
the binding tree. It never modifies repository source.

Each control is one process invocation:

    python c3_controls.py <control> [--watchdog SECONDS]

Exit code 0 = PASS, 1 = FAIL (assertion/contract violation), and a watchdog
abort (faulthandler dump_traceback_later with exit=True) = hang, which the
shell driver records via the non-zero/abort return code.

Controls
--------
control1b  Instrumented replica of the binding target test's combined
           sequence, recording events.store_status() immediately before the
           second (already-degraded) /ws/logs connect.  Discriminates the
           "store legitimately flipped back to ready" hypothesis from the
           "TestClient/AnyIO lost wakeup" hypothesis.
control1c  control1b with the natural commit-control race amplified.
control1d  Deterministic causal isolation: one successful EventHub.query()
           re-marks a degraded store ready, after which /ws/logs takes the
           normal subscribe path instead of the degraded fast path.
control2b  control2 plus a deterministic startup barrier (join the
           service ready_thread) so no in-flight startup emit can
           re-mark the store ready after the outage patch.
control2   Isolated already-degraded single connection: one app, one
           TestClient, degrade first, verify store_available() is False, then
           open exactly one /ws/logs.
control3   Two sequential complete /ws/logs lifecycles on one TestClient with
           a healthy store (no outage at all).
control4   Degraded connection exercised across a fresh TestClient/lifecycle
           boundary rather than immediately after a previous websocket session.
"""

from __future__ import annotations

import argparse
import faulthandler
import importlib.util
import json
import os
import sys
import tempfile

SRC = os.environ.get("C3_SRC", "/home/marco/w5r02c3-native-src")
sys.path.insert(0, SRC)

from api_fastapi_server.server import ServerSettings, create_app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402


def _load_test_module():
    """Import the real test module for its AutoScheduler/FakeRecorder doubles."""
    path = os.path.join(SRC, "tests", "unit", "test_fastapi_server_multi_user.py")
    spec = importlib.util.spec_from_file_location("_c3_testmod", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_c3_testmod"] = module
    spec.loader.exec_module(module)
    return module


_T = _load_test_module()


class ControlFailure(AssertionError):
    pass


# Populated by each control so the failure path can report the same
# instrumentation the success path reports.
LAST_RECORD: dict = {}


def _check(condition, message):
    if not condition:
        raise ControlFailure(message)


def _settings(temp_dir):
    return ServerSettings(
        model_warmup=False,
        data_root_path=temp_dir,
        admin_api_key="test-admin-secret",
        request_log_stdout=False,
        performance_log_stdout=False,
    )


def _app(temp_dir):
    return create_app(
        _settings(temp_dir),
        scheduler_factory=_T.AutoScheduler,
        recorder_factory=_T.FakeRecorder,
    )


def _settle_startup(app):
    """Join the service's own startup worker.

    `VoiceSTTService.start()` spawns `self.ready_thread`
    (`api_fastapi_server/server.py`, name "VoiceSTTServerReady"), which emits
    `server.ready` and the `models.loaded` performance event. Those emits run
    concurrently with the test body. `EventHub.emit` resolves
    `self._store.append` and only then calls it, so an emit that resolved the
    real method microseconds before the outage patch still succeeds afterwards
    and legitimately re-marks the store `ready` (event_logging.py line 978).
    Joining that thread is a deterministic barrier - no sleep, no polling, no
    retry - and it is the exact background worker involved.
    """
    service = app.state.voicestt_service
    thread = getattr(service, "ready_thread", None)
    if thread is not None:
        thread.join(timeout=30.0)
    return service


def _break_append(events):
    """Same real failure mechanism the binding test uses."""
    original = events._store.append
    events._store.append = lambda event: (_ for _ in ()).throw(
        OSError("simulated outage")
    )
    return original


def _assert_degraded_fast_path(client, note=""):
    """The production contract under test: connect -> log.error -> close 1011."""
    with client.websocket_connect("/ws/logs") as degraded:
        error = degraded.receive_json()
        _check(error["type"] == "log.error", f"{note}type={error.get('type')!r}")
        _check(
            error["code"] == "event_store_unavailable",
            f"{note}code={error.get('code')!r}",
        )
        try:
            degraded.receive_json()
        except WebSocketDisconnect as closed:
            _check(closed.code == 1011, f"{note}close code={closed.code}")
        else:
            raise ControlFailure(f"{note}expected WebSocketDisconnect(1011)")


def _drain_subscribe(logs, after_cursor):
    """log.hello / log.subscribed / zero+ replay log.event / log.replay_completed."""
    _check(logs.receive_json()["type"] == "log.hello", "expected log.hello")
    _check(logs.receive_json()["type"] == "log.subscribed", "expected log.subscribed")
    cursor = after_cursor
    while True:
        message = logs.receive_json()
        if message["type"] == "log.event":
            event_cursor = int(message["event"]["cursor"])
            _check(event_cursor > cursor, "replay cursor must strictly advance")
            cursor = event_cursor
        elif message["type"] == "log.replay_completed":
            return cursor
        else:
            raise ControlFailure(
                f"unexpected message before replay completion: {message['type']!r}"
            )


def _drain_to_error(logs, cursor, events):
    """Zero+ already-committed log.event, then the mandatory log.error."""
    seen = 0
    while True:
        message = logs.receive_json()
        if message["type"] == "log.event":
            seen += 1
            _check(seen <= 50, "too many intervening log.event frames")
            event_cursor = int(message["event"]["cursor"])
            _check(event_cursor > cursor, "intervening cursor must strictly advance")
            _check(
                message["event"]["event"] != "outage.not_committed",
                "the failed event must never be exposed as committed",
            )
            cursor = event_cursor
        elif message["type"] == "log.error":
            return message, cursor, seen
        else:
            raise ControlFailure(f"unexpected message type: {message['type']!r}")


# --------------------------------------------------------------------------
# control1b - instrumented replica of the combined binding scenario
# --------------------------------------------------------------------------
def control1b():
    record = LAST_RECORD
    record["control"] = "control1b"
    with tempfile.TemporaryDirectory() as temp_dir:
        app = _app(temp_dir)
        with TestClient(app) as client:
            events = app.state.voicestt_service.events
            original_append = events._store.append
            record["store_status_at_start"] = events.store_status()

            with client.websocket_connect("/ws/logs") as logs:
                after_cursor = events.latest_cursor()
                logs.send_json({
                    "type": "subscribe",
                    "accessToken": "test-admin-secret",
                    "afterCursor": after_cursor,
                })
                cursor = _drain_subscribe(logs, after_cursor)

                _break_append(events)
                _check(
                    events.emit("system", "outage.not_committed") is None,
                    "the deliberately failed emit must return None",
                )
                record["store_status_after_failed_emit"] = events.store_status()

                error, cursor, intervening = _drain_to_error(logs, cursor, events)
                record["intervening_log_events"] = intervening
                _check(error["type"] == "log.error", "expected log.error")
                _check(
                    error["code"] == "event_store_unavailable",
                    f"code={error.get('code')!r}",
                )
                try:
                    logs.receive_json()
                except WebSocketDisconnect as closed:
                    _check(closed.code == 1011, f"first close code={closed.code}")
                else:
                    raise ControlFailure("expected WebSocketDisconnect(1011)")

            # THE DECISIVE MEASUREMENT: what is the canonical store state at the
            # exact moment the second, "already degraded" connection is opened?
            status = events.store_status()
            record["store_status_before_second_connect"] = status
            record["store_available_before_second_connect"] = events.store_available()
            print(json.dumps(record, default=str), flush=True)

            _assert_degraded_fast_path(client, note="second connection: ")

            events._store.append = original_append
    record["result"] = "PASS"
    print(json.dumps(record, default=str), flush=True)
    return 0


# --------------------------------------------------------------------------
# control2 - isolated already-degraded single connection
# --------------------------------------------------------------------------
def control2():
    with tempfile.TemporaryDirectory() as temp_dir:
        app = _app(temp_dir)
        with TestClient(app) as client:
            events = app.state.voicestt_service.events
            original_append = _break_append(events)
            _check(
                events.emit("system", "outage.not_committed") is None,
                "the deliberately failed emit must return None",
            )
            _check(
                not events.store_available(),
                f"precondition: store must be degraded, got {events.store_status()}",
            )
            _assert_degraded_fast_path(client, note="isolated degraded: ")
            events._store.append = original_append
    print(json.dumps({"control": "control2", "result": "PASS"}), flush=True)
    return 0


# --------------------------------------------------------------------------
# control2b - control2 plus the deterministic startup barrier
# --------------------------------------------------------------------------
def control2b():
    with tempfile.TemporaryDirectory() as temp_dir:
        app = _app(temp_dir)
        with TestClient(app) as client:
            _settle_startup(app)
            events = app.state.voicestt_service.events
            original_append = _break_append(events)
            _check(
                events.emit("system", "outage.not_committed") is None,
                "the deliberately failed emit must return None",
            )
            _check(
                not events.store_available(),
                f"precondition: store must be degraded, got {events.store_status()}",
            )
            _assert_degraded_fast_path(client, note="isolated degraded: ")
            events._store.append = original_append
    print(json.dumps({"control": "control2b", "result": "PASS"}), flush=True)
    return 0


# --------------------------------------------------------------------------
# control3 - two sequential complete /ws/logs lifecycles, healthy store
# --------------------------------------------------------------------------
def control3():
    with tempfile.TemporaryDirectory() as temp_dir:
        app = _app(temp_dir)
        with TestClient(app) as client:
            events = app.state.voicestt_service.events
            for index in (1, 2):
                with client.websocket_connect("/ws/logs") as logs:
                    after_cursor = events.latest_cursor()
                    logs.send_json({
                        "type": "subscribe",
                        "accessToken": "test-admin-secret",
                        "afterCursor": after_cursor,
                    })
                    _drain_subscribe(logs, after_cursor)
                    logs.send_json({"type": "ping"})
                    while True:
                        message = logs.receive_json()
                        if message["type"] == "log.pong":
                            break
                        _check(
                            message["type"] == "log.event",
                            f"socket {index}: unexpected {message['type']!r}",
                        )
            _check(events.store_available(), "store must still be ready")
    print(json.dumps({"control": "control3", "result": "PASS"}), flush=True)
    return 0


# --------------------------------------------------------------------------
# control4 - degraded connection across a fresh TestClient lifecycle boundary
# --------------------------------------------------------------------------
def control4():
    with tempfile.TemporaryDirectory() as temp_dir:
        app = _app(temp_dir)
        # First lifecycle: legitimate live stream + real store outage, exactly
        # as in the combined scenario, then the client context is closed.
        with TestClient(app) as client:
            _settle_startup(app)
            events = app.state.voicestt_service.events
            with client.websocket_connect("/ws/logs") as logs:
                after_cursor = events.latest_cursor()
                logs.send_json({
                    "type": "subscribe",
                    "accessToken": "test-admin-secret",
                    "afterCursor": after_cursor,
                })
                cursor = _drain_subscribe(logs, after_cursor)
                _break_append(events)
                _check(
                    events.emit("system", "outage.not_committed") is None,
                    "the deliberately failed emit must return None",
                )
                _drain_to_error(logs, cursor, events)
                try:
                    logs.receive_json()
                except WebSocketDisconnect as closed:
                    _check(closed.code == 1011, f"first close code={closed.code}")
                else:
                    raise ControlFailure("expected WebSocketDisconnect(1011)")

        # Second, fresh TestClient lifecycle over the same app instance. The
        # degraded precondition is re-established legitimately if the store
        # flipped back to ready in the meantime.
        with TestClient(app) as client:
            events = app.state.voicestt_service.events
            if events.store_available():
                _check(
                    events.emit("system", "outage.still_broken") is None,
                    "re-establishing emit must fail while append is broken",
                )
            _check(
                not events.store_available(),
                f"precondition: store must be degraded, got {events.store_status()}",
            )
            _assert_degraded_fast_path(client, note="fresh-lifecycle degraded: ")
    print(json.dumps({"control": "control4", "result": "PASS"}), flush=True)
    return 0


# --------------------------------------------------------------------------
# control1c - race amplifier for the combined scenario
# --------------------------------------------------------------------------
def control1c():
    """control1b with the natural race deliberately amplified.

    A legitimate event is committed immediately before `append` is broken, so a
    `commit` control is still in flight in the live subscriber's queue when the
    store degrades. This is the exact situation real GitHub Actions hit (run
    34135266167): the live /ws/logs loop then processes that commit control and
    calls `service.events.query(...)` AFTER the degradation.
    """
    record = LAST_RECORD
    record["control"] = "control1c"
    with tempfile.TemporaryDirectory() as temp_dir:
        app = _app(temp_dir)
        with TestClient(app) as client:
            events = app.state.voicestt_service.events
            original_append = events._store.append

            with client.websocket_connect("/ws/logs") as logs:
                after_cursor = events.latest_cursor()
                logs.send_json({
                    "type": "subscribe",
                    "accessToken": "test-admin-secret",
                    "afterCursor": after_cursor,
                })
                cursor = _drain_subscribe(logs, after_cursor)

                # Commit a legitimate event and break the store in the same
                # uninterrupted step, so its commit control is still queued.
                _check(
                    events.emit("system", "outage.pre_commit") is not None,
                    "the pre-outage event must commit normally",
                )
                _break_append(events)
                _check(
                    events.emit("system", "outage.not_committed") is None,
                    "the deliberately failed emit must return None",
                )
                record["store_status_after_failed_emit"] = events.store_status()

                error, cursor, intervening = _drain_to_error(logs, cursor, events)
                record["intervening_log_events"] = intervening
                _check(error["type"] == "log.error", "expected log.error")
                _check(
                    error["code"] == "event_store_unavailable",
                    f"code={error.get('code')!r}",
                )
                try:
                    logs.receive_json()
                except WebSocketDisconnect as closed:
                    _check(closed.code == 1011, f"first close code={closed.code}")
                else:
                    raise ControlFailure("expected WebSocketDisconnect(1011)")

            status = events.store_status()
            record["store_status_before_second_connect"] = status
            record["store_available_before_second_connect"] = events.store_available()
            print(json.dumps(record, default=str), flush=True)

            _assert_degraded_fast_path(client, note="second connection: ")

            events._store.append = original_append
    record["result"] = "PASS"
    print(json.dumps(record, default=str), flush=True)
    return 0


# --------------------------------------------------------------------------
# control1d - deterministic causal isolation of the state flip
# --------------------------------------------------------------------------
def control1d():
    """Deterministic, no race, no hang: isolate the causal step itself.

    Shows that a single successful `EventHub.query(...)` - exactly the call the
    live /ws/logs loop makes on every wake-up - re-marks a degraded store as
    ready, and that a /ws/logs connection opened in that state takes the normal
    subscribe path instead of the degraded fast path. A client that (like the
    binding test) never sends a subscribe frame therefore waits forever.
    """
    record = LAST_RECORD
    record["control"] = "control1d"
    with tempfile.TemporaryDirectory() as temp_dir:
        app = _app(temp_dir)
        with TestClient(app) as client:
            events = app.state.voicestt_service.events
            original_append = _break_append(events)
            _check(
                events.emit("system", "outage.not_committed") is None,
                "the deliberately failed emit must return None",
            )
            record["store_status_after_failed_emit"] = events.store_status()
            _check(not events.store_available(), "store must be degraded here")

            # The exact call api_fastapi_server/server.py makes inside the live
            # /ws/logs loop. `append` is still broken; only reads succeed.
            rows = events.query(limit=1)
            record["query_rows"] = len(rows)
            record["store_status_after_successful_query"] = events.store_status()
            record["store_available_after_successful_query"] = events.store_available()
            _check(
                events.store_available(),
                "a successful query is expected to re-mark the store ready; "
                f"got {events.store_status()}",
            )

            # A new connection in this state must NOT take the degraded fast
            # path. Prove it positively (no hang): send a real subscribe and
            # observe the normal protocol-v2 handshake.
            with client.websocket_connect("/ws/logs") as normal:
                after_cursor = events.latest_cursor()
                normal.send_json({
                    "type": "subscribe",
                    "accessToken": "test-admin-secret",
                    "afterCursor": after_cursor,
                })
                first = normal.receive_json()
                record["first_frame_of_new_connection"] = first["type"]
                _check(
                    first["type"] == "log.hello",
                    "the handler took the degraded fast path unexpectedly: "
                    f"{first!r}",
                )
                _check(
                    normal.receive_json()["type"] == "log.subscribed",
                    "expected log.subscribed",
                )
            events._store.append = original_append
    record["result"] = "PASS"
    print(json.dumps(record, default=str), flush=True)
    return 0


CONTROLS = {
    "control1b": control1b,
    "control1c": control1c,
    "control1d": control1d,
    "control2": control2,
    "control2b": control2b,
    "control3": control3,
    "control4": control4,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("control", choices=sorted(CONTROLS))
    parser.add_argument("--watchdog", type=float, default=20.0)
    args = parser.parse_args()
    faulthandler.enable()
    if args.watchdog > 0:
        faulthandler.dump_traceback_later(args.watchdog, exit=True)
    try:
        return CONTROLS[args.control]()
    except ControlFailure as exc:
        failure = dict(LAST_RECORD)
        failure["control"] = args.control
        failure["result"] = "FAIL"
        failure["error"] = str(exc)
        print(json.dumps(failure, default=str), flush=True)
        return 1
    finally:
        faulthandler.cancel_dump_traceback_later()


if __name__ == "__main__":
    sys.exit(main())
