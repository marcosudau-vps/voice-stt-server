"""Opt-in real Kroko license-server integration tests (PR #15 Korrekturlauf, D2).

Runs ONLY with ``VOICESTT_KROKO_LIVE_TESTS=1`` plus:
  ``VOICESTT_KROKO_TEST_ENV_FILE`` - path to a local ``KEY=...`` env file
      (read at runtime, never committed, never printed), and
  ``VOICESTT_KROKO_LIVE_MODEL`` - path to a local licensed Pro ``.data`` file
      whose header UUID is the technical model identity under test.

Key*)
Do not run these from ordinary CI: every positive/negative check below opens
a real WebSocket to the Kroko license service. Connection counts are kept
minimal and documented (R1:1, R2:1, R4:1; R3 uses the native runtime path).

*) ``KROKO_ASR_API_KEY``/``KROKO_ASR_API_KEY_SECOND`` are the VPS secret names;
any ``NAME=value`` entry of the env file works - the test passes the loaded
value explicitly via engine options, which is a supported key source.
"""
import json
import os
import subprocess
import sys

import pytest

LIVE = os.getenv("VOICESTT_KROKO_LIVE_TESTS") == "1"

pytestmark = pytest.mark.skipif(
    not LIVE,
    reason="opt-in live Kroko license tests "
           "(VOICESTT_KROKO_LIVE_TESTS=1 with key env file and Pro model)",
)


def load_key(env_file):
    values = {}
    with open(env_file, "r", encoding="utf-8") as handle:
        for line in handle.read().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            values[name.strip()] = value.strip().strip("'\"")
    for name in ("KROKO_ASR_API_KEY", "KROKO_ASR_API_KEY_SECOND",
                 "KROKO_API_KEY", "KROKO_ONNX_KEY",
                 "VOICESTT_KROKO_ONNX_KEY", "KROKO_KEY"):
        if values.get(name):
            return values[name]
    raise AssertionError(
        "live env file contains none of the supported Kroko key variables")


@pytest.fixture(scope="module")
def live_key():
    env_file = os.getenv("VOICESTT_KROKO_TEST_ENV_FILE", "")
    if not env_file or not os.path.isfile(env_file):
        pytest.skip("VOICESTT_KROKO_TEST_ENV_FILE missing: no key available")
    return load_key(env_file)


@pytest.fixture(scope="module")
def live_model():
    model = os.getenv("VOICESTT_KROKO_LIVE_MODEL", "")
    if not model or not os.path.isfile(model):
        pytest.skip("VOICESTT_KROKO_LIVE_MODEL missing: no Pro model file")
    return model


@pytest.fixture(scope="module")
def live_uuid(live_model):
    from VoiceSTT.kroko.models import read_model_uuid
    uuid = read_model_uuid(live_model)
    if not uuid:
        pytest.skip("Pro model file carries no header UUID")
    return uuid


def counting_connect(counter):
    import websocket

    real_create = websocket.create_connection

    def connect(url, timeout=None):
        counter[0] += 1
        assert url.startswith("wss://license.kroko.ai/ws/v1/"), \
            "unexpected license endpoint"
        return real_create(url, timeout=timeout)

    return connect


def assert_no_secret_leak(*objects):
    blob = repr(objects)
    for name in ("KROKO_ASR_API_KEY", "KROKO_API_KEY", "KROKO_ONNX_KEY",
                 "KROKO_KEY", "wss://license.kroko.ai/ws/v1/"):
        assert name not in blob


def test_r1_positive_license_check(live_key, live_uuid):
    """R1: real positive check for the header UUID of a licensed Pro model."""
    from api_fastapi_server.security.kroko import KrokoLicenseGate
    gate = KrokoLicenseGate()
    counter = [0]
    decision, started = gate.refresh(
        live_uuid, options={"key": live_key},
        connect=counting_connect(counter), timeout=10.0,
    )
    assert started is True
    assert counter[0] == 1
    assert decision["tier"] == "pro", decision
    assert decision["model_uuid"] == live_uuid
    assert gate.state.pro_enabled_for(live_uuid) is True
    snapshot = gate.state.public_snapshot()
    assert snapshot["status"] == "VALID"
    assert_no_secret_leak(decision, snapshot)
    assert live_key not in json.dumps(decision, default=str)
    assert live_key not in json.dumps(snapshot, default=str)


def test_r2_invalid_key_grants_nothing(live_uuid):
    """R2: one deliberately invalid key must not produce any grant."""
    from api_fastapi_server.security.kroko import KrokoLicenseGate
    gate = KrokoLicenseGate()
    counter = [0]
    decision, started = gate.refresh(
        live_uuid, options={"key": "live-invalid-test-key"},
        connect=counting_connect(counter), timeout=10.0,
    )
    assert started is True
    assert counter[0] == 1
    assert decision["tier"] == "community"
    assert gate.state.pro_enabled_for(live_uuid) is False
    assert gate.state.public_snapshot()["status"] in ("INVALID", "CHECK_FAILED")


