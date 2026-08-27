"""AP-SRV-050 - RuntimeConfigStore coexistence-format and write-preservation.

The runtime JSON document is shared by the legacy ``settings`` section and the
AP-SRV-050 ``settingsControlOverlay``/``settingsRevision`` sections plus every
unknown compatible top-level field. Each write family must preserve everything
it does not own, both directions, atomically and under one shared lock
(AP-SRV-050 prompt 22-26).
"""

import json
import threading

import pytest

from VoiceSTT_server.operations import RuntimeConfigStore
from api_fastapi_server import settings_control as sc


@pytest.fixture
def store(tmp_path):
    return RuntimeConfigStore(tmp_path / "runtime.json")


@pytest.fixture
def control(store):
    state = sc.ServerSettingsState(
        sc.build_default_registry(),
        persist=lambda overlay, revision: store.save_settings_control(
            overlay, revision
        ),
    )
    return store, state


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_legacy_patch_preserves_legacy_and_creates_overlay(control, tmp_path):
    store, state = control
    store.save({"language": "de", "model": "small"}, {"language", "model"})
    state.patch_server(0, {sc.ACTIVATION_FOLLOWUP: 8000})

    payload = read(tmp_path / "runtime.json")
    # legacy section unchanged
    assert payload["settings"] == {"language": "de", "model": "small"}
    # overlay/revision present
    assert payload["settingsControlOverlay"][sc.ACTIVATION_FOLLOWUP] == 8000
    assert payload["settingsRevision"] == 1


def test_legacy_save_preserves_overlay_and_revision(control, tmp_path):
    store, state = control
    state.patch_server(0, {sc.ACTIVATION_FOLLOWUP: 8000})
    store.save({"language": "fr", "model": "large-v3"},
               {"language", "model"})

    payload = read(tmp_path / "runtime.json")
    # overlay/revision unchanged
    assert payload["settingsControlOverlay"][sc.ACTIVATION_FOLLOWUP] == 8000
    assert payload["settingsRevision"] == 1
    # legacy updated
    assert payload["settings"] == {"language": "fr", "model": "large-v3"}


def test_restart_restores_overlay_and_revision(control, tmp_path):
    store, state = control
    state.patch_server(0, {sc.ACTIVATION_FOLLOWUP: 8000})

    reloaded = RuntimeConfigStore(tmp_path / "runtime.json")
    overlay, revision = reloaded.load_control()
    new_state = sc.ServerSettingsState(
        sc.build_default_registry(), overlay=overlay, revision=revision
    )
    assert new_state.settings_revision == 1
    assert new_state.server_effective()[sc.ACTIVATION_FOLLOWUP] == 8000
    assert new_state.server_effective()[sc.ACTIVATION_INITIAL_SPEECH] == 15000


def test_invalid_or_failed_patch_leaves_the_file_unchanged(control, tmp_path):
    store, state = control
    path = tmp_path / "runtime.json"
    store.save({"language": "de"}, {"language"})
    before = path.read_bytes()

    # invalid value -> rejected -> no persist call
    state.patch_server(0, {sc.ACTIVATION_WATCHDOG_INITIAL: -1})
    # stale base revision -> conflict -> no persist call
    state.patch_server(9, {sc.ACTIVATION_FOLLOWUP: 8000})
    # unknown key -> rejected -> no persist call
    state.patch_server(0, {"no.such.key": 1})

    assert path.read_bytes() == before
    assert read(path)["settings"] == {"language": "de"}


def test_no_change_patch_creates_no_churn(control, tmp_path):
    store, state = control
    store.save({"language": "de"}, {"language"})
    before = path = tmp_path / "runtime.json"
    first = path.read_bytes()
    result = state.patch_server(0, {sc.ACTIVATION_FOLLOWUP: 3000})
    assert result.accepted
    assert result.result == sc.RESULT_NO_CHANGE
    assert result.settings_revision == 0
    assert state.settings_revision == 0
    assert path.read_bytes() == first
    assert before.read_bytes() == first


