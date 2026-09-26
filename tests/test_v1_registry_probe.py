from __future__ import annotations

import subprocess
from unittest.mock import patch

from tools.v1_registry_probe import classify, main


DIGEST = "sha256:" + "a" * 64
OTHER = "sha256:" + "b" * 64


def test_match_and_conflict():
    assert classify(0, f"Name: image\nDigest: {DIGEST}\n", "", DIGEST).state == "MATCH"
    result = classify(0, f"Digest: {OTHER}\n", "", DIGEST)
    assert (result.state, result.actual) == ("CONFLICT", OTHER)


def test_explicit_missing_tag_only():
    assert classify(1, "", "ERROR: docker.io/a/b:1.0.0: not found\n", DIGEST).state == "ABSENT"
    assert classify(1, "", "manifest unknown: manifest unknown", DIGEST).state == "ABSENT"


def test_ambiguous_failures_never_become_absent():
    for error in (
        "unauthorized: access denied",
        "403 Forbidden: manifest unknown",
        "429 Too Many Requests: not found",
        "toomanyrequests: manifest unknown",
        "connection timeout",
        "unexpected failure",
        "manifest unknown\nextra unexplained error",
        "",
    ):
        assert classify(1, "", error, DIGEST).state == "UNKNOWN"
    assert classify(0, f"Digest: {DIGEST}\n", "warning: unauthorized", DIGEST).state == "UNKNOWN"
    assert classify(0, "inspect succeeded without digest", "", DIGEST).state == "UNKNOWN"
    assert classify(0, f"Digest: {DIGEST}\nDigest: {OTHER}\n", "", DIGEST).state == "UNKNOWN"


def test_cli_stops_unknown_and_absent_when_match_required(capsys):
    with patch("tools.v1_registry_probe.subprocess.run") as run:
        run.return_value = subprocess.CompletedProcess([], 1, "", "connection timeout")
        assert main(["image:1.0.0", DIGEST]) == 2
        run.return_value = subprocess.CompletedProcess([], 1, "", "ERROR: image:1.0.0: not found")
        assert main(["image:1.0.0", DIGEST, "--require-match"]) == 2
        assert main(["image:1.0.0", DIGEST]) == 0
    assert "ABSENT" in capsys.readouterr().out
