"""AP-SRV-070 W5-R01-C1: the shared release engine (real publish and
dry-run walk the exact same operation graph/state machine).

Every adapter here is a fake test double - no test in this module makes a
real network/subprocess call. This is where the Root Review-mandated
resume, reconciliation, conflict-fail-closed, and dry-run-zero-write
scenarios are proven.
"""

from __future__ import annotations

import unittest

from release_tooling.engine import STEP_DEFINITIONS, ExecutionMode, plan_from, run_engine
from release_tooling.errors import ConflictError, VerificationUnavailableError
from release_tooling.remote_checks import ABSENT, MATCH
from release_tooling.state import STATE_ORDER, ReleaseState, advance, load_state, new_state, save_state

ALL_KEYS = [s.key for s in STEP_DEFINITIONS if s.key != "complete"]


class FakeAdapter:
    """A test double: pops one entry per ``verify()`` call; raises it if
    it is an exception instance, else returns it. ``publish()`` just
    counts calls unless overridden."""

    def __init__(self, name: str, verify_sequence):
        self.name = name
        self._sequence = list(verify_sequence)
        self.publish_calls = 0
        self.publish_args = []

    def verify(self, manifest, state):
        if not self._sequence:
            raise AssertionError(f"{self.name}.verify() called more times than the test expected")
        result = self._sequence.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def publish(self, manifest, state):
        self.publish_calls += 1
        self.publish_args.append((manifest, state))


class PoisonedAdapter(FakeAdapter):
    """Fails the test immediately if ``publish()`` is ever called - used to
    prove dry-run structurally never writes anything."""

    def publish(self, manifest, state):
        raise AssertionError(f"{self.name}.publish() must never be called in dry-run")


def _manifest(**overrides):
    manifest = {
        "productVersion": "2.0.0",
        "sourceCommit": "a" * 40,
        "sourceTree": "b" * 40,
        "wheel": {"filename": "voicestt-2.0.0-py3-none-any.whl", "sha256": "c" * 64},
        "sdist": {"filename": "voicestt-2.0.0.tar.gz", "sha256": "d" * 64},
        "images": {
            "free": {"tag": "voice-stt-server:2.0.0", "imageId": "sha256:" + "e" * 64},
            "pro": {"tag": "voice-stt-server-pro:2.0.0", "imageId": "sha256:" + "f" * 64},
        },
    }
    manifest.update(overrides)
    return manifest


def _state(state_name: str = "PREPARED"):
    result = new_state(
        version="2.0.0",
        source_commit="a" * 40,
        source_tree="b" * 40,
        wheel={"filename": "voicestt-2.0.0-py3-none-any.whl", "sha256": "c" * 64},
        sdist={"filename": "voicestt-2.0.0.tar.gz", "sha256": "d" * 64},
        free_image={"tag": "voice-stt-server:2.0.0", "imageId": "sha256:" + "e" * 64},
        pro_image={"tag": "voice-stt-server-pro:2.0.0", "imageId": "sha256:" + "f" * 64},
    )
    for target in STATE_ORDER[1:STATE_ORDER.index(state_name) + 1]:
        result = advance(result, target)
    return result


def _all_absent_then_match_adapters():
    return {
        "pypi": FakeAdapter("pypi", [ABSENT, MATCH]),
        "ghcr": FakeAdapter("ghcr", [ABSENT, MATCH]),
        "dockerhub": FakeAdapter("dockerhub", [ABSENT, MATCH]),
        "external_verification": FakeAdapter("external_verification", [MATCH]),
        "git_tag": FakeAdapter("git_tag", [ABSENT, MATCH]),
        "github_release": FakeAdapter("github_release", [ABSENT, MATCH]),
        "final_verification": FakeAdapter("final_verification", [MATCH]),
    }


