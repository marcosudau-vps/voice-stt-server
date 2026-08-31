"""AP-SRV-070 W4A - the Kroko model authority.

Before W4A anything that happened to sit behind ``VOICESTT_KROKO_MODEL_ROOT``
was treated as the product's model authority, nothing was integrity-checked,
and a missing model quietly became a Hugging Face download during server
start-up.

These tests pin the three boundaries that replaced it: a manifest that knows
each model's identity and integrity, a license boundary that keeps every Kroko
model out of the distributed artifact, and a deterministic runtime that never
downloads on its own.
"""

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from VoiceSTT.kroko import models as kroko_models

REPO_ROOT = Path(__file__).resolve().parents[2]


def entry(**overrides):
    """A synthetic manifest entry, so tests never need a 150 MB model."""
    values = {
        "id": "test-model",
        "filename": "Test-Model.data",
        "language": "de",
        "tier": "community",
        "requiresRuntimeVariant": "free",
        "licenseClass": "community-unresolved",
        "redistributionStatus": "POLICY_REQUIRED",
        "sha256": "",
        "bytes": 0,
        "provenance": {"kind": "test"},
    }
    values.update(overrides)
    return kroko_models._parse_entry(values)


class ManifestLoadingTests(unittest.TestCase):
    def setUp(self):
        self.manifest = kroko_models.load_manifest()

    def test_manifest_ships_with_the_package(self):
        self.assertTrue(kroko_models.default_manifest_path().is_file())
        self.assertEqual(self.manifest.schema_version, 1)
        self.assertGreaterEqual(self.manifest.manifest_revision, 1)

    def test_every_entry_declares_the_required_authority_fields(self):
        self.assertTrue(self.manifest.entries)
        for item in self.manifest.entries:
            with self.subTest(model=item.id):
                self.assertTrue(item.filename)
                self.assertIn(item.requires_runtime_variant, ("free", "pro"))
                self.assertIn(item.tier, ("community", "pro"))
                self.assertTrue(item.license_class)
                self.assertTrue(item.redistribution_status)
                self.assertEqual(len(item.sha256), 64)
                self.assertGreater(item.bytes, 0)
                self.assertTrue(item.provenance)

    def test_community_models_are_pinned_to_an_immutable_upstream_revision(self):
        upstream = self.manifest.upstream
        self.assertEqual(len(upstream["communityRevision"]), 40)
        community = [e for e in self.manifest.entries if e.tier == "community"]
        self.assertEqual(len(community), 4)
        for item in community:
            with self.subTest(model=item.id):
                self.assertEqual(item.provenance.get("kind"), "upstream-verified")
                self.assertEqual(
                    item.provenance.get("revision"), upstream["communityRevision"]
                )

    def test_lookup_by_id_and_by_filename(self):
        by_id = self.manifest.get("kroko-de-community-64-l")
        self.assertIsNotNone(by_id)
        by_name = self.manifest.get("Kroko-DE-Community-64-L-Streaming-001.data")
        self.assertEqual(by_id, by_name)
        by_path = self.manifest.get("/models/kroko/Kroko-DE-Community-64-L-Streaming-001.data")
        self.assertEqual(by_id, by_path)
        self.assertIsNone(self.manifest.get("no-such-model"))


