"""AP-SRV-050 - settings domain control plane unit proofs.

Pure domain tests: registry contract, atomic patch validation, the
requested/effective apply-policy semantics, the monotonic ``settingsRevision``
rules, optimistic concurrency, the watchdog cross-field rule and the server
default overlay. No WebSocket, no socket: every assertion talks to the same
module the wire layer binds.

AP-SRV-050 C2 (root-correction) additionally covers: sequential cross-field
bypass (F1), wake-selection fail-closed validation (F2), the atomic activation
admission bundle (F3), persisted-overlay startup validation (F4) and the
prepare->persist->commit atomicity of server settings (F5).
"""

import threading
import time

import pytest

from api_fastapi_server import settings_control as sc


def registry():
    return sc.build_default_registry()


def session_state(**kwargs):
    return sc.SessionSettingsState(registry(), **kwargs)


def server_state(**kwargs):
    return sc.ServerSettingsState(registry(), **kwargs)


# -- registry contract --------------------------------------------------------

class TestRegistryContract:
    def test_every_frozen_setting_key_is_present(self):
        keys = set(registry().keys())
        assert sc.ACTIVATION_INITIAL_SPEECH in keys
        assert sc.ACTIVATION_FOLLOWUP in keys
        assert sc.ACTIVATION_WATCHDOG_INITIAL in keys
        assert sc.ACTIVATION_WATCHDOG_REFRESH in keys
        assert sc.ACTIVATION_WATCHDOG_WARNING in keys
        assert sc.ACTIVATION_CLOSING_RECOVERY in keys
        assert sc.WAKE_WORD_SENSITIVITY in keys
        assert sc.WAKE_WORD_SELECTION in keys
        assert sc.WAKE_WORD_GLOBAL_DISABLED in keys
        assert sc.RUNTIME_SUPPRESSION_MANUAL in keys
        assert sc.RUNTIME_SUPPRESSION_WAKE_WORD in keys

    def test_the_six_timings_follow_the_frozen_contract(self):
        reg = registry()
        for key, expected in {
            sc.ACTIVATION_INITIAL_SPEECH: (15000, 100, 3600000),
            sc.ACTIVATION_FOLLOWUP: (3000, 100, 60000),
            sc.ACTIVATION_WATCHDOG_INITIAL: (600000, 60000, 3600000),
            sc.ACTIVATION_WATCHDOG_REFRESH: (180000, 30000, 600000),
            sc.ACTIVATION_WATCHDOG_WARNING: (30000, 5000, None),
            sc.ACTIVATION_CLOSING_RECOVERY: (5000, 1000, 30000),
        }.items():
            definition = reg.get(key)
            assert definition.scope == sc.SCOPE_SESSION
            assert definition.auth == sc.AUTH_SESSION
            assert definition.type == sc.TYPE_INT
            assert definition.apply_policy == sc.APPLY_NEXT_ACTIVATION
            assert definition.default_value == expected[0]
            assert definition.constraints["min"] == expected[1]
            assert definition.constraints.get("max") == expected[2]
            assert definition.has_server_default is True

    def test_wake_sensitivity_follows_the_frozen_contract(self):
        definition = registry().get(sc.WAKE_WORD_SENSITIVITY)
        assert definition.scope == sc.SCOPE_SESSION
        assert definition.auth == sc.AUTH_SESSION
        assert definition.type == sc.TYPE_FLOAT
        assert definition.constraints["min"] == 0.0
        assert definition.constraints["max"] == 1.0
        assert definition.default_value == 0.5
        assert definition.apply_policy == sc.APPLY_NEXT_ACTIVATION

    def test_wake_selection_is_session_next_session(self):
        definition = registry().get(sc.WAKE_WORD_SELECTION)
        assert definition.scope == sc.SCOPE_SESSION
        assert definition.auth == sc.AUTH_SESSION
        assert definition.type == sc.TYPE_STRING_LIST
        assert definition.apply_policy == sc.APPLY_NEXT_SESSION
        assert definition.default_value == []

    def test_global_disable_is_server_admin(self):
        definition = registry().get(sc.WAKE_WORD_GLOBAL_DISABLED)
        assert definition.scope == sc.SCOPE_SERVER
        assert definition.auth == sc.AUTH_ADMIN
        assert definition.type == sc.TYPE_STRING_LIST
        assert definition.apply_policy == sc.APPLY_NEXT_SESSION
        assert definition.has_server_default is True

    def test_runtime_suppression_is_metadata_only(self):
        for key in (sc.RUNTIME_SUPPRESSION_MANUAL,
                    sc.RUNTIME_SUPPRESSION_WAKE_WORD):
            definition = registry().get(key)
            assert definition.scope == sc.SCOPE_SESSION
            assert definition.type == sc.TYPE_BOOL
            assert definition.writable is False

    def test_schema_is_sorted_by_key_without_secrets(self):
        entries = registry().schema_payload()
        keys = [entry["key"] for entry in entries]
        assert keys == sorted(keys)
        for entry in entries:
            for field in ("key", "scope", "auth", "type", "constraints",
                          "defaultValue", "applyPolicy"):
                assert field in entry
            assert "admin_api_key" not in str(entry)
            assert "openai_api_key" not in str(entry)

    def test_no_private_policy_synonyms_exist(self):
        policies = {definition.apply_policy
                    for definition in registry().definitions.values()}
        assert policies <= set(sc.APPLY_POLICIES)
        assert "mixed" not in policies
        assert "deferred" not in policies
        assert "restart_required" not in policies


