"""Portable Docker Compose launcher backed by the root config.yaml."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config.yaml"
COMPOSE_FILE = PROJECT_ROOT / "docker-compose.yml"

MODEL_ENV_NAMES = {
    "faster_whisper": "VOICESTT_FASTER_WHISPER_HOST_PATH",
    "kroko": "VOICESTT_KROKO_HOST_PATH",
    "openwakeword": "VOICESTT_OPENWAKEWORD_HOST_PATH",
}


def load_deployment_config(path: Path = DEFAULT_CONFIG) -> Dict[str, Any]:
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "PyYAML fehlt. Installiere zuerst die Projektabhängigkeiten."
        ) from exc

    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError("config.yaml muss ein YAML-Objekt enthalten.")
    deployment = payload.get("deployment")
    if not isinstance(deployment, dict):
        raise ValueError("config.yaml enthält keinen deployment-Abschnitt.")
    return deployment


def _resolve_path(value: str, project_root: Path) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(str(value)))
    path = Path(expanded)
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def discover_model_path(
    name: str,
    config: Dict[str, Any],
    project_root: Path = PROJECT_ROOT,
) -> Path:
    raw = config.get(name)
    if not isinstance(raw, dict):
        raise ValueError(f"deployment.model_paths.{name} fehlt.")

    configured = str(raw.get("path", "auto")).strip()
    candidates: Iterable[str]
    if configured.lower() != "auto":
        candidates = (configured,)
    else:
        candidates = raw.get("candidates") or ()

    checked = []
    for candidate in candidates:
        path = _resolve_path(str(candidate), project_root)
        checked.append(str(path))
        if path.is_dir():
            return path

    locations = "\n  - ".join(checked) if checked else "(keine)"
    raise FileNotFoundError(
        f"Kein Modellpfad für '{name}' gefunden. Geprüft:\n  - {locations}\n"
        "Ergänze genau einen Kandidaten in config.yaml unter "
        f"deployment.model_paths.{name}.candidates."
    )


def discover_data_path(
    config: Dict[str, Any],
    project_root: Path = PROJECT_ROOT,
) -> Path:
    raw = config.get("runtime_data")
    if not isinstance(raw, dict):
        raise ValueError("config.yaml: deployment.runtime_data fehlt.")
    configured = str(raw.get("path", "auto")).strip()
    candidates = (
        (configured,)
        if configured.lower() != "auto"
        else tuple(str(item) for item in (raw.get("candidates") or ()))
    )
    if not candidates:
        raise ValueError("deployment.runtime_data.candidates darf nicht leer sein.")

    resolved = [_resolve_path(candidate, project_root) for candidate in candidates]
    for path in resolved:
        if path.is_dir():
            return path
    # Laufzeitdaten dürfen neu angelegt werden; Modellverzeichnisse dagegen nicht.
    return resolved[-1]


def build_compose_environment(
    deployment: Dict[str, Any],
    project_root: Path = PROJECT_ROOT,
) -> Dict[str, str]:
    environment = os.environ.copy()
    model_paths = deployment.get("model_paths")
    if not isinstance(model_paths, dict):
        raise ValueError("config.yaml: deployment.model_paths fehlt.")

    for model_name, env_name in MODEL_ENV_NAMES.items():
        environment[env_name] = str(
            discover_model_path(model_name, model_paths, project_root)
        )

    data_path = discover_data_path(deployment, project_root)
    kroko_variant = str(deployment.get("kroko_variant", "free")).strip().lower()
    if kroko_variant not in {"free", "pro"}:
        raise ValueError(
            "deployment.kroko_variant muss 'free' oder 'pro' sein."
        )
    environment.update({
        "VOICESTT_IMAGE": str(deployment.get("image", "voicestt-cpu:local")),
        "VOICESTT_KROKO_VARIANT": kroko_variant,
        "VOICESTT_PORT": str(deployment.get("server_port", 8010)),
        "VOICESTT_BROWSER_PORT": str(deployment.get("browser_port", 8081)),
        "VOICESTT_CPU_THREADS": str(deployment.get("cpu_threads", 4)),
        "VOICESTT_DATA_PATH": str(data_path),
    })
    return environment


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="VoiceSTT Compose mit automatischer Pfaderkennung starten."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Zentrale Projektkonfiguration (Standard: config.yaml).",
    )
    parser.add_argument(
        "compose_args",
        nargs=argparse.REMAINDER,
        help="Argumente für 'docker compose', z. B. up --build -d.",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if not args.compose_args:
        raise SystemExit("Compose-Befehl fehlt, z. B.: up --build -d")

    deployment = load_deployment_config(args.config.resolve())
    environment = build_compose_environment(deployment)
    if args.compose_args[0] in {"up", "create", "run"}:
        Path(environment["VOICESTT_DATA_PATH"]).mkdir(parents=True, exist_ok=True)

    command = [
        "docker",
        "compose",
        "--project-name",
        str(deployment.get("compose_project", "voice")),
        "--file",
        str(COMPOSE_FILE),
        *args.compose_args,
    ]
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        check=False,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