class LicenseBoundaryTests(unittest.TestCase):
    """W4A-01/W4A-07 - nothing is redistributed without a clear grant."""

    def setUp(self):
        self.manifest = kroko_models.load_manifest()

    def test_no_model_is_currently_redistributable(self):
        self.assertEqual(self.manifest.redistributable_entries(), ())

    def test_community_models_are_policy_required_not_allowed(self):
        for item in self.manifest.entries:
            if item.tier == "community":
                with self.subTest(model=item.id):
                    self.assertEqual(
                        item.redistribution_status,
                        kroko_models.REDISTRIBUTION_POLICY_REQUIRED,
                    )
                    self.assertFalse(item.redistributable)

    def test_pro_models_are_prohibited(self):
        pro = [e for e in self.manifest.entries if e.tier == "pro"]
        self.assertTrue(pro)
        for item in pro:
            with self.subTest(model=item.id):
                self.assertEqual(
                    item.redistribution_status, kroko_models.REDISTRIBUTION_PROHIBITED
                )
                self.assertEqual(item.requires_runtime_variant, "pro")

    def test_license_policy_records_the_evidence_for_the_decision(self):
        policy = self.manifest.license_policy
        self.assertEqual(
            policy["communityRedistribution"], kroko_models.REDISTRIBUTION_POLICY_REQUIRED
        )
        evidence = policy["evidence"]
        # The upstream LICENSE the model card points at is empty, which is why
        # the CC-BY-SA claim in the README prose is not a sufficient grant.
        self.assertEqual(evidence["licenseFileBytes"], 0)
        self.assertEqual(evidence["cardLicenseField"], "other")
        self.assertTrue(evidence["conflict"])

    def test_no_kroko_model_file_is_bundled_in_the_package(self):
        asset_dir = REPO_ROOT / "VoiceSTT" / "assets" / "kroko"
        shipped = sorted(p.name for p in asset_dir.iterdir() if p.is_file())
        self.assertEqual(shipped, ["models.json"])

    def test_setup_ships_only_the_manifest_from_the_kroko_assets(self):
        setup_text = (REPO_ROOT / "setup.py").read_text(encoding="utf-8")
        self.assertIn("assets/kroko/models.json", setup_text)
        self.assertNotIn("assets/kroko/*.data", setup_text)


class IntegrityVerificationTests(unittest.TestCase):
    """W4A-09.15 - hash and size mismatches must be detected."""

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)

    def _model(self, content=b"model-bytes"):
        path = self.dir / "Test-Model.data"
        path.write_bytes(content)
        return path

    def test_matching_model_verifies(self):
        path = self._model()
        item = entry(sha256=kroko_models.sha256_of(path), bytes=path.stat().st_size)
        ok, problems = kroko_models.verify_model_file(item, path)
        self.assertTrue(ok, problems)

    def test_hash_mismatch_is_detected(self):
        path = self._model()
        item = entry(sha256="0" * 64, bytes=path.stat().st_size)
        ok, problems = kroko_models.verify_model_file(item, path)
        self.assertFalse(ok)
        self.assertTrue(any("sha256" in problem for problem in problems))

    def test_size_mismatch_is_detected(self):
        path = self._model()
        item = entry(sha256=kroko_models.sha256_of(path), bytes=999999)
        ok, problems = kroko_models.verify_model_file(item, path)
        self.assertFalse(ok)
        self.assertTrue(any("size" in problem for problem in problems))

    def test_missing_model_is_detected(self):
        item = entry(sha256="0" * 64, bytes=1)
        ok, problems = kroko_models.verify_model_file(item, self.dir / "absent.data")
        self.assertFalse(ok)
        self.assertTrue(any("not found" in problem for problem in problems))

    def test_hash_check_can_be_skipped_for_the_runtime_path(self):
        path = self._model()
        item = entry(sha256="0" * 64, bytes=path.stat().st_size)
        ok, _ = kroko_models.verify_model_file(item, path, verify_hash=False)
        self.assertTrue(ok)


class VariantCompatibilityTests(unittest.TestCase):
    """W4A-09.10 - a Pro model must never run on a free runtime."""

    def test_matching_variant_is_accepted(self):
        ok, problem = kroko_models.check_variant_compatibility(
            entry(requiresRuntimeVariant="free"), "free"
        )
        self.assertTrue(ok)
        self.assertIsNone(problem)

    def test_pro_model_on_free_runtime_is_refused(self):
        ok, problem = kroko_models.check_variant_compatibility(
            entry(id="pro-model", requiresRuntimeVariant="pro"), "free"
        )
        self.assertFalse(ok)
        self.assertIn("pro", problem)

    def test_free_model_on_pro_runtime_is_refused(self):
        ok, problem = kroko_models.check_variant_compatibility(
            entry(requiresRuntimeVariant="free"), "pro"
        )
        self.assertFalse(ok)

    def test_unknown_runtime_variant_is_not_assumed_compatible(self):
        ok, problem = kroko_models.check_variant_compatibility(
            entry(requiresRuntimeVariant="pro"), None
        )
        self.assertFalse(ok)
        self.assertIn("could not be determined", problem)


