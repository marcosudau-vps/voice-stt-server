"""The two complete public distributions (AP-SRV-070 W5-R04).

``tools/build_distribution.py`` merges a qualified Kroko native runtime into
the VoiceSTT wheel, producing a distribution that installs complete with no
local native build. These tests cover that merge with synthetic wheels, so they
are fast, offline, and do not need a 30-minute Kroko compile.

Gates touched: W5R4-G13 (Free and Pro identities never cross), G16 (the
candidate binds the embedded artifact), and the new authority's sections 1-3
(two distributions, one import name, no separate public Kroko distribution).
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for candidate in (REPO_ROOT, REPO_ROOT / "tools"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import build_distribution as bd  # noqa: E402

KROKO_SHA_PLACEHOLDER = "0" * 64


def make_base_wheel(directory: Path, distribution: str = "voice-stt-server") -> Path:
    """A synthetic pure-Python VoiceSTT wheel, shaped like the real one."""
    escaped = bd.escaped_name(distribution)
    path = directory / f"{escaped}-2.0.0-py3-none-any.whl"
    dist_info = f"{escaped}-2.0.0.dist-info"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("voice_stt_server/__init__.py", "VERSION = '2.0.0'\n")
        archive.writestr("VoiceSTT/__init__.py", "# implementation lives here\n")
        archive.writestr("VoiceSTT_server/server.py", "def main():\n    pass\n")
        archive.writestr(
            f"{dist_info}/METADATA",
            f"Metadata-Version: 2.1\nName: {distribution}\nVersion: 2.0.0\n",
        )
        archive.writestr(
            f"{dist_info}/WHEEL",
            "Wheel-Version: 1.0\nGenerator: setuptools\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        )
        archive.writestr(f"{dist_info}/RECORD", "")
    return path


def make_kroko_wheel(directory: Path, variant: str = "free",
                     platform: str = "linux_x86_64") -> Path:
    """A synthetic Kroko wheel with the real one's payload shape."""
    path = directory / f"kroko_onnx-1.12.9-1{variant}-cp312-cp312-{platform}.whl"
    dist_info = "kroko_onnx-1.12.9.dist-info"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("kroko_onnx/__init__.py", f"VARIANT = '{variant}'\n")
        archive.writestr("sherpa_onnx/__init__.py", "# bindings\n")
        archive.writestr("sherpa_onnx/lib/libsherpa.so", b"\x7fELF" + variant.encode())
        archive.writestr("_sherpa_onnx.cpython-312-x86_64-linux-gnu.so", b"\x7fELFnative")
        archive.writestr(f"{dist_info}/METADATA", "Metadata-Version: 2.1\nName: kroko-onnx\nVersion: 1.12.9\n")
        archive.writestr(f"{dist_info}/WHEEL", f"Wheel-Version: 1.0\nBuild: 1{variant}\n")
        archive.writestr(f"{dist_info}/licenses/LICENSE", "Kroko licence text\n")
        archive.writestr(f"{dist_info}/RECORD", "")
    return path


class NamingTests(unittest.TestCase):
    def test_the_two_variants_map_to_the_two_public_distributions(self):
        self.assertEqual(bd.distribution_name_for("free"), "voice-stt-server")
        self.assertEqual(bd.distribution_name_for("pro"), "voice-stt-server-pro")

    def test_the_mapping_matches_setup_py(self):
        # One authority, not two: a drifting name would publish the Pro
        # runtime under the Free project.
        source = (REPO_ROOT / "setup.py").read_text(encoding="utf-8")
        self.assertIn('"free": "voice-stt-server"', source)
        self.assertIn('"pro": "voice-stt-server-pro"', source)

    def test_an_unknown_variant_is_refused(self):
        for value in ("", "community", "FREE-ish", None):
            with self.subTest(value=value):
                with self.assertRaises(bd.DistributionBuildError):
                    bd.distribution_name_for(value)

    def test_variant_names_are_case_insensitive(self):
        self.assertEqual(bd.distribution_name_for(" PRO "), "voice-stt-server-pro")

    def test_wheel_filenames_are_parsed_into_their_tags(self):
        parsed = bd.parse_wheel_filename("kroko_onnx-1.12.9-1free-cp312-cp312-linux_x86_64.whl")
        self.assertEqual(parsed["name"], "kroko_onnx")
        self.assertEqual(parsed["version"], "1.12.9")
        self.assertEqual(parsed["build"], "1free")
        self.assertEqual(parsed["python"], "cp312")
        self.assertEqual(parsed["platform"], "linux_x86_64")

    def test_a_non_wheel_filename_is_refused(self):
        with self.assertRaises(bd.DistributionBuildError):
            bd.parse_wheel_filename("voicestt-2.0.0.tar.gz")


class MergeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _merge(self, variant="free", platform="linux_x86_64"):
        distribution = bd.distribution_name_for(variant)
        base = make_base_wheel(self.tmp, distribution)
        kroko = make_kroko_wheel(self.tmp, variant, platform)
        return bd.merge_kroko_runtime(
            base_wheel=base, kroko_wheel=kroko, variant=variant,
            out_dir=self.tmp / f"out-{variant}-{platform}", fingerprint="fp123",
        )

    def _names(self, result):
        with zipfile.ZipFile(result["path"]) as archive:
            return archive.namelist()

    def test_the_merged_wheel_carries_the_whole_native_runtime(self):
        names = self._names(self._merge())
        self.assertIn("kroko_onnx/__init__.py", names)
        self.assertIn("sherpa_onnx/lib/libsherpa.so", names)
        self.assertIn("_sherpa_onnx.cpython-312-x86_64-linux-gnu.so", names)

    def test_the_merged_wheel_keeps_the_voicestt_payload(self):
        names = self._names(self._merge())
        self.assertIn("voice_stt_server/__init__.py", names)
        self.assertIn("VoiceSTT/__init__.py", names)
        self.assertIn("VoiceSTT_server/server.py", names)

    def test_no_separate_kroko_distribution_metadata_is_shipped(self):
        # New authority section 2: there is no public kroko-onnx distribution,
        # and pip must not be told one is installed that it cannot uninstall.
        names = self._names(self._merge())
        self.assertFalse([n for n in names if n.startswith("kroko_onnx-1.12.9.dist-info/")])

    def test_the_kroko_licence_is_still_redistributed(self):
        names = self._names(self._merge())
        licences = [n for n in names if "KROKO-ONNX-LICENSE" in n]
        self.assertEqual(len(licences), 1)

    def test_the_wheel_is_retagged_for_the_real_platform(self):
        # Section 8: an embedded native runtime makes this a platform wheel.
        result = self._merge()
        self.assertEqual(result["pythonTag"], "cp312")
        self.assertEqual(result["platformTag"], "linux_x86_64")
        self.assertEqual(
            result["filename"], "voice_stt_server-2.0.0-cp312-cp312-linux_x86_64.whl"
        )
        with zipfile.ZipFile(result["path"]) as archive:
            wheel_metadata = archive.read(
                "voice_stt_server-2.0.0.dist-info/WHEEL"
            ).decode("utf-8")
        self.assertIn("Tag: cp312-cp312-linux_x86_64", wheel_metadata)
        self.assertIn("Root-Is-Purelib: false", wheel_metadata)
        self.assertNotIn("py3-none-any", wheel_metadata)

    def test_a_windows_kroko_wheel_produces_a_windows_distribution(self):
        result = self._merge(platform="win_amd64")
        self.assertEqual(result["platformTag"], "win_amd64")
        self.assertTrue(result["filename"].endswith("-cp312-cp312-win_amd64.whl"))

    def test_the_embedded_provenance_names_the_variant_and_the_artifact(self):
        # This is what makes "the installed distribution decides the runtime"
        # checkable rather than merely asserted.
        result = self._merge("pro")
        with zipfile.ZipFile(result["path"]) as archive:
            embedded = json.loads(archive.read("voice_stt_server/_embedded_kroko.json"))
        self.assertEqual(embedded["variant"], "pro")
        self.assertEqual(embedded["distribution"], "voice-stt-server-pro")
        self.assertEqual(embedded["kroko"]["buildTag"], "1pro")
        self.assertEqual(embedded["kroko"]["fingerprint"], "fp123")
        self.assertRegex(embedded["kroko"]["wheelSha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(embedded["runtimeSelectedBy"], "installed-distribution")
        self.assertTrue(embedded["licenseKeyIsRuntimeCredentialOnly"])

    def test_free_and_pro_never_produce_the_same_wheel(self):
        # W5R4-G13: the two identities cannot cross.
        free = self._merge("free")
        pro = self._merge("pro")
        self.assertNotEqual(free["filename"], pro["filename"])
        self.assertNotEqual(free["sha256"], pro["sha256"])
        self.assertNotEqual(free["distribution"], pro["distribution"])

    def test_a_free_wheel_never_contains_the_pro_runtime(self):
        with zipfile.ZipFile(self._merge("free")["path"]) as archive:
            self.assertIn(b"free", archive.read("kroko_onnx/__init__.py"))
            self.assertNotIn(b"pro", archive.read("kroko_onnx/__init__.py"))

    def test_the_merge_is_byte_reproducible(self):
        # A resumed release must re-derive, never re-invent, a candidate.
        first = self._merge()
        base = make_base_wheel(self.tmp / "second", "voice-stt-server") if False else None
        second = bd.merge_kroko_runtime(
            base_wheel=self.tmp / "voice_stt_server-2.0.0-py3-none-any.whl",
            kroko_wheel=self.tmp / "kroko_onnx-1.12.9-1free-cp312-cp312-linux_x86_64.whl",
            variant="free", out_dir=self.tmp / "again", fingerprint="fp123",
        )
        self.assertEqual(first["sha256"], second["sha256"])

    def test_the_record_lists_every_entry(self):
        result = self._merge()
        with zipfile.ZipFile(result["path"]) as archive:
            names = set(archive.namelist())
            record = archive.read("voice_stt_server-2.0.0.dist-info/RECORD").decode("utf-8")
        recorded = {line.split(",")[0] for line in record.splitlines() if line.strip()}
        self.assertEqual(recorded, names)

    def test_a_payload_collision_is_refused_rather_than_overwritten(self):
        # If VoiceSTT ever shipped its own kroko_onnx/, silently letting one
        # win would produce a wheel nobody could reason about.
        base = self.tmp / "colliding-2.0.0-py3-none-any.whl"
        with zipfile.ZipFile(base, "w") as archive:
            archive.writestr("kroko_onnx/__init__.py", "# ours\n")
            archive.writestr("voice_stt_server-2.0.0.dist-info/METADATA", "Name: voice-stt-server\n")
            archive.writestr("voice_stt_server-2.0.0.dist-info/WHEEL", "Tag: py3-none-any\n")
        kroko = make_kroko_wheel(self.tmp, "free")
        with self.assertRaises(bd.DistributionBuildError) as caught:
            bd.merge_kroko_runtime(base_wheel=base, kroko_wheel=kroko, variant="free",
                                   out_dir=self.tmp / "collide")
        self.assertIn("both provide", str(caught.exception))


class NoLocalPathTests(unittest.TestCase):
    def test_the_distribution_manifest_records_no_absolute_local_path(self):
        # W5R4-G07: the identity that travels into the RC manifest must be
        # machine-independent. (`path` is intentionally excluded from what the
        # RC manifest consumes; only filename/sha256/tags are bound.)
        import re

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result = bd.merge_kroko_runtime(
                base_wheel=make_base_wheel(tmp_path),
                kroko_wheel=make_kroko_wheel(tmp_path),
                variant="free", out_dir=tmp_path / "out",
            )
            bound = {k: v for k, v in result.items() if k != "path"}
            # \b keeps the "s:/" of an https:// URL from reading as a drive letter.
            self.assertIsNone(re.search(r"\b[A-Za-z]:[\\/]", json.dumps(bound)))


if __name__ == "__main__":
    unittest.main()
