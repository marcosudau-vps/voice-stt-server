"""AP-SRV-070 W5: read-only remote-artifact conflict detection.

Every test here uses an injected fake fetcher/runner - none makes a real
network call (section 17: "Do not use real public publishing as a test").
"""

from __future__ import annotations

import json
import unittest

from release_tooling.errors import ConflictError, VerificationUnavailableError
from release_tooling.remote_checks import (
    ABSENT,
    MATCH,
    CommandResult,
    check_pypi_release,
    check_registry_image,
)


class PyPIConflictTests(unittest.TestCase):
    def test_absent_release_is_safe_to_publish(self):
        result = check_pypi_release("voicestt", "2.0.0", {"voicestt-2.0.0.tar.gz": "a" * 64}, fetch=lambda url: None)
        self.assertEqual(result, ABSENT)

    def test_identical_existing_release_resumes_as_match(self):
        payload = {
            "releases": {
                "2.0.0": [
                    {"filename": "voicestt-2.0.0.tar.gz", "digests": {"sha256": "a" * 64}},
                    {"filename": "voicestt-2.0.0-py3-none-any.whl", "digests": {"sha256": "b" * 64}},
                ]
            }
        }
        result = check_pypi_release(
            "voicestt",
            "2.0.0",
            {"voicestt-2.0.0.tar.gz": "a" * 64, "voicestt-2.0.0-py3-none-any.whl": "b" * 64},
            fetch=lambda url: payload,
        )
        self.assertEqual(result, MATCH)

    def test_conflicting_hash_fails_closed(self):
        payload = {"releases": {"2.0.0": [{"filename": "voicestt-2.0.0.tar.gz", "digests": {"sha256": "different"}}]}}
        with self.assertRaises(ConflictError):
            check_pypi_release("voicestt", "2.0.0", {"voicestt-2.0.0.tar.gz": "a" * 64}, fetch=lambda url: payload)

    def test_missing_expected_file_fails_closed(self):
        payload = {"releases": {"2.0.0": []}}
        with self.assertRaises(ConflictError):
            check_pypi_release("voicestt", "2.0.0", {"voicestt-2.0.0.tar.gz": "a" * 64}, fetch=lambda url: payload)

    def test_fetcher_receives_the_expected_url(self):
        seen = {}

        def fetch(url):
            seen["url"] = url
            return None

        check_pypi_release("voicestt", "2.0.0", {}, fetch=fetch)
        self.assertEqual(seen["url"], "https://pypi.org/pypi/voicestt/2.0.0/json")


class RegistryConflictTests(unittest.TestCase):
    def _runner(self, returncode: int, stdout: str, stderr: str = ""):
        def runner(cmd):
            return CommandResult(args=list(cmd), returncode=returncode, stdout=stdout, stderr=stderr)

        return runner

    def test_absent_tag_is_safe_to_publish(self):
        # A real "docker manifest inspect" against a tag that does not exist
        # yet exits non-zero with a "no such manifest" style message - that
        # specific shape is what distinguishes a genuine absence from the
        # registry being unreachable (see test_unavailable_tool_fails_closed).
        result = check_registry_image(
            "ghcr.io/org/voice-stt-server:2.0.0",
            "sha256:" + "a" * 64,
            runner=self._runner(1, "", stderr="no such manifest: ghcr.io/org/voice-stt-server:2.0.0"),
        )
        self.assertEqual(result, ABSENT)

    def test_unavailable_tool_fails_closed_instead_of_claiming_absent(self):
        # A missing/unreachable docker binary or daemon must never be
        # silently treated as "safe to publish".
        with self.assertRaises(VerificationUnavailableError):
            check_registry_image(
                "ghcr.io/org/voice-stt-server:2.0.0",
                "sha256:" + "a" * 64,
                runner=self._runner(127, "", stderr="docker: command not found"),
            )

    def test_identical_remote_manifest_resumes_as_match(self):
        payload = json.dumps({"config": {"digest": "sha256:" + "a" * 64}})
        result = check_registry_image(
            "ghcr.io/org/voice-stt-server:2.0.0", "sha256:" + "a" * 64, runner=self._runner(0, payload)
        )
        self.assertEqual(result, MATCH)

    def test_conflicting_remote_digest_fails_closed(self):
        payload = json.dumps({"config": {"digest": "sha256:" + "b" * 64}})
        with self.assertRaises(ConflictError):
            check_registry_image(
                "ghcr.io/org/voice-stt-server:2.0.0", "sha256:" + "a" * 64, runner=self._runner(0, payload)
            )

    def test_non_json_manifest_fails_closed(self):
        with self.assertRaises(ConflictError):
            check_registry_image(
                "ghcr.io/org/voice-stt-server:2.0.0", "sha256:" + "a" * 64, runner=self._runner(0, "not json")
            )

    def test_runner_never_receives_a_push_or_tag_command(self):
        calls = []

        def runner(cmd):
            calls.append(cmd)
            return CommandResult(args=list(cmd), returncode=1, stdout="", stderr="no such manifest")

        check_registry_image("ghcr.io/org/voice-stt-server:2.0.0", "sha256:" + "a" * 64, runner=runner)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][:3], ["docker", "manifest", "inspect"])


if __name__ == "__main__":
    unittest.main()
