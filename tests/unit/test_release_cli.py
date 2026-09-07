"""AP-SRV-070 W5 / W5-R01-C1: the release.py CLI surface.

Exercises the CLI's argument wiring and exit-code contract, not the
underlying checks (those have their own dedicated test modules -
``release_tooling.engine``/``adapters`` for the real publication paths).
``publish`` is proven to perform zero subprocess/network calls whenever it
refuses (missing ``--manifest``, missing ``--yes``, or a failing preflight) -
exactly the paths this correction run is allowed to exercise.
"""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from release_tooling import cli
from release_tooling.rc_manifest import build_rc_manifest, write_rc_manifest


def _write_sample_manifest(path: Path, **overrides) -> None:
    kwargs = dict(
        candidate_id="W5-RC1", product_version="2.0.0",
        source_commit="a" * 40, source_tree="b" * 40,
        wheel_path=Path("voicestt-2.0.0-py3-none-any.whl"), wheel_sha256="c" * 64,
        sdist_path=Path("voicestt-2.0.0.tar.gz"), sdist_sha256="d" * 64,
        kroko_free_fingerprint="ff", kroko_free_artifact_sha256="e" * 64,
        kroko_pro_fingerprint="pf", kroko_pro_artifact_sha256="f" * 64,
        free_image_tag="voice-stt-server:2.0.0", free_image_id="sha256:" + "1" * 64,
        pro_image_tag="voice-stt-server-pro:2.0.0", pro_image_id="sha256:" + "2" * 64,
        oci_version="2.0.0", oci_revision="a" * 40,
        qualification_timestamp_utc="2026-09-06T00:00:00Z",
        qualification_context="ctx", qualification_evidence_ref="ref",
    )
    kwargs.update(overrides)
    write_rc_manifest(path, build_rc_manifest(**kwargs))


class HelpAndUsageTests(unittest.TestCase):
    def test_help_exits_zero_and_lists_every_subcommand(self):
        out = io.StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                cli.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)
        for subcommand in ("preflight", "dry-run", "status", "manifest", "prepare-next-version", "publish"):
            self.assertIn(subcommand, out.getvalue())

    def test_no_subcommand_is_a_usage_error(self):
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                cli.main([])
        self.assertNotEqual(ctx.exception.code, 0)


#: Command prefixes that would perform a real public write. Preflight's own
#: read-only git check (``git rev-parse``, etc.) is deliberately allowed
#: through untouched - AP-SRV-070 W5, section 2.1: "Real remote read-only
#: checks are allowed only where already part of safe preflight behavior."
_FORBIDDEN_WRITE_PREFIXES = (
    ["twine", "upload"],
    ["docker", "push"],
    ["docker", "tag"],
    ["git", "tag"],
    ["git", "push"],
    ["gh", "release", "create"],
)


