"""AP-SRV-050 REST-v2 surface tests.

``/api/v2/settings/schema`` and ``/api/v2/settings/server`` are public;
``PATCH /api/v2/settings/server`` reuses the existing admin-key
authentication. Secrets never leave the server.
"""

import pytest

from fastapi.testclient import TestClient

from api_fastapi_server.server import ServerSettings, create_app
from api_fastapi_server.settings_control import (
    ACTIVATION_WATCHDOG_INITIAL,
    ACTIVATION_INITIAL_SPEECH,
    ACTIVATION_FOLLOWUP,
    ApplyPolicy,
    AuthRequirement,
    SettingDefinition,
    SettingScope,
    SettingType,
)
from tests.unit.test_fastapi_server_multi_user import AutoScheduler, FakeRecorder


def make_client(settings):
    app = create_app(
        settings,
        scheduler_factory=AutoScheduler,
        recorder_factory=FakeRecorder,
    )
    return TestClient(app)


TIMING_KEYS = {
    "activation.initialSpeechTimeoutMs",
    "activation.followupTimeoutMs",
    "activation.segmentWatchdogInitialMs",
    "activation.segmentWatchdogRefreshMs",
    "activation.segmentWatchdogWarningMs",
    "activation.closingRecoveryTimeoutMs",
}


def configured_client(admin_key="test-admin-secret"):
    settings = ServerSettings(
        model_warmup=False,
        admin_api_key=admin_key,
    )
    return make_client(settings)


def test_schema_endpoint_is_public_and_covers_timings():
    with configured_client() as client:
        response = client.get("/api/v2/settings/schema")
    assert response.status_code == 200
    body = response.json()
    assert body["protocolVersion"] == 2
    assert body["secretsExposed"] is False
    entries = {entry["key"]: entry for entry in body["settings"]}
    assert TIMING_KEYS <= set(entries)
    for key in TIMING_KEYS:
        entry = entries[key]
        assert entry["scope"] == "session"
        assert entry["auth"] == "session"
        assert entry["type"] == "int"
        assert entry["applyPolicy"] == "next_activation"
        assert "requestedValue" not in entry
        assert "effectiveValue" not in entry


def test_server_endpoint_is_public_and_shows_defaults():
    with configured_client() as client:
        response = client.get("/api/v2/settings/server")
    assert response.status_code == 200
    body = response.json()
    assert body["settingsRevision"] == 0
    by_key = {entry["key"]: entry for entry in body["settings"]}
    assert by_key[ACTIVATION_INITIAL_SPEECH]["requestedValue"] == 15000
    assert by_key[ACTIVATION_INITIAL_SPEECH]["effectiveValue"] == 15000
    assert by_key["wakeWord.sensitivity"]["requestedValue"] == 0.5


def test_server_patch_without_key_is_rejected():
    with configured_client() as client:
        response = client.patch(
            "/api/v2/settings/server",
            json={ACTIVATION_INITIAL_SPEECH: "x"},  # auth fails first
        )
    assert response.status_code == 401


def test_server_patch_with_wrong_key_is_rejected():
    with configured_client() as client:
        response = client.patch(
            "/api/v2/settings/server",
            json={ACTIVATION_INITIAL_SPEECH: "x"},
            headers={"X-VoiceSTT-Admin-Key": "wrong"},
        )
    assert response.status_code == 401


def test_server_patch_with_correct_key_applies_atomically():
    with configured_client() as client:
        ok = client.patch(
            "/api/v2/settings/server",
            json={
                "baseSettingsRevision": 0,
                "changes": {
                    ACTIVATION_INITIAL_SPEECH: 20000,
                    ACTIVATION_FOLLOWUP: 4000,
                },
            },
            headers={"X-VoiceSTT-Admin-Key": "test-admin-secret"},
        )
    assert ok.status_code == 200
    body = ok.json()
    assert body["accepted"] is True
    assert body["result"] == "applied"
    assert body["settingsRevision"] == 1
    assert set(body["changedKeys"]) == {
        ACTIVATION_INITIAL_SPEECH, ACTIVATION_FOLLOWUP
    }


def test_server_patch_stale_revision_returns_conflict():
    with configured_client() as client:
        headers = {"X-VoiceSTT-Admin-Key": "test-admin-secret"}
        first = client.patch(
            "/api/v2/settings/server",
            json={"baseSettingsRevision": 0, "changes": {ACTIVATION_INITIAL_SPEECH: 20000}},
            headers=headers,
        )
        stale = client.patch(
            "/api/v2/settings/server",
            json={"baseSettingsRevision": 0, "changes": {ACTIVATION_FOLLOWUP: 4000}},
            headers=headers,
        )
    assert first.status_code == 200
    assert stale.status_code == 409
    assert stale.json()["result"] == "settings_revision_conflict"


