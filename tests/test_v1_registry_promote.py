from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from tools.v1_registry_probe import ProbeResult
from tools.v1_registry_promote import exact_single_child_wrapper, promote


DIGEST = "sha256:" + "a" * 64
OTHER = "sha256:" + "b" * 64
DEST = "docker.io/example/image:1.0.0"
SOURCE = "ghcr.io/example/image@" + DIGEST


def wrapper(child: str = DIGEST, platform: dict[str, str] | None = None) -> str:
    return json.dumps(
        {
            "mediaType": "application/vnd.docker.distribution.manifest.list.v2+json",
            "manifests": [
                {
                    "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                    "digest": child,
                    "platform": platform or {"architecture": "amd64", "os": "linux"},
                }
            ],
        }
    )


def test_wrapper_requires_exact_single_expected_linux_image():
    assert exact_single_child_wrapper(wrapper(), DIGEST)
    assert not exact_single_child_wrapper(wrapper(OTHER), DIGEST)
    assert not exact_single_child_wrapper(wrapper(platform={"architecture": "arm64", "os": "linux"}), DIGEST)
    assert not exact_single_child_wrapper("{}", DIGEST)
    assert not exact_single_child_wrapper("not JSON", DIGEST)
    two = json.loads(wrapper())
    two["manifests"].append(two["manifests"][0])
    assert not exact_single_child_wrapper(json.dumps(two), DIGEST)


def test_absent_promotion_uses_carbon_copy_and_requires_match():
    with patch("tools.v1_registry_promote.probe", side_effect=[ProbeResult("ABSENT"), ProbeResult("MATCH")]), patch(
        "tools.v1_registry_promote.subprocess.run"
    ) as run:
        assert promote(DEST, SOURCE, DIGEST, False) == "MATCH"
    assert run.call_args.args[0] == [
        "docker", "buildx", "imagetools", "create", "--prefer-index=false", "--tag", DEST, SOURCE
    ]


def test_conflict_repairs_only_expected_wrapper():
    with patch("tools.v1_registry_promote.probe", side_effect=[ProbeResult("CONFLICT", OTHER), ProbeResult("MATCH")]), patch(
        "tools.v1_registry_promote.subprocess.run"
    ) as run:
        run.return_value.stdout = wrapper()
        assert promote(DEST, SOURCE, DIGEST, True) == "MATCH"
    assert run.call_args.args[0][-1] == "docker.io/example/image@" + DIGEST


@pytest.mark.parametrize("state", ["CONFLICT", "UNKNOWN"])
def test_unapproved_conflicts_never_write(state: str):
    with patch("tools.v1_registry_promote.probe", return_value=ProbeResult(state, OTHER)), patch(
        "tools.v1_registry_promote.subprocess.run"
    ) as run:
        with pytest.raises(RuntimeError):
            promote(DEST, SOURCE, DIGEST, False)
    run.assert_not_called()


def test_failed_verification_after_push_stops():
    with patch("tools.v1_registry_promote.probe", side_effect=[ProbeResult("ABSENT"), ProbeResult("CONFLICT", OTHER)]), patch(
        "tools.v1_registry_promote.subprocess.run"
    ):
        with pytest.raises(RuntimeError, match="did not preserve"):
            promote(DEST, SOURCE, DIGEST, False)
