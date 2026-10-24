import threading
import time
from types import SimpleNamespace

import pytest

from voice_stt_server.models.downloads import DownloadJobManager, ModelManagementError


def wait_job(manager, job_id, state):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        result = manager.snapshot(job_id)
        if result["state"] == state:
            return result
        time.sleep(.005)
    pytest.fail(str(manager.snapshot(job_id)))


def queue(install=None, limit=128):
    calls = []
    completed = []
    events = []

    def default_install(product, transition, progress):
        calls.append(product.id)
        progress(5)
        transition("verifying")
        transition("installing")

    manager = DownloadJobManager(
        gate=lambda model: SimpleNamespace(id=model, engine="faster_whisper", bytes=5),
        installed=lambda product: product.id in completed,
        install=install or default_install,
        completed=lambda: completed.append(calls[-1]) if calls else None,
        emit=lambda event, **data: events.append((event, data)), limit=limit)
    return manager, calls, events


def test_dedupe_merges_origins_and_queued_only_cancel():
    manager, calls, events = queue()
    first, created = manager.enqueue("a", "automatic")
    second, duplicate = manager.enqueue("a")
    assert created and not duplicate
    assert first["jobId"] == second["jobId"]
    assert second["origins"] == ["automatic", "manual"]
    manager.deselect([])
    assert manager.snapshot(first["jobId"])["state"] == "queued"
    assert manager.cancel(first["jobId"])["state"] == "cancelled"
    with pytest.raises(ModelManagementError, match="already_started"):
        manager.cancel(first["jobId"])
    assert not calls


def test_deselection_cancels_only_queued_pure_automatic_jobs():
    manager, _, _ = queue()
    first, _ = manager.enqueue("a", "automatic")
    second, _ = manager.enqueue("b")
    manager.deselect([])
    assert manager.snapshot(first["jobId"])["state"] == "cancelled"
    assert manager.snapshot(second["jobId"])["state"] == "queued"


@pytest.mark.parametrize("blocked_state", ["downloading", "verifying", "installing"])
def test_started_job_cannot_cancel_and_survives_deselection(blocked_state):
    entered, release = threading.Event(), threading.Event()

    def install(product, transition, progress):
        if blocked_state != "downloading":
            transition("verifying")
        if blocked_state == "installing":
            transition("installing")
        entered.set()
        assert release.wait(3)
        if blocked_state == "downloading":
            transition("verifying")
        if blocked_state != "installing":
            transition("installing")

    manager, _, _ = queue(install)
    job, _ = manager.enqueue("a", "automatic")
    manager.start()
    try:
        assert entered.wait(3)
        manager.deselect([])
        with pytest.raises(ModelManagementError, match="already_started"):
            manager.cancel(job["jobId"])
        release.set()
        wait_job(manager, job["jobId"], "completed")
    finally:
        release.set()
        manager.stop()


def test_one_transfer_and_atomic_start_cancel_race():
    entered, release = threading.Event(), threading.Event()
    executing = []

    def install(product, transition, progress):
        executing.append(product.id)
        entered.set()
        assert release.wait(3)
        transition("verifying")
        transition("installing")

    manager, _, _ = queue(install)
    a, _ = manager.enqueue("a")
    b, _ = manager.enqueue("b")
    manager.start()
    try:
        assert entered.wait(3)
        manager.cancel(b["jobId"])
        assert executing == ["a"]
        release.set()
        wait_job(manager, a["jobId"], "completed")
        assert executing == ["a"]
    finally:
        release.set()
        manager.stop()


def test_failure_is_redacted_has_no_retry_and_history_is_bounded():
    def install(*args):
        raise RuntimeError("secret https://private.example credential path")

    manager, _, events = queue(install, limit=2)
    manager.start()
    try:
        for name in "abc":
            job, _ = manager.enqueue(name)
            result = wait_job(manager, job["jobId"], "failed")
            assert result["errorCode"] == "download_failed"
        assert len(manager.snapshot()) == 2
        assert "secret" not in str(manager.snapshot()) + str(events)
        assert len([event for event, _ in events if event.endswith("started")]) == 3
    finally:
        manager.stop()


def test_pending_queue_capacity_and_unknown_ids():
    manager, _, _ = queue(limit=1)
    manager.enqueue("a")
    with pytest.raises(ModelManagementError, match="queue_full"):
        manager.enqueue("b")
    for operation in (manager.snapshot, manager.cancel):
        with pytest.raises(ModelManagementError) as error:
            operation("missing")
        assert error.value.status == 404


def test_product_gate_runs_before_job_and_again_before_execution():
    manager, _, _ = queue()
    job, _ = manager.enqueue("a")
    manager._gate = lambda model: (_ for _ in ()).throw(ModelManagementError("rights_missing", 422))
    with pytest.raises(ModelManagementError, match="rights_missing"):
        manager.enqueue("b")
    assert len(manager.snapshot()) == 1
    manager.start()
    try:
        assert wait_job(manager, job["jobId"], "failed")["errorCode"] == "rights_missing"
    finally:
        manager.stop()


def test_restart_drops_manual_jobs_and_progress_is_not_persisted():
    manager, _, _ = queue()
    manager.enqueue("a")
    replacement, _, _ = queue()
    assert replacement.snapshot() == []


def test_terminal_job_does_not_duplicate_an_installed_model():
    manager, calls, events = queue()
    job, _ = manager.enqueue("a")
    manager.start()
    try:
        result = wait_job(manager, job["jobId"], "completed")
        assert result["downloadedBytes"] == 5 and result["percent"] == 100
        duplicate, created = manager.enqueue("a")
        assert not created and duplicate["alreadyInstalled"]
        assert calls == ["a"]
        assert [event for event, _ in events] == [
            "stt.download.queued", "stt.download.started", "stt.download.completed"]
    finally:
        manager.stop()
