"""AP-SRV-070 W4A - the Kroko build fingerprint decides reuse, and nothing else.

The fingerprint exists so a ~30-minute native Kroko build can be skipped when
an equivalent artifact already exists. That only works if it is stable for
identical inputs *and* genuinely insensitive to everything that does not change
the produced binary - above all the VoiceSTT product version and the ordinary
server/wake/docs source that W3 established as a separate concern.

These tests pin both halves of that contract.
"""

import builtins
import hashlib
import inspect
import unittest
from unittest import mock

from VoiceSTT.kroko import buildinputs, fingerprint


class FingerprintStabilityTests(unittest.TestCase):
    """W4A-09.1 - identical inputs must always produce the same fingerprint."""

    def test_repeated_computation_is_stable(self):
        first = fingerprint.compute_fingerprint(variant="free")
        second = fingerprint.compute_fingerprint(variant="free")
        self.assertEqual(first["fingerprint"], second["fingerprint"])
        self.assertEqual(first["canonical"], second["canonical"])

    def test_canonical_serialization_is_key_order_independent(self):
        document = fingerprint.build_fingerprint_document(
            variant="free", target_platform="linux", architecture="amd64",
            python_tag="cp312", abi_tag="cp312", toolchain={"kind": "host-native"},
        )
        reordered = dict(reversed(list(document.items())))
        self.assertEqual(
            fingerprint.canonical_json(document),
            fingerprint.canonical_json(reordered),
        )
        self.assertEqual(
            fingerprint.fingerprint_id(document),
            fingerprint.fingerprint_id(reordered),
        )

    def test_fingerprint_id_is_a_short_stable_hex_id(self):
        value = fingerprint.fingerprint_id(
            fingerprint.build_fingerprint_document(variant="free")
        )
        self.assertEqual(len(value), fingerprint.FINGERPRINT_ID_LENGTH)
        int(value, 16)  # raises if it is not hex


class FingerprintIndependenceTests(unittest.TestCase):
    """W4A-09.2/09.3 - unrelated VoiceSTT changes must not invalidate Kroko."""

    def test_computing_a_fingerprint_reads_no_source_file(self):
        """The strongest form of "server code is not a build input".

        If the fingerprint never opens a file, then no amount of editing the
        FastAPI server, the wake-word code, the docs or the README can possibly
        change it.
        """
        real_open = builtins.open
        opened = []

        def tracking_open(file, *args, **kwargs):
            opened.append(str(file))
            return real_open(file, *args, **kwargs)

        with mock.patch.object(builtins, "open", tracking_open):
            fingerprint.compute_fingerprint(variant="free")

        self.assertEqual(opened, [], f"fingerprint unexpectedly read files: {opened}")

    def test_product_version_is_not_part_of_the_fingerprint(self):
        """W3's VERSION authority must never force a native recompilation."""
        from VoiceSTT import _version

        baseline = fingerprint.compute_fingerprint(variant="free")

        with mock.patch.dict(
            "os.environ", {_version.BUILD_VERSION_ENV: "99.98.97"}, clear=False
        ):
            self.assertEqual(_version.resolve_version(), "99.98.97")
            bumped = fingerprint.compute_fingerprint(variant="free")

        self.assertEqual(baseline["fingerprint"], bumped["fingerprint"])
        self.assertNotIn("99.98.97", baseline["canonical"])

    def test_fingerprint_document_declares_only_build_relevant_keys(self):
        document = fingerprint.build_fingerprint_document(variant="free")
        self.assertEqual(
            set(document),
            {"schemaVersion", "upstream", "variant", "target", "python", "build", "toolchain"},
        )


