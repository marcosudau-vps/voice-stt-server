"""GitHub Actions release-infrastructure guards (AP-SRV-070 W5-R04).

These are static contract tests over the workflow files themselves. They exist
because the workflows cannot be executed here, and because the properties they
guard are exactly the ones whose violation is both easy (one careless edit) and
expensive (an accidental public publish, or a secret handed to fork code).

Gates covered: W5R4-G40 (normal CI cannot publish), G41 (publication needs an
explicit dispatch/approval boundary), G42 (no release secret on a PR path),
G43 (third-party Actions pinned to full commit SHAs), G44 (least privilege),
G45 (GHCR uses GITHUB_TOKEN), G46 (Docker Hub username + PAT, no delete),
G47 (PyPI Trusted Publishing), G48 (qualification performs no public write),
G50 (the runtime Kroko key is never a build input), and the section 9
no-operator-local-path rule.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

CI = WORKFLOW_DIR / "ci.yml"
CANDIDATE = WORKFLOW_DIR / "release-candidate.yml"
PUBLISH = WORKFLOW_DIR / "release-publish.yml"

#: A pinned third-party action: ``owner/repo@<40 hex>`` (optionally with a
#: subdirectory). A tag or branch reference is exactly what this forbids.
_PINNED_USES_RE = re.compile(r"^[\w.-]+/[\w.-]+(/[\w./-]+)?@[0-9a-f]{40}$")

#: A drive-letter path is the shape of "this release needs Marco's PC".
#: The word boundary keeps the ``s:/`` of an ``https://`` URL from reading as
#: a drive letter.
_LOCAL_PATH_RE = re.compile(r"\b[A-Za-z]:[\\/]")


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def triggers(document: dict) -> dict:
    # PyYAML parses the bare key `on` as the boolean True.
    return document.get("on", document.get(True))


def steps_of(document: dict):
    for job_name, job in document["jobs"].items():
        for step in job.get("steps", []):
            yield job_name, step


class WorkflowInventoryTests(unittest.TestCase):
    def test_exactly_the_three_expected_workflows_exist(self):
        self.assertEqual(
            sorted(p.name for p in WORKFLOW_DIR.glob("*.yml")),
            ["ci.yml", "release-candidate.yml", "release-publish.yml"],
        )

    def test_every_workflow_parses(self):
        for path in WORKFLOW_DIR.glob("*.yml"):
            with self.subTest(workflow=path.name):
                self.assertIsInstance(load(path), dict)


class TriggerSafetyTests(unittest.TestCase):
    def test_ci_runs_on_ordinary_events(self):
        self.assertEqual(
            sorted(triggers(load(CI))), ["pull_request", "push", "workflow_dispatch"]
        )

    def test_both_release_workflows_are_dispatch_only(self):
        # W5R4-G41: no push, no tag push, no schedule can start a release.
        for path in (CANDIDATE, PUBLISH):
            with self.subTest(workflow=path.name):
                self.assertEqual(list(triggers(load(path))), ["workflow_dispatch"])

    def test_no_workflow_uses_pull_request_target(self):
        # W5R4-G42: `pull_request_target` runs with the base repository's
        # secrets while checking out fork code. It must never appear here.
        for path in WORKFLOW_DIR.glob("*.yml"):
            with self.subTest(workflow=path.name):
                self.assertNotIn("pull_request_target", path.read_text(encoding="utf-8"))

    def test_every_workflow_declares_a_concurrency_group(self):
        # W5R4: two publications of the same version must never race.
        for path in WORKFLOW_DIR.glob("*.yml"):
            with self.subTest(workflow=path.name):
                self.assertIn("concurrency", load(path))

    def test_the_publish_concurrency_group_is_per_version(self):
        group = load(PUBLISH)["concurrency"]["group"]
        self.assertIn("inputs.version", group)
        self.assertFalse(load(PUBLISH)["concurrency"]["cancel-in-progress"])


class PermissionTests(unittest.TestCase):
    def test_ci_is_read_only_everywhere(self):
        # W5R4-G40: normal CI cannot publish, because it cannot write anything.
        document = load(CI)
        self.assertEqual(document["permissions"], {"contents": "read"})
        for job_name, job in document["jobs"].items():
            with self.subTest(job=job_name):
                self.assertEqual(job.get("permissions"), {"contents": "read"})

    def test_the_candidate_workflow_may_only_write_packages(self):
        # W5R4-G48: candidate-linux needs `packages: write` for PRIVATE staging and nothing
        # else. No contents:write means it cannot tag or create a release.
        jobs = load(CANDIDATE)["jobs"]
        self.assertEqual(jobs["candidate-linux"]["permissions"], {"contents": "read", "packages": "write"})
        self.assertEqual(jobs["candidate-windows"]["permissions"], {"contents": "read"})
        self.assertEqual(jobs["candidate"]["permissions"], {"contents": "read"})

    def test_the_publish_workflow_grants_nothing_by_default(self):
        # W5R4-G44: every capability is opted into per job.
        self.assertEqual(load(PUBLISH)["permissions"], {})

    def test_id_token_is_granted_only_to_the_pypi_job(self):
        # W5R4-G47: OIDC reaches exactly the one job that publishes to PyPI.
        jobs = load(PUBLISH)["jobs"]
        with_id_token = [
            name for name, job in jobs.items()
            if "id-token" in (job.get("permissions") or {})
        ]
        self.assertEqual(with_id_token, ["pypi"])

    def test_contents_write_is_granted_only_where_a_tag_or_release_happens(self):
        jobs = load(PUBLISH)["jobs"]
        writers = [
            name for name, job in jobs.items()
            if (job.get("permissions") or {}).get("contents") == "write"
        ]
        self.assertEqual(sorted(writers), ["finalize", "tag"])

    def test_packages_write_is_granted_only_to_the_registry_jobs(self):
        jobs = load(PUBLISH)["jobs"]
        writers = [
            name for name, job in jobs.items()
            if (job.get("permissions") or {}).get("packages") == "write"
        ]
        self.assertEqual(sorted(writers), ["finalize", "registries"])

    def test_the_pypi_job_cannot_write_contents_or_packages(self):
        permissions = load(PUBLISH)["jobs"]["pypi"]["permissions"]
        self.assertEqual(permissions.get("contents"), "read")
        self.assertNotIn("packages", permissions)
        self.assertEqual(permissions.get("actions"), "read")
        self.assertEqual(permissions.get("id-token"), "write")

    def test_every_cross_run_artifact_download_job_has_actions_read(self):
        # B1: downloading artifacts across workflow runs requires actions: read
        jobs = load(PUBLISH)["jobs"]
        for name, job in jobs.items():
            perms = job.get("permissions") or {}
            self.assertEqual(
                perms.get("actions"), "read",
                f"publish job {name!r} downloads cross-run artifacts but lacks actions: read",
            )

    def test_every_checkout_job_has_contents_permission(self):
        # B1: checking out the repo requires at least contents: read
        jobs = load(PUBLISH)["jobs"]
        for name, job in jobs.items():
            perms = job.get("permissions") or {}
            self.assertIn(
                perms.get("contents"), ("read", "write"),
                f"publish job {name!r} runs checkout but lacks contents permission",
            )


class ApprovalBoundaryTests(unittest.TestCase):
    def test_every_publish_job_runs_in_the_protected_release_environment(self):
        # W5R4-G41/G42: the environment is where the required reviewer and the
        # release secrets live, so nothing outside it can publish.
        for name, job in load(PUBLISH)["jobs"].items():
            with self.subTest(job=name):
                self.assertEqual(job.get("environment"), "release")

    def test_no_candidate_or_ci_job_uses_the_release_environment(self):
        for path in (CI, CANDIDATE):
            for name, job in load(path)["jobs"].items():
                with self.subTest(workflow=path.name, job=name):
                    self.assertIsNone(job.get("environment"))

    def test_publication_requires_an_explicit_candidate_run(self):
        # A publish cannot be started without naming the qualified candidate.
        inputs = triggers(load(PUBLISH))["workflow_dispatch"]["inputs"]
        self.assertTrue(inputs["candidate_run_id"]["required"])
        self.assertTrue(inputs["version"]["required"])


class PinnedActionTests(unittest.TestCase):
    def test_every_third_party_action_is_pinned_to_a_full_commit_sha(self):
        # W5R4-G43. A tag is mutable; a commit SHA is not.
        for path in WORKFLOW_DIR.glob("*.yml"):
            for job_name, step in steps_of(load(path)):
                uses = step.get("uses")
                if not uses:
                    continue
                with self.subTest(workflow=path.name, job=job_name, uses=uses):
                    self.assertRegex(uses, _PINNED_USES_RE)

    def test_every_pinned_action_carries_a_readable_version_comment(self):
        # A bare SHA is unreviewable; the trailing comment is what makes an
        # upgrade auditable.
        for path in WORKFLOW_DIR.glob("*.yml"):
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("- uses:") or stripped.startswith("uses:"):
                    with self.subTest(workflow=path.name, line=stripped):
                        self.assertIn("#", stripped, "pinned action lacks a version comment")


class NoPublicWriteInQualificationTests(unittest.TestCase):
    def test_ci_never_mentions_a_publishing_command(self):
        # W5R4-G40.
        text = CI.read_text(encoding="utf-8")
        for forbidden in ("twine upload", "docker push", "gh release create",
                          "git push", "imagetools create", "release.py publish"):
            with self.subTest(command=forbidden):
                self.assertNotIn(forbidden, text)

    def test_the_candidate_workflow_never_publishes_publicly(self):
        # W5R4-G48. It may push to private staging; nothing else.
        text = CANDIDATE.read_text(encoding="utf-8")
        for forbidden in ("twine upload", "gh release create", "git push",
                          "release.py publish", "pypi-publish"):
            with self.subTest(command=forbidden):
                self.assertNotIn(forbidden, text)

    def test_the_candidate_workflow_pushes_only_to_staging(self):
        text = CANDIDATE.read_text(encoding="utf-8")
        self.assertIn("--push-staging", text)
        self.assertIn("-staging@sha256:", text)

    def test_only_the_publish_workflow_drives_the_release_engine(self):
        self.assertIn("release.py publish", PUBLISH.read_text(encoding="utf-8"))


class PublishOrderTests(unittest.TestCase):
    def test_the_jobs_are_chained_in_the_canonical_order(self):
        jobs = load(PUBLISH)["jobs"]
        self.assertIsNone(jobs["tag"].get("needs"))
        self.assertEqual(jobs["pypi"]["needs"], "tag")
        self.assertEqual(jobs["registries"]["needs"], "pypi")
        self.assertEqual(jobs["finalize"]["needs"], "registries")

    def test_each_job_bounds_itself_with_the_canonical_until_boundary(self):
        # The order is not re-implemented in YAML - each job hands the state
        # machine a boundary and the state machine enforces everything else.
        from release_tooling.state import STATE_ORDER

        text = PUBLISH.read_text(encoding="utf-8")
        boundaries = re.findall(r"--until (\w+)", text)
        self.assertEqual(boundaries, ["TAGGED", "PYPI_PUBLISHED", "EXTERNAL_VERIFIED", "COMPLETE"])
        for boundary in boundaries:
            self.assertIn(boundary, STATE_ORDER)

    def test_the_tag_job_comes_before_every_public_artifact_job(self):
        # W5R4-G21 expressed at the workflow level too.
        text = PUBLISH.read_text(encoding="utf-8")
        self.assertLess(text.index("--until TAGGED"), text.index("--until PYPI_PUBLISHED"))
        self.assertLess(text.index("--until PYPI_PUBLISHED"), text.index("--until EXTERNAL_VERIFIED"))
        self.assertLess(text.index("--until EXTERNAL_VERIFIED"), text.index("--until COMPLETE"))


class CredentialContractTests(unittest.TestCase):
    def test_ghcr_always_authenticates_with_the_github_token(self):
        # W5R4-G45: no long-lived GHCR PAT anywhere.
        for path in (CANDIDATE, PUBLISH):
            text = path.read_text(encoding="utf-8")
            for block in text.split("docker/login-action")[1:]:
                head = block[:400]
                if "registry: ghcr.io" in head:
                    with self.subTest(workflow=path.name):
                        self.assertIn("secrets.GITHUB_TOKEN", head)

    def test_docker_hub_uses_a_repository_variable_plus_a_secret_token(self):
        # W5R4-G46: the username is a variable (not sensitive), the PAT is a
        # secret, and no delete capability is ever requested.
        text = PUBLISH.read_text(encoding="utf-8")
        self.assertIn("vars.DOCKERHUB_USERNAME", text)
        self.assertIn("secrets.DOCKERHUB_TOKEN", text)
        self.assertNotIn("DOCKERHUB_USERNAME }}\n          password: ${{ vars.", text)

    def test_no_workflow_requires_a_pypi_token(self):
        # W5R4-G47: Trusted Publishing means there is no token to leak.
        for path in WORKFLOW_DIR.glob("*.yml"):
            text = path.read_text(encoding="utf-8")
            with self.subTest(workflow=path.name):
                self.assertNotIn("PYPI_API_TOKEN", text)
                self.assertNotIn("TWINE_PASSWORD", text)

    def test_no_workflow_uses_the_runtime_kroko_key_as_a_build_input(self):
        # W5R4-G50: the Pro *build* needs no key; the key is runtime-only.
        for path in WORKFLOW_DIR.glob("*.yml"):
            text = path.read_text(encoding="utf-8")
            with self.subTest(workflow=path.name):
                self.assertNotIn("VOICESTT_KROKO_ONNX_KEY", text)
                self.assertNotIn("KROKO_LICENSE_KEY", text)

    def test_no_secret_is_ever_echoed(self):
        for path in WORKFLOW_DIR.glob("*.yml"):
            text = path.read_text(encoding="utf-8")
            for line in text.splitlines():
                if "echo" in line and "secrets." in line:
                    self.fail(f"{path.name}: a secret may be echoed: {line.strip()}")


class PortabilityTests(unittest.TestCase):
    def test_no_workflow_contains_an_operator_local_absolute_path(self):
        # W5R4-G07 / section 9: release authority must not need one machine.
        for path in WORKFLOW_DIR.glob("*.yml"):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if _LOCAL_PATH_RE.search(line):
                    self.fail(f"{path.name}:{number} contains a local absolute path: {line.strip()}")

    def test_release_workflows_run_on_pinned_runners(self):
        for path in (CANDIDATE, PUBLISH):
            for name, job in load(path)["jobs"].items():
                with self.subTest(workflow=path.name, job=name):
                    if name == "candidate-windows":
                        self.assertEqual(job["runs-on"], "windows-latest")
                    else:
                        self.assertEqual(job["runs-on"], "ubuntu-24.04")

    def test_candidate_workflow_has_both_linux_and_windows_build_jobs(self):
        # B2: GitHub-native candidate builds both Linux and Windows public wheels
        jobs = load(CANDIDATE)["jobs"]
        self.assertIn("candidate-linux", jobs)
        self.assertIn("candidate-windows", jobs)
        self.assertIn("candidate", jobs)
        self.assertEqual(jobs["candidate-linux"]["runs-on"], "ubuntu-24.04")
        self.assertEqual(jobs["candidate-windows"]["runs-on"], "windows-latest")
        self.assertEqual(sorted(jobs["candidate"]["needs"]), ["candidate-linux", "candidate-windows"])

    def test_the_kroko_cache_is_keyed_per_variant_by_fingerprint(self):
        # W5R4-G13: Free and Pro caches can never cross.
        document = load(CANDIDATE)
        cache_steps = [
            step for _, step in steps_of(document)
            if (step.get("uses") or "").startswith("actions/cache@")
        ]
        self.assertEqual(len(cache_steps), 2)
        keys = sorted(step["with"]["key"] for step in cache_steps)
        self.assertTrue(keys[0].startswith("kroko-free-"))
        self.assertTrue(keys[1].startswith("kroko-pro-"))
        self.assertIn("fingerprints.outputs.free", keys[0])
        self.assertIn("fingerprints.outputs.pro", keys[1])
        paths = sorted(step["with"]["path"] for step in cache_steps)
        self.assertTrue(paths[0].endswith("/free"))
        self.assertTrue(paths[1].endswith("/pro"))

    def test_the_candidate_workflow_requires_a_clean_checkout(self):
        # A candidate must bind an exact committed source.
        self.assertIn("git status --porcelain", CANDIDATE.read_text(encoding="utf-8"))

    def test_shell_steps_use_a_strict_failure_mode(self):
        # A silent mid-script failure in a release job is unacceptable.
        for path in (CANDIDATE, PUBLISH):
            for job_name, step in steps_of(load(path)):
                script = step.get("run")
                if script and "\n" in script.strip():
                    with self.subTest(workflow=path.name, job=job_name, step=step.get("name")):
                        self.assertIn("set -euo pipefail", script)


class CandidateVersionValidationTests(unittest.TestCase):
    """B6: Validates workflow input version against candidate manifest before publication."""

    def test_publish_workflow_validates_manifest_version_before_tag(self):
        doc = load(PUBLISH)
        steps = doc["jobs"]["tag"]["steps"]
        step_names = [s.get("name") for s in steps]
        self.assertIn("Validate candidate manifest version against workflow input", step_names)
        val_idx = step_names.index("Validate candidate manifest version against workflow input")
        tag_idx = step_names.index("Advance to TAGGED")
        self.assertLess(val_idx, tag_idx, "Version validation must precede tag creation")
        val_step = steps[val_idx]
        script = val_step.get("run", "")
        self.assertIn("python release.py preflight", script)
        self.assertIn('--version "${{ inputs.version }}"', script)
        self.assertIn('--manifest "$CANDIDATE_DIR/rc-manifest.json"', script)
        self.assertIn("--require-qualified", script)

    def test_publish_workflow_passes_version_to_all_publish_invocations(self):
        doc = load(PUBLISH)
        for job_name, step in steps_of(doc):
            script = step.get("run", "")
            if "python release.py publish" in script:
                with self.subTest(job=job_name, step=step.get("name")):
                    self.assertIn(
                        '--version "${{ inputs.version }}"',
                        script,
                        f"Job {job_name} step {step.get('name')} must pass --version to publish",
                    )


if __name__ == "__main__":
    unittest.main()
