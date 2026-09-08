"""Read-only remote identity checks (AP-SRV-070 W5-R04).

Gates W5R4-G25 (exact identities verified), G26 (conflict hard-stops) and G27
(unverifiable state hard-stops). Every check here is offline: the PyPI fetcher
and the registry runner are both injected.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from release_support import RecordingRunner, digest_response, failed, ok, pypi_fetcher  # noqa: E402

from release_tooling.errors import ConflictError, VerificationUnavailableError  # noqa: E402
from release_tooling.remote_checks import (  # noqa: E402
    ABSENT,
    MATCH,
    check_pypi_release,
    check_registry_alias,
    check_registry_image,
    inspect_pypi_release,
    precheck_pypi,
    remote_manifest_digest,
)

DIGEST = "sha256:" + "a1" * 32
OTHER_DIGEST = "sha256:" + "b2" * 32


class PyPICheckTests(unittest.TestCase):
    def test_an_unpublished_project_is_absent(self):
        status = check_pypi_release(
            "voice-stt-server", "2.0.0", {"w.whl": "a" * 64}, fetch=pypi_fetcher({})
        )
        self.assertEqual(status, ABSENT)

    def test_identical_files_resume_as_match(self):
        # W5R4-G28: a rerun after a partial failure must not re-upload.
        # B5: Verified using the official PyPI release API shape with top-level 'urls'.
        fetch = pypi_fetcher({"voice-stt-server": {"w.whl": "a" * 64}})
        self.assertEqual(
            check_pypi_release("voice-stt-server", "2.0.0", {"w.whl": "a" * 64}, fetch=fetch),
            MATCH,
        )

    def test_current_release_specific_urls_shape_yields_match(self):
        # B5: Official PyPI endpoint https://pypi.org/pypi/<project>/<version>/json
        # returns {"info": {...}, "urls": [{"filename": "...", "digests": {"sha256": "..."}}]}.
        def official_fetch(url: str):
            return {
                "info": {"name": "voice-stt-server", "version": "2.0.0"},
                "urls": [
                    {"filename": "voice_stt_server-2.0.0-cp312-cp312-linux_x86_64.whl", "digests": {"sha256": "aa" * 32}},
                    {"filename": "voice_stt_server-2.0.0-cp312-cp312-win_amd64.whl", "digests": {"sha256": "bb" * 32}},
                ],
            }

        expected = {
            "voice_stt_server-2.0.0-cp312-cp312-linux_x86_64.whl": "aa" * 32,
            "voice_stt_server-2.0.0-cp312-cp312-win_amd64.whl": "bb" * 32,
        }
        res = inspect_pypi_release("voice-stt-server", "2.0.0", expected, fetch=official_fetch)
        self.assertEqual(res["status"], MATCH)
        self.assertEqual(set(res["matched"]), set(expected.keys()))
        self.assertEqual(res["absent"], [])
        self.assertEqual(res["conflicts"], [])

    def test_a_hash_mismatch_is_a_hard_conflict(self):
        # PyPI files are immutable, so a differing hash can never be resolved
        # by re-uploading - it must stop the release.
        fetch = pypi_fetcher({"voice-stt-server": {"w.whl": "b" * 64}})
        with self.assertRaises(ConflictError) as caught:
            check_pypi_release("voice-stt-server", "2.0.0", {"w.whl": "a" * 64}, fetch=fetch)
        self.assertIn("sha256 mismatch", str(caught.exception))

    def test_a_missing_expected_file_is_a_hard_conflict(self):
        fetch = pypi_fetcher({"voice-stt-server": {"other.whl": "a" * 64}})
        with self.assertRaises(ConflictError):
            check_pypi_release("voice-stt-server", "2.0.0", {"w.whl": "a" * 64}, fetch=fetch)

    def test_the_two_distributions_are_checked_independently(self):
        # Free published, Pro not: exactly the resume case the new authority
        # names (section 6).
        fetch = pypi_fetcher({"voice-stt-server": {"free.whl": "a" * 64}})
        self.assertEqual(
            check_pypi_release("voice-stt-server", "2.0.0", {"free.whl": "a" * 64}, fetch=fetch),
            MATCH,
        )
        self.assertEqual(
            check_pypi_release("voice-stt-server-pro", "2.0.0", {"pro.whl": "c" * 64}, fetch=fetch),
            ABSENT,
        )

    def test_partial_candidate_files_yields_partial_status(self):
        # B5: When some files match and others are absent, inspect returns PARTIAL
        # so staging can selectively upload only the missing ones.
        fetch = pypi_fetcher({"voice-stt-server": {"linux.whl": "aa" * 32}})
        expected = {"linux.whl": "aa" * 32, "win.whl": "bb" * 32}
        res = inspect_pypi_release("voice-stt-server", "2.0.0", expected, fetch=fetch)
        self.assertEqual(res["status"], "PARTIAL")
        self.assertEqual(res["matched"], ["linux.whl"])
        self.assertEqual(res["absent"], ["win.whl"])
        self.assertEqual(res["conflicts"], [])

    def test_response_without_usable_urls_fails_closed(self):
        # B5: Response missing top-level 'urls' must fail closed with VerificationUnavailableError
        # rather than being mistakenly treated as a safe empty release.
        malformed = lambda url: {"info": {"version": "2.0.0"}}  # missing urls key
        with self.assertRaises(VerificationUnavailableError) as caught:
            inspect_pypi_release("voice-stt-server", "2.0.0", {"w.whl": "a" * 64}, fetch=malformed)
        self.assertIn("missing or invalid 'urls' list", str(caught.exception))

        non_list = lambda url: {"urls": "invalid"}  # not a list
        with self.assertRaises(VerificationUnavailableError):
            inspect_pypi_release("voice-stt-server", "2.0.0", {"w.whl": "a" * 64}, fetch=non_list)

    def test_response_with_malformed_file_entry_fails_closed(self):
        # B5: File entry missing sha256 or filename fails closed
        missing_hash = lambda url: {"urls": [{"filename": "w.whl", "digests": {}}]}
        with self.assertRaises(VerificationUnavailableError):
            inspect_pypi_release("voice-stt-server", "2.0.0", {"w.whl": "a" * 64}, fetch=missing_hash)

    def test_empty_urls_list_yields_absent(self):
        # B5: A release existing on PyPI but having no distribution files uploaded yet
        # returns 'urls': [] and reports all expected files as absent.
        empty_urls = lambda url: {"info": {"name": "voice-stt-server"}, "urls": []}
        res = inspect_pypi_release("voice-stt-server", "2.0.0", {"w.whl": "a" * 64}, fetch=empty_urls)
        self.assertEqual(res["status"], ABSENT)
        self.assertEqual(res["matched"], [])
        self.assertEqual(res["absent"], ["w.whl"])



class RegistryDigestTests(unittest.TestCase):
    def test_a_missing_reference_reads_back_as_none(self):
        runner = RecordingRunner()
        self.assertIsNone(remote_manifest_digest("ghcr.io/x/y:2.0.0", runner=runner))

    def test_a_present_reference_returns_its_manifest_digest(self):
        runner = RecordingRunner([("imagetools inspect", digest_response(DIGEST))])
        self.assertEqual(remote_manifest_digest("ghcr.io/x/y:2.0.0", runner=runner), DIGEST)

    def test_the_check_is_read_only(self):
        # It must never pull, push, tag or create anything.
        runner = RecordingRunner([("imagetools inspect", digest_response(DIGEST))])
        remote_manifest_digest("ghcr.io/x/y:2.0.0", runner=runner)
        runner.assert_no_writes(self)
        self.assertEqual(len(runner.calls), 1)
        self.assertIn("inspect", runner.commands[0])

    def test_an_unreadable_registry_is_unavailable_not_absent(self):
        # W5R4-G27: "cannot check" must never be mistaken for "safe to
        # publish". A missing docker binary is the classic instance.
        runner = RecordingRunner(default=failed("docker: command not found", 127))
        with self.assertRaises(VerificationUnavailableError):
            remote_manifest_digest("ghcr.io/x/y:2.0.0", runner=runner)

    def test_a_garbled_digest_is_unavailable(self):
        runner = RecordingRunner([("imagetools inspect", ok("not-a-digest\n"))])
        with self.assertRaises(VerificationUnavailableError):
            remote_manifest_digest("ghcr.io/x/y:2.0.0", runner=runner)


class ExactTagCheckTests(unittest.TestCase):
    def test_absent_tag_is_safe_to_publish(self):
        self.assertEqual(
            check_registry_image("docker.io/x/y:2.0.0", DIGEST, runner=RecordingRunner()),
            ABSENT,
        )

    def test_matching_digest_resumes(self):
        runner = RecordingRunner([("imagetools inspect", digest_response(DIGEST))])
        self.assertEqual(check_registry_image("docker.io/x/y:2.0.0", DIGEST, runner=runner), MATCH)

    def test_a_different_digest_on_an_exact_tag_is_a_hard_conflict(self):
        # W5R4-G33: an exact version tag is immutable and is never repointed.
        runner = RecordingRunner([("imagetools inspect", digest_response(OTHER_DIGEST))])
        with self.assertRaises(ConflictError) as caught:
            check_registry_image("docker.io/x/y:2.0.0", DIGEST, runner=runner)
        self.assertIn("expected", str(caught.exception))

    def test_a_candidate_without_a_digest_cannot_be_verified(self):
        # The pre-W5-R04 manifest recorded a local image Id here, which is not
        # a registry-checkable identity. Refusing is the honest answer.
        runner = RecordingRunner()
        with self.assertRaises(VerificationUnavailableError):
            check_registry_image("docker.io/x/y:2.0.0", "", runner=runner)
        with self.assertRaises(VerificationUnavailableError):
            check_registry_image("docker.io/x/y:2.0.0", "sha256:not-hex", runner=runner)


class AliasCheckTests(unittest.TestCase):
    def test_an_alias_pointing_elsewhere_is_absent_not_a_conflict(self):
        # An alias is *meant* to move; only exact tags are immutable.
        runner = RecordingRunner([("imagetools inspect", digest_response(OTHER_DIGEST))])
        self.assertEqual(
            check_registry_alias("docker.io/x/y:latest", DIGEST, runner=runner), ABSENT
        )

    def test_an_alias_already_on_the_expected_digest_matches(self):
        runner = RecordingRunner([("imagetools inspect", digest_response(DIGEST))])
        self.assertEqual(
            check_registry_alias("docker.io/x/y:latest", DIGEST, runner=runner), MATCH
        )

    def test_a_missing_alias_is_absent(self):
        self.assertEqual(
            check_registry_alias("docker.io/x/y:latest", DIGEST, runner=RecordingRunner()),
            ABSENT,
        )

    def test_alias_checks_are_read_only(self):
        runner = RecordingRunner([("imagetools inspect", digest_response(DIGEST))])
        check_registry_alias("docker.io/x/y:latest", DIGEST, runner=runner)
        runner.assert_no_writes(self)


if __name__ == "__main__":
    unittest.main()
