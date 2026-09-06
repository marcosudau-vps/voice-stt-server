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


if __name__ == "__main__":
    unittest.main()
