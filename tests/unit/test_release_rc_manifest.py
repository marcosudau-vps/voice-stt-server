"""AP-SRV-070 W5: the canonical RC manifest format."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from release_tooling.errors import ManifestError, SecretDetectedError
from release_tooling.rc_manifest import (
    READINESS_NOT_QUALIFIED,
    build_rc_manifest,
    load_rc_manifest,
    validate_rc_manifest,
    write_rc_manifest,
)


def _sample_kwargs(**overrides) -> dict:
    kwargs = dict(
        candidate_id="W5-RC1",
        product_version="2.0.0",
        source_commit="a" * 40,
        source_tree="b" * 40,
        wheel_path=Path("voicestt-2.0.0-py3-none-any.whl"),
        wheel_sha256="c" * 64,
        sdist_path=Path("voicestt-2.0.0.tar.gz"),
        sdist_sha256="d" * 64,
        kroko_free_fingerprint="freefingerprint123",
        kroko_free_artifact_sha256="e" * 64,
        kroko_pro_fingerprint="profingerprint456",
        kroko_pro_artifact_sha256="f" * 64,
        free_image_tag="voice-stt-server:2.0.0",
        free_image_id="sha256:" + "1" * 64,
        pro_image_tag="voice-stt-server-pro:2.0.0",
        pro_image_id="sha256:" + "2" * 64,
        oci_version="2.0.0",
        oci_revision="a" * 40,
        qualification_timestamp_utc="2026-09-06T12:00:00Z",
        qualification_context="W5-R02 qualification run",
        qualification_evidence_ref="_workflow-tools/AP-SRV-070/Runs/W5-R02/03_GATE_INDEX.md",
    )
    kwargs.update(overrides)
    return kwargs


class BuildAndValidateTests(unittest.TestCase):
    def test_build_rc_manifest_produces_a_valid_document(self):
        manifest = build_rc_manifest(**_sample_kwargs())
        validate_rc_manifest(manifest)  # must not raise
        self.assertEqual(manifest["candidateId"], "W5-RC1")
        self.assertEqual(manifest["releaseReadiness"], READINESS_NOT_QUALIFIED)

    def test_validate_rejects_a_bad_candidate_id(self):
        manifest = build_rc_manifest(**_sample_kwargs())
        manifest["candidateId"] = "not-a-candidate-id"
        with self.assertRaises(ManifestError):
            validate_rc_manifest(manifest)

    def test_validate_rejects_a_non_hex_source_commit(self):
        manifest = build_rc_manifest(**_sample_kwargs())
        manifest["sourceCommit"] = "not-a-commit"
        with self.assertRaises(ManifestError):
            validate_rc_manifest(manifest)

    def test_validate_rejects_a_short_sha256(self):
        manifest = build_rc_manifest(**_sample_kwargs())
        manifest["wheel"]["sha256"] = "tooshort"
        with self.assertRaises(ManifestError):
            validate_rc_manifest(manifest)

    def test_validate_rejects_missing_kroko_block(self):
        manifest = build_rc_manifest(**_sample_kwargs())
        del manifest["kroko"]["pro"]
        with self.assertRaises(ManifestError):
            validate_rc_manifest(manifest)

    def test_validate_rejects_an_invalid_release_readiness(self):
        manifest = build_rc_manifest(**_sample_kwargs())
        manifest["releaseReadiness"] = "MAYBE"
        with self.assertRaises(ManifestError):
            validate_rc_manifest(manifest)

    def test_validate_rejects_a_secret_shaped_field(self):
        manifest = build_rc_manifest(**_sample_kwargs())
        manifest["krokoApiKey"] = "sk-AAAAAAAAAAAAAAAAAAAAAAAA"
        with self.assertRaises(SecretDetectedError):
            validate_rc_manifest(manifest)

    def test_validate_reports_multiple_problems_at_once(self):
        manifest = build_rc_manifest(**_sample_kwargs())
        manifest["candidateId"] = "bad"
        manifest["sourceCommit"] = "bad"
        with self.assertRaises(ManifestError) as ctx:
            validate_rc_manifest(manifest)
        message = str(ctx.exception)
        self.assertIn("candidateId", message)
        self.assertIn("sourceCommit", message)


class PersistenceTests(unittest.TestCase):
    def test_write_then_load_round_trips(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            manifest = build_rc_manifest(**_sample_kwargs())
            write_rc_manifest(path, manifest)
            reloaded = load_rc_manifest(path)
            self.assertEqual(reloaded, manifest)

    def test_load_rejects_a_missing_file(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ManifestError):
                load_rc_manifest(Path(tmp) / "missing.json")

    def test_load_rejects_invalid_json(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ManifestError):
                load_rc_manifest(path)

    def test_write_refuses_to_write_an_invalid_manifest(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            manifest = build_rc_manifest(**_sample_kwargs())
            manifest["releaseReadiness"] = "MAYBE"
            with self.assertRaises(ManifestError):
                write_rc_manifest(path, manifest)
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
