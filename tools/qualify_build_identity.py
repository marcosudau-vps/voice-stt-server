"""Targeted RC identity gates; no publishing, promotion, tags or model downloads."""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv
import zipfile

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from VoiceSTT._build_identity import BuildIdentity, IdentityError  # noqa: E402
from VoiceSTT._version import resolve_version  # noqa: E402
from build_identity_support import capture_identity, match_identity, wheel_identity  # noqa: E402
from tools.build_distribution import distribution_name_for  # noqa: E402


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def validate_distribution(path: Path, source: BuildIdentity, variant: str,
                          *, kroko_sha256: str, fingerprint: str) -> BuildIdentity:
    identity = wheel_identity(path)
    identity.require_complete()
    match_identity(identity, replace(
        source, distributionName=distribution_name_for(variant), krokoVariant=variant
    ))
    try:
        with zipfile.ZipFile(path) as archive:
            embedded = json.loads(archive.read("voice_stt_server/_embedded_kroko.json"))
            names = archive.namelist()
        if (
            names.count("voice_stt_server/_embedded_kroko.json") != 1
            or type(embedded.get("schemaVersion")) is not int
            or embedded["schemaVersion"] != 1
            or embedded.get("distribution") != identity.distributionName
            or embedded.get("variant") != variant
            or embedded.get("productVersion") != identity.productVersion
            or embedded.get("kroko", {}).get("wheelSha256") != kroko_sha256
            or embedded.get("kroko", {}).get("fingerprint") != fingerprint
            or not any(name.startswith("kroko_onnx/") for name in names)
        ):
            raise IdentityError("distribution and qualified Kroko provenance conflict")
    except (KeyError, ValueError, AttributeError, OSError, zipfile.BadZipFile):
        raise IdentityError("unreadable or conflicting distribution provenance") from None
    return identity


INSTALLED_CHECK = r"""
import contextlib, json, socket, sys, tempfile, threading, time
import httpx, uvicorn
from websockets.sync.client import connect
from VoiceSTT._build_identity import validated_build_identity
from VoiceSTT.kroko.artifacts import verify_installed_runtime
from api_fastapi_server.server import ServerSettings, create_app

@contextlib.contextmanager
def running_app(app):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=port, log_level="critical", access_log=False,
        ))
        worker = threading.Thread(
            target=lambda: server.run(sockets=[listener]),
            name="identity-qualification-http", daemon=True,
        )
        worker.start()
        try:
            deadline = time.monotonic() + 30
            while not server.started and worker.is_alive() and time.monotonic() < deadline:
                time.sleep(.01)
            assert server.started and worker.is_alive(), "qualification server did not start"
            with httpx.Client(
                base_url=f"http://127.0.0.1:{port}", timeout=10, trust_env=False,
            ) as client:
                yield client, f"ws://127.0.0.1:{port}/ws/v2"
        finally:
            server.should_exit = True
            worker.join(30)
            assert not worker.is_alive(), "qualification server did not stop"

expected = json.loads(sys.argv[1])
variant = sys.argv[2] if len(sys.argv) > 2 else expected["krokoVariant"]
identity = validated_build_identity()
assert identity is not None
identity.require_complete()
assert json.loads(identity.to_json()) == expected
runtime = verify_installed_runtime(variant)
assert runtime["ok"], "native Kroko import/variant qualification failed"
with tempfile.TemporaryDirectory() as data:
    settings = ServerSettings(
        model_warmup=False, data_root_path=data, stt_auto_download_enabled=False,
        event_store_enabled=False, log_live_enabled=False,
        request_logging_enabled=False, system_event_logging_enabled=False,
        performance_logging_enabled=False, performance_log_mirror_enabled=False,
        transcription_logging_enabled=False,
    )
    app = create_app(settings)
    with running_app(app) as (client, ws_url):
        response = client.get("/api/v2/info")
        assert response.status_code == 200
        info = response.json()
        assert response.headers["cache-control"] == "no-store"
        assert info["identityStatus"] == "complete"
        assert info["serverVersion"] == expected["productVersion"]
        assert info["serverCommit"] == expected["sourceCommit"]
        assert info["distribution"]["name"] == expected["distributionName"]
        assert info["runtime"]["krokoVariant"] == variant
        assert info["distribution"]["packageVersion"] == expected["packageVersion"]
        assert info["build"] == {
            "sourceTree": expected["sourceTree"], "sourceDirty": False,
            "sourceDate": expected["sourceDate"],
        }
        assert info["serverInstanceId"] == app.state.voicestt_service.events.server_instance_id
        assert client.get("/api/v2/info").json() == info
        for path in ("/api/v2/settings/schema", "/api/v2/settings/server"):
            response = client.get(path)
            assert response.status_code == 200
            payload = response.json()
            assert payload["serverVersion"] == info["serverVersion"]
            assert payload["serverCommit"] == info["serverCommit"]
        assert client.get("/openapi.json").json()["info"]["version"] == info["serverVersion"]
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["ready"] is False
        with socket.create_connection(("127.0.0.1", client.base_url.port), timeout=10) as connection, \
                connect(ws_url, sock=connection, open_timeout=10, close_timeout=10) as ws:
            ws.send(json.dumps({
                "type": "hello", "supportedProtocolVersions": [999],
                "clientVersion": "2.0.0", "clientCommit": "unknown",
                "clientRunId": "10000000-0000-4000-8000-000000000001",
                "requestedSession": {"trigger": {"manual": True, "wakeWord": False}, "wakeWordIds": []},
                "runtimeSuppression": {"manual": False, "wakeWord": False},
            }))
            refusal = json.loads(ws.recv(timeout=10))
            assert refusal["type"] == "protocol.incompatible"
            assert refusal["serverVersion"] == info["serverVersion"]
            assert refusal["serverCommit"] == info["serverCommit"]
print("IDENTITY_QUALIFICATION=" + json.dumps({"info": info, "nativeImport": runtime["ok"]}))
"""