class FingerprintSensitivityTests(unittest.TestCase):
    """W4A-09.4/09.5/09.6 - real build inputs must change the fingerprint."""

    def _fingerprint(self, **kwargs):
        defaults = dict(
            variant="free",
            target_platform="linux",
            architecture="amd64",
            python_tag="cp312",
            abi_tag="cp312",
            toolchain={"kind": "host-native"},
        )
        defaults.update(kwargs)
        return fingerprint.compute_fingerprint(**defaults)["fingerprint"]

    def test_upstream_revision_changes_the_fingerprint(self):
        baseline = self._fingerprint()
        with mock.patch.object(
            buildinputs, "KROKO_UPSTREAM_REVISION", "0" * 40
        ):
            changed = self._fingerprint()
        self.assertNotEqual(baseline, changed)

    def test_variant_changes_the_fingerprint(self):
        self.assertNotEqual(self._fingerprint(variant="free"), self._fingerprint(variant="pro"))

    def test_platform_changes_the_fingerprint(self):
        self.assertNotEqual(
            self._fingerprint(target_platform="linux"),
            self._fingerprint(target_platform="windows"),
        )

    def test_architecture_changes_the_fingerprint(self):
        self.assertNotEqual(
            self._fingerprint(architecture="amd64"),
            self._fingerprint(architecture="arm64"),
        )

    def test_python_abi_changes_the_fingerprint(self):
        self.assertNotEqual(
            self._fingerprint(python_tag="cp312", abi_tag="cp312"),
            self._fingerprint(python_tag="cp311", abi_tag="cp311"),
        )

    def test_toolchain_identity_changes_the_fingerprint(self):
        self.assertNotEqual(
            self._fingerprint(toolchain={"kind": "host-native", "cmake": "3.28"}),
            self._fingerprint(toolchain={"kind": "host-native", "cmake": "3.31"}),
        )

    def test_patch_set_revision_changes_the_fingerprint(self):
        baseline = self._fingerprint()
        with mock.patch.object(buildinputs, "PATCH_SET_REVISION", 999):
            changed = self._fingerprint()
        self.assertNotEqual(baseline, changed)

    def test_linux_cmake_flags_change_the_fingerprint(self):
        baseline = self._fingerprint(target_platform="linux")
        with mock.patch.object(
            buildinputs, "LINUX_CMAKE_FLAGS", "-DSHERPA_ONNX_ENABLE_GPU=ON"
        ):
            changed = self._fingerprint(target_platform="linux")
        self.assertNotEqual(baseline, changed)


class VariantValidationTests(unittest.TestCase):
    def test_unknown_variant_is_refused(self):
        with self.assertRaises(ValueError):
            fingerprint.build_fingerprint_document(variant="enterprise")

    def test_variant_normalization_is_case_insensitive(self):
        self.assertEqual(buildinputs.normalize_variant("FREE"), "free")
        self.assertEqual(buildinputs.normalize_variant(" Pro "), "pro")


class UpstreamPinTests(unittest.TestCase):
    """W4A-02 - the upstream must be pinned to an immutable revision."""

    def test_pinned_revision_is_a_full_commit_sha(self):
        revision = buildinputs.KROKO_UPSTREAM_REVISION
        self.assertEqual(len(revision), 40, "pin must be a full 40-char commit sha")
        int(revision, 16)

    def test_pin_is_not_a_branch_name(self):
        self.assertNotEqual(
            buildinputs.KROKO_UPSTREAM_REVISION,
            buildinputs.KROKO_UPSTREAM_BRANCH_HINT,
        )

    def test_builder_defaults_to_the_pinned_revision(self):
        from VoiceSTT import install_kroko

        self.assertEqual(
            install_kroko.DEFAULT_REVISION, buildinputs.KROKO_UPSTREAM_REVISION
        )
        args = install_kroko.parse_args(["--build"])
        self.assertEqual(args.revision, buildinputs.KROKO_UPSTREAM_REVISION)