class PublishRefusesSafelyTests(unittest.TestCase):
    """AP-SRV-070 W5-R01-C1: ``publish`` is real-capable, but this run must
    never actually perform a public write. Every path below refuses before
    a single adapter runs a write command - proven by guarding the one
    subprocess primitive every adapter's ``publish()`` ultimately depends
    on and failing the test if a write-shaped command ever reaches it."""

    def _guarded_subprocess(self):
        import subprocess as subprocess_module

        real_run = subprocess_module.run

        def guarded(cmd, *args, **kwargs):
            cmd_list = [str(part) for part in cmd]
            for forbidden in _FORBIDDEN_WRITE_PREFIXES:
                if cmd_list[: len(forbidden)] == forbidden:
                    raise AssertionError(f"publish must not run a write command here: {cmd_list}")
            return real_run(cmd, *args, **kwargs)

        return mock.patch("subprocess.run", side_effect=guarded)

    def _poisoned(self):
        # Kept for the argument-validation tests (missing --manifest/--yes),
        # which must refuse before even reading git/network state.
        return (
            mock.patch("subprocess.run", side_effect=AssertionError("publish must not run any subprocess here")),
            mock.patch("urllib.request.urlopen", side_effect=AssertionError("publish must not make any network call here")),
        )

    def test_publish_without_manifest_refuses(self):
        p1, p2 = self._poisoned()
        with p1, p2:
            out = io.StringIO()
            with redirect_stderr(out):
                exit_code = cli.main(["publish", "--yes"])
        self.assertEqual(exit_code, cli.EXIT_USAGE)
        self.assertIn("--manifest", out.getvalue())

    def test_publish_without_yes_refuses(self):
        with TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            _write_sample_manifest(manifest_path)
            p1, p2 = self._poisoned()
            with p1, p2:
                out = io.StringIO()
                with redirect_stderr(out):
                    exit_code = cli.main(["publish", "--manifest", str(manifest_path)])
        self.assertEqual(exit_code, cli.EXIT_USAGE)
        self.assertIn("--yes", out.getvalue())

    def test_publish_with_yes_but_failing_preflight_refuses_before_any_adapter_runs(self):
        # The sample manifest's commit/tree/registry identities cannot match
        # this real checkout, so preflight fails deterministically - proving
        # publish stops there without ever running a write command. Real,
        # read-only preflight subprocess calls (git status/rev-parse) are
        # deliberately allowed through - see _FORBIDDEN_WRITE_PREFIXES.
        with TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            _write_sample_manifest(manifest_path)
            with self._guarded_subprocess():
                out = io.StringIO()
                with redirect_stdout(out), redirect_stderr(io.StringIO()) as err:
                    exit_code = cli.main(["publish", "--manifest", str(manifest_path), "--yes"])
        self.assertEqual(exit_code, cli.EXIT_FAILED)
        self.assertIn("Preflight failed", err.getvalue())

    def test_publish_never_leaks_a_synthetic_secret_from_the_environment(self):
        sentinel = "ghp_SENTINELDONOTLEAKAAAAAAAAAAAAAAAAAAAAAA"
        with TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            _write_sample_manifest(manifest_path)
            with self._guarded_subprocess(), mock.patch.dict("os.environ", {"VOICESTT_RELEASE_GITHUB_TOKEN": sentinel}):
                out = io.StringIO()
                err = io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    cli.main(["publish", "--manifest", str(manifest_path), "--yes"])
        self.assertNotIn(sentinel, out.getvalue())
        self.assertNotIn(sentinel, err.getvalue())


class DryRunCommandTests(unittest.TestCase):
    def test_dry_run_with_no_manifest_uses_a_placeholder_and_reports_every_step(self):
        # Poison the network/subprocess primitives the *default real*
        # adapters would use, so this proves dry-run degrades to
        # "unavailable" per step instead of crashing when nothing is
        # reachable/configured - it must never require network access to
        # run at all.
        with mock.patch("urllib.request.urlopen", side_effect=OSError("no network in this test")), \
             mock.patch("subprocess.run", side_effect=FileNotFoundError("no such tool in this test")):
            out = io.StringIO()
            with redirect_stderr(io.StringIO()):
                with redirect_stdout(out):
                    exit_code = cli.main(["dry-run"])
        self.assertEqual(exit_code, cli.EXIT_OK)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["mode"], "DRY_RUN")
        self.assertTrue(payload["sideEffectFree"])
        self.assertEqual(len(payload["plannedSteps"]), 8)
        self.assertEqual({s["executed"] for s in payload["plannedSteps"]}, {False})

    def test_dry_run_with_an_explicit_manifest_plans_against_it(self):
        with TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            _write_sample_manifest(manifest_path)
            with mock.patch("urllib.request.urlopen", side_effect=OSError("no network in this test")), \
                 mock.patch("subprocess.run", side_effect=FileNotFoundError("no such tool in this test")):
                out = io.StringIO()
                with redirect_stderr(io.StringIO()):
                    with redirect_stdout(out):
                        exit_code = cli.main(["dry-run", "--manifest", str(manifest_path)])
        self.assertEqual(exit_code, cli.EXIT_OK)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["version"], "2.0.0")


