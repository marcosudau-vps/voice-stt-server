import hashlib
import os
from pathlib import Path
import threading
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from voice_stt_server.models.downloads import ModelManagementError
from voice_stt_server.models.storage import (
    ArtifactFile, VerifiedModelStorage, _Redirects, safe_name, tree_signature,
)


def product(directory=False):
    payload = b"model"
    digest = hashlib.sha256(payload).hexdigest()
    return SimpleNamespace(id="a", filename="model-a" if directory else "a.data",
                           artifact_kind="directory" if directory else "file",
                           sha256=digest, bytes=5, source="fixture://model",
                           source_identity="fixture://model",
                           files=(ArtifactFile("model.bin", digest, 5),))


@pytest.mark.parametrize("directory", [False, True])
def test_verified_install_is_atomic_and_tracks_real_states(tmp_path, directory):
    entry = product(directory)
    transitions, progress = [], []
    target = tmp_path / entry.filename

    def fetch(source, path):
        assert not target.exists()
        path.write_bytes(b"model")
        return source

    storage = VerifiedModelStorage(threading.RLock(), fetcher=fetch)
    storage.install(entry, tmp_path, transitions.append, progress.append, lambda model: entry)
    assert target.exists()
    assert transitions == ["verifying", "installing"] and progress == [5]
    assert list(tmp_path.glob(".*.part")) == []


@pytest.mark.parametrize("failure", ["size", "hash", "source", "rights", "commit"])
def test_failed_install_has_no_visible_partial_or_leftovers(tmp_path, failure):
    entry = product()

    def fetch(source, path):
        path.write_bytes(b"other" if failure == "hash" else b"bad" if failure == "size" else b"model")
        return "fixture://other" if failure == "source" else source

    def gate(model):
        if failure == "rights":
            raise ModelManagementError("rights_missing", 422)

    storage = VerifiedModelStorage(threading.RLock(), fetcher=fetch)
    with patch("voice_stt_server.models.storage.os.replace", side_effect=OSError("commit")) if failure == "commit" else __import__('contextlib').nullcontext():
        with pytest.raises((ModelManagementError, OSError)):
            storage.install(entry, tmp_path, lambda state: None, lambda count: None, gate)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("name", ["../model", "/model", "a/b", "a\\b", "a:stream", ".", "..", "NUL", "COM1.bin", "model."])
def test_unsafe_names_are_rejected(name):
    with pytest.raises(ModelManagementError):
        safe_name(name)


def test_external_directory_is_never_a_delete_target(tmp_path):
    external = tmp_path / "external"
    external.mkdir()
    target = external / "model"
    target.write_bytes(b"model")
    root = tmp_path / "managed"
    root.mkdir()
    storage = VerifiedModelStorage(threading.RLock())
    with pytest.raises(ModelManagementError, match="not_managed"):
        storage.delete(target, root, lambda: None)
    assert target.read_bytes() == b"model"


def test_hardlinks_are_rejected_before_mutation(tmp_path):
    original = tmp_path / "original"
    original.write_bytes(b"model")
    root = tmp_path / "managed"
    root.mkdir()
    linked = root / "a.data"
    os.link(original, linked)
    with pytest.raises(ModelManagementError, match="unsafe_storage_link"):
        VerifiedModelStorage(threading.RLock()).delete(linked, root, lambda: None)
    assert linked.exists() and original.exists()


def test_symlink_root_and_tree_are_refused(tmp_path):
    external = tmp_path / "external"
    external.mkdir()
    link = tmp_path / "managed"
    try:
        link.symlink_to(external, target_is_directory=True)
    except OSError:
        pytest.skip("host does not permit unprivileged symlinks")
    storage = VerifiedModelStorage(threading.RLock())
    with pytest.raises(ModelManagementError, match="unsafe_storage_link"):
        storage.cleanup(link)
    assert list(external.iterdir()) == []


def test_delete_guard_is_rechecked_after_quarantine_and_rollback(tmp_path):
    target = tmp_path / "a.data"
    target.write_bytes(b"model")
    calls = []

    def guard():
        calls.append(True)
        if len(calls) == 2:
            raise ModelManagementError("installation_in_use")

    with pytest.raises(ModelManagementError, match="in_use"):
        VerifiedModelStorage(threading.RLock()).delete(target, tmp_path, guard)
    assert target.read_bytes() == b"model"
    assert list(tmp_path.iterdir()) == [target]


def test_restart_cleanup_removes_only_owned_partial_names(tmp_path):
    owned = tmp_path / (".a.data." + "a" * 32 + ".part")
    owned.write_bytes(b"partial")
    unrelated = tmp_path / "external.part"
    unrelated.write_bytes(b"untouched")
    installed = tmp_path / "a.data"
    installed.write_bytes(b"model")
    VerifiedModelStorage(threading.RLock()).cleanup(tmp_path)
    assert not owned.exists()
    assert unrelated.exists() and installed.exists()


@pytest.mark.parametrize("url", ["http://huggingface.co/x", "https://evil.invalid/model", "https://huggingface.co@evil.invalid/x", "https://huggingface.co:444/x", "file:///tmp/model", "https://127.0.0.1/model"])
def test_redirect_is_refused_before_contact(url):
    with pytest.raises(ModelManagementError, match="source_rejected"):
        _Redirects().redirect_request(None, None, 302, "redirect", {}, url)
