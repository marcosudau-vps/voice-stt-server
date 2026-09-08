"""The ``release_tooling.pipeline`` facade (AP-SRV-070 W5-R01-C1 / W5-R04).

``pipeline`` exists only so older call sites keep working; the graph itself
lives in ``release_tooling.engine``. These tests exist to prove the facade is
still a facade - that it re-exports the *same* graph rather than growing a
second, drifting copy of the order (gate W5R4-G19).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from release_support import make_manifest, make_state  # noqa: E402

from release_tooling.engine import STEP_DEFINITIONS  # noqa: E402
from release_tooling.pipeline import PIPELINE_STEPS, dry_run  # noqa: E402
from release_tooling.remote_checks import ABSENT, MATCH  # noqa: E402
from release_tooling.state import STATE_ORDER  # noqa: E402


class RefusingAdapter:
    """Fails the test loudly if a dry-run ever tries to write."""

    def __init__(self, testcase, status=ABSENT):
        self._testcase = testcase
        self._status = status

    def verify(self, manifest, state):
        return self._status

    def publish(self, manifest, state):
        self._testcase.fail("dry_run() called publish() on an adapter")


def refusing_bundle(testcase):
    bundle = {}
    for step in STEP_DEFINITIONS:
        if step.key == "complete":
            continue
        status = MATCH if step.kind.value == "VERIFY_ONLY" else ABSENT
        bundle[step.key] = RefusingAdapter(testcase, status)
    return bundle


class FacadeTests(unittest.TestCase):
    def test_pipeline_steps_mirror_the_engine_graph_exactly(self):
        self.assertEqual(
            list(PIPELINE_STEPS),
            [(s.from_state, s.to_state, s.description) for s in STEP_DEFINITIONS],
        )

    def test_pipeline_steps_span_the_whole_state_order(self):
        self.assertEqual([step[0] for step in PIPELINE_STEPS], STATE_ORDER[:-1])
        self.assertEqual([step[1] for step in PIPELINE_STEPS], STATE_ORDER[1:])

    def test_the_facade_encodes_the_w5_r04_order(self):
        to_states = [step[1] for step in PIPELINE_STEPS]
        self.assertLess(to_states.index("TAGGED"), to_states.index("PYPI_PUBLISHED"))
        self.assertLess(to_states.index("PYPI_PUBLISHED"), to_states.index("DOCKERHUB_PUBLISHED"))
        self.assertLess(to_states.index("DOCKERHUB_PUBLISHED"), to_states.index("GHCR_PUBLISHED"))
        self.assertLess(to_states.index("EXTERNAL_VERIFIED"), to_states.index("ALIASES_PUBLISHED"))
        self.assertLess(to_states.index("ALIASES_PUBLISHED"), to_states.index("GITHUB_RELEASED"))
        self.assertEqual(to_states[-1], "COMPLETE")


class DryRunSideEffectFreedomTests(unittest.TestCase):
    def test_dry_run_never_publishes(self):
        result = dry_run(make_state("PREPARED"), make_manifest(), refusing_bundle(self))
        self.assertTrue(result.to_json_dict()["sideEffectFree"])

    def test_dry_run_reports_the_full_plan_from_prepared(self):
        result = dry_run(make_state("PREPARED"), make_manifest(), refusing_bundle(self))
        self.assertEqual(len(result.outcomes), len(STEP_DEFINITIONS))

    def test_dry_run_reports_a_shorter_plan_when_resuming(self):
        result = dry_run(make_state("GHCR_PUBLISHED"), make_manifest(), refusing_bundle(self))
        self.assertEqual(
            [o.stepKey for o in result.outcomes],
            ["external_verification", "aliases", "github_release", "final_verification", "complete"],
        )

    def test_dry_run_at_complete_plans_nothing(self):
        result = dry_run(make_state("COMPLETE"), make_manifest(), refusing_bundle(self))
        self.assertEqual(result.outcomes, [])

    def test_dry_run_honours_the_same_until_boundary_publish_uses(self):
        result = dry_run(
            make_state("PREPARED"), make_manifest(), refusing_bundle(self),
            stop_after="PYPI_PUBLISHED",
        )
        self.assertEqual([o.stepKey for o in result.outcomes], ["git_tag", "pypi"])

    def test_dry_run_never_mutates_the_state_it_was_given(self):
        state = make_state("PREPARED")
        dry_run(state, make_manifest(), refusing_bundle(self))
        self.assertEqual(state.state, "PREPARED")
        self.assertEqual(len(state.history), 1)


if __name__ == "__main__":
    unittest.main()