class PrepareNextVersionTests(unittest.TestCase):
    def test_default_bump_is_patch_and_does_not_write_version(self):
        with TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            version_path = repo_root / "VERSION"
            version_path.write_text("2.0.0\n", encoding="utf-8")
            with mock.patch.object(cli, "read_version_file", return_value="2.0.0"), \
                 mock.patch.object(cli.config, "REPO_ROOT", repo_root):
                out = io.StringIO()
                with redirect_stdout(out):
                    exit_code = cli.main(["prepare-next-version"])
            self.assertEqual(exit_code, cli.EXIT_OK)
            payload = json.loads(out.getvalue())
            self.assertEqual(payload["proposedNextVersion"], "2.0.1")
            self.assertFalse(payload["applied"])
            self.assertEqual(version_path.read_text(encoding="utf-8"), "2.0.0\n")

    def test_minor_and_major_are_mutually_exclusive(self):
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                cli.main(["prepare-next-version", "--minor", "--major"])
        self.assertNotEqual(ctx.exception.code, 0)

    def test_apply_writes_version_but_only_in_the_apply_path(self):
        with TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            version_path = repo_root / "VERSION"
            version_path.write_text("2.0.0\n", encoding="utf-8")
            with mock.patch.object(cli, "read_version_file", return_value="2.0.0"), \
                 mock.patch.object(cli.config, "REPO_ROOT", repo_root):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    cli.main(["prepare-next-version", "--minor", "--apply"])
            self.assertEqual(version_path.read_text(encoding="utf-8"), "2.1.0\n")