class SharedGraphTests(unittest.TestCase):
    def test_plan_from_prepared_lists_every_step_in_fixed_order(self):
        steps = plan_from("PREPARED")
        self.assertEqual([s.key for s in steps], ALL_KEYS + ["complete"])

    def test_dry_run_and_real_walk_the_same_step_definitions(self):
        # Both modes call plan_from() internally with no branching on mode
        # anywhere in STEP_DEFINITIONS itself - this is the structural half
        # of "same operation graph"; the behavioral half is proven by the
        # zero-write tests below.
        real_result = run_engine(_state(), _manifest(), mode=ExecutionMode.REAL, adapters=_all_absent_then_match_adapters())
        dry_result = run_engine(_state(), _manifest(), mode=ExecutionMode.DRY_RUN, adapters=_all_absent_then_match_adapters())
        self.assertEqual([o.stepKey for o in real_result.outcomes], [o.stepKey for o in dry_result.outcomes])


class DryRunNeverWritesTests(unittest.TestCase):
    def _poisoned_adapters(self):
        return {key: PoisonedAdapter(key, [ABSENT]) for key in ALL_KEYS}

    def test_dry_run_never_calls_publish_on_any_adapter(self):
        result = run_engine(_state(), _manifest(), mode=ExecutionMode.DRY_RUN, adapters=self._poisoned_adapters())
        self.assertFalse(result.stoppedEarly)
        self.assertEqual(result.finalState.state, "PREPARED")  # never advanced

    def test_dry_run_never_persists_state(self):
        persisted = []
        result = run_engine(
            _state(), _manifest(), mode=ExecutionMode.DRY_RUN, adapters=self._poisoned_adapters(), persist=persisted.append
        )
        self.assertEqual(persisted, [])
        self.assertFalse(result.stoppedEarly)

    def test_dry_run_reports_every_step_as_planned_or_pending(self):
        result = run_engine(_state(), _manifest(), mode=ExecutionMode.DRY_RUN, adapters=self._poisoned_adapters())
        actions = {o.stepKey: o.action for o in result.outcomes}
        self.assertEqual(actions["pypi"], "planned")
        self.assertEqual(actions["ghcr"], "planned")
        self.assertEqual(actions["dockerhub"], "planned")
        self.assertEqual(actions["external_verification"], "pending")  # ABSENT -> not yet satisfied
        self.assertEqual(actions["git_tag"], "planned")
        self.assertEqual(actions["github_release"], "planned")
        self.assertEqual(actions["final_verification"], "pending")
        self.assertEqual(actions["complete"], "planned")


class RealFullSuccessTests(unittest.TestCase):
    def test_full_success_path_reaches_complete(self):
        adapters = _all_absent_then_match_adapters()
        result = run_engine(_state(), _manifest(), mode=ExecutionMode.REAL, adapters=adapters)
        self.assertFalse(result.stoppedEarly)
        self.assertEqual(result.finalState.state, "COMPLETE")
        self.assertEqual(adapters["pypi"].publish_calls, 1)
        self.assertEqual(adapters["ghcr"].publish_calls, 1)
        self.assertEqual(adapters["dockerhub"].publish_calls, 1)
        self.assertEqual(adapters["git_tag"].publish_calls, 1)
        self.assertEqual(adapters["github_release"].publish_calls, 1)

    def test_full_success_path_persists_after_every_step(self):
        persisted = []
        run_engine(_state(), _manifest(), mode=ExecutionMode.REAL, adapters=_all_absent_then_match_adapters(), persist=persisted.append)
        # 8 transitions: PREPARED->...->COMPLETE
        self.assertEqual(len(persisted), 8)
        self.assertEqual(persisted[-1].state, "COMPLETE")


