"""AP-SRV-070 W5-R01-C1: the real, W6-capable publication adapters.

Every test injects a fake runner/fetcher - none makes a real network call,
runs Twine/Docker/git/gh for real, or reads a real credential. Sentinel
"secret" values are obvious synthetic strings that must never leak into a
raised exception message.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from release_tooling.adapters import (
    AggregateVerificationAdapter,
    DockerHubAdapter,
    GHCRAdapter,
    GitHubReleaseAdapter,
    GitTagAdapter,
    PyPIAdapter,
)
from release_tooling.errors import ConflictError, OrderError, ReleaseError, VerificationUnavailableError
from release_tooling.remote_checks import ABSENT, MATCH, CommandResult
from release_tooling.state import advance, new_state

SENTINEL_SECRET = "ghp_SENTINELSECRETVALUEAAAAAAAAAAAAAAAAAAA"


def _sample_manifest(**overrides):
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


def _sample_state(**overrides):
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


class PyPIAdapterTests(unittest.TestCase):
    def test_verify_absent_is_safe_to_publish(self):
        adapter = PyPIAdapter(dist_dir=Path("."), fetch=lambda url: None)
        self.assertEqual(adapter.verify(_sample_manifest(), _sample_state()), ABSENT)

    def test_verify_matching_release_resumes(self):
        payload = {
            "releases": {
                "2.0.0": [
                    {"filename": "voicestt-2.0.0-py3-none-any.whl", "digests": {"sha256": "c" * 64}},
                    {"filename": "voicestt-2.0.0.tar.gz", "digests": {"sha256": "d" * 64}},
                ]
            }
        }
        adapter = PyPIAdapter(dist_dir=Path("."), fetch=lambda url: payload)
        self.assertEqual(adapter.verify(_sample_manifest(), _sample_state()), MATCH)

    def test_verify_conflicting_release_fails_closed(self):
        payload = {"releases": {"2.0.0": [{"filename": "voicestt-2.0.0-py3-none-any.whl", "digests": {"sha256": "different"}}]}}
        adapter = PyPIAdapter(dist_dir=Path("."), fetch=lambda url: payload)
        with self.assertRaises(ConflictError):
            adapter.verify(_sample_manifest(), _sample_state())

    def test_verify_network_failure_is_unavailable_not_absent(self):
        def failing_fetch(url):
            raise OSError("network unreachable")

        adapter = PyPIAdapter(dist_dir=Path("."), fetch=failing_fetch)
        with self.assertRaises(VerificationUnavailableError):
            adapter.verify(_sample_manifest(), _sample_state())

    def test_publish_refuses_when_local_artifacts_missing(self):
        with TemporaryDirectory() as tmp:
            adapter = PyPIAdapter(dist_dir=Path(tmp), fetch=lambda url: None)
            with self.assertRaises(ReleaseError):
                adapter.publish(_sample_manifest(), _sample_state())

    def test_publish_invokes_twine_upload_non_interactive(self):
        with TemporaryDirectory() as tmp:
            dist_dir = Path(tmp)
            (dist_dir / "voicestt-2.0.0-py3-none-any.whl").write_text("wheel", encoding="utf-8")
            (dist_dir / "voicestt-2.0.0.tar.gz").write_text("sdist", encoding="utf-8")
            calls = []

            def runner(cmd, **kwargs):
                calls.append(cmd)
                return CommandResult(args=list(cmd), returncode=0, stdout="", stderr="")

            adapter = PyPIAdapter(dist_dir=dist_dir, runner=runner, fetch=lambda url: None)
            adapter.publish(_sample_manifest(), _sample_state())
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][:2], ["twine", "upload"])
            self.assertIn("--non-interactive", calls[0])

    def test_publish_never_places_a_secret_in_the_command_line(self):
        with TemporaryDirectory() as tmp:
            dist_dir = Path(tmp)
            (dist_dir / "voicestt-2.0.0-py3-none-any.whl").write_text("wheel", encoding="utf-8")
            (dist_dir / "voicestt-2.0.0.tar.gz").write_text("sdist", encoding="utf-8")
            captured = {}

            def runner(cmd, **kwargs):
                captured["cmd"] = cmd
                return CommandResult(args=list(cmd), returncode=0, stdout="", stderr="")

            with mock.patch.dict("os.environ", {"TWINE_PASSWORD": SENTINEL_SECRET}):
                adapter = PyPIAdapter(dist_dir=dist_dir, runner=runner, fetch=lambda url: None)
                adapter.publish(_sample_manifest(), _sample_state())
            self.assertNotIn(SENTINEL_SECRET, " ".join(captured["cmd"]))

    def test_publish_failure_redacts_secret_shaped_stderr(self):
        with TemporaryDirectory() as tmp:
            dist_dir = Path(tmp)
            (dist_dir / "voicestt-2.0.0-py3-none-any.whl").write_text("wheel", encoding="utf-8")
            (dist_dir / "voicestt-2.0.0.tar.gz").write_text("sdist", encoding="utf-8")

            def failing_runner(cmd, **kwargs):
                return CommandResult(args=list(cmd), returncode=1, stdout="", stderr=f"auth failed with token {SENTINEL_SECRET}")

            adapter = PyPIAdapter(dist_dir=dist_dir, runner=failing_runner, fetch=lambda url: None)
            with self.assertRaises(ReleaseError) as ctx:
                adapter.publish(_sample_manifest(), _sample_state())
            self.assertNotIn(SENTINEL_SECRET, str(ctx.exception))


class RegistryAdapterTests(unittest.TestCase):
    def _runner_sequence(self, results):
        calls = []

        def runner(cmd):
            calls.append(cmd)
            return results.pop(0)

        return runner, calls

    def test_verify_absent_for_both_variants(self):
        results = [
            CommandResult(args=[], returncode=1, stdout="", stderr="no such manifest"),
            CommandResult(args=[], returncode=1, stdout="", stderr="no such manifest"),
        ]
        runner, _ = self._runner_sequence(results)
        with mock.patch.dict("os.environ", {"VOICESTT_RELEASE_GHCR_REPO": "ghcr.io/org"}):
            adapter = GHCRAdapter(runner=runner)
            self.assertEqual(adapter.verify(_sample_manifest(), _sample_state()), ABSENT)

    def test_verify_match_when_both_variants_match(self):
        payload_free = json.dumps({"config": {"digest": "sha256:" + "e" * 64}})
        payload_pro = json.dumps({"config": {"digest": "sha256:" + "f" * 64}})
        runner, _ = self._runner_sequence(
            [CommandResult(args=[], returncode=0, stdout=payload_free, stderr=""), CommandResult(args=[], returncode=0, stdout=payload_pro, stderr="")]
        )
        with mock.patch.dict("os.environ", {"VOICESTT_RELEASE_GHCR_REPO": "ghcr.io/org"}):
            adapter = GHCRAdapter(runner=runner)
            self.assertEqual(adapter.verify(_sample_manifest(), _sample_state()), MATCH)

    def test_verify_conflicting_digest_fails_closed(self):
        payload_free = json.dumps({"config": {"digest": "sha256:" + "0" * 64}})
        runner, _ = self._runner_sequence([CommandResult(args=[], returncode=0, stdout=payload_free, stderr="")])
        with mock.patch.dict("os.environ", {"VOICESTT_RELEASE_GHCR_REPO": "ghcr.io/org"}):
            adapter = GHCRAdapter(runner=runner)
            with self.assertRaises(ConflictError):
                adapter.verify(_sample_manifest(), _sample_state())

    def test_verify_without_repo_configured_is_unavailable(self):
        with mock.patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("VOICESTT_RELEASE_GHCR_REPO", None)
            adapter = GHCRAdapter(runner=lambda cmd: CommandResult(args=[], returncode=0, stdout="", stderr=""))
            with self.assertRaises(VerificationUnavailableError):
                adapter.verify(_sample_manifest(), _sample_state())

    def test_publish_tags_and_pushes_each_absent_variant(self):
        # verify()x2 (absent, absent) inside publish()'s per-variant check, then tag+push per variant.
        results = [
            CommandResult(args=[], returncode=1, stdout="", stderr="no such manifest"),  # free verify
            CommandResult(args=[], returncode=0, stdout="", stderr=""),  # free tag
            CommandResult(args=[], returncode=0, stdout="", stderr=""),  # free push
            CommandResult(args=[], returncode=1, stdout="", stderr="no such manifest"),  # pro verify
            CommandResult(args=[], returncode=0, stdout="", stderr=""),  # pro tag
            CommandResult(args=[], returncode=0, stdout="", stderr=""),  # pro push
        ]
        runner, calls = self._runner_sequence(results)
        with mock.patch.dict("os.environ", {"VOICESTT_RELEASE_GHCR_REPO": "ghcr.io/org"}):
            adapter = GHCRAdapter(runner=runner)
            adapter.publish(_sample_manifest(), _sample_state())
        push_calls = [c for c in calls if c[:2] == ["docker", "push"]]
        self.assertEqual(len(push_calls), 2)

    def test_publish_skips_a_variant_already_matching(self):
        payload_free = json.dumps({"config": {"digest": "sha256:" + "e" * 64}})  # already matches
        results = [
            CommandResult(args=[], returncode=0, stdout=payload_free, stderr=""),  # free verify -> MATCH, skip
            CommandResult(args=[], returncode=1, stdout="", stderr="no such manifest"),  # pro verify -> ABSENT
            CommandResult(args=[], returncode=0, stdout="", stderr=""),  # pro tag
            CommandResult(args=[], returncode=0, stdout="", stderr=""),  # pro push
        ]
        runner, calls = self._runner_sequence(results)
        with mock.patch.dict("os.environ", {"VOICESTT_RELEASE_GHCR_REPO": "ghcr.io/org"}):
            adapter = GHCRAdapter(runner=runner)
            adapter.publish(_sample_manifest(), _sample_state())
        push_calls = [c for c in calls if c[:2] == ["docker", "push"]]
        self.assertEqual(len(push_calls), 1)  # only the pro variant was pushed

    def test_dockerhub_adapter_uses_its_own_repo_env(self):
        with mock.patch.dict("os.environ", {"VOICESTT_RELEASE_DOCKERHUB_REPO": "org"}):
            adapter = DockerHubAdapter(runner=lambda cmd: CommandResult(args=[], returncode=1, stdout="", stderr="no such manifest"))
            self.assertEqual(adapter.verify(_sample_manifest(), _sample_state()), ABSENT)


class GitTagAdapterTests(unittest.TestCase):
    def test_verify_absent_when_no_local_or_remote_tag(self):
        with mock.patch("release_tooling.adapters.gitinfo.local_tag_commit", return_value=None), \
             mock.patch("release_tooling.adapters.gitinfo.remote_tag_commit", return_value=None):
            adapter = GitTagAdapter(repo_root=Path("."))
            self.assertEqual(adapter.verify(_sample_manifest(), _sample_state()), ABSENT)

    def test_verify_matching_remote_tag_resumes(self):
        with mock.patch("release_tooling.adapters.gitinfo.local_tag_commit", return_value=None), \
             mock.patch("release_tooling.adapters.gitinfo.remote_tag_commit", return_value="a" * 40):
            adapter = GitTagAdapter(repo_root=Path("."))
            self.assertEqual(adapter.verify(_sample_manifest(), _sample_state()), MATCH)

    def test_verify_wrong_commit_fails_closed(self):
        with mock.patch("release_tooling.adapters.gitinfo.local_tag_commit", return_value=None), \
             mock.patch("release_tooling.adapters.gitinfo.remote_tag_commit", return_value="z" * 40):
            adapter = GitTagAdapter(repo_root=Path("."))
            with self.assertRaises(ConflictError):
                adapter.verify(_sample_manifest(), _sample_state())

    def test_publish_refuses_before_external_verified(self):
        adapter = GitTagAdapter(repo_root=Path("."))
        state = _sample_state()  # still PREPARED
        with self.assertRaises(OrderError):
            adapter.publish(_sample_manifest(), state)

    def test_publish_creates_and_pushes_tag_once_externally_verified(self):
        state = _sample_state()
        for target in ("PYPI_PUBLISHED", "GHCR_PUBLISHED", "DOCKERHUB_PUBLISHED", "EXTERNAL_VERIFIED"):
            state = advance(state, target)
        with mock.patch("release_tooling.adapters.gitinfo.create_tag") as create_tag, \
             mock.patch("release_tooling.adapters.gitinfo.push_tag") as push_tag:
            adapter = GitTagAdapter(repo_root=Path("."))
            adapter.publish(_sample_manifest(), state)
            create_tag.assert_called_once_with(Path("."), "v2.0.0", "a" * 40)
            push_tag.assert_called_once()


class GitHubReleaseAdapterTests(unittest.TestCase):
    def test_verify_absent_when_release_not_found(self):
        runner = lambda cmd: CommandResult(args=list(cmd), returncode=1, stdout="", stderr="release not found")
        adapter = GitHubReleaseAdapter(runner=runner)
        self.assertEqual(adapter.verify(_sample_manifest(), _sample_state()), ABSENT)

    def test_verify_matching_release_resumes(self):
        payload = json.dumps({"tagName": "v2.0.0", "name": "2.0.0", "isDraft": False})
        runner = lambda cmd: CommandResult(args=list(cmd), returncode=0, stdout=payload, stderr="")
        adapter = GitHubReleaseAdapter(runner=runner)
        self.assertEqual(adapter.verify(_sample_manifest(), _sample_state()), MATCH)

    def test_verify_incompatible_tag_fails_closed(self):
        payload = json.dumps({"tagName": "v1.9.9", "name": "1.9.9", "isDraft": False})
        runner = lambda cmd: CommandResult(args=list(cmd), returncode=0, stdout=payload, stderr="")
        adapter = GitHubReleaseAdapter(runner=runner)
        with self.assertRaises(ConflictError):
            adapter.verify(_sample_manifest(), _sample_state())

    def test_verify_tool_unavailable_is_not_absent(self):
        runner = lambda cmd: CommandResult(args=list(cmd), returncode=127, stdout="", stderr="gh: command not found")
        adapter = GitHubReleaseAdapter(runner=runner)
        with self.assertRaises(VerificationUnavailableError):
            adapter.verify(_sample_manifest(), _sample_state())

    def test_publish_refuses_before_tagged(self):
        adapter = GitHubReleaseAdapter(runner=lambda cmd: CommandResult(args=[], returncode=0, stdout="", stderr=""))
        state = _sample_state()
        for target in ("PYPI_PUBLISHED", "GHCR_PUBLISHED", "DOCKERHUB_PUBLISHED", "EXTERNAL_VERIFIED"):
            state = advance(state, target)  # not yet TAGGED
        with self.assertRaises(OrderError):
            adapter.publish(_sample_manifest(), state)

    def test_publish_creates_release_once_tagged(self):
        state = _sample_state()
        for target in ("PYPI_PUBLISHED", "GHCR_PUBLISHED", "DOCKERHUB_PUBLISHED", "EXTERNAL_VERIFIED", "TAGGED"):
            state = advance(state, target)
        calls = []

        def runner(cmd):
            calls.append(cmd)
            return CommandResult(args=list(cmd), returncode=0, stdout="", stderr="")

        adapter = GitHubReleaseAdapter(runner=runner)
        adapter.publish(_sample_manifest(), state)
        self.assertEqual(calls[0][:3], ["gh", "release", "create"])
        self.assertIn("v2.0.0", calls[0])

    def test_publish_never_places_a_secret_in_the_command_line(self):
        state = _sample_state()
        for target in ("PYPI_PUBLISHED", "GHCR_PUBLISHED", "DOCKERHUB_PUBLISHED", "EXTERNAL_VERIFIED", "TAGGED"):
            state = advance(state, target)
        captured = {}

        def runner(cmd):
            captured["cmd"] = cmd
            return CommandResult(args=list(cmd), returncode=0, stdout="", stderr="")

        with mock.patch.dict("os.environ", {"GH_TOKEN": SENTINEL_SECRET}):
            adapter = GitHubReleaseAdapter(runner=runner)
            adapter.publish(_sample_manifest(), state)
        self.assertNotIn(SENTINEL_SECRET, " ".join(captured["cmd"]))


class AggregateVerificationAdapterTests(unittest.TestCase):
    class _Fake:
        def __init__(self, status):
            self._status = status
            self.name = "fake"

        def verify(self, manifest, state):
            if isinstance(self._status, Exception):
                raise self._status
            return self._status

        def publish(self, manifest, state):
            raise AssertionError("aggregate verification adapters must never publish")

    def test_match_only_when_every_sub_adapter_matches(self):
        aggregate = AggregateVerificationAdapter(name="ext", sub_adapters=[self._Fake(MATCH), self._Fake(MATCH)])
        self.assertEqual(aggregate.verify(_sample_manifest(), _sample_state()), MATCH)

    def test_absent_when_any_sub_adapter_is_absent(self):
        aggregate = AggregateVerificationAdapter(name="ext", sub_adapters=[self._Fake(MATCH), self._Fake(ABSENT)])
        self.assertEqual(aggregate.verify(_sample_manifest(), _sample_state()), ABSENT)

    def test_propagates_a_sub_adapter_conflict(self):
        aggregate = AggregateVerificationAdapter(name="ext", sub_adapters=[self._Fake(ConflictError("boom"))])
        with self.assertRaises(ConflictError):
            aggregate.verify(_sample_manifest(), _sample_state())

    def test_publish_is_a_documented_no_op_refusal(self):
        aggregate = AggregateVerificationAdapter(name="ext", sub_adapters=[])
        with self.assertRaises(ReleaseError):
            aggregate.publish(_sample_manifest(), _sample_state())


if __name__ == "__main__":
    unittest.main()
