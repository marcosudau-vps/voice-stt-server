"""Engineering path contracts (V2 pre-release cleanup, AP-CLN-010/030).

These are mechanical guards for the repository's *physical* layout: every
path that CI, the container build, packaging or the root release entry point
depends on must exist where those callers expect it. They exist so that a
future structural move (for example a consolidation under ``engineering/``)
fails here, loudly and specifically, instead of silently breaking a workflow
that only runs on dispatch.

The tests only read files; they build, import-execute and publish nothing.
"""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

_PYTHON_SCRIPT_RE = re.compile(r"\bpython3?\s+((?:[\w.-]+/)*[\w.-]+\.py)\b")
_FROM_TOOLS_IMPORT_RE = re.compile(r"\bfrom tools import (\w+)")


def _workflow_texts():
    for path in sorted(WORKFLOWS.glob("*.yml")):
        yield path, path.read_text(encoding="utf-8")


def _dockerfile_copy_sources(text):
    """Local ``COPY`` sources of a Dockerfile (``--from`` stages excluded)."""
    sources = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line.upper().startswith("COPY "):
            continue
        parts = line.split()[1:]
        if any(part.startswith("--from") for part in parts):
            continue
        parts = [part for part in parts if not part.startswith("--")]
        sources.extend(parts[:-1])
    return sources


def _console_scripts():
    """``name=module:function`` entries of setup.py, read via the AST."""
    tree = ast.parse((REPO_ROOT / "setup.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "console_scripts"
                    and isinstance(value, ast.List)
                ):
                    return [elt.value for elt in value.elts if isinstance(elt, ast.Constant)]
    return []


def _module_defines(module_path, name):
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
        for node in tree.body
    ) or any(
        isinstance(node, (ast.Import, ast.ImportFrom))
        and any((alias.asname or alias.name) == name for alias in node.names)
        for node in tree.body
    )


class WorkflowScriptPathTests(unittest.TestCase):
    def test_every_python_script_a_workflow_runs_exists(self):
        missing = []
        seen = 0
        for path, text in _workflow_texts():
            for match in _PYTHON_SCRIPT_RE.finditer(text):
                seen += 1
                if not (REPO_ROOT / match.group(1)).is_file():
                    missing.append(f"{path.name}: {match.group(1)}")
        self.assertGreater(seen, 0, "no workflow script invocations found - parser drifted")
        self.assertEqual(missing, [])

    def test_every_tools_module_a_workflow_imports_exists(self):
        missing = []
        for path, text in _workflow_texts():
            for match in _FROM_TOOLS_IMPORT_RE.finditer(text):
                if not (REPO_ROOT / "tools" / f"{match.group(1)}.py").is_file():
                    missing.append(f"{path.name}: tools.{match.group(1)}")
        self.assertEqual(missing, [])

    def test_the_release_workflows_still_call_the_root_release_entry_point(self):
        for name in ("release-candidate.yml", "release-publish.yml"):
            with self.subTest(workflow=name):
                self.assertIn("python release.py ", (WORKFLOWS / name).read_text(encoding="utf-8"))