class ResumeAfterPartialSuccessTests(unittest.TestCase):
    """AP-SRV-070 W5-R01-C1, section 8: resume after each partial failure point."""

    def test_resume_after_pypi_success_ghcr_failure(self):
        # PyPI already MATCH (published in a prior run); GHCR/Docker Hub not yet.
        adapters = {
            "pypi": FakeAdapter("pypi", [MATCH]),
            "ghcr": FakeAdapter("ghcr", [ABSENT, MATCH]),
            "dockerhub": FakeAdapter("dockerhub", [ABSENT, MATCH]),
            "external_verification": FakeAdapter("external_verification", [MATCH]),
            "git_tag": FakeAdapter("git_tag", [ABSENT, MATCH]),
            "github_release": FakeAdapter("github_release", [ABSENT, MATCH]),
            "final_verification": FakeAdapter("final_verification", [MATCH]),
        }
        result = run_engine(_state(), _manifest(), mode=ExecutionMode.REAL, adapters=adapters)
        self.assertFalse(result.stoppedEarly)
        self.assertEqual(adapters["pypi"].publish_calls, 0)  # never re-uploaded
        self.assertEqual(result.finalState.state, "COMPLETE")

    def test_resume_starts_at_ghcr_when_state_already_says_pypi_published(self):
        adapters = {
            "ghcr": FakeAdapter("ghcr", [ABSENT, MATCH]),
            "dockerhub": FakeAdapter("dockerhub", [ABSENT, MATCH]),
            "external_verification": FakeAdapter("external_verification", [MATCH]),
            "git_tag": FakeAdapter("git_tag", [ABSENT, MATCH]),
            "github_release": FakeAdapter("github_release", [ABSENT, MATCH]),
            "final_verification": FakeAdapter("final_verification", [MATCH]),
        }
        result = run_engine(_state("PYPI_PUBLISHED"), _manifest(), mode=ExecutionMode.REAL, adapters=adapters)
        self.assertEqual([o.stepKey for o in result.outcomes][0], "ghcr")
        self.assertEqual(result.finalState.state, "COMPLETE")

    def test_resume_after_ghcr_success_dockerhub_failure(self):
        adapters = {
            "dockerhub": FakeAdapter("dockerhub", [ABSENT, MATCH]),
            "external_verification": FakeAdapter("external_verification", [MATCH]),
            "git_tag": FakeAdapter("git_tag", [ABSENT, MATCH]),
            "github_release": FakeAdapter("github_release", [ABSENT, MATCH]),
            "final_verification": FakeAdapter("final_verification", [MATCH]),
        }
        result = run_engine(_state("GHCR_PUBLISHED"), _manifest(), mode=ExecutionMode.REAL, adapters=adapters)
        self.assertFalse(result.stoppedEarly)
        self.assertEqual(result.finalState.state, "COMPLETE")

    def test_resume_after_dockerhub_success_starts_at_external_verification(self):
        adapters = {
            "external_verification": FakeAdapter("external_verification", [MATCH]),
            "git_tag": FakeAdapter("git_tag", [ABSENT, MATCH]),
            "github_release": FakeAdapter("github_release", [ABSENT, MATCH]),
            "final_verification": FakeAdapter("final_verification", [MATCH]),
        }
        result = run_engine(_state("DOCKERHUB_PUBLISHED"), _manifest(), mode=ExecutionMode.REAL, adapters=adapters)
        self.assertEqual([o.stepKey for o in result.outcomes][0], "external_verification")
        self.assertEqual(result.finalState.state, "COMPLETE")

    def test_resume_after_external_verification_may_proceed_to_tag(self):
        adapters = {
            "git_tag": FakeAdapter("git_tag", [ABSENT, MATCH]),
            "github_release": FakeAdapter("github_release", [ABSENT, MATCH]),
            "final_verification": FakeAdapter("final_verification", [MATCH]),
        }
        result = run_engine(_state("EXTERNAL_VERIFIED"), _manifest(), mode=ExecutionMode.REAL, adapters=adapters)
        self.assertEqual(result.outcomes[0].stepKey, "git_tag")
        self.assertEqual(result.outcomes[0].action, "published")
        self.assertEqual(result.finalState.state, "COMPLETE")

    def test_resume_after_tag_verifies_existing_tag_and_continues_to_release(self):
        adapters = {
            "git_tag": FakeAdapter("git_tag", [MATCH]),  # already tagged
            "github_release": FakeAdapter("github_release", [ABSENT, MATCH]),
            "final_verification": FakeAdapter("final_verification", [MATCH]),
        }
        result = run_engine(_state("EXTERNAL_VERIFIED"), _manifest(), mode=ExecutionMode.REAL, adapters=adapters)
        self.assertEqual(adapters["git_tag"].publish_calls, 0)  # resumed, not re-created
        self.assertEqual(result.finalState.state, "COMPLETE")

    def test_resume_after_github_release_verifies_existing_release_and_finishes(self):
        adapters = {
            "final_verification": FakeAdapter("final_verification", [MATCH]),
        }
        result = run_engine(_state("GITHUB_RELEASED"), _manifest(), mode=ExecutionMode.REAL, adapters=adapters)
        self.assertFalse(result.stoppedEarly)
        self.assertEqual(result.finalState.state, "COMPLETE")