class BuildEffectiveLogicGuardTests(unittest.TestCase):
    """VoiceSTT's own build-effective logic may not drift out of the fingerprint.

    The fingerprint deliberately hashes *declared values* instead of source
    files, so that editing the FastAPI server or a docstring cannot invalidate a
    30-minute native build. That design has one danger, and this class exists to
    remove it: if VoiceSTT's own build-effective code changed without bumping a
    declared revision, the fingerprint would stay the same and a stale artifact
    would be reused for a build that now produces different bytes.

    Two surfaces are guarded, each tied to its own declared revision:

    * the **patch surface** - what VoiceSTT rewrites in the upstream sources
      (WebSocket on, OpenSSL provisioning, native license logging), tracked by
      :data:`PATCH_SET_REVISION`;
    * the **builder surface** - which revision is checked out, which patches are
      applied, how the compiler is invoked and which produced wheel is taken,
      tracked by :data:`BUILDER_REVISION`.

    Both revisions are fingerprint inputs, so bumping either correctly
    invalidates stored artifacts.
    """

    #: SHA-256 over the source of every build-affecting patch function, pinned
    #: together with PATCH_SET_REVISION = 1.
    EXPECTED_PATCH_SOURCE_DIGEST = (
        "0d716f365d720da08fac14ec519aed151ea023314f27047344bdccbe567eee9c"
    )

    #: SHA-256 over the source of the builder surface, pinned together with
    #: BUILDER_REVISION = 3 (AP-SRV-070 W4A-C2: materialize_pristine_checkout
    #: was added, prepare_checkout now calls it, and linux_build_env's own
    #: body changed again - see buildinputs.BUILDER_REVISION).
    EXPECTED_BUILDER_SOURCE_DIGEST = (
        "5d4baea1924953743a3c8c9ee083383905f0fc4372f1d47e872f5d44703ada93"
    )

    PATCH_FUNCTION_NAMES = (
        "patch_windows_bat",
        "patch_windows_dockerfile",
        "patch_windows_container_script",
        "patch_license_quiet_env",
        "_wrap_license_output_line",
        "_insert_after_line",
    )

    #: Everything that decides *what* is built and *which* wheel becomes the
    #: artifact, plus - as of W4A-C1 - everything that decides what feeds the
    #: cache key (fingerprint_for) and what a native build subprocess's
    #: environment may contain (sanitize_build_subprocess_env,
    #: windows_build_env). A change to any of these can silently make an
    #: existing fingerprint describe a different real build - either a
    #: different produced runtime, a different effective source, or a leaked
    #: secret - without a source-controlled revision constant, none of this
    #: would be caught by "the fingerprint changes when a build input changes",
    #: because these functions are exactly what decides which values the
    #: fingerprint sees or what a subprocess may read.
    BUILDER_FUNCTION_NAMES = (
        "prepare_checkout",
        "ensure_pinned_revision",
        "materialize_pristine_checkout",
        "prepare_windows_checkout",
        "linux_build_env",
        "windows_build_env",
        "sanitize_build_subprocess_env",
        "build_linux_wheel",
        "build_windows_wheel",
        "build_wheel",
        "find_linux_wheel",
        "find_windows_wheel",
        "fingerprint_for",
    )

    def _digest_of(self, names):
        from VoiceSTT import install_kroko

        digest = hashlib.sha256()
        for name in names:
            function = getattr(install_kroko, name)
            digest.update(name.encode("utf-8"))
            digest.update(inspect.getsource(function).encode("utf-8"))
        return digest.hexdigest()

    def test_patch_set_matches_its_declared_revision(self):
        self.assertEqual(
            self._digest_of(self.PATCH_FUNCTION_NAMES),
            self.EXPECTED_PATCH_SOURCE_DIGEST,
            "The Kroko patch set changed. Those patches alter the compiled "
            "binary, so bump PATCH_SET_REVISION in VoiceSTT/kroko/buildinputs.py "
            "(which invalidates stored artifacts) and update "
            "EXPECTED_PATCH_SOURCE_DIGEST here.",
        )

    def test_builder_surface_matches_its_declared_revision(self):
        self.assertEqual(
            self._digest_of(self.BUILDER_FUNCTION_NAMES),
            self.EXPECTED_BUILDER_SOURCE_DIGEST,
            "The Kroko builder surface changed - checkout, patch application, "
            "build invocation or wheel selection. That can change the produced "
            "runtime, so bump BUILDER_REVISION in VoiceSTT/kroko/buildinputs.py "
            "(which invalidates stored artifacts) and update "
            "EXPECTED_BUILDER_SOURCE_DIGEST here.",
        )

    def test_both_declared_revisions_are_fingerprint_inputs(self):
        """Bumping either revision must really invalidate stored artifacts."""
        document = fingerprint.build_fingerprint_document(variant="free")
        self.assertIn("patchSetRevision", document["build"])
        self.assertIn("builderRevision", document["build"])

    def test_declared_patched_sources_are_documented(self):
        self.assertIn("sherpa-onnx/csrc/license.h", buildinputs.PATCHED_UPSTREAM_SOURCES)
        self.assertIn("build_windows.bat", buildinputs.PATCHED_UPSTREAM_SOURCES)


