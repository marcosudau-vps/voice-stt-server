import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import yaml

from app_talk_with_llm.example_app_config import (
    load_example_app_defaults,
    load_example_app_env,
)
from tools.compose import build_compose_environment, discover_model_path


class ProjectConfigTests(TestCase):
    def test_root_config_is_valid_for_server_and_example_app(self):
        root = Path(__file__).resolve().parents[2]
        payload = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8"))

        self.assertEqual(payload["version"], 1)
        self.assertIn("settings", payload)
        self.assertIn("deployment", payload)
        self.assertEqual(payload["deployment"]["kroko_variant"], "free")
        generated_path_keys = {
            "data_root_path",
            "request_log_path",
            "performance_log_path",
            "transcription_log_path",
            "system_event_log_path",
            "event_store_path",
            "audio_log_dir",
            "runtime_config_path",
        }
        self.assertEqual(
            generated_path_keys.intersection(payload["settings"]),
            {"data_root_path"},
        )
        self.assertEqual(payload["settings"]["data_root_path"], "/data")
        compose = yaml.safe_load(
            (root / "docker-compose.yml").read_text(encoding="utf-8")
        )
        # AP-SRV-070 W4C: the production Dockerfile no longer has a
        # KROKO_VARIANT build arg that triggers a native Kroko compile - the
        # variant is decided before `docker build` runs, by which wheel
        # tools/build_production.py stages under dist/kroko/. The ARG here is
        # informational (an OCI label) only.
        self.assertEqual(
            compose["services"]["server"]["build"]["args"]["VOICESTT_KROKO_VARIANT"],
            "${VOICESTT_KROKO_VARIANT:-free}",
        )
        # AP-SRV-070 W4C: the public compose is portable by default - a
        # single persistent runtime root at /var/lib/voicestt with a
        # documented fallback, not a value tools/compose.py must supply.
        data_mount = next(
            mount
            for mount in compose["services"]["server"]["volumes"]
            if mount.get("target") == "/var/lib/voicestt"
        )
        self.assertEqual(data_mount["source"], "${VOICESTT_DATA_PATH:-./data}")
        defaults = load_example_app_defaults(root / "config.yaml")
        self.assertEqual(defaults["STT_BACKEND"], "faster_whisper")
        self.assertEqual(defaults["USER_COLOR_RGB"], "0,188,242")
        self.assertEqual(defaults["SUPPRESS_TOKENS"], "-1")

    def test_process_environment_overrides_yaml_defaults(self):
        with patch.dict(os.environ, {"STT_BACKEND": "custom_api"}, clear=True):
            load_example_app_env()
            self.assertEqual(os.environ["STT_BACKEND"], "custom_api")
            self.assertEqual(os.environ["REALTIME_STT_BACKEND"], "faster_whisper")

    def test_model_path_discovery_uses_first_existing_candidate(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            second = root / "models" / "second"
            second.mkdir(parents=True)
            config = {
                "faster_whisper": {
                    "path": "auto",
                    "candidates": ["models/missing", "models/second"],
                }
            }
            self.assertEqual(
                discover_model_path("faster_whisper", config, root),
                second.resolve(),
            )

    def test_model_path_discovery_is_optional_and_returns_none_when_unconfigured(self):
        """AP-SRV-070 W4C: a custom model path is optional, not a hard requirement."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertIsNone(discover_model_path("faster_whisper", {}, root))
            self.assertIsNone(
                discover_model_path(
                    "kroko",
                    {"kroko": {"path": "auto", "candidates": ["models/missing"]}},
                    root,
                )
            )

    def test_compose_environment_skips_env_var_for_an_unconfigured_optional_model_path(self):
        ambient = {
            key: value
            for key, value in os.environ.items()
            if key not in ("VOICESTT_FASTER_WHISPER_HOST_PATH", "VOICESTT_KROKO_HOST_PATH")
        }
        with patch.dict(os.environ, ambient, clear=True):
            with TemporaryDirectory() as directory:
                root = Path(directory)
                deployment = {
                    "image": "test-image",
                    "kroko_variant": "free",
                    "runtime_data": {"path": "auto", "candidates": ["./runtime-data"]},
                    # No model_paths at all - AP-SRV-070 W4C made both optional.
                }

                environment = build_compose_environment(deployment, root)

                self.assertNotIn("VOICESTT_FASTER_WHISPER_HOST_PATH", environment)
                self.assertNotIn("VOICESTT_KROKO_HOST_PATH", environment)

    def test_compose_environment_comes_only_from_deployment_config(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            candidates = {}
            for name in ("faster_whisper", "kroko", "openwakeword"):
                model_path = root / "models" / name
                model_path.mkdir(parents=True)
                candidates[name] = {
                    "path": "auto",
                    "candidates": [str(model_path)],
                }
            deployment = {
                "image": "test-image",
                "kroko_variant": "pro",
                "server_port": 9000,
                "browser_port": 9001,
                "cpu_threads": 3,
                "runtime_data": {
                    "path": "auto",
                    "candidates": ["./runtime-data"],
                },
                "model_paths": candidates,
            }

            environment = build_compose_environment(deployment, root)

            self.assertEqual(environment["VOICESTT_IMAGE"], "test-image")
            self.assertEqual(environment["VOICESTT_KROKO_VARIANT"], "pro")
            self.assertEqual(environment["VOICESTT_PORT"], "9000")
            self.assertEqual(environment["VOICESTT_CPU_THREADS"], "3")
            self.assertEqual(
                environment["VOICESTT_DATA_PATH"],
                str((root / "runtime-data").resolve()),
            )

    def test_compose_rejects_unknown_kroko_variant(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            candidates = {}
            for name in ("faster_whisper", "kroko", "openwakeword"):
                model_path = root / "models" / name
                model_path.mkdir(parents=True)
                candidates[name] = {
                    "path": "auto",
                    "candidates": [str(model_path)],
                }
            deployment = {
                "kroko_variant": "licensed",
                "runtime_data": {"path": "./data", "candidates": []},
                "model_paths": candidates,
            }

            with self.assertRaisesRegex(ValueError, "free.*pro"):
                build_compose_environment(deployment, root)
