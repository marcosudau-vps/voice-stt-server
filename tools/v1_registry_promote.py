"""Promote a qualified V1 image without silently changing its manifest digest.

The single-child wrapper exception is limited to repairing the Docker Hub Free
tag written by the interrupted first publish run. All other conflicts stop.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

from tools.v1_registry_probe import probe


def exact_single_child_wrapper(raw: str, expected: str) -> bool:
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError:
        return False
    if manifest.get("mediaType") not in {
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.index.v1+json",
    }:
        return False
    children = manifest.get("manifests")
    if not isinstance(children, list) or len(children) != 1:
        return False
    child = children[0]
    return (
        child.get("digest") == expected
        and child.get("mediaType")
        in {
            "application/vnd.docker.distribution.manifest.v2+json",
            "application/vnd.oci.image.manifest.v1+json",
        }
        and child.get("platform") == {"architecture": "amd64", "os": "linux"}
    )


def promote(reference: str, source: str, expected: str, repair_wrapper: bool) -> str:
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", expected):
        raise ValueError("invalid expected digest")
    state = probe(reference, expected)
    if state.state == "MATCH":
        return "MATCH"
    if state.state == "CONFLICT" and repair_wrapper:
        raw = subprocess.run(
            ["docker", "buildx", "imagetools", "inspect", reference, "--raw"],
            capture_output=True,
            text=True,
            check=True,
            timeout=90,
        ).stdout
        if not exact_single_child_wrapper(raw, expected):
            raise RuntimeError(f"unrelated registry conflict at {reference}")
        # The image manifest is already present in the destination registry.
        source = reference.rsplit(":", 1)[0] + "@" + expected
    elif state.state != "ABSENT":
        raise RuntimeError(f"unsafe registry state {state.state} at {reference}")
    subprocess.run(
        ["docker", "buildx", "imagetools", "create", "--prefer-index=false", "--tag", reference, source],
        check=True,
        timeout=600,
    )
    verified = probe(reference, expected)
    if verified.state != "MATCH":
        raise RuntimeError(f"promotion did not preserve expected digest at {reference}: {verified.state}")
    return "MATCH"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference")
    parser.add_argument("source")
    parser.add_argument("expected")
    parser.add_argument("--repair-single-child-wrapper", action="store_true")
    args = parser.parse_args()
    try:
        print(promote(args.reference, args.source, args.expected, args.repair_single_child_wrapper))
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"PROMOTION STOPPED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
