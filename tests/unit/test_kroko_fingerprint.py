"""AP-SRV-070 W4A - the Kroko build fingerprint decides reuse, and nothing else.

The fingerprint exists so a ~30-minute native Kroko build can be skipped when
an equivalent artifact already exists. That only works if it is stable for
identical inputs *and* genuinely insensitive to everything that does not change
the produced binary - above all the VoiceSTT product version and the ordinary
server/wake/docs source that W3 established as a separate concern.

These tests pin both halves of that contract.
"""

import builtins
import contextlib
import hashlib
import inspect
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from VoiceSTT import install_kroko
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

    def test_qualified_windows_fingerprint_remains_byte_stable(self):
        computed = fingerprint.compute_fingerprint(
            variant="free",
            target_platform="windows",
            architecture="amd64",
            python_tag="cp312",
            abi_tag="cp312",
        )
        self.assertEqual(computed["fingerprint"], "28594e6d201fc4a7")

    def test_linux_revision_change_does_not_move_windows_fingerprint(self):
        before = fingerprint.compute_fingerprint(
            variant="free",
            target_platform="windows",
            architecture="amd64",
            python_tag="cp312",
            abi_tag="cp312",
        )
        with mock.patch.object(buildinputs, "LINUX_BUILDER_REVISION", 999):
            after = fingerprint.compute_fingerprint(
                variant="free",
                target_platform="windows",
                architecture="amd64",
                python_tag="cp312",
                abi_tag="cp312",
            )
        self.assertEqual(before["fingerprint"], after["fingerprint"])