# -- session patch transaction rules --------------------------------------------

class TestSessionPatchAtomicity:
    def test_single_key_applied_bumps_revision_once(self):
        state = session_state()
        result = state.apply_patch(0, {sc.ACTIVATION_FOLLOWUP: 8000})
        assert result.accepted
        assert result.result == sc.RESULT_APPLIED
        assert result.settings_revision == 1
        assert result.changed_keys == (sc.ACTIVATION_FOLLOWUP,)
        assert state.settings_revision == 1
        assert state.effective_values()[sc.ACTIVATION_FOLLOWUP] == 8000

    def test_multi_key_same_policy_revision_only_once(self):
        state = session_state()
        result = state.apply_patch(0, {
            sc.ACTIVATION_FOLLOWUP: 8000,
            sc.ACTIVATION_INITIAL_SPEECH: 22000,
        })
        assert result.accepted
        assert result.settings_revision == 1
        assert result.changed_keys == (
            sc.ACTIVATION_FOLLOWUP, sc.ACTIVATION_INITIAL_SPEECH,
        )
        assert state.settings_revision == 1

    def test_multi_policy_groups_and_single_revision(self):
        state = session_state()
        result = state.apply_patch(0, {
            sc.ACTIVATION_FOLLOWUP: 8000,             # next_activation
            sc.WAKE_WORD_SELECTION: ["hey_jarvis"],   # next_session
        })
        assert result.accepted
        assert result.settings_revision == 1
        assert state.settings_revision == 1
        assert result.apply_policies[sc.ACTIVATION_FOLLOWUP] == \
            sc.APPLY_NEXT_ACTIVATION
        assert result.apply_policies[sc.WAKE_WORD_SELECTION] == \
            sc.APPLY_NEXT_SESSION

    def test_invalid_field_rejects_the_whole_transaction(self):
        state = session_state()
        before = dict(state.effective_values())
        result = state.apply_patch(0, {
            sc.ACTIVATION_FOLLOWUP: 8000,              # valid
            sc.ACTIVATION_WATCHDOG_INITIAL: -5,        # invalid range
        })
        assert not result.accepted
        assert result.result == sc.RESULT_REJECTED
        assert state.settings_revision == 0
        # no partial write
        assert state.effective_values()[sc.ACTIVATION_FOLLOWUP] == \
            before[sc.ACTIVATION_FOLLOWUP]

    def test_errors_are_deterministically_sorted_by_field(self):
        state = session_state()
        result = state.apply_patch(0, {
            "activation.zzzKey": 1,
            "activation.aaaKey": "not-an-int",
        })
        assert result.result == sc.RESULT_REJECTED
        fields = [error.field for error in result.errors]
        assert fields == sorted(fields)

    def test_stale_base_revision_conflicts(self):
        state = session_state()
        state.apply_patch(0, {sc.ACTIVATION_FOLLOWUP: 8000})
        conflict = state.apply_patch(0, {sc.ACTIVATION_FOLLOWUP: 9000})
        assert not conflict.accepted
        assert conflict.result == sc.RESULT_REVISION_CONFLICT
        assert conflict.errors[0].code == sc.CODE_STALE_REVISION
        assert state.settings_revision == 1
        assert state.effective_values()[sc.ACTIVATION_FOLLOWUP] == 8000

    def test_no_change_does_not_bump_revision(self):
        state = session_state()
        first = state.apply_patch(0, {sc.ACTIVATION_FOLLOWUP: 3000})
        assert first.accepted
        assert first.result == sc.RESULT_NO_CHANGE
        assert first.settings_revision == 0
        assert state.settings_revision == 0
        assert first.changed_keys == ()

    def test_server_scope_key_is_rejected_in_a_session_patch(self):
        state = session_state()
        result = state.apply_patch(0, {sc.WAKE_WORD_GLOBAL_DISABLED: ["x"]})
        assert result.result == sc.RESULT_REJECTED
        assert result.errors[0].code == sc.CODE_WRONG_SCOPE

    def test_suppression_is_not_a_second_write_path(self):
        state = session_state()
        result = state.apply_patch(0, {sc.RUNTIME_SUPPRESSION_MANUAL: True})
        assert result.result == sc.RESULT_REJECTED
        assert result.errors[0].code == sc.CODE_READ_ONLY_AUTHORITY

    def test_unknown_key_is_machine_readable(self):
        state = session_state()
        result = state.apply_patch(0, {"nonsense.key": 1})
        assert result.result == sc.RESULT_REJECTED
        assert result.errors[0].code == sc.CODE_UNKNOWN_KEY

    def test_bool_never_accepted_for_numeric_types(self):
        state = session_state()
        result = state.apply_patch(0, {sc.ACTIVATION_FOLLOWUP: True})
        assert result.result == sc.RESULT_REJECTED
        assert result.errors[0].code == sc.CODE_INVALID_TYPE


