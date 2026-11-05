"""Mechanical guards for the code-derived V2 reference (AP-DOC-V2-100).

``docs/v2-code-reference/`` documents the implementation from source code.
These tests keep the most drift-prone facts honest without judging prose:

* every page exists, is substantial and ends with its primary sources;
* every relative link resolves, and the reference never links into the
  older documentation tree (it must stand on its own);
* every HTTP/WebSocket route, every frozen v2 command/result/event name,
  every v2 settings key and every registered engine name that the code
  defines is mentioned on the page that documents it.

Everything is read from source via ``ast``/text; nothing is started.
"""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE = REPO_ROOT / "docs" / "v2-code-reference"
DOCS = REPO_ROOT / "docs"

PAGES = (
    "README.md",
    "01_system_und_architektur.md",
    "02_installation_und_betrieb.md",
    "03_konfiguration_und_settings.md",
    "04_transkription_und_modelle.md",
    "05_audio_trigger_wakeword.md",
    "06_http_rest_api.md",
    "07_websocket_protokolle.md",
    "08_authentisierung_und_kroko.md",
    "09_events_logs_persistenz.md",
    "10_build_ci_und_release_technik.md",
    "11_entwickler_tests_debugging.md",
    "12_feature_und_quellenmatrix.md",
)

_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_ROUTE_METHODS = {"get", "post", "put", "patch", "delete", "websocket"}


def _read(name):
    return (REFERENCE / name).read_text(encoding="utf-8")


def _module_literal(path, name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == name
        ):
            return node.value
    raise AssertionError(f"{name} not found in {path}")


def _schema_constants():
    """Name -> literal string value of every simple constant in schema.py."""
    tree = ast.parse(
        (REPO_ROOT / "api_fastapi_server" / "protocol_v2" / "schema.py").read_text(encoding="utf-8")
    )
    values = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            values[node.targets[0].id] = node.value.value
    return values


def _schema_collection(name):
    constants = _schema_constants()
    node = _module_literal(
        REPO_ROOT / "api_fastapi_server" / "protocol_v2" / "schema.py", name
    )
    if isinstance(node, ast.Call):  # frozenset({...})
        node = node.args[0]
    return {constants[element.id] for element in node.elts}


def _declared_routes():
    routes = set()
    sources = list((REPO_ROOT / "api_fastapi_server").glob("*.py"))
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr in _ROUTE_METHODS
                    and decorator.args
                    and isinstance(decorator.args[0], ast.Constant)
                ):
                    routes.add((decorator.func.attr, decorator.args[0].value))
    return routes


class ReferenceStructureTests(unittest.TestCase):
    def test_every_page_exists_and_is_substantial(self):
        for name in PAGES:
            with self.subTest(page=name):
                path = REFERENCE / name
                self.assertTrue(path.is_file(), name)
                self.assertGreater(len(path.read_text(encoding="utf-8")), 2500, name)

    def test_every_content_page_ends_with_its_primary_sources(self):
        for name in PAGES:
            if name == "12_feature_und_quellenmatrix.md":
                continue  # the matrix *is* the source list
            with self.subTest(page=name):
                text = _read(name)
                self.assertIn("## Primäre Quellen", text)
                tail = text.split("## Primäre Quellen", 1)[1]
                self.assertTrue(_LINK_RE.search(tail), f"{name}: no source link")

    def test_the_index_links_every_page(self):
        index = _read("README.md")
        for name in PAGES[1:]:
            with self.subTest(page=name):
                self.assertIn(f"({name})", index)

    def test_every_relative_link_resolves(self):
        broken = []
        for name in PAGES:
            for target in _LINK_RE.findall(_read(name)):
                if re.match(r"^[a-z]+://", target) or target.startswith("#"):
                    continue
                resolved = (REFERENCE / target.split("#", 1)[0]).resolve()
                if not resolved.exists():
                    broken.append(f"{name}: {target}")
        self.assertEqual(broken, [])

    def test_the_reference_does_not_depend_on_older_documentation(self):
        offenders = []
        for name in PAGES:
            for target in _LINK_RE.findall(_read(name)):
                if re.match(r"^[a-z]+://", target) or target.startswith("#"):
                    continue
                resolved = (REFERENCE / target.split("#", 1)[0]).resolve()
                inside_docs = DOCS.resolve() in resolved.parents or resolved == DOCS.resolve()
                inside_reference = (
                    REFERENCE.resolve() in resolved.parents or resolved == REFERENCE.resolve()
                )
                is_document = resolved.suffix.lower() in {".md", ".rst"}
                if not inside_reference and (inside_docs or is_document):
                    offenders.append(f"{name}: {target}")
        self.assertEqual(offenders, [])


class ReferenceCoverageTests(unittest.TestCase):
    def test_every_declared_route_is_documented(self):
        routes = _declared_routes()
        self.assertGreaterEqual(len(routes), 30, "route discovery drifted")
        documented = _read("06_http_rest_api.md") + _read("07_websocket_protokolle.md")
        missing = sorted(f"{method.upper()} {path}" for method, path in routes if f"`{path}`" not in documented)
        self.assertEqual(missing, [])

    def test_the_frozen_v2_vocabulary_is_documented(self):
        page = _read("07_websocket_protokolle.md")
        for collection in ("COMMAND_TYPES", "RESULT_CODES", "EVENT_TYPES"):
            values = _schema_collection(collection)
            self.assertTrue(values, collection)
            missing = sorted(value for value in values if f"`{value}`" not in page)
            with self.subTest(collection=collection):
                self.assertEqual(missing, [])

    def test_every_v2_settings_key_is_documented(self):
        from api_fastapi_server.settings_control import build_default_registry

        page = _read("03_konfiguration_und_settings.md")
        keys = [item["key"] for item in build_default_registry().schema_payload()]
        self.assertTrue(keys)
        missing = sorted(key for key in keys if f"`{key}`" not in page)
        self.assertEqual(missing, [])

    def test_every_registered_engine_name_is_documented(self):
        node = _module_literal(
            REPO_ROOT / "VoiceSTT" / "transcription_engines" / "factory.py",
            "ENGINE_CLASS_PATHS",
        )
        names = {key.value for key in node.keys}
        self.assertGreater(len(names), 10)
        page = _read("04_transkription_und_modelle.md")
        missing = sorted(name for name in names if f"`{name}`" not in page)
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
