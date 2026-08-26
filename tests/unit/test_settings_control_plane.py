"""AP-SRV-050 settings control plane: registry, validation, revision,
atomicity, apply policies, session patch port, provider and persistence.

These tests are deliberately free of torch/VoiceSTT imports so they stay fast
and pure. The REST/auth surface lives in ``test_settings_control_rest.py``.
"""

import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from api_fastapi_server.settings_control import (
    ACTIVATION_CLOSING_RECOVERY,
    ACTIVATION_FOLLOWUP,
    ACTIVATION_INITIAL_SPEECH,
    ACTIVATION_WATCHDOG_INITIAL,
    ACTIVATION_WATCHDOG_REFRESH,
    ACTIVATION_WATCHDOG_WARNING,
    RUNTIME_SUPPRESSION_MANUAL,
    WAKE_WORD_GLOBAL_DISABLED,
    WAKE_WORD_SELECTION,
    WAKE_WORD_SENSITIVITY,
    ApplyPolicy,
    AuthRequirement,
    SettingDefinition,
    SettingScope,
    SettingType,
    SettingsControlPlane,
    SettingsRegistry,
    RuntimeSettingsStore,
    SessionActivationSettingsProvider,
    SessionSettingsState,
    build_default_registry,
    milliseconds_to_seconds,
    timing_keys,
)

#: key -> (default, min, max)
EXPECTED_TIMINGS = {
    ACTIVATION_INITIAL_SPEECH: (15000, 100, 3600000),
    ACTIVATION_FOLLOWUP: (3000, 100, 60000),
    ACTIVATION_WATCHDOG_INITIAL: (600000, 60000, 3600000),
    ACTIVATION_WATCHDOG_REFRESH: (180000, 30000, 600000),
    ACTIVATION_WATCHDOG_WARNING: (30000, 5000, None),
    ACTIVATION_CLOSING_RECOVERY: (5000, 1000, 30000),
}


def make_plane(overlay=None, registry=None, revision=0, store=None):
    return SettingsControlPlane(
        registry=registry or build_default_registry(),
        overlay=overlay,
        revision=revision,
        store=store,
    )


# ---------------------------------------------------------------------------
# Registry / Schema
# ---------------------------------------------------------------------------


def test_registry_defines_exactly_the_six_contract_timings():
    registry = build_default_registry()
    assert timing_keys() == set(EXPECTED_TIMINGS)
    for key, (default, minimum, maximum) in EXPECTED_TIMINGS.items():
        definition = registry.get(key)
        assert definition is not None
        assert definition.scope == SettingScope.SESSION.value
        assert definition.auth == AuthRequirement.SESSION.value
        assert definition.type == SettingType.INT.value
        assert definition.apply_policy == ApplyPolicy.NEXT_ACTIVATION.value
        assert definition.has_server_default is True
        assert definition.default_value == default
        if minimum is not None:
            assert definition.constraints["min"] == minimum
        if maximum is not None:
            assert definition.constraints["max"] == maximum


def test_registry_wake_word_sensitivity_contract():
    definition = build_default_registry().get(WAKE_WORD_SENSITIVITY)
    assert definition.type == SettingType.FLOAT.value
    assert definition.constraints == {"min": 0.0, "max": 1.0}
    assert definition.default_value == 0.5
    assert definition.scope == SettingScope.SESSION.value
    assert definition.apply_policy == ApplyPolicy.NEXT_ACTIVATION.value


def test_schema_payload_is_public_and_free_of_values():
    payload = build_default_registry().schema_payload()
    for entry in payload:
        assert "requestedValue" not in entry
        assert "effectiveValue" not in entry
        assert "value" not in entry


def test_builtin_registry_has_no_secret_keys():
    registry = build_default_registry()
    assert not [k for k in registry.keys() if registry.is_secret(k)]


def test_wake_selection_and_suppression_metadata_present():
    registry = build_default_registry()
    selection = registry.get(WAKE_WORD_SELECTION)
    assert selection.type == SettingType.STRING_LIST.value
    assert selection.apply_policy == ApplyPolicy.NEXT_SESSION.value
    manual = registry.get(RUNTIME_SUPPRESSION_MANUAL)
    assert manual.type == SettingType.BOOL.value
    assert manual.apply_policy == ApplyPolicy.LIVE.value


def test_server_only_disable_list_is_admin_scope():
    definition = build_default_registry().get(WAKE_WORD_GLOBAL_DISABLED)
    assert definition.scope == SettingScope.SERVER.value
    assert definition.auth == AuthRequirement.ADMIN.value


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _timing_params():
    cases = []
    for key, (_default, minimum, maximum) in EXPECTED_TIMINGS.items():
        if maximum is not None:
            cases.append((key, minimum, True))
            cases.append((key, maximum, True))
            cases.append((key, minimum - 1, False))
            cases.append((key, maximum + 1, False))
        else:
            # watchdog warning: bounded by the cross-field rule instead.
            cases.append((key, 5000, True))
    return cases


@pytest.mark.parametrize(
    "key,value,accepted", _timing_params()
)
def test_timing_boundaries(key, value, accepted):
    session = make_plane().create_session_state()
    result = session.apply_patch(0, {key: value})
    assert result.accepted is accepted
    if accepted:
        assert result.changed_keys == (key,)
    else:
        assert [e.code for e in result.errors] == ["out_of_range"]


def test_watchdog_warning_boundary_is_cross_field_not_hard_max():
    session = make_plane().create_session_state()
    ok = session.apply_patch(
        0,
        {
            ACTIVATION_WATCHDOG_INITIAL: 60000,
            ACTIVATION_WATCHDOG_REFRESH: 40000,
            ACTIVATION_WATCHDOG_WARNING: 40000,
        },
    )
    assert ok.accepted is False
    assert [e.code for e in ok.errors] == ["cross_field_conflict"]


def test_watchdog_warning_must_be_less_than_effective_deadline():
    session = make_plane().create_session_state()
    patch = session.apply_patch(
        0,
        {
            ACTIVATION_WATCHDOG_INITIAL: 70000,
            ACTIVATION_WATCHDOG_REFRESH: 50000,
            ACTIVATION_WATCHDOG_WARNING: 50000,
        },
    )
    assert patch.accepted is False
    assert ACTIVATION_WATCHDOG_WARNING in {
        error.field for error in patch.errors
    }

    session2 = make_plane().create_session_state()
    ok = session2.apply_patch(
        0,
        {
            ACTIVATION_WATCHDOG_INITIAL: 70000,
            ACTIVATION_WATCHDOG_REFRESH: 60000,
            ACTIVATION_WATCHDOG_WARNING: 59999,
        },
    )
    assert ok.accepted is True


def test_invalid_types_rejected():
    session = make_plane().create_session_state()
    for raw in ("15000", 15000.0, True, None):
        result = session.apply_patch(0, {ACTIVATION_INITIAL_SPEECH: raw})
        assert result.accepted is False
        assert result.result == "settings_rejected"


def test_unknown_key_rejected():
    session = make_plane().create_session_state()
    result = session.apply_patch(0, {"activation.madeUp": 1})
    assert result.accepted is False
    assert [e.code for e in result.errors] == ["unknown_key"]


def test_wrong_scope_session_patch_rejects_server_key():
    session = make_plane().create_session_state()
    result = session.apply_patch(
        0, {WAKE_WORD_GLOBAL_DISABLED: ["alexa"]}
    )
    assert result.accepted is False
    assert [e.code for e in result.errors] == ["wrong_scope"]


def test_envelope_validation():
    session = make_plane().create_session_state()
    for base, changes in ((None, {ACTIVATION_FOLLOWUP: 4000}),
                          (-1, {ACTIVATION_FOLLOWUP: 4000}),
                          (True, {ACTIVATION_FOLLOWUP: 4000}),
                          (0, None),
                          (0, {})):
        result = session.apply_patch(base, changes)
        assert result.accepted is False
        assert result.result == "settings_rejected"


# ---------------------------------------------------------------------------
# Revision
# ---------------------------------------------------------------------------


def test_successful_patch_increments_revision_exactly_once():
    plane = make_plane()
    session = plane.create_session_state()
    assert session.settings_revision == 0
    result = session.apply_patch(0, {ACTIVATION_INITIAL_SPEECH: 20000})
    assert result.accepted is True
    assert result.settings_revision == 1
    assert plane.settings_revision == 1
    assert session.settings_revision == 1


def test_stale_revision_rejected():
    session = make_plane().create_session_state()
    session.apply_patch(0, {ACTIVATION_INITIAL_SPEECH: 20000})
    stale = session.apply_patch(0, {ACTIVATION_FOLLOWUP: 4000})
    assert stale.result == "settings_revision_conflict"
    assert stale.settings_revision == 1


def test_concurrent_patches_exactly_one_wins_on_same_base():
    session = make_plane().create_session_state()
    barrier = threading.Barrier(2)
    results = []

    def patch(value):
        barrier.wait()
        return session.apply_patch(0, {ACTIVATION_INITIAL_SPEECH: value})

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(patch, (20000, 25000)))

    applied = [r for r in results if r.accepted]
    conflicts = [r for r in results if r.result == "settings_revision_conflict"]
    assert len(applied) == 1
    assert len(conflicts) == 1
    assert session.settings_revision == 1
    assert session.effective_values()[ACTIVATION_INITIAL_SPEECH] in (20000, 25000)


def test_retry_on_new_revision_after_conflict():
    session = make_plane().create_session_state()
    first = session.apply_patch(0, {ACTIVATION_INITIAL_SPEECH: 20000})
    second = session.apply_patch(0, {ACTIVATION_INITIAL_SPEECH: 25000})
    assert second.result == "settings_revision_conflict"
    retry = session.apply_patch(
        second.settings_revision, {ACTIVATION_INITIAL_SPEECH: 25000}
    )
    assert retry.accepted is True
    assert retry.settings_revision == 2
    assert session.effective_values()[ACTIVATION_INITIAL_SPEECH] == 25000


def test_no_change_does_not_bump_revision():
    session = make_plane().create_session_state()
    result = session.apply_patch(0, {ACTIVATION_INITIAL_SPEECH: 15000})
    assert result.accepted is True
    assert result.result == "no_change"
    assert result.settings_revision == 0
    assert session.settings_revision == 0


# ---------------------------------------------------------------------------
# Atomicity
# ---------------------------------------------------------------------------


def test_multi_key_patch_with_one_invalid_field_applies_nothing(tmp_path):
    store = RuntimeSettingsStore(tmp_path / "runtime.json")
    plane = make_plane(overlay={}, store=store, revision=0)
    session = plane.create_session_state()
    before_memory = dict(session.effective_values())
    before_overlay = tmp_path / "runtime.json"

    result = session.apply_patch(
        0,
        {
            ACTIVATION_INITIAL_SPEECH: 20000,
            ACTIVATION_WATCHDOG_INITIAL: 5000,  # below 60000 min
            ACTIVATION_FOLLOWUP: 4000,
        },
        register_commit=plane.register_commit,
    )
    assert result.accepted is False
    assert set(result.changed_keys) == set()
    # Memory unchanged.
    assert session.effective_values() == before_memory
    assert session.settings_revision == 0
    if before_overlay.is_file():
        assert store.load_overlay() == {}


def test_server_patch_atomicity_persists_nothing_on_invalid(tmp_path):
    store = RuntimeSettingsStore(tmp_path / "runtime.json")
    plane = make_plane(overlay={}, store=store, revision=0)
    result = plane.patch_server(
        0,
        {
            ACTIVATION_INITIAL_SPEECH: 20000,
            ACTIVATION_WATCHDOG_INITIAL: 5000,
            ACTIVATION_FOLLOWUP: 4000,
        },
    )
    assert result.result == "settings_rejected"
    assert plane.settings_revision == 0
    assert plane.server_default(ACTIVATION_INITIAL_SPEECH) == 15000
    assert store.load_revision() == 0
    assert store.load_overlay() == {}


def test_server_patch_persists_only_after_validation(tmp_path):
    store = RuntimeSettingsStore(tmp_path / "runtime.json")
    plane = make_plane(overlay={}, store=store, revision=0)
    result = plane.patch_server(
        0, {ACTIVATION_INITIAL_SPEECH: 20000}
    )
    assert result.accepted is True
    assert store.load_revision() == 1
    assert store.load_overlay()[ACTIVATION_INITIAL_SPEECH] == 20000


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def test_running_activation_keeps_its_snapshot():
    session = make_plane().create_session_state()
    frozen_before = session.freeze_activation()
    session.apply_patch(0, {ACTIVATION_INITIAL_SPEECH: 20000})
    frozen_after = session.freeze_activation()
    assert frozen_before[ACTIVATION_INITIAL_SPEECH] == 15000
    assert frozen_after[ACTIVATION_INITIAL_SPEECH] == 20000


def test_next_activation_receives_new_values():
    session = make_plane().create_session_state()
    session.apply_patch(0, {ACTIVATION_FOLLOWUP: 4000, ACTIVATION_CLOSING_RECOVERY: 6000})
    provider = SessionActivationSettingsProvider(session)
    timings = provider.activation_timings_seconds()
    assert timings["followup_timeout"] == 4.0
    assert timings["closing_recovery_timeout"] == 6.0
    assert timings["initial_speech_timeout"] == 15.0
    assert timings["segment_watchdog_initial"] == 600.0


def test_next_session_value_not_live_in_running_session():
    session = make_plane().create_session_state()
    session.apply_patch(0, {WAKE_WORD_SELECTION: ["hey_jarvis"]})
    assert session.effective_values()[WAKE_WORD_SELECTION] == []
    session.realize_next_session()
    assert session.effective_values()[WAKE_WORD_SELECTION] == ["hey_jarvis"]


def test_suppression_is_live_for_new_admission():
    session = make_plane().create_session_state()
    session.apply_patch(0, {RUNTIME_SUPPRESSION_MANUAL: True})
    assert session.effective_values()[RUNTIME_SUPPRESSION_MANUAL] is True


def test_server_restart_not_shown_as_live():
    registry = SettingsRegistry([
        SettingDefinition(
            key="server.restartKey",
            scope=SettingScope.SERVER.value,
            auth=AuthRequirement.ADMIN.value,
            type=SettingType.INT.value,
            constraints={"min": 1, "max": 100},
            default_value=5,
            apply_policy=ApplyPolicy.SERVER_RESTART.value,
            has_server_default=True,
        ),
        # Keep the session keys required by the base defaults.
        *build_default_registry().definitions.values(),
    ])
    plane = make_plane(registry=registry)
    result = plane.patch_server(0, {"server.restartKey": 9})
    assert result.accepted is True
    assert result.requires_restart is True
    # Requested changed, effective stays on the old value until restart.
    assert plane.server_default("server.restartKey") == 9
    assert plane.server_effective("server.restartKey") == 5
    entries = {e["key"]: e for e in plane.server_public()["settings"]}
    assert entries["server.restartKey"]["requestedValue"] == 9
    assert entries["server.restartKey"]["effectiveValue"] == 5
    assert entries["server.restartKey"]["applyPolicy"] == "server_restart"
    plane.realize_after_restart()
    assert plane.server_effective("server.restartKey") == 9


def test_session_state_shares_control_plane_revision():
    plane = make_plane()
    session = plane.create_session_state()
    assert session.settings_revision == 0
    session.apply_patch(0, {ACTIVATION_INITIAL_SPEECH: 20000})
    assert plane.settings_revision == 1
    assert session.settings_revision == 1


# ---------------------------------------------------------------------------
# Session patch port (SRV-040 seam)
# ---------------------------------------------------------------------------


def test_session_patch_result_is_directly_projectable_to_ack():
    session = make_plane().create_session_state()
    result = session.apply_patch(
        0,
        {ACTIVATION_INITIAL_SPEECH: 20000, ACTIVATION_FOLLOWUP: 4000},
    )
    ack = result.to_command_ack_parts()
    assert ack["accepted"] is True
    assert ack["result"] == "applied"
    assert ack["settingsRevision"] == 1
    assert set(ack["changedKeys"]) == {
        ACTIVATION_INITIAL_SPEECH, ACTIVATION_FOLLOWUP
    }
    assert ack["effectiveSettings"][ACTIVATION_INITIAL_SPEECH] == 20000
    assert ack["errors"] == []


def test_freeze_is_immutable_and_defensive():
    session = make_plane().create_session_state()
    frozen = session.freeze_activation()
    with pytest.raises(TypeError):
        frozen[ACTIVATION_INITIAL_SPEECH] = 1  # MappingProxyType
    provider = SessionActivationSettingsProvider(session)
    assert provider.freeze() is not session.freeze_activation()


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_runtime_settings_store_round_trip(tmp_path):
    path = tmp_path / "runtime.json"
    store = RuntimeSettingsStore(path)
    store.save_overlay_and_revision(
        {ACTIVATION_INITIAL_SPEECH: 21000}, 7
    )
    reopened = RuntimeSettingsStore(path)
    assert reopened.load_overlay()[ACTIVATION_INITIAL_SPEECH] == 21000
    assert reopened.load_revision() == 7


def test_runtime_settings_store_writes_atomically(tmp_path):
    path = tmp_path / "runtime.json"
    store = RuntimeSettingsStore(path)
    store.save_overlay_and_revision({ACTIVATION_FOLLOWUP: 4000}, 3)
    leftovers = [
        item for item in tmp_path.iterdir()
        if item.name.startswith(".runtime.json.")
    ]
    assert leftovers == []
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["settingsRevision"] == 3


def test_plane_restart_read_path(tmp_path):
    path = tmp_path / "runtime.json"
    first = SettingsControlPlane(
        registry=build_default_registry(),
        store=RuntimeSettingsStore(path),
        overlay={},
        revision=0,
    )
    first.patch_server(0, {ACTIVATION_INITIAL_SPEECH: 24000})

    store = RuntimeSettingsStore(path)
    second = SettingsControlPlane(
        registry=build_default_registry(),
        store=store,
        overlay=store.load_overlay(),
        revision=store.load_revision(),
    )
    assert second.settings_revision == 1
    assert second.server_default(ACTIVATION_INITIAL_SPEECH) == 24000


def test_ms_to_seconds_conversion_is_exact():
    assert milliseconds_to_seconds(15000) == 15.0
    assert milliseconds_to_seconds(600000) == 600.0
    assert milliseconds_to_seconds(1) == 0.001