class TestRequestedEffectiveSemantics:
    def test_next_activation_without_running_activation_is_effective_now(self):
        state = session_state()
        result = state.apply_patch(0, {sc.ACTIVATION_FOLLOWUP: 8000})
        assert result.accepted
        assert result.values[sc.ACTIVATION_FOLLOWUP] == 8000
        assert result.effective_values[sc.ACTIVATION_FOLLOWUP] == 8000
        frozen = state.freeze_activation()
        assert frozen[sc.ACTIVATION_FOLLOWUP] == 8000

    def test_next_session_keeps_the_current_session_value(self):
        state = session_state()
        result = state.apply_patch(0, {sc.WAKE_WORD_SELECTION: ["hey_jarvis"]})
        assert result.accepted
        assert result.values[sc.WAKE_WORD_SELECTION] == ["hey_jarvis"]
        # effectiveValue remains the running session's value until the rebuild.
        assert result.effective_values[sc.WAKE_WORD_SELECTION] == []
        assert state.effective_values()[sc.WAKE_WORD_SELECTION] == []

    def test_freeze_activation_covers_only_activation_relevant_policies(self):
        state = session_state()
        state.apply_patch(0, {
            sc.ACTIVATION_FOLLOWUP: 8000,
            sc.WAKE_WORD_SELECTION: ["hey_jarvis"],
        })
        frozen = state.freeze_activation()
        assert frozen[sc.ACTIVATION_FOLLOWUP] == 8000
        assert sc.WAKE_WORD_SELECTION not in frozen
        assert sc.RUNTIME_SUPPRESSION_MANUAL not in frozen

    def test_activation_timings_are_seconds_and_complete(self):
        state = session_state()
        state.apply_patch(0, {
            sc.ACTIVATION_FOLLOWUP: 8000,
            sc.ACTIVATION_WATCHDOG_REFRESH: 120000,
        })
        timings = state.activation_timings_seconds()
        assert timings[sc.ACTIVATION_FOLLOWUP] == 8.0
        assert timings[sc.ACTIVATION_WATCHDOG_REFRESH] == 120.0
        for key in sc.TIMING_KEYS:
            assert key in timings


class TestWatchdogCrossFieldValidation:
    def test_warning_equal_or_above_refresh_is_rejected_atomically(self):
        state = session_state()
        result = state.apply_patch(0, {
            sc.ACTIVATION_WATCHDOG_WARNING: 30000,
            sc.ACTIVATION_WATCHDOG_REFRESH: 30000,
        })
        assert result.result == sc.RESULT_REJECTED
        assert result.errors[0].code == sc.CODE_CROSS_FIELD_CONFLICT
        assert result.settings_revision == 0

    def test_valid_combination_is_accepted(self):
        state = session_state()
        result = state.apply_patch(0, {
            sc.ACTIVATION_WATCHDOG_WARNING: 5000,
            sc.ACTIVATION_WATCHDOG_REFRESH: 30000,
            sc.ACTIVATION_WATCHDOG_INITIAL: 60000,
        })
        assert result.accepted
        assert result.result == sc.RESULT_APPLIED
        assert result.settings_revision == 1

    def test_warning_strictly_below_initial_is_accepted(self):
        state = session_state()
        result = state.apply_patch(0, {
            sc.ACTIVATION_WATCHDOG_WARNING: 59999,
            sc.ACTIVATION_WATCHDOG_INITIAL: 60000,
            sc.ACTIVATION_WATCHDOG_REFRESH: 60000,
        })
        assert result.accepted
        assert result.settings_revision == 1

    def test_warning_equal_to_initial_is_rejected(self):
        state = session_state()
        result = state.apply_patch(0, {
            sc.ACTIVATION_WATCHDOG_WARNING: 60000,
            sc.ACTIVATION_WATCHDOG_INITIAL: 60000,
        })
        assert result.result == sc.RESULT_REJECTED
        assert result.errors[0].code == sc.CODE_CROSS_FIELD_CONFLICT

    def test_transaction_is_validated_against_the_final_candidate(self):
        # Changing refresh and warning in one transaction is judged on the
        # final candidate, never on the field-by-field order.
        ok = session_state()
        result = ok.apply_patch(0, {
            sc.ACTIVATION_WATCHDOG_WARNING: 5000,
            sc.ACTIVATION_WATCHDOG_REFRESH: 30000,
        })
        assert result.accepted

        rejected = session_state()
        result = rejected.apply_patch(0, {
            sc.ACTIVATION_WATCHDOG_WARNING: 31000,
            sc.ACTIVATION_WATCHDOG_REFRESH: 31000,
        })
        assert result.result == sc.RESULT_REJECTED
        assert result.errors[0].code == sc.CODE_CROSS_FIELD_CONFLICT


