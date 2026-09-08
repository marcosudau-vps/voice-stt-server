"""The ``release.py`` operator surface (AP-SRV-070 W5-R04).

The CLI is the only way a human drives the release, so these tests are mostly
about refusals: it must be impossible to publish by accident, against a
placeholder identity, or without the qualified candidate.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from release_support import make_manifest  # noqa: E402

from release_tooling import cli, rc_manifest  # noqa: E402


def run_cli(argv):
    """Runs the CLI, capturing stdout/stderr and the exit code."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


class DryRunCommandTests(unittest.TestCase):
    def test_dry_run_without_a_manifest_uses_an_obvious_placeholder(self):
        code, out, _ = run_cli(["dry-run"])
        self.assertEqual(code, cli.EXIT_OK)
        payload = json.loads(out)
        self.assertTrue(payload["sideEffectFree"])
        self.assertEqual(payload["startingState"], "PREPARED")

    def test_dry_run_reports_every_step_of_the_canonical_graph(self):
        _, out, _ = run_cli(["dry-run"])
        steps = [s["stepKey"] for s in json.loads(out)["plannedSteps"]]
        self.assertEqual(
            steps,
            ["git_tag", "pypi", "dockerhub", "ghcr", "external_verification",
             "aliases", "github_release", "final_verification", "complete"],
        )

    def test_dry_run_executes_nothing(self):
        _, out, _ = run_cli(["dry-run"])
        self.assertTrue(all(not s["executed"] for s in json.loads(out)["plannedSteps"]))

    def test_dry_run_honours_until(self):
        _, out, _ = run_cli(["dry-run", "--until", "TAGGED"])
        steps = [s["stepKey"] for s in json.loads(out)["plannedSteps"]]
        self.assertEqual(steps, ["git_tag"])

    def test_dry_run_against_an_explicit_manifest_plans_against_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rc-manifest.json"
            rc_manifest.write_rc_manifest(path, make_manifest())
            code, out, _ = run_cli(["dry-run", "--manifest", str(path),
                                    "--state-file", str(Path(tmp) / "state.json")])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertEqual(json.loads(out)["version"], "2.0.0")