class StaleLocalStateReconciliationTests(unittest.TestCase):
    """AP-SRV-070 W5-R01-C1, section 8.7: an external operation succeeded
    but local state never advanced (crash before persistence)."""

    def test_remote_already_published_reconciles_state_without_republishing(self):
        # Local state says PREPARED, but PyPI (checked for real) already has it.
        adapters = _all_absent_then_match_adapters()
        adapters["pypi"] = FakeAdapter("pypi", [MATCH])  # remote already has it despite stale local state
        result = run_engine(_state("PREPARED"), _manifest(), mode=ExecutionMode.REAL, adapters=adapters)
        self.assertEqual(adapters["pypi"].publish_calls, 0)
        self.assertFalse(result.stoppedEarly)
        self.assertEqual(result.finalState.state, "COMPLETE")

    def test_remote_conflicting_identity_stops_even_with_stale_local_state(self):
        adapters = _all_absent_then_match_adapters()
        adapters["pypi"] = FakeAdapter("pypi", [ConflictError("someone else published a different 2.0.0")])
        result = run_engine(_state("PREPARED"), _manifest(), mode=ExecutionMode.REAL, adapters=adapters)
        self.assertTrue(result.stoppedEarly)
        self.assertIn("different 2.0.0", result.stopReason)
        self.assertEqual(result.finalState.state, "PREPARED")  # never advanced past the conflict


class ConflictFailsClosedTests(unittest.TestCase):
    def _adapters_with_conflict_at(self, key):
        adapters = _all_absent_then_match_adapters()
        adapters[key] = FakeAdapter(key, [ConflictError(f"{key} conflict")])
        return adapters

    def test_pypi_conflict_stops_real_run(self):
        result = run_engine(_state(), _manifest(), mode=ExecutionMode.REAL, adapters=self._adapters_with_conflict_at("pypi"))
        self.assertTrue(result.stoppedEarly)
        self.assertEqual(result.finalState.state, "PREPARED")

    def test_ghcr_conflict_stops_real_run(self):
        result = run_engine(_state(), _manifest(), mode=ExecutionMode.REAL, adapters=self._adapters_with_conflict_at("ghcr"))
        self.assertTrue(result.stoppedEarly)

    def test_dockerhub_conflict_stops_real_run(self):
        result = run_engine(_state(), _manifest(), mode=ExecutionMode.REAL, adapters=self._adapters_with_conflict_at("dockerhub"))
        self.assertTrue(result.stoppedEarly)

    def test_git_tag_conflict_stops_real_run(self):
        result = run_engine(_state(), _manifest(), mode=ExecutionMode.REAL, adapters=self._adapters_with_conflict_at("git_tag"))
        self.assertTrue(result.stoppedEarly)

    def test_github_release_conflict_stops_real_run(self):
        result = run_engine(_state(), _manifest(), mode=ExecutionMode.REAL, adapters=self._adapters_with_conflict_at("github_release"))
        self.assertTrue(result.stoppedEarly)

    def test_conflict_also_stops_a_dry_run_plan_at_the_same_point(self):
        # A dry-run must report the exact wall a real run would hit, not
        # optimistically plan past a known conflict.
        adapters = self._adapters_with_conflict_at("ghcr")
        result = run_engine(_state(), _manifest(), mode=ExecutionMode.DRY_RUN, adapters=adapters)
        self.assertTrue(result.stoppedEarly)
        self.assertEqual(result.outcomes[-1].stepKey, "ghcr")
        self.assertEqual(result.outcomes[-1].action, "conflict")

    def test_verification_unavailable_stops_real_run_but_not_dry_run(self):
        adapters = _all_absent_then_match_adapters()
        adapters["ghcr"] = FakeAdapter("ghcr", [VerificationUnavailableError("no network")])
        real_result = run_engine(_state(), _manifest(), mode=ExecutionMode.REAL, adapters=adapters)
        self.assertTrue(real_result.stoppedEarly)

        adapters_dry = _all_absent_then_match_adapters()
        adapters_dry["ghcr"] = FakeAdapter("ghcr", [VerificationUnavailableError("no network")])
        dry_result = run_engine(_state(), _manifest(), mode=ExecutionMode.DRY_RUN, adapters=adapters_dry)
        self.assertFalse(dry_result.stoppedEarly)  # dry-run keeps walking past an unrelated unavailable check
        self.assertEqual([o.action for o in dry_result.outcomes if o.stepKey == "ghcr"], ["unavailable"])


