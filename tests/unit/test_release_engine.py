"""The one release engine (AP-SRV-070 W5-R04).

Gates covered here: W5R4-G19 (one canonical graph), G20 (dry-run and real use
the same graph), G21-G24 (order), G26/G27 (conflict and unverifiable remote
state hard-stop), G28 (resume from any partial state), G32 (final verification
precedes COMPLETE), plus the `--until` boundary the publish workflow relies on.

Every adapter here is a fake. Nothing in this module can reach the network,
Docker, git, PyPI or a registry.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from release_support import make_manifest, make_state  # noqa: E402

from release_tooling.engine import (  # noqa: E402
    STEP_DEFINITIONS,
    ExecutionMode,
    StepKind,
    plan_from,
    run_engine,
)
from release_tooling.errors import (
    ConflictError,
    ManifestError,
    VerificationUnavailableError,
)  # noqa: E402
from release_tooling.remote_checks import ABSENT, MATCH  # noqa: E402
from release_tooling.state import STATE_ORDER  # noqa: E402

STEP_KEYS = [step.key for step in STEP_DEFINITIONS]


class FakeAdapter:
    """A scripted adapter: says what it is told, records what it was asked."""

    def __init__(self, status=MATCH, raises=None, name="fake"):
        self.name = name
        self._status = status
        self._raises = raises
        self.verify_calls = 0
        self.publish_calls = 0
        self.published = False

    def verify(self, manifest, state):
        self.verify_calls += 1
        if self._raises is not None:
            raise self._raises
        if self.published:
            return MATCH
        return self._status

    def publish(self, manifest, state):
        self.publish_calls += 1
        self.published = True


def adapters(**overrides):
    """A full adapter bundle, MATCH by default, with named overrides."""
    bundle = {key: FakeAdapter(name=key) for key in STEP_KEYS if key != "complete"}
    bundle.update(overrides)
    return bundle


#: The two read-only aggregate barriers. They have no write of their own, so
#: they are MATCH exactly when the steps they aggregate have succeeded - which
#: in these fakes is "by the time the walk reaches them".
VERIFY_ONLY_KEYS = {s.key for s in STEP_DEFINITIONS if s.kind == StepKind.VERIFY_ONLY}


def absent_adapters(**overrides):
    """A bundle modelling "nothing is published yet".

    Publishing steps report ABSENT (so a real run performs them); the
    verification barriers report MATCH, because they only ever aggregate the
    steps that just succeeded. Modelling the barriers as ABSENT instead would
    test a state that cannot occur - it would mean "PyPI and both registries
    are published, but verifying them says they are not", which is the
    separate hard-stop case covered by
    ``test_an_unsatisfied_verification_barrier_stops_the_run``.
    """
    bundle = {
        key: FakeAdapter(
            status=MATCH if key in VERIFY_ONLY_KEYS else ABSENT, name=key
        )
        for key in STEP_KEYS
        if key != "complete"
    }
    bundle.update(overrides)
    return bundle


class GraphShapeTests(unittest.TestCase):
    def test_the_graph_covers_the_state_order_exactly_once(self):
        # W5R4-G19: one graph, and it *is* the state order.
        self.assertEqual([s.from_state for s in STEP_DEFINITIONS], STATE_ORDER[:-1])
        self.assertEqual([s.to_state for s in STEP_DEFINITIONS], STATE_ORDER[1:])

    def test_the_step_order_is_the_w5_r04_publication_order(self):
        self.assertEqual(
            STEP_KEYS,
            [
                "git_tag",
                "pypi",
                "dockerhub",
                "ghcr",
                "external_verification",
                "aliases",
                "github_release",
                "final_verification",
                "complete",
            ],
        )

    def test_verification_steps_can_never_write(self):
        verify_only = [s.key for s in STEP_DEFINITIONS if s.kind == StepKind.VERIFY_ONLY]
        self.assertEqual(verify_only, ["external_verification", "final_verification"])

    def test_plan_from_returns_only_the_remaining_steps(self):
        self.assertEqual(len(plan_from("PREPARED")), len(STEP_DEFINITIONS))
        self.assertEqual([s.key for s in plan_from("ALIASES_PUBLISHED")],
                         ["github_release", "final_verification", "complete"])
        self.assertEqual(plan_from("COMPLETE"), [])


class StopAfterTests(unittest.TestCase):
    def test_stop_after_shortens_the_plan_without_reordering_it(self):
        self.assertEqual([s.key for s in plan_from("PREPARED", "TAGGED")], ["git_tag"])
        self.assertEqual(
            [s.key for s in plan_from("TAGGED", "GHCR_PUBLISHED")],
            ["pypi", "dockerhub", "ghcr"],
        )

    def test_stop_after_a_state_already_passed_plans_nothing(self):
        self.assertEqual(plan_from("GHCR_PUBLISHED", "TAGGED"), [])

    def test_stop_after_is_validated(self):
        with self.assertRaises(ValueError):
            plan_from("PREPARED", "NOT_A_STATE")

    def test_a_bounded_real_run_stops_exactly_at_the_boundary(self):
        bundle = absent_adapters()
        result = run_engine(
            make_state("PREPARED"), make_manifest(), mode=ExecutionMode.REAL,
            adapters=bundle, stop_after="TAGGED",
        )
        self.assertEqual(result.finalState.state, "TAGGED")
        self.assertEqual(bundle["git_tag"].publish_calls, 1)
        # Nothing past the boundary was even consulted.
        self.assertEqual(bundle["pypi"].verify_calls, 0)
        self.assertEqual(bundle["dockerhub"].publish_calls, 0)

    def test_bounded_jobs_chained_together_reach_complete(self):
        # This is exactly what the publish workflow does across four jobs.
        bundle = absent_adapters()
        manifest = make_manifest()
        state = make_state("PREPARED")
        for boundary in ("TAGGED", "PYPI_PUBLISHED", "EXTERNAL_VERIFIED", "COMPLETE"):
            result = run_engine(
                state, manifest, mode=ExecutionMode.REAL, adapters=bundle,
                stop_after=boundary,
            )
            self.assertFalse(result.stoppedEarly, result.stopReason)
            state = result.finalState
        self.assertEqual(state.state, "COMPLETE")


class DryRunTests(unittest.TestCase):
    def test_dry_run_never_calls_a_single_publish(self):
        # W5R4-G20 and "dry-run zero writes".
        bundle = absent_adapters()
        result = run_engine(
            make_state("PREPARED"), make_manifest(), mode=ExecutionMode.DRY_RUN,
            adapters=bundle,
        )
        for key, adapter in bundle.items():
            self.assertEqual(adapter.publish_calls, 0, f"{key} published in a dry-run")
        self.assertTrue(result.to_json_dict()["sideEffectFree"])
        self.assertEqual(result.finalState.state, "PREPARED")

    def test_dry_run_reports_every_remaining_step(self):
        result = run_engine(
            make_state("PREPARED"), make_manifest(), mode=ExecutionMode.DRY_RUN,
            adapters=absent_adapters(),
        )
        self.assertEqual([o.stepKey for o in result.outcomes], STEP_KEYS)
        self.assertTrue(all(o.executed is False for o in result.outcomes))

    def test_dry_run_and_real_walk_the_same_graph(self):
        # W5R4-G20: the only difference is the mode.
        manifest = make_manifest()
        dry = run_engine(make_state("PREPARED"), manifest,
                         mode=ExecutionMode.DRY_RUN, adapters=absent_adapters())
        real = run_engine(make_state("PREPARED"), manifest,
                          mode=ExecutionMode.REAL, adapters=absent_adapters())
        self.assertEqual([o.stepKey for o in dry.outcomes],
                         [o.stepKey for o in real.outcomes])

    def test_dry_run_keeps_walking_past_an_unavailable_step(self):
        bundle = absent_adapters(
            dockerhub=FakeAdapter(raises=VerificationUnavailableError("no network"),
                                  name="dockerhub")
        )
        result = run_engine(make_state("PREPARED"), make_manifest(),
                            mode=ExecutionMode.DRY_RUN, adapters=bundle)
        statuses = {o.stepKey: o.remoteStatus for o in result.outcomes}
        self.assertEqual(statuses["dockerhub"], "UNKNOWN")
        self.assertIn("github_release", statuses)  # the walk continued

    def test_dry_run_still_stops_at_a_genuine_conflict(self):
        bundle = absent_adapters(
            pypi=FakeAdapter(raises=ConflictError("2.0.0 already exists differently"),
                             name="pypi")
        )
        result = run_engine(make_state("PREPARED"), make_manifest(),
                            mode=ExecutionMode.DRY_RUN, adapters=bundle)
        self.assertTrue(result.stoppedEarly)
        self.assertEqual(result.outcomes[-1].remoteStatus, "CONFLICT")


class RealRunTests(unittest.TestCase):
    def test_a_full_absent_release_publishes_every_step_in_order(self):
        bundle = absent_adapters()
        result = run_engine(make_state("PREPARED"), make_manifest(),
                            mode=ExecutionMode.REAL, adapters=bundle)
        self.assertEqual(result.finalState.state, "COMPLETE")
        self.assertEqual(
            [o.stepKey for o in result.outcomes if o.action == "published"],
            ["git_tag", "pypi", "dockerhub", "ghcr", "aliases", "github_release"],
        )

    def test_publication_is_always_reverified_before_the_state_advances(self):
        # A step that publishes but cannot then be verified must not advance.
        class PublishesButNeverAppears(FakeAdapter):
            def verify(self, manifest, state):
                self.verify_calls += 1
                return ABSENT

        bundle = absent_adapters(pypi=PublishesButNeverAppears(name="pypi"))
        result = run_engine(make_state("PREPARED"), make_manifest(),
                            mode=ExecutionMode.REAL, adapters=bundle)
        self.assertTrue(result.stoppedEarly)
        self.assertIn("did not result in a verified matching identity", result.stopReason)
        self.assertEqual(result.finalState.state, "TAGGED")

    def test_a_conflict_hard_stops_a_real_run(self):
        # W5R4-G26.
        bundle = absent_adapters(
            dockerhub=FakeAdapter(raises=ConflictError("tag exists with another digest"),
                                  name="dockerhub")
        )
        result = run_engine(make_state("PYPI_PUBLISHED"), make_manifest(),
                            mode=ExecutionMode.REAL, adapters=bundle)
        self.assertTrue(result.stoppedEarly)
        self.assertEqual(result.finalState.state, "PYPI_PUBLISHED")
        self.assertEqual(bundle["ghcr"].publish_calls, 0)

    def test_unverifiable_remote_state_hard_stops_a_real_run(self):
        # W5R4-G27: "cannot check" is never treated as "safe to publish".
        bundle = absent_adapters(
            ghcr=FakeAdapter(raises=VerificationUnavailableError("registry unreachable"),
                             name="ghcr")
        )
        result = run_engine(make_state("DOCKERHUB_PUBLISHED"), make_manifest(),
                            mode=ExecutionMode.REAL, adapters=bundle)
        self.assertTrue(result.stoppedEarly)
        self.assertEqual(result.outcomes[-1].remoteStatus, "UNKNOWN")
        self.assertEqual(bundle["ghcr"].publish_calls, 0)

    def test_an_unsatisfied_verification_barrier_stops_the_run(self):
        bundle = absent_adapters(
            external_verification=FakeAdapter(status=ABSENT, name="external_verification")
        )
        bundle["external_verification"].publish = None  # must never be called
        result = run_engine(make_state("GHCR_PUBLISHED"), make_manifest(),
                            mode=ExecutionMode.REAL, adapters=bundle)
        self.assertTrue(result.stoppedEarly)
        self.assertEqual(result.finalState.state, "GHCR_PUBLISHED")


class ResumeTests(unittest.TestCase):
    def test_an_already_published_step_resumes_without_republishing(self):
        # W5R4-G28: MATCH means "already done", never "do it again".
        bundle = absent_adapters(pypi=FakeAdapter(status=MATCH, name="pypi"))
        result = run_engine(make_state("TAGGED"), make_manifest(),
                            mode=ExecutionMode.REAL, adapters=bundle)
        pypi_outcome = next(o for o in result.outcomes if o.stepKey == "pypi")
        self.assertEqual(pypi_outcome.action, "resumed")
        self.assertFalse(pypi_outcome.executed)
        self.assertEqual(bundle["pypi"].publish_calls, 0)

    def test_a_run_can_resume_from_every_partial_state(self):
        for start in STATE_ORDER[:-1]:
            with self.subTest(start=start):
                bundle = absent_adapters()
                result = run_engine(make_state(start), make_manifest(),
                                    mode=ExecutionMode.REAL, adapters=bundle)
                self.assertEqual(result.finalState.state, "COMPLETE")

    def test_resume_never_changes_the_version(self):
        # W5R4-G29.
        manifest = make_manifest()
        result = run_engine(make_state("DOCKERHUB_PUBLISHED"), manifest,
                            mode=ExecutionMode.REAL, adapters=absent_adapters())
        self.assertEqual(result.version, "2.0.0")
        self.assertEqual(result.finalState.version, "2.0.0")

    def test_state_is_persisted_after_each_advance(self):
        persisted = []
        run_engine(make_state("PREPARED"), make_manifest(), mode=ExecutionMode.REAL,
                   adapters=absent_adapters(), persist=lambda s: persisted.append(s.state))
        self.assertEqual(persisted, STATE_ORDER[1:])

class QualificationBarrierTests(unittest.TestCase):
    def test_not_qualified_manifest_fails_real_publish(self):
        manifest = make_manifest(release_readiness="NOT_QUALIFIED")
        with self.assertRaises(ManifestError) as ctx:
            run_engine(make_state("PREPARED"), manifest, mode=ExecutionMode.REAL, adapters=absent_adapters())
        self.assertIn("NOT_QUALIFIED", str(ctx.exception))

    def test_rejected_manifest_fails_real_publish(self):
        manifest = make_manifest(release_readiness="REJECTED")
        with self.assertRaises(ManifestError) as ctx:
            run_engine(make_state("PREPARED"), manifest, mode=ExecutionMode.REAL, adapters=absent_adapters())
        self.assertIn("REJECTED", str(ctx.exception))

    def test_missing_evidence_ref_fails_real_publish(self):
        manifest = make_manifest()
        manifest["qualification"]["evidenceRef"] = ""
        with self.assertRaises(ManifestError) as ctx:
            run_engine(make_state("PREPARED"), manifest, mode=ExecutionMode.REAL, adapters=absent_adapters())
        self.assertIn("evidenceRef", str(ctx.exception))

    def test_mismatched_commit_fails_real_publish(self):
        manifest = make_manifest()
        state = make_state("PREPARED")
        state.sourceCommit = "f" * 40
        with self.assertRaises(ManifestError) as ctx:
            run_engine(state, manifest, mode=ExecutionMode.REAL, adapters=absent_adapters())
        self.assertIn("sourceCommit", str(ctx.exception))

    def test_mismatched_tree_fails_real_publish(self):
        manifest = make_manifest()
        state = make_state("PREPARED")
        state.sourceTree = "f" * 40
        with self.assertRaises(ManifestError) as ctx:
            run_engine(state, manifest, mode=ExecutionMode.REAL, adapters=absent_adapters())
        self.assertIn("sourceTree", str(ctx.exception))

    def test_dry_run_accepts_unqualified_manifest_for_planning(self):
        manifest = make_manifest(release_readiness="NOT_QUALIFIED")
        result = run_engine(make_state("PREPARED"), manifest, mode=ExecutionMode.DRY_RUN, adapters=absent_adapters())
        self.assertEqual(len(result.outcomes), len(STEP_KEYS))


if __name__ == "__main__":
    unittest.main()