class ManifestCommandTests(unittest.TestCase):
    def test_validate_accepts_a_complete_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rc-manifest.json"
            rc_manifest.write_rc_manifest(path, make_manifest())
            code, out, _ = run_cli(["manifest", "validate", str(path)])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn("VALID", out)

    def test_validate_rejects_an_incomplete_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rc-manifest.json"
            broken = make_manifest()
            broken["images"]["free"].pop("digest")
            path.write_text(json.dumps(broken), encoding="utf-8")
            code, _, err = run_cli(["manifest", "validate", str(path)])
        self.assertEqual(code, cli.EXIT_FAILED)
        self.assertIn("INVALID", err)

    def test_manifest_build_assembles_from_a_candidate_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate"
            _write_candidate_dir(candidate)
            out_path = Path(tmp) / "rc-manifest.json"
            code, out, err = run_cli([
                "manifest", "build",
                "--candidate-dir", str(candidate),
                "--candidate-id", "gh-4242-1",
                "--source-tree", "b" * 40,
                "--qualification-timestamp", "2026-09-08T00:00:00Z",
                "--qualification-context", "unit test",
                "--qualification-evidence-ref", "W5-R04",
                "--out", str(out_path),
            ])
            self.assertEqual(code, cli.EXIT_OK, err)
            manifest = rc_manifest.load_rc_manifest(out_path)
        self.assertEqual(manifest["candidateId"], "gh-4242-1")
        self.assertEqual(
            rc_manifest.distribution_names(manifest),
            {"free": "voice-stt-server", "pro": "voice-stt-server-pro"},
        )

    def test_manifest_build_refuses_a_candidate_built_from_two_commits(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate"
            _write_candidate_dir(candidate, pro_commit="9" * 40)
            code, _, err = run_cli([
                "manifest", "build",
                "--candidate-dir", str(candidate),
                "--candidate-id", "gh-4242-1",
                "--source-tree", "b" * 40,
                "--qualification-timestamp", "2026-09-08T00:00:00Z",
                "--qualification-context", "unit test",
                "--qualification-evidence-ref", "W5-R04",
                "--out", str(Path(tmp) / "out.json"),
            ])
        self.assertEqual(code, cli.EXIT_FAILED)
        self.assertIn("different", err)

    def test_manifest_qualify_sets_readiness_and_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rc-manifest.json"
            manifest = make_manifest(release_readiness=rc_manifest.READINESS_NOT_QUALIFIED)
            rc_manifest.write_rc_manifest(path, manifest)
            code, out, err = run_cli([
                "manifest", "qualify",
                "--manifest", str(path),
                "--evidence-ref", "https://actions/runs/123",
                "--context", "CI qualification run",
            ])
            self.assertEqual(code, cli.EXIT_OK, err)
            loaded = rc_manifest.load_rc_manifest(path)
            self.assertEqual(loaded["releaseReadiness"], "QUALIFIED")
            self.assertEqual(loaded["qualification"]["evidenceRef"], "https://actions/runs/123")
            self.assertEqual(loaded["qualification"]["context"], "CI qualification run")


class PublishRefusalTests(unittest.TestCase):
    def test_publish_without_yes_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rc-manifest.json"
            rc_manifest.write_rc_manifest(path, make_manifest())
            code, _, err = run_cli(["publish", "--manifest", str(path)])
        self.assertEqual(code, cli.EXIT_USAGE)
        self.assertIn("--yes", err)

    def test_publish_without_a_manifest_refuses(self):
        # A real publish must never run against a placeholder identity.
        code, _, err = run_cli(["publish", "--yes"])
        self.assertEqual(code, cli.EXIT_USAGE)
        self.assertIn("placeholder", err)

    def test_publish_refuses_not_qualified_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rc-manifest.json"
            manifest = make_manifest(release_readiness="NOT_QUALIFIED")
            rc_manifest.write_rc_manifest(path, manifest)
            code, _, err = run_cli(["publish", "--manifest", str(path), "--yes"])
        self.assertEqual(code, cli.EXIT_FAILED)
        self.assertIn("NOT_QUALIFIED", err)

    def test_publish_refuses_rejected_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rc-manifest.json"
            manifest = make_manifest(release_readiness="REJECTED")
            rc_manifest.write_rc_manifest(path, manifest)
            code, _, err = run_cli(["publish", "--manifest", str(path), "--yes"])
        self.assertEqual(code, cli.EXIT_FAILED)
        self.assertIn("REJECTED", err)

    def test_publish_refuses_manifest_lacking_evidence_ref(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rc-manifest.json"
            manifest = make_manifest(release_readiness="QUALIFIED")
            manifest["qualification"]["evidenceRef"] = ""
            path.write_text(json.dumps(manifest), encoding="utf-8")
            code, _, err = run_cli(["publish", "--manifest", str(path), "--yes"])
        self.assertEqual(code, cli.EXIT_FAILED)
        self.assertIn("evidenceRef", err)

    def test_publish_stops_before_any_adapter_when_preflight_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rc-manifest.json"
            rc_manifest.write_rc_manifest(path, make_manifest())
            with mock.patch("release_tooling.adapters.build_default_adapters") as build_adapters:
                code, _, err = run_cli(["publish", "--manifest", str(path), "--yes"])
        # The manifest's commit is not this checkout's HEAD, so preflight fails.
        self.assertEqual(code, cli.EXIT_FAILED)
        self.assertIn("Preflight failed", err)
        build_adapters.assert_not_called()

    def test_publish_refuses_version_mismatch_with_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rc-manifest.json"
            rc_manifest.write_rc_manifest(path, make_manifest(version="2.0.0"))
            code, _, err = run_cli(["publish", "--manifest", str(path), "--version", "9.9.9", "--yes"])
        self.assertEqual(code, cli.EXIT_FAILED)
        self.assertIn("does not match candidate manifest productVersion", err)

    def test_publish_accepts_matching_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rc-manifest.json"
            rc_manifest.write_rc_manifest(path, make_manifest(version="2.0.0"))
            code, _, err = run_cli(["publish", "--manifest", str(path), "--version", "2.0.0", "--yes"])
        # Passes version check, reaches preflight (which fails on HEAD mismatch).
        self.assertEqual(code, cli.EXIT_FAILED)
        self.assertIn("Preflight failed", err)

    def test_publish_never_echoes_an_environment_secret(self):
        # W5R4-G49.
        secret = "dckr_pat_ZZZZYYYYXXXXWWWWVVVVUUUU"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rc-manifest.json"
            rc_manifest.write_rc_manifest(path, make_manifest())
            with mock.patch.dict("os.environ", {"DOCKERHUB_TOKEN": secret}):
                code, out, err = run_cli(["publish", "--manifest", str(path), "--yes"])
        self.assertNotIn(secret, out)
        self.assertNotIn(secret, err)


class PreflightCommandCliTests(unittest.TestCase):
    def test_preflight_cli_fails_on_manifest_version_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rc-manifest.json"
            rc_manifest.write_rc_manifest(path, make_manifest(version="2.0.0"))
            code, out, err = run_cli(["preflight", "--manifest", str(path), "--version", "9.9.9"])
        self.assertEqual(code, cli.EXIT_FAILED)
        payload = json.loads(out)
        self.assertFalse(payload["passed"])
        checks = {c["name"]: c["status"] for c in payload["checks"]}
        self.assertEqual(checks.get("rc_manifest_version_matches"), "FAIL")


class PrecheckPypiCommandTests(unittest.TestCase):
    def test_precheck_pypi_stages_absent_files(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path = tmp_path / "rc-manifest.json"
            manifest = make_manifest()
            dist_dir = tmp_path / "dist"
            dist_dir.mkdir()
            for variant in ("free", "pro"):
                for w in manifest["distributions"][variant]["wheels"]:
                    wheel_file = dist_dir / w["filename"]
                    wheel_file.write_bytes(b"dummy wheel " + w["filename"].encode())
                    w["sha256"] = hashlib.sha256(wheel_file.read_bytes()).hexdigest()
            rc_manifest.write_rc_manifest(manifest_path, manifest)

            stage_dir = tmp_path / "stage"
            fake_report = {
                "free": {
                    "status": "ABSENT",
                    "project": "voice-stt-server",
                    "version": "2.0.0",
                    "matched": [],
                    "absent": [w["filename"] for w in manifest["distributions"]["free"]["wheels"]],
                    "conflicts": [],
                },
                "pro": {
                    "status": "ABSENT",
                    "project": "voice-stt-server-pro",
                    "version": "2.0.0",
                    "matched": [],
                    "absent": [w["filename"] for w in manifest["distributions"]["pro"]["wheels"]],
                    "conflicts": [],
                },
            }
            with mock.patch("release_tooling.remote_checks.precheck_pypi", return_value=fake_report):
                code, out, err = run_cli([
                    "precheck-pypi",
                    "--manifest", str(manifest_path),
                    "--dist-dir", str(dist_dir),
                    "--stage-dir", str(stage_dir),
                ])
            self.assertEqual(code, cli.EXIT_OK, err)
            self.assertTrue((stage_dir / "free").is_dir())
            self.assertTrue((stage_dir / "pro").is_dir())
            free_staged = [p.name for p in (stage_dir / "free").iterdir()]
            self.assertEqual(len(free_staged), 2)
            pro_staged = [p.name for p in (stage_dir / "pro").iterdir()]
            self.assertEqual(len(pro_staged), 2)


class PrepareNextVersionTests(unittest.TestCase):
    def test_it_is_read_only_without_apply(self):
        code, out, _ = run_cli(["prepare-next-version"])
        payload = json.loads(out)
        self.assertEqual(code, cli.EXIT_OK)
        self.assertFalse(payload["applied"])
        self.assertEqual(payload["currentVersion"], "2.0.0")

    def test_it_never_runs_as_part_of_publishing(self):
        # W5R4-G29: a failed publication must never produce 2.0.1.
        source = Path(cli.__file__).read_text(encoding="utf-8")
        publish_body = source[source.index("def _cmd_publish("):source.index("def build_parser(")]
        self.assertNotIn("prepare_next_version", publish_body)
        self.assertNotIn("bump(", publish_body)


def _write_candidate_dir(candidate: Path, pro_commit: str = "a" * 40) -> None:
    """A minimal but structurally real candidate output directory."""
    candidate.mkdir(parents=True, exist_ok=True)
    for variant, commit in (("free", "a" * 40), ("pro", pro_commit)):
        digest = "sha256:" + ("1" if variant == "free" else "2") * 64
        (candidate / f"build-manifest-{variant}.json").write_text(json.dumps({
            "gitCommit": commit,
            "gitDirty": False,
            "voicesttVersion": "2.0.0",
            "variants": {
                variant: {
                    "kroko": {
                        "fingerprint": f"fp-{variant}",
                        "artifact": {"wheelSha256": ("3" if variant == "free" else "4") * 64},
                    },
                    "image": {"versionTag": f"voice-stt-server{'-pro' if variant == 'pro' else ''}:2.0.0"},
                }
            },
        }), encoding="utf-8")
        name = "voice-stt-server-pro" if variant == "pro" else "voice-stt-server"
        (candidate / f"distribution-{variant}.json").write_text(json.dumps({
            "distribution": name,
            "filename": f"{name.replace('-', '_')}-2.0.0-cp312-cp312-linux_x86_64.whl",
            "sha256": ("5" if variant == "free" else "6") * 64,
            "pythonTag": "cp312",
            "abiTag": "cp312",
            "platformTag": "linux_x86_64",
            "embedded": {"kroko": {"wheelSha256": ("3" if variant == "free" else "4") * 64}},
        }), encoding="utf-8")
        (candidate / f"distribution-{variant}-win_amd64.json").write_text(json.dumps({
            "distribution": name,
            "filename": f"{name.replace('-', '_')}-2.0.0-cp312-cp312-win_amd64.whl",
            "sha256": ("7" if variant == "free" else "8") * 64,
            "pythonTag": "cp312",
            "abiTag": "cp312",
            "platformTag": "win_amd64",
            "embedded": {"kroko": {"wheelSha256": ("3" if variant == "free" else "4") * 64}},
        }), encoding="utf-8")
        (candidate / f"staging-{variant}.json").write_text(json.dumps({
            "pushed": True,
            "digest": digest,
            "reference": f"ghcr.io/marcosudau-vps/{name}-staging@{digest}",
        }), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
