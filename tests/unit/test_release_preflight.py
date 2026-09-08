"""AP-SRV-070 W5: read-only release preflight.

Every external dependency (Git, PATH tools, environment variables) is
mocked/monkeypatched so these tests never touch the real repository state,
the network, or Docker/git binaries, and never depend on this checkout's
actual current VERSION.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
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
            "DOCKERHUB_USERNAME",
            "DOCKERHUB_TOKEN",
            "GITHUB_TOKEN",
            "GITHUB_REPOSITORY_OWNER",
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
    def test_the_ghcr_root_is_derived_and_needs_no_operator_variable(self):
        # AP-SRV-070 W5-R04 section 24: minimise required configuration. A
        # GHCR package always lives under the repository owner, so requiring
        # the operator to also state the registry root would be redundant.
        report = self._run()
        check = self._find(report, "ghcr_repo_derived")
        self.assertEqual(check.status, preflight.PASS)
        self.assertIn("ghcr.io/marcosudau-vps", check.detail)

    def test_the_ghcr_root_follows_the_runner_owner_when_present(self):
        with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY_OWNER": "some-fork-owner"}):
            report = self._run()
        self.assertIn("ghcr.io/some-fork-owner", self._find(report, "ghcr_repo_derived").detail)

    def test_an_unset_dockerhub_namespace_fails_closed(self):
        # It genuinely cannot be derived, so preflight refuses rather than
        # guessing a namespace and publishing into somebody else's account.
        report = self._run()
        self.assertEqual(self._find(report, "dockerhub_repo_configured").status, preflight.FAIL)
        self.assertFalse(report.passed)

    def test_a_configured_dockerhub_namespace_passes(self):
        with mock.patch.dict(os.environ, {"DOCKERHUB_USERNAME": "marcosudau"}):
            report = self._run()
        self.assertEqual(self._find(report, "dockerhub_repo_configured").status, preflight.PASS)

    def test_both_public_distributions_are_reported(self):
        report = self._run()
        self.assertIn("voice-stt-server", self._find(report, "pypi_project_free").detail)
        self.assertIn("voice-stt-server-pro", self._find(report, "pypi_project_pro").detail)

    def test_both_public_images_are_reported(self):
        report = self._run()
        self.assertIn("voice-stt-server", self._find(report, "image_name_free").detail)
        self.assertIn("voice-stt-server-pro", self._find(report, "image_name_pro").detail)

    def test_credential_presence_never_leaks_the_value(self):
        # W5R4-G49: only a boolean ever reaches a report.
        with mock.patch.dict(os.environ, {"DOCKERHUB_TOKEN": "dckr_pat_supersecretvalue"}):
            report = self._run()
        check = self._find(report, "credential_dockerhubTokenPresent")
        self.assertEqual(check.status, preflight.PASS)
        self.assertNotIn("supersecretvalue", check.detail)

    def test_no_pypi_token_is_required_at_all(self):
        # Section 17 / W5R4-G47: Trusted Publishing means there is no token.
        report = self._run()
        names = [check.name for check in report.checks]
        self.assertNotIn("credential_pypiTokenPresent", names)


class LocalPathGuardTests(PreflightTestCase):
    def test_a_manifest_with_an_operator_local_path_fails(self):
        # W5R4-G07: a candidate that names P:\... could only ever be published
        # from one machine.
        import json
        from release_support import make_manifest

        manifest = make_manifest()
        manifest["qualification"]["evidenceRef"] = r"P:\GithubRepos\evidence"
        path = self.repo_root / "rc-manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        report = self._run(rc_manifest_path=path)
        check = self._find(report, "no_local_path_dependency")
        self.assertEqual(check.status, preflight.FAIL)

    def test_a_clean_manifest_passes(self):
        from release_support import make_manifest
        from release_tooling import rc_manifest as rcm

        path = self.repo_root / "rc-manifest.json"
        rcm.write_rc_manifest(path, make_manifest())
        report = self._run(rc_manifest_path=path)
        self.assertEqual(self._find(report, "no_local_path_dependency").status, preflight.PASS)


class StateConflictCheckTests(PreflightTestCase):
    def test_no_existing_state_passes(self):
        report = self._run()
        self.assertEqual(self._find(report, "no_state_conflict").status, preflight.PASS)

    def test_existing_valid_state_passes_and_reports_it(self):
        from release_tooling.state import default_state_path, new_state, save_state

        state = new_state(
            version="2.0.0", source_commit="a" * 40, source_tree="b" * 40,
            distributions={
                "free": {"name": "voice-stt-server", "wheels": "w.whl=" + "c" * 64},
                "pro": {"name": "voice-stt-server-pro", "wheels": "p.whl=" + "d" * 64},
            },
            images={
                "free": {"tag": "voice-stt-server:2.0.0", "digest": "sha256:" + "1" * 64},
                "pro": {"tag": "voice-stt-server-pro:2.0.0", "digest": "sha256:" + "2" * 64},
            },
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


class QualificationCheckTests(PreflightTestCase):
    def test_unqualified_manifest_warns_by_default(self):
        from release_support import make_manifest
        from release_tooling import rc_manifest as rcm

        manifest = make_manifest(release_readiness=rcm.READINESS_NOT_QUALIFIED)
        path = self.repo_root / "rc-manifest.json"
        rcm.write_rc_manifest(path, manifest)
        report = self._run(rc_manifest_path=path, require_qualified=False)
        check = self._find(report, "candidate_qualification")
        self.assertEqual(check.status, preflight.WARN)

    def test_unqualified_manifest_fails_when_qualification_required(self):
        from release_support import make_manifest
        from release_tooling import rc_manifest as rcm

        manifest = make_manifest(release_readiness=rcm.READINESS_NOT_QUALIFIED)
        path = self.repo_root / "rc-manifest.json"
        rcm.write_rc_manifest(path, manifest)
        report = self._run(rc_manifest_path=path, require_qualified=True)
        check = self._find(report, "candidate_qualification")
        self.assertEqual(check.status, preflight.FAIL)
        self.assertFalse(report.passed)

    def test_qualified_manifest_passes_when_qualification_required(self):
        from release_support import make_manifest
        from release_tooling import rc_manifest as rcm

        manifest = make_manifest(release_readiness=rcm.READINESS_QUALIFIED)
        path = self.repo_root / "rc-manifest.json"
        rcm.write_rc_manifest(path, manifest)
        report = self._run(rc_manifest_path=path, require_qualified=True)
        check = self._find(report, "candidate_qualification")
        self.assertEqual(check.status, preflight.PASS)

    def test_qualified_manifest_without_evidence_ref_fails(self):
        import json
        from release_support import make_manifest

        manifest = make_manifest(release_readiness="QUALIFIED")
        manifest["qualification"]["evidenceRef"] = ""
        path = self.repo_root / "rc-manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        report = self._run(rc_manifest_path=path, require_qualified=True)
        check = self._find(report, "candidate_qualification")
        self.assertEqual(check.status, preflight.FAIL)


class ManifestVersionCheckTests(PreflightTestCase):
    def test_matching_manifest_version_passes(self):
        from release_support import make_manifest
        from release_tooling import rc_manifest as rcm

        manifest = make_manifest(version="2.0.0")
        path = self.repo_root / "rc-manifest.json"
        rcm.write_rc_manifest(path, manifest)
        report = self._run(rc_manifest_path=path, expected_version="2.0.0")
        check = self._find(report, "rc_manifest_version_matches")
        self.assertEqual(check.status, preflight.PASS)

    def test_mismatched_manifest_version_fails(self):
        from release_support import make_manifest
        from release_tooling import rc_manifest as rcm

        manifest = make_manifest(version="2.0.0")
        path = self.repo_root / "rc-manifest.json"
        rcm.write_rc_manifest(path, manifest)
        report = self._run(rc_manifest_path=path, expected_version="2.0.1")
        check = self._find(report, "rc_manifest_version_matches")
        self.assertEqual(check.status, preflight.FAIL)
        self.assertFalse(report.passed)

    def test_no_manifest_warns(self):
        report = self._run(rc_manifest_path=None, expected_version="2.0.0")
        check = self._find(report, "rc_manifest_version_matches")
        self.assertEqual(check.status, preflight.WARN)


if __name__ == "__main__":
    unittest.main()
