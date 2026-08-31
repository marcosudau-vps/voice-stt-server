"""AP-SRV-070 W4A - persistent Kroko artifacts: reuse, force, integrity, secrets.

The point of the store is that a normal build must not recompile Kroko. These
tests drive the real ``install_kroko.main`` flow with an instrumented builder,
so "did it compile?" is answered by counting actual builder invocations rather
than by trusting a log line.

The builder is instrumented rather than executed: a real native build takes
about half an hour, and repeating it would prove nothing that counting the
calls does not.
"""

import json
import os
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from VoiceSTT import install_kroko
from VoiceSTT.kroko import artifacts, buildinputs, fingerprint


def make_wheel(directory, *, variant="free", tag="cp312-cp312-win_amd64", version="1.12.9",
               payload=b"native-bytes"):
    """Writes a structurally valid Kroko-style wheel.

    Real enough for every check the store performs - PEP 427 filename, a
    ``dist-info/WHEEL`` carrying the tag and the ``1free``/``1pro`` build tag -
    without needing a real 30-minute compilation.
    """
    build_tag = "1" + variant
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"kroko_onnx-{version}-{build_tag}-{tag}.whl"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            f"kroko_onnx-{version}.dist-info/WHEEL",
            "Wheel-Version: 1.0\nGenerator: voicestt-test\n"
            f"Root-Is-Purelib: false\nTag: {tag}\nBuild: {build_tag}\n",
        )
        archive.writestr(
            f"kroko_onnx-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.1\nName: kroko-onnx\nVersion: {version}\n",
        )
        archive.writestr("kroko_onnx/__init__.py", "")
        archive.writestr("kroko_onnx/_payload.bin", payload)
    return path


class WheelIntrospectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)

    def test_parses_a_pep427_wheel_filename_with_build_tag(self):
        parsed = artifacts.parse_wheel_filename(
            "kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64.whl"
        )
        self.assertEqual(parsed["name"], "kroko_onnx")
        self.assertEqual(parsed["build"], "1free")
        self.assertEqual(parsed["abi"], "cp312")
        self.assertEqual(parsed["platform"], "win_amd64")

    def test_reads_the_variant_from_the_wheel_itself(self):
        self.assertEqual(artifacts.variant_of_wheel(make_wheel(self.dir, variant="free")), "free")
        self.assertEqual(artifacts.variant_of_wheel(make_wheel(self.dir, variant="pro")), "pro")

    def test_wheel_without_a_variant_tag_stays_unproven(self):
        path = self.dir / "kroko_onnx-1.12.9-cp312-cp312-win_amd64.whl"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(
                "kroko_onnx-1.12.9.dist-info/WHEEL",
                "Wheel-Version: 1.0\nTag: cp312-cp312-win_amd64\n",
            )
        self.assertIsNone(artifacts.variant_of_wheel(path))

    def test_corrupt_archive_is_reported_not_guessed(self):
        path = self.dir / "kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64.whl"
        path.write_bytes(b"this is not a zip file")
        self.assertIsNone(artifacts.variant_of_wheel(path))


class StoreBaseTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = artifacts.KrokoArtifactStore(self.root / "store")
        self.build_dir = self.root / "build"

    def inputs_for(self, variant="free"):
        return fingerprint.compute_fingerprint(
            variant=variant,
            target_platform="windows",
            architecture="amd64",
            python_tag="cp312",
            abi_tag="cp312",
        )