def test_r3_model_integration_smoke(live_key, live_model, live_uuid, tmp_path):
    """R3: licensed model loads in the installed runtime (separate process).

    Runs the native load + a short deterministic transcription in a child
    process so the native Kroko singletons stay isolated. The child prints a
    redacted JSON summary only.
    """
    try:
        import kroko_onnx  # noqa: F401 - establishes "runtime installed"
    except Exception:
        pytest.skip("kroko_onnx runtime not installed in this environment")
    audio = os.path.join(os.path.dirname(__file__), "audio",
                         "asr-reference-short.wav")
    if not os.path.isfile(audio):
        pytest.skip("no local test audio available")
    script = (
        "import json, os, sys;"
        "sys.path.insert(0, %r);"
        "from VoiceSTT.transcription_engines.kroko_onnx_engine import KrokoOnnxBackend;"
        "from VoiceSTT.transcription_engines import TranscriptionEngineConfig;"
        "import wave;"
        "key = open(os.environ['VOICESTT_KROKO_LIVE_KEY_FILE'], encoding='utf-8').read().split('=', 1)[1].strip();"
        "backend = KrokoOnnxBackend(TranscriptionEngineConfig(model=%r, engine_options={'key': key, 'provider': 'cpu', 'num_threads': 1}));"
        "wav = wave.open(%r, 'rb');"
        "frames = wav.readframes(wav.getnframes());"
        "import numpy;"
        "samples = (numpy.frombuffer(frames, dtype=numpy.int16).astype(numpy.float32) / 32768.0)[:16000 * 8];"
        "result = backend.transcribe(list(samples), language='en');"
        "print(json.dumps({'loaded': True, 'textChars': len(result.text or ''), 'hasText': bool((result.text or '').strip())}))"
    ) % (os.getcwd(), live_model, audio)
    key_file = tmp_path / "live_key.txt"
    key_file.write_text("KROKO_LIVE_KEY=" + live_key, encoding="utf-8")
    try:
        child_env = dict(os.environ)
        child_env["VOICESTT_KROKO_LIVE_KEY_FILE"] = str(key_file)
        completed = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True,
            timeout=300, env=child_env, cwd=os.getcwd(),
        )
    finally:
        try:
            key_file.unlink()
        except OSError:
            pass
    assert live_key not in (completed.stdout + completed.stderr), \
        "child process leaked the key"
    assert completed.returncode == 0, completed.stderr[-2000:]
    summary = json.loads(completed.stdout.strip().splitlines()[-1])
    assert summary["loaded"] is True
    assert summary["hasText"] is True


def test_r4_grant_revoked_by_force_and_removal(live_key, live_uuid):
    """R4: force community / key removal revoke a real grant (no extra net)."""
    from api_fastapi_server.security.kroko import KrokoLicenseGate
    gate = KrokoLicenseGate()
    counter = [0]
    decision, _started = gate.refresh(
        live_uuid, options={"key": live_key},
        connect=counting_connect(counter), timeout=10.0,
    )
    assert decision["tier"] == "pro"
    assert counter[0] == 1
    gate.state.bind(key=live_key, force_community=True)
    assert gate.state.pro_enabled_for(live_uuid) is False
    assert counter[0] == 1, "revocation must not contact the network"
    gate.state.bind(key="", force_community=False)
    assert gate.state.pro_enabled_for(live_uuid) is False
    assert gate.state.public_snapshot()["status"] == "NOT_CHECKED"


def test_r3b_community_model_loads_without_key(tmp_path):
    """R3b (H-06): a Community model loads without any key on this runtime.

    Runs only with ``VOICESTT_KROKO_PRO_RUNTIME_TESTS=1`` on a machine with a
    Pro-capable runtime installed; proves the eligibility direction
    (Community usable under a Pro install) with a real native load. Separate
    child process, no key involved at all.
    """
    if os.getenv("VOICESTT_KROKO_PRO_RUNTIME_TESTS") != "1":
        pytest.skip("needs VOICESTT_KROKO_PRO_RUNTIME_TESTS=1 on a Pro runtime")
    community = os.getenv("VOICESTT_KROKO_COMMUNITY_MODEL", "")
    if not community or not os.path.isfile(community):
        pytest.skip("VOICESTT_KROKO_COMMUNITY_MODEL missing")
    try:
        import kroko_onnx  # noqa: F401
    except Exception:
        pytest.skip("kroko_onnx runtime not installed in this environment")
    script = (
        "import json, sys;"
        "sys.path.insert(0, %r);"
        "from VoiceSTT.transcription_engines.kroko_onnx_engine import KrokoOnnxBackend;"
        "from VoiceSTT.transcription_engines import TranscriptionEngineConfig;"
        "backend = KrokoOnnxBackend(TranscriptionEngineConfig(model=%r, engine_options={'provider': 'cpu', 'num_threads': 1}));"
        "print(json.dumps({'loaded': True}))"
    ) % (os.getcwd(), community)
    completed = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        timeout=300, cwd=os.getcwd(),
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
    summary = json.loads(completed.stdout.strip().splitlines()[-1])
    assert summary["loaded"] is True
