"""AP-SRV-070 - the single automatic product version authority.

Before this module, ``setup.py`` carried its own ``current_version`` string
and ``api_fastapi_server/protocol_v2/identity.py`` carried a second,
independently hardcoded ``SERVER_VERSION`` (W0 finding: they had drifted,
``1.0.2`` vs. the already-established v2 identity ``2.0.0``). These tests pin
down the resolver in ``VoiceSTT/_version.py`` that replaces both, and prove
that the whole product - package metadata, the running server, the v2
handshake and the FastAPI app itself - reports one consistent value.
"""

import importlib
import os
import pathlib
import re
import unittest
from importlib import metadata as importlib_metadata
from unittest import mock

from VoiceSTT import _version


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


class SemVerValidationTests(unittest.TestCase):
    def test_accepts_plain_release_versions(self):
        for value in ("0.0.0", "1.0.0", "2.0.0", "10.20.30"):
            with self.subTest(value=value):
                self.assertTrue(_version.is_valid_semver(value))

    def test_accepts_prerelease_and_build_metadata(self):
        for value in ("1.0.0-rc.1", "1.0.0+build.5", "1.0.0-rc.1+build.5"):
            with self.subTest(value=value):
                self.assertTrue(_version.is_valid_semver(value))

    def test_rejects_invalid_versions(self):
        # Note: incidental surrounding whitespace is intentionally tolerated
        # (see parse_semver) so a VERSION file's trailing newline or an
        # env-var override with accidental padding still resolves cleanly;
        # that is not exercised as an "invalid" case here.
        for value in (
            "1.0", "1", "v1.0.0", "1.0.0.0", "1.0.0-", "01.0.0", "1.00.0",
            "", "not-a-version",
        ):
            with self.subTest(value=value):
                self.assertFalse(_version.is_valid_semver(value))

    def test_validate_semver_raises_for_invalid_input(self):
        with self.assertRaises(_version.SemVerError):
            _version.validate_semver("not-a-version")

    def test_validate_semver_returns_the_value_for_valid_input(self):
        self.assertEqual(_version.validate_semver("1.2.3"), "1.2.3")


class BumpTests(unittest.TestCase):
    def test_patch_increments_patch_only(self):
        self.assertEqual(_version.bump("1.2.3", "patch"), "1.2.4")

    def test_minor_increments_minor_and_resets_patch(self):
        self.assertEqual(_version.bump("1.2.3", "minor"), "1.3.0")

    def test_major_increments_major_and_resets_minor_and_patch(self):
        self.assertEqual(_version.bump("1.2.3", "major"), "2.0.0")

    def test_bump_from_a_prerelease_input_drops_the_suffix(self):
        self.assertEqual(_version.bump("1.2.3-rc.1", "patch"), "1.2.4")

    def test_bump_rejects_an_unknown_kind(self):
        with self.assertRaises(ValueError):
            _version.bump("1.2.3", "sideways")

    def test_bump_rejects_an_invalid_input_version(self):
        with self.assertRaises(_version.SemVerError):
            _version.bump("not-a-version", "patch")


class ResolveBumpKindTests(unittest.TestCase):
    def test_no_flags_means_patch(self):
        self.assertEqual(_version.resolve_bump_kind(minor=False, major=False), "patch")

    def test_minor_flag(self):
        self.assertEqual(_version.resolve_bump_kind(minor=True, major=False), "minor")

    def test_major_flag(self):
        self.assertEqual(_version.resolve_bump_kind(minor=False, major=True), "major")

    def test_minor_and_major_together_is_rejected(self):
        with self.assertRaises(ValueError):
            _version.resolve_bump_kind(minor=True, major=True)


class VersionFileTests(unittest.TestCase):
    def test_version_file_exists_at_repo_root(self):
        path = REPO_ROOT / "VERSION"
        self.assertTrue(path.is_file(), f"missing {path}")

    def test_version_file_is_valid_semver(self):
        content = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertTrue(_version.is_valid_semver(content))

    def test_version_file_has_no_stray_whitespace_or_prefix(self):
        raw = (REPO_ROOT / "VERSION").read_text(encoding="utf-8")
        self.assertEqual(raw, raw.strip() + "\n")
        self.assertFalse(raw.lstrip().startswith("v"))

    def test_read_version_file_matches_disk_content(self):
        expected = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(_version.read_version_file(), expected)