class TestSessionRevisionSeams:
    def test_each_session_has_an_own_revision(self):
        first = session_state()
        second = session_state()
        first.apply_patch(0, {sc.ACTIVATION_FOLLOWUP: 8000})
        assert first.settings_revision == 1
        # A change in session A never conflicts session B via a foreign revision.
        assert second.settings_revision == 0
        assert second.apply_patch(0, {sc.ACTIVATION_FOLLOWUP: 9000}).accepted

    def test_server_default_change_never_rewrites_an_existing_session(self):
        server = server_state()
        session_before = sc.SessionSettingsState(
            registry(), server_defaults=server.server_effective()
        )
        changed = session_before.effective_values()[sc.ACTIVATION_FOLLOWUP]

        server.patch_server(0, {sc.ACTIVATION_FOLLOWUP: 8000})
        assert session_before.effective_values()[sc.ACTIVATION_FOLLOWUP] == \
            changed
        # A new session sees the new server default.
        session_after = sc.SessionSettingsState(
            registry(), server_defaults=server.server_effective()
        )
        assert session_after.effective_values()[sc.ACTIVATION_FOLLOWUP] == 8000


class TestServerSettings:
    def test_server_patch_success_persists_and_bumps_once(self):
        written = {}

        def persist(overlay, revision):
            written["overlay"] = dict(overlay)
            written["revision"] = revision

        server = server_state(persist=persist)
        result = server.patch_server(0, {sc.ACTIVATION_FOLLOWUP: 8000})
        assert result.accepted
        assert result.result == sc.RESULT_APPLIED
        assert result.settings_revision == 1
        assert server.settings_revision == 1
        assert written["revision"] == 1
        assert written["overlay"][sc.ACTIVATION_FOLLOWUP] == 8000

    def test_server_no_change_does_not_churn(self):
        server = server_state()
        result = server.patch_server(0, {sc.ACTIVATION_FOLLOWUP: 3000})
        assert result.accepted
        assert result.result == sc.RESULT_NO_CHANGE
        assert result.settings_revision == 0
        assert server.settings_revision == 0

    def test_server_stale_revision_conflicts(self):
        server = server_state()
        result = server.patch_server(5, {sc.ACTIVATION_FOLLOWUP: 8000})
        assert result.result == sc.RESULT_REVISION_CONFLICT
        assert result.errors[0].code == sc.CODE_STALE_REVISION

    def test_server_rejects_session_only_keys(self):
        server = server_state()
        # ``wakeWord.selection`` has no admin-managed server default.
        result = server.patch_server(0, {sc.WAKE_WORD_SELECTION: ["x"]})
        assert result.result == sc.RESULT_REJECTED
        assert result.errors[0].code == sc.CODE_WRONG_SCOPE

    def test_server_rejects_secrets(self):
        secret_definition = sc.SettingDefinition(
            key="admin.something",
            scope=sc.SCOPE_SERVER,
            auth=sc.AUTH_ADMIN,
            type=sc.TYPE_STRING,
            constraints={},
            default_value="",
            apply_policy=sc.APPLY_NEXT_SESSION,
            has_server_default=True,
            secret=True,
        )
        reg = sc.SettingsRegistry(
            [d for d in sc.builtin_definitions()] + [secret_definition]
        )
        server = sc.ServerSettingsState(reg)
        result = server.patch_server(0, {"admin.something": "top-secret"})
        assert result.result == sc.RESULT_REJECTED
        assert result.errors[0].code == sc.CODE_READ_ONLY_AUTHORITY

    def test_server_public_never_publishes_values_of_session_only_keys(self):
        server = server_state()
        payload = server.server_public()
        assert payload["settingsRevision"] == 0
        entries = {entry["key"]: entry for entry in payload["settings"]}
        for key in (sc.ACTIVATION_FOLLOWUP, sc.WAKE_WORD_SENSITIVITY,
                    sc.WAKE_WORD_GLOBAL_DISABLED):
            assert key in entries
            assert "requestedValue" in entries[key]
            assert "effectiveValue" in entries[key]
        assert sc.WAKE_WORD_SELECTION not in entries
        assert sc.RUNTIME_SUPPRESSION_MANUAL not in entries


