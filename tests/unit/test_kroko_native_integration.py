"""Opt-in native Kroko integration tests (PR #15 Abschlusskorrektur, T2).

Runs ONLY with ``VOICESTT_KROKO_NATIVE_TESTS=1`` plus

* ``VOICESTT_KROKO_TEST_ENV_FILE``  - local ``KEY=...`` file (never printed),
* ``VOICESTT_KROKO_TEST_MODEL_DIR`` - directory holding the Community DE 64 L
  and the Pro DE 16 L ``.data`` files,
* ``VOICESTT_KROKO_TEST_AUDIO_DE``  - 16 kHz mono German WAV,
* optional ``VOICESTT_KROKO_TEST_EXPECT`` - comma separated words that must
  appear in the transcript (default ``guten,test``).

Every scenario runs in a fresh child interpreter (``kroko_native_child.py``)
so the process-wide native license singleton cannot leak between scenarios,
and a native hang is killed by the timeout. Pro-model-A -> Pro-model-B is
deliberately NOT exercised: it crashes the native runtime and is covered by
the process guard's deterministic tests instead. Missing prerequisites skip
(``NOT_RUN``), they never pass.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ENABLED = os.getenv("VOICESTT_KROKO_NATIVE_TESTS") == "1"

pytestmark = pytest.mark.skipif(
    not ENABLED,
    reason="opt-in native Kroko tests (VOICESTT_KROKO_NATIVE_TESTS=1)",
)

CHILD = Path(__file__).with_name("kroko_native_child.py")


def _require(name):
    value = os.getenv(name, "")
    if not value or not os.path.exists(value):
        pytest.skip(f"{name} is not set to an existing path (NOT_RUN)")
    return value


def _run(scenario, *, key=False, timeout=1200):
    try:
        import kroko_onnx  # noqa: F401
    except Exception:
        pytest.skip("kroko_onnx runtime not installed (NOT_RUN)")
    model_dir = _require("VOICESTT_KROKO_TEST_MODEL_DIR")
    audio = _require("VOICESTT_KROKO_TEST_AUDIO_DE")
    environ = dict(os.environ)
    for name in ("KROKO_ASR_API_KEY", "KROKO_ASR_API_KEY_SECOND",
                 "KROKO_API_KEY", "KROKO_ONNX_KEY", "VOICESTT_KROKO_ONNX_KEY",
                 "KROKO_KEY"):
        environ.pop(name, None)
    environ.update(
        KROKO_NATIVE_MODEL_DIR=model_dir, KROKO_NATIVE_AUDIO=audio,
        KROKO_NATIVE_EXPECT=os.getenv("VOICESTT_KROKO_TEST_EXPECT", "guten,test"),
        VOICESTT_KROKO_MODEL_ROOT="", PYTHONIOENCODING="utf-8",
    )
    secret = ""
    if key:
        key_file = _require("VOICESTT_KROKO_TEST_ENV_FILE")
        environ["KROKO_NATIVE_KEY_FILE"] = key_file
        with open(key_file, "r", encoding="utf-8") as handle:
            secret = handle.read()
    # Optional bounded diagnostic run; an exceeded deadline is FAILED.
    timeout = float(os.getenv("VOICESTT_KROKO_NATIVE_PROCESS_TIMEOUT", str(timeout)))
    completed = subprocess.run(
        [sys.executable, str(CHILD), scenario], capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        timeout=timeout, env=environ, cwd=str(CHILD.parents[2]),
    )
    output = completed.stdout + completed.stderr
    for line in secret.splitlines():
        value = line.partition("=")[2].strip().strip("'\"")
        assert not value or value not in output, "a child leaked the key"
    assert completed.returncode == 0, output[-3000:]
    results = [line[len("RESULT "):] for line in completed.stdout.splitlines()
               if line.startswith("RESULT ")]
    assert results, output[-3000:]
    return json.loads(results[-1])


def test_n1_community_model_in_pro_runtime_without_key():
    result = _run("community_no_key")
    assert result["loaded"] is True
    assert result["text"].strip() and result["hits"]
    assert result["guard"]["nativeProContextActive"] is False


def test_n2_pro_model_with_valid_key():
    result = _run("pro_with_key", key=True)
    assert result["loaded"] is True
    assert result["text"].strip() and result["hits"]
    assert result["guard"]["nativeProContextActive"] is True


def test_n3_one_pro_instance_serves_final_and_realtime():
    result = _run("pro_shared_final_realtime", key=True)
    assert result["ready"] is True and result["sharedInstance"] is True
    assert result["errors"] == []
    assert set(result["texts"]) == {"final", "realtime"}
    assert all(text.strip() for text in result["texts"].values())
    assert all(result["hits"].values())
    assert result["guard"]["nativeProContextActive"] is True


def test_n4_productive_community_pro_community_switch():
    result = _run("service_community_pro_switch", key=True, timeout=2400)
    steps = {step["step"]: step for step in result["steps"]}
    start = steps["community_start"]
    assert start["hits"] and set(start["active"].values()) == {"kroko-de-community-64-l"}
    assert start["runtime"]["activeProPresent"] is False

    pro = steps["switched_to_pro"]
    assert pro["hits"] and set(pro["active"].values()) == {"kroko-de-pro-16-l"}
    assert pro["runtime"]["activeProPresent"] is True
    assert pro["runtime"]["liveNativeInstances"] == 1
    assert pro["final"].strip() and pro["realtime"].strip()

    assert steps["force_community_locked"]["refusedImmediately"] is True
    forced = steps["force_community_done"]
    assert forced["reconcile"] == "changed" and forced["hits"]
    assert set(forced["active"].values()) == {"kroko-de-community-64-l"}
    assert forced["runtime"]["activeProPresent"] is False
    # Honest native status: the Pro license context still exists.
    assert forced["runtime"]["nativeProContextActive"] is True
    assert forced["runtime"]["restartRequired"] is False

    again = steps["pro_again"]
    assert again["hits"] and set(again["active"].values()) == {"kroko-de-pro-16-l"}
    assert again["runtime"]["liveNativeInstances"] == 1
    # The provider rejects a further external check while the native reporter
    # is alive; the confirmed native context is the evidence for the same
    # model and key.
    assert again["runtime"]["licenseSource"] == "native_context"
