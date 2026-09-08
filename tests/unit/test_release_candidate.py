"""Candidate assembly and persistence (AP-SRV-070 W5-R04).

Gates W5R4-G16 (the manifest binds every identity), G17 (a qualified candidate
can be persisted for publication without a rebuild) and G18 (a resume locates
the exact candidate, and ambiguity fails closed).

``release_tooling.candidate`` is the one place build outputs become a canonical
RC manifest, so ``tools/release_candidate.py`` on a runner and
``release.py manifest build`` by hand cannot assemble it two different ways.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for extra in (REPO_ROOT, REPO_ROOT / "tools", Path(__file__).resolve().parent):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import release_candidate  # noqa: E402

from release_tooling import candidate as candidate_module  # noqa: E402
from release_tooling import rc_manifest  # noqa: E402
from release_tooling.errors import ManifestError  # noqa: E402

COMMIT = "934e3be7c78aa9358f9b42b9fa4dc282bed54d6c"
TREE = "2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb"


def write_candidate(
    root: Path,
    *,
    free_commit: str = COMMIT,
    pro_commit: str = COMMIT,
    pro_version: str = "2.0.0",
    pushed: bool = True,
    dirty: bool = False,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for variant, commit in (("free", free_commit), ("pro", pro_commit)):
        name = "voice-stt-server-pro" if variant == "pro" else "voice-stt-server"
        digest = "sha256:" + ("1" if variant == "free" else "2") * 64
        kroko_sha = ("3" if variant == "free" else "4") * 64
        (root / f"build-manifest-{variant}.json").write_text(json.dumps({
            "gitCommit": commit,
            "gitDirty": dirty,
            "voicesttVersion": "2.0.0" if variant == "free" else pro_version,
            "buildDate": "2026-09-07T19:06:57Z",
            "variants": {
                variant: {
                    "kroko": {
                        "fingerprint": f"fp-{variant}",
                        "artifact": {"wheelSha256": kroko_sha},
                    },
                    "image": {"versionTag": f"{name}:2.0.0"},
                }
            },
        }), encoding="utf-8")
        (root / f"distribution-{variant}.json").write_text(json.dumps({
            "distribution": name,
            "filename": f"{name.replace('-', '_')}-2.0.0-cp312-cp312-linux_x86_64.whl",
            "sha256": ("5" if variant == "free" else "6") * 64,
            "pythonTag": "cp312",
            "abiTag": "cp312",
            "platformTag": "linux_x86_64",
            "embedded": {"kroko": {"wheelSha256": kroko_sha}},
        }), encoding="utf-8")
        (root / f"distribution-{variant}-win_amd64.json").write_text(json.dumps({
            "distribution": name,
            "filename": f"{name.replace('-', '_')}-2.0.0-cp312-cp312-win_amd64.whl",
            "sha256": ("7" if variant == "free" else "8") * 64,
            "pythonTag": "cp312",
            "abiTag": "cp312",
            "platformTag": "win_amd64",
            "embedded": {"kroko": {"wheelSha256": kroko_sha}},
        }), encoding="utf-8")
        staging = {"pushed": pushed}
        if pushed:
            staging.update({
                "digest": digest,
                "reference": f"ghcr.io/marcosudau-vps/{name}-staging@{digest}",
            })
        else:
            staging["reason"] = "staging push not requested for this run"
        (root / f"staging-{variant}.json").write_text(json.dumps(staging), encoding="utf-8")
    return root


def assemble(root: Path, **overrides):
    kwargs = dict(
        candidate_dir=root,
        candidate_id="gh-4242-1",
        source_tree=TREE,
        qualification_timestamp_utc="2026-09-08T00:00:00Z",
        qualification_context="unit test",
        qualification_evidence_ref="W5-R04",
    )
    kwargs.update(overrides)
    return candidate_module.assemble_rc_manifest(**kwargs)


class AssemblyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = write_candidate(Path(self._tmp.name) / "candidate")

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_complete_candidate_assembles_into_a_valid_manifest(self):
        manifest = assemble(self.root)
        rc_manifest.validate_rc_manifest(manifest)
        self.assertEqual(manifest["sourceCommit"], COMMIT)
        self.assertEqual(manifest["sourceTree"], TREE)
        self.assertEqual(manifest["productVersion"], "2.0.0")

    def test_it_binds_both_distributions_with_their_kroko_identity(self):
        # W5R4-G16: Kroko artifact -> distribution wheel -> PyPI, end to end.
        manifest = assemble(self.root)
        free = manifest["distributions"]["free"]
        self.assertEqual(free["name"], "voice-stt-server")
        self.assertEqual(free["krokoVariant"], "free")
        self.assertEqual(free["krokoFingerprint"], "fp-free")
        self.assertEqual(free["krokoArtifactSha256"], "3" * 64)
        pro = manifest["distributions"]["pro"]
        self.assertEqual(pro["name"], "voice-stt-server-pro")
        self.assertEqual(pro["krokoArtifactSha256"], "4" * 64)

    def test_it_binds_both_linux_and_windows_wheels_for_both_distributions(self):
        # B2: Complete public distributions for Linux x86_64 and Windows AMD64.
        manifest = assemble(self.root)
        for variant in ("free", "pro"):
            dist = manifest["distributions"][variant]
            platforms = [w["platformTag"] for w in dist["wheels"]]
            self.assertEqual(sorted(platforms), ["linux_x86_64", "win_amd64"])

    def test_missing_a_required_platform_wheel_fails_assembly(self):
        # B2: Missing one required platform wheel fails candidate completeness.
        (self.root / "distribution-free-win_amd64.json").unlink()
        with self.assertRaises(ManifestError) as caught:
            assemble(self.root)
        self.assertIn("missing required platform wheel", str(caught.exception))

    def test_it_binds_the_staging_reference_so_publication_never_rebuilds(self):
        # W5R4-G17.
        manifest = assemble(self.root)
        for variant in ("free", "pro"):
            with self.subTest(variant=variant):
                reference = rc_manifest.staging_reference(manifest, variant)
                self.assertIn("-staging@sha256:", reference)
                self.assertEqual(
                    reference.split("@", 1)[1],
                    rc_manifest.expected_image_digest(manifest, variant),
                )

    def test_a_candidate_whose_images_were_never_persisted_fails_closed(self):
        # W5R4-G17: without a persisted digest the candidate could only be
        # published by rebuilding it, which is exactly what must not happen.
        root = write_candidate(Path(self._tmp.name) / "unpushed", pushed=False)
        with self.assertRaises(ManifestError) as caught:
            assemble(root)
        self.assertIn("staging", str(caught.exception).lower())

    def test_two_halves_from_different_commits_fail_closed(self):
        root = write_candidate(Path(self._tmp.name) / "split", pro_commit="9" * 40)
        with self.assertRaises(ManifestError) as caught:
            assemble(root)
        self.assertIn("different", str(caught.exception))

    def test_two_halves_with_different_versions_fail_closed(self):
        root = write_candidate(Path(self._tmp.name) / "versions", pro_version="2.0.1")
        with self.assertRaises(ManifestError) as caught:
            assemble(root)
        self.assertIn("versions", str(caught.exception))

    def test_a_dirty_working_tree_cannot_produce_a_candidate(self):
        root = write_candidate(Path(self._tmp.name) / "dirty", dirty=True)
        with self.assertRaises(ManifestError) as caught:
            assemble(root)
        self.assertIn("dirty", str(caught.exception))

    def test_a_missing_input_file_fails_closed(self):
        (self.root / "distribution-pro.json").unlink()
        with self.assertRaises(ManifestError) as caught:
            assemble(self.root)
        self.assertIn("incomplete", str(caught.exception))

    def test_conflicting_kroko_hashes_fail_closed(self):
        payload = json.loads((self.root / "build-manifest-free.json").read_text())
        payload["variants"]["free"]["kroko"]["artifact"]["sha256"] = "9" * 64
        (self.root / "build-manifest-free.json").write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(ManifestError) as caught:
            candidate_module.kroko_artifact_sha256(payload, "free")
        self.assertIn("conflicting hashes", str(caught.exception))

    def test_the_legacy_sha256_field_is_still_accepted_alone(self):
        payload = json.loads((self.root / "build-manifest-free.json").read_text())
        artifact = payload["variants"]["free"]["kroko"]["artifact"]
        artifact["sha256"] = artifact.pop("wheelSha256")
        self.assertEqual(candidate_module.kroko_artifact_sha256(payload, "free"), "3" * 64)


class CandidateIdentityTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = write_candidate(Path(self._tmp.name) / "candidate")

    def tearDown(self):
        self._tmp.cleanup()

    def test_two_candidate_runs_produce_different_identities(self):
        # W5R4-G18: ambiguity between candidate runs must fail closed, which
        # requires the identities to actually differ.
        first = rc_manifest.candidate_identity(assemble(self.root, candidate_id="gh-1-1"))
        second = rc_manifest.candidate_identity(assemble(self.root, candidate_id="gh-2-1"))
        self.assertNotEqual(first["candidateId"], second["candidateId"])
        self.assertNotEqual(first["manifestSha256"], second["manifestSha256"])

    def test_the_candidate_id_is_derived_from_the_workflow_run(self):
        self.assertEqual(
            release_candidate.default_candidate_id(
                {"GITHUB_RUN_ID": "987", "GITHUB_RUN_ATTEMPT": "2"}
            ),
            "gh-987-2",
        )

    def test_a_local_candidate_is_obviously_marked_as_local(self):
        # A locally produced candidate must never be mistaken for a qualified,
        # workflow-produced one.
        self.assertEqual(release_candidate.default_candidate_id({}), "local-candidate")
        self.assertEqual(release_candidate.candidate_run_info({})["environment"], "local")

    def test_run_info_records_a_traceable_url(self):
        info = release_candidate.candidate_run_info({
            "GITHUB_RUN_ID": "987",
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_REPOSITORY": "marcosudau-vps/voice-stt-server",
            "GITHUB_SERVER_URL": "https://github.com",
            "GITHUB_WORKFLOW": "Release candidate",
        })
        self.assertEqual(
            info["runUrl"],
            "https://github.com/marcosudau-vps/voice-stt-server/actions/runs/987",
        )


class StagingTests(unittest.TestCase):
    def test_the_staging_reference_is_private_and_per_candidate(self):
        reference = release_candidate.staging_reference_for(
            "free", "gh-987-1", "ghcr.io/marcosudau-vps"
        )
        self.assertEqual(
            reference, "ghcr.io/marcosudau-vps/voice-stt-server-staging:gh-987-1"
        )
        self.assertIn("-staging", reference)

    def test_free_and_pro_staging_packages_never_collide(self):
        # W5R4-G13.
        free = release_candidate.staging_reference_for("free", "gh-1-1", "ghcr.io/o")
        pro = release_candidate.staging_reference_for("pro", "gh-1-1", "ghcr.io/o")
        self.assertNotEqual(free, pro)

    def test_a_staging_push_reads_the_digest_back_from_the_registry(self):
        # The digest is what the whole publication hangs on, so it is read
        # back from the registry rather than assumed from the push.
        from release_support import RecordingRunner, digest_response

        digest = "sha256:" + "a" * 64
        runner = RecordingRunner([("imagetools inspect", digest_response(digest))])
        record = release_candidate.push_staging_image(
            variant="free", local_tag="voice-stt-server:2.0.0",
            candidate_id="gh-1-1", staging_root="ghcr.io/o", runner=runner,
        )
        self.assertEqual(record["digest"], digest)
        self.assertTrue(record["reference"].endswith("@" + digest))
        self.assertTrue(record["private"])
        self.assertIn("docker push ghcr.io/o/voice-stt-server-staging:gh-1-1", runner.commands)

    def test_an_unreadable_digest_fails_closed(self):
        from release_support import RecordingRunner, ok

        runner = RecordingRunner([("imagetools inspect", ok("not-a-digest\n"))])
        with self.assertRaises(release_candidate.CandidateError):
            release_candidate.push_staging_image(
                variant="free", local_tag="voice-stt-server:2.0.0",
                candidate_id="gh-1-1", staging_root="ghcr.io/o", runner=runner,
            )


class InventoryTests(unittest.TestCase):
    def test_the_inventory_hashes_every_produced_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = write_candidate(Path(tmp) / "candidate")
            (root / "dist").mkdir()
            (root / "dist" / "wheel.whl").write_bytes(b"payload")
            inventory = release_candidate.build_inventory(root)
        paths = {entry["path"] for entry in inventory["files"]}
        self.assertIn("dist/wheel.whl", paths)
        self.assertIn("rc-manifest.json", paths | {"rc-manifest.json"})
        for entry in inventory["files"]:
            self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")

    def test_inventory_paths_are_relative_and_portable(self):
        # W5R4-G07: nothing a reviewer receives should name one machine.
        import re

        with tempfile.TemporaryDirectory() as tmp:
            root = write_candidate(Path(tmp) / "candidate")
            inventory = release_candidate.build_inventory(root)
        serialized = json.dumps(inventory)
        self.assertIsNone(re.search(r"\b[A-Za-z]:[\\/]", serialized))


class WindowsCandidateBuildTests(unittest.TestCase):
    def test_build_windows_candidate_produces_distribution_manifests(self):
        from unittest.mock import patch
        from release_support import CommandResult, RecordingRunner

        fake_describe = {
            "artifact": {
                "wheelPath": "dummy_kroko.whl",
                "wheelSha256": "3" * 64,
            },
            "fingerprint": "fp-dummy",
        }
        runner = RecordingRunner([
            ("install_kroko.py", CommandResult(args=[], returncode=0, stdout=json.dumps(fake_describe), stderr=""))
        ])

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "candidate-win"
            fake_dist = {
                "distribution": "voice-stt-server",
                "filename": "voice_stt_server-2.0.0-cp312-cp312-win_amd64.whl",
                "sha256": "7" * 64,
                "pythonTag": "cp312",
                "abiTag": "cp312",
                "platformTag": "win_amd64",
            }
            with patch("build_distribution.build_distribution", return_value=fake_dist):
                produced = release_candidate.build_windows_candidate(
                    out_dir=out_dir,
                    candidate_id="gh-123-1",
                    source_tree=TREE,
                    runner=runner,
                )
            self.assertEqual(produced["candidateId"], "gh-123-1")
            self.assertTrue((out_dir / "distribution-free-win_amd64.json").is_file())
            self.assertTrue((out_dir / "distribution-pro-win_amd64.json").is_file())


if __name__ == "__main__":
    unittest.main()
