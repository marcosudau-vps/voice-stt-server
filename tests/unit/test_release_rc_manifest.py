"""The canonical RC manifest, schema v2 (AP-SRV-070 W5-R04).

Gate W5R4-G16: the manifest binds the exact source, package, Kroko and image
identities - now for **two** complete alternative distributions, each with its
own embedded native runtime.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from release_support import (  # noqa: E402
    COMMIT,
    FREE_WHEEL,
    FREE_WHEEL_WIN,
    PRO_WHEEL,
    PRO_WHEEL_WIN,
    TREE,
    make_manifest,
)

from release_tooling import rc_manifest  # noqa: E402
from release_tooling.errors import ManifestError, SecretDetectedError  # noqa: E402


class SchemaTests(unittest.TestCase):
    def test_a_complete_candidate_validates(self):
        rc_manifest.validate_rc_manifest(make_manifest())

    def test_the_schema_version_is_two(self):
        self.assertEqual(rc_manifest.SCHEMA_VERSION, 2)
        self.assertEqual(make_manifest()["schemaVersion"], 2)

    def test_both_distributions_are_bound(self):
        manifest = make_manifest()
        self.assertEqual(
            rc_manifest.distribution_names(manifest),
            {"free": "voice-stt-server", "pro": "voice-stt-server-pro"},
        )

    def test_each_distribution_binds_its_kroko_variant_and_artifact(self):
        # The identity chain Kroko artifact -> distribution wheel -> PyPI.
        manifest = make_manifest()
        for variant in ("free", "pro"):
            block = manifest["distributions"][variant]
            self.assertEqual(block["krokoVariant"], variant)
            self.assertRegex(block["krokoArtifactSha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(block["krokoFingerprint"])

    def test_each_wheel_declares_its_interpreter_and_platform(self):
        # B2: CPython 3.12 on Linux x86_64 and Windows AMD64.
        for variant, expected in (("free", FREE_WHEEL), ("pro", PRO_WHEEL)):
            wheel = make_manifest()["distributions"][variant]["wheels"][0]
            self.assertEqual(wheel["filename"], expected)
            self.assertEqual(wheel["pythonTag"], "cp312")
            self.assertEqual(wheel["platformTag"], "linux_x86_64")
        for variant, expected in (("free", FREE_WHEEL_WIN), ("pro", PRO_WHEEL_WIN)):
            wheel = make_manifest()["distributions"][variant]["wheels"][1]
            self.assertEqual(wheel["filename"], expected)
            self.assertEqual(wheel["pythonTag"], "cp312")
            self.assertEqual(wheel["platformTag"], "win_amd64")

    def test_no_sdist_is_part_of_the_contract(self):
        # Section 9: an sdist cannot carry a native runtime, so publishing one
        # would break the "no local build" guarantee.
        self.assertNotIn("sdist", make_manifest())

    def test_images_bind_an_oci_manifest_digest_and_a_staging_reference(self):
        manifest = make_manifest()
        for variant in ("free", "pro"):
            self.assertRegex(
                rc_manifest.expected_image_digest(manifest, variant), r"^sha256:[0-9a-f]{64}$"
            )
            self.assertIn("@sha256:", rc_manifest.staging_reference(manifest, variant))


class ValidationFailureTests(unittest.TestCase):
    def _invalid(self, mutate):
        manifest = make_manifest()
        mutate(manifest)
        with self.assertRaises(ManifestError) as caught:
            rc_manifest.validate_rc_manifest(manifest)
        return str(caught.exception)

    def test_a_wrong_schema_version_is_rejected(self):
        self.assertIn("schemaVersion", self._invalid(lambda m: m.update(schemaVersion=1)))

    def test_a_non_hex_source_commit_is_rejected(self):
        self.assertIn("sourceCommit", self._invalid(lambda m: m.update(sourceCommit="nope")))

    def test_a_non_hex_source_tree_is_rejected(self):
        self.assertIn("sourceTree", self._invalid(lambda m: m.update(sourceTree="nope")))

    def test_a_missing_distribution_is_rejected(self):
        self.assertIn("distributions.pro", self._invalid(lambda m: m["distributions"].pop("pro")))

    def test_a_distribution_with_the_wrong_variant_is_rejected(self):
        def mutate(m):
            m["distributions"]["pro"]["krokoVariant"] = "free"

        self.assertIn("krokoVariant", self._invalid(mutate))

    def test_the_two_distributions_may_not_share_a_name(self):
        def mutate(m):
            m["distributions"]["pro"]["name"] = "voice-stt-server"

        self.assertIn("different PyPI names", self._invalid(mutate))

    def test_a_distribution_without_wheels_is_rejected(self):
        def mutate(m):
            m["distributions"]["free"]["wheels"] = []

        self.assertIn("non-empty list", self._invalid(mutate))

    def test_a_short_sha256_is_rejected(self):
        def mutate(m):
            m["distributions"]["free"]["wheels"][0]["sha256"] = "abc"

        self.assertIn("sha256", self._invalid(mutate))

    def test_missing_platform_tag_is_rejected(self):
        def mutate(m):
            m["distributions"]["free"]["wheels"][0].pop("platformTag")

        self.assertIn("platformTag", self._invalid(mutate))

    def test_missing_a_required_platform_wheel_is_rejected(self):
        def mutate(m):
            # Drop the Windows wheel
            m["distributions"]["free"]["wheels"] = [m["distributions"]["free"]["wheels"][0]]

        self.assertIn("must include a wheel for platform", self._invalid(mutate))

    def test_duplicate_platform_wheel_is_rejected(self):
        def mutate(m):
            m["distributions"]["free"]["wheels"].append(
                dict(m["distributions"]["free"]["wheels"][0], filename="voice_stt_server-2.0.0-cp312-cp312-linux_x86_64_2.whl")
            )

        self.assertIn("duplicate platform tags", self._invalid(mutate))

    def test_unsupported_platform_tag_is_rejected(self):
        def mutate(m):
            m["distributions"]["free"]["wheels"][0]["platformTag"] = "macosx_10_9_x86_64"

        self.assertIn("platformTag must be one of", self._invalid(mutate))

    def test_an_image_without_a_digest_is_rejected(self):
        def mutate(m):
            m["images"]["free"].pop("digest")

        self.assertIn("digest", self._invalid(mutate))

    def test_an_image_id_is_not_accepted_as_a_digest(self):
        # The v1 mistake: a local image Id is not a registry-checkable identity.
        def mutate(m):
            m["images"]["free"]["digest"] = "abc123"

        self.assertIn("OCI manifest digest", self._invalid(mutate))

    def test_a_staging_reference_must_be_digest_pinned(self):
        # A tag-pinned staging reference could silently move under the release.
        def mutate(m):
            m["images"]["free"]["staging"] = "ghcr.io/x/voice-stt-server-staging:latest"

        self.assertIn("digest-pinned", self._invalid(mutate))

    def test_the_two_images_may_not_share_a_digest(self):
        def mutate(m):
            m["images"]["pro"]["digest"] = m["images"]["free"]["digest"]

        self.assertIn("share one manifest digest", self._invalid(mutate))

    def test_an_invalid_candidate_id_is_rejected(self):
        self.assertIn("candidateId", self._invalid(lambda m: m.update(candidateId="!!")))

    def test_a_github_run_candidate_id_is_accepted(self):
        rc_manifest.validate_rc_manifest(make_manifest(candidateId="gh-987654321-2"))

    def test_a_manual_candidate_id_is_still_accepted(self):
        rc_manifest.validate_rc_manifest(make_manifest(candidateId="W5-RC1"))

    def test_an_invalid_readiness_is_rejected(self):
        self.assertIn("releaseReadiness", self._invalid(lambda m: m.update(releaseReadiness="MAYBE")))

    def test_several_problems_are_reported_at_once(self):
        message = self._invalid(lambda m: m.update(sourceCommit="x", sourceTree="y", candidateId="!"))
        self.assertIn("sourceCommit", message)
        self.assertIn("sourceTree", message)
        self.assertIn("candidateId", message)

    def test_a_secret_shaped_field_is_refused(self):
        manifest = make_manifest()
        manifest["qualification"]["token"] = "pypi-AgEIcHlwaS5vcmcsecretsecret"
        with self.assertRaises(SecretDetectedError):
            rc_manifest.validate_rc_manifest(manifest)


class IdentityHelperTests(unittest.TestCase):
    def test_state_identity_contains_both_distributions_and_images(self):
        identity = rc_manifest.state_identity(make_manifest())
        self.assertEqual(sorted(identity["distributions"]), ["free", "pro"])
        self.assertEqual(sorted(identity["images"]), ["free", "pro"])

    def test_state_identity_is_order_stable(self):
        manifest = make_manifest()
        shuffled = make_manifest()
        shuffled["distributions"]["free"]["wheels"] = list(
            reversed(shuffled["distributions"]["free"]["wheels"])
        )
        self.assertEqual(
            rc_manifest.state_identity(manifest), rc_manifest.state_identity(shuffled)
        )

    def test_candidate_identity_binds_candidate_id_and_manifest_hash(self):
        identity = rc_manifest.candidate_identity(make_manifest())
        self.assertEqual(identity["candidateId"], "gh-12345-1")
        self.assertEqual(identity["runId"], "12345")
        self.assertRegex(identity["manifestSha256"], r"^[0-9a-f]{64}$")

    def test_two_different_candidates_never_share_a_manifest_hash(self):
        # W5R4-G18: ambiguity between candidate runs must fail closed.
        first = rc_manifest.candidate_identity(make_manifest())
        second = rc_manifest.candidate_identity(make_manifest(candidateId="gh-99999-1"))
        self.assertNotEqual(first["manifestSha256"], second["manifestSha256"])

    def test_expected_pypi_files_are_per_distribution(self):
        manifest = make_manifest()
        self.assertEqual(
            sorted(rc_manifest.expected_pypi_files(manifest, "free")),
            sorted([FREE_WHEEL, FREE_WHEEL_WIN]),
        )
        self.assertEqual(
            sorted(rc_manifest.expected_pypi_files(manifest, "pro")),
            sorted([PRO_WHEEL, PRO_WHEEL_WIN]),
        )


class QualifyManifestTests(unittest.TestCase):
    def test_qualify_manifest_sets_qualified_readiness_and_evidence(self):
        manifest = make_manifest(release_readiness=rc_manifest.READINESS_NOT_QUALIFIED)
        self.assertEqual(manifest["releaseReadiness"], rc_manifest.READINESS_NOT_QUALIFIED)
        qualified = rc_manifest.qualify_manifest(
            manifest,
            evidence_ref="https://github.com/marcosudau-vps/voice-stt-server/actions/runs/123",
            context="smoke tests passed",
        )
        self.assertEqual(qualified["releaseReadiness"], rc_manifest.READINESS_QUALIFIED)
        self.assertEqual(
            qualified["qualification"]["evidenceRef"],
            "https://github.com/marcosudau-vps/voice-stt-server/actions/runs/123",
        )
        self.assertEqual(qualified["qualification"]["context"], "smoke tests passed")
        rc_manifest.validate_rc_manifest(qualified)

    def test_qualify_manifest_requires_non_empty_evidence_ref(self):
        manifest = make_manifest()
        with self.assertRaises(ManifestError):
            rc_manifest.qualify_manifest(manifest, evidence_ref="")


class PersistenceTests(unittest.TestCase):
    def test_write_then_load_round_trips(self):
        manifest = make_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rc-manifest.json"
            rc_manifest.write_rc_manifest(path, manifest)
            self.assertEqual(rc_manifest.load_rc_manifest(path), manifest)

    def test_writing_an_invalid_manifest_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rc-manifest.json"
            with self.assertRaises(ManifestError):
                rc_manifest.write_rc_manifest(path, make_manifest(sourceCommit="x"))
            self.assertFalse(path.exists())

    def test_loading_a_missing_manifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ManifestError):
                rc_manifest.load_rc_manifest(Path(tmp) / "absent.json")

    def test_the_manifest_hash_is_stable_across_a_round_trip(self):
        manifest = make_manifest()
        expected = rc_manifest.manifest_sha256(manifest)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rc-manifest.json"
            rc_manifest.write_rc_manifest(path, manifest)
            self.assertEqual(
                rc_manifest.manifest_sha256(rc_manifest.load_rc_manifest(path)), expected
            )

    def test_the_manifest_carries_no_operator_local_path(self):
        # W5R4-G07: release authority never depends on one machine.
        serialized = json.dumps(make_manifest())
        self.assertNotIn("P:\\", serialized)
        self.assertNotIn("P:/", serialized)


if __name__ == "__main__":
    unittest.main()
