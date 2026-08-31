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
    #: BUILDER_REVISION = 1.
    EXPECTED_BUILDER_SOURCE_DIGEST = (
        "cdb728918600a2605d3254c354e3defc8956fd8e7d8986e1471ace57fb43ae70"
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
    #: artifact. A change here can change the produced runtime even when the
    #: upstream revision and the patches are untouched.
    BUILDER_FUNCTION_NAMES = (
        "prepare_checkout",
        "ensure_pinned_revision",
        "prepare_windows_checkout",
        "linux_build_env",
        "build_linux_wheel",
        "build_windows_wheel",
        "build_wheel",
        "find_linux_wheel",
        "find_windows_wheel",
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


if __name__ == "__main__":
    unittest.main()
