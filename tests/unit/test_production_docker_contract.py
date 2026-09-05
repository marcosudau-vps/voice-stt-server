"""AP-SRV-070 W4C: static contract checks on the public production Docker
and Compose files.

These are text/YAML-structure assertions, not a real Docker build - a real
build/smoke is out of scope for the unit suite and is covered by the run's
Evidence (Evidence/03_Docker_Free, Evidence/04_Docker_Pro,
Evidence/07_Isolated_Smoke). What belongs here is exactly what a careless
future edit could silently regress: no editable install, no native Kroko
build in the production image, no operator-specific hostpaths/domains in the
public compose, and a Docker health probe that never requires a loaded STT
model.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

DOCKERFILE = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
KROKO_BUILDER_DOCKERFILE = (REPO_ROOT / "build" / "kroko-builder.Dockerfile").read_text(encoding="utf-8")
COMPOSE = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

#: Betreiberspezifische Marker, die im oeffentlichen Productionpfad nichts
#: verloren haben (AP-SRV-070 W4C, Abschnitt 11 / Gate W4C-G33).
PRIVATE_MARKERS = (
    "marcosudau",
    "selfhost",
    "/home/marco",
    "S:/MODELS",
    "voice.marcosudau.com",
    "build/vps",
)


def test_production_dockerfile_never_installs_voicestt_editable():
    assert "pip install -e" not in DOCKERFILE
    assert "pip install --editable" not in DOCKERFILE


def test_production_dockerfile_has_no_kroko_builder_stage():
    assert "AS kroko-builder" not in DOCKERFILE
    assert "install_kroko" not in DOCKERFILE


def test_production_dockerfile_installs_prebuilt_wheels_as_build_inputs():
    assert "dist/voicestt" in DOCKERFILE
    assert "dist/kroko" in DOCKERFILE


def test_production_dockerfile_runtime_targets_ubuntu_2404():
    assert "FROM ubuntu:24.04 AS runtime" in DOCKERFILE


def test_production_dockerfile_runs_as_non_root():
    assert "USER voicestt" in DOCKERFILE
    assert "useradd" in DOCKERFILE


def test_production_dockerfile_declares_required_oci_labels():
    for label in (
        "org.opencontainers.image.version",
        "org.opencontainers.image.revision",
        "org.opencontainers.image.created",
        "org.opencontainers.image.source",
    ):
        assert label in DOCKERFILE


def test_production_dockerfile_healthcheck_never_requires_ready_or_ok():
    """AP-SRV-070 W4C, section 10: a missing STT model must never fail Docker health."""
    healthcheck_line = next(
        line for line in DOCKERFILE.splitlines() if "urlopen" in line
    )
    assert "ready" not in healthcheck_line
    assert "'ok'" not in healthcheck_line
    assert "getcode() == 200" in healthcheck_line


def test_production_dockerfile_never_receives_a_kroko_license_key_build_arg():
    for name in ("KROKO_API_KEY", "KROKO_ONNX_KEY", "VOICESTT_KROKO_ONNX_KEY", "KROKO_KEY"):
        assert name not in DOCKERFILE


def test_production_dockerfile_never_copies_from_a_kroko_builder_stage():
    assert "--from=kroko-builder" not in DOCKERFILE


def test_kroko_builder_dockerfile_never_hardcodes_a_license_key():
    for name in ("KROKO_API_KEY", "KROKO_ONNX_KEY", "VOICESTT_KROKO_ONNX_KEY", "KROKO_KEY"):
        assert name not in KROKO_BUILDER_DOCKERFILE


# --------------------------------------------------------------------------
# Public compose contract
# --------------------------------------------------------------------------


def test_compose_defines_exactly_one_service():
    import yaml

    document = yaml.safe_load(COMPOSE)
    assert set(document["services"]) == {"server"}


def test_compose_persists_the_canonical_runtime_root():
    assert "/var/lib/voicestt" in COMPOSE


def test_compose_healthcheck_never_requires_ready_or_ok():
    import yaml

    document = yaml.safe_load(COMPOSE)
    test_cmd = " ".join(document["services"]["server"]["healthcheck"]["test"])
    assert "ready" not in test_cmd
    assert "'ok'" not in test_cmd
    assert "getcode() == 200" in test_cmd


def test_compose_has_no_hardcoded_private_paths_domains_or_networks():
    lowered = COMPOSE.lower()
    for marker in PRIVATE_MARKERS:
        assert marker.lower() not in lowered, f"found private marker in docker-compose.yml: {marker}"


@pytest.mark.parametrize("required_env", ["VOICESTT_IMAGE", "VOICESTT_PORT", "VOICESTT_DATA_PATH"])
def test_compose_environment_overrides_have_portable_defaults(required_env):
    # Every override in the public compose uses a `:-default` bash-style
    # fallback (never `:?required`, which is what made the previous compose
    # unusable without tools/compose.py + a private config.yaml).
    assert f"${{{required_env}:?" not in COMPOSE
    assert f"${{{required_env}:-" in COMPOSE


def test_compose_no_longer_requires_a_separate_browserclient_container():
    assert "nginx" not in COMPOSE
    assert "browserclient" not in COMPOSE
