"""AP-KR-010 only: audit qualified embedded payloads and probe in fresh processes.

No license requests: keys are removed and only a hash-verified Community model
may be supplied. --child is internal. Outputs belong outside the repository.
"""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import zipfile


KEYS = ("KROKO_API_KEY", "KROKO_ONNX_KEY", "VOICESTT_KROKO_ONNX_KEY", "KROKO_KEY")
PREFIXES = ("kroko_onnx/", "sherpa_onnx/", "kroko_onnx.libs/")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def payload_name(name):
    if ".data/platlib/" in name:
        return True
    return name.startswith(PREFIXES) or (
        "/" not in name and (name.endswith((".pyd", ".dll", ".so", ".lib")) or ".so." in name)
    )


def audit(rc, out):
    checked = 0
    for row in json.loads((rc / "sha256-inventory.json").read_text())["files"]:
        path = rc / row["path"]
        data = path.read_bytes()
        assert len(data) == row["bytes"] and digest(data) == row["sha256"], row["path"]
        checked += 1
    result = {"inventoryVerified": checked, "wheels": [], "collisions": {}}
    payloads = {}
    for wheel in sorted((rc / "dist").glob("*.whl")):
        variant = "pro" if "server_pro-" in wheel.name else "free"
        target = "windows" if "win_amd64" in wheel.name else "linux"
        root = out / target / variant
        root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(wheel) as z:
            manifest = json.loads(z.read("voice_stt_server/_embedded_kroko.json"))
            assert manifest["variant"] == variant
            payload = {n: z.read(n) for n in z.namelist() if payload_name(n) and not n.endswith("/")}
            assert payload and "kroko_onnx/__init__.py" in payload
            installed = {}
            for name, data in payload.items():
                # Wheel installers spread .data/platlib into site-packages.
                relative = name.split(".data/platlib/", 1)[-1]
                assert relative not in installed
                installed[relative] = data
                dest = root / relative
                assert dest.resolve().is_relative_to(root.resolve())
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
            payloads[target, variant] = installed
            result["wheels"].append({"filename": wheel.name, "sha256": digest(wheel.read_bytes()),
                "payloadFiles": len(payload), "native": manifest["kroko"],
                "binaryFiles": [n for n in payload if n.endswith((".pyd", ".dll", ".so")) or ".so." in n],
                "licenses": [n for n in z.namelist() if "/licenses/" in n.lower()]})
    for target in ("linux", "windows"):
        a, b = payloads[target, "free"], payloads[target, "pro"]
        common = sorted(set(a) & set(b))
        result["collisions"][target] = {"samePath": len(common),
            "differentBytes": [n for n in common if a[n] != b[n]]}
    return result


def child(args):
    assert not any(os.environ.get(k) for k in KEYS)
    root = args.root.resolve()
    sys.path.insert(0, str(root))
    k = importlib.import_module("kroko_onnx")
    native = importlib.import_module("_sherpa_onnx")
    assert Path(k.__file__).resolve().is_relative_to(root)
    assert Path(native.__file__).resolve().is_relative_to(root)
    result = {"python": platform.python_version(), "machine": platform.machine(),
        "module": str(Path(k.__file__).relative_to(root)),
        "extension": str(Path(native.__file__).relative_to(root)),
        "licenseApis": [n for n in dir(native) if any(s in n.lower() for s in ("license", "validat", "entitle"))]}
    if args.second:
        sys.path.insert(0, str(args.second.resolve()))
        again = importlib.import_module("kroko_onnx")
        result["pathSwitchKeptOriginal"] = again is k and importlib.import_module("_sherpa_onnx") is native
        assert result["pathSwitchKeptOriginal"]
    print(json.dumps({"importReady": True}), flush=True)
    if args.model or args.bad:
        model = args.model or args.bad
        recognizer = k.OnlineRecognizer.from_transducer(model_path=str(model), key="", num_threads=1, provider="cpu")
        result["recognizerCreated"] = True
        if not args.bad:
            import numpy as np
            stream = recognizer.create_stream()
            stream.accept_waveform(16000, np.zeros(16000, dtype=np.float32))
            stream.input_finished()
            while recognizer.is_ready(stream):
                recognizer.decode_stream(stream)
            result["silenceDecoded"] = True
            result["silenceTextEmpty"] = not recognizer.get_result(stream).strip()
    print(json.dumps(result), flush=True)


def probes(args):
    assert sys.version_info[:2] == (3, 12)
    if args.model:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        entries = [r for r in manifest["models"] if r["filename"] == args.model.name and r["tier"] == "community"]
        assert len(entries) == 1, "only manifested Community models allowed"
        data = args.model.read_bytes()
        assert len(data) == entries[0]["bytes"] and digest(data) == entries[0]["sha256"]
    env = {k: v for k, v in os.environ.items() if k not in KEYS and k not in ("PYTHONPATH", "PYTHONHOME")}
    env["KROKO_ONNX_SUPPRESS_LICENSE_OUTPUT"] = "1"
    env["OMP_NUM_THREADS"] = "1"
    bad = args.out / "invalid-header.fixture"
    args.out.mkdir(parents=True, exist_ok=True)
    bad.write_bytes(b"AP-KR-010 invalid header fixture\n")
    result = {"platform": platform.platform(), "cases": []}
    cases = [("free-import", "free", None), ("pro-import", "pro", None),
        ("free-pro-path", "free", "pro"), ("pro-free-path", "pro", "free")]
    if args.model:
        cases += [("free-init", "free", "model"), ("pro-community-init", "pro", "model")]
    cases += [("pro-fatal-header", "pro", "bad")]
    if args.model:
        cases += [("free-after-failure", "free", "model"), ("pro-after-free", "pro", "model")]
    for name, variant, mode in cases:
        cmd = [sys.executable, "-I", str(Path(__file__).resolve()), "child", "--root", str(args.root / variant)]
        if mode in ("free", "pro"):
            cmd += ["--second", str(args.root / mode)]
        elif mode == "model":
            cmd += ["--model", str(args.model)]
        elif mode == "bad":
            cmd += ["--bad", str(bad)]
        try:
            run = subprocess.run(cmd, env=env, capture_output=True, timeout=45)
            row = {"case": name, "exit": run.returncode,
                "stdout": run.stdout.decode(errors="replace"), "stderr": run.stderr.decode(errors="replace")}
        except subprocess.TimeoutExpired:
            row = {"case": name, "timeout": True}
        result["cases"].append(row)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("audit", "probes", "child"))
    for key in ("rc", "out", "root", "second", "model", "manifest", "bad"):
        parser.add_argument("--" + key, type=Path)
    args = parser.parse_args()
    if args.action == "child":
        child(args)
        return
    result = audit(args.rc, args.out) if args.action == "audit" else probes(args)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / (args.action + ".json")).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if args.action == "probes":
        assert all((r.get("exit") == 1 and '"importReady": true' in r["stdout"] and "Traceback" not in r["stderr"]
            if r["case"] == "pro-fatal-header" else r.get("exit") == 0) for r in result["cases"])


if __name__ == "__main__":
    main()