def qualification_evidence(stdout: str) -> dict:
    markers = [line.partition("=")[2] for line in stdout.splitlines()
               if line.startswith("IDENTITY_QUALIFICATION=")]
    if len(markers) != 1:
        raise IdentityError("installed qualification must produce exactly one evidence record")
    try:
        evidence = json.loads(markers[0])
    except ValueError:
        raise IdentityError("unreadable installed qualification evidence") from None
    if (
        not isinstance(evidence, dict)
        or evidence.get("nativeImport") is not True
        or not isinstance(evidence.get("info"), dict)
    ):
        raise IdentityError("installed qualification lacks native HTTP evidence")
    return evidence


def qualify_installed_wheel(path: Path, identity: BuildIdentity) -> dict:
    """A real fresh installation, outside the checkout, on the native host."""
    with tempfile.TemporaryDirectory(prefix="voicestt-identity-") as temporary:
        root = Path(temporary)
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        env = dict(os.environ)
        for key in ("PYTHONPATH", "VOICESTT_BUILD_VERSION", "VOICESTT_SERVER_COMMIT",
                    "VOICESTT_DISTRIBUTION_VARIANT"):
            env.pop(key, None)
        env.update(VOICESTT_OFFLINE_MODELS="1", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
        for args in (
            ["-m", "pip", "install", str(path.resolve())],
            ["-m", "pip", "check"],
            ["-I", "-c", INSTALLED_CHECK, identity.to_json()],
        ):
            result = subprocess.run(
                [str(python), *args], cwd=root, env=env, text=True,
                encoding="utf-8", errors="replace", capture_output=True,
            )
            print(result.stdout)
            if result.returncode:
                print(result.stderr, file=sys.stderr)
                raise IdentityError("installed wheel qualification failed; see qualification log")
        return qualification_evidence(result.stdout)


def qualify_candidate(directory: Path, *, platform: str | None = None,
                      install: bool = False, check_reports: bool = False) -> dict:
    source = capture_identity(REPO_ROOT, resolve_version(), "voicestt")
    source.require_complete()
    if install and platform is None:
        raise IdentityError("native installation requires an explicit platform")
    entries = []
    seen = set()
    for manifest in sorted(directory.glob("distribution-*.json")):
        record = json.loads(manifest.read_text(encoding="utf-8"))
        target = record["platformTag"]
        if platform and (("win" if target.startswith("win") else "linux") !=
                         ("win" if platform == "windows" else "linux")):
            continue
        variant = record["variant"]
        if (variant, target) in seen:
            raise IdentityError("duplicate candidate distribution/platform")
        seen.add((variant, target))
        filename = record["filename"]
        if Path(filename).name != filename:
            raise IdentityError("candidate wheel filename must be a basename")
        wheel = directory / "dist" / filename
        if sha256(wheel) != record["sha256"]:
            raise IdentityError("candidate wheel hash differs from distribution manifest")
        kroko = record["embedded"]["kroko"]
        identity = validate_distribution(
            wheel, source, variant, kroko_sha256=kroko["wheelSha256"],
            fingerprint=kroko["fingerprint"],
        )
        entry = {"filename": filename, "sha256": record["sha256"],
                 "sourceCommit": source.sourceCommit, "sourceTree": source.sourceTree,
                 "variant": variant, "platformTag": target,
                 "krokoFingerprint": kroko["fingerprint"],
                 "krokoArtifactSha256": kroko["wheelSha256"]}
        if install:
            entry["installed"] = qualify_installed_wheel(wheel, identity)
        entries.append(entry)
    expected = {("free", "win_amd64"), ("pro", "win_amd64")} if platform == "windows" else {
        ("free", "linux_x86_64"), ("pro", "linux_x86_64")
    }
    if platform is None:
        expected |= {("free", "win_amd64"), ("pro", "win_amd64")}
    if seen != expected:
        raise IdentityError("candidate identity gate lacks the required variant/platform wheels")
    if check_reports:
        proven = {}
        expected_entries = {entry["filename"]: entry for entry in entries}
        for target in ("linux", "windows"):
            report = json.loads((directory / f"identity-qualification-{target}.json").read_text(encoding="utf-8"))
            if type(report.get("schemaVersion")) is not int or report["schemaVersion"] != 1:
                raise IdentityError("unsupported installed qualification report schema")
            reported = set()
            for entry in report["wheels"]:
                expected_entry = expected_entries.get(entry["filename"])
                if (
                    expected_entry is None
                    or any(entry.get(key) != value for key, value in expected_entry.items())
                    or ("windows" if entry["platformTag"] == "win_amd64" else "linux") != target
                ):
                    raise IdentityError("installed qualification report conflicts with candidate wheel")
                reported.add(entry["filename"])
                info = entry["installed"]["info"]
                expected_name = distribution_name_for(entry["variant"])
                if (
                    entry["sourceCommit"] != source.sourceCommit
                    or entry["sourceTree"] != source.sourceTree
                    or entry["installed"]["nativeImport"] is not True
                    or info["serverCommit"] != source.sourceCommit
                    or info["identityStatus"] != "complete"
                    or info["serverVersion"] != source.productVersion
                    or info["distribution"] != {
                        "name": expected_name, "packageVersion": source.packageVersion
                    }
                    or info["runtime"] != {"krokoVariant": entry["variant"]}
                    or info["build"] != {
                        "sourceTree": source.sourceTree, "sourceDirty": False,
                        "sourceDate": source.sourceDate,
                    }
                ):
                    raise IdentityError("installed qualification report conflicts with source identity")
                if entry["filename"] in proven:
                    raise IdentityError("duplicate installed qualification report")
                proven[entry["filename"]] = entry["sha256"]
            if len(reported) != 2:
                raise IdentityError("installed qualification report lacks both native variants")
        if proven != {entry["filename"]: entry["sha256"] for entry in entries}:
            raise IdentityError("installed qualification reports do not bind all candidate wheel bytes")
        manifest = json.loads((directory / "rc-manifest.json").read_text(encoding="utf-8"))
        if (manifest["sourceCommit"], manifest["sourceTree"], manifest["productVersion"]) != (
            source.sourceCommit, source.sourceTree, source.productVersion
        ):
            raise IdentityError("RC manifest conflicts with qualified source identity")
        manifest_wheels = {}
        for variant, block in manifest["distributions"].items():
            if block["name"] != distribution_name_for(variant) or block["krokoVariant"] != variant:
                raise IdentityError("RC manifest conflicts with qualified distribution variant")
            for wheel in block["wheels"]:
                filename = wheel["filename"]
                entry = expected_entries.get(filename)
                if filename in manifest_wheels or entry is None or (
                    wheel["sha256"], wheel["platformTag"], variant,
                    wheel.get("krokoFingerprint", block["krokoFingerprint"]),
                    wheel.get("krokoArtifactSha256", block["krokoArtifactSha256"]),
                ) != (
                    entry["sha256"], entry["platformTag"], entry["variant"],
                    entry["krokoFingerprint"], entry["krokoArtifactSha256"],
                ):
                    raise IdentityError("RC manifest conflicts with qualified wheel/native provenance")
                manifest_wheels[filename] = wheel["sha256"]
        if manifest_wheels != proven:
            raise IdentityError("RC manifest does not bind the installed candidate wheel bytes")
    return {"schemaVersion": 1, "wheels": entries}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--platform", choices=("linux", "windows"))
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--check-reports", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = qualify_candidate(
            args.candidate_dir, platform=args.platform,
            install=args.install, check_reports=args.check_reports,
        )
        if args.install:
            path = args.candidate_dir / f"identity-qualification-{args.platform}.json"
            path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except IdentityError as exc:
        print(f"identity qualification failed: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError):
        print("identity qualification failed: unreadable or malformed candidate inputs", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
