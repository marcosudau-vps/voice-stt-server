"""The resumable release-state contract (AP-SRV-070 W5-R04).

Covers the new canonical order and its barriers - gates W5R4-G21 (tag before
the first public artifact), G22 (PyPI after the tag), G23 (Docker Hub before
GHCR), G28/G29 (same-version resume, never a version bump), G31 (GitHub
Release last), G18 (candidate binding).
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from release_support import make_manifest, make_state  # noqa: E402

from release_tooling.errors import OrderError, StateError  # noqa: E402
from release_tooling.state import (  # noqa: E402
    STATE_INDEX,
    STATE_ORDER,
    ReleaseState,
    advance,
    assert_aliases_allowed,
    assert_github_release_allowed,
    assert_public_publication_allowed,
    assert_tag_allowed,
    ensure_same_identity,
    ensure_same_version,
    load_state,
    save_state,
)
from release_tooling import rc_manifest  # noqa: E402


class StateOrderTests(unittest.TestCase):
    def test_the_canonical_order_is_exactly_the_w5_r04_order(self):
        self.assertEqual(
            STATE_ORDER,
            [
                "PREPARED",
                "TAGGED",
                "PYPI_PUBLISHED",
                "DOCKERHUB_PUBLISHED",
                "GHCR_PUBLISHED",
                "EXTERNAL_VERIFIED",
                "ALIASES_PUBLISHED",
                "GITHUB_RELEASED",
                "FINAL_VERIFIED",
                "COMPLETE",
            ],
        )

    def test_the_tag_precedes_every_public_artifact(self):
        # W5R4-G21/G22. Once 2.0.0 exists on PyPI the version is publicly
        # reserved, so the immutable source anchor must already exist.
        for public in ("PYPI_PUBLISHED", "DOCKERHUB_PUBLISHED", "GHCR_PUBLISHED"):
            with self.subTest(state=public):
                self.assertLess(STATE_INDEX["TAGGED"], STATE_INDEX[public])

    def test_dockerhub_precedes_ghcr(self):
        # W5R4-G23: GHCR is a promotion of the Docker Hub manifest, so it
        # cannot come first.
        self.assertLess(STATE_INDEX["DOCKERHUB_PUBLISHED"], STATE_INDEX["GHCR_PUBLISHED"])

    def test_aliases_follow_external_verification(self):
        # W5R4-G38: `latest` may only move once both registries verified.
        self.assertLess(STATE_INDEX["EXTERNAL_VERIFIED"], STATE_INDEX["ALIASES_PUBLISHED"])

    def test_github_release_is_the_last_public_step(self):
        # W5R4-G31/G32.
        self.assertLess(STATE_INDEX["ALIASES_PUBLISHED"], STATE_INDEX["GITHUB_RELEASED"])
        self.assertLess(STATE_INDEX["GITHUB_RELEASED"], STATE_INDEX["FINAL_VERIFIED"])
        self.assertEqual(STATE_ORDER[-1], "COMPLETE")


class AdvanceTests(unittest.TestCase):
    def test_advancing_one_step_at_a_time_walks_the_whole_order(self):
        state = make_state("PREPARED")
        for expected_next in STATE_ORDER[1:]:
            state = advance(state, expected_next)
            self.assertEqual(state.state, expected_next)

    def test_advancing_to_the_current_state_is_an_idempotent_resume(self):
        state = make_state("PYPI_PUBLISHED")
        history_before = len(state.history)
        self.assertIs(advance(state, "PYPI_PUBLISHED"), state)
        self.assertEqual(len(state.history), history_before)

    def test_skipping_a_state_is_refused(self):
        state = make_state("PREPARED")
        with self.assertRaises(OrderError):
            advance(state, "PYPI_PUBLISHED")

    def test_moving_backwards_is_refused(self):
        state = make_state("GHCR_PUBLISHED")
        with self.assertRaises(OrderError):
            advance(state, "PYPI_PUBLISHED")

    def test_an_unknown_state_is_refused(self):
        with self.assertRaises(OrderError):
            advance(make_state("PREPARED"), "PUBLISHED_SOMEWHERE")


class BarrierTests(unittest.TestCase):
    def test_the_tag_is_only_allowed_while_still_prepared(self):
        assert_tag_allowed(make_state("PREPARED"))
        for later in STATE_ORDER[1:]:
            with self.subTest(state=later):
                with self.assertRaises(OrderError):
                    assert_tag_allowed(make_state(later))

    def test_public_publication_is_blocked_before_the_tag(self):
        # W5R4-G21 enforced defensively, not only structurally.
        with self.assertRaises(OrderError) as caught:
            assert_public_publication_allowed(make_state("PREPARED"), "PyPI")
        self.assertIn("Git tag", str(caught.exception))

    def test_public_publication_is_allowed_from_tagged_onwards(self):
        for state_name in STATE_ORDER[STATE_INDEX["TAGGED"]:]:
            with self.subTest(state=state_name):
                assert_public_publication_allowed(make_state(state_name), "PyPI")

    def test_aliases_are_blocked_before_external_verification(self):
        # W5R4-G38: latest must never point at an unverified release.
        for state_name in STATE_ORDER[:STATE_INDEX["EXTERNAL_VERIFIED"]]:
            with self.subTest(state=state_name):
                with self.assertRaises(OrderError):
                    assert_aliases_allowed(make_state(state_name))
        assert_aliases_allowed(make_state("EXTERNAL_VERIFIED"))

    def test_github_release_is_blocked_before_aliases_are_published(self):
        # W5R4-G31.
        for state_name in STATE_ORDER[:STATE_INDEX["ALIASES_PUBLISHED"]]:
            with self.subTest(state=state_name):
                with self.assertRaises(OrderError):
                    assert_github_release_allowed(make_state(state_name))
        assert_github_release_allowed(make_state("ALIASES_PUBLISHED"))


class VersionAndIdentityTests(unittest.TestCase):
    def test_a_state_is_pinned_to_its_version(self):
        # W5R4-G29: a partially published 2.0.0 never becomes 2.0.1.
        state = make_state("PYPI_PUBLISHED")
        ensure_same_version(state, "2.0.0")
        with self.assertRaises(StateError) as caught:
            ensure_same_version(state, "2.0.1")
        self.assertIn("immutable", str(caught.exception))

    def test_resuming_the_same_candidate_passes(self):
        manifest = make_manifest()
        state = make_state("PYPI_PUBLISHED", manifest)
        identity = rc_manifest.state_identity(manifest)
        ensure_same_identity(
            state,
            source_commit=manifest["sourceCommit"],
            source_tree=manifest["sourceTree"],
            distributions=identity["distributions"],
            images=identity["images"],
            candidate=rc_manifest.candidate_identity(manifest),
        )

    def test_a_drifted_wheel_hash_fails_closed(self):
        manifest = make_manifest()
        state = make_state("PYPI_PUBLISHED", manifest)
        drifted = make_manifest()
        drifted["distributions"]["free"]["wheels"][0]["sha256"] = "0" * 64
        identity = rc_manifest.state_identity(drifted)
        with self.assertRaises(StateError) as caught:
            ensure_same_identity(
                state,
                source_commit=manifest["sourceCommit"],
                source_tree=manifest["sourceTree"],
                distributions=identity["distributions"],
                images=identity["images"],
            )
        self.assertIn("distributions", str(caught.exception))

    def test_a_drifted_image_digest_fails_closed(self):
        manifest = make_manifest()
        state = make_state("DOCKERHUB_PUBLISHED", manifest)
        drifted = make_manifest()
        drifted["images"]["pro"]["digest"] = "sha256:" + "9" * 64
        identity = rc_manifest.state_identity(drifted)
        with self.assertRaises(StateError):
            ensure_same_identity(
                state,
                source_commit=manifest["sourceCommit"],
                source_tree=manifest["sourceTree"],
                distributions=identity["distributions"],
                images=identity["images"],
            )

    def test_a_different_candidate_run_fails_closed(self):
        # W5R4-G18: resume must locate the *same* qualified candidate. A
        # second candidate build for the same version is a different candidate.
        manifest = make_manifest()
        state = make_state("PYPI_PUBLISHED", manifest)
        other = make_manifest(candidateId="gh-99999-1")
        identity = rc_manifest.state_identity(manifest)
        with self.assertRaises(StateError) as caught:
            ensure_same_identity(
                state,
                source_commit=manifest["sourceCommit"],
                source_tree=manifest["sourceTree"],
                distributions=identity["distributions"],
                images=identity["images"],
                candidate=rc_manifest.candidate_identity(other),
            )
        self.assertIn("candidate", str(caught.exception))

    def test_a_drifted_source_commit_fails_closed(self):
        manifest = make_manifest()
        state = make_state("TAGGED", manifest)
        identity = rc_manifest.state_identity(manifest)
        with self.assertRaises(StateError):
            ensure_same_identity(
                state,
                source_commit="0" * 40,
                source_tree=manifest["sourceTree"],
                distributions=identity["distributions"],
                images=identity["images"],
            )


class PersistenceTests(unittest.TestCase):
    def test_round_trip_preserves_every_binding(self):
        import tempfile

        state = make_state("GHCR_PUBLISHED")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2.0.0.json"
            save_state(path, state)
            reloaded = load_state(path)
        self.assertEqual(reloaded.state, "GHCR_PUBLISHED")
        self.assertEqual(reloaded.distributions, state.distributions)
        self.assertEqual(reloaded.images, state.images)
        self.assertEqual(reloaded.candidate, state.candidate)

    def test_a_corrupt_state_file_is_never_treated_as_absent(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2.0.0.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(StateError):
                load_state(path)

    def test_a_missing_state_file_is_none(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(load_state(Path(tmp) / "nothing.json"))

    def test_a_state_carrying_a_secret_is_refused(self):
        from release_tooling.errors import SecretDetectedError

        state = make_state("PREPARED")
        state.candidate["apiToken"] = "pypi-AgEIcHlwaS5vcmc-secret-value"
        with self.assertRaises(SecretDetectedError):
            state.to_json_dict()

    def test_the_persisted_document_names_both_distributions(self):
        payload = json.loads(json.dumps(make_state("PREPARED").to_json_dict()))
        self.assertEqual(
            payload["distributions"]["free"]["name"], "voice-stt-server"
        )
        self.assertEqual(
            payload["distributions"]["pro"]["name"], "voice-stt-server-pro"
        )

    def test_an_older_state_without_a_candidate_block_still_loads(self):
        payload = make_state("PREPARED").to_json_dict()
        payload.pop("candidate")
        restored = ReleaseState.from_json_dict(payload)
        self.assertEqual(restored.candidate, {})


if __name__ == "__main__":
    unittest.main()