class BuildInputCoverageTests(unittest.TestCase):
    """One consolidated proof over every build-effective input at once.

    Requested as a root check: the fingerprint reading no source files must not
    quietly mean that VoiceSTT-specific Kroko build inputs fall *out* of it.
    Each entry below mutates exactly one genuinely build-effective input and
    asserts the fingerprint moves; the counter-proof asserts that ordinary
    VoiceSTT and product-version changes leave it identical.
    """

    def _fingerprint(self, **kwargs):
        defaults = dict(
            variant="free",
            target_platform="linux",
            architecture="amd64",
            python_tag="cp312",
            abi_tag="cp312",
            toolchain={"kind": "host-native", "cmake": "3.28"},
        )
        defaults.update(kwargs)
        return fingerprint.compute_fingerprint(**defaults)["fingerprint"]

    def test_every_build_effective_input_changes_the_fingerprint(self):
        baseline = self._fingerprint()

        cases = {
            "kroko upstream revision": (
                {"attr": ("KROKO_UPSTREAM_REVISION", "0" * 40)}, {}
            ),
            "kroko upstream repo": (
                {"attr": ("KROKO_UPSTREAM_REPO", "https://example.invalid/fork.git")}, {}
            ),
            "free|pro variant": ({}, {"variant": "pro"}),
            "target platform": ({}, {"target_platform": "windows"}),
            "architecture": ({}, {"architecture": "arm64"}),
            "python tag": ({}, {"python_tag": "cp311", "abi_tag": "cp311"}),
            "python abi only": ({}, {"abi_tag": "cp312d"}),
            "cmake flags": (
                {"attr": ("LINUX_CMAKE_FLAGS", "-DSHERPA_ONNX_ENABLE_GPU=ON")}, {}
            ),
            "make args": ({"attr": ("LINUX_MAKE_ARGS", "-j99")}, {}),
            "compiler/toolchain identity": (
                {}, {"toolchain": {"kind": "host-native", "cmake": "3.31"}}
            ),
            "voicestt kroko patch set": ({"attr": ("PATCH_SET_REVISION", 42)}, {}),
            "voicestt kroko builder logic": ({"attr": ("BUILDER_REVISION", 42)}, {}),
            "fingerprint schema": (
                {"schema": 99}, {}
            ),
        }

        for label, (patches, kwargs) in cases.items():
            with self.subTest(build_input=label):
                if "attr" in patches:
                    name, value = patches["attr"]
                    with mock.patch.object(buildinputs, name, value):
                        changed = self._fingerprint(**kwargs)
                elif "schema" in patches:
                    with mock.patch.object(
                        fingerprint, "FINGERPRINT_SCHEMA_VERSION", patches["schema"]
                    ):
                        changed = self._fingerprint(**kwargs)
                else:
                    changed = self._fingerprint(**kwargs)
                self.assertNotEqual(
                    baseline, changed,
                    f"changing {label!r} must change the Kroko fingerprint",
                )

    def test_ordinary_voicestt_changes_leave_the_fingerprint_identical(self):
        """The counter-proof: non-build-effective changes must not invalidate."""
        from VoiceSTT import _version

        baseline = self._fingerprint()

        # A product version bump (W3 authority) - the case W4A-10 calls out.
        with mock.patch.dict(
            "os.environ", {_version.BUILD_VERSION_ENV: "77.66.55"}, clear=False
        ):
            self.assertEqual(_version.resolve_version(), "77.66.55")
            self.assertEqual(baseline, self._fingerprint())

        # Server, wake-word, docs and README source cannot participate at all,
        # because computing a fingerprint opens no file whatsoever.
        real_open = builtins.open
        opened = []

        def tracking_open(file, *args, **kwargs):
            opened.append(str(file))
            return real_open(file, *args, **kwargs)

        with mock.patch.object(builtins, "open", tracking_open):
            self.assertEqual(baseline, self._fingerprint())
        self.assertEqual(opened, [])