class TestSessionWakeSelectionValidation:
    def test_empty_selection_is_rejected_when_wake_is_configured(self):
        from api_fastapi_server.server import (
            RecorderBackedRealtimeSession as _SessionClass,
        )

        class FakeSettings:
            def wake_word_enabled(self):
                return True

        class FakeService:
            def session_capabilities(self):
                return {"wakeWord": {"availableWakeWords": [
                    {"id": "hey_jarvis"},
                ]}}

        class FakeSession:
            settings = FakeSettings()
            service = FakeService()

        errors = _SessionClass._validate_wake_selection_key(
            FakeSession(), sc.WAKE_WORD_SELECTION, []
        )
        assert any(error.code == sc.CODE_WAKE_SELECTION_REQUIRED
                   for error in errors)

    def test_unknown_ids_are_rejected_machine_readable(self):
        from api_fastapi_server.server import (
            RecorderBackedRealtimeSession as _SessionClass,
        )

        class FakeSettings:
            def wake_word_enabled(self):
                return False

        class FakeService:
            def session_capabilities(self):
                return {"wakeWord": {"availableWakeWords": [
                    {"id": "hey_jarvis"},
                ]}}

        class FakeSession:
            settings = FakeSettings()
            service = FakeService()

        errors = _SessionClass._validate_wake_selection_key(
            FakeSession(), sc.WAKE_WORD_SELECTION, ["nope"]
        )
        assert any(error.code == sc.CODE_WAKE_WORD_UNAVAILABLE
                   for error in errors)
        assert all(error.field == sc.WAKE_WORD_SELECTION for error in errors)


class TestConcurrentSessionPatches:
    def test_exactly_one_same_base_patch_wins_20x(self):
        for iteration in range(20):
            state = session_state()
            barrier = threading.Barrier(2)
            results = []
            lock = threading.Lock()

            def patch_one(value):
                try:
                    barrier.wait(timeout=10)
                except threading.BrokenBarrierError:
                    pass
                result = state.apply_patch(0, {sc.ACTIVATION_FOLLOWUP: value})
                with lock:
                    results.append(result)

            first = threading.Thread(target=patch_one, args=(8000,))
            second = threading.Thread(target=patch_one, args=(9000,))
            first.start()
            second.start()
            first.join(timeout=15)
            second.join(timeout=15)
            applied = [r for r in results if r.accepted]
            conflicts = [r for r in results
                         if r.result == sc.RESULT_REVISION_CONFLICT]
            assert len(applied) == 1
            assert len(conflicts) == 1
            # The winning value is the only visible one.
            assert state.settings_revision == 1
            assert state.effective_values()[sc.ACTIVATION_FOLLOWUP] in (
                8000, 9000,
            )

    def test_two_sequential_transactions_keep_an_gapless_revision(self):
        state = session_state()
        state.apply_patch(0, {sc.ACTIVATION_FOLLOWUP: 8000})
        state.apply_patch(1, {sc.ACTIVATION_INITIAL_SPEECH: 22000})
        assert state.settings_revision == 2
        assert state.effective_values()[sc.ACTIVATION_FOLLOWUP] == 8000
        assert state.effective_values()[sc.ACTIVATION_INITIAL_SPEECH] == 22000


# -- F1: sequential cross-field bypass ------------------------------------------

