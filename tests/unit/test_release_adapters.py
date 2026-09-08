"""Publication adapters (AP-SRV-070 W5-R04).

Gates covered: W5R4-G20 (dry-run zero writes), G21/G22 (tag before the first
public artifact), G23/G24 (Docker Hub first, GHCR by manifest promotion with no
second build), G25 (post-write verification), G26/G27 (fail closed), G28 (the
Free/Pro resume case), G30 (a tag is never moved), G38/G39 (aliases only after
verification, and verified after being set), G49 (no secret in output).

Every adapter is driven with an injected fake runner/fetcher, so nothing here
can reach PyPI, a registry, git or ``gh``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from release_support import (  # noqa: E402
    DOCKERHUB_ROOT,
    FREE_DIGEST,
    FREE_WHEEL,
    FREE_WHEEL_SHA,
    FREE_WHEEL_WIN,
    FREE_WHEEL_WIN_SHA,
    GHCR_ROOT,
    PRO_DIGEST,
    PRO_WHEEL,
    PRO_WHEEL_SHA,
    PRO_WHEEL_WIN,
    PRO_WHEEL_WIN_SHA,
    RecordingRunner,
    digest_response,
    failed,
    make_manifest,
    make_state,
    ok,
    pypi_fetcher,
)

from release_tooling.adapters import (  # noqa: E402
    AliasAdapter,
    DockerHubAdapter,
    ExternalUploader,
    GHCRAdapter,
    GitHubReleaseAdapter,
    GitTagAdapter,
    PyPIAdapter,
    TwineUploader,
    AggregateVerificationAdapter,
)
from release_tooling.errors import ConflictError, OrderError, ReleaseError, VerificationUnavailableError  # noqa: E402
from release_tooling.remote_checks import ABSENT, MATCH  # noqa: E402

MANIFEST = make_manifest()
BOTH_PUBLISHED = {
    "voice-stt-server": {
        FREE_WHEEL: FREE_WHEEL_SHA,
        FREE_WHEEL_WIN: FREE_WHEEL_WIN_SHA,
    },
    "voice-stt-server-pro": {
        PRO_WHEEL: PRO_WHEEL_SHA,
        PRO_WHEEL_WIN: PRO_WHEEL_WIN_SHA,
    },
}


class RecordingUploader:
    def __init__(self):
        self.uploads = []

    def upload(self, distribution, filenames):
        self.uploads.append((distribution, list(filenames)))


class PyPIAdapterTests(unittest.TestCase):
    def test_both_distributions_must_be_published_for_a_match(self):
        adapter = PyPIAdapter(uploader=RecordingUploader(), fetch=pypi_fetcher(BOTH_PUBLISHED))
        self.assertEqual(adapter.verify(MANIFEST, make_state("TAGGED")), MATCH)

    def test_only_free_published_is_not_a_match(self):
        # Section 6: PYPI_PUBLISHED means *both*, never "one of them worked".
        partial = {
            "voice-stt-server": {
                FREE_WHEEL: FREE_WHEEL_SHA,
                FREE_WHEEL_WIN: FREE_WHEEL_WIN_SHA,
            }
        }
        adapter = PyPIAdapter(uploader=RecordingUploader(), fetch=pypi_fetcher(partial))
        self.assertEqual(adapter.verify(MANIFEST, make_state("TAGGED")), ABSENT)

    def test_resume_uploads_only_the_missing_distribution(self):
        # W5R4-G28: Free already live, Pro missing -> publish Pro only.
        partial = {
            "voice-stt-server": {
                FREE_WHEEL: FREE_WHEEL_SHA,
                FREE_WHEEL_WIN: FREE_WHEEL_WIN_SHA,
            }
        }
        uploader = RecordingUploader()
        adapter = PyPIAdapter(uploader=uploader, fetch=pypi_fetcher(partial))
        adapter.publish(MANIFEST, make_state("TAGGED"))
        self.assertEqual([name for name, _ in uploader.uploads], ["voice-stt-server-pro"])

    def test_a_conflicting_distribution_hard_stops(self):
        conflicting = {"voice-stt-server": {FREE_WHEEL: "0" * 64}}
        adapter = PyPIAdapter(uploader=RecordingUploader(), fetch=pypi_fetcher(conflicting))
        with self.assertRaises(ConflictError):
            adapter.verify(MANIFEST, make_state("TAGGED"))

    def test_publishing_before_the_tag_is_refused(self):
        # W5R4-G21/G22, enforced by the adapter itself.
        adapter = PyPIAdapter(uploader=RecordingUploader(), fetch=pypi_fetcher({}))
        with self.assertRaises(OrderError):
            adapter.publish(MANIFEST, make_state("PREPARED"))

    def test_a_network_failure_is_unavailable_not_absent(self):
        def exploding(url):
            raise OSError("dns failure")

        adapter = PyPIAdapter(uploader=RecordingUploader(), fetch=exploding)
        with self.assertRaises(VerificationUnavailableError):
            adapter.verify(MANIFEST, make_state("TAGGED"))

    def test_trusted_publishing_refuses_to_upload_itself(self):
        # The engine must verify the OIDC action's result, never quietly fall
        # back to some other credential path.
        adapter = PyPIAdapter(uploader=ExternalUploader(), fetch=pypi_fetcher({}))
        with self.assertRaises(ReleaseError) as caught:
            adapter.publish(MANIFEST, make_state("TAGGED"))
        self.assertIn("gh-action-pypi-publish", str(caught.exception))

    def test_twine_uploader_refuses_when_the_qualified_wheel_is_missing(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            uploader = TwineUploader(dist_dir=Path(tmp), runner=RecordingRunner())
            with self.assertRaises(ReleaseError) as caught:
                uploader.upload("voice-stt-server", [FREE_WHEEL])
            self.assertIn("missing", str(caught.exception))


class DockerHubPromotionTests(unittest.TestCase):
    def _adapter(self, runner):
        return DockerHubAdapter(repo_root=DOCKERHUB_ROOT, runner=runner)

    def test_absent_tags_are_safe_to_publish(self):
        self.assertEqual(
            self._adapter(RecordingRunner()).verify(MANIFEST, make_state("PYPI_PUBLISHED")),
            ABSENT,
        )

    def test_both_variants_present_is_a_match(self):
        runner = RecordingRunner([
            ("marcosudau/voice-stt-server:2.0.0", digest_response(FREE_DIGEST)),
            ("marcosudau/voice-stt-server-pro:2.0.0", digest_response(PRO_DIGEST)),
        ])
        self.assertEqual(
            self._adapter(runner).verify(MANIFEST, make_state("PYPI_PUBLISHED")), MATCH
        )

    def test_publication_promotes_the_staging_manifest_and_never_builds(self):
        # W5R4-G24: no second production build anywhere in the graph.
        runner = RecordingRunner()
        self._adapter(runner).publish(MANIFEST, make_state("PYPI_PUBLISHED"))
        creates = [c for c in runner.commands if "imagetools create" in c]
        self.assertEqual(len(creates), 2)
        for command in creates:
            self.assertIn("-staging@sha256:", command)
        # "docker buildx imagetools" is a manifest copy, not a build; a real
        # image build would start with "docker build ".
        self.assertFalse([c for c in runner.commands if c.startswith("docker build ")])

    def test_publication_before_the_tag_is_refused(self):
        with self.assertRaises(OrderError):
            self._adapter(RecordingRunner()).publish(MANIFEST, make_state("PREPARED"))

    def test_an_already_promoted_variant_is_not_promoted_again(self):
        runner = RecordingRunner([
            ("marcosudau/voice-stt-server:2.0.0", digest_response(FREE_DIGEST)),
        ])
        self._adapter(runner).publish(MANIFEST, make_state("PYPI_PUBLISHED"))
        creates = [c for c in runner.commands if "imagetools create" in c]
        self.assertEqual(len(creates), 1)
        self.assertIn("voice-stt-server-pro", creates[0])

    def test_an_unconfigured_namespace_is_unavailable(self):
        adapter = DockerHubAdapter(repo_root="", runner=RecordingRunner())
        with self.assertRaises(VerificationUnavailableError):
            adapter.verify(MANIFEST, make_state("PYPI_PUBLISHED"))

    def test_a_conflicting_exact_tag_hard_stops(self):
        runner = RecordingRunner([
            ("voice-stt-server:2.0.0", digest_response("sha256:" + "9" * 64)),
        ])
        with self.assertRaises(ConflictError):
            self._adapter(runner).verify(MANIFEST, make_state("PYPI_PUBLISHED"))


class GHCRPromotionTests(unittest.TestCase):
    def _adapter(self, runner):
        return GHCRAdapter(repo_root=GHCR_ROOT, dockerhub_root=DOCKERHUB_ROOT, runner=runner)

    def test_ghcr_promotes_from_docker_hub_by_digest(self):
        # W5R4-G23/G24: the same manifest, addressed by digest, not a rebuild.
        runner = RecordingRunner()
        self._adapter(runner).publish(MANIFEST, make_state("DOCKERHUB_PUBLISHED"))
        creates = [c for c in runner.commands if "imagetools create" in c]
        self.assertEqual(len(creates), 2)
        for command in creates:
            self.assertIn(f"{DOCKERHUB_ROOT}/voice-stt-server", command)
            self.assertIn("@sha256:", command)
            self.assertIn("--tag ghcr.io/marcosudau-vps/", command)

    def test_ghcr_never_promotes_from_staging(self):
        runner = RecordingRunner()
        self._adapter(runner).publish(MANIFEST, make_state("DOCKERHUB_PUBLISHED"))
        for command in runner.commands:
            if "imagetools create" in command:
                self.assertNotIn("-staging@", command)

    def test_the_promoted_digest_is_the_qualified_one(self):
        runner = RecordingRunner([
            ("ghcr.io/marcosudau-vps/voice-stt-server:2.0.0", digest_response(FREE_DIGEST)),
            ("ghcr.io/marcosudau-vps/voice-stt-server-pro:2.0.0", digest_response(PRO_DIGEST)),
        ])
        self.assertEqual(
            self._adapter(runner).verify(MANIFEST, make_state("DOCKERHUB_PUBLISHED")), MATCH
        )

    def test_without_a_docker_hub_root_promotion_is_unavailable(self):
        adapter = GHCRAdapter(repo_root=GHCR_ROOT, dockerhub_root="", runner=RecordingRunner())
        with self.assertRaises(VerificationUnavailableError):
            adapter.publish(MANIFEST, make_state("DOCKERHUB_PUBLISHED"))


class AliasAdapterTests(unittest.TestCase):
    ROOTS = {"dockerhub": DOCKERHUB_ROOT, "ghcr": GHCR_ROOT}

    def _adapter(self, runner):
        return AliasAdapter(registry_roots=self.ROOTS, runner=runner)

    def test_aliases_cover_both_registries_and_both_variants(self):
        # 2 registries x 2 variants x 3 aliases (2.0, 2, latest) = 12.
        runner = RecordingRunner()
        self._adapter(runner).publish(MANIFEST, make_state("EXTERNAL_VERIFIED"))
        creates = [c for c in runner.commands if "imagetools create" in c]
        self.assertEqual(len(creates), 12)
        for alias in ("2.0", ":2 ", "latest"):
            self.assertTrue(any(alias.strip() in c for c in creates), alias)

    def test_aliases_are_set_from_the_verified_digest(self):
        runner = RecordingRunner()
        self._adapter(runner).publish(MANIFEST, make_state("EXTERNAL_VERIFIED"))
        for command in runner.commands:
            if "imagetools create" in command:
                self.assertTrue(
                    FREE_DIGEST in command or PRO_DIGEST in command, command
                )

    def test_aliases_before_external_verification_are_refused(self):
        # W5R4-G38: latest must never point at an unverified release.
        with self.assertRaises(OrderError):
            self._adapter(RecordingRunner()).publish(MANIFEST, make_state("GHCR_PUBLISHED"))

    def test_an_alias_already_on_the_digest_is_not_rewritten(self):
        runner = RecordingRunner(default=digest_response(FREE_DIGEST))
        self._adapter(runner).publish(MANIFEST, make_state("EXTERNAL_VERIFIED"))
        creates = [c for c in runner.commands if "imagetools create" in c]
        # Only the Pro aliases still need moving; the Free ones already match.
        self.assertTrue(all("voice-stt-server-pro" in c for c in creates))

    def test_verify_requires_every_alias_to_be_correct(self):
        # W5R4-G39: alias digests are verified, not assumed.
        runner = RecordingRunner(default=digest_response(FREE_DIGEST))
        self.assertEqual(
            self._adapter(runner).verify(MANIFEST, make_state("EXTERNAL_VERIFIED")), ABSENT
        )

    def test_a_prerelease_owns_no_aliases_and_is_trivially_satisfied(self):
        prerelease = make_manifest(productVersion="2.0.0-rc.1")
        runner = RecordingRunner()
        adapter = self._adapter(runner)
        self.assertEqual(adapter.verify(prerelease, make_state("EXTERNAL_VERIFIED")), MATCH)
        adapter.publish(prerelease, make_state("EXTERNAL_VERIFIED"))
        self.assertEqual([c for c in runner.commands if "imagetools create" in c], [])

    def test_an_unconfigured_registry_is_unavailable(self):
        adapter = AliasAdapter(registry_roots={"dockerhub": "", "ghcr": GHCR_ROOT},
                               runner=RecordingRunner())
        with self.assertRaises(VerificationUnavailableError):
            adapter.verify(MANIFEST, make_state("EXTERNAL_VERIFIED"))


class GitTagAdapterTests(unittest.TestCase):
    def test_the_tag_name_is_v_prefixed(self):
        self.assertEqual(GitTagAdapter.tag_name(MANIFEST), "v2.0.0")

    def test_an_existing_tag_on_another_commit_is_a_hard_conflict(self):
        # W5R4-G30: never moved, never replaced.
        from unittest import mock

        adapter = GitTagAdapter(repo_root=Path("."))
        with mock.patch("release_tooling.gitinfo.local_tag_commit", return_value="0" * 40), \
             mock.patch("release_tooling.gitinfo.remote_tag_commit", return_value=None):
            with self.assertRaises(ConflictError):
                adapter.verify(MANIFEST, make_state("PREPARED"))

    def test_an_existing_tag_on_the_expected_commit_resumes(self):
        from unittest import mock

        adapter = GitTagAdapter(repo_root=Path("."))
        with mock.patch("release_tooling.gitinfo.local_tag_commit", return_value=MANIFEST["sourceCommit"]), \
             mock.patch("release_tooling.gitinfo.remote_tag_commit", return_value=MANIFEST["sourceCommit"]):
            self.assertEqual(adapter.verify(MANIFEST, make_state("PREPARED")), MATCH)

    def test_an_unreachable_remote_is_unavailable(self):
        from unittest import mock

        from release_tooling.gitinfo import GitError

        adapter = GitTagAdapter(repo_root=Path("."))
        with mock.patch("release_tooling.gitinfo.local_tag_commit", return_value=None), \
             mock.patch("release_tooling.gitinfo.remote_tag_commit", side_effect=GitError("offline")):
            with self.assertRaises(VerificationUnavailableError):
                adapter.verify(MANIFEST, make_state("PREPARED"))

    def test_tagging_after_a_public_artifact_exists_is_refused(self):
        adapter = GitTagAdapter(repo_root=Path("."))
        with self.assertRaises(OrderError):
            adapter.publish(MANIFEST, make_state("PYPI_PUBLISHED"))


class GitHubReleaseAdapterTests(unittest.TestCase):
    def test_a_missing_release_is_absent(self):
        runner = RecordingRunner(default=failed("release not found"))
        adapter = GitHubReleaseAdapter(runner=runner)
        self.assertEqual(adapter.verify(MANIFEST, make_state("ALIASES_PUBLISHED")), ABSENT)

    def test_an_existing_release_for_the_tag_matches(self):
        runner = RecordingRunner([("gh release view", ok('{"tagName": "v2.0.0"}'))])
        adapter = GitHubReleaseAdapter(runner=runner)
        self.assertEqual(adapter.verify(MANIFEST, make_state("ALIASES_PUBLISHED")), MATCH)

    def test_a_release_bound_to_another_tag_is_a_conflict(self):
        runner = RecordingRunner([("gh release view", ok('{"tagName": "v1.9.0"}'))])
        with self.assertRaises(ConflictError):
            GitHubReleaseAdapter(runner=runner).verify(MANIFEST, make_state("ALIASES_PUBLISHED"))

    def test_creating_the_release_before_aliases_is_refused(self):
        # W5R4-G31: the GitHub Release is the last public marker.
        adapter = GitHubReleaseAdapter(runner=RecordingRunner())
        with self.assertRaises(OrderError):
            adapter.publish(MANIFEST, make_state("EXTERNAL_VERIFIED"))

    def test_the_release_is_created_for_the_exact_tag(self):
        runner = RecordingRunner(default=ok(""))
        GitHubReleaseAdapter(runner=runner).publish(MANIFEST, make_state("ALIASES_PUBLISHED"))
        self.assertIn("gh release create v2.0.0", runner.commands[0])


class AggregateVerificationTests(unittest.TestCase):
    class Sub:
        def __init__(self, status=MATCH, raises=None):
            self.status, self.raises = status, raises

        def verify(self, manifest, state):
            if self.raises:
                raise self.raises
            return self.status

    def test_every_sub_adapter_must_match(self):
        adapter = AggregateVerificationAdapter(
            name="external_verification", sub_adapters=[self.Sub(), self.Sub(ABSENT)]
        )
        self.assertEqual(adapter.verify(MANIFEST, make_state("GHCR_PUBLISHED")), ABSENT)

    def test_all_matching_is_a_match(self):
        adapter = AggregateVerificationAdapter(
            name="external_verification", sub_adapters=[self.Sub(), self.Sub()]
        )
        self.assertEqual(adapter.verify(MANIFEST, make_state("GHCR_PUBLISHED")), MATCH)

    def test_a_sub_adapter_conflict_propagates(self):
        adapter = AggregateVerificationAdapter(
            name="external_verification",
            sub_adapters=[self.Sub(raises=ConflictError("boom"))],
        )
        with self.assertRaises(ConflictError):
            adapter.verify(MANIFEST, make_state("GHCR_PUBLISHED"))

    def test_it_has_no_publish_action_of_its_own(self):
        adapter = AggregateVerificationAdapter(name="final_verification", sub_adapters=[])
        with self.assertRaises(ReleaseError):
            adapter.publish(MANIFEST, make_state("GITHUB_RELEASED"))


class SecretHygieneTests(unittest.TestCase):
    def test_a_failing_command_never_echoes_a_secret_back(self):
        # W5R4-G49: an adapter's error text is redacted before it is raised.
        leaked = "dckr_pat_AAAABBBBCCCCDDDDEEEEFFFFGGGG"
        runner = RecordingRunner(default=failed(f"unauthorized using {leaked}"))
        adapter = DockerHubAdapter(repo_root=DOCKERHUB_ROOT, runner=runner)
        with self.assertRaises(Exception) as caught:
            adapter.verify(MANIFEST, make_state("PYPI_PUBLISHED"))
        self.assertNotIn(leaked, str(caught.exception))


if __name__ == "__main__":
    unittest.main()
