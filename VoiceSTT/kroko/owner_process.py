"""Native-free launcher/control channel for one ASGI owner at a time.

Control files contain fixed events and a generation only, never settings/keys.
The existing runtime config remains the only persisted operator intent.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time

from .supervisor import OwnerSpec, OwnerSupervisor, SupervisorError, OWNER_GENERATION_ENV

CONTROL_ENV = "VOICESTT_KROKO_OWNER_CONTROL"
FALLBACK_ENV = "VOICESTT_KROKO_COMMUNITY_FALLBACK"
COMMUNITY_ROOT_ENV = "VOICESTT_KROKO_COMMUNITY_PAYLOAD_ROOT"


def managed_owner():
    return bool(os.environ.get(CONTROL_ENV) and os.environ.get(OWNER_GENERATION_ENV))


def publish(event):
    if event not in {"ready", "restart", "community"} or not managed_owner():
        return False
    root = Path(os.environ[CONTROL_ENV])
    payload = {"generation": os.environ[OWNER_GENERATION_ENV], "event": event}
    target = root / (event + ".json")
    # Unique tempfile also makes concurrent requests safe.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=root,
                                     delete=False) as stream:
        json.dump(payload, stream)
        temporary = Path(stream.name)
    os.replace(temporary, target)
    return True


def read_event(root, event, generation):
    try:
        data = json.loads((Path(root) / (event + ".json")).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return data == {"generation": str(generation), "event": event}


def supervise(argv, *, owner_argv=None, start_timeout=180.0, poll_interval=0.05,
              supervisor=None, max_transitions=None, graceful_shutdown=10.0):
    """Run an owner until clean exit, bounded failure, or explicit restart.

    Startup timeout/abnormal exit permits one Community fallback, then uses
    the supervisor's bounded budget. An intentional config restart gets a
    separate fingerprint. No unchanged Pro crash loop is possible.
    Test injection changes the child command, never the production proof path.
    """
    supervisor = supervisor or OwnerSupervisor()
    command = owner_argv or [sys.executable, "-m", "VoiceSTT_server.server", *argv]
    fallback = False
    intent_revision = 0
    transitions = 0
    stopping = False

    def stop_signal(*_args):
        nonlocal stopping
        stopping = True

    previous_handlers = {}
    for name in (signal.SIGINT, signal.SIGTERM):
        try:
            previous_handlers[name] = signal.signal(name, stop_signal)
        except ValueError:  # Test harness may run the launcher on a worker thread.
            pass
    try:
        with tempfile.TemporaryDirectory(prefix="voicestt-owner-") as temporary:
            while not stopping:
                transitions += 1
                if max_transitions is not None and transitions > max_transitions:
                    return 1
                # Every attempt has its own channel; stale files cannot satisfy readiness.
                control = Path(temporary) / str(transitions)
                control.mkdir()
                env = {CONTROL_ENV: str(control), FALLBACK_ENV: "1" if fallback else "0"}
                if fallback and os.environ.get("VOICESTT_KROKO_PAYLOAD_ROOT"):
                    free_root = os.environ.get(COMMUNITY_ROOT_ENV)
                    if not free_root:
                        # Never silently reuse a private Pro root as Community.
                        return 1
                    env["VOICESTT_KROKO_PAYLOAD_ROOT"] = free_root

                def ready(deadline):
                    generation = supervisor.current_generation
                    while time.monotonic() < deadline and not stopping:
                        if read_event(control, "ready", generation):
                            return True
                        if read_event(control, "community", generation):
                            return False
                        # Detect native exit during startup without waiting out the deadline.
                        if not supervisor.is_current(generation):
                            return False
                        time.sleep(poll_interval)
                    return False

                try:
                    handle = supervisor.start(
                        OwnerSpec(command, env=env, start_deadline_seconds=start_timeout,
                                  graceful_shutdown_seconds=graceful_shutdown),
                        config={"communityFallback": fallback, "intentRevision": intent_revision},
                        wait_ready=ready,
                    )
                except SupervisorError:
                    if fallback:
                        return 1
                    fallback = True
                    continue
                action = None
                while not stopping and handle.process.poll() is None:
                    for event in ("community", "restart"):
                        if read_event(control, event, handle.generation):
                            action = event
                            break
                    if action:
                        break
                    time.sleep(poll_interval)
                if stopping:
                    return 0
                if action:
                    # The child asks Uvicorn to drain HTTP/WS and exit. Confirm
                    # that exit before a hard-stop fallback or the next spawn.
                    import subprocess
                    try:
                        handle.process.wait(timeout=graceful_shutdown)
                    except subprocess.TimeoutExpired:
                        pass
                if action == "restart":
                    supervisor.stop()
                    intent_revision += 1
                    fallback = False
                    continue
                if action == "community" or handle.process.returncode != 0:
                    supervisor.stop()
                    if fallback:
                        return 1
                    fallback = True
                    continue
                return 0
    finally:
        supervisor.stop()
        for name, handler in previous_handlers.items():
            signal.signal(name, handler)