class StoreAndReuseTests(StoreBaseTest):
    """W4A-09.7/09.8/09.9 - build once, then reuse."""

    def test_storing_a_wheel_produces_a_verified_artifact(self):
        computed = self.inputs_for("free")
        wheel = make_wheel(self.build_dir, variant="free")

        record = self.store.store(
            wheel_path=wheel,
            fingerprint=computed["fingerprint"],
            inputs=computed["inputs"],
        )

        self.assertTrue(record.wheel_path.is_file())
        self.assertEqual(record.variant, "free")
        self.assertEqual(record.wheel_sha256, artifacts.sha256_of(wheel))
        self.assertEqual(record.metadata["wheelBytes"], wheel.stat().st_size)
        self.assertEqual(record.metadata["upstreamRevision"], buildinputs.KROKO_UPSTREAM_REVISION)
        self.assertEqual(record.metadata["wheelTags"], ["cp312-cp312-win_amd64"])

    def test_stored_artifact_is_found_again(self):
        computed = self.inputs_for("free")
        self.store.store(
            wheel_path=make_wheel(self.build_dir, variant="free"),
            fingerprint=computed["fingerprint"],
            inputs=computed["inputs"],
        )
        found, problems = self.store.lookup(
            variant="free",
            fingerprint=computed["fingerprint"],
            inputs=computed["inputs"],
        )
        self.assertIsNotNone(found)
        self.assertEqual(problems, [])

    def test_free_and_pro_use_separate_namespaces(self):
        free = self.inputs_for("free")
        pro = self.inputs_for("pro")
        self.assertNotEqual(free["fingerprint"], pro["fingerprint"])

        self.store.store(
            wheel_path=make_wheel(self.build_dir / "free", variant="free"),
            fingerprint=free["fingerprint"], inputs=free["inputs"],
        )
        self.store.store(
            wheel_path=make_wheel(self.build_dir / "pro", variant="pro"),
            fingerprint=pro["fingerprint"], inputs=pro["inputs"],
        )

        self.assertTrue(self.store.variant_dir("free").is_dir())
        self.assertTrue(self.store.variant_dir("pro").is_dir())
        self.assertNotEqual(
            self.store.slot_dir("free", free["fingerprint"]),
            self.store.slot_dir("pro", pro["fingerprint"]),
        )

        # W4A-09.9: the free artifact survives an intervening pro build.
        found, _ = self.store.lookup(
            variant="free", fingerprint=free["fingerprint"], inputs=free["inputs"]
        )
        self.assertIsNotNone(found)
        self.assertEqual(found.variant, "free")


class VariantConfusionTests(StoreBaseTest):
    """W4A-09.10 - free and pro must never be substituted for one another."""

    def test_a_pro_wheel_cannot_be_stored_as_free(self):
        computed = self.inputs_for("free")
        pro_wheel = make_wheel(self.build_dir, variant="pro")
        with self.assertRaises(artifacts.KrokoArtifactError) as caught:
            self.store.store(
                wheel_path=pro_wheel,
                fingerprint=computed["fingerprint"],
                inputs=computed["inputs"],
            )
        self.assertIn("variant", str(caught.exception))

    def test_a_free_artifact_is_not_returned_for_a_pro_request(self):
        free = self.inputs_for("free")
        self.store.store(
            wheel_path=make_wheel(self.build_dir, variant="free"),
            fingerprint=free["fingerprint"], inputs=free["inputs"],
        )
        pro = self.inputs_for("pro")
        found, problems = self.store.lookup(
            variant="pro", fingerprint=pro["fingerprint"], inputs=pro["inputs"]
        )
        self.assertIsNone(found)
        self.assertTrue(problems)

    def test_metadata_variant_mismatch_is_refused(self):
        computed = self.inputs_for("free")
        wheel = make_wheel(self.build_dir, variant="free")
        metadata = artifacts.build_metadata(
            fingerprint=computed["fingerprint"],
            inputs=computed["inputs"],
            wheel_path=wheel,
            wheel_sha256=artifacts.sha256_of(wheel),
        )
        metadata["variant"] = "pro"
        ok, problems = artifacts.verify_artifact(
            metadata, wheel,
            expected_fingerprint=computed["fingerprint"],
            expected_variant="free",
        )
        self.assertFalse(ok)
        self.assertTrue(any("variant" in problem for problem in problems))