class LinuxOpenSSLToolchainAuthorityTests(unittest.TestCase):
    def _root(self, parent, name, marker):
        root = Path(parent) / name
        include = root / "include" / "openssl"
        library = root / "lib"
        include.mkdir(parents=True)
        library.mkdir(parents=True)
        (include / "opensslv.h").write_text(
            '#define OPENSSL_VERSION_TEXT "OpenSSL {0}"\n'.format(marker),
            encoding="utf-8",
        )
        (include / "ssl.h").write_text("ssl-{0}\n".format(marker), encoding="utf-8")
        (library / "libssl.so").write_bytes(("ssl-" + marker).encode())
        (library / "libcrypto.so").write_bytes(("crypto-" + marker).encode())
        return root

    def test_explicit_openssl_root_and_bytes_change_linux_fingerprint(self):
        with TemporaryDirectory() as temporary:
            first_root = self._root(temporary, "first", "3.0-a")
            second_root = self._root(temporary, "second", "3.0-b")
            first = install_kroko.detect_linux_openssl_identity(
                first_root, required=True
            )
            second = install_kroko.detect_linux_openssl_identity(
                second_root, required=True
            )
            first_fp = fingerprint.compute_fingerprint(
                variant="free",
                target_platform="linux",
                architecture="amd64",
                python_tag="cp312",
                abi_tag="cp312",
                toolchain={"kind": "host-native", "opensslDevelopment": first},
            )
            second_fp = fingerprint.compute_fingerprint(
                variant="free",
                target_platform="linux",
                architecture="amd64",
                python_tag="cp312",
                abi_tag="cp312",
                toolchain={"kind": "host-native", "opensslDevelopment": second},
            )
        self.assertNotEqual(first_fp["fingerprint"], second_fp["fingerprint"])
        self.assertEqual(first["source"], "explicit-root")
        self.assertNotIn("zlib", first)

    def test_missing_explicit_openssl_development_stack_fails_early(self):
        with TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                install_kroko.KrokoInstallError,
                "libssl-dev|OPENSSL_ROOT_DIR",
            ):
                install_kroko.detect_linux_openssl_identity(
                    Path(temporary) / "missing",
                    required=True,
                )

    def test_system_and_explicit_openssl_authorities_cannot_collide(self):
        common = {
            "version": "OpenSSL 3.0",
            "headers": [{"path": "/include/opensslv.h", "sha256": "a" * 64}],
            "libraries": [{"name": "ssl", "path": "/lib/libssl.so", "sha256": "b" * 64}],
        }
        explicit = dict(common, source="explicit-root", root="/opt/project-openssl")
        system = dict(common, source="system-development-stack", root=None)
        kwargs = dict(
            variant="free",
            target_platform="linux",
            architecture="amd64",
            python_tag="cp312",
            abi_tag="cp312",
        )
        explicit_fp = fingerprint.compute_fingerprint(
            **kwargs,
            toolchain={"kind": "host-native", "opensslDevelopment": explicit},
        )
        system_fp = fingerprint.compute_fingerprint(
            **kwargs,
            toolchain={"kind": "host-native", "opensslDevelopment": system},
        )
        self.assertNotEqual(explicit_fp["fingerprint"], system_fp["fingerprint"])


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
    * platform-specific **builder surfaces** - shared checkout plus the Windows
      or Linux invocation/selection logic, tracked independently so a Linux-only
      correction cannot invalidate the qualified Windows artifact.

    Both revisions are fingerprint inputs, so bumping either correctly
    invalidates stored artifacts.
    """

    #: SHA-256 over the source of every build-affecting patch function, pinned
    #: together with PATCH_SET_REVISION = 3 (AP-SRV-070 W4A-C4, Root Finding L/M:
    #: the Windows Dockerfile patch now pins xwin channel manifest, package
    #: manifest, SDK version, and CRT version, with size and digest verification).
    EXPECTED_PATCH_SOURCE_DIGEST = (
        "70d8bacbe95c358e532db9ce1b6127d2aa575ff7724b90464a5aec71b7387c80"
    )

    EXPECTED_WINDOWS_BUILDER_SOURCE_DIGEST = (
        "58736daff6b3eff495240cdf4ec061d90991f1139bf39cdba8593d2296f7553b"
    )
    EXPECTED_LINUX_BUILDER_SOURCE_DIGEST = (
        "69bdaea499d9b2a373b39a044eba743a78c4e0b4f64cec3015f8dea08cf5ad76"
    )

    #: AP-SRV-070 W4A-C3, Root Finding J added the two functions that *declare*
    #: what the Windows Dockerfile patch emits. They are as build-effective as
    #: the patch function that applies them - they decide the base image digest,
    #: the apt snapshot, the packaging-tool pins and every download hash - so
    #: they belong to the guarded patch surface, not outside it.
    PATCH_FUNCTION_NAMES = (
        "patch_windows_bat",
        "patch_windows_dockerfile",
        "_packaging_tool_assertion",
        "_pinned_windows_dockerfile_edits",
        "_pinned_windows_openssl_block",
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
    COMMON_BUILDER_FUNCTION_NAMES = (
        "prepare_checkout",
        "checkout_origin_url",
        "normalize_repo_authority",
        "checkout_matches_repo_authority",
        "ensure_pinned_revision",
        "materialize_pristine_checkout",
        "sanitize_build_subprocess_env",
        "build_wheel",
    )
    WINDOWS_BUILDER_FUNCTION_NAMES = COMMON_BUILDER_FUNCTION_NAMES + (
        "prepare_windows_checkout",
        "windows_build_env",
        "build_windows_wheel",
        "find_windows_wheel",
    )
    LINUX_BUILDER_FUNCTION_NAMES = COMMON_BUILDER_FUNCTION_NAMES + (
        "effective_linux_openssl_root",
        "linux_build_env",
        "find_linux_wheel",
        "retag_linux_wheel",
        "build_linux_wheel",
        "detect_linux_openssl_identity",
        "detect_linux_toolchain_identity",
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

    def test_windows_builder_surface_matches_its_declared_revision(self):
        self.assertEqual(
            self._digest_of(self.WINDOWS_BUILDER_FUNCTION_NAMES),
            self.EXPECTED_WINDOWS_BUILDER_SOURCE_DIGEST,
            "The Windows Kroko builder surface changed; bump "
            "WINDOWS_BUILDER_REVISION and its guard digest.",
        )

    def test_linux_builder_surface_matches_its_declared_revision(self):
        self.assertEqual(
            self._digest_of(self.LINUX_BUILDER_FUNCTION_NAMES),
            self.EXPECTED_LINUX_BUILDER_SOURCE_DIGEST,
            "The Linux Kroko builder surface changed; bump "
            "LINUX_BUILDER_REVISION and its guard digest.",
        )

    def test_platform_builder_revisions_are_fingerprint_inputs(self):
        windows = fingerprint.build_fingerprint_document(
            variant="free", target_platform="windows"
        )
        linux = fingerprint.build_fingerprint_document(
            variant="free",
            target_platform="linux",
            toolchain={"kind": "host-native"},
        )
        self.assertEqual(
            windows["build"]["builderRevision"],
            buildinputs.WINDOWS_BUILDER_REVISION,
        )
        self.assertEqual(
            linux["build"]["builderRevision"],
            buildinputs.LINUX_BUILDER_REVISION,
        )
        self.assertIn("patchSetRevision", windows["build"])

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
            "voicestt kroko builder logic": (
                {"attr": ("LINUX_BUILDER_REVISION", 42)},
                {},
            ),
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


#: The exact sections of the pinned Kroko upstream's own Windows build sources
#: that VoiceSTT's patch functions anchor on (upstream revision
#: ``buildinputs.KROKO_UPSTREAM_REVISION``). Kept here rather than reading a
#: live builder checkout so these tests need neither network nor a warm cache,
#: and so a reader can see at a glance exactly how much of upstream the pin
#: depends on. Unrelated upstream lines are elided with a marker comment.
_UPSTREAM_DOCKERFILE_WINDOWS = """\
# Linux -> Windows cross-compile image for kroko-onnx.

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Pinned versions so reproducible across reruns. Bump deliberately.
ARG CLANG_VERSION=19
ARG XWIN_VERSION=0.6.5
ARG CMAKE_VERSION=3.30.5
ARG NSIS_VERSION=3.10

RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential \\
    curl \\
    unzip \\
    nsis \\
    python3 \\
    python3-pip \\
    python3-venv \\
 && rm -rf /var/lib/apt/lists/* \\
 && pip3 install --break-system-packages \\
        setuptools wheel delvewheel

# Modern CMake. Static binary from Kitware mirror.
RUN curl -sLo /tmp/cmake.tar.gz \\
    "https://github.com/Kitware/CMake/releases/download/v${CMAKE_VERSION}/cmake-${CMAKE_VERSION}-linux-x86_64.tar.gz" \\
 && tar -xzf /tmp/cmake.tar.gz -C /opt \\
 && ln -sf /opt/cmake-${CMAKE_VERSION}-linux-x86_64/bin/cmake /usr/local/bin/cmake \\
 && rm /tmp/cmake.tar.gz

# Microsoft SDK + CRT via xwin (prebuilt binary release).
RUN cd /tmp \\
 && curl -sLo xwin.tar.gz \\
    "https://github.com/Jake-Shadle/xwin/releases/download/${XWIN_VERSION}/xwin-${XWIN_VERSION}-x86_64-unknown-linux-musl.tar.gz" \\
 && tar -xzf xwin.tar.gz \\
 && mv xwin-${XWIN_VERSION}-x86_64-unknown-linux-musl/xwin /usr/local/bin/xwin \\
 && xwin --accept-license --arch x86_64 splat --output /opt/xwin

# Cache Microsoft's VC++ Redistributable installer.
RUN mkdir -p /opt/vc_redist \\
 && curl -sL https://aka.ms/vs/17/release/vc_redist.x64.exe \\
        -o /opt/vc_redist/vc_redist.x64.exe \\
 && ls -lh /opt/vc_redist/vc_redist.x64.exe

ENV XWIN_DIR=/opt/xwin

# Windows CPython target - headers and python3XX.lib import library.
ARG PYTHON_TARGET_VERSION=3.12.7
ARG PYTHON_TAG=312
RUN mkdir -p /opt/python-win64 \\
 && cd /tmp \\
 && curl -sLf "https://www.nuget.org/api/v2/package/python/${PYTHON_TARGET_VERSION}" \\
        -o python.nupkg \\
 && 7z x -y -o/opt/python-win64 python.nupkg >/dev/null \\
 && rm -f /tmp/python.nupkg

ENV PYTHON_WIN_TAG=cp312

# Windows-native OpenSSL - required by sherpa-onnx's CMakeLists when
# SHERPA_ONNX_ENABLE_WEBSOCKET=ON.
RUN apt-get update && apt-get install -y --no-install-recommends \\
        msitools innoextract \\
 && rm -rf /var/lib/apt/lists/* \\
 && cd /tmp \\
 && for v in 3_6_2 3_6_1 3_5_4 3_5_3; do \\
        if curl -sLf "https://slproweb.com/download/Win64OpenSSL-${v}.msi" \\
                -o openssl.msi; then \\
            echo "Downloaded Win64OpenSSL-${v}.msi"; \\
            break; \\
        fi; \\
        rm -f openssl.msi; \\
    done \\
 && test -s openssl.msi \\
 && msiextract -C /tmp/openssl-msi openssl.msi

ENV OPENSSL_ROOT_DIR=/opt/openssl-win64/app
ENV OPENSSL_LIB_DIR=/opt/openssl-win64/app/lib

WORKDIR /src

COPY in_windows_container.sh /usr/local/bin/in_windows_container.sh
RUN chmod +x /usr/local/bin/in_windows_container.sh
ENTRYPOINT ["/usr/local/bin/in_windows_container.sh"]
"""

_UPSTREAM_IN_WINDOWS_CONTAINER = """\
#!/bin/bash
set -euo pipefail

OPENFST_DIR=/tmp/openfst-prepatched
if [ ! -d "$OPENFST_DIR/src" ]; then
    echo "Pre-fetching + patching openfst (shared across installer + wheel)"
    rm -rf "$OPENFST_DIR"
    mkdir -p "$OPENFST_DIR"
    curl -sLo /tmp/openfst.tgz \\
        "https://github.com/csukuangfj/openfst/archive/refs/tags/sherpa-onnx-2024-06-19.tar.gz"
    tar -xzf /tmp/openfst.tgz -C /tmp/
fi

cmake \\
    -B "$BUILD_DIR" \\
    -DOPENSSL_CRYPTO_LIBRARY=/usr/lib/x86_64-linux-gnu/libcrypto.so.3 \\
    -DOPENSSL_SSL_LIBRARY=/usr/lib/x86_64-linux-gnu/libssl.so.3 \\
    -DSHERPA_ONNX_ENABLE_WEBSOCKET=OFF \\
    -DSHERPA_ONNX_ENABLE_TTS=OFF \\
    "$@"
"""
class RootFindingJWindowsToolchainAuthorityTests(unittest.TestCase):
    """AP-SRV-070 W4A-C3, Root Finding J - the Windows toolchain is really immutable.

    The Windows fingerprint used to describe its toolchain only as
    ``"definedBy": "upstream-revision+patch-set"``. That claimed more than the
    builder could deliver: the image pulled a floating ``ubuntu:24.04`` tag,
    resolved apt packages against the live archive, installed unpinned Python
    packaging tools, downloaded binaries with no content hash, and - worst -
    walked a list of OpenSSL versions and took whichever one a third party
    still happened to serve. The *same* fingerprint could therefore describe
    materially different compiled bytes.

    These tests prove the two halves of the correction: the declaration really
    is an immutable, hashed authority inside the fingerprint, and the emitted
    Dockerfile/container script really consume exactly that declaration.
    """

    #: One representative constant per pinned input class, so "changing this
    #: moves the fingerprint" is proven for every category rather than once.
    PINNED_CONSTANTS = (
        ("WINDOWS_BASE_IMAGE_DIGEST", "sha256:" + "0" * 64),
        ("WINDOWS_APT_SNAPSHOT_URI", "https://snapshot.ubuntu.com/ubuntu/20200101T000000Z"),
        ("WINDOWS_CLANG_VERSION", "18"),
        ("WINDOWS_CMAKE_SHA256", "1" * 64),
        ("WINDOWS_XWIN_SHA256", "2" * 64),
        ("WINDOWS_PYTHON_NUPKG_SHA256", "3" * 64),
        ("WINDOWS_VC_REDIST_SHA256", "4" * 64),
        ("WINDOWS_OPENSSL_VERSION", "3.5.8"),
        ("WINDOWS_OPENSSL_SHA256", "5" * 64),
        ("WINDOWS_OPENFST_SHA256", "6" * 64),
        ("WINDOWS_PACKAGING_TOOLS", ("setuptools==1.0.0", "wheel==0.1.0")),
    )

    def _windows_fingerprint(self):
        return fingerprint.compute_fingerprint(
            variant="free", target_platform="windows", architecture="amd64",
            python_tag="cp312", abi_tag="cp312",
        )

    def test_windows_fingerprint_names_a_concrete_immutable_authority(self):
        """RED-proof #1: not just 'defined by the upstream revision' any more."""
        toolchain = self._windows_fingerprint()["inputs"]["toolchain"]
        self.assertEqual(toolchain["kind"], "kroko-docker-windows-crossbuild")
        self.assertNotEqual(toolchain.get("definedBy"), "upstream-revision+patch-set")
        self.assertRegex(str(toolchain.get("authority", "")), r"^[0-9a-f]{16}$")

        declared = toolchain["inputs"]
        self.assertEqual(declared["baseImageDigest"], buildinputs.WINDOWS_BASE_IMAGE_DIGEST)
        self.assertTrue(declared["baseImageDigest"].startswith("sha256:"))
        self.assertEqual(declared["aptSnapshot"], buildinputs.WINDOWS_APT_SNAPSHOT_URI)
        for section in ("cmake", "xwin", "pythonTarget", "vcRedist", "openssl", "openfst"):
            with self.subTest(section=section):
                self.assertRegex(declared[section]["sha256"], r"^[0-9a-f]{64}$")
        for pin in declared["packagingTools"]:
            with self.subTest(tool=pin):
                self.assertIn("==", pin)

    def test_changing_any_pinned_input_changes_the_windows_fingerprint(self):
        """RED-proof #2: the authority is a real hashed input, not decoration."""
        baseline = self._windows_fingerprint()
        for name, replacement in self.PINNED_CONSTANTS:
            with self.subTest(constant=name):
                with mock.patch.object(buildinputs, name, replacement):
                    changed = self._windows_fingerprint()
                self.assertNotEqual(
                    changed["fingerprint"], baseline["fingerprint"],
                    f"changing {name} must invalidate stored Windows artifacts",
                )
                self.assertNotEqual(
                    changed["inputs"]["toolchain"]["authority"],
                    baseline["inputs"]["toolchain"]["authority"],
                )

    def test_generated_windows_build_has_no_availability_based_openssl_choice(self):
        """RED-proof #3: exactly one declared OpenSSL, no 'first URL that answers'."""
        dockerfile = self._patched_upstream()["Dockerfile.windows"]
        self.assertIn(buildinputs.windows_openssl_url(), dockerfile)
        self.assertNotIn("slproweb.com", dockerfile)
        openssl_section = dockerfile[dockerfile.index("# Windows-native OpenSSL"):]
        openssl_section = openssl_section[: openssl_section.index("ENV OPENSSL_ROOT_DIR=")]
        self.assertNotIn("for v in", openssl_section)
        self.assertNotIn("break", openssl_section)
        self.assertEqual(
            openssl_section.count("curl -"), 1,
            "exactly one OpenSSL download, not a list walked until one answers",
        )

    def test_generated_windows_build_verifies_openssl_against_a_declared_hash(self):
        """RED-proof #4: the OpenSSL bytes are checked before they are used."""
        dockerfile = self._patched_upstream()["Dockerfile.windows"]
        self.assertIn(
            '&& echo "{0}  /tmp/openssl.conda" | sha256sum -c -'.format(
                buildinputs.WINDOWS_OPENSSL_SHA256
            ),
            dockerfile,
        )
        # The hash check has to sit between the download and the unpack.
        download = dockerfile.index("-o /tmp/openssl.conda")
        check = dockerfile.index(buildinputs.WINDOWS_OPENSSL_SHA256)
        unpack = dockerfile.index("unzip -q /tmp/openssl.conda")
        self.assertLess(download, check)
        self.assertLess(check, unpack)

    def test_generated_windows_build_closes_the_mutable_image_inputs(self):
        """RED-proof #5: base image, apt resolution and packaging tools are pinned."""
        patched = self._patched_upstream()
        dockerfile = patched["Dockerfile.windows"]

        self.assertIn(
            "FROM {0}@{1}".format(
                buildinputs.WINDOWS_BASE_IMAGE, buildinputs.WINDOWS_BASE_IMAGE_DIGEST
            ),
            dockerfile,
        )
        self.assertNotIn("FROM ubuntu:24.04\n", dockerfile)
        self.assertIn(buildinputs.WINDOWS_APT_SNAPSHOT_URI, dockerfile)
        self.assertNotIn("pip3 install --break-system-packages \\\n        setuptools wheel", dockerfile)
        for pin in buildinputs.WINDOWS_PACKAGING_TOOLS:
            with self.subTest(tool=pin):
                self.assertIn(pin, dockerfile)
        # The pins only bite if they actually beat Ubuntu's own dpkg-managed
        # copies, which pip cannot uninstall - so the image installs alongside
        # them and then asserts what the interpreter really resolves.
        self.assertIn("--ignore-installed", dockerfile)
        for pin in buildinputs.WINDOWS_PACKAGING_TOOLS:
            name, _, version = pin.partition("==")
            with self.subTest(assertion=name):
                self.assertIn(
                    "assert m.version('{0}') == '{1}'".format(name, version), dockerfile
                )
        self.assertIn("import wheel.bdist_wheel", dockerfile)
        for sha in (
            buildinputs.WINDOWS_CMAKE_SHA256,
            buildinputs.WINDOWS_XWIN_SHA256,
            buildinputs.WINDOWS_PYTHON_NUPKG_SHA256,
            buildinputs.WINDOWS_VC_REDIST_SHA256,
        ):
            with self.subTest(sha256=sha):
                self.assertIn('echo "{0}  '.format(sha), dockerfile)
        self.assertNotIn("aka.ms/vs/17/release/vc_redist", dockerfile)

        # openfst is fetched at container run time and compiled straight in.
        container = patched["in_windows_container.sh"]
        self.assertIn(
            'echo "{0}  /tmp/openfst.tgz" | sha256sum -c -'.format(
                buildinputs.WINDOWS_OPENFST_SHA256
            ),
            container,
        )

    def test_describe_and_fingerprint_stay_offline_for_windows(self):
        """RED-proof #6: a stored artifact must never need a Docker build to be found."""
        from VoiceSTT import install_kroko

        with mock.patch.object(
            install_kroko.kroko_fingerprint, "detect_target_platform", return_value="windows"
        ), mock.patch.object(install_kroko, "run") as run_call, \
                mock.patch.object(install_kroko.subprocess, "run") as raw_run, \
                mock.patch.object(install_kroko.subprocess, "check_output") as check_output, \
                mock.patch.object(install_kroko, "prepare_checkout") as checkout:
            args = install_kroko.parse_args(["--describe-artifact", "--variant", "free"])
            computed = install_kroko.fingerprint_for(args)
            self.assertEqual(computed["inputs"]["target"]["platform"], "windows")
            self.assertEqual(
                computed["inputs"]["toolchain"]["authority"],
                fingerprint.windows_toolchain_authority(),
            )

        run_call.assert_not_called()
        raw_run.assert_not_called()
        check_output.assert_not_called()
        checkout.assert_not_called()

    def test_ordinary_voicestt_changes_still_leave_the_windows_fingerprint_alone(self):
        """RED-proof #7: pinning the toolchain must not couple it to the product."""
        from VoiceSTT import _version

        baseline = self._windows_fingerprint()["fingerprint"]
        with mock.patch.dict(
            "os.environ", {_version.BUILD_VERSION_ENV: "99.88.77"}, clear=False
        ):
            self.assertEqual(_version.resolve_version(), "99.88.77")
            bumped = self._windows_fingerprint()["fingerprint"]
        self.assertEqual(baseline, bumped)

    def test_declared_pins_are_the_only_source_of_the_generated_build(self):
        """The image cannot drift from the declaration the fingerprint hashes."""
        moved = self._patched_upstream(
            patches={"WINDOWS_OPENSSL_SHA256": "7" * 64}
        )["Dockerfile.windows"]
        self.assertIn("7" * 64, moved)
        self.assertNotIn(buildinputs.WINDOWS_OPENSSL_SHA256, moved)

    def test_a_missing_upstream_anchor_fails_loudly(self):
        """A pin that cannot be applied must never be silently skipped."""
        from VoiceSTT import install_kroko

        checkout = self._materialize_pristine()
        path = checkout / "Dockerfile.windows"
        path.write_text("FROM scratch\n", encoding="utf-8")
        with self.assertRaises(install_kroko.KrokoInstallError):
            install_kroko.patch_windows_dockerfile(checkout)

    # -- helpers -----------------------------------------------------------

    def _materialize_pristine(self):
        """Writes the pinned upstream's own Windows build sources to a temp dir.

        Read straight out of this repository's declared expectations rather
        than out of a live Kroko checkout, so the test needs no network and no
        builder cache: the fixtures below are the exact upstream sections the
        patch functions anchor on.
        """
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / "Dockerfile.windows").write_text(
            _UPSTREAM_DOCKERFILE_WINDOWS, encoding="utf-8", newline="\n"
        )
        (root / "in_windows_container.sh").write_text(
            _UPSTREAM_IN_WINDOWS_CONTAINER, encoding="utf-8", newline="\n"
        )
        return root

    def _patched_upstream(self, patches=None):
        from VoiceSTT import install_kroko

        checkout = self._materialize_pristine()
        if patches:
            with contextlib.ExitStack() as stack:
                for name, value in patches.items():
                    stack.enter_context(mock.patch.object(buildinputs, name, value))
                install_kroko.patch_windows_dockerfile(checkout)
                install_kroko.patch_windows_container_script(checkout)
        else:
            install_kroko.patch_windows_dockerfile(checkout)
            install_kroko.patch_windows_container_script(checkout)
        return {
            "Dockerfile.windows": (checkout / "Dockerfile.windows").read_text(encoding="utf-8"),
            "in_windows_container.sh": (
                checkout / "in_windows_container.sh"
            ).read_text(encoding="utf-8"),
        }


class RootFindingLMWindowsToolchainAuthorityTests(RootFindingJWindowsToolchainAuthorityTests):
    """AP-SRV-070 W4A-C4, Root Finding L/M - xwin manifests, SDK, and CRT are source-controlled.

    xwin 0.6.5 formerly resolved SDK and CRT versions implicitly from a floating
    live Microsoft channel manifest. These tests prove:
    1. The Channel Manifest, Package Manifest, SDK version, and CRT version are
       formally declared and hashed into the Windows toolchain authority;
    2. Changing any of these inputs invalidates the toolchain authority and fingerprint;
    3. The emitted Dockerfile downloads and verifies both manifests (including
       the actual uncompressed vsman package manifest SHA-256) before invoking
       xwin with explicit pinned parameters;
    4. There is no unpinned/latest fallback or duplicate unpinned splat command;
    5. Offline fingerprinting remains strictly network/docker-free;
    6. Negative proofs: incorrect manifest hashes fail verification, and a missing
       upstream xwin block raises KrokoInstallError.
    """

    def test_xwin_declaration_contains_complete_c3_reconstructed_authority(self):
        """10.1: Declaration contains exact manifests, SDK and CRT versions."""
        toolchain = self._windows_fingerprint()["inputs"]["toolchain"]["inputs"]
        xwin_decl = toolchain["xwin"]

        self.assertEqual(xwin_decl["version"], "0.6.5")
        self.assertEqual(xwin_decl["sha256"], buildinputs.WINDOWS_XWIN_SHA256)

        # Channel Manifest
        channel = xwin_decl["channelManifest"]
        self.assertEqual(channel["url"], "https://aka.ms/vs/17/release/channel")
        self.assertEqual(channel["cacheName"], "manifest_17.json")
        self.assertEqual(channel["bytes"], 91833)
        self.assertEqual(
            channel["sha256"],
            "4c81e902fb7fe2acea779b828e6dc548fe0bbb693df50eda0224263c16686bdd",
        )

        # Package Manifest
        pkg = xwin_decl["packageManifest"]
        self.assertIn("VisualStudio.vsman", pkg["url"])
        self.assertEqual(
            pkg["cacheKey"],
            "bd98dd01efa4195cb1c11030da63b9e4a3bcec7bc406799a9db80339d6dabd79",
        )
        self.assertEqual(
            pkg["cacheName"],
            "pkg_manifest_bd98dd01efa4195cb1c11030da63b9e4a3bcec7bc406799a9db80339d6dabd79.vsman",
        )
        self.assertEqual(pkg["bytes"], 17955171)
        self.assertEqual(
            pkg["sha256"],
            "3891c3018a07338b3880cbb28088bb22ef7762eb9206523655b2e3972b9d527e",
        )

        # SDK & CRT Versions
        self.assertEqual(xwin_decl["sdkVersion"], "10.0.26100")
        self.assertEqual(xwin_decl["crtVersion"], "14.44.17.14")

    def test_changing_any_manifest_or_sdk_crt_input_invalidates_fingerprint(self):
        """10.2: Invalidation proof for each individual xwin manifest, SDK, and CRT input."""
        baseline = self._windows_fingerprint()

        mutations = [
            ("WINDOWS_XWIN_MANIFEST_SHA256", "0" * 64),
            ("WINDOWS_XWIN_MANIFEST_URL", "https://aka.ms/vs/17/preview/channel"),
            ("WINDOWS_XWIN_PACKAGE_MANIFEST_SHA256", "f" * 64),
            ("WINDOWS_XWIN_PACKAGE_MANIFEST_URL", "https://example.com/vsman"),
            ("WINDOWS_XWIN_PACKAGE_MANIFEST_CACHE_KEY", "0" * 64),
            ("WINDOWS_XWIN_SDK_VERSION", "10.0.22621"),
            ("WINDOWS_XWIN_CRT_VERSION", "14.40.33807"),
        ]

        for attr, bad_value in mutations:
            with self.subTest(mutation=attr):
                with mock.patch.object(buildinputs, attr, bad_value):
                    mutated = self._windows_fingerprint()
                self.assertNotEqual(
                    mutated["fingerprint"],
                    baseline["fingerprint"],
                    f"Changing {attr} must change the fingerprint",
                )
                self.assertNotEqual(
                    mutated["inputs"]["toolchain"]["authority"],
                    baseline["inputs"]["toolchain"]["authority"],
                    f"Changing {attr} must change the toolchain authority",
                )

    def test_generated_dockerfile_downloads_and_verifies_manifests_and_invokes_pinned_xwin(self):
        """10.3: Generated Dockerfile has verified downloads and pinned splat invocation."""
        patched = self._patched_upstream()
        dockerfile = patched["Dockerfile.windows"]

        # Channel Manifest download + checks
        self.assertIn("curl -sLf \"https://aka.ms/vs/17/release/channel\"", dockerfile)
        self.assertIn("-o /tmp/.xwin-cache/dl/manifest_17.json", dockerfile)
        self.assertIn(
            'test "$(stat -c %s /tmp/.xwin-cache/dl/manifest_17.json)" = "91833"',
            dockerfile,
        )
        self.assertIn(
            'echo "4c81e902fb7fe2acea779b828e6dc548fe0bbb693df50eda0224263c16686bdd  /tmp/.xwin-cache/dl/manifest_17.json" | sha256sum -c -',
            dockerfile,
        )

        # Package Manifest download + checks
        pkg_name = "pkg_manifest_bd98dd01efa4195cb1c11030da63b9e4a3bcec7bc406799a9db80339d6dabd79.vsman"
        self.assertIn(f"-o /tmp/.xwin-cache/dl/{pkg_name}", dockerfile)
        self.assertIn(
            f'test "$(stat -c %s /tmp/.xwin-cache/dl/{pkg_name})" = "17955171"',
            dockerfile,
        )
        self.assertIn(
            f'echo "3891c3018a07338b3880cbb28088bb22ef7762eb9206523655b2e3972b9d527e  /tmp/.xwin-cache/dl/{pkg_name}" | sha256sum -c -',
            dockerfile,
        )

        # Pinned xwin splat invocation
        self.assertIn("--cache-dir /tmp/.xwin-cache", dockerfile)
        self.assertIn("--manifest /tmp/.xwin-cache/dl/manifest_17.json", dockerfile)
        self.assertIn("--sdk-version 10.0.26100", dockerfile)
        self.assertIn("--crt-version 14.44.17.14", dockerfile)
        self.assertIn("--arch x86_64", dockerfile)
        self.assertIn("splat", dockerfile)
        self.assertIn("--output /opt/xwin", dockerfile)

        # No unpinned xwin invocation or availability fallback
        self.assertNotIn("xwin --accept-license --arch x86_64 splat --output /opt/xwin", dockerfile)
        # Exactly one splat invocation
        self.assertEqual(dockerfile.count("splat"), 1)

        # Ordering check: both sha256 checks must precede the xwin invocation
        channel_check_idx = dockerfile.index(buildinputs.WINDOWS_XWIN_MANIFEST_SHA256)
        pkg_check_idx = dockerfile.index(buildinputs.WINDOWS_XWIN_PACKAGE_MANIFEST_SHA256)
        splat_idx = dockerfile.index("splat")
        self.assertLess(channel_check_idx, splat_idx)
        self.assertLess(pkg_check_idx, splat_idx)

    def test_missing_xwin_anchor_raises_kroko_install_error(self):
        """10.5 Negative proof: missing upstream anchor raises KrokoInstallError."""
        from VoiceSTT import install_kroko

        bad_dockerfile = _UPSTREAM_DOCKERFILE_WINDOWS.replace(
            "xwin --accept-license --arch x86_64 splat --output /opt/xwin",
            "broken_command_line",
        )
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / "Dockerfile.windows").write_text(bad_dockerfile, encoding="utf-8", newline="\n")

        with self.assertRaises(install_kroko.KrokoInstallError) as ctx:
            install_kroko.patch_windows_dockerfile(root)
        self.assertIn("xwin manifest authority and splat", str(ctx.exception))

    def test_manifest_sha_mismatch_would_fail_verification(self):
        """10.5 Negative proof: wrong manifest SHA would fail sha256sum verification."""
        patched = self._patched_upstream(
            patches={"WINDOWS_XWIN_MANIFEST_SHA256": "0" * 64}
        )
        dockerfile = patched["Dockerfile.windows"]
        self.assertIn(f'echo "{"0" * 64}  /tmp/.xwin-cache/dl/manifest_17.json" | sha256sum -c -', dockerfile)


if __name__ == "__main__":
    unittest.main()
