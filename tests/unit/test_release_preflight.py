"""AP-SRV-070 W5: read-only release preflight.

Every external dependency (Git, PATH tools, environment variables) is
mocked/monkeypatched so these tests never touch the real repository state,
the network, or Docker/git binaries, and never depend on this checkout's
actual current VERSION.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from release_tooling import preflight
from release_tooling.gitinfo import GitIdentity


CLEAN_IDENTITY = GitIdentity(commit="a" * 40, tree="b" * 40, dirty=False, branch="work/test")
DIRTY_IDENTITY = GitIdentity(commit="a" * 40, tree="b" * 40, dirty=True, branch="work/test")


class PreflightTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.repo_root = Path(self._tmp.name)
        (self.repo_root / "RELEASE_NOTES.md").write_text("# Release Notes\n\n## Unreleased\n", encoding="utf-8")
        self._env_patch = mock.patch.dict(os.environ, {}, clear=False)
        self._env_patch.start()
        for key in (
            "VOICESTT_RELEASE_GHCR_REPO",
            "VOICESTT_RELEASE_DOCKERHUB_REPO",
            "VOICESTT_RELEASE_PYPI_TOKEN",
            "VOICESTT_RELEASE_GHCR_TOKEN",
            "VOICESTT_RELEASE_DOCKERHUB_TOKEN",
            "VOICESTT_RELEASE_GITHUB_TOKEN",
        ):
            os.environ.pop(key, None)

    def tearDown(self):
        self._env_patch.stop()
        self._tmp.cleanup()

    def _run(self, **kwargs):
        defaults = dict(repo_root=self.repo_root, expected_version="2.0.0")
        defaults.update(kwargs)
        with mock.patch.object(preflight, "read_version_file", return_value="2.0.0"), \
             mock.patch.object(preflight.gitinfo, "resolve_identity", return_value=CLEAN_IDENTITY), \
             mock.patch.object(preflight.gitinfo, "local_tag_commit", return_value=None):
            return preflight.run_preflight(**defaults)

    def _find(self, report, name):
        for check in report.checks:
            if check.name == name:
                return check
        raise AssertionError(f"no check named {name!r} in {[c.name for c in report.checks]}")


class VersionCheckTests(PreflightTestCase):
    def test_matching_version_passes(self):
        report = self._run(expected_version="2.0.0")
        self.assertEqual(self._find(report, "version_matches_expected").status, preflight.PASS)

    def test_mismatched_version_fails(self):
        report = self._run(expected_version="2.0.1")
        self.assertEqual(self._find(report, "version_matches_expected").status, preflight.FAIL)
        self.assertFalse(report.passed)


class ReleaseNotesCheckTests(PreflightTestCase):
    def test_missing_dated_section_fails(self):
        report = self._run()
        self.assertEqual(self._find(report, "release_notes_prepared").status, preflight.FAIL)

    def test_present_dated_section_passes(self):
        (self.repo_root / "RELEASE_NOTES.md").write_text("# Release Notes\n\n## 2.0.0 - 2026-09-06\n", encoding="utf-8")
        report = self._run()
        self.assertEqual(self._find(report, "release_notes_prepared").status, preflight.PASS)

    def test_missing_file_fails(self):
        (self.repo_root / "RELEASE_NOTES.md").unlink()
        report = self._run()
        self.assertEqual(self._find(report, "release_notes_prepared").status, preflight.FAIL)


class GitCheckTests(PreflightTestCase):
    def test_clean_tree_and_matching_commit_tree_pass(self):
        with mock.patch.object(preflight, "read_version_file", return_value="2.0.0"), \
             mock.patch.object(preflight.gitinfo, "resolve_identity", return_value=CLEAN_IDENTITY), \
             mock.patch.object(preflight.gitinfo, "local_tag_commit", return_value=None):
            report = preflight.run_preflight(
                repo_root=self.repo_root, expected_version="2.0.0",
                expected_commit="a" * 40, expected_tree="b" * 40,
            )
        self.assertEqual(self._find(report, "git_clean_tree").status, preflight.PASS)
        self.assertEqual(self._find(report, "git_exact_commit").status, preflight.PASS)
        self.assertEqual(self._find(report, "git_exact_tree").status, preflight.PASS)

    def test_dirty_tree_fails(self):
        with mock.patch.object(preflight, "read_version_file", return_value="2.0.0"), \
             mock.patch.object(preflight.gitinfo, "resolve_identity", return_value=DIRTY_IDENTITY), \
             mock.patch.object(preflight.gitinfo, "local_tag_commit", return_value=None):
            report = preflight.run_preflight(repo_root=self.repo_root, expected_version="2.0.0")
        self.assertEqual(self._find(report, "git_clean_tree").status, preflight.FAIL)

    def test_unexpected_commit_fails(self):
        with mock.patch.object(preflight, "read_version_file", return_value="2.0.0"), \
             mock.patch.object(preflight.gitinfo, "resolve_identity", return_value=CLEAN_IDENTITY), \
             mock.patch.object(preflight.gitinfo, "local_tag_commit", return_value=None):
            report = preflight.run_preflight(
                repo_root=self.repo_root, expected_version="2.0.0", expected_commit="c" * 40,
            )
        self.assertEqual(self._find(report, "git_exact_commit").status, preflight.FAIL)


class TagCheckTests(PreflightTestCase):
    def test_absent_tag_passes(self):
        report = self._run()
        self.assertEqual(self._find(report, "git_tag_absent_or_compatible").status, preflight.PASS)

    def test_tag_pointing_at_expected_commit_passes(self):
        with mock.patch.object(preflight, "read_version_file", return_value="2.0.0"), \
             mock.patch.object(preflight.gitinfo, "resolve_identity", return_value=CLEAN_IDENTITY), \
             mock.patch.object(preflight.gitinfo, "local_tag_commit", return_value="a" * 40):
            report = preflight.run_preflight(
                repo_root=self.repo_root, expected_version="2.0.0", expected_commit="a" * 40,
            )
        self.assertEqual(self._find(report, "git_tag_absent_or_compatible").status, preflight.PASS)

    def test_tag_pointing_elsewhere_fails(self):
        with mock.patch.object(preflight, "read_version_file", return_value="2.0.0"), \
             mock.patch.object(preflight.gitinfo, "resolve_identity", return_value=CLEAN_IDENTITY), \
             mock.patch.object(preflight.gitinfo, "local_tag_commit", return_value="z" * 40):
            report = preflight.run_preflight(
                repo_root=self.repo_root, expected_version="2.0.0", expected_commit="a" * 40,
            )
        self.assertEqual(self._find(report, "git_tag_absent_or_compatible").status, preflight.FAIL)


class RegistryAndCredentialCheckTests(PreflightTestCase):
    def test_unset_registry_identifiers_fail(self):
        report = self._run()
        self.assertEqual(self._find(report, "ghcr_repo_configured").status, preflight.FAIL)
        self.assertEqual(self._find(report, "dockerhub_repo_configured").status, preflight.FAIL)

    def test_configured_registry_identifiers_pass(self):
        with mock.patch.dict(os.environ, {
            "VOICESTT_RELEASE_GHCR_REPO": "ghcr.io/org/voice-stt-server",
            "VOICESTT_RELEASE_DOCKERHUB_REPO": "org/voice-stt-server",
        }):
            report = self._run()
        self.assertEqual(self._find(report, "ghcr_repo_configured").status, preflight.PASS)
        self.assertEqual(self._find(report, "dockerhub_repo_configured").status, preflight.PASS)

    def test_credential_presence_never_leaks_the_value(self):
        with mock.patch.dict(os.environ, {"VOICESTT_RELEASE_PYPI_TOKEN": "pypi-supersecretvalue"}):
            report = self._run()
        check = self._find(report, "credential_pypiTokenPresent")
        self.assertEqual(check.status, preflight.PASS)
        self.assertNotIn("supersecretvalue", check.detail)


class StateConflictCheckTests(PreflightTestCase):
    def test_no_existing_state_passes(self):
        report = self._run()
        self.assertEqual(self._find(report, "no_state_conflict").status, preflight.PASS)

    def test_existing_valid_state_passes_and_reports_it(self):
        from release_tooling.state import default_state_path, new_state, save_state

        state = new_state(
            version="2.0.0", source_commit="a" * 40, source_tree="b" * 40,
            wheel={"filename": "w.whl", "sha256": "c" * 64},
            sdist={"filename": "s.tar.gz", "sha256": "d" * 64},
            free_image={"tag": "t:1", "imageId": "id1"},
            pro_image={"tag": "t:2", "imageId": "id2"},
        )
        save_state(default_state_path(self.repo_root, "2.0.0"), state)
        report = self._run()
        check = self._find(report, "no_state_conflict")
        self.assertEqual(check.status, preflight.PASS)
        self.assertIn("PREPARED", check.detail)

    def test_corrupted_state_fails(self):
        from release_tooling.state import default_state_path

        state_path = default_state_path(self.repo_root, "2.0.0")
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text("{not json", encoding="utf-8")
        report = self._run()
        self.assertEqual(self._find(report, "no_state_conflict").status, preflight.FAIL)


class OverallPassFailTests(PreflightTestCase):
    def test_preflight_never_writes_anything_under_repo_root(self):
        before = sorted(p.relative_to(self.repo_root).as_posix() for p in self.repo_root.rglob("*"))
        self._run()
        after = sorted(p.relative_to(self.repo_root).as_posix() for p in self.repo_root.rglob("*"))
        self.assertEqual(before, after)

    def test_report_passed_is_false_if_any_check_fails(self):
        report = self._run(expected_version="9.9.9")
        self.assertFalse(report.passed)


if __name__ == "__main__":
    unittest.main()