class ResolveVersionTests(unittest.TestCase):
    def setUp(self):
        self._env_backup = os.environ.pop(_version.BUILD_VERSION_ENV, None)
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        if self._env_backup is None:
            os.environ.pop(_version.BUILD_VERSION_ENV, None)
        else:
            os.environ[_version.BUILD_VERSION_ENV] = self._env_backup

    def test_resolves_to_the_version_file_by_default(self):
        expected = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(_version.resolve_version(), expected)

    def test_build_override_wins_over_the_version_file(self):
        os.environ[_version.BUILD_VERSION_ENV] = "9.9.9"
        self.assertEqual(_version.resolve_version(), "9.9.9")

    def test_build_override_is_stripped_of_surrounding_whitespace(self):
        os.environ[_version.BUILD_VERSION_ENV] = "  9.9.9  "
        self.assertEqual(_version.resolve_version(), "9.9.9")

    def test_blank_override_is_treated_as_unset(self):
        os.environ[_version.BUILD_VERSION_ENV] = "   "
        expected = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(_version.resolve_version(), expected)

    def test_invalid_override_is_a_hard_error_not_a_silent_fallback(self):
        os.environ[_version.BUILD_VERSION_ENV] = "not-a-version"
        with self.assertRaises(_version.SemVerError):
            _version.resolve_version()

    def test_repeated_resolution_without_a_release_in_between_is_deterministic(self):
        first = _version.resolve_version()
        second = _version.resolve_version()
        self.assertEqual(first, second)

    def test_falls_back_to_installed_metadata_when_no_version_file_is_present(self):
        with mock.patch.object(
            _version, "_version_file_path",
            return_value=pathlib.Path("Z:/does/not/exist/VERSION"),
        ):
            with mock.patch.object(
                importlib_metadata, "version", return_value="3.4.5",
            ):
                self.assertEqual(_version.resolve_version(), "3.4.5")


class RuntimeConsistencyTests(unittest.TestCase):
    """W3-06: setup/package/runtime/handshake must agree, always."""

    def setUp(self):
        self._env_backup = os.environ.pop(_version.BUILD_VERSION_ENV, None)
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        if self._env_backup is None:
            os.environ.pop(_version.BUILD_VERSION_ENV, None)
        else:
            os.environ[_version.BUILD_VERSION_ENV] = self._env_backup

    def test_package_and_identity_agree_on_the_baseline_version(self):
        import VoiceSTT
        from api_fastapi_server.protocol_v2 import identity

        expected = _version.resolve_version()
        self.assertEqual(VoiceSTT.get_version(), expected)
        self.assertEqual(VoiceSTT.__version__, expected)
        self.assertEqual(identity.server_version(), expected)

    def test_build_override_propagates_to_package_and_handshake_identically(self):
        import VoiceSTT
        from api_fastapi_server.protocol_v2 import identity

        os.environ[_version.BUILD_VERSION_ENV] = "7.8.9"
        try:
            self.assertEqual(VoiceSTT.get_version(), "7.8.9")
            self.assertEqual(identity.server_version(), "7.8.9")
        finally:
            os.environ.pop(_version.BUILD_VERSION_ENV, None)

    def test_no_second_hardcoded_semver_literal_in_identity_module(self):
        """Only comments may mention a literal version; no assignable one."""
        source = pathlib.Path(
            REPO_ROOT / "api_fastapi_server" / "protocol_v2" / "identity.py"
        ).read_text(encoding="utf-8")
        code_lines = [
            line for line in source.splitlines()
            if not line.strip().startswith("#")
        ]
        code_without_comments = "\n".join(code_lines)
        self.assertNotRegex(
            code_without_comments,
            r'=\s*["\']\d+\.\d+\.\d+["\']',
            "identity.py must resolve the version, not assign a literal one",
        )

    def test_no_second_hardcoded_semver_literal_in_setup_py(self):
        source = (REPO_ROOT / "setup.py").read_text(encoding="utf-8")
        code_lines = [
            line for line in source.splitlines()
            if not line.strip().startswith("#")
        ]
        code_without_comments = "\n".join(code_lines)
        self.assertNotRegex(
            code_without_comments,
            r'current_version\s*=\s*["\']\d+\.\d+\.\d+["\']',
            "setup.py must resolve current_version, not assign a literal",
        )

    def test_fastapi_app_version_reads_the_same_authority(self):
        from api_fastapi_server import server as server_module
        from tests.unit.test_fastapi_server_multi_user import (
            AutoScheduler, FakeRecorder,
        )

        app = server_module.create_app(
            scheduler_factory=AutoScheduler, recorder_factory=FakeRecorder,
        )
        self.assertEqual(app.version, _version.resolve_version())


if __name__ == "__main__":
    unittest.main()
