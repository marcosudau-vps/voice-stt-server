"""AP-SRV-070 W4C: isolated, disposable public Docker/Compose smoke.

Not part of the product - a throwaway evidence-gathering script for this run.
Uses `docker compose -p <isolated project>` directly against the repo's
public docker-compose.yml, with a fully isolated temp data/model root and a
free local high port. Never touches tools/compose.py or config.yaml (which
carry Marco's private candidate paths), and never assumes any existing
deployment, reverse proxy, or private network.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path

import websockets

REPO_ROOT = Path(r"P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w4c")
PROJECT = "voicestt-w4c-smoke"
PORT = 18020
ADMIN_KEY = "w4c-smoke-admin-key-not-a-secret"


def run(cmd, **kwargs):
    print("+ " + " ".join(str(c) for c in cmd))
    result = subprocess.run(cmd, cwd=str(REPO_ROOT), text=True, encoding="utf-8",
                             errors="replace", capture_output=True, **kwargs)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result


def compose(*args, env):
    return run(["docker", "compose", "-p", PROJECT, "-f", "docker-compose.yml", *args], env=env)


def http_get(path, timeout=5):
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


async def ws_handshake():
    hello = {
        "type": "hello",
        "supportedProtocolVersions": [2],
        "clientVersion": "w4c-smoke-probe",
        "clientCommit": "0" * 40,
        "clientRunId": str(uuid.uuid4()),
        "requestedSession": {"trigger": {"manual": True, "wakeWord": False}, "wakeWordIds": []},
        "runtimeSuppression": {"manual": False, "wakeWord": False},
    }
    async with websockets.connect(f"ws://127.0.0.1:{PORT}/ws/v2", open_timeout=10) as ws:
        await ws.send(json.dumps(hello))
        raw = await asyncio.wait_for(ws.recv(), timeout=10)
        return json.loads(raw)


def container_id():
    result = run(["docker", "compose", "-p", PROJECT, "-f", "docker-compose.yml", "ps", "-q", "server"],
                 env=os.environ)
    return result.stdout.strip().splitlines()[0]


def docker_inspect(cid, fmt):
    result = run(["docker", "inspect", "--format", fmt, cid], env=os.environ)
    return result.stdout.strip()


def main():
    image = sys.argv[1] if len(sys.argv) > 1 else "voice-stt-server:2.0.0"
    tmp_root = Path(tempfile.gettempdir()) / "voicestt-w4c-smoke"
    if tmp_root.exists():
        import shutil
        shutil.rmtree(tmp_root)
    data_path = tmp_root / "data"
    fw_path = tmp_root / "models" / "faster-whisper"
    kroko_path = tmp_root / "models" / "kroko"
    for p in (data_path, fw_path, kroko_path):
        p.mkdir(parents=True)

    env = os.environ.copy()
    env.update({
        "VOICESTT_IMAGE": image,
        "VOICESTT_PORT": str(PORT),
        "VOICESTT_DATA_PATH": str(data_path),
        "VOICESTT_FASTER_WHISPER_HOST_PATH": str(fw_path),
        "VOICESTT_KROKO_HOST_PATH": str(kroko_path),
        "VOICESTT_ADMIN_API_KEY": ADMIN_KEY,
        "VOICESTT_ENV_FILE": str(tmp_root / "does-not-exist.env"),
    })

    report = {"image": image, "project": PROJECT, "port": PORT, "tempRoot": str(tmp_root)}

    try:
        up = compose("up", "-d", env=env)
        report["composeUp"] = {"returncode": up.returncode}

        cid = container_id()
        report["containerId"] = cid

        # wait for health
        deadline = time.time() + 90
        health_status = None
        while time.time() < deadline:
            health_status = docker_inspect(cid, "{{.State.Health.Status}}")
            if health_status == "healthy":
                break
            time.sleep(2)
        report["dockerHealthStatus"] = health_status
        report["restartCountAfterStart"] = docker_inspect(cid, "{{.RestartCount}}")

        status, health_body = http_get("/health")
        report["healthHttpStatus"] = status
        report["healthBody"] = health_body

        report["wsV2Handshake"] = asyncio.run(ws_handshake())

        mgmt_req = urllib.request.Request(
            f"http://127.0.0.1:{PORT}/api/models/management",
            headers={"X-Voicestt-Admin-Key": ADMIN_KEY},
        )
        try:
            with urllib.request.urlopen(mgmt_req, timeout=5) as resp:
                report["modelManagement"] = {"status": resp.status, "body": json.loads(resp.read())}
        except Exception as exc:  # noqa: BLE001
            report["modelManagement"] = {"error": str(exc)}

        wake_probe = run(["docker", "exec", cid, "/opt/venv/bin/python", "-c",
                           "import pathlib, VoiceSTT, json; "
                           "p = pathlib.Path(VoiceSTT.__file__).parent / 'assets' / 'wakeword_models'; "
                           "print(json.dumps(sorted(x.name for x in p.glob('*.onnx'))))"], env=env)
        report["wakeAssetProbe"] = json.loads(wake_probe.stdout.strip() or "[]")

        # persistence: write a marker, recreate, verify it survives
        marker = f"w4c-smoke-{uuid.uuid4().hex}"
        run(["docker", "exec", cid, "sh", "-c", f"echo {marker} > /var/lib/voicestt/w4c-marker.txt"], env=env)
        report["markerWritten"] = marker

        compose("down", env=env)
        report["hostMarkerExistsAfterDown"] = (data_path / "w4c-marker.txt").is_file()

        up2 = compose("up", "-d", env=env)
        report["composeUpAfterRecreate"] = {"returncode": up2.returncode}
        cid2 = container_id()
        report["containerIdAfterRecreate"] = cid2
        report["recreatedNewContainer"] = cid2 != cid

        deadline = time.time() + 90
        health_status2 = None
        while time.time() < deadline:
            health_status2 = docker_inspect(cid2, "{{.State.Health.Status}}")
            if health_status2 == "healthy":
                break
            time.sleep(2)
        report["dockerHealthStatusAfterRecreate"] = health_status2

        marker_check = run(["docker", "exec", cid2, "cat", "/var/lib/voicestt/w4c-marker.txt"], env=env)
        report["markerAfterRecreate"] = marker_check.stdout.strip()
        report["markerPersisted"] = marker in marker_check.stdout

        status2, health_body2 = http_get("/health")
        report["healthAfterRecreate"] = {"status": status2, "ready": health_body2.get("ready"), "sttReady": health_body2.get("sttReady")}

        # shutdown: SIGTERM via `docker compose stop`, measure clean exit
        stop_started = time.time()
        stop_result = compose("stop", "-t", "15", env=env)
        stop_elapsed = time.time() - stop_started
        report["stopElapsedSeconds"] = stop_elapsed
        report["stopReturnCode"] = stop_result.returncode
        report["finishedAt"] = docker_inspect(cid2, "{{.State.FinishedAt}}")
        report["exitCodeAfterStop"] = docker_inspect(cid2, "{{.State.ExitCode}}")
        report["oomKilled"] = docker_inspect(cid2, "{{.State.OOMKilled}}")

        logs_tail = run(["docker", "logs", "--tail", "40", cid2], env=env)
        report["logsTailAfterStop"] = logs_tail.stdout[-4000:]

    finally:
        compose("down", "-v", env=env)

    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    Path(tempfile.gettempdir(), "voicestt-w4c-smoke-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