class VerifyOnlyBarrierTests(unittest.TestCase):
    def test_external_verification_not_satisfied_stops_real_run(self):
        adapters = _all_absent_then_match_adapters()
        adapters["external_verification"] = FakeAdapter("external_verification", [ABSENT])
        result = run_engine(_state("DOCKERHUB_PUBLISHED"), _manifest(), mode=ExecutionMode.REAL, adapters=adapters)
        self.assertTrue(result.stoppedEarly)
        self.assertEqual(result.finalState.state, "DOCKERHUB_PUBLISHED")

    def test_final_verification_not_satisfied_stops_real_run(self):
        adapters = {"final_verification": FakeAdapter("final_verification", [ABSENT])}
        result = run_engine(_state("GITHUB_RELEASED"), _manifest(), mode=ExecutionMode.REAL, adapters=adapters)
        self.assertTrue(result.stoppedEarly)
        self.assertEqual(result.finalState.state, "GITHUB_RELEASED")


class NoAutomaticVersionBumpTests(unittest.TestCase):
    def test_state_version_is_unchanged_after_a_stopped_real_run(self):
        adapters = self_conflict = _all_absent_then_match_adapters()
        self_conflict["ghcr"] = FakeAdapter("ghcr", [ConflictError("boom")])
        result = run_engine(_state(), _manifest(), mode=ExecutionMode.REAL, adapters=adapters)
        self.assertEqual(result.finalState.version, "2.0.0")

    def test_resuming_with_a_different_version_manifest_is_the_callers_responsibility(self):
        # The engine trusts the manifest/state pairing it is given; the CLI
        # layer (release_tooling.cli / state.ensure_same_version) is what
        # refuses to mix versions - proven in tests/unit/test_release_state.py
        # and tests/unit/test_release_cli.py. This test documents that the
        # engine itself always reports whatever version the manifest says.
        result = run_engine(_state(), _manifest(productVersion="2.0.0"), mode=ExecutionMode.DRY_RUN, adapters=_all_absent_then_match_adapters())
        self.assertEqual(result.version, "2.0.0")


class RepeatInvocationIdempotenceTests(unittest.TestCase):
    def test_dry_run_can_be_invoked_repeatedly_without_changing_anything(self):
        state = _state()
        manifest = _manifest()
        first = run_engine(state, manifest, mode=ExecutionMode.DRY_RUN, adapters=_all_absent_then_match_adapters())
        second = run_engine(state, manifest, mode=ExecutionMode.DRY_RUN, adapters=_all_absent_then_match_adapters())
        self.assertEqual(state.state, "PREPARED")  # original untouched by clone()
        self.assertEqual([o.to_json_dict() for o in first.outcomes], [o.to_json_dict() for o in second.outcomes])


if __name__ == "__main__":
    unittest.main()