class ManifestValidateCommandTests(unittest.TestCase):
    def test_validate_reports_valid_manifest(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            manifest = build_rc_manifest(
                candidate_id="W5-RC1", product_version="2.0.0",
                source_commit="a" * 40, source_tree="b" * 40,
                wheel_path=Path("w.whl"), wheel_sha256="c" * 64,
                sdist_path=Path("s.tar.gz"), sdist_sha256="d" * 64,
                kroko_free_fingerprint="ff", kroko_free_artifact_sha256="e" * 64,
                kroko_pro_fingerprint="pf", kroko_pro_artifact_sha256="f" * 64,
                free_image_tag="t:1", free_image_id="id1",
                pro_image_tag="t:2", pro_image_id="id2",
                oci_version="2.0.0", oci_revision="a" * 40,
                qualification_timestamp_utc="2026-09-06T00:00:00Z",
                qualification_context="ctx", qualification_evidence_ref="ref",
            )
            write_rc_manifest(path, manifest)
            out = io.StringIO()
            with redirect_stdout(out):
                exit_code = cli.main(["manifest", "validate", str(path)])
            self.assertEqual(exit_code, cli.EXIT_OK)
            self.assertIn("VALID", out.getvalue())

    def test_validate_reports_invalid_manifest(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text('{"not": "a manifest"}', encoding="utf-8")
            with redirect_stderr(io.StringIO()) as err:
                exit_code = cli.main(["manifest", "validate", str(path)])
            self.assertEqual(exit_code, cli.EXIT_FAILED)
            self.assertIn("INVALID", err.getvalue())


class ManifestBuildCommandTests(unittest.TestCase):
    """AP-SRV-070 W5-R02-C1 (D3): ``release.py manifest build`` against
    real ``tools/build_production.py``-shaped input.

    Uses the real ``tools.build_production.resolve_kroko_wheel()`` (with
    a fake, no-Docker ``CommandRunner`` - the same pattern
    ``tests/unit/test_build_production.py`` already uses to test that
    function itself) to produce a genuinely production-code-shaped Kroko
    artifact payload, then assembles a full free/pro build-manifest the
    same way ``tools.build_production.run()`` does, and feeds that into
    this CLI subcommand. This is deliberately not another hand-typed
    synthetic fixture: the field this correction fixes (``wheelSha256``)
    comes from calling the real producer function, not from typing the
    key name into the test.
    """

    @classmethod
    def setUpClass(cls):
        import sys

        repo_root = Path(__file__).resolve().parents[2]
        tools_dir = repo_root / "tools"
        if str(tools_dir) not in sys.path:
            sys.path.insert(0, str(tools_dir))
        import build_production as bp

        cls.bp = bp

    def _real_kroko_payload(self, tmp_path, *, variant, fingerprint, wheel_sha256):
        from tests.unit.test_build_production import RecordingRunner, contains

        store = tmp_path / f"store-{variant}"
        work = tmp_path / f"work-{variant}"
        wheel_name = f"kroko_onnx-1.12.9-1{variant}-cp312-cp312-linux_x86_64.whl"
        wheel = store / variant / fingerprint / wheel_name
        wheel.parent.mkdir(parents=True)
        wheel.write_bytes(b"fake wheel bytes")

        describe_payload = {
            "variant": variant,
            "fingerprint": fingerprint,
            "inputs": {},
            "artifactStore": "/artifact-store",
            "artifactPresent": True,
            "artifact": {
                "fingerprint": fingerprint,
                "variant": variant,
                "wheelPath": f"/artifact-store/{variant}/{fingerprint}/{wheel_name}",
                "wheelFilename": wheel_name,
                "wheelSha256": wheel_sha256,
            },
        }
        runner = RecordingRunner()
        runner.respond(contains("--describe-artifact"), stdout=json.dumps(describe_payload))

        # Real production code, no Docker involved: resolve_kroko_wheel()
        # is the exact function tools.build_production.run() calls once
        # per variant.
        return self.bp.resolve_kroko_wheel(
            variant=variant,
            builder_image="voicestt-kroko-builder:test",
            artifact_store_host=store,
            work_dir_host=work,
            runner=runner,
        )

    def _production_shaped_manifest(
        self, tmp_path, *, variant, fingerprint, wheel_sha256, image_tag, image_id
    ):
        kroko_payload = self._real_kroko_payload(
            tmp_path, variant=variant, fingerprint=fingerprint, wheel_sha256=wheel_sha256,
        )
        # Mirrors tools.build_production.run()'s own literal manifest
        # shape (not a re-implementation of its logic) - see that
        # module's `manifest["variants"][variant] = {...}` assignment.
        return {
            "target": variant,
            "gitCommit": "a" * 40,
            "gitDirty": False,
            "voicesttVersion": "2.0.0",
            "voicesttWheel": {
                "path": "dist/voicestt/voicestt-2.0.0-py3-none-any.whl",
                "name": "voicestt-2.0.0-py3-none-any.whl",
                "bytes": 123,
                "sha256": "b" * 64,
            },
            "toolVersions": {"docker": "27.0.0", "git": "git version 2.45.0"},
            "variants": {
                variant: {
                    "kroko": kroko_payload,
                    "image": {"versionTag": image_tag, "image": image_tag.split(":")[0]},
                    "imageId": image_id,
                    "imageLabels": {"org.opencontainers.image.version": "2.0.0"},
                },
            },
        }

    def _run_manifest_build(self, free_path, pro_path, out_path):
        return cli.main([
            "manifest", "build",
            "--candidate-id", "W5-RC1",
            "--free-build-manifest", str(free_path),
            "--pro-build-manifest", str(pro_path),
            "--source-tree", "c" * 40,
            "--sdist-path", "voicestt-2.0.0.tar.gz",
            "--sdist-sha256", "d" * 64,
            "--qualification-timestamp", "2026-09-07T00:00:00Z",
            "--qualification-context", "test",
            "--qualification-evidence-ref", "test",
            "--out", str(out_path),
        ])

    def test_manifest_build_succeeds_with_real_production_shaped_input(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            free_manifest = self._production_shaped_manifest(
                tmp_path, variant="free", fingerprint="ab8986fd7fb93756",
                wheel_sha256="e" * 64,
                image_tag="voice-stt-server:2.0.0", image_id="sha256:" + "1" * 64,
            )
            pro_manifest = self._production_shaped_manifest(
                tmp_path, variant="pro", fingerprint="36b440630c0a9475",
                wheel_sha256="f" * 64,
                image_tag="voice-stt-server-pro:2.0.0", image_id="sha256:" + "2" * 64,
            )
            free_path = tmp_path / "free-build-manifest.json"
            pro_path = tmp_path / "pro-build-manifest.json"
            free_path.write_text(json.dumps(free_manifest), encoding="utf-8")
            pro_path.write_text(json.dumps(pro_manifest), encoding="utf-8")
            out_path = tmp_path / "rc-manifest.json"

            out = io.StringIO()
            with redirect_stdout(out):
                exit_code = self._run_manifest_build(free_path, pro_path, out_path)

            self.assertEqual(exit_code, cli.EXIT_OK, out.getvalue())
            self.assertTrue(out_path.is_file())
            from release_tooling.rc_manifest import load_rc_manifest

            written = load_rc_manifest(out_path)
            self.assertEqual(written["kroko"]["free"]["fingerprint"], "ab8986fd7fb93756")
            self.assertEqual(written["kroko"]["free"]["artifactSha256"], "e" * 64)
            self.assertEqual(written["kroko"]["pro"]["fingerprint"], "36b440630c0a9475")
            self.assertEqual(written["kroko"]["pro"]["artifactSha256"], "f" * 64)
            self.assertEqual(written["sourceCommit"], "a" * 40)
            self.assertEqual(written["sourceTree"], "c" * 40)
            self.assertNotIn("KROKO_API_KEY", json.dumps(written))

    def test_manifest_build_accepts_legacy_sha256_fallback_field(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            free_manifest = self._production_shaped_manifest(
                tmp_path, variant="free", fingerprint="ff", wheel_sha256="e" * 64,
                image_tag="voice-stt-server:2.0.0", image_id="sha256:" + "1" * 64,
            )
            # Simulate an older/legacy-shaped manifest that only carries
            # the pre-correction field name.
            artifact = free_manifest["variants"]["free"]["kroko"]["artifact"]
            artifact["sha256"] = artifact.pop("wheelSha256")
            pro_manifest = self._production_shaped_manifest(
                tmp_path, variant="pro", fingerprint="pf", wheel_sha256="f" * 64,
                image_tag="voice-stt-server-pro:2.0.0", image_id="sha256:" + "2" * 64,
            )
            free_path = tmp_path / "free-build-manifest.json"
            pro_path = tmp_path / "pro-build-manifest.json"
            free_path.write_text(json.dumps(free_manifest), encoding="utf-8")
            pro_path.write_text(json.dumps(pro_manifest), encoding="utf-8")
            out_path = tmp_path / "rc-manifest.json"

            exit_code = self._run_manifest_build(free_path, pro_path, out_path)

            self.assertEqual(exit_code, cli.EXIT_OK)
            from release_tooling.rc_manifest import load_rc_manifest

            written = load_rc_manifest(out_path)
            self.assertEqual(written["kroko"]["free"]["artifactSha256"], "e" * 64)

    def test_manifest_build_fails_closed_on_conflicting_dual_key_hashes(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            free_manifest = self._production_shaped_manifest(
                tmp_path, variant="free", fingerprint="ff", wheel_sha256="e" * 64,
                image_tag="voice-stt-server:2.0.0", image_id="sha256:" + "1" * 64,
            )
            artifact = free_manifest["variants"]["free"]["kroko"]["artifact"]
            artifact["sha256"] = "9" * 64  # deliberately disagrees with wheelSha256
            pro_manifest = self._production_shaped_manifest(
                tmp_path, variant="pro", fingerprint="pf", wheel_sha256="f" * 64,
                image_tag="voice-stt-server-pro:2.0.0", image_id="sha256:" + "2" * 64,
            )
            free_path = tmp_path / "free-build-manifest.json"
            pro_path = tmp_path / "pro-build-manifest.json"
            free_path.write_text(json.dumps(free_manifest), encoding="utf-8")
            pro_path.write_text(json.dumps(pro_manifest), encoding="utf-8")
            out_path = tmp_path / "rc-manifest.json"

            err = io.StringIO()
            with redirect_stderr(err):
                exit_code = self._run_manifest_build(free_path, pro_path, out_path)

            self.assertEqual(exit_code, cli.EXIT_FAILED)
            self.assertIn("conflicting hashes", err.getvalue())
            self.assertFalse(out_path.exists())


if __name__ == "__main__":
    unittest.main()