class RootFindingASourceOverrideTests(unittest.TestCase):
    """AP-SRV-070 W4A-C1, Root Finding A - source overrides must feed the fingerprint.

    ``prepare_checkout()`` genuinely uses ``--repo``/``--revision`` for the
    real clone and checkout. Before this correction, ``fingerprint_for(args)``
    ignored both and always hashed the static pin, so two builds from
    different sources could collide on the same cache key.
    """

    def test_default_and_different_revision_never_share_a_fingerprint(self):
        from VoiceSTT import install_kroko

        default_fp = install_kroko.fingerprint_for(
            install_kroko.parse_args(["--build"])
        )["fingerprint"]
        override_fp = install_kroko.fingerprint_for(
            install_kroko.parse_args(["--build", "--revision", "f" * 40])
        )["fingerprint"]
        self.assertNotEqual(default_fp, override_fp)

    def test_default_and_different_repo_never_share_a_fingerprint(self):
        from VoiceSTT import install_kroko

        default_fp = install_kroko.fingerprint_for(
            install_kroko.parse_args(["--build"])
        )["fingerprint"]
        override_fp = install_kroko.fingerprint_for(
            install_kroko.parse_args(
                ["--build", "--repo", "https://example.invalid/kroko-fork.git"]
            )
        )["fingerprint"]
        self.assertNotEqual(default_fp, override_fp)

    def test_default_invocation_resolves_to_the_static_pin(self):
        """Passing the CLI defaults through must not itself change anything."""
        from VoiceSTT import install_kroko

        computed = install_kroko.fingerprint_for(install_kroko.parse_args(["--build"]))
        self.assertEqual(
            computed["inputs"]["upstream"]["revision"], buildinputs.KROKO_UPSTREAM_REVISION
        )
        self.assertEqual(
            computed["inputs"]["upstream"]["repo"], buildinputs.KROKO_UPSTREAM_REPO
        )

    def test_describe_artifact_and_fingerprint_for_agree_on_the_effective_source(self):
        """describe-artifact, cache-lookup and the real build must agree."""
        from VoiceSTT import install_kroko

        args = install_kroko.parse_args(
            ["--build", "--revision", "e" * 40, "--repo", "https://example.invalid/x.git"]
        )
        computed = install_kroko.fingerprint_for(args)
        described = install_kroko.describe_artifact(args)

        self.assertEqual(described["fingerprint"], computed["fingerprint"])
        self.assertEqual(described["inputs"]["upstream"]["revision"], "e" * 40)
        self.assertEqual(
            described["inputs"]["upstream"]["repo"], "https://example.invalid/x.git"
        )

    def test_prepare_checkout_uses_the_same_revision_the_fingerprint_hashes(self):
        """The revision fingerprint_for hashes is the one actually checked out."""
        import tempfile
        from pathlib import Path

        from VoiceSTT import install_kroko

        args = install_kroko.parse_args(["--build", "--revision", "d" * 40])
        computed = install_kroko.fingerprint_for(args)
        self.assertEqual(computed["inputs"]["upstream"]["revision"], "d" * 40)

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(install_kroko, "run"), mock.patch.object(
                install_kroko, "ensure_pinned_revision"
            ) as ensure_pinned:
                install_kroko.prepare_checkout(args, work_dir=Path(tmp))

        ensure_pinned.assert_called_once()
        call_args, call_kwargs = ensure_pinned.call_args
        used_revision = call_args[1] if len(call_args) > 1 else call_kwargs.get("revision")
        self.assertEqual(used_revision, "d" * 40)