class RootEntryPointTests(unittest.TestCase):
    def test_release_py_stays_a_thin_root_facade_over_release_tooling_cli(self):
        text = (REPO_ROOT / "release.py").read_text(encoding="utf-8")
        self.assertIn("from release_tooling.cli import main", text)
        self.assertTrue((REPO_ROOT / "release_tooling" / "cli.py").is_file())
        self.assertTrue(_module_defines(REPO_ROOT / "release_tooling" / "cli.py", "main"))

    def test_root_build_entry_files_stay_at_the_root(self):
        for name in (
            "setup.py",
            "pyproject.toml",
            "MANIFEST.in",
            "Dockerfile",
            "docker-compose.yml",
            ".dockerignore",
            "VERSION",
            "build_identity_support.py",
            "wakeword_package_resources.py",
            "release.py",
            "config.yaml",
        ):
            with self.subTest(path=name):
                self.assertTrue((REPO_ROOT / name).is_file())

    def test_every_console_script_target_exists(self):
        scripts = _console_scripts()
        names = {entry.split("=", 1)[0].strip() for entry in scripts}
        # The public CLI and its compatibility aliases (CI's install smoke
        # test checks exactly this set on the installed wheel).
        self.assertTrue(
            {"voice-stt-server", "stt-server", "stt-server-legacy", "stt", "stt-install-kroko"} <= names,
            names,
        )
        for entry in scripts:
            name, target = (part.strip() for part in entry.split("=", 1))
            module, function = target.split(":", 1)
            module_path = REPO_ROOT.joinpath(*module.split(".")).with_suffix(".py")
            with self.subTest(script=name):
                self.assertTrue(module_path.is_file(), module_path)
                self.assertTrue(_module_defines(module_path, function), f"{module}:{function}")

    def test_public_import_packages_exist(self):
        for package in ("voice_stt_server", "VoiceSTT", "VoiceSTT_server", "api_fastapi_server"):
            with self.subTest(package=package):
                self.assertTrue((REPO_ROOT / package / "__init__.py").is_file())


class ReleaseAuthorityLocationTests(unittest.TestCase):
    def test_the_redistribution_authority_stays_where_release_tooling_reads_it(self):
        config_text = (REPO_ROOT / "release_tooling" / "config.py").read_text(encoding="utf-8")
        self.assertIn('"build/kroko-redistribution.json"', config_text)
        self.assertTrue((REPO_ROOT / "build" / "kroko-redistribution.json").is_file())

    def test_release_tooling_still_finds_the_tools_directory(self):
        config_text = (REPO_ROOT / "release_tooling" / "config.py").read_text(encoding="utf-8")
        self.assertIn('REPO_ROOT / "tools"', config_text)
        for name in ("build_production.py", "build_distribution.py"):
            with self.subTest(module=name):
                self.assertTrue((REPO_ROOT / "tools" / name).is_file())

    def test_the_kroko_builder_dockerfile_stays_where_build_production_expects_it(self):
        text = (REPO_ROOT / "tools" / "build_production.py").read_text(encoding="utf-8")
        self.assertIn('REPO_ROOT / "build" / "kroko-builder.Dockerfile"', text)
        self.assertTrue((REPO_ROOT / "build" / "kroko-builder.Dockerfile").is_file())


class ContainerAndPackagingPathTests(unittest.TestCase):
    def test_production_dockerfile_copy_sources_are_repository_paths_or_staged_wheels(self):
        sources = _dockerfile_copy_sources((REPO_ROOT / "Dockerfile").read_text(encoding="utf-8"))
        self.assertTrue(sources)
        for source in sources:
            with self.subTest(source=source):
                if source.startswith("dist/"):
                    # Staged by tools/build_production.py at build time.
                    self.assertTrue(source.endswith(".whl"), source)
                    continue
                self.assertTrue((REPO_ROOT / source).exists(), source)

    def test_kroko_builder_copy_sources_exist(self):
        text = (REPO_ROOT / "build" / "kroko-builder.Dockerfile").read_text(encoding="utf-8")
        sources = _dockerfile_copy_sources(text)
        self.assertTrue(sources)
        for source in sources:
            with self.subTest(source=source):
                self.assertTrue((REPO_ROOT / source).exists(), source)

    def test_compose_builds_the_root_dockerfile_from_the_root_context(self):
        text = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^\s+context:\s*\.\s*$")

    def test_manifest_in_includes_exist(self):
        for raw in (REPO_ROOT / "MANIFEST.in").read_text(encoding="utf-8").splitlines():
            parts = raw.split()
            if len(parts) == 2 and parts[0] == "include":
                with self.subTest(path=parts[1]):
                    self.assertTrue((REPO_ROOT / parts[1]).is_file(), parts[1])


if __name__ == "__main__":
    unittest.main()
