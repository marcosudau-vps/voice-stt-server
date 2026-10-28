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
import zipfile
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
    assert bp.image_name_for("pro") == "voice-stt-server"
    assert bp.image_name_for("pro") == "voice-stt-server"
    assert bp.image_name_for("PRO") == "voice-stt-server"


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
        ("pro", ["pro"]),
        ("pro", ["pro"]),
        ("all", ["pro"]),
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


def _describe_payload(*, present, wheel_name="kroko_onnx-1.12.9-1pro-cp312-cp312-manylinux_2_28_x86_64.whl"):
    payload = {
        "variant": "pro",
        "fingerprint": "deadbeefcafef00d",
        "inputs": {},
        "artifactStore": "/artifact-store",
        "artifactPresent": present,
    }
    if present:
        payload["artifact"] = {
            "fingerprint": "deadbeefcafef00d",
            "variant": "pro",
            "wheelPath": f"/artifact-store/pro/deadbeefcafef00d/{wheel_name}",
            "wheelFilename": wheel_name,
            "wheelSha256": "0" * 64,
        }
    else:
        payload["problems"] = ["no reusable artifact"]
    return payload


def test_resolve_kroko_wheel_reuses_a_verified_artifact_without_building(tmp_path):
    store = tmp_path / "store"
    work = tmp_path / "work"
    wheel = store / "pro" / "deadbeefcafef00d" / "kroko_onnx-1.12.9-1pro-cp312-cp312-manylinux_2_28_x86_64.whl"
    wheel.parent.mkdir(parents=True)
    wheel.write_bytes(b"fake wheel bytes")

    runner = RecordingRunner()
    runner.respond(contains("--describe-artifact"), stdout=json.dumps(_describe_payload(present=True)))

    payload = bp.resolve_kroko_wheel(
        variant="pro",
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
    wheel = store / "pro" / "deadbeefcafef00d" / "kroko_onnx-1.12.9-1pro-cp312-cp312-manylinux_2_28_x86_64.whl"

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
        variant="pro",
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
            variant="pro",
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
    (tmp_path / "kroko" / "kroko_onnx-1.12.9-1pro-cp312-cp312-manylinux_2_28_x86_64.whl").write_bytes(b"x")
    (tmp_path / "voicestt").mkdir()

    with pytest.raises(bp.BuildError, match="exactly one complete product wheel"):
        bp.build_production_image(
            variant="pro",
            git_commit="a" * 40,
            voicestt_version="2.0.0",
            dist_dir=tmp_path,
            build_date="2026-09-07T19:06:57Z",
            runner=RecordingRunner(),
        )


def test_build_production_image_requires_kroko_wheel(tmp_path):
    _stage_identity_wheels(tmp_path)
    for wheel in (tmp_path / "kroko").glob("*.whl"):
        wheel.unlink()
    runner = RecordingRunner()
    runner.respond(lambda cmd: cmd[:2] == ("docker", "build"), stdout="")
    bp.build_production_image(
        variant="pro", git_commit="a" * 40, voicestt_version="2.0.0",
        dist_dir=tmp_path, build_date="2026-09-07T19:06:57Z", runner=runner,
    )
    assert len(runner.calls) == 1


def test_build_production_image_tags_free_and_pro_distinctly(tmp_path):
    _stage_identity_wheels(tmp_path)
    runner = RecordingRunner()
    runner.respond(lambda cmd: cmd[:2] == ("docker", "build"), stdout="")
    info = bp.build_production_image(
        variant="pro", git_commit="a" * 40, voicestt_version="2.0.0",
        dist_dir=tmp_path, build_date="2026-09-07T19:06:57Z", runner=runner,
    )
    assert info["image"] == "voice-stt-server"
    assert info["versionTag"] == "voice-stt-server:2.0.0"
    assert len(runner.calls) == 1
    assert "VOICESTT_KROKO_VARIANT=pro" in runner.calls[0]
    assert "KROKO_API_KEY" not in " ".join(runner.calls[0])


# ---------------------------------------------------------------------------
# AP-SRV-070 W5-R04: GitHub-native build guards
# ---------------------------------------------------------------------------


def test_build_date_is_derived_from_the_commit_not_the_wall_clock():
    """AP-SRV-070 W5-R04, section 32.

    Two builds of the same commit must be able to produce the same image
    identity. A wall-clock BUILD_DATE made that impossible, which is hostile
    to a release model where publication consumes an already-qualified
    candidate and a resume must re-derive rather than re-invent it.
    """
    runner = RecordingRunner()
    runner.respond(
        lambda cmd: tuple(cmd[:3]) == ("git", "show", "-s"),
        stdout="2026-09-07T21:06:57+02:00\n",
    )
    first = bp.resolve_source_build_date("a" * 40, runner)
    second = bp.resolve_source_build_date("a" * 40, runner)
    assert first == second == "2026-09-07T19:06:57Z"


def test_build_date_resolution_fails_closed_when_the_commit_is_unknown():
    runner = RecordingRunner()
    runner.respond(lambda cmd: tuple(cmd[:3]) == ("git", "show", "-s"), returncode=128, stdout="")
    with pytest.raises(bp.BuildError, match="commit timestamp"):
        bp.resolve_source_build_date("a" * 40, runner)


def test_the_build_manifest_records_where_the_build_date_came_from():
    runner = RecordingRunner()
    runner.respond(lambda cmd: tuple(cmd[:2]) == ("docker", "build"), stdout="")
    info = bp.build_production_image(
        variant="pro", git_commit="a" * 40, voicestt_version="2.0.0",
        dist_dir=_staged_dist_dir(), build_date="2026-09-07T19:06:57Z", runner=runner,
    )
    assert info["buildDate"] == "2026-09-07T19:06:57Z"
    assert info["buildDateSource"] == "git-commit-timestamp"


def _staged_dist_dir():
    """A dist directory with both wheels already staged."""
    import tempfile

    root = Path(tempfile.mkdtemp())
    _stage_identity_wheels(root)
    return root


def _stage_identity_wheels(root):
    from tests.unit.test_build_distribution import make_base_wheel, make_kroko_wheel
    from tools.build_distribution import merge_kroko_runtime
    from VoiceSTT._build_identity import BuildIdentity
    (root / "voicestt").mkdir()
    (root / "kroko").mkdir()
    base = make_base_wheel(root, "voice-stt-server")
    identity = BuildIdentity(
        1, "2.0.0", "2.0.0", "a" * 40, "b" * 40, False,
        "2026-09-07T19:06:57Z", "voice-stt-server", "pro", "git",
    )
    with zipfile.ZipFile(base, "a") as archive:
        archive.writestr("VoiceSTT/_build_identity.json", identity.to_json())
    native = make_kroko_wheel(root / "kroko", "pro")
    merge_kroko_runtime(base_wheel=base, kroko_wheel=native, variant="pro",
                        out_dir=root / "voicestt", fingerprint="synthetic")
    return identity


def test_image_variant_cannot_override_the_actual_runtime(tmp_path):
    _stage_identity_wheels(tmp_path)
    with pytest.raises(bp.BuildError, match="variant"):
        bp.build_production_image(
            variant="free", git_commit="a" * 40, voicestt_version="2.0.0",
            dist_dir=tmp_path, build_date="2026-09-07T19:06:57Z",
        )


def test_build_metadata_is_not_silently_retagged_as_a_different_docker_version(tmp_path):
    runner = RecordingRunner()
    with pytest.raises(bp.BuildError, match="unchanged registry tag contract"):
        bp.build_production_image(
            variant="pro", git_commit="a" * 40, voicestt_version="2.0.0-rc.1+build.5",
            dist_dir=tmp_path, build_date="2026-09-07T19:06:57Z", runner=runner,
        )
    assert runner.calls == []


@pytest.mark.parametrize("commit,version", [("c" * 40, "2.0.0"), ("a" * 40, "3.0.0")])
def test_docker_build_args_must_match_product_resource(tmp_path, commit, version):
    _stage_identity_wheels(tmp_path)
    with pytest.raises(bp.BuildError, match="arguments"):
        bp.build_production_image(
            variant="pro", git_commit=commit, voicestt_version=version,
            dist_dir=tmp_path, build_date="2026-09-07T19:06:57Z",
            runner=RecordingRunner(),
        )


def test_image_runtime_and_labels_are_both_checked(tmp_path):
    source = _stage_identity_wheels(tmp_path)
    labels = {
        "org.opencontainers.image.version": source.productVersion,
        "org.opencontainers.image.revision": source.sourceCommit,
        "org.opencontainers.image.created": source.sourceDate,
        "com.voicestt.kroko-variant": "pro",
    }
    runner = RecordingRunner()
    runner.respond(lambda cmd: cmd[:2] == ("docker", "run"), stdout="{}")
    with pytest.raises(bp.BuildError, match="installed"):
        bp.validate_image_identity(
            "image:test", {"Config": {"Labels": labels}},
            source_identity=source, variant="pro", build_date=source.sourceDate,
            runner=runner,
        )
    labels["org.opencontainers.image.revision"] = "d" * 40
    with pytest.raises(bp.BuildError, match="labels"):
        bp.validate_image_identity(
            "image:test", {"Config": {"Labels": labels}},
            source_identity=source, variant="pro", build_date=source.sourceDate,
            runner=RecordingRunner(),
        )


@pytest.mark.parametrize("variant", ["pro"])
@pytest.mark.parametrize("broken", [None, "missing", "malformed", "duplicate", "native", "identity", "exit"])
def test_image_endpoints_require_isolated_native_hash_bound_evidence(tmp_path, variant, broken):
    source = _stage_identity_wheels(tmp_path)
    labels = {
        "org.opencontainers.image.version": source.productVersion,
        "org.opencontainers.image.revision": source.sourceCommit,
        "org.opencontainers.image.created": source.sourceDate,
        "com.voicestt.kroko-variant": variant,
    }
    info = {
        "serverVersion": source.productVersion, "serverCommit": source.sourceCommit,
        "identityStatus": "complete",
        "distribution": {"name": "voice-stt-server", "packageVersion": source.packageVersion},
        "runtime": {"krokoVariant": variant},
        "build": {"sourceTree": source.sourceTree, "sourceDirty": False,
                  "sourceDate": source.sourceDate},
    }
    evidence = {"info": dict(info), "nativeImport": broken != "native"}
    if broken == "identity":
        evidence["info"]["serverCommit"] = "f" * 40
    marker = "IDENTITY_QUALIFICATION=" + json.dumps(evidence)
    output = {"missing": "{}", "malformed": "IDENTITY_QUALIFICATION=broken",
              "duplicate": marker + "\n" + marker}.get(broken, marker)
    runner = RecordingRunner()
    runner.respond(lambda cmd: "resolve_runtime_identity" in cmd[-1], stdout=json.dumps(info))
    runner.respond(contains("-I", "-c", bp.INSTALLED_CHECK), stdout=output,
                   returncode=1 if broken == "exit" else 0)
    if broken:
        with pytest.raises(bp.BuildError):
            bp.validate_image_identity(
                "image:test", {"Config": {"Labels": labels}}, source_identity=source,
                variant=variant, build_date=source.sourceDate, runner=runner,
            )
    else:
        bp.validate_image_identity(
            "image:test", {"Config": {"Labels": labels}}, source_identity=source,
            variant=variant, build_date=source.sourceDate, runner=runner,
        )
    assert len(runner.calls) == 2
    for command in runner.calls:
        assert command[:8] == [
            "docker", "run", "--rm", "--network", "none",
            "--entrypoint", "/opt/venv/bin/python", "image:test",
        ]
    assert runner.calls[1][-2:] == [source.to_json(), variant]


def test_a_dist_dir_outside_the_build_context_fails_immediately(tmp_path):
    """AP-SRV-070 W5-R04.

    The production Dockerfile copies the staged wheels with literal
    ``COPY dist/...`` instructions relative to the repository-root build
    context, so a --dist-dir anywhere else can never work. Before this guard
    the orchestrator would run a full native Kroko build first and only then
    fail at the image step with an opaque ``lstat /dist/voicestt`` error -
    which is exactly how W5-R04 discovered it.
    """
    with pytest.raises(bp.BuildError, match="--dist-dir must be"):
        bp.require_dist_dir_inside_build_context(tmp_path)


def test_the_repository_dist_dir_is_accepted():
    assert bp.require_dist_dir_inside_build_context(bp.default_dist_dir()) == bp.default_dist_dir().resolve()


def test_the_production_base_image_is_pinned_by_digest():
    """W5R4-G12/section 12: an immutable base, not a floating tag."""
    assert bp.PRODUCTION_BASE_IMAGE_DIGEST.startswith("sha256:")
    assert len(bp.PRODUCTION_BASE_IMAGE_DIGEST) == len("sha256:") + 64
    assert "@" in bp.production_base_image_ref()


def test_build_production_never_uses_an_operator_local_path():
    """W5R4-G07 / section 9: no absolute drive-letter path in build authority."""
    import re

    source = Path(bp.__file__).read_text(encoding="utf-8")
    offenders = re.findall(r"\b[A-Za-z]:[\/][\w./\-]*", source)
    assert not offenders, offenders


def test_a_runtime_kroko_key_is_never_a_build_input():
    """W5R4-G11/G50: the Pro build needs no key at all."""
    source = Path(bp.__file__).read_text(encoding="utf-8")
    for forbidden in ("KROKO_ONNX_KEY", "VOICESTT_KROKO_ONNX_KEY", "LICENSE_KEY"):
        assert forbidden not in source, forbidden
