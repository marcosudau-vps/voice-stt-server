"""Fast candidate-gate tests use synthetic archives, not native qualification."""

from dataclasses import replace
import json
from types import SimpleNamespace
import zipfile

import pytest

from VoiceSTT._build_identity import BuildIdentity, IdentityError
from tools import qualify_build_identity as q
from tools.release_candidate import CandidateError, candidate_source


@pytest.fixture
def source():
    return BuildIdentity.from_dict({
        "schemaVersion": 1, "productVersion": "2.0.0", "packageVersion": "2.0.0",
        "sourceCommit": "a" * 40, "sourceTree": "b" * 40, "sourceDirty": False,
        "sourceDate": "2026-10-20T00:00:00Z", "distributionName": "voicestt",
        "krokoVariant": None, "provenance": "git",
    })


def write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def modify_json(path, mutate):
    data = json.loads(path.read_text())
    mutate(data)
    write_json(path, data)


@pytest.fixture
def candidate(tmp_path, monkeypatch, source):
    monkeypatch.setattr(q, "capture_identity", lambda *args: source)
    monkeypatch.setattr(q, "resolve_version", lambda: source.productVersion)
    dist = tmp_path / "dist"
    dist.mkdir()
    manifest = {
        "sourceCommit": source.sourceCommit, "sourceTree": source.sourceTree,
        "productVersion": source.productVersion, "distributions": {},
    }
    for variant in ("free", "pro"):
        name = q.distribution_name_for(variant)
        identity = replace(source, distributionName=name, krokoVariant=variant)
        block = {
            "name": name, "krokoVariant": variant, "krokoFingerprint": "synthetic-linux",
            "krokoArtifactSha256": "c" * 64, "wheels": [],
        }
        for target in ("linux_x86_64", "win_amd64"):
            filename = f"{name.replace('-', '_')}-2.0.0-cp312-cp312-{target}.whl"
            kroko = {
                "fingerprint": f"synthetic-{variant}-{target}",
                "wheelSha256": ("c" if target.startswith("linux") else "d") * 64,
            }
            embedded = {
                "schemaVersion": 1, "distribution": name, "variant": variant,
                "productVersion": source.productVersion, "kroko": kroko,
            }
            wheel = dist / filename
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("VoiceSTT/_build_identity.json", identity.to_json())
                archive.writestr(f"{name.replace('-', '_')}-2.0.0.dist-info/METADATA",
                                 f"Name: {name}\nVersion: 2.0.0\n")
                archive.writestr("voice_stt_server/_embedded_kroko.json", json.dumps(embedded))
                archive.writestr("kroko_onnx/__init__.py", "# synthetic fixture\n")
            record = {
                "filename": filename, "sha256": q.sha256(wheel),
                "platformTag": target, "variant": variant, "embedded": embedded,
            }
            write_json(tmp_path / f"distribution-{variant}-{target}.json", record)
            block["wheels"].append({
                "filename": filename, "sha256": record["sha256"], "platformTag": target,
                "krokoFingerprint": kroko["fingerprint"], "krokoArtifactSha256": kroko["wheelSha256"],
            })
        manifest["distributions"][variant] = block
    write_json(tmp_path / "rc-manifest.json", manifest)

    def installed(wheel, identity):
        return {"nativeImport": True, "info": {
            "identityStatus": "complete", "serverVersion": identity.productVersion,
            "serverCommit": identity.sourceCommit,
            "distribution": {"name": identity.distributionName, "packageVersion": identity.packageVersion},
            "runtime": {"krokoVariant": identity.krokoVariant},
            "build": {"sourceTree": identity.sourceTree, "sourceDirty": False,
                      "sourceDate": identity.sourceDate},
        }}

    monkeypatch.setattr(q, "qualify_installed_wheel", installed)
    for target in ("linux", "windows"):
        report = q.qualify_candidate(tmp_path, platform=target, install=True)
        write_json(tmp_path / f"identity-qualification-{target}.json", report)
    return tmp_path


def test_both_platform_reports_bind_exact_candidate_and_native_bytes(candidate):
    assert len(q.qualify_candidate(candidate, check_reports=True)["wheels"]) == 4


