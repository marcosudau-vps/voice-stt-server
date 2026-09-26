"""Conservative, read-only registry tag classification for V1 publication.

The CLI prints ABSENT or MATCH only when it can prove that state. Every
unclear result exits nonzero before the caller can write a registry tag.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass


DIGEST = re.compile(r"^Digest:\s*(sha256:[0-9a-f]{64})\s*$", re.MULTILINE)
EXPLICIT_ABSENCE = re.compile(
    r"(?:ERROR:\s+.+:\s+not found|(?:ERROR:\s+.+:\s+)?manifest unknown(?::.*)?)",
    re.IGNORECASE,
)
UNSAFE_FAILURE = re.compile(
    r"\b(?:unauthori[sz]ed|denied|forbidden|timeout|timed out|"
    r"connection|rate.?limit|too many requests|toomanyrequests|"
    r"deadline exceeded|certificate|tls|"
    r"401|403|429|5\d\d)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ProbeResult:
    state: str
    actual: str | None = None
    reason: str = ""


def classify(returncode: int, stdout: str, stderr: str, expected: str) -> ProbeResult:
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", expected):
        raise ValueError("expected digest must be lowercase sha256:<64 hex>")
    if UNSAFE_FAILURE.search(stderr):
        return ProbeResult("UNKNOWN", reason="registry authentication, transport, or server failure")
    if returncode == 0:
        digests = DIGEST.findall(stdout)
        if len(digests) != 1:
            return ProbeResult("UNKNOWN", reason="successful inspect lacked one top-level digest")
        actual = digests[0]
        return ProbeResult("MATCH" if actual == expected else "CONFLICT", actual=actual)
    if EXPLICIT_ABSENCE.fullmatch(stderr.strip()):
        return ProbeResult("ABSENT")
    return ProbeResult("UNKNOWN", reason="inspect failed without explicit tag absence")


def probe(reference: str, expected: str) -> ProbeResult:
    completed = subprocess.run(
        ["docker", "buildx", "imagetools", "inspect", reference],
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )
    return classify(completed.returncode, completed.stdout, completed.stderr, expected)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference")
    parser.add_argument("expected_digest")
    parser.add_argument("--require-match", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = probe(args.reference, args.expected_digest)
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        print(f"UNKNOWN {args.reference}: {exc}", file=sys.stderr)
        return 2
    if result.state in {"CONFLICT", "UNKNOWN"} or (
        args.require_match and result.state != "MATCH"
    ):
        print(
            f"{result.state} {args.reference}: actual={result.actual or '-'} "
            f"expected={args.expected_digest} {result.reason}",
            file=sys.stderr,
        )
        return 2
    print(result.state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
