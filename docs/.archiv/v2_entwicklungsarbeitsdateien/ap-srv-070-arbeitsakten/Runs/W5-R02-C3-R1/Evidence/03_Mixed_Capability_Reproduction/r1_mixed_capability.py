"""AP-SRV-070 W5-R02-C3-R1 — mixed-capability semantic reproduction.

Untracked diagnostic. Establishes the exact condition

    READ:  works
    WRITE: persistently fails

on the real StructuredEventHub / real SQLite store, and records the nine
observations required by prompt Section 10. The write failure is induced with
the same mechanism the existing tests use (`_store.append` raises OSError) and
is kept active for the whole observation window - it is never toggled off and
`_store_state` is never written directly.

    python r1_mixed_capability.py hub      # StructuredEventHub level
    python r1_mixed_capability.py app      # full app + TestClient, incl. /ws/logs
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

SRC = os.environ.get("R1_SRC", "/home/marco/w5r02c3r1-native-src")
sys.path.insert(0, SRC)

from VoiceSTT_server.event_logging import StructuredEventHub  # noqa: E402


# The test modules are a real package (tests/__init__.py, tests/unit/__init__.py),
# so import them normally - they use relative imports internally.
import tests.unit.test_server_operations as _ops_tests  # noqa: E402
import tests.unit.test_fastapi_server_multi_user as _mu_tests  # noqa: E402

# LogSettings is the test-suite's own settings shape for StructuredEventHub;
# reuse the real one so this probe constructs the hub exactly the way the
# existing store-failure tests do.
LogSettings = _ops_tests.LogSettings


def _persistent_write_failure(store):
    """The same mechanism the existing unit tests use, but never lifted."""
    def always_fail(event):
        raise OSError("simulated persistent write outage")
    store.append = always_fail


# ---------------------------------------------------------------------------
# Hub level
# ---------------------------------------------------------------------------
def probe_hub():
    record = {"probe": "mixed_capability_hub", "observations": {}}
    obs = record["observations"]
    with tempfile.TemporaryDirectory() as temp_dir:
        settings = LogSettings(
            request_log_stdout=False,
            request_log_path=os.path.join(temp_dir, "audit"),
            performance_logging_enabled=False,
            system_event_logging_enabled=True,
            system_event_log_path=os.path.join(temp_dir, "system"),
            event_store_enabled=True,
            event_store_path=os.path.join(temp_dir, "events.sqlite3"),
        )
        hub = StructuredEventHub(settings)
        controls = []
        subscription = hub.subscribe(controls.append)

        # A genuinely committed baseline event, so reads have something to find.
        baseline_id = hub.emit("audit", "baseline.committed", sessionId="a")
        hub.flush()
        obs["0_baseline_event_committed"] = baseline_id is not None
        obs["0_state_before_outage"] = hub.store_status()["state"]
        baseline_cursor = hub.latest_cursor()
        obs["0_baseline_cursor"] = baseline_cursor

        # WRITE breaks, permanently, for the whole rest of this probe.
        _persistent_write_failure(hub._store)

        # (1) a generated event cannot be committed
        first_failed_id = hub.emit("audit", "outage.first_write", sessionId="a")
        hub.flush()
        obs["1_first_write_returns_none"] = first_failed_id is None

        # (2) the attempted event gets no cursor and is absent from history
        history = hub.query(limit=1000)
        obs["2_cursor_unchanged"] = hub.latest_cursor() == baseline_cursor
        obs["2_failed_event_absent_from_history"] = "outage.first_write" not in {
            item["event"] for item in history
        }

        # (3) state immediately after the write failure
        obs["3_state_after_write_failure"] = hub.store_status()["state"]
        obs["3_store_available_after_write_failure"] = hub.store_available()

        # (4) a canonical query succeeds while writes are broken
        read_rows = hub.query(limit=1000)
        obs["4_query_succeeded"] = True
        obs["4_query_row_count"] = len(read_rows)

        # (5) state immediately after that successful query
        obs["5_state_after_successful_query"] = hub.store_status()["state"]
        obs["5_store_available_after_successful_query"] = hub.store_available()

        # (6) a second generated event still cannot be committed
        second_failed_id = hub.emit("audit", "outage.second_write", sessionId="a")
        hub.flush()
        obs["6_second_write_returns_none"] = second_failed_id is None
        obs["6_second_failed_event_absent"] = "outage.second_write" not in {
            item["event"] for item in hub.query(limit=1000)
        }

        # (7) state after that second write failure
        obs["7_state_after_second_write_failure"] = hub.store_status()["state"]

        # Control frames the subscriber actually saw during the window.
        obs["8_control_frames"] = [
            item.get("_logControl")
            for item in controls
            if item.get("_logControl")
        ]

        hub.unsubscribe(subscription)
        hub.close()
    print(json.dumps(record, indent=2, default=str), flush=True)
    return 0


# ---------------------------------------------------------------------------
# Application level (TestClient), including /ws/logs and the HTTP surfaces
# ---------------------------------------------------------------------------
def probe_app():
    from api_fastapi_server.server import ServerSettings, create_app
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    T = _mu_tests

    record = {"probe": "mixed_capability_app", "observations": {}}
    obs = record["observations"]
    with tempfile.TemporaryDirectory() as temp_dir:
        app = create_app(
            ServerSettings(
                model_warmup=False,
                data_root_path=temp_dir,
                admin_api_key="test-admin-secret",
                request_log_stdout=False,
                performance_log_stdout=False,
            ),
            scheduler_factory=T.AutoScheduler,
            recorder_factory=T.FakeRecorder,
        )
        with TestClient(app) as client:
            service = app.state.voicestt_service
            service.ready_thread.join(timeout=30)
            events = service.events

            obs["0_state_before_outage"] = events.store_status()["state"]
            obs["0_health_ok_before"] = client.get("/health").json()["ok"]

            _persistent_write_failure(events._store)

            obs["1_first_write_returns_none"] = (
                events.emit("system", "outage.first_write") is None
            )
            obs["2_failed_event_absent_from_history"] = (
                "outage.first_write"
                not in {item["event"] for item in events._store.query(limit=1000)}
            )
            obs["3_state_after_write_failure"] = events.store_status()["state"]

            obs["4_query_succeeded"] = len(events.query(limit=1000)) >= 0
            obs["5_state_after_successful_query"] = events.store_status()["state"]
            obs["5_store_available_after_successful_query"] = (
                events.store_available()
            )

            # (8) /ws/logs behaviour in exactly this mixed-capability window
            try:
                with client.websocket_connect("/ws/logs") as socket_client:
                    socket_client.send_json({
                        "type": "subscribe",
                        "accessToken": "test-admin-secret",
                        "afterCursor": 0,
                    })
                    frames = []
                    for _ in range(3):
                        try:
                            frames.append(socket_client.receive_json()["type"])
                        except WebSocketDisconnect as closed:
                            frames.append(f"close:{closed.code}")
                            break
                    obs["8_ws_logs_frames_in_mixed_state"] = frames
            except WebSocketDisconnect as closed:
                obs["8_ws_logs_frames_in_mixed_state"] = [f"close:{closed.code}"]

            # (6)/(7) writes still broken afterwards
            obs["6_second_write_returns_none"] = (
                events.emit("system", "outage.second_write") is None
            )
            obs["7_state_after_second_write_failure"] = (
                events.store_status()["state"]
            )

            # (9) health / log-access surfaces exposing the same state
            health = client.get("/health").json()
            obs["9_health_ok_in_mixed_state"] = health["ok"]
            obs["9_log_access_available_in_mixed_state"] = bool(
                service.create_log_access("probe-session")["available"]
            )
            history = client.get(
                "/api/logs/events",
                headers={"X-VoiceSTT-Admin-Key": "test-admin-secret"},
            )
            obs["9_history_status_in_mixed_state"] = history.status_code

    print(json.dumps(record, indent=2, default=str), flush=True)
    return 0


PROBES = {"hub": probe_hub, "app": probe_app}

if __name__ == "__main__":
    sys.exit(PROBES[sys.argv[1]]())
