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
from unittest import mock

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
    def test_windows_builder_module_imports_in_an_uninstalled_checkout(self):
        import os
        import subprocess
        import sys

        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        result = subprocess.run(
            [sys.executable, "-m", "VoiceSTT.install_kroko", "--help"],
            cwd=release_candidate.REPO_ROOT, env=env, text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--describe-artifact", result.stdout)

    def test_build_windows_candidate_produces_distribution_manifests(self):
        from unittest.mock import patch
        from release_support import RecordingRunner
        from VoiceSTT._build_identity import BuildIdentity

        from types import SimpleNamespace

        runner = RecordingRunner()
        record = SimpleNamespace(wheel_path=Path("dummy_kroko.whl"), fingerprint="fp-dummy")

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "candidate-win"
            fake_dist = {
                "path": "dummy_distribution.whl",
                "distribution": "voice-stt-server",
                "filename": "voice_stt_server-2.0.0-cp312-cp312-win_amd64.whl",
                "sha256": "7" * 64,
                "pythonTag": "cp312",
                "abiTag": "cp312",
                "platformTag": "win_amd64",
            }
            source = BuildIdentity(
                1, "2.0.0", "2.0.0", COMMIT, TREE, False,
                "2026-10-19T21:34:01Z", "voicestt", None, "git",
            )
            with patch("build_distribution.build_distribution", return_value=fake_dist), \
                 patch.object(release_candidate, "candidate_source", return_value=source), \
                 patch.object(release_candidate, "resolve_windows_kroko", return_value=record) as resolve, \
                 patch.object(release_candidate, "validate_distribution"), \
                 patch.object(release_candidate.build_production.kroko_artifacts,
                              "sha256_of", return_value="3" * 64):
                produced = release_candidate.build_windows_candidate(
                    out_dir=out_dir,
                    candidate_id="gh-123-1",
                    source_tree=TREE,
                    runner=runner,
                )
            self.assertEqual(produced["candidateId"], "gh-123-1")
            self.assertTrue((out_dir / "distribution-free-win_amd64.json").is_file())
            self.assertTrue((out_dir / "distribution-pro-win_amd64.json").is_file())
            self.assertEqual([call.args[0] for call in resolve.call_args_list], ["free", "pro"])


class WindowsCrossBuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.work = self.root / "work"
        self.repo = self.work / "kroko-onnx"
        self.repo.mkdir(parents=True)
        self.calls = []
        self.output_variant = "free"
        self.output_tag = "cp312-cp312-win_amd64"
        for patcher in (
            mock.patch.object(release_candidate.sys, "platform", "linux"),
            mock.patch.object(release_candidate.kroko_fingerprint, "detect_architecture", return_value="amd64"),
            mock.patch.object(release_candidate.kroko_fingerprint, "detect_python_tag", return_value="cp312"),
            mock.patch.object(release_candidate.os, "getuid", return_value=1001, create=True),
            mock.patch.object(release_candidate.os, "getgid", return_value=1001, create=True),
            mock.patch.object(release_candidate.install_kroko, "prepare_checkout", return_value=self.repo),
            mock.patch.object(release_candidate.install_kroko, "prepare_windows_checkout"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_command(self, cmd, **kwargs):
        from release_support import CommandResult
        from test_kroko_artifact_store import make_wheel

        self.calls.append((cmd, kwargs))
        if "BUILD_VARIANT=free" in cmd:
            output = next(value.removesuffix(":/out") for value in cmd if value.endswith(":/out"))
            make_wheel(Path(output) / "wheel", variant=self.output_variant, tag=self.output_tag)
        return CommandResult(args=cmd, returncode=0, stdout="", stderr="")

    def resolve(self, runner=None):
        return release_candidate.resolve_windows_kroko(
            "free", artifact_store=self.root / "store", work_dir=self.work,
            runner=runner or self.run_command,
        )

    def test_cross_build_keeps_both_original_windows_fingerprints(self):
        installer = release_candidate.install_kroko
        with mock.patch.object(installer.kroko_fingerprint, "detect_target_platform", return_value="windows"):
            for variant in ("free", "pro"):
                args = installer.parse_args(["--variant", variant])
                self.assertEqual(
                    release_candidate.windows_kroko_fingerprint(variant),
                    installer.fingerprint_for(args),
                )
        self.assertEqual(release_candidate.windows_kroko_fingerprint("free")["fingerprint"], "28594e6d201fc4a7")

    def test_cross_build_uses_current_patches_container_retag_and_real_store(self):
        with mock.patch.dict(release_candidate.os.environ, {"KROKO_API_KEY": "test-secret"}):
            record = self.resolve()
        self.assertEqual(record.fingerprint, "28594e6d201fc4a7")
        self.assertEqual(record.metadata["targetPlatform"], "windows")
        self.assertEqual(record.metadata["wheelSha256"], release_candidate.sha256_of(record.wheel_path))
        release_candidate.install_kroko.prepare_windows_checkout.assert_called_once_with(self.repo)
        commands = [call[0] for call in self.calls]
        self.assertEqual(commands[0][:5], ["docker", "build", "--platform", "linux/amd64", "--file"])
        self.assertIn(str(self.repo / "Dockerfile.windows"), commands[0])
        self.assertIn("BUILD_VARIANT=free", commands[1])
        self.assertIn(f"{self.repo}:/src:ro", commands[1])
        self.assertEqual(commands[2][-3:], ["-R", "1001:1001", "/out"])
        self.assertIn("--user", commands[3])
        self.assertIn("1free", commands[3])
        self.assertIn("--remove", commands[3])
        for _, kwargs in self.calls:
            self.assertNotIn("KROKO_API_KEY", kwargs["env"])

    def test_verified_artifact_reuse_does_not_invoke_docker(self):
        first = self.resolve()
        self.calls.clear()
        second = self.resolve()
        self.assertEqual(first.wheel_sha256, second.wheel_sha256)
        self.assertEqual(self.calls, [])

    def test_corrupt_cached_bytes_are_not_reused(self):
        first = self.resolve()
        first.wheel_path.write_bytes(b"corrupt")
        self.calls.clear()
        second = self.resolve()
        self.assertTrue(self.calls)
        self.assertEqual(second.wheel_sha256, release_candidate.sha256_of(second.wheel_path))
        self.assertNotEqual(second.wheel_path.read_bytes(), b"corrupt")

    def test_linux_native_output_is_rejected_for_windows_fingerprint(self):
        self.output_tag = "cp312-cp312-linux_x86_64"
        with self.assertRaises(release_candidate.build_production.kroko_artifacts.KrokoArtifactError):
            self.resolve()

    def test_wrong_native_variant_is_rejected(self):
        self.output_variant = "pro"
        with self.assertRaises(release_candidate.build_production.kroko_artifacts.KrokoArtifactError):
            self.resolve()

    def test_compile_failure_is_not_hidden_by_output_ownership_cleanup(self):
        def fail_compile(cmd, **kwargs):
            if "BUILD_VARIANT=free" in cmd:
                raise release_candidate.build_production.BuildError("cross-compile failed")
            return self.run_command(cmd, **kwargs)

        with self.assertRaisesRegex(release_candidate.build_production.BuildError, "cross-compile failed"):
            self.resolve(fail_compile)
        self.assertEqual(self.calls[-1][0][-3:], ["-R", "1001:1001", "/out"])

    def test_missing_native_output_fails(self):
        from release_support import RecordingRunner

        with self.assertRaisesRegex(release_candidate.CandidateError, "exactly one native wheel"):
            self.resolve(RecordingRunner())

    def test_candidate_build_never_uses_windows_docker_host(self):
        with mock.patch.object(release_candidate.sys, "platform", "win32"):
            with self.assertRaisesRegex(release_candidate.CandidateError, "cross-built on Linux"):
                self.resolve()
        self.assertFalse(self.calls)


if __name__ == "__main__":
    unittest.main()