class DownloadPolicyTests(unittest.TestCase):
    """W4A-08/W4A-09.16 - production never downloads by itself."""

    def setUp(self):
        self._clean_env()

    def _clean_env(self):
        for name in (kroko_models.ALLOW_MODEL_DOWNLOAD_ENV,):
            if name in os.environ:
                backup = os.environ.pop(name)
                self.addCleanup(os.environ.__setitem__, name, backup)

    def test_download_is_disabled_by_default(self):
        self.assertFalse(kroko_models.model_download_allowed())

    def test_environment_opt_in_enables_download(self):
        with mock.patch.dict(
            os.environ, {kroko_models.ALLOW_MODEL_DOWNLOAD_ENV: "1"}, clear=False
        ):
            self.assertTrue(kroko_models.model_download_allowed())

    def test_explicit_engine_option_wins_over_the_environment(self):
        with mock.patch.dict(
            os.environ, {kroko_models.ALLOW_MODEL_DOWNLOAD_ENV: "1"}, clear=False
        ):
            self.assertFalse(
                kroko_models.model_download_allowed({"auto_download_model": False})
            )
        self.assertTrue(kroko_models.model_download_allowed({"auto_download_model": True}))

    def test_hash_verification_is_opt_in_on_the_runtime_path(self):
        self.assertFalse(kroko_models.hash_verification_enabled())
        with mock.patch.dict(
            os.environ, {kroko_models.VERIFY_MODEL_HASH_ENV: "1"}, clear=False
        ):
            self.assertTrue(kroko_models.hash_verification_enabled())


class LocateModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = kroko_models.load_manifest()

    def test_missing_model_is_reported_as_unprovisioned_without_network(self):
        report = kroko_models.locate_model(
            "kroko-de-community-64-l",
            manifest=self.manifest,
            options={"model_root": str(self.root)},
        )
        self.assertTrue(report["manifested"])
        self.assertIsNone(report["path"])
        self.assertFalse(report["verified"])
        self.assertIn("not provisioned", report["problems"][0])

    def test_provisioned_model_is_located_under_the_configured_root(self):
        item = self.manifest.get("kroko-de-community-64-l")
        target = self.root / item.filename
        target.write_bytes(b"placeholder")

        report = kroko_models.locate_model(
            "kroko-de-community-64-l",
            manifest=self.manifest,
            options={"model_root": str(self.root), "verify_model_hash": False},
        )
        self.assertEqual(Path(report["path"]), target.resolve())
        # Size still fails, because the placeholder is not the real model - the
        # authority does not accept a file just because the name matches.
        self.assertFalse(report["verified"])
        self.assertTrue(any("size" in p for p in report["problems"]))

    def test_unmanaged_operator_override_is_allowed_but_labelled(self):
        override = self.root / "Custom-Model.data"
        override.write_bytes(b"operator supplied")

        report = kroko_models.locate_model(str(override), manifest=self.manifest)
        self.assertFalse(report["manifested"])
        self.assertTrue(report.get("unmanaged"))
        self.assertEqual(Path(report["path"]), override.resolve())

    def test_provisioning_error_explains_what_to_do(self):
        item = self.manifest.get("kroko-de-community-64-l")
        error = kroko_models.provisioning_error(item, item.filename)
        message = str(error)
        self.assertIn(kroko_models.KROKO_MODEL_ROOT_ENV, message)
        self.assertIn(item.sha256, message)
        self.assertIn("will not download it automatically", message)


class LocalAvailabilityTests(unittest.TestCase):
    def test_availability_is_computed_not_stored_in_the_manifest(self):
        raw = json.loads(
            kroko_models.default_manifest_path().read_text(encoding="utf-8")
        )
        for item in raw["models"]:
            self.assertNotIn("available", item)
            self.assertNotIn("path", item)

    def test_inventory_reports_availability_per_model(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = kroko_models.load_manifest()
            present = manifest.entries[0]
            (root / present.filename).write_bytes(b"x")

            inventory = kroko_models.describe_local_availability(
                manifest, options={"model_root": str(root)}
            )

        self.assertFalse(inventory["downloadAllowed"])
        available = [m for m in inventory["models"] if m["available"]]
        self.assertEqual([m["id"] for m in available], [present.id])


if __name__ == "__main__":
    unittest.main()
