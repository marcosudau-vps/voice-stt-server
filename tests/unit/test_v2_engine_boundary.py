"""V2 product boundary: exactly two transcription engines (engine cleanup).

Supported: ``faster_whisper`` and ``kroko_onnx``. Five former adapters are kept
only as non-packaged drafts under ``engineering/drafts/transcription_engines/``;
seven were removed. These tests pin that decision at every layer that could
quietly re-open it: the factory, the server policy, the public capability
report, the import graph at server start, the package configuration and the
repository layout.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import unittest
from pathlib import Path

from VoiceSTT.transcription_engines import (
    TranscriptionEngineConfig,
    UnsupportedTranscriptionEngineError,
    create_transcription_engine,
    get_supported_transcription_engines,
)
from VoiceSTT.transcription_engines.factory import ENGINE_CLASS_PATHS

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = REPO_ROOT / "VoiceSTT" / "transcription_engines"
DRAFT_DIR = REPO_ROOT / "engineering" / "drafts" / "transcription_engines"

SUPPORTED = ["faster_whisper", "kroko_onnx"]
DRAFTS = (
    "parakeet_engine.py",
    "whisper_cpp_engine.py",
    "openai_api_engine.py",
    "openai_whisper_engine.py",
    "sherpa_onnx_engine.py",
)
REMOVED = (
    "cohere_transcribe_engine.py",
    "funasr_engine.py",
    "granite_speech_engine.py",
    "hf_transformers_engines.py",
    "moonshine_engine.py",
    "omnilingual_asr_engine.py",
    "qwen3_asr_engine.py",
)
#: Every engine name/alias the factory registered before the cleanup.
FORMER_NAMES = (
    "whisper_cpp", "openai_whisper", "openai_api", "parakeet", "nvidia_parakeet",
    "cohere_transcribe", "cohere", "granite_speech", "granite", "qwen3_asr",
    "qwen_asr", "omnilingual_asr", "omnilingual", "meta_omnilingual_asr",
    "omni_asr", "moonshine", "moonshine_streaming", "sherpa_onnx_parakeet",
    "sherpa_parakeet", "parakeet_sherpa_onnx", "sherpa_onnx_moonshine",
    "sherpa_moonshine", "moonshine_sherpa_onnx", "kroko", "banafo_kroko", "funasr",
)


class FactoryBoundaryTests(unittest.TestCase):
    def test_the_factory_registers_exactly_the_two_product_engines(self):
        self.assertEqual(sorted(ENGINE_CLASS_PATHS), SUPPORTED)
        self.assertEqual(get_supported_transcription_engines(), SUPPORTED)

    def test_every_former_engine_name_is_rejected_with_a_clear_error(self):
        for name in FORMER_NAMES:
            with self.subTest(engine=name):
                with self.assertRaises(UnsupportedTranscriptionEngineError) as caught:
                    create_transcription_engine(name, TranscriptionEngineConfig(model="x"))
                message = str(caught.exception)
                self.assertIn("Supported engines: faster_whisper, kroko_onnx", message)


class ServerPolicyBoundaryTests(unittest.TestCase):
    def test_unsupported_engines_are_rejected_before_any_import(self):
        from api_fastapi_server.server import ServerSettings, enforce_cpu_model_policy

        for field in ("transcription_engine", "realtime_transcription_engine"):
            for name in ("whisper_cpp", "parakeet", "kroko"):
                with self.subTest(field=field, engine=name):
                    settings = ServerSettings()
                    setattr(settings, field, name)
                    with self.assertRaisesRegex(ValueError, "Unsupported transcription engine"):
                        enforce_cpu_model_policy(settings)

    def test_the_default_product_configuration_stays_valid(self):
        from api_fastapi_server.server import ServerSettings, enforce_cpu_model_policy

        settings = ServerSettings()
        enforce_cpu_model_policy(settings)
        self.assertEqual(settings.transcription_engine, "faster_whisper")
        self.assertEqual(settings.realtime_transcription_engine, "kroko_onnx")

    def test_the_model_manager_still_serves_both_engines(self):
        from VoiceSTT_server.stt_model_management import (
            STTModelManager,
            default_product_authority,
        )

        engines = {product.engine for product in default_product_authority()}
        self.assertEqual(sorted(engines), SUPPORTED)
        manager = STTModelManager(runtime_root=REPO_ROOT / ".no-such-runtime-root")
        self.assertEqual(sorted(manager._adapters), SUPPORTED)

    def test_server_start_imports_no_unsupported_engine_module(self):
        code = (
            "import json, sys\n"
            "import api_fastapi_server.server as server\n"
            "server.ServerSettings()\n"
            "names = sorted(m for m in sys.modules if m.startswith('VoiceSTT.transcription_engines.'))\n"
            "print(json.dumps(names))\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        )
        loaded = {name.rsplit(".", 1)[1] for name in json.loads(result.stdout.strip().splitlines()[-1])}
        allowed = {"base", "factory", "model_resolver", "_model_utils",
                   "faster_whisper_engine", "kroko_onnx_engine"}
        self.assertEqual(loaded - allowed, set())


class RepositoryLayoutTests(unittest.TestCase):
    def test_only_the_two_engine_modules_remain_in_the_product_package(self):
        engines = sorted(path.name for path in ENGINE_DIR.glob("*_engine*.py"))
        self.assertEqual(engines, ["faster_whisper_engine.py", "kroko_onnx_engine.py"])

    def test_the_seven_removed_engines_are_gone_everywhere(self):
        for name in REMOVED:
            with self.subTest(file=name):
                hits = [p for p in REPO_ROOT.rglob(name) if ".git" not in p.parts]
                self.assertEqual(hits, [])

    def test_the_five_drafts_exist_but_are_isolated(self):
        for name in DRAFTS:
            with self.subTest(file=name):
                self.assertTrue((DRAFT_DIR / name).is_file())
                self.assertFalse((ENGINE_DIR / name).exists())
        for directory in (DRAFT_DIR, DRAFT_DIR.parent, DRAFT_DIR.parent.parent):
            with self.subTest(directory=str(directory.relative_to(REPO_ROOT))):
                self.assertFalse((directory / "__init__.py").exists())

    def test_no_product_code_imports_a_draft(self):
        drafts = {name[:-3] for name in DRAFTS}
        offenders = []
        for package in ("VoiceSTT", "VoiceSTT_server", "api_fastapi_server", "voice_stt_server"):
            for path in (REPO_ROOT / package).rglob("*.py"):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    modules = []
                    if isinstance(node, ast.Import):
                        modules = [alias.name for alias in node.names]
                    elif isinstance(node, ast.ImportFrom):
                        modules = [node.module or ""] + [alias.name for alias in node.names]
                    elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                        # dynamic import tables such as ENGINE_CLASS_PATHS
                        modules = [node.value] if node.value.startswith(".") else []
                    for module in modules:
                        parts = set(module.replace(".", " ").split())
                        if "engineering" in parts or parts & drafts:
                            offenders.append(f"{path.relative_to(REPO_ROOT)}: {module}")
        self.assertEqual(offenders, [])


class PackagingConfigurationTests(unittest.TestCase):
    def _extras(self):
        tree = ast.parse((REPO_ROOT / "setup.py").read_text(encoding="utf-8"))
        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "extras_require"
            ):
                return {key.value for key in node.value.keys}
        raise AssertionError("extras_require not found")

    def test_no_extra_for_an_unsupported_engine(self):
        extras = self._extras()
        for name in ("whisper-cpp", "whispercpp", "openai-whisper", "sherpa-onnx", "sherpa",
                     "omnilingual", "omnilingual-asr", "meta-omnilingual-asr", "transformers",
                     "moonshine", "granite", "cohere", "qwen", "qwen3-asr", "parakeet"):
            with self.subTest(extra=name):
                self.assertNotIn(name, extras)
        for name in ("faster-whisper", "recommended", "server", "openwakeword", "kroko-builder"):
            with self.subTest(extra=name):
                self.assertIn(name, extras)

    def test_no_engine_only_dependency_remains(self):
        setup_text = (REPO_ROOT / "setup.py").read_text(encoding="utf-8")
        requirements = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
        for package in ("pywhispercpp", "openai-whisper", "sherpa-onnx", "nemo_toolkit",
                        "omnilingual-asr", "qwen-asr", "transformers", "funasr", "torchaudio"):
            with self.subTest(package=package):
                self.assertNotIn(f'"{package}', setup_text)
                self.assertNotIn(package, requirements.split())

    def test_engineering_never_ships(self):
        manifest = (REPO_ROOT / "MANIFEST.in").read_text(encoding="utf-8")
        self.assertIn("prune engineering", manifest.splitlines())
        setup_text = (REPO_ROOT / "setup.py").read_text(encoding="utf-8")
        self.assertNotIn('"engineering', setup_text)


if __name__ == "__main__":
    unittest.main()
