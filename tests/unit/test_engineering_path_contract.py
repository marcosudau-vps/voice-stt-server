"""Engineering path contracts (V2 pre-release cleanup, AP-CLN-010/020/030).

Mechanical guards for the repository's *physical* layout after the
consolidation under ``engineering/`` and ``examples/``: every path that CI,
the container build, packaging or the root release entry point depends on
must exist where those callers expect it, and every historical entry point
that was kept for compatibility must still resolve to the one implementation.

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
_FROM_TOOLS_IMPORT_RE = re.compile(r"\bfrom (?:engineering\.)?tools import (\w+)")


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
                if not (REPO_ROOT / "engineering" / "tools" / f"{match.group(1)}.py").is_file():
                    missing.append(f"{path.name}: tools.{match.group(1)}")
        self.assertEqual(missing, [])

    def test_the_release_workflows_still_call_the_root_release_entry_point(self):
        for name in ("release-candidate.yml", "release-publish.yml"):
            with self.subTest(workflow=name):
                self.assertIn("python release.py ", (WORKFLOWS / name).read_text(encoding="utf-8"))


class RootEntryPointTests(unittest.TestCase):
    def test_release_py_stays_a_thin_root_facade_over_release_tooling_cli(self):
        text = (REPO_ROOT / "release.py").read_text(encoding="utf-8")
        self.assertIn("from engineering.release.cli import main", text)
        self.assertTrue((REPO_ROOT / "engineering" / "release" / "cli.py").is_file())
        self.assertTrue(_module_defines(REPO_ROOT / "engineering" / "release" / "cli.py", "main"))

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
    def test_the_redistribution_authority_stays_where_the_release_tooling_reads_it(self):
        # Canonical release authority: deliberately NOT moved.
        config_text = (REPO_ROOT / "engineering" / "release" / "config.py").read_text(encoding="utf-8")
        self.assertIn('"build/kroko-redistribution.json"', config_text)
        self.assertTrue((REPO_ROOT / "build" / "kroko-redistribution.json").is_file())

    def test_the_release_tooling_imports_the_build_tools_by_package_identity(self):
        config_text = (REPO_ROOT / "engineering" / "release" / "config.py").read_text(encoding="utf-8")
        self.assertIn("from engineering.tools.build_production import", config_text)
        self.assertIn("from engineering.tools.build_distribution import", config_text)
        for name in ("build_production.py", "build_distribution.py"):
            with self.subTest(module=name):
                self.assertTrue((REPO_ROOT / "engineering" / "tools" / name).is_file())

    def test_the_kroko_builder_dockerfile_stays_beside_its_build_reference(self):
        # Deliberately not moved: build/BUILD.md (immutable) links it as a
        # sibling and tests/unit/test_docs_surface.py enforces that link; the
        # Kroko fingerprint guard hashes its content.
        text = (REPO_ROOT / "engineering" / "tools" / "build_production.py").read_text(encoding="utf-8")
        self.assertIn('REPO_ROOT / "build" / "kroko-builder.Dockerfile"', text)
        self.assertTrue((REPO_ROOT / "build" / "kroko-builder.Dockerfile").is_file())


class EngineeringLayoutTests(unittest.TestCase):
    def test_the_target_structure_exists(self):
        for relative in (
            "engineering/release/cli.py",
            "engineering/tools/build_production.py",
            "engineering/deployment/docker/nginx.conf",
            "engineering/deployment/docker/Dockerfile.pro-upgrade",
            "engineering/deployment/vps/release-voice-stt.sh",
            "engineering/deployment/vps/build-area/restore-venv.sh",
            "examples/app_browserclient/client.js",
            "examples/app_talk_with_llm/example_app_config.py",
            "examples/app_webserver/server.py",
        ):
            with self.subTest(path=relative):
                self.assertTrue((REPO_ROOT / relative).is_file())

    def test_the_old_example_and_tool_folders_hold_no_implementation(self):
        for name in ("app_browserclient", "app_talk_with_llm", "app_webserver"):
            with self.subTest(folder=name):
                self.assertFalse((REPO_ROOT / name).exists())
        for path in sorted((REPO_ROOT / "tools").glob("*.py")):
            with self.subTest(shim=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn(f"from engineering.tools import {path.stem} as _implementation", text)
                self.assertLess(len(text.splitlines()), 30, "a shim must not grow logic")
                self.assertTrue((REPO_ROOT / "engineering" / "tools" / path.name).is_file())

    def test_every_engineering_tool_keeps_a_historical_entry_point(self):
        for path in sorted((REPO_ROOT / "engineering" / "tools").glob("*.py")):
            with self.subTest(tool=path.name):
                self.assertTrue((REPO_ROOT / "tools" / path.name).is_file())

    def test_compatibility_imports_share_one_module_identity(self):
        import importlib
        import sys as _sys

        if str(REPO_ROOT) not in _sys.path:
            _sys.path.insert(0, str(REPO_ROOT))
        for name in ("release_candidate", "build_production", "cpu_only"):
            with self.subTest(tool=name):
                legacy = importlib.import_module(f"tools.{name}")
                current = importlib.import_module(f"engineering.tools.{name}")
                self.assertIs(legacy, current)
        for name in ("cli", "engine", "state", "adapters"):
            with self.subTest(release=name):
                legacy = importlib.import_module(f"release_tooling.{name}")
                current = importlib.import_module(f"engineering.release.{name}")
                self.assertIs(legacy, current)

    def test_historical_cli_paths_still_run(self):
        import subprocess
        import sys as _sys

        for script in ("tools/kroko_catalog_cli.py", "tools/build_production.py", "release.py"):
            with self.subTest(script=script):
                result = subprocess.run(
                    [_sys.executable, script, "--help"], cwd=REPO_ROOT,
                    capture_output=True, text=True, timeout=120,
                )
                self.assertEqual(result.returncode, 0, result.stderr[-2000:])

    def test_vps_compatibility_wrappers_forward_to_the_new_location(self):
        for relative in ("release-voice-stt.sh", "build-area/restore-venv.sh"):
            with self.subTest(script=relative):
                text = (REPO_ROOT / "build" / "vps" / relative).read_text(encoding="utf-8")
                self.assertIn(f"engineering/deployment/vps/{relative}", text)
                self.assertIn("exec ", text)
        script = (REPO_ROOT / "engineering" / "deployment" / "vps" / "release-voice-stt.sh").read_text(encoding="utf-8")
        self.assertIn("$CHECKOUT/engineering/deployment/vps/build-area/restore-venv.sh", script)

    def test_examples_are_tracked_again(self):
        self.assertNotIn("examples/", (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines())


class ContainerAndPackagingPathTests(unittest.TestCase):
    def test_production_dockerfile_copy_sources_are_repository_paths_or_staged_wheels(self):
        sources = _dockerfile_copy_sources((REPO_ROOT / "Dockerfile").read_text(encoding="utf-8"))
        self.assertTrue(sources)
        for source in sources:
            with self.subTest(source=source):
                if source.startswith("dist/"):
                    # Staged by engineering/tools/build_production.py at build time.
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