class TestSequentialCrossFieldBypass:
    def _session_with_warning(self, warning):
        state = session_state()
        result = state.apply_patch(0, {
            sc.ACTIVATION_WATCHDOG_WARNING: warning,
        })
        assert result.accepted, result
        return state

    def test_sequential_session_patch_lowering_refresh_below_existing_warning_is_rejected(self):
        state = self._session_with_warning(59000)
        before = dict(state.effective_values())
        result = state.apply_patch(
            state.settings_revision, {sc.ACTIVATION_WATCHDOG_REFRESH: 30000}
        )
        assert result.result == sc.RESULT_REJECTED
        assert result.errors[0].code == sc.CODE_CROSS_FIELD_CONFLICT
        assert result.errors[0].field == sc.ACTIVATION_WATCHDOG_WARNING
        # no mutation, no revision bump
        assert state.settings_revision == 1
        assert state.effective_values()[sc.ACTIVATION_WATCHDOG_WARNING] == \
            before[sc.ACTIVATION_WATCHDOG_WARNING]
        assert state.effective_values()[sc.ACTIVATION_WATCHDOG_REFRESH] == \
            before[sc.ACTIVATION_WATCHDOG_REFRESH]

    def test_sequential_session_patch_lowering_initial_to_existing_warning_is_rejected(self):
        state = self._session_with_warning(120000)
        before = dict(state.effective_values())
        result = state.apply_patch(
            state.settings_revision, {sc.ACTIVATION_WATCHDOG_INITIAL: 100000}
        )
        assert result.result == sc.RESULT_REJECTED
        assert result.errors[0].code == sc.CODE_CROSS_FIELD_CONFLICT
        assert state.settings_revision == 1
        assert state.effective_values()[sc.ACTIVATION_WATCHDOG_INITIAL] == \
            before[sc.ACTIVATION_WATCHDOG_INITIAL]

    def test_sequential_server_patch_lowering_refresh_below_existing_warning_is_rejected(self):
        server = server_state(persist=lambda overlay, revision: None)
        first = server.patch_server(0, {sc.ACTIVATION_WATCHDOG_WARNING: 59000})
        assert first.accepted, first
        before = server.overlay()
        result = server.patch_server(
            server.settings_revision, {sc.ACTIVATION_WATCHDOG_REFRESH: 30000}
        )
        assert result.result == sc.RESULT_REJECTED
        assert result.errors[0].code == sc.CODE_CROSS_FIELD_CONFLICT
        assert server.settings_revision == 1
        assert server.overlay() == before

    def test_transaction_changing_warning_and_refresh_uses_final_candidate_not_input_order(self):
        # Changing refresh and warning together is judged on the final candidate.
        ok = session_state()
        result = ok.apply_patch(0, {
            sc.ACTIVATION_WATCHDOG_WARNING: 5000,
            sc.ACTIVATION_WATCHDOG_REFRESH: 30000,
        })
        assert result.accepted

        rejected = session_state()
        result = rejected.apply_patch(0, {
            sc.ACTIVATION_WATCHDOG_WARNING: 40000,
            sc.ACTIVATION_WATCHDOG_REFRESH: 30000,
        })
        assert result.result == sc.RESULT_REJECTED
        assert result.errors[0].code == sc.CODE_CROSS_FIELD_CONFLICT


# -- F2: wake-word selection fail-closed -----------------------------------------

class TestWakeSelectionFailClosed:
    @staticmethod
    def _validator_with(service):
        from api_fastapi_server.server import (
            RecorderBackedRealtimeSession as _SessionClass,
        )

        class FakeSettings:
            def wake_word_enabled(self):
                return False

        class FakeSession:
            settings = FakeSettings()

        session = FakeSession()
        session.service = service
        return _SessionClass._validate_wake_selection_key, session

    def test_wake_selection_nonempty_rejected_when_catalog_empty(self):
        class EmptyCatalog:
            def session_capabilities(self):
                return {"wakeWord": {"availableWakeWords": []}}

        validator, session = self._validator_with(EmptyCatalog())
        errors = validator(session, sc.WAKE_WORD_SELECTION, ["hey_jarvis"])
        assert any(error.code == sc.CODE_WAKE_WORD_UNAVAILABLE
                   for error in errors)
        assert all(error.field == sc.WAKE_WORD_SELECTION for error in errors)

    def test_wake_selection_nonempty_rejected_when_catalog_lookup_raises(self):
        class RaisingCatalog:
            def session_capabilities(self):
                raise RuntimeError("catalog unavailable")

        validator, session = self._validator_with(RaisingCatalog())
        errors = validator(session, sc.WAKE_WORD_SELECTION, ["hey_jarvis"])
        assert any(error.code == sc.CODE_WAKE_WORD_UNAVAILABLE
                   for error in errors)
        # no exception details leak into the listener-visible message
        for error in errors:
            assert "catalog unavailable" not in error.message

    def test_wake_selection_known_remains_accepted(self):
        class KnownCatalog:
            def session_capabilities(self):
                return {"wakeWord": {"availableWakeWords": [
                    {"id": "hey_jarvis"},
                ]}}

        validator, session = self._validator_with(KnownCatalog())
        errors = validator(session, sc.WAKE_WORD_SELECTION, ["hey_jarvis"])
        assert errors == []

    def test_wake_selection_empty_allowed_when_wake_not_configured(self):
        class EmptyCatalog:
            def session_capabilities(self):
                return {"wakeWord": {"availableWakeWords": []}}

        validator, session = self._validator_with(EmptyCatalog())
        assert validator(session, sc.WAKE_WORD_SELECTION, []) == []

    def test_wake_selection_empty_rejected_when_wake_configured(self):
        from api_fastapi_server.server import (
            RecorderBackedRealtimeSession as _SessionClass,
        )

        class FakeSettings:
            def wake_word_enabled(self):
                return True

        class EmptyCatalog:
            def session_capabilities(self):
                return {"wakeWord": {"availableWakeWords": []}}

        class FakeSession:
            settings = FakeSettings()
            service = EmptyCatalog()

        errors = _SessionClass._validate_wake_selection_key(
            FakeSession(), sc.WAKE_WORD_SELECTION, []
        )
        assert any(error.code == sc.CODE_WAKE_SELECTION_REQUIRED
                   for error in errors)

    def test_wake_selection_patch_via_session_validator_is_fail_closed(self):
        class EmptyCatalog:
            def session_capabilities(self):
                return {"wakeWord": {"availableWakeWords": []}}

        validator, session = self._validator_with(EmptyCatalog())
        state = sc.SessionSettingsState(
            sc.build_default_registry(),
            validate_key=lambda key, value: validator(session, key, value),
        )
        result = state.apply_patch(0, {sc.WAKE_WORD_SELECTION: ["hey_jarvis"]})
        assert result.result == sc.RESULT_REJECTED
        assert any(error.code == sc.CODE_WAKE_WORD_UNAVAILABLE
                   for error in result.errors)
        assert state.settings_revision == 0
        assert state.effective_values()[sc.WAKE_WORD_SELECTION] == []