class IntegrityRejectionTests(StoreBaseTest):
    """W4A-09.13/09.14 - a damaged or foreign artifact is a hard miss."""

    def _stored(self, variant="free"):
        computed = self.inputs_for(variant)
        record = self.store.store(
            wheel_path=make_wheel(self.build_dir, variant=variant),
            fingerprint=computed["fingerprint"],
            inputs=computed["inputs"],
        )
        return computed, record

    def test_tampered_wheel_bytes_are_rejected(self):
        computed, record = self._stored()
        record.wheel_path.write_bytes(b"corrupted")
        found, problems = self.store.lookup(
            variant="free", fingerprint=computed["fingerprint"], inputs=computed["inputs"]
        )
        self.assertIsNone(found)
        self.assertTrue(any("sha256" in p or "bytes" in p for p in problems))

    def test_missing_wheel_is_rejected(self):
        computed, record = self._stored()
        record.wheel_path.unlink()
        found, problems = self.store.lookup(
            variant="free", fingerprint=computed["fingerprint"], inputs=computed["inputs"]
        )
        self.assertIsNone(found)
        self.assertTrue(any("missing" in p for p in problems))

    def test_foreign_fingerprint_is_rejected(self):
        computed, record = self._stored()
        metadata_path = record.slot_dir / artifacts.ARTIFACT_METADATA_NAME
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["fingerprint"] = "deadbeefdeadbeef"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        found, problems = self.store.lookup(
            variant="free", fingerprint=computed["fingerprint"], inputs=computed["inputs"]
        )
        self.assertIsNone(found)
        self.assertTrue(any("fingerprint" in p for p in problems))

    def test_incompatible_abi_tag_is_rejected(self):
        computed = self.inputs_for("free")
        wheel = make_wheel(self.build_dir, variant="free", tag="cp311-cp311-win_amd64")
        with self.assertRaises(artifacts.KrokoArtifactError):
            self.store.store(
                wheel_path=wheel,
                fingerprint=computed["fingerprint"],
                inputs=computed["inputs"],
            )

    def test_mismatched_stored_inputs_are_rejected(self):
        computed, record = self._stored()
        other = self.inputs_for("free")
        other["inputs"]["target"]["architecture"] = "arm64"
        found, problems = self.store.lookup(
            variant="free", fingerprint=computed["fingerprint"], inputs=other["inputs"]
        )
        self.assertIsNone(found)
        self.assertTrue(problems)

    def test_absent_artifact_is_a_clean_miss(self):
        computed = self.inputs_for("free")
        found, problems = self.store.lookup(
            variant="free", fingerprint=computed["fingerprint"], inputs=computed["inputs"]
        )
        self.assertIsNone(found)
        self.assertEqual(problems, ["no stored artifact for this variant/fingerprint"])


class AtomicReplacementTests(StoreBaseTest):
    """W4A-09.12 - a failed rebuild must not destroy a good artifact."""

    def test_failed_store_keeps_the_previous_good_artifact(self):
        computed = self.inputs_for("free")
        good = make_wheel(self.build_dir / "good", variant="free", payload=b"good-build")
        record = self.store.store(
            wheel_path=good,
            fingerprint=computed["fingerprint"],
            inputs=computed["inputs"],
        )
        good_sha = record.wheel_sha256

        # A "rebuild" that produced the wrong variant must be refused outright.
        bad = make_wheel(self.build_dir / "bad", variant="pro", payload=b"bad-build")
        with self.assertRaises(artifacts.KrokoArtifactError):
            self.store.store(
                wheel_path=bad,
                fingerprint=computed["fingerprint"],
                inputs=computed["inputs"],
            )

        still_there, problems = self.store.lookup(
            variant="free", fingerprint=computed["fingerprint"], inputs=computed["inputs"]
        )
        self.assertIsNotNone(still_there, f"good artifact was lost: {problems}")
        self.assertEqual(still_there.wheel_sha256, good_sha)

    def test_successful_store_replaces_the_previous_artifact(self):
        computed = self.inputs_for("free")
        first = self.store.store(
            wheel_path=make_wheel(self.build_dir / "a", variant="free", payload=b"first"),
            fingerprint=computed["fingerprint"], inputs=computed["inputs"],
        )
        second = self.store.store(
            wheel_path=make_wheel(self.build_dir / "b", variant="free", payload=b"second"),
            fingerprint=computed["fingerprint"], inputs=computed["inputs"],
        )
        self.assertNotEqual(first.wheel_sha256, second.wheel_sha256)

        found, _ = self.store.lookup(
            variant="free", fingerprint=computed["fingerprint"], inputs=computed["inputs"]
        )
        self.assertEqual(found.wheel_sha256, second.wheel_sha256)
        # No leftover staging or backup directories.
        leftovers = [p.name for p in self.store.root.glob("*") if p.name.startswith(".")]
        for name in leftovers:
            self.assertEqual(name, artifacts.STAGING_DIR_NAME)
        self.assertEqual(list((self.store.root / artifacts.STAGING_DIR_NAME).iterdir()), [])