def test_parallel_writes_are_atomic_and_lose_no_section(store, tmp_path):
    path = tmp_path / "runtime.json"
    store.save({"language": "de"}, {"language"})

    barrier = threading.Barrier(2)
    errors = []

    def legacy_write():
        try:
            barrier.wait(timeout=10)
        except threading.BrokenBarrierError:
            pass
        try:
            store.save({"language": "fr"}, {"language"})
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    def control_write():
        try:
            barrier.wait(timeout=10)
        except threading.BrokenBarrierError:
            pass
        try:
            store.save_settings_control(
                {sc.ACTIVATION_FOLLOWUP: 8000}, 1
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [
        threading.Thread(target=legacy_write),
        threading.Thread(target=control_write),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    assert errors == []
    payload = read(path)
    # valid JSON with both sections intact; nothing was lost on either side
    assert payload["settings"] == {"language": "fr"}
    assert payload["settingsControlOverlay"][sc.ACTIVATION_FOLLOWUP] == 8000
    assert payload["settingsRevision"] == 1


def test_unknown_top_level_fields_survive_both_write_families(store, tmp_path):
    path = tmp_path / "runtime.json"
    path.write_text(json.dumps({
        "version": 1,
        "updatedAt": "2026-08-27T00:00:00Z",
        "settings": {"language": "de"},
        "futureSection": {"a": 1},
    }), encoding="utf-8")

    store.save({"model": "small"}, {"model"})
    store.save_settings_control(
        {sc.ACTIVATION_FOLLOWUP: 8000}, 1
    )
    payload = read(path)
    assert payload["futureSection"] == {"a": 1}
    assert payload["settings"] == {"model": "small"}
    assert payload["settingsControlOverlay"][sc.ACTIVATION_FOLLOWUP] == 8000


def test_parallel_writes_against_separate_instances_lose_no_section(tmp_path):
    path = tmp_path / "runtime.json"
    RuntimeConfigStore(path).save({"language": "de"}, {"language"})

    barrier = threading.Barrier(2)
    errors = []

    def legacy_write():
        try:
            barrier.wait(timeout=10)
        except threading.BrokenBarrierError:
            pass
        try:
            RuntimeConfigStore(path).save({"language": "fr"}, {"language"})
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    def control_write():
        try:
            barrier.wait(timeout=10)
        except threading.BrokenBarrierError:
            pass
        try:
            RuntimeConfigStore(path).save_settings_control(
                {sc.ACTIVATION_FOLLOWUP: 8000}, 1
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [
        threading.Thread(target=legacy_write),
        threading.Thread(target=control_write),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    assert errors == []
    payload = read(path)
    assert payload["settings"] == {"language": "fr"}
    assert payload["settingsControlOverlay"][sc.ACTIVATION_FOLLOWUP] == 8000
    assert payload["settingsRevision"] == 1


# -- F4: persisted control data fails fast on startup ----------------------------

def write_runtime(tmp_path, payload):
    path = tmp_path / "runtime.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_control_rejects_negative_persisted_settings_revision(tmp_path):
    path = write_runtime(tmp_path, {
        "settingsControlOverlay": {}, "settingsRevision": -1
    })
    with pytest.raises(ValueError):
        RuntimeConfigStore(path).load_control()


def test_load_control_rejects_boolean_persisted_settings_revision(tmp_path):
    path = write_runtime(tmp_path, {
        "settingsControlOverlay": {}, "settingsRevision": True
    })
    with pytest.raises(ValueError):
        RuntimeConfigStore(path).load_control()


def test_load_control_rejects_non_object_settings_control_overlay(tmp_path):
    path = write_runtime(tmp_path, {
        "settingsControlOverlay": "not-an-object", "settingsRevision": 1
    })
    with pytest.raises(ValueError):
        RuntimeConfigStore(path).load_control()


def test_load_control_accepts_missing_control_sections(tmp_path):
    path = write_runtime(tmp_path, {"version": 1, "settings": {}})
    overlay, revision = RuntimeConfigStore(path).load_control()
    assert overlay == {}
    assert revision == 0


def test_valid_persisted_control_restores_values_and_revision(tmp_path):
    path = write_runtime(tmp_path, {
        "settingsControlOverlay": {sc.ACTIVATION_FOLLOWUP: 8000},
        "settingsRevision": 3,
    })
    overlay, revision = RuntimeConfigStore(path).load_control()
    assert revision == 3
    assert overlay[sc.ACTIVATION_FOLLOWUP] == 8000


# -- F5: persistence failure must stay atomic and replaceable --------------------

def test_os_replace_failure_keeps_original_runtime_json(tmp_path, monkeypatch):
    import os

    path = tmp_path / "runtime.json"
    RuntimeConfigStore(path).save({"language": "de"}, {"language"})
    original = path.read_bytes()

    def failing_replace(source, destination):
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", failing_replace)
    with pytest.raises(OSError):
        RuntimeConfigStore(path).save({"language": "fr"}, {"language"})

    assert path.read_bytes() == original
    # no lingering temporary file
    leftovers = list(path.parent.glob(f".{path.name}.*.tmp"))
    assert leftovers == []


def test_startup_rejects_bad_validated_control_via_service_shape(tmp_path):
    """Cross-check: a persisted out-of-range value reaches no live state."""
    path = write_runtime(tmp_path, {
        "settingsControlOverlay": {sc.ACTIVATION_FOLLOWUP: -999},
        "settingsRevision": 1,
    })
    overlay, revision = RuntimeConfigStore(path).load_control()
    with pytest.raises(ValueError):
        sc.ServerSettingsState(
            sc.build_default_registry(), overlay=overlay, revision=revision
        )