class RootFindingBLinuxToolchainFingerprintTests(unittest.TestCase):
    """AP-SRV-070 W4A-C1, Root Finding B - the Linux toolchain identity is declared.

    ``toolchain_identity("linux")`` collapses to the generic
    ``{"kind": "host-native"}`` by design (see its docstring) so
    ``compute_fingerprint()`` stays pure by default; it is
    ``install_kroko.fingerprint_for()`` - the real production entry point -
    that must supply the concrete, probed identity for a real Linux build.
    """

    def test_linux_fingerprint_uses_a_probed_toolchain_not_the_generic_placeholder(self):
        from VoiceSTT import install_kroko

        args = install_kroko.parse_args(["--build"])
        probed = {"kind": "host-native", "cmakeVersion": "cmake 3.28.0", "compilerVersion": "gcc 12"}
        with mock.patch.object(
            install_kroko.kroko_fingerprint, "detect_target_platform", return_value="linux"
        ), mock.patch.object(
            install_kroko, "detect_linux_toolchain_identity", return_value=probed
        ):
            computed = install_kroko.fingerprint_for(args)

        self.assertEqual(computed["inputs"]["toolchain"], probed)
        self.assertNotEqual(computed["inputs"]["toolchain"], {"kind": "host-native"})

    def test_different_cmake_version_changes_the_linux_fingerprint(self):
        from VoiceSTT import install_kroko

        args = install_kroko.parse_args(["--build"])

        def fp_with(cmake_version):
            with mock.patch.object(
                install_kroko.kroko_fingerprint, "detect_target_platform", return_value="linux"
            ), mock.patch.object(
                install_kroko, "detect_linux_toolchain_identity",
                return_value={"kind": "host-native", "cmakeVersion": cmake_version, "compilerVersion": "gcc 12"},
            ):
                return install_kroko.fingerprint_for(args)["fingerprint"]

        self.assertNotEqual(fp_with("cmake 3.28.0"), fp_with("cmake 3.31.0"))

    def test_different_compiler_version_changes_the_linux_fingerprint(self):
        from VoiceSTT import install_kroko

        args = install_kroko.parse_args(["--build"])

        def fp_with(compiler_version):
            with mock.patch.object(
                install_kroko.kroko_fingerprint, "detect_target_platform", return_value="linux"
            ), mock.patch.object(
                install_kroko, "detect_linux_toolchain_identity",
                return_value={"kind": "host-native", "cmakeVersion": "cmake 3.28", "compilerVersion": compiler_version},
            ):
                return install_kroko.fingerprint_for(args)["fingerprint"]

        self.assertNotEqual(fp_with("gcc 11.4"), fp_with("gcc 13.2"))

    def test_windows_fingerprint_never_probes_the_host_toolchain(self):
        """The Windows crossbuild identity stays host-independent (unchanged)."""
        from VoiceSTT import install_kroko

        args = install_kroko.parse_args(["--build"])
        with mock.patch.object(
            install_kroko.kroko_fingerprint, "detect_target_platform", return_value="windows"
        ), mock.patch.object(install_kroko, "detect_linux_toolchain_identity") as probe:
            install_kroko.fingerprint_for(args)
        probe.assert_not_called()

    def test_ordinary_voicestt_change_still_does_not_move_a_linux_fingerprint(self):
        """The counter-proof, specifically for the now-probed Linux path."""
        from VoiceSTT import _version, install_kroko

        args = install_kroko.parse_args(["--build"])
        probed = {"kind": "host-native", "cmakeVersion": "cmake 3.28", "compilerVersion": "gcc 12"}
        with mock.patch.object(
            install_kroko.kroko_fingerprint, "detect_target_platform", return_value="linux"
        ), mock.patch.object(
            install_kroko, "detect_linux_toolchain_identity", return_value=probed
        ):
            baseline = install_kroko.fingerprint_for(args)["fingerprint"]
            with mock.patch.dict(
                "os.environ", {_version.BUILD_VERSION_ENV: "55.44.33"}, clear=False
            ):
                self.assertEqual(_version.resolve_version(), "55.44.33")
                bumped = install_kroko.fingerprint_for(args)["fingerprint"]
        self.assertEqual(baseline, bumped)

    def test_detect_linux_toolchain_identity_probes_real_tools(self):
        from VoiceSTT import install_kroko

        def fake_which(name):
            return {"cmake": "/usr/bin/cmake", "cc": "/usr/bin/cc"}.get(name)

        class FakeCompleted:
            def __init__(self, stdout):
                self.stdout = stdout
                self.stderr = ""

        def fake_run(cmd, **kwargs):
            return FakeCompleted(f"{cmd[0]} version 1.2.3\n")

        with mock.patch("shutil.which", side_effect=fake_which), mock.patch(
            "subprocess.run", side_effect=fake_run
        ):
            identity = install_kroko.detect_linux_toolchain_identity()

        self.assertEqual(identity["cmakePath"], "/usr/bin/cmake")
        self.assertIn("1.2.3", identity["cmakeVersion"])
        self.assertEqual(identity["compilerPath"], "/usr/bin/cc")
        self.assertIn("1.2.3", identity["compilerVersion"])

    def test_detect_linux_toolchain_identity_tolerates_a_missing_tool(self):
        from VoiceSTT import install_kroko

        with mock.patch("shutil.which", return_value=None):
            identity = install_kroko.detect_linux_toolchain_identity()

        self.assertIsNone(identity["cmakePath"])
        self.assertIsNone(identity["cmakeVersion"])
        self.assertIsNone(identity["compilerPath"])
        self.assertIsNone(identity["compilerVersion"])