@pytest.mark.parametrize("field,value", [
    ("sourceCommit", "e" * 40), ("sourceTree", "e" * 40), ("variant", "free"),
    ("sha256", "e" * 64), ("platformTag", "win_amd64"),
    ("krokoFingerprint", "different"), ("krokoArtifactSha256", "e" * 64),
])
def test_installed_report_mismatches_fail(candidate, field, value):
    path = candidate / "identity-qualification-linux.json"
    modify_json(path, lambda data: data["wheels"][-1].update({field: value}))
    with pytest.raises(IdentityError):
        q.qualify_candidate(candidate, check_reports=True)


@pytest.mark.parametrize("change", [
    lambda data: data.update(schemaVersion=True),
    lambda data: data["wheels"].pop(),
    lambda data: data["wheels"].append(data["wheels"][0]),
    lambda data: data["wheels"][0]["installed"].update(nativeImport=False),
    lambda data: data["wheels"][0]["installed"]["info"].update(identityStatus="incomplete"),
    lambda data: data["wheels"][0]["installed"]["info"]["build"].update(sourceDirty=True),
    lambda data: data["wheels"][0]["installed"]["info"]["runtime"].update(krokoVariant="pro"),
])
def test_incomplete_or_false_native_report_cannot_qualify(candidate, change):
    modify_json(candidate / "identity-qualification-linux.json", change)
    with pytest.raises(IdentityError):
        q.qualify_candidate(candidate, check_reports=True)


@pytest.mark.parametrize("change", [
    lambda data: data.update(sourceCommit="e" * 40),
    lambda data: data.update(sourceTree="e" * 40),
    lambda data: data["distributions"]["free"].update(krokoVariant="pro"),
    lambda data: data["distributions"]["free"]["wheels"][0].update(krokoArtifactSha256="e" * 64),
    lambda data: data["distributions"]["free"]["wheels"][1].update(krokoFingerprint="wrong"),
    lambda data: data["distributions"]["free"]["wheels"][0].update(sha256="e" * 64),
    lambda data: data["distributions"]["free"]["wheels"].pop(),
])
def test_rc_manifest_cannot_rebind_qualified_source_or_bytes(candidate, change):
    modify_json(candidate / "rc-manifest.json", change)
    with pytest.raises(IdentityError):
        q.qualify_candidate(candidate, check_reports=True)


@pytest.mark.parametrize("change", [
    lambda data: data.update(sha256="e" * 64),
    lambda data: data.update(filename="../escape.whl"),
    lambda data: data["embedded"]["kroko"].update(fingerprint="wrong"),
    lambda data: data["embedded"]["kroko"].update(wheelSha256="e" * 64),
])
def test_static_candidate_mismatch_fails_before_install(candidate, change):
    modify_json(candidate / "distribution-free-linux_x86_64.json", change)
    with pytest.raises(IdentityError):
        q.qualify_candidate(candidate)


def test_native_gate_requires_explicit_platform(candidate):
    with pytest.raises(IdentityError, match="explicit platform"):
        q.qualify_candidate(candidate, install=True)


def test_installation_failure_is_not_a_success_report(tmp_path, source, monkeypatch):
    monkeypatch.setattr(q.venv.EnvBuilder, "create", lambda *args: None)
    monkeypatch.setattr(q.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        returncode=1, stdout="", stderr="synthetic pip failure",
    ))
    with pytest.raises(IdentityError, match="installed wheel qualification failed"):
        q.qualify_installed_wheel(tmp_path / "wheel.whl", source)


def test_cli_malformed_inputs_fail_redacted(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(q, "qualify_candidate", lambda *args, **kwargs: (_ for _ in ()).throw(
        KeyError("SECRET_SENTINEL")
    ))
    assert q.main(["--candidate-dir", str(tmp_path)]) == 1
    assert "SECRET_SENTINEL" not in capsys.readouterr().err


@pytest.mark.parametrize("changes", [
    {"sourceDirty": True}, {"sourceDirty": None}, {"sourceCommit": None}, {"sourceTree": None},
])
def test_rc_source_requires_clean_complete_provenance(source, monkeypatch, changes):
    import tools.release_candidate as rc
    monkeypatch.setattr(rc, "capture_identity", lambda *args, **kwargs: replace(source, **changes))
    with pytest.raises(IdentityError):
        candidate_source(source.sourceTree, None)


def test_rc_source_tree_mismatch_fails(source, monkeypatch):
    import tools.release_candidate as rc
    monkeypatch.setattr(rc, "capture_identity", lambda *args, **kwargs: source)
    with pytest.raises(CandidateError, match="tree"):
        candidate_source("e" * 40, None)


@pytest.mark.parametrize("distribution,variant", [
    ("voicestt", "free"), ("voicestt", "pro"),
    ("voice-stt-server", "free"), ("voice-stt-server-pro", "pro"),
])
@pytest.mark.parametrize("failure", [None, "http", "websocket"])
def test_installed_probe_uses_real_loopback_and_cleans_up(
    source, monkeypatch, capsys, distribution, variant, failure,
):
    import sys
    import threading
    from contextlib import asynccontextmanager
    from fastapi import FastAPI, WebSocket
    from fastapi.responses import JSONResponse
    from api_fastapi_server import server
    from VoiceSTT import _build_identity
    from VoiceSTT.kroko import artifacts

    identity = replace(
        source, distributionName=distribution,
        krokoVariant=None if distribution == "voicestt" else variant,
    )
    info = {
        "serverVersion": source.productVersion, "serverCommit": source.sourceCommit,
        "identityStatus": "complete", "serverInstanceId": "probe-instance",
        "distribution": {"name": distribution, "packageVersion": source.packageVersion},
        "runtime": {"krokoVariant": variant},
        "build": {"sourceTree": source.sourceTree, "sourceDirty": False,
                  "sourceDate": source.sourceDate},
    }
    @asynccontextmanager
    async def lifespan(app):
        app.state.initialized = True
        yield
        app.state.initialized = False

    app = FastAPI(version=source.productVersion, lifespan=lifespan)
    app.state.initialized = False
    app.state.voicestt_service = SimpleNamespace(
        events=SimpleNamespace(server_instance_id=info["serverInstanceId"]),
    )

    @app.get("/api/v2/info")
    def get_info():
        return JSONResponse(info, status_code=503 if failure == "http" else 200,
                            headers={"Cache-Control": "no-store"})

    @app.get("/api/v2/settings/schema")
    @app.get("/api/v2/settings/server")
    def get_settings():
        return {"serverVersion": source.productVersion, "serverCommit": source.sourceCommit}

    @app.get("/health")
    def health():
        return {"ready": app.state.initialized, "sttReady": False, "ok": False}

    @app.websocket("/ws/v2")
    async def incompatible(ws: WebSocket):
        await ws.accept()
        hello = await ws.receive_json()
        assert hello["supportedProtocolVersions"] == [999]
        await ws.send_json({
            "type": "protocol.incompatible", "serverVersion": source.productVersion,
            "serverCommit": "f" * 40 if failure == "websocket" else source.sourceCommit,
        })
        await ws.close()

    monkeypatch.setattr(server, "create_app", lambda settings: app)
    monkeypatch.setattr(_build_identity, "validated_build_identity", lambda: identity)
    monkeypatch.setattr(artifacts, "verify_installed_runtime",
                        lambda expected: {"ok": expected == variant})
    argv = ["qualification", identity.to_json()]
    if distribution == "voicestt":
        argv.append(variant)
    monkeypatch.setattr(sys, "argv", argv)
    if failure:
        with pytest.raises(AssertionError):
            exec(compile(q.INSTALLED_CHECK, "<installed-probe>", "exec"), {})
        assert "IDENTITY_QUALIFICATION=" not in capsys.readouterr().out
    else:
        exec(compile(q.INSTALLED_CHECK, "<installed-probe>", "exec"), {})
        evidence = q.qualification_evidence(capsys.readouterr().out)
        assert evidence == {"nativeImport": True, "info": info}
    assert not any(worker.name == "identity-qualification-http" for worker in threading.enumerate())
