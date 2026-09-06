"""AP-SRV-070 W5: the resumable release-state contract.

Covers: fixed monotonic order, idempotent resume, version immutability once
a state exists, artifact-identity immutability, corrupted-state handling,
and the Git-tag / GitHub-Release barriers.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from release_tooling.errors import OrderError, StateError
from release_tooling.state import (
    STATE_ORDER,
    ReleaseState,
    advance,
    assert_github_release_allowed,
    assert_tag_allowed,
    ensure_same_identity,
    ensure_same_version,
    load_state,
    new_state,
    save_state,
)


def _sample_state(**overrides) -> ReleaseState:
    kwargs = dict(
        version="2.0.0",
        source_commit="a" * 40,
        source_tree="b" * 40,
        wheel={"filename": "voicestt-2.0.0-py3-none-any.whl", "sha256": "c" * 64},
        sdist={"filename": "voicestt-2.0.0.tar.gz", "sha256": "d" * 64},
        free_image={"tag": "voice-stt-server:2.0.0", "imageId": "sha256:" + "e" * 64},
        pro_image={"tag": "voice-stt-server-pro:2.0.0", "imageId": "sha256:" + "f" * 64},
    )
    kwargs.update(overrides)
    return new_state(**kwargs)


class StateOrderTests(unittest.TestCase):
    def test_new_state_starts_at_prepared(self):
        state = _sample_state()
        self.assertEqual(state.state, "PREPARED")
        self.assertEqual(state.history[-1]["state"], "PREPARED")

    def test_advance_walks_the_fixed_order_one_step_at_a_time(self):
        state = _sample_state()
        for expected_next in STATE_ORDER[1:]:
            state = advance(state, expected_next)
            self.assertEqual(state.state, expected_next)

    def test_advance_to_the_current_state_is_an_idempotent_no_op(self):
        state = _sample_state()
        resumed = advance(state, "PREPARED")
        self.assertEqual(resumed.state, "PREPARED")
        self.assertEqual(len(resumed.history), 1)

    def test_advance_cannot_skip_ahead(self):
        state = _sample_state()
        with self.assertRaises(OrderError):
            advance(state, "TAGGED")

    def test_advance_cannot_move_backwards(self):
        state = _sample_state()
        state = advance(state, "PYPI_PUBLISHED")
        with self.assertRaises(OrderError):
            advance(state, "PREPARED")

    def test_advance_rejects_an_unknown_state_name(self):
        state = _sample_state()
        with self.assertRaises(OrderError):
            advance(state, "NOT_A_REAL_STATE")


class TagAndReleaseBarrierTests(unittest.TestCase):
    def test_tag_blocked_before_external_verification(self):
        state = _sample_state()
        for intermediate in ("PYPI_PUBLISHED", "GHCR_PUBLISHED", "DOCKERHUB_PUBLISHED"):
            state = advance(state, intermediate)
            with self.assertRaises(OrderError):
                assert_tag_allowed(state)

    def test_tag_allowed_once_externally_verified(self):
        state = _sample_state()
        for intermediate in ("PYPI_PUBLISHED", "GHCR_PUBLISHED", "DOCKERHUB_PUBLISHED", "EXTERNAL_VERIFIED"):
            state = advance(state, intermediate)
        assert_tag_allowed(state)  # must not raise

    def test_github_release_blocked_before_tag(self):
        state = _sample_state()
        for intermediate in ("PYPI_PUBLISHED", "GHCR_PUBLISHED", "DOCKERHUB_PUBLISHED", "EXTERNAL_VERIFIED"):
            state = advance(state, intermediate)
        with self.assertRaises(OrderError):
            assert_github_release_allowed(state)

    def test_github_release_allowed_once_tagged(self):
        state = _sample_state()
        for intermediate in ("PYPI_PUBLISHED", "GHCR_PUBLISHED", "DOCKERHUB_PUBLISHED", "EXTERNAL_VERIFIED", "TAGGED"):
            state = advance(state, intermediate)
        assert_github_release_allowed(state)  # must not raise


class VersionAndIdentityImmutabilityTests(unittest.TestCase):
    def test_ensure_same_version_passes_for_a_matching_version(self):
        state = _sample_state()
        ensure_same_version(state, "2.0.0")  # must not raise

    def test_ensure_same_version_rejects_a_different_version(self):
        state = _sample_state()
        with self.assertRaises(StateError):
            ensure_same_version(state, "2.0.1")

    def test_ensure_same_identity_passes_for_matching_artifacts(self):
        state = _sample_state()
        ensure_same_identity(
            state,
            source_commit="a" * 40,
            source_tree="b" * 40,
            wheel={"filename": "voicestt-2.0.0-py3-none-any.whl", "sha256": "c" * 64},
            sdist={"filename": "voicestt-2.0.0.tar.gz", "sha256": "d" * 64},
            free_image={"tag": "voice-stt-server:2.0.0", "imageId": "sha256:" + "e" * 64},
            pro_image={"tag": "voice-stt-server-pro:2.0.0", "imageId": "sha256:" + "f" * 64},
        )

    def test_ensure_same_identity_rejects_a_mismatched_wheel_hash(self):
        state = _sample_state()
        with self.assertRaises(StateError):
            ensure_same_identity(
                state,
                source_commit="a" * 40,
                source_tree="b" * 40,
                wheel={"filename": "voicestt-2.0.0-py3-none-any.whl", "sha256": "0" * 64},
                sdist={"filename": "voicestt-2.0.0.tar.gz", "sha256": "d" * 64},
                free_image={"tag": "voice-stt-server:2.0.0", "imageId": "sha256:" + "e" * 64},
                pro_image={"tag": "voice-stt-server-pro:2.0.0", "imageId": "sha256:" + "f" * 64},
            )


class PersistenceTests(unittest.TestCase):
    def test_load_state_returns_none_when_no_file_exists(self):
        with TemporaryDirectory() as tmp:
            self.assertIsNone(load_state(Path(tmp) / "does-not-exist.json"))

    def test_save_then_load_round_trips(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            state = _sample_state()
            state = advance(state, "PYPI_PUBLISHED")
            save_state(path, state)
            reloaded = load_state(path)
            self.assertEqual(reloaded.state, "PYPI_PUBLISHED")
            self.assertEqual(reloaded.version, "2.0.0")
            self.assertEqual(len(reloaded.history), 2)

    def test_load_state_raises_on_corrupted_json(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text("{not valid json", encoding="utf-8")
            with self.assertRaises(StateError):
                load_state(path)

    def test_load_state_raises_when_required_fields_are_missing(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text('{"version": "2.0.0"}', encoding="utf-8")
            with self.assertRaises(StateError):
                load_state(path)

    def test_repeat_save_is_idempotent_and_does_not_duplicate_history(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            state = _sample_state()
            save_state(path, state)
            save_state(path, state)
            reloaded = load_state(path)
            self.assertEqual(len(reloaded.history), 1)


if __name__ == "__main__":
    unittest.main()
