"""Regression tests for the final W5-R04 Root Review corrections B7-B9."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from release_support import make_manifest, make_state  # noqa: E402

from release_tooling import cli, gitinfo, rc_manifest  # noqa: E402
from release_tooling.adapters import GitTagAdapter  # noqa: E402
from release_tooling.errors import ConflictError  # noqa: E402
from release_tooling.remote_checks import ABSENT  # noqa: E402
from tools import release_candidate  # noqa: E402


class PublishHappyPathVersionTests(unittest.TestCase):
    def test_real_publish_happy_path_uses_manifest_version_without_nameerror(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path = tmp_path / "rc-manifest.json"
            state_path = tmp_path / "state.json"
            manifest = make_manifest(version="2.0.0", release_readiness="QUALIFIED")
            rc_manifest.write_rc_manifest(manifest_path, manifest)

            preflight = SimpleNamespace(passed=True, to_json_dict=lambda: {"passed": True})
            engine_result = SimpleNamespace(
                stoppedEarly=False,
                to_json_dict=lambda: {"mode": "REAL", "finalState": "TAGGED"},
            )

            with mock.patch("release_tooling.preflight.run_preflight", return_value=preflight), \
                 mock.patch("release_tooling.adapters.build_default_adapters", return_value={}), \
                 mock.patch("release_tooling.engine.run_engine", return_value=engine_result) as run_engine:
                code = cli.main([
                    "publish",
                    "--manifest", str(manifest_path),
                    "--version", "2.0.0",
                    "--state-file", str(state_path),
                    "--until", "TAGGED",
                    "--yes",
                ])

            self.assertEqual(code, cli.EXIT_OK)
            run_engine.assert_called_once()
            state = run_engine.call_args.args[0]
            self.assertEqual(state.version, manifest["productVersion"])
            self.assertEqual(state.sourceCommit, manifest["sourceCommit"])


class GitTagIntegrationTests(unittest.TestCase):
    def _git(self, cwd: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        return result.stdout.strip()

    def _repos(self, root: Path) -> tuple[Path, Path, str]:
        remote = root / "remote.git"
        work = root / "work"
        remote.mkdir()
        work.mkdir()
        self._git(remote, "init", "--bare")
        self._git(work, "init")
        self._git(work, "config", "user.email", "w5r04@example.invalid")
        self._git(work, "config", "user.name", "W5-R04 Test")
        (work / "file.txt").write_text("one\n", encoding="utf-8")
        self._git(work, "add", "file.txt")
        self._git(work, "commit", "-m", "first")
        commit = self._git(work, "rev-parse", "HEAD")
        self._git(work, "remote", "add", "origin", str(remote))
        return work, remote, commit

    def test_remote_tag_commit_peels_annotated_tag_to_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            work, _remote, commit = self._repos(Path(tmp))
            gitinfo.create_tag(work, "v2.0.0", commit)
            gitinfo.push_tag(work, "origin", "v2.0.0")
            tag_object = self._git(work, "rev-parse", "refs/tags/v2.0.0")
            self.assertNotEqual(tag_object, commit)
            self.assertEqual(gitinfo.remote_tag_commit(work, "origin", "v2.0.0"), commit)

    def test_remote_tag_commit_supports_lightweight_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            work, _remote, commit = self._repos(Path(tmp))
            self._git(work, "tag", "v2.0.1", commit)
            self._git(work, "push", "origin", "refs/tags/v2.0.1")
            self.assertEqual(gitinfo.remote_tag_commit(work, "origin", "v2.0.1"), commit)

    def test_correct_local_tag_without_remote_is_absent_and_publish_resumes_push(self):
        with tempfile.TemporaryDirectory() as tmp:
            work, _remote, commit = self._repos(Path(tmp))
            manifest = make_manifest(version="2.0.0")
            manifest["sourceCommit"] = commit
            gitinfo.create_tag(work, "v2.0.0", commit)
            adapter = GitTagAdapter(repo_root=work, remote="origin")

            self.assertEqual(adapter.verify(manifest, make_state("PREPARED")), ABSENT)
            adapter.publish(manifest, make_state("PREPARED"))
            self.assertEqual(gitinfo.remote_tag_commit(work, "origin", "v2.0.0"), commit)

    def test_conflicting_local_tag_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            work, _remote, first = self._repos(Path(tmp))
            gitinfo.create_tag(work, "v2.0.0", first)
            (work / "file.txt").write_text("two\n", encoding="utf-8")
            self._git(work, "add", "file.txt")
            self._git(work, "commit", "-m", "second")
            second = self._git(work, "rev-parse", "HEAD")
            manifest = make_manifest(version="2.0.0")
            manifest["sourceCommit"] = second
            adapter = GitTagAdapter(repo_root=work, remote="origin")
            with self.assertRaises(ConflictError):
                adapter.verify(manifest, make_state("PREPARED"))


class CandidateInventoryTests(unittest.TestCase):
    def test_inventory_binds_final_qualified_manifest_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "rc-manifest.json"
            manifest = make_manifest(release_readiness=rc_manifest.READINESS_NOT_QUALIFIED)
            rc_manifest.write_rc_manifest(manifest_path, manifest)
            qualified = rc_manifest.qualify_manifest(
                manifest,
                evidence_ref="https://example.invalid/actions/runs/1",
                context="unit-test qualification",
                timestamp_utc="2026-09-08T00:00:00Z",
            )
            rc_manifest.write_rc_manifest(manifest_path, qualified)

            inventory = release_candidate.build_inventory(root)
            entry = next(item for item in inventory["files"] if item["path"] == "rc-manifest.json")
            actual = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            self.assertEqual(entry["sha256"], actual)
            self.assertEqual(json.loads(manifest_path.read_text())["releaseReadiness"], "QUALIFIED")

    def test_candidate_workflow_finalizes_inventory_after_qualification(self):
        workflow = (Path(__file__).resolve().parents[2] / ".github" / "workflows" / "release-candidate.yml").read_text(encoding="utf-8")
        qualify = workflow.index("- name: Qualify candidate manifest")
        inventory = workflow.index("- name: Build final SHA256 inventory")
        verify = workflow.index("- name: Verify final SHA256 inventory")
        upload = workflow.index("- name: Upload candidate artifacts")
        self.assertLess(qualify, inventory)
        self.assertLess(inventory, verify)
        self.assertLess(verify, upload)


if __name__ == "__main__":
    unittest.main()
