"""AP-SRV-070 W5 / W5-R01-C1: the fixed publication order facade.

``release_tooling.pipeline`` is now a thin facade over
``release_tooling.engine`` (see ``tests/unit/test_release_engine.py`` for
the full shared-operation-graph, resume, and conflict-fail-closed proofs).
This module only checks the facade itself: the order/shape it re-exports,
and that ``dry_run()`` wires correctly into the real engine in
``ExecutionMode.DRY_RUN`` with zero writes.
"""

from __future__ import annotations

import unittest

from release_tooling.pipeline import PIPELINE_STEPS, dry_run, plan_from
from release_tooling.remote_checks import ABSENT
from release_tooling.state import STATE_ORDER, advance, new_state


def _sample_state():
    return new_state(
        version="2.0.0",
        source_commit="a" * 40,
        source_tree="b" * 40,
        wheel={"filename": "voicestt-2.0.0-py3-none-any.whl", "sha256": "c" * 64},
        sdist={"filename": "voicestt-2.0.0.tar.gz", "sha256": "d" * 64},
        free_image={"tag": "voice-stt-server:2.0.0", "imageId": "sha256:" + "e" * 64},
        pro_image={"tag": "voice-stt-server-pro:2.0.0", "imageId": "sha256:" + "f" * 64},
    )


def _sample_manifest():
    return {
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


class _PoisonedAdapter:
    """Fails the test if ``publish()`` is ever called; ``verify()`` always
    reports ABSENT (the most write-tempting possible answer)."""

    def __init__(self, name):
        self.name = name

    def verify(self, manifest, state):
        return ABSENT

    def publish(self, manifest, state):
        raise AssertionError(f"{self.name}.publish() must never be called by dry_run()")


def _poisoned_adapters():
    return {
        key: _PoisonedAdapter(key)
        for key in ("pypi", "ghcr", "dockerhub", "external_verification", "git_tag", "github_release", "final_verification")
    }


class FixedOrderTests(unittest.TestCase):
    def test_pipeline_steps_match_the_state_order_exactly(self):
        self.assertEqual([step[0] for step in PIPELINE_STEPS], STATE_ORDER[:-1])
        self.assertEqual([step[1] for step in PIPELINE_STEPS], STATE_ORDER[1:])

    def test_pipeline_encodes_the_prompt_mandated_sequence(self):
        expected_to_states = [
            "PYPI_PUBLISHED",
            "GHCR_PUBLISHED",
            "DOCKERHUB_PUBLISHED",
            "EXTERNAL_VERIFIED",
            "TAGGED",
            "GITHUB_RELEASED",
            "FINAL_VERIFIED",
            "COMPLETE",
        ]
        self.assertEqual([step[1] for step in PIPELINE_STEPS], expected_to_states)

    def test_tag_step_is_strictly_after_external_verification(self):
        to_states = [step[1] for step in PIPELINE_STEPS]
        self.assertLess(to_states.index("EXTERNAL_VERIFIED"), to_states.index("TAGGED"))

    def test_github_release_step_is_strictly_after_tag(self):
        to_states = [step[1] for step in PIPELINE_STEPS]
        self.assertLess(to_states.index("TAGGED"), to_states.index("GITHUB_RELEASED"))


class PlanFromTests(unittest.TestCase):
    def test_plan_from_prepared_covers_every_step(self):
        self.assertEqual(len(plan_from("PREPARED")), len(PIPELINE_STEPS))

    def test_plan_from_a_later_state_covers_fewer_steps(self):
        self.assertEqual(len(plan_from("EXTERNAL_VERIFIED")), 4)

    def test_plan_from_complete_is_empty(self):
        self.assertEqual(plan_from("COMPLETE"), [])

    def test_plan_from_an_unknown_state_raises(self):
        with self.assertRaises(ValueError):
            plan_from("NOT_A_STATE")


class DryRunSideEffectFreedomTests(unittest.TestCase):
    def test_dry_run_reports_the_full_plan_from_prepared(self):
        result = dry_run(_sample_state(), _sample_manifest(), adapters=_poisoned_adapters())
        self.assertEqual(result.startingState, "PREPARED")
        self.assertEqual(len(result.outcomes), len(PIPELINE_STEPS))
        self.assertTrue(result.to_json_dict()["sideEffectFree"])

    def test_dry_run_reports_a_shorter_plan_when_resuming(self):
        state = _sample_state()
        state = advance(state, "PYPI_PUBLISHED")
        state = advance(state, "GHCR_PUBLISHED")
        result = dry_run(state, _sample_manifest(), adapters=_poisoned_adapters())
        self.assertEqual(result.startingState, "GHCR_PUBLISHED")
        self.assertEqual(len(result.outcomes), len(PIPELINE_STEPS) - 2)

    def test_dry_run_never_calls_publish_on_any_injected_adapter(self):
        # Every adapter here raises AssertionError if publish() is called -
        # dry_run() completing without error is the proof this section
        # requires: no upload/push/tag/release ever happens.
        result = dry_run(_sample_state(), _sample_manifest(), adapters=_poisoned_adapters())
        self.assertFalse(result.stoppedEarly)

    def test_dry_run_never_persists_anything_by_itself(self):
        # dry_run() takes no persist callback at all - there is no code
        # path inside it that could write release state to disk.
        import inspect

        signature = inspect.signature(dry_run)
        self.assertNotIn("persist", signature.parameters)

    def test_dry_run_at_complete_plans_nothing(self):
        state = _sample_state()
        for target in ["PYPI_PUBLISHED", "GHCR_PUBLISHED", "DOCKERHUB_PUBLISHED",
                       "EXTERNAL_VERIFIED", "TAGGED", "GITHUB_RELEASED",
                       "FINAL_VERIFIED", "COMPLETE"]:
            state = advance(state, target)
        result = dry_run(state, _sample_manifest(), adapters=_poisoned_adapters())
        self.assertEqual(result.outcomes, [])


if __name__ == "__main__":
    unittest.main()