class RootFindingGCxxToolchainTests(unittest.TestCase):
    """AP-SRV-070 W4A-C2, Root Finding G.1 - the C++ compiler is a real build input.

    Kroko builds a native C++ extension, not a plain C one. C1 only probed
    the C compiler; since CXX is deliberately stripped from the ambient
    environment (Root Finding B), CMake picks its own default C++ compiler,
    and that compiler is exactly as build-effective as the C one C1 already
    tracked.
    """

    def test_identity_declares_a_separate_cxx_compiler_field(self):
        from VoiceSTT import install_kroko

        def fake_which(name):
            return {"cmake": "/usr/bin/cmake", "cc": "/usr/bin/cc", "c++": "/usr/bin/c++"}.get(name)

        class FakeCompleted:
            def __init__(self, stdout):
                self.stdout = stdout
                self.stderr = ""

        def fake_run(cmd, **kwargs):
            return FakeCompleted(f"{cmd[0]} version 9.9.9\n")

        with mock.patch("shutil.which", side_effect=fake_which), mock.patch(
            "subprocess.run", side_effect=fake_run
        ):
            identity = install_kroko.detect_linux_toolchain_identity()

        self.assertEqual(identity["cxxCompilerPath"], "/usr/bin/c++")
        self.assertIn("9.9.9", identity["cxxCompilerVersion"])

    def test_c_and_cxx_compilers_are_not_collapsed_into_one_identity(self):
        """The two must be genuinely independent fields, not aliases of one probe."""
        from VoiceSTT import install_kroko

        def fake_which(name):
            return {"cmake": "/usr/bin/cmake", "cc": "/usr/bin/cc", "c++": "/usr/bin/c++"}.get(name)

        def fake_run(cmd, **kwargs):
            executable = cmd[0]
            version = "11.1" if executable == "/usr/bin/cc" else "12.2"
            return type("R", (), {"stdout": f"{executable} version {version}\n", "stderr": ""})()

        with mock.patch("shutil.which", side_effect=fake_which), mock.patch(
            "subprocess.run", side_effect=fake_run
        ):
            identity = install_kroko.detect_linux_toolchain_identity()

        self.assertIn("11.1", identity["compilerVersion"])
        self.assertIn("12.2", identity["cxxCompilerVersion"])
        self.assertNotEqual(identity["compilerVersion"], identity["cxxCompilerVersion"])
        self.assertNotEqual(identity["compilerPath"], identity["cxxCompilerPath"])

    def test_different_cxx_compiler_version_changes_the_linux_fingerprint(self):
        from VoiceSTT import install_kroko

        args = install_kroko.parse_args(["--build"])

        def fp_with(cxx_version):
            identity = {
                "kind": "host-native", "cmakeVersion": "cmake 3.28",
                "compilerVersion": "gcc 12", "cxxCompilerVersion": cxx_version,
            }
            with mock.patch.object(
                install_kroko.kroko_fingerprint, "detect_target_platform", return_value="linux"
            ), mock.patch.object(
                install_kroko, "detect_linux_toolchain_identity", return_value=identity
            ):
                return install_kroko.fingerprint_for(args)["fingerprint"]

        self.assertNotEqual(fp_with("g++ 11.4"), fp_with("g++ 13.2"))

    def test_ambient_cxx_override_does_not_survive_into_the_build_environment(self):
        """RED-proof #3: a host-set CXX must not become build-effective."""
        from VoiceSTT import install_kroko

        with mock.patch.dict(
            "os.environ", {"CXX": "/tmp/evil-cxx-wrapper"}, clear=False
        ):
            env = install_kroko.linux_build_env("free")
        self.assertNotIn("CXX", env)

    def test_ordinary_voicestt_change_still_does_not_move_a_linux_fingerprint_with_cxx(self):
        """The counter-proof, now with the C++ compiler field present too."""
        from VoiceSTT import _version, install_kroko

        args = install_kroko.parse_args(["--build"])
        identity = {
            "kind": "host-native", "cmakeVersion": "cmake 3.28",
            "compilerVersion": "gcc 12", "cxxCompilerVersion": "g++ 12",
        }
        with mock.patch.object(
            install_kroko.kroko_fingerprint, "detect_target_platform", return_value="linux"
        ), mock.patch.object(
            install_kroko, "detect_linux_toolchain_identity", return_value=identity
        ):
            baseline = install_kroko.fingerprint_for(args)["fingerprint"]
            with mock.patch.dict(
                "os.environ", {_version.BUILD_VERSION_ENV: "44.33.22"}, clear=False
            ):
                self.assertEqual(_version.resolve_version(), "44.33.22")
                bumped = install_kroko.fingerprint_for(args)["fingerprint"]
        self.assertEqual(baseline, bumped)