def test_server_patch_invalid_value_is_machine_readable_and_non_mutating():
    with configured_client() as client:
        headers = {"X-VoiceSTT-Admin-Key": "test-admin-secret"}
        ok = client.patch(
            "/api/v2/settings/server",
            json={"baseSettingsRevision": 0, "changes": {ACTIVATION_INITIAL_SPEECH: 20000}},
            headers=headers,
        )
        bad = client.patch(
            "/api/v2/settings/server",
            json={
                "baseSettingsRevision": ok.json()["settingsRevision"],
                "changes": {
                    ACTIVATION_INITIAL_SPEECH: 30000,
                    ACTIVATION_WATCHDOG_INITIAL: 5000,  # below 60000 min
                },
            },
            headers=headers,
        )
        server = client.get("/api/v2/settings/server").json()
    assert bad.status_code == 422
    assert bad.json()["result"] == "settings_rejected"
    assert [e["code"] for e in bad.json()["errors"]] == ["out_of_range"]
    by_key = {entry["key"]: entry for entry in server["settings"]}
    assert by_key[ACTIVATION_INITIAL_SPEECH]["requestedValue"] == 20000
    assert by_key[ACTIVATION_WATCHDOG_INITIAL]["requestedValue"] == 600000


def test_secret_values_are_redacted_from_server_surface(tmp_path):
    settings = ServerSettings(
        model_warmup=False,
        admin_api_key="test-admin-secret",
        data_root_path=str(tmp_path),
    )
    app = create_app(
        settings,
        scheduler_factory=AutoScheduler,
        recorder_factory=FakeRecorder,
    )
    secret_key = "server.apiSecretToken"
    cp = app.state.settings_control_plane
    cp.registry.definitions[secret_key] = SettingDefinition(
        key=secret_key,
        scope=SettingScope.SERVER.value,
        auth=AuthRequirement.ADMIN.value,
        type=SettingType.STRING.value,
        constraints={},
        default_value="",
        apply_policy=ApplyPolicy.SERVER_RESTART.value,
        has_server_default=True,
        secret=True,
    )
    cp.patch_server(0, {secret_key: "super-secret-token"},
                     server_commit="unknown")

    with TestClient(app) as client:
        server = client.get("/api/v2/settings/server")
        patch = client.patch(
            "/api/v2/settings/server",
            json={
                "baseSettingsRevision": cp.settings_revision,
                "changes": {secret_key: "another-secret"},
            },
            headers={"X-VoiceSTT-Admin-Key": "test-admin-secret"},
        )
        schema = client.get("/api/v2/settings/schema")

    assert "super-secret-token" not in server.text
    assert "another-secret" not in patch.text
    assert "another-secret" not in schema.text
    entry = next(
        e for e in server.json()["settings"] if e["key"] == secret_key
    )
    assert entry["redacted"] is True
    assert "requestedValue" not in entry
    assert "effectiveValue" not in entry
    assert set(patch.json()["redactedKeys"]) == {secret_key}


def test_restart_read_path_across_app_instances(tmp_path):
    settings = ServerSettings(
        model_warmup=False,
        admin_api_key="test-admin-secret",
        data_root_path=str(tmp_path),
    )
    with make_client(settings) as client:
        patch = client.patch(
            "/api/v2/settings/server",
            json={"baseSettingsRevision": 0, "changes": {ACTIVATION_INITIAL_SPEECH: 20000}},
            headers={"X-VoiceSTT-Admin-Key": "test-admin-secret"},
        )
        assert patch.status_code == 200

    second_settings = ServerSettings(
        model_warmup=False,
        admin_api_key="test-admin-secret",
        data_root_path=str(tmp_path),
    )
    with make_client(second_settings) as client:
        server = client.get("/api/v2/settings/server").json()
        schema = client.get("/api/v2/settings/schema")
    assert schema.status_code == 200
    by_key = {entry["key"]: entry for entry in server["settings"]}
    assert by_key[ACTIVATION_INITIAL_SPEECH]["requestedValue"] == 20000
    assert server["settingsRevision"] == 1


def test_protocol_version_is_two_on_all_endpoints():
    with configured_client() as client:
        schema = client.get("/api/v2/settings/schema").json()
        server = client.get("/api/v2/settings/server").json()
    assert schema["protocolVersion"] == 2
    assert server["protocolVersion"] == 2