# -- F3: one atomic activation-admission bundle ----------------------------------

class TestActivationAdmissionBundle:
    def test_activation_admission_settings_bundle_is_atomic(self):
        state = session_state()
        state.apply_patch(0, {sc.ACTIVATION_FOLLOWUP: 8000})
        bundle = state.activation_admission_settings()
        assert bundle.settings_revision == 1
        # effective and timing come from the SAME snapshot
        assert bundle.effective_settings[sc.ACTIVATION_FOLLOWUP] == 8000
        assert bundle.timing_seconds[sc.ACTIVATION_FOLLOWUP] == 8.0
        for key in sc.TIMING_KEYS:
            assert key in bundle.timing_seconds
        assert bundle.timing_seconds[sc.ACTIVATION_INITIAL_SPEECH] == 15.0

    def test_activation_admission_bundle_never_mixes_revisions(self):
        state = session_state()
        state.apply_patch(0, {sc.ACTIVATION_FOLLOWUP: 4000})
        first = state.activation_admission_settings()
        state.apply_patch(1, {sc.ACTIVATION_FOLLOWUP: 8000})
        second = state.activation_admission_settings()
        assert first.settings_revision == 1
        assert second.settings_revision == 2
        assert first.effective_settings[sc.ACTIVATION_FOLLOWUP] == 4000
        assert first.timing_seconds[sc.ACTIVATION_FOLLOWUP] == 4.0
        assert second.effective_settings[sc.ACTIVATION_FOLLOWUP] == 8000
        assert second.timing_seconds[sc.ACTIVATION_FOLLOWUP] == 8.0

    def test_admission_bundle_vs_patch_is_atomically_ordered_20x(self):
        for _ in range(20):
            state = session_state()
            barrier = threading.Barrier(4)
            observed = []
            lock = threading.Lock()

            def patcher():
                try:
                    barrier.wait(timeout=10)
                except threading.BrokenBarrierError:
                    pass
                for i in range(50):
                    state.apply_patch(
                        state.settings_revision,
                        {sc.ACTIVATION_FOLLOWUP: 3000 + i},
                    )

            def reader():
                try:
                    barrier.wait(timeout=10)
                except threading.BrokenBarrierError:
                    pass
                for _ in range(50):
                    bundle = state.activation_admission_settings()
                    effective = bundle.effective_settings[
                        sc.ACTIVATION_FOLLOWUP
                    ]
                    timing_ms = int(round(
                        bundle.timing_seconds[sc.ACTIVATION_FOLLOWUP] * 1000
                    ))
                    with lock:
                        observed.append((effective, timing_ms))

            threads = [
                threading.Thread(target=patcher),
                threading.Thread(target=reader),
                threading.Thread(target=reader),
            ]

            def release():
                try:
                    barrier.wait(timeout=10)
                except threading.BrokenBarrierError:
                    pass

            starter = threading.Thread(target=release)
            for thread in threads:
                thread.start()
            starter.start()
            for thread in threads + [starter]:
                thread.join(timeout=30)

            assert observed
            # every observed bundle is internally consistent: the pair
            # effective/timing always describes exactly one settings revision.
            for effective, timing_ms in observed:
                assert effective == timing_ms, (effective, timing_ms)


# -- F4: persisted control data must be validated at startup --------------------

