"""AP-SRV-070 W4C: production build orchestrator unit tests.

These tests never invoke Docker or git for real; every external call goes
through a stub :data:`tools.build_production.CommandRunner`, so the tests
stay fast and hermetic while still exercising the real variant-selection,
Free/Pro-mapping and Kroko-artifact-resolution logic the orchestrator uses
for a real build.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tools"))

import build_production as bp  # noqa: E402


class RecordingRunner:
    """A stub :data:`CommandRunner` driven by a queue of canned results."""

    def __init__(self):
        self.calls = []
        self._responses = {}

    def respond(self, matcher, *, stdout="", returncode=0, stderr=""):
        self._responses[matcher] = bp.CommandResult(
            args=[], returncode=returncode, stdout=stdout, stderr=stderr
        )

    def __call__(self, cmd, *, cwd=None, env=None, check=True):
        self.calls.append(list(cmd))
        key = tuple(str(part) for part in cmd)
        for matcher, response in self._responses.items():
            if matcher(key):
                if check and response.returncode != 0:
                    raise bp.BuildError(f"stubbed failure for {key}")
                return response
        raise AssertionError(f"unexpected command in test: {cmd}")


def contains(*fragment):
    fragment = tuple(str(part) for part in fragment)

    def matcher(cmd):
        return any(cmd[i:i + len(fragment)] == fragment for i in range(len(cmd)))

    return matcher


# --------------------------------------------------------------------------
# Variant selection / Free-Pro mapping
# --------------------------------------------------------------------------


def test_image_name_for_maps_free_and_pro_to_distinct_public_identities():
    assert bp.image_name_for("free") == "voice-stt-server"
    assert bp.image_name_for("pro") == "voice-stt-server-pro"
    assert bp.image_name_for("FREE") == "voice-stt-server"


def test_image_name_for_rejects_unknown_variant():
    with pytest.raises(bp.BuildError):
        bp.image_name_for("enterprise")


def test_a_runtime_kroko_key_can_never_select_a_variant():
    """AP-SRV-070 W4C gate W4C-G30/G31: no key-shaped input exists in this API."""
    import inspect

    signature = inspect.signature(bp.image_name_for)
    assert list(signature.parameters) == ["variant"]


@pytest.mark.parametrize(
    "target,expected",
    [
        ("free", ["free"]),
        ("pro", ["pro"]),
        ("all", ["free", "pro"]),
    ],
)
def test_variants_for_target(target, expected):
    assert bp.variants_for_target(target) == expected


def test_variants_for_target_rejects_unknown_target():
    with pytest.raises(bp.BuildError):
        bp.variants_for_target("enterprise")


# --------------------------------------------------------------------------
# Kroko artifact resolution: REUSE vs BUILD
# --------------------------------------------------------------------------


def _describe_payload(*, present, wheel_name="kroko_onnx-1.12.9-1free-cp312-cp312-manylinux_2_28_x86_64.whl"):
    payload = {
        "variant": "free",
        "fingerprint": "deadbeefcafef00d",
        "inputs": {},
        "artifactStore": "/artifact-store",
        "artifactPresent": present,
    }
    if present:
        payload["artifact"] = {
            "fingerprint": "deadbeefcafef00d",
            "variant": "free",
            "wheelPath": f"/artifact-store/free/deadbeefcafef00d/{wheel_name}",
            "wheelFilename": wheel_name,
            "wheelSha256": "0" * 64,
        }
    else:
        payload["problems"] = ["no reusable artifact"]
    return payload


def test_resolve_kroko_wheel_reuses_a_verified_artifact_without_building(tmp_path):
    store = tmp_path / "store"
    work = tmp_path / "work"
    wheel = store / "free" / "deadbeefcafef00d" / "kroko_onnx-1.12.9-1free-cp312-cp312-manylinux_2_28_x86_64.whl"
    wheel.parent.mkdir(parents=True)
    wheel.write_bytes(b"fake wheel bytes")

    runner = RecordingRunner()
    runner.respond(contains("--describe-artifact"), stdout=json.dumps(_describe_payload(present=True)))

    payload = bp.resolve_kroko_wheel(
        variant="free",
        builder_image="voicestt-kroko-builder:test",
        artifact_store_host=store,
        work_dir_host=work,
        runner=runner,
    )

    assert payload["reused"] is True
    assert payload["hostWheelPath"] == str(wheel)
    build_calls = [call for call in runner.calls if "--build" in call]
    assert build_calls == []


def test_resolve_kroko_wheel_builds_once_on_a_real_miss(tmp_path):
    store = tmp_path / "store"
    work = tmp_path / "work"
    wheel = store / "free" / "deadbeefcafef00d" / "kroko_onnx-1.12.9-1free-cp312-cp312-manylinux_2_28_x86_64.whl"

    runner = RecordingRunner()
    call_count = {"describe": 0}

    def describe_matcher(cmd):
        return "--describe-artifact" in cmd

    def dynamic_runner(cmd, *, cwd=None, env=None, check=True):
        runner.calls.append(list(cmd))
        if describe_matcher(cmd):
            call_count["describe"] += 1
            if call_count["describe"] == 1:
                return bp.CommandResult([], 0, json.dumps(_describe_payload(present=False)), "")
            wheel.parent.mkdir(parents=True, exist_ok=True)
            wheel.write_bytes(b"fake wheel bytes")
            return bp.CommandResult([], 0, json.dumps(_describe_payload(present=True)), "")
        if "--build" in cmd:
            return bp.CommandResult([], 0, "", "")
        raise AssertionError(f"unexpected command: {cmd}")

    payload = bp.resolve_kroko_wheel(
        variant="free",
        builder_image="voicestt-kroko-builder:test",
        artifact_store_host=store,
        work_dir_host=work,
        runner=dynamic_runner,
    )

    assert payload["reused"] is False
    assert call_count["describe"] == 2
    build_calls = [call for call in runner.calls if "--build" in call]
    assert len(build_calls) == 1
    # AP-SRV-070 W4A/W4C: the Pro key must never reach the builder container.
    for call in build_calls:
        joined = " ".join(call)
        assert "KROKO_API_KEY" not in joined


def test_resolve_kroko_wheel_raises_if_build_did_not_actually_produce_an_artifact(tmp_path):
    store = tmp_path / "store"
    work = tmp_path / "work"

    runner = RecordingRunner()
    runner.respond(contains("--describe-artifact"), stdout=json.dumps(_describe_payload(present=False)))
    runner.respond(contains("--build"), stdout="")

    with pytest.raises(bp.BuildError):
        bp.resolve_kroko_wheel(
            variant="free",
            builder_image="voicestt-kroko-builder:test",
            artifact_store_host=store,
            work_dir_host=work,
            runner=runner,
        )


def test_host_wheel_path_rejects_a_path_outside_the_mounted_store(tmp_path):
    with pytest.raises(bp.BuildError):
        bp._host_wheel_path(tmp_path, "/etc/passwd")


# --------------------------------------------------------------------------
# Production image build: requires both wheels already staged
# --------------------------------------------------------------------------


def test_build_production_image_requires_voicestt_wheel(tmp_path):
    (tmp_path / "kroko").mkdir()
    (tmp_path / "kroko" / "kroko_onnx-1.12.9-1free-cp312-cp312-manylinux_2_28_x86_64.whl").write_bytes(b"x")
    (tmp_path / "voicestt").mkdir()

    with pytest.raises(bp.BuildError, match="no VoiceSTT wheel"):
        bp.build_production_image(
            variant="free",
            git_commit="a" * 40,
            voicestt_version="2.0.0",
            dist_dir=tmp_path,
            runner=RecordingRunner(),
        )


def test_build_production_image_requires_kroko_wheel(tmp_path):
    (tmp_path / "voicestt").mkdir()
    (tmp_path / "voicestt" / "voicestt-2.0.0-py3-none-any.whl").write_bytes(b"x")
    (tmp_path / "kroko").mkdir()

    with pytest.raises(bp.BuildError, match="no Kroko wheel"):
        bp.build_production_image(
            variant="free",
            git_commit="a" * 40,
            voicestt_version="2.0.0",
            dist_dir=tmp_path,
            runner=RecordingRunner(),
        )


def test_build_production_image_tags_free_and_pro_distinctly(tmp_path):
    (tmp_path / "voicestt").mkdir()
    (tmp_path / "voicestt" / "voicestt-2.0.0-py3-none-any.whl").write_bytes(b"x")
    (tmp_path / "kroko").mkdir()
    (tmp_path / "kroko" / "kroko_onnx-1.12.9-1free-cp312-cp312-manylinux_2_28_x86_64.whl").write_bytes(b"x")

    runner = RecordingRunner()
    runner.respond(lambda cmd: cmd[:2] == ("docker", "build"), stdout="")

    free_info = bp.build_production_image(
        variant="free", git_commit="a" * 40, voicestt_version="2.0.0",
        dist_dir=tmp_path, runner=runner,
    )
    pro_info = bp.build_production_image(
        variant="pro", git_commit="a" * 40, voicestt_version="2.0.0",
        dist_dir=tmp_path, runner=runner,
    )

    assert free_info["image"] == "voice-stt-server"
    assert pro_info["image"] == "voice-stt-server-pro"
    assert free_info["versionTag"] != pro_info["versionTag"]

    free_build_cmd = runner.calls[0]
    assert "--build-arg" in free_build_cmd
    assert "VOICESTT_KROKO_VARIANT=free" in free_build_cmd
    pro_build_cmd = runner.calls[1]
    assert "VOICESTT_KROKO_VARIANT=pro" in pro_build_cmd
    for call in runner.calls:
        joined = " ".join(call)
        assert "KROKO_API_KEY" not in joined
        assert "KROKO_LICENSE" not in joined
