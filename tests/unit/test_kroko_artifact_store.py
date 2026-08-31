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
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
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

    def test_forced_store_replaces_the_previous_artifact(self):
        """adopt_existing=False (the --rebuild-kroko path) always replaces.

        See RootHardeningConcurrentSlotAccessTests / BuilderReuseFlowTests for
        the *default* (adopt_existing=True) behavior, which deliberately does
        the opposite for an ordinary reuse-by-default race: it adopts an
        already-stored, equally valid artifact instead of replacing it.
        """
        computed = self.inputs_for("free")
        first = self.store.store(
            wheel_path=make_wheel(self.build_dir / "a", variant="free", payload=b"first"),
            fingerprint=computed["fingerprint"], inputs=computed["inputs"],
            adopt_existing=False,
        )
        second = self.store.store(
            wheel_path=make_wheel(self.build_dir / "b", variant="free", payload=b"second"),
            fingerprint=computed["fingerprint"], inputs=computed["inputs"],
            adopt_existing=False,
        )
        self.assertNotEqual(first.wheel_sha256, second.wheel_sha256)

        found, _ = self.store.lookup(
            variant="free", fingerprint=computed["fingerprint"], inputs=computed["inputs"]
        )
        self.assertEqual(found.wheel_sha256, second.wheel_sha256)
        # No leftover staging or backup directories/files.
        #
        # AP-SRV-070 W4A-C2, Root Finding H: the lock *file* itself is no
        # longer expected to be absent here - it is now deliberately never
        # deleted (see KrokoArtifactStore._slot_lock's docstring for why:
        # unlinking it would reintroduce the classic advisory-lock "unlink
        # race"). Only the OS lock state is released, not the file. Staging
        # must still be fully empty; the lock directory containing exactly
        # this one inert marker file is the expected, correct steady state.
        leftovers = [p.name for p in self.store.root.glob("*") if p.name.startswith(".")]
        for name in leftovers:
            self.assertIn(name, (artifacts.STAGING_DIR_NAME, artifacts.LOCK_DIR_NAME))
        self.assertEqual(list((self.store.root / artifacts.STAGING_DIR_NAME).iterdir()), [])
        lock_files = list((self.store.root / artifacts.LOCK_DIR_NAME).iterdir())
        self.assertEqual(len(lock_files), 1)
        self.assertTrue(lock_files[0].name.startswith("free__"))

    def test_default_store_adopts_rather_than_replaces_an_existing_artifact(self):
        """The counterpart: adopt_existing defaults to True (Root Hardening)."""
        computed = self.inputs_for("free")
        first = self.store.store(
            wheel_path=make_wheel(self.build_dir / "a", variant="free", payload=b"first"),
            fingerprint=computed["fingerprint"], inputs=computed["inputs"],
        )
        second = self.store.store(
            wheel_path=make_wheel(self.build_dir / "b", variant="free", payload=b"second"),
            fingerprint=computed["fingerprint"], inputs=computed["inputs"],
        )
        self.assertEqual(first.wheel_sha256, second.wheel_sha256)


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
            # A distinct payload per invocation, so a test can tell whether the
            # *stored* artifact actually came from this specific build call
            # (Root Hardening: adopt_existing=False on a forced rebuild must
            # really replace, not silently keep an earlier build's bytes).
            return make_wheel(
                self.root / f"build-{len(self.build_calls)}",
                variant=wheel_variant or args.variant,
                payload=f"native-bytes-build-{len(self.build_calls)}".encode(),
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

    def test_reuse_hit_never_calls_prepare_checkout(self):
        """AP-SRV-070 W4A-C2, Root Finding F, RED-proof #4.

        The pristine-checkout materialization added for Finding F lives
        inside prepare_checkout(); a reuse hit must never reach it at all, so
        a cache hit stays exactly as cheap as before - no checkout, no git
        commands, no re-materialization.
        """
        self.assertEqual(self.run_builder(), 0)  # first run: real cache miss

        argv = ["--build", "--skip-install", "--artifact-store", str(self.store_root)]
        with mock.patch.object(install_kroko, "build_wheel") as build_wheel, \
             mock.patch.object(install_kroko, "preflight_build") as preflight, \
             mock.patch.object(install_kroko, "prepare_checkout") as prepare:
            exit_code = install_kroko.main(argv)  # second run: must be a hit

        self.assertEqual(exit_code, 0)
        prepare.assert_not_called()
        preflight.assert_not_called()
        build_wheel.assert_not_called()

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

    def test_force_rebuild_actually_replaces_the_stored_artifact(self):
        """Root Hardening: adopt_existing=False on --rebuild-kroko must hold.

        Two independent build-then-store calls for the same slot could
        otherwise "adopt" each other's result (the race-safety behavior that
        protects an ordinary reuse-by-default miss) - which would make
        --rebuild-kroko silently keep the stale artifact it was explicitly
        asked to replace. This asserts the *stored bytes* actually changed,
        not merely that the builder was called twice.
        """
        self.run_builder()
        self.run_builder(["--rebuild-kroko"])

        computed = fingerprint.compute_fingerprint(variant="free")
        store = artifacts.KrokoArtifactStore(self.store_root)
        found, problems = store.lookup(
            variant="free", fingerprint=computed["fingerprint"], inputs=computed["inputs"]
        )
        self.assertIsNotNone(found, problems)
        second_build_wheel = self.root / "build-2"
        expected_sha = artifacts.sha256_of(next(second_build_wheel.glob("*.whl")))
        self.assertEqual(
            found.wheel_sha256, expected_sha,
            "the forced rebuild's own wheel must be the one stored, not the earlier one",
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
        """AP-SRV-070 W4A-C1, Root Finding C.

        The previous version of this test only checked that the secret value
        did not appear inside the CMAKE_ARGS/MAKE_ARGS *strings* - it never
        proved the key variables themselves were absent from the environment
        dict, and they were not: linux_build_env() copied the full host
        environment. This asserts the actual Root Finding C requirement: the
        variable names are gone from the build child environment entirely.
        """
        environment = {name: self.SECRET for name in self.KEY_ENVS}
        with mock.patch.dict(os.environ, environment, clear=False):
            build_env = install_kroko.linux_build_env("pro")

        for name in self.KEY_ENVS:
            self.assertNotIn(
                name, build_env, f"{name} leaked into the Linux build environment"
            )
        # The Pro build is enabled by a capability switch, not by a key.
        self.assertEqual(
            build_env[buildinputs.PRO_BUILD_ENV_NAME], buildinputs.PRO_BUILD_ENV_VALUE
        )
        self.assertNotIn(self.SECRET, build_env["SHERPA_ONNX_CMAKE_ARGS"])
        self.assertNotIn(self.SECRET, build_env.get("SHERPA_ONNX_MAKE_ARGS", ""))

    def test_windows_build_environment_carries_no_key(self):
        """AP-SRV-070 W4A-C1, Root Finding C - the Windows build child env.

        The Windows path previously started cmd.exe with no explicit
        environment at all (env=None), which meant it silently inherited the
        full parent process environment, keys included.
        """
        environment = {name: self.SECRET for name in self.KEY_ENVS}
        with mock.patch.dict(os.environ, environment, clear=False):
            build_env = install_kroko.windows_build_env()

        for name in self.KEY_ENVS:
            self.assertNotIn(
                name, build_env, f"{name} leaked into the Windows build environment"
            )

    def test_free_build_environment_does_not_enable_pro(self):
        """AP-SRV-070 W4A-C2, Root Finding E strengthened this assertion.

        Before C2, a free build simply left KROKO_LICENSE unset (absent) -
        which was itself the bug: if the operator's own shell already had
        KROKO_LICENSE=ON, "absent from our own explicit settings" meant
        "silently inherited as ON". The switch must now be explicitly OFF,
        not merely absent; see RootFindingELinuxCapabilityIsolationTests for
        the direct ambient-inheritance regression test.
        """
        build_env = install_kroko.linux_build_env("free")
        self.assertIn(buildinputs.PRO_BUILD_ENV_NAME, build_env)
        self.assertEqual(
            build_env[buildinputs.PRO_BUILD_ENV_NAME], buildinputs.PRO_BUILD_ENV_OFF_VALUE
        )

    def test_runtime_key_lookup_outside_the_builder_is_unchanged(self):
        """The Secret Boundary correction must not touch runtime key reading.

        Root Finding C is exclusively about the *build* subprocess
        environment; the engine's own runtime key lookup
        (kroko_onnx_engine.py) is untouched by this correction and still
        reads the same four environment variables directly.
        """
        from VoiceSTT.transcription_engines import kroko_onnx_engine as engine_module

        with mock.patch.dict(os.environ, {"KROKO_API_KEY": self.SECRET}, clear=False):
            self.assertEqual(os.environ.get("KROKO_API_KEY"), self.SECRET)
        source = engine_module.__file__
        import pathlib

        text = pathlib.Path(source).read_text(encoding="utf-8")
        for name in self.KEY_ENVS:
            self.assertIn(name, text, f"engine no longer reads {name} at runtime")


class RootFindingBLinuxBuildEnvTests(unittest.TestCase):
    """AP-SRV-070 W4A-C1, Root Finding B - no undeclared ambient build input.

    linux_build_env() used to copy the full host environment, append to any
    pre-existing SHERPA_ONNX_CMAKE_ARGS instead of overriding it, and only
    default SHERPA_ONNX_MAKE_ARGS if unset - so a value already present in the
    operator's shell silently participated in the compile without ever being
    reflected in the declared build inputs.
    """

    AMBIENT_OVERRIDE_ENVS = {
        "CC": "clang",
        "CXX": "clang++",
        "CFLAGS": "-O0 -fsanitize=address",
        "CXXFLAGS": "-O0 -fsanitize=address",
        "LDFLAGS": "-static",
        "CPPFLAGS": "-DEVIL",
        "CMAKE_GENERATOR": "Ninja",
        "CMAKE_TOOLCHAIN_FILE": "/tmp/evil-toolchain.cmake",
        "LD_LIBRARY_PATH": "/tmp/evil-lib",
    }

    def test_ambient_compiler_overrides_never_reach_the_build_environment(self):
        with mock.patch.dict(os.environ, self.AMBIENT_OVERRIDE_ENVS, clear=False):
            env = install_kroko.linux_build_env("free")

        for name in self.AMBIENT_OVERRIDE_ENVS:
            self.assertNotIn(
                name, env, f"{name} leaked into the Linux build environment"
            )

    def test_cmake_args_override_ambient_value_instead_of_appending(self):
        with mock.patch.dict(
            os.environ, {"SHERPA_ONNX_CMAKE_ARGS": "-DEVIL_FLAG=ON"}, clear=False
        ):
            env = install_kroko.linux_build_env("free")
        self.assertEqual(env["SHERPA_ONNX_CMAKE_ARGS"], buildinputs.LINUX_CMAKE_FLAGS)
        self.assertNotIn("-DEVIL_FLAG=ON", env["SHERPA_ONNX_CMAKE_ARGS"])

    def test_make_args_override_ambient_value_instead_of_defaulting(self):
        with mock.patch.dict(os.environ, {"SHERPA_ONNX_MAKE_ARGS": "-j999"}, clear=False):
            env = install_kroko.linux_build_env("free")
        self.assertEqual(env["SHERPA_ONNX_MAKE_ARGS"], buildinputs.LINUX_MAKE_ARGS)

    def test_declared_flags_are_still_applied_with_a_clean_environment(self):
        env = install_kroko.linux_build_env("free")
        self.assertEqual(env["SHERPA_ONNX_CMAKE_ARGS"], buildinputs.LINUX_CMAKE_FLAGS)
        self.assertEqual(env["SHERPA_ONNX_MAKE_ARGS"], buildinputs.LINUX_MAKE_ARGS)


class RootFindingDWheelPlatformVerificationTests(StoreBaseTest):
    """AP-SRV-070 W4A-C1, Root Finding D - the wheel tag's platform must match.

    verify_artifact() used to check only that a wheel tag *started with* the
    expected Python/ABI fragment - a structurally valid
    cp312-cp312-win_amd64 wheel could pass under a Linux-targeted fingerprint
    whose Python tag/ABI happened to match, because the platform component of
    the tag itself was never checked against the target.
    """

    def _store_and_lookup(self, *, wheel_tag, target_platform, architecture):
        computed = fingerprint.compute_fingerprint(
            variant="free",
            target_platform=target_platform,
            architecture=architecture,
            python_tag="cp312",
            abi_tag="cp312",
            toolchain={"kind": "test"},
        )
        wheel = make_wheel(self.build_dir, variant="free", tag=wheel_tag)
        try:
            self.store.store(
                wheel_path=wheel, fingerprint=computed["fingerprint"], inputs=computed["inputs"]
            )
        except artifacts.KrokoArtifactError:
            return None, computed
        found, problems = self.store.lookup(
            variant="free", fingerprint=computed["fingerprint"], inputs=computed["inputs"]
        )
        return found, computed

    def test_windows_wheel_is_rejected_under_linux_inputs(self):
        found, _ = self._store_and_lookup(
            wheel_tag="cp312-cp312-win_amd64",
            target_platform="linux",
            architecture="amd64",
        )
        self.assertIsNone(found, "a Windows wheel must never satisfy a Linux fingerprint")

    def test_linux_wheel_is_rejected_under_windows_inputs(self):
        found, _ = self._store_and_lookup(
            wheel_tag="cp312-cp312-linux_x86_64",
            target_platform="windows",
            architecture="amd64",
        )
        self.assertIsNone(found, "a Linux wheel must never satisfy a Windows fingerprint")

    def test_arm64_wheel_is_rejected_under_amd64_inputs(self):
        found, _ = self._store_and_lookup(
            wheel_tag="cp312-cp312-manylinux_2_28_aarch64",
            target_platform="linux",
            architecture="amd64",
        )
        self.assertIsNone(found, "an arm64 wheel must never satisfy an amd64 fingerprint")

    def test_amd64_wheel_is_rejected_under_arm64_inputs(self):
        found, _ = self._store_and_lookup(
            wheel_tag="cp312-cp312-manylinux_2_28_x86_64",
            target_platform="linux",
            architecture="arm64",
        )
        self.assertIsNone(found, "an amd64 wheel must never satisfy an arm64 fingerprint")

    def test_matching_windows_wheel_is_accepted(self):
        found, _ = self._store_and_lookup(
            wheel_tag="cp312-cp312-win_amd64",
            target_platform="windows",
            architecture="amd64",
        )
        self.assertIsNotNone(found)

    def test_matching_manylinux_wheel_is_accepted(self):
        found, _ = self._store_and_lookup(
            wheel_tag="cp312-cp312-manylinux_2_28_x86_64",
            target_platform="linux",
            architecture="amd64",
        )
        self.assertIsNotNone(found)

    def test_platform_tag_matcher_directly(self):
        matches = artifacts.wheel_platform_tag_matches_target
        self.assertTrue(matches("win_amd64", "windows", "amd64"))
        self.assertFalse(matches("win_amd64", "linux", "amd64"))
        self.assertFalse(matches("linux_x86_64", "windows", "amd64"))
        self.assertTrue(matches("manylinux_2_28_x86_64", "linux", "amd64"))
        self.assertFalse(matches("manylinux_2_28_aarch64", "linux", "amd64"))
        self.assertTrue(matches("manylinux_2_28_aarch64", "linux", "arm64"))
        self.assertFalse(matches("", "linux", "amd64"))


class RootHardeningConcurrentSlotAccessTests(unittest.TestCase):
    """AP-SRV-070 W4A-C1, Root Hardening - the same slot under concurrent writers.

    Two processes that both see a cache miss for the same variant+fingerprint
    can both proceed to build and then both call store() around the same
    moment. This drives that scenario with real OS threads racing on the real
    filesystem lock/replace primitives - a meaningful stand-in for separate OS
    processes, because the lock this exercises (os.open with O_CREAT|O_EXCL)
    is an OS-level primitive, not a Python-level (GIL) one, and file I/O
    releases the GIL, so the threads genuinely race at the filesystem.
    """

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = artifacts.KrokoArtifactStore(self.root / "store")
        self.build_dir = self.root / "build"

    def test_concurrent_stores_of_the_same_slot_do_not_corrupt_it(self):
        import threading

        computed = fingerprint.compute_fingerprint(variant="free")
        wheel_a = make_wheel(self.build_dir / "a", variant="free", payload=b"racer-a")
        wheel_b = make_wheel(self.build_dir / "b", variant="free", payload=b"racer-b")

        barrier = threading.Barrier(2)
        results = {}
        errors = []

        def racer(name, wheel):
            try:
                barrier.wait(timeout=10)
                record = self.store.store(
                    wheel_path=wheel,
                    fingerprint=computed["fingerprint"],
                    inputs=computed["inputs"],
                )
                results[name] = record
            except Exception as exc:  # noqa: BLE001 - captured for assertion
                errors.append((name, exc))

        threads = [
            threading.Thread(target=racer, args=("a", wheel_a)),
            threading.Thread(target=racer, args=("b", wheel_b)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        self.assertEqual(errors, [], f"a concurrent store() call raised: {errors}")
        self.assertEqual(set(results), {"a", "b"})

        # Both racers must converge on exactly the same stored artifact -
        # whichever one actually won the race - not two different ones.
        self.assertEqual(results["a"].wheel_sha256, results["b"].wheel_sha256)

        # The persisted slot itself must verify cleanly and contain exactly
        # one wheel file - no partial write, no leftover competing copy.
        found, problems = self.store.lookup(
            variant="free", fingerprint=computed["fingerprint"], inputs=computed["inputs"]
        )
        self.assertIsNotNone(found, f"slot failed verification after the race: {problems}")
        wheel_files = list(found.slot_dir.glob("*.whl"))
        self.assertEqual(len(wheel_files), 1)

        # No staging debris left behind. AP-SRV-070 W4A-C2, Root Finding H:
        # the lock *file* is deliberately never deleted (see
        # KrokoArtifactStore._slot_lock's docstring - removing it would
        # reintroduce the advisory-lock "unlink race"), so exactly one inert
        # marker file for this slot is the expected steady state, not zero.
        self.assertEqual(list((self.store.root / artifacts.STAGING_DIR_NAME).glob("*")), [])
        lock_files = list((self.store.root / artifacts.LOCK_DIR_NAME).glob("*"))
        self.assertEqual(len(lock_files), 1)

    def test_a_second_store_call_reuses_an_already_stored_artifact(self):
        """A parallel process must adopt a hit, not clobber it (Root Hardening)."""
        computed = fingerprint.compute_fingerprint(variant="free")
        first = self.store.store(
            wheel_path=make_wheel(self.build_dir / "first", variant="free", payload=b"first"),
            fingerprint=computed["fingerprint"],
            inputs=computed["inputs"],
        )
        second = self.store.store(
            wheel_path=make_wheel(self.build_dir / "second", variant="free", payload=b"second"),
            fingerprint=computed["fingerprint"],
            inputs=computed["inputs"],
        )
        self.assertEqual(first.wheel_sha256, second.wheel_sha256)
        self.assertEqual(second.wheel_sha256, artifacts.sha256_of(first.wheel_path))

    def test_slot_lock_is_mutually_exclusive(self):
        """Direct proof of the lock primitive itself, independent of store()."""
        import threading
        import time as time_module

        order = []
        lock_entered = threading.Event()

        def holder():
            with self.store._slot_lock("free", "deadbeefdeadbeef", timeout=5):
                lock_entered.set()
                order.append("holder-enter")
                time_module.sleep(0.2)
                order.append("holder-exit")

        def waiter():
            lock_entered.wait(timeout=5)
            with self.store._slot_lock("free", "deadbeefdeadbeef", timeout=5):
                order.append("waiter-enter")

        threads = [threading.Thread(target=holder), threading.Thread(target=waiter)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertEqual(order, ["holder-enter", "holder-exit", "waiter-enter"])


class RootFindingELinuxCapabilityIsolationTests(unittest.TestCase):
    """AP-SRV-070 W4A-C2, Root Finding E - KROKO_LICENSE must never be ambient.

    Before this correction, only the ``pro`` branch of ``linux_build_env()``
    set ``KROKO_LICENSE`` explicitly; a ``free`` build silently kept whatever
    value (if any) the parent process already had. An operator whose shell
    already exported ``KROKO_LICENSE=ON`` - or a checkout whose CMake cache
    still carried it from a previous Pro build - could therefore get a
    Pro-capable build from ``--variant free``.
    """

    def test_ambient_license_on_does_not_survive_a_free_build(self):
        with mock.patch.dict(os.environ, {"KROKO_LICENSE": "ON"}, clear=False):
            env = install_kroko.linux_build_env("free")
        self.assertEqual(
            env[buildinputs.PRO_BUILD_ENV_NAME], buildinputs.PRO_BUILD_ENV_OFF_VALUE
        )

    def test_ambient_license_off_does_not_prevent_a_pro_build(self):
        with mock.patch.dict(os.environ, {"KROKO_LICENSE": "OFF"}, clear=False):
            env = install_kroko.linux_build_env("pro")
        self.assertEqual(
            env[buildinputs.PRO_BUILD_ENV_NAME], buildinputs.PRO_BUILD_ENV_VALUE
        )

    def test_ambient_garbage_value_does_not_survive_a_free_build(self):
        """Any ambient value, not just ON/OFF, must be overridden - free means OFF."""
        with mock.patch.dict(
            os.environ, {"KROKO_LICENSE": "definitely-not-a-recognized-value"}, clear=False
        ):
            env = install_kroko.linux_build_env("free")
        self.assertEqual(
            env[buildinputs.PRO_BUILD_ENV_NAME], buildinputs.PRO_BUILD_ENV_OFF_VALUE
        )

    def test_windows_build_env_does_not_inherit_the_ambient_capability_switch(self):
        with mock.patch.dict(os.environ, {"KROKO_LICENSE": "ON"}, clear=False):
            env = install_kroko.windows_build_env()
        self.assertNotIn(buildinputs.PRO_BUILD_ENV_NAME, env)

    def test_sanitizer_strips_the_capability_switch_directly(self):
        sanitized = install_kroko.sanitize_build_subprocess_env(
            {"KROKO_LICENSE": "ON", "PATH": "/usr/bin"}
        )
        self.assertNotIn("KROKO_LICENSE", sanitized)
        self.assertEqual(sanitized["PATH"], "/usr/bin")

    def test_runtime_key_variables_remain_stripped_regression(self):
        """Regression: Finding E must not weaken Finding C's key stripping."""
        environment = {name: "still-a-secret" for name in install_kroko.KROKO_LICENSE_KEY_ENV_NAMES}
        environment["KROKO_LICENSE"] = "ON"
        with mock.patch.dict(os.environ, environment, clear=False):
            env = install_kroko.linux_build_env("free")
        for name in install_kroko.KROKO_LICENSE_KEY_ENV_NAMES:
            self.assertNotIn(name, env)


class RootFindingFPristineCheckoutTests(unittest.TestCase):
    """AP-SRV-070 W4A-C2, Root Finding F - every real build starts pristine.

    Drives a real, throwaway local git repository (never the VoiceSTT
    worktree and never the real Kroko upstream) through the actual
    ``prepare_checkout()``/``materialize_pristine_checkout()`` code path, so
    "tracked files are reset and untracked ones are removed" is proven against
    real git behavior rather than asserted against a mock.
    """

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work_dir = Path(self.temp.name) / "work"
        self.work_dir.mkdir()
        self._make_local_upstream()

    def _run_git(self, args, cwd):
        subprocess.run(
            ["git"] + args, cwd=str(cwd), check=True,
            capture_output=True, text=True,
        )

    def _make_local_upstream(self):
        source = Path(self.temp.name) / "source"
        source.mkdir()
        self._run_git(["init"], cwd=source)
        self._run_git(["config", "user.email", "test@example.invalid"], cwd=source)
        self._run_git(["config", "user.name", "Test"], cwd=source)
        (source / "build_windows.bat").write_text("REM pristine upstream content\r\n")
        self._run_git(["add", "."], cwd=source)
        self._run_git(["commit", "-m", "initial"], cwd=source)
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(source),
            check=True, capture_output=True, text=True,
        )
        self.pinned_revision = result.stdout.strip()
        self.upstream_dir = Path(self.temp.name) / "upstream.git"
        self._run_git(["clone", "--bare", str(source), str(self.upstream_dir)], cwd=self.temp.name)

    def _clone_into_work_dir(self):
        repo_dir = self.work_dir / "kroko-onnx"
        self._run_git(["clone", str(self.upstream_dir), str(repo_dir)], cwd=self.work_dir)
        self._run_git(["checkout", "--detach", self.pinned_revision], cwd=repo_dir)
        return repo_dir

    def _args(self):
        return SimpleNamespace(
            force=False, branch="main", repo=str(self.upstream_dir),
            revision=self.pinned_revision,
        )

    def test_prepare_checkout_restores_a_tracked_file_modified_by_a_previous_patch_run(self):
        repo_dir = self._clone_into_work_dir()
        tracked = repo_dir / "build_windows.bat"
        tracked.write_text("REM already patched by a previous run\r\n")

        install_kroko.prepare_checkout(self._args(), work_dir=self.work_dir)

        # Compared with normalized line endings: git's own autocrlf handling
        # on this host may legitimately rewrite CRLF<->LF on checkout, which
        # is unrelated to what this test actually proves (that the *content*
        # was reset to the pristine upstream commit, not left as the
        # "already patched" modification).
        self.assertEqual(
            tracked.read_text().replace("\r\n", "\n").strip(),
            "REM pristine upstream content",
        )

    def test_prepare_checkout_removes_a_stale_cmake_cache_and_build_artifacts(self):
        repo_dir = self._clone_into_work_dir()
        cmake_cache = repo_dir / "CMakeCache.txt"
        cmake_cache.write_text("KROKO_LICENSE:BOOL=ON\n")
        build_dir = repo_dir / "release_artifacts"
        build_dir.mkdir()
        (build_dir / "stale.whl").write_bytes(b"stale")

        install_kroko.prepare_checkout(self._args(), work_dir=self.work_dir)

        self.assertFalse(
            cmake_cache.exists(), "a stale CMake cache must not survive prepare_checkout"
        )
        self.assertFalse(
            build_dir.exists(), "a stale build-artifact directory must not survive prepare_checkout"
        )

    def test_free_cannot_inherit_a_pro_builds_cached_cmake_state(self):
        """RED-proof #3: a stale Pro CMake cache cannot leak into a free build."""
        repo_dir = self._clone_into_work_dir()
        (repo_dir / "CMakeCache.txt").write_text("KROKO_LICENSE:BOOL=ON\n")

        install_kroko.prepare_checkout(self._args(), work_dir=self.work_dir)

        self.assertFalse((repo_dir / "CMakeCache.txt").exists())
        env = install_kroko.linux_build_env("free")
        self.assertEqual(
            env[buildinputs.PRO_BUILD_ENV_NAME], buildinputs.PRO_BUILD_ENV_OFF_VALUE
        )

    def test_effective_repo_and_revision_still_feed_the_fingerprint(self):
        """RED-proof #3 (fingerprint side): unaffected by the F correction."""
        args = SimpleNamespace(variant="free", repo="https://example.invalid/x.git", revision="d" * 40)
        computed = install_kroko.fingerprint_for(args)
        self.assertEqual(computed["inputs"]["upstream"]["repo"], "https://example.invalid/x.git")
        self.assertEqual(computed["inputs"]["upstream"]["revision"], "d" * 40)

    def test_abbreviated_revision_cannot_bypass_the_exact_commit_postcheck(self):
        """RED-proof #5: a short/abbreviated revision can never silently pass."""
        repo_dir = self._clone_into_work_dir()
        short_revision = self.pinned_revision[:10]
        with self.assertRaises(install_kroko.KrokoInstallError):
            install_kroko.ensure_pinned_revision(repo_dir, short_revision)

    def test_materialize_pristine_checkout_refuses_a_path_outside_the_work_root(self):
        """Defensive scoping guard, mirroring remove_tree_inside's existing pattern."""
        outside = Path(self.temp.name) / "not-under-work-dir"
        outside.mkdir()
        with self.assertRaises(install_kroko.KrokoInstallError):
            install_kroko.materialize_pristine_checkout(
                outside, self.pinned_revision, work_dir=self.work_dir
            )

    def test_materialize_pristine_checkout_refuses_the_work_root_itself(self):
        with self.assertRaises(install_kroko.KrokoInstallError):
            install_kroko.materialize_pristine_checkout(
                self.work_dir, self.pinned_revision, work_dir=self.work_dir
            )


class RootFindingHCrashRecoverableLockTests(unittest.TestCase):
    """AP-SRV-070 W4A-C2, Root Finding H - the slot lock survives a crash.

    C1's lock treated the lock file's mere *existence* as the mutex; a
    process killed after acquiring it left that file behind forever, and
    every future acquirer of the same slot would wait out the full timeout on
    every attempt with no automatic recovery. The lock is now a real OS
    advisory lock on an open handle, released by the OS itself the instant
    the holding handle closes - including when the process is killed.
    """

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = artifacts.KrokoArtifactStore(Path(self.temp.name) / "store")

    def test_orphaned_lock_is_reacquirable_without_manual_cleanup(self):
        """Simulates a crashed holder: acquire the OS lock, then close the
        handle *without* releasing it first - exactly what happens when a
        process is killed. A fresh acquirer must succeed immediately, not
        wait out the lock timeout, and no file needs to be deleted by hand.
        """
        lock_path = self.store._slot_lock_path("free", "deadbeefdeadbeef")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        crashed = open(lock_path, "a+b")
        if crashed.seek(0, 2) == 0:
            crashed.write(b"\0")
            crashed.flush()
        self.assertTrue(artifacts._acquire_os_lock(crashed))
        crashed.close()  # simulated crash: no _release_os_lock call

        import time

        start = time.monotonic()
        acquired = []
        with self.store._slot_lock("free", "deadbeefdeadbeef", timeout=5, poll_interval=0.01):
            acquired.append(True)
        elapsed = time.monotonic() - start
        self.assertEqual(acquired, [True])
        self.assertLess(elapsed, 1.0, "must not wait out the lock timeout for an orphaned lock")

    def test_orphaned_lock_after_a_real_killed_subprocess(self):
        """The strongest form of the proof: a genuinely separate OS process,
        forcibly killed while holding the lock.
        """
        lock_path = self.store._slot_lock_path("free", "cafebabecafebabe")
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        holder_script = (
            "import sys\n"
            "sys.path.insert(0, {repo!r})\n"
            "from VoiceSTT.kroko import artifacts\n"
            "handle = open({lock!r}, 'a+b')\n"
            "if handle.seek(0, 2) == 0:\n"
            "    handle.write(b'\\0'); handle.flush()\n"
            "assert artifacts._acquire_os_lock(handle)\n"
            "print('LOCKED', flush=True)\n"
            "import time\n"
            "time.sleep(30)\n"
        ).format(repo=str(Path(__file__).resolve().parents[2]), lock=str(lock_path))

        process = subprocess.Popen(
            [sys.executable, "-c", holder_script],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            line = process.stdout.readline()
            if line.strip() != "LOCKED":
                # ``process.stderr.read()`` blocks until the child's stderr
                # pipe hits EOF, which requires the (still-sleeping) child to
                # exit - so it must stay out of assertEqual's eagerly
                # evaluated ``msg`` argument. Calling it there previously made
                # every run of this test wait out the child's full 30s sleep
                # before ever reaching the ``kill()`` below, which defeated
                # the point of proving a *prompt* recovery after a kill.
                self.fail(f"expected LOCKED, got {line!r}: {process.stderr.read()}")
        finally:
            process.kill()
            process.wait(timeout=10)

        import time

        start = time.monotonic()
        acquired = []
        with self.store._slot_lock("free", "cafebabecafebabe", timeout=10, poll_interval=0.05):
            acquired.append(True)
        elapsed = time.monotonic() - start
        self.assertEqual(acquired, [True])
        self.assertLess(elapsed, 5.0, "must not wait out the lock timeout after a real process kill")

    def test_fresh_lock_still_excludes_a_second_acquirer(self):
        """Regression: the crash-safety change must not weaken exclusivity."""
        import threading
        import time as time_module

        order = []
        lock_entered = threading.Event()

        def holder():
            with self.store._slot_lock("free", "fadefadefadefade", timeout=5):
                lock_entered.set()
                order.append("holder-enter")
                time_module.sleep(0.2)
                order.append("holder-exit")

        def waiter():
            lock_entered.wait(timeout=5)
            with self.store._slot_lock("free", "fadefadefadefade", timeout=5):
                order.append("waiter-enter")

        threads = [threading.Thread(target=holder), threading.Thread(target=waiter)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertEqual(order, ["holder-enter", "holder-exit", "waiter-enter"])

    def test_force_rebuild_still_really_replaces_regression(self):
        """RED-proof #4: the lock rewrite must not weaken --rebuild-kroko."""
        computed = fingerprint.compute_fingerprint(variant="free")
        with TemporaryDirectory() as build_dir:
            first = self.store.store(
                wheel_path=make_wheel(Path(build_dir) / "a", variant="free", payload=b"first"),
                fingerprint=computed["fingerprint"], inputs=computed["inputs"],
                adopt_existing=False,
            )
            second = self.store.store(
                wheel_path=make_wheel(Path(build_dir) / "b", variant="free", payload=b"second"),
                fingerprint=computed["fingerprint"], inputs=computed["inputs"],
                adopt_existing=False,
            )
        self.assertNotEqual(first.wheel_sha256, second.wheel_sha256)

    def test_concurrent_store_still_avoids_corruption_regression(self):
        """RED-proof #3: the lock rewrite must not weaken concurrency safety."""
        import threading

        computed = fingerprint.compute_fingerprint(variant="free")
        with TemporaryDirectory() as build_dir:
            wheel_a = make_wheel(Path(build_dir) / "a", variant="free", payload=b"racer-a")
            wheel_b = make_wheel(Path(build_dir) / "b", variant="free", payload=b"racer-b")

            barrier = threading.Barrier(2)
            results = {}
            errors = []

            def racer(name, wheel):
                try:
                    barrier.wait(timeout=10)
                    results[name] = self.store.store(
                        wheel_path=wheel,
                        fingerprint=computed["fingerprint"],
                        inputs=computed["inputs"],
                    )
                except Exception as exc:  # noqa: BLE001 - captured for assertion
                    errors.append((name, exc))

            threads = [
                threading.Thread(target=racer, args=("a", wheel_a)),
                threading.Thread(target=racer, args=("b", wheel_b)),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=30)

        self.assertEqual(errors, [])
        self.assertEqual(results["a"].wheel_sha256, results["b"].wheel_sha256)


if __name__ == "__main__":
    unittest.main()