class StoreRootResolutionTests(unittest.TestCase):
    """W4A-04 - configurable store root, no hardcoded personal paths."""

    def test_explicit_argument_wins(self):
        with TemporaryDirectory() as temp:
            self.assertEqual(
                artifacts.resolve_store_root(temp), Path(temp).resolve()
            )

    def test_environment_variable_is_honoured(self):
        with TemporaryDirectory() as temp:
            with mock.patch.dict(
                os.environ, {artifacts.ARTIFACT_STORE_ENV: temp}, clear=False
            ):
                self.assertEqual(artifacts.resolve_store_root(), Path(temp).resolve())

    def test_default_root_is_outside_the_repository(self):
        repo_root = Path(__file__).resolve().parents[2]
        default = artifacts.default_store_root().resolve()
        self.assertNotIn(repo_root, default.parents)
        self.assertNotEqual(default, repo_root)


class BuilderReuseFlowTests(unittest.TestCase):
    """W4A-09.8/09.11 - the real CLI flow reuses by default and rebuilds on demand."""

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store_root = self.root / "store"
        self.build_calls = []

    def run_builder(self, extra_args=(), wheel_variant=None, build_error=None):
        """Runs ``install_kroko.main`` with an instrumented, non-compiling builder."""

        def fake_build_wheel(args, repo_dir):
            self.build_calls.append(args.variant)
            if build_error is not None:
                raise build_error
            return make_wheel(
                self.root / f"build-{len(self.build_calls)}",
                variant=wheel_variant or args.variant,
            )

        argv = [
            "--build",
            "--skip-install",
            "--artifact-store", str(self.store_root),
        ] + list(extra_args)

        with mock.patch.object(install_kroko, "build_wheel", side_effect=fake_build_wheel), \
             mock.patch.object(install_kroko, "preflight_build", return_value=self.root / "work"), \
             mock.patch.object(install_kroko, "prepare_checkout", return_value=self.root / "checkout"):
            return install_kroko.main(argv)

    def test_first_build_compiles_and_stores(self):
        self.assertEqual(self.run_builder(), 0)
        self.assertEqual(self.build_calls, ["free"])

    def test_second_identical_run_does_not_compile_again(self):
        self.assertEqual(self.run_builder(), 0)
        self.assertEqual(self.run_builder(), 0)
        self.assertEqual(
            self.build_calls, ["free"], "a matching artifact must be reused, not rebuilt"
        )

    def test_free_artifact_is_reused_after_an_intervening_pro_build(self):
        self.run_builder()                               # free build
        self.run_builder(["--variant", "pro"])           # pro build
        self.run_builder()                               # free again -> reuse
        self.assertEqual(self.build_calls, ["free", "pro"])

    def test_force_rebuild_really_invokes_the_builder(self):
        self.run_builder()
        self.assertEqual(self.build_calls, ["free"])
        self.assertEqual(self.run_builder(["--rebuild-kroko"]), 0)
        self.assertEqual(
            self.build_calls, ["free", "free"], "--rebuild-kroko must call the builder"
        )

    def test_failed_force_rebuild_keeps_the_existing_artifact(self):
        self.run_builder()
        computed = fingerprint.compute_fingerprint(variant="free")
        store = artifacts.KrokoArtifactStore(self.store_root)
        before, _ = store.lookup(
            variant="free", fingerprint=computed["fingerprint"], inputs=computed["inputs"]
        )
        self.assertIsNotNone(before)

        exit_code = self.run_builder(
            ["--rebuild-kroko"],
            build_error=install_kroko.KrokoInstallError("compiler exploded"),
        )
        self.assertEqual(exit_code, 1)

        after, problems = store.lookup(
            variant="free", fingerprint=computed["fingerprint"], inputs=computed["inputs"]
        )
        self.assertIsNotNone(after, f"failed rebuild destroyed the artifact: {problems}")
        self.assertEqual(after.wheel_sha256, before.wheel_sha256)

    def test_describe_artifact_reports_presence_without_building(self):
        payload = install_kroko.describe_artifact(
            install_kroko.parse_args(
                ["--build", "--artifact-store", str(self.store_root)]
            )
        )
        self.assertFalse(payload["artifactPresent"])
        self.assertEqual(self.build_calls, [])

        self.run_builder()

        payload = install_kroko.describe_artifact(
            install_kroko.parse_args(
                ["--build", "--artifact-store", str(self.store_root)]
            )
        )
        self.assertTrue(payload["artifactPresent"])
        self.assertEqual(payload["variant"], "free")
        self.assertIn("wheelSha256", payload["artifact"])