class RootFindingGPreInstalledOnnxRuntimeTests(unittest.TestCase):
    """AP-SRV-070 W4A-C2, Root Finding G.2 - opportunistic pre-installed ONNX Runtime disabled."""

    def test_declared_linux_cmake_flags_disable_the_pre_installed_onnxruntime_default(self):
        self.assertIn(
            "-DSHERPA_ONNX_USE_PRE_INSTALLED_ONNXRUNTIME_IF_AVAILABLE=OFF",
            buildinputs.LINUX_CMAKE_FLAGS,
        )

    def test_changing_the_declared_flags_changes_the_linux_fingerprint(self):
        """Confirms the flag change is a real, hashed fingerprint input."""
        baseline = fingerprint.compute_fingerprint(
            variant="free", target_platform="linux", architecture="amd64",
            python_tag="cp312", abi_tag="cp312", toolchain={"kind": "host-native"},
        )["fingerprint"]
        with mock.patch.object(
            buildinputs, "LINUX_CMAKE_FLAGS",
            buildinputs.LINUX_CMAKE_FLAGS.replace(
                "-DSHERPA_ONNX_USE_PRE_INSTALLED_ONNXRUNTIME_IF_AVAILABLE=OFF", ""
            ).strip(),
        ):
            changed = fingerprint.compute_fingerprint(
                variant="free", target_platform="linux", architecture="amd64",
                python_tag="cp312", abi_tag="cp312", toolchain={"kind": "host-native"},
            )["fingerprint"]
        self.assertNotEqual(baseline, changed)


if __name__ == "__main__":
    unittest.main()