class TestStartupPersistenceValidation:
    def test_startup_rejects_out_of_range_persisted_control_value(self):
        with pytest.raises(ValueError):
            server_state(overlay={sc.ACTIVATION_FOLLOWUP: -999})

    def test_startup_rejects_conflicting_warning_and_initial_bundle(self):
        with pytest.raises(ValueError):
            server_state(overlay={
                sc.ACTIVATION_WATCHDOG_WARNING: 60000,
                sc.ACTIVATION_WATCHDOG_INITIAL: 60000,
            })

    def test_startup_rejects_negative_persisted_settings_revision(self):
        with pytest.raises(ValueError):
            server_state(revision=-1)

    def test_startup_rejects_boolean_persisted_settings_revision(self):
        with pytest.raises(ValueError):
            server_state(revision=True)

    def test_startup_rejects_non_object_settings_control_overlay(self):
        with pytest.raises(ValueError) as exc:
            server_state(overlay="not-an-object")
        # clear operator-readable error naming the control overlay section,
        # not a bare dict-construction accident
        assert "settingsControlOverlay" in str(exc.value)

    def test_startup_rejects_unknown_key_inside_settings_control_overlay(self):
        with pytest.raises(ValueError):
            server_state(overlay={"nonsense.key": 1})

    def test_startup_rejects_secret_key_inside_settings_control_overlay(self):
        secret_definition = sc.SettingDefinition(
            key="admin.secret",
            scope=sc.SCOPE_SERVER,
            auth=sc.AUTH_ADMIN,
            type=sc.TYPE_STRING,
            constraints={},
            default_value="",
            apply_policy=sc.APPLY_NEXT_SESSION,
            has_server_default=True,
            secret=True,
        )
        reg = sc.SettingsRegistry(
            [d for d in sc.builtin_definitions()] + [secret_definition]
        )
        with pytest.raises(ValueError):
            sc.ServerSettingsState(reg, overlay={"admin.secret": "x"})

    def test_valid_persisted_overlay_still_restores_values_and_revision(self):
        server = server_state(
            overlay={sc.ACTIVATION_FOLLOWUP: 8000},
            revision=3,
            persist=lambda overlay, revision: None,
        )
        assert server.settings_revision == 3
        assert server.server_effective()[sc.ACTIVATION_FOLLOWUP] == 8000
        assert server.server_effective()[sc.ACTIVATION_INITIAL_SPEECH] == 15000


# -- F5: persistence failure must not produce a half commit ----------------------

class TestServerSettingsCommitOnFailure:
    def test_failure_does_not_mutate_server_state(self):
        def fail_persist(overlay, revision):
            raise RuntimeError("disk full")

        server = server_state(persist=fail_persist)
        before_overlay = server.overlay()
        before_revision = server.settings_revision
        result = server.patch_server(0, {sc.ACTIVATION_FOLLOWUP: 8000})
        assert not result.accepted
        assert result.result == "internal_error"
        assert result.settings_revision == before_revision
        assert any(error.code == "persistence_failed" for error in result.errors)
        assert server.overlay() == before_overlay
        assert server.settings_revision == before_revision

    def test_retry_with_same_base_can_succeed_after_failure(self):
        calls = {"n": 0}

        def flaky(overlay, revision):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("disk full")

        server = server_state(persist=flaky)
        failed = server.patch_server(0, {sc.ACTIVATION_FOLLOWUP: 8000})
        assert not failed.accepted
        assert server.settings_revision == 0
        # retry with the SAME base revision after the store recovered
        ok = server.patch_server(0, {sc.ACTIVATION_FOLLOWUP: 8000})
        assert ok.accepted
        assert ok.settings_revision == 1
        assert server.settings_revision == 1
        assert server.server_effective()[sc.ACTIVATION_FOLLOWUP] == 8000

    def test_no_commit_gap_after_failure(self):
        calls = {"n": 0}

        def flaky(overlay, revision):
            calls["n"] += 1
            if calls["n"] == 3:
                raise RuntimeError("disk full")

        server = server_state(persist=flaky)
        assert server.patch_server(0, {sc.ACTIVATION_FOLLOWUP: 4000}).accepted
        assert server.patch_server(1, {sc.ACTIVATION_FOLLOWUP: 5000}).accepted
        assert server.settings_revision == 2
        failed = server.patch_server(2, {sc.ACTIVATION_FOLLOWUP: 9000})
        assert not failed.accepted
        assert server.settings_revision == 2
        # next revision after a successful retry is 3 - no gap, no lost value
        ok = server.patch_server(2, {sc.ACTIVATION_FOLLOWUP: 9000})
        assert ok.accepted
        assert ok.settings_revision == 3
        assert server.server_effective()[sc.ACTIVATION_FOLLOWUP] == 9000


if __name__ == "__main__":  # pragma: no cover
    import pytest
    raise SystemExit(pytest.main([__file__]))