class SecretLeakageTests(StoreBaseTest):
    """W4A-09.17 - a Kroko license key must never reach an artifact."""

    KEY_ENVS = (
        "KROKO_API_KEY", "KROKO_ONNX_KEY", "VOICESTT_KROKO_ONNX_KEY", "KROKO_KEY",
    )
    SECRET = "kroko-secret-key-should-never-be-stored-4a7f"

    def test_no_key_env_reaches_artifact_metadata_or_wheel(self):
        computed = self.inputs_for("free")
        environment = {name: self.SECRET for name in self.KEY_ENVS}

        with mock.patch.dict(os.environ, environment, clear=False):
            record = self.store.store(
                wheel_path=make_wheel(self.build_dir, variant="free"),
                fingerprint=computed["fingerprint"],
                inputs=computed["inputs"],
            )
            fingerprint_blob = fingerprint.compute_fingerprint(variant="free")["canonical"]

        metadata_text = (record.slot_dir / artifacts.ARTIFACT_METADATA_NAME).read_text(
            encoding="utf-8"
        )
        self.assertNotIn(self.SECRET, metadata_text)
        self.assertNotIn(self.SECRET, fingerprint_blob)
        self.assertNotIn(self.SECRET, record.wheel_path.read_bytes().decode("latin-1"))
        self.assertNotIn(self.SECRET, json.dumps(record.public_dict()))

    def test_pro_build_environment_carries_no_key(self):
        environment = {name: self.SECRET for name in self.KEY_ENVS}
        with mock.patch.dict(os.environ, environment, clear=False):
            build_env = install_kroko.linux_build_env("pro")

        # The Pro build is enabled by a capability switch, not by a key.
        self.assertEqual(
            build_env[buildinputs.PRO_BUILD_ENV_NAME], buildinputs.PRO_BUILD_ENV_VALUE
        )
        cmake_args = build_env["SHERPA_ONNX_CMAKE_ARGS"]
        self.assertNotIn(self.SECRET, cmake_args)
        self.assertNotIn(self.SECRET, build_env.get("SHERPA_ONNX_MAKE_ARGS", ""))

    def test_free_build_environment_does_not_enable_pro(self):
        build_env = install_kroko.linux_build_env("free")
        self.assertNotIn(buildinputs.PRO_BUILD_ENV_NAME, build_env)


if __name__ == "__main__":
    unittest.main()
