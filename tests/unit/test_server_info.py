"""Runtime identity projections without models, Docker or a source repository."""

from dataclasses import replace
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from api_fastapi_server.protocol_v2 import identity
from tests.unit.test_protocol_v2_e2e import V2Session, hello_message
from tests.unit.test_server_controlled_e2e import build_app


COMMIT = "a" * 40


@pytest.mark.parametrize("commit", [None, "", "  ", "unknown", COMMIT])
def test_optional_commit_and_exact_sha(monkeypatch, commit):
    if commit is None:
        monkeypatch.delenv("VOICESTT_SERVER_COMMIT", raising=False)
    else:
        monkeypatch.setenv("VOICESTT_SERVER_COMMIT", commit)
    assert identity.server_commit() == (COMMIT if commit == COMMIT else "unknown")


@pytest.mark.parametrize("commit", ["abc", "A" * 40, "g" * 40, "a" * 41, "secret/key"])
def test_invalid_commit_is_redacted_start_error(monkeypatch, commit):
    monkeypatch.setenv("VOICESTT_SERVER_COMMIT", commit)
    with pytest.raises(identity.IdentityError) as error:
        build_app()
    assert commit not in str(error.value)


@pytest.mark.parametrize(
    "name,variant", [("voicestt", "free"), ("voicestt", "pro"),
                     ("voice-stt-server", "free"), ("voice-stt-server-pro", "pro")]
)
def test_info_does_not_infer_distribution_from_runtime(name, variant):
    resolved = identity.RuntimeIdentity("2.0.0", COMMIT, name, "2.0.0", variant)
    with mock.patch.object(identity, "resolve_runtime_identity", return_value=resolved):
        app = build_app()
    with TestClient(app) as client:
        response = client.get("/api/v2/info")
        info = response.json()
        assert response.headers["cache-control"] == "no-store"
        assert info == {
            "schemaVersion": 1, "protocolVersion": 2,
            "serverVersion": "2.0.0", "serverCommit": COMMIT,
            "identityStatus": "incomplete",
            "build": {"sourceTree": None, "sourceDirty": None, "sourceDate": None},
            "distribution": {"name": name, "packageVersion": "2.0.0"},
            "runtime": {"krokoVariant": variant},
            "serverInstanceId": app.state.voicestt_service.events.server_instance_id,
        }


def test_info_is_cached_projection_even_if_environment_changes(monkeypatch):
    monkeypatch.setenv("VOICESTT_SERVER_COMMIT", COMMIT)
    app = build_app()
    with TestClient(app) as client:
        initial = client.get("/api/v2/info").json()
        monkeypatch.setenv("VOICESTT_SERVER_COMMIT", "b" * 40)
        monkeypatch.setenv("VOICESTT_BUILD_VERSION", "8.9.0")
        with mock.patch.object(identity, "resolve_runtime_identity", side_effect=AssertionError):
            assert client.get("/api/v2/info").json() == initial
            for path in ("/api/v2/settings/schema", "/api/v2/settings/server"):
                settings = client.get(path).json()
                assert settings["serverVersion"] == initial["serverVersion"]
                assert settings["serverCommit"] == initial["serverCommit"]
            assert client.get("/openapi.json").json()["info"]["version"] == initial["serverVersion"]
            with V2Session(client) as session:
                accepted = session.accepted
                snapshot = session.snapshot()
                for message in (accepted, snapshot):
                    assert message["serverVersion"] == initial["serverVersion"]
                    assert message["serverCommit"] == COMMIT
            with V2Session(client, hello=hello_message(versions=(99,)), expect_accept=False) as session:
                refusal = session.expect()
                assert refusal["serverVersion"] == initial["serverVersion"]
                assert refusal["serverCommit"] == COMMIT


def test_no_model_or_external_probe_in_info_and_instance_is_hub_local():
    first, second = build_app(), build_app()
    with TestClient(first) as client:
        service = first.state.voicestt_service
        with mock.patch.object(service, "metrics", side_effect=AssertionError), \
             mock.patch("subprocess.run", side_effect=AssertionError), \
             mock.patch.object(identity.metadata, "distribution", side_effect=AssertionError):
            info = client.get("/api/v2/info").json()
            assert client.get("/api/v2/info").json() == info
        assert info["serverInstanceId"] == service.events.server_instance_id
    with TestClient(second) as client:
        assert client.get("/api/v2/info").json()["serverInstanceId"] != info["serverInstanceId"]


def test_complete_requires_all_provenance_and_clean_source():
    partial = identity.RuntimeIdentity("2.0.0", COMMIT, "voicestt", "2.0.0", "pro")
    full = replace(partial, source_tree="b" * 40, source_dirty=False,
                   source_date="2026-10-19T21:34:01Z")
    assert full.public_info("instance")["identityStatus"] == "complete"
    for missing in (
        replace(full, source_dirty=None), replace(full, source_dirty=True),
        replace(full, source_tree=None), replace(full, source_date=None),
        replace(full, commit="unknown"), replace(full, distribution_name=None),
    ):
        assert missing.public_info("instance")["identityStatus"] == "incomplete"
