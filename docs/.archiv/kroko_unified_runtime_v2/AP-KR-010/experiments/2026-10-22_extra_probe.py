"""AP-KR-010 experimental wheels, NOT product/release builds.

Synthetic server metadata plus byte-identical real payloads. Uses an isolated
venv, local wheelhouse and no-index resolution; never uploads or compiles.
"""
import argparse
import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import sysconfig
import venv
import zipfile


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts}


def wheel(out, root, name, package, tag, extra=False):
    info = name + "-0.0.0.dist-info"
    entries = {package + "/__init__.py": b'"""Investigation fixture; no automatic native import."""\n'}
    for p in root.rglob("*"):
        if p.is_file() and "__pycache__" not in p.parts:
            entries[package + "/payload/" + p.relative_to(root).as_posix()] = p.read_bytes()
    metadata = f"Metadata-Version: 2.1\nName: {name.replace('_', '-')}\nVersion: 0.0.0\nRequires-Python: >=3.12,<3.13\n"
    if extra:
        metadata += 'Provides-Extra: kroko-pro\nRequires-Dist: voice-stt-kroko-pro==0.0.0; extra == "kroko-pro"\n'
    else:
        metadata += 'Requires-Dist: voice-stt-server==0.0.0\n'
    entries[info + "/METADATA"] = (metadata + "\nExperimental fixture only.\n").encode()
    entries[info + "/WHEEL"] = f"Wheel-Version: 1.0\nGenerator: AP-KR-010-experiment\nRoot-Is-Purelib: false\nTag: {tag}\n".encode()
    rows = []
    for path, data in entries.items():
        encoded = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        rows.append((path, "sha256=" + encoded, len(data)))
    rows.append((info + "/RECORD", "", ""))
    buf = io.StringIO(newline="")
    csv.writer(buf, lineterminator="\n").writerows(rows)
    entries[info + "/RECORD"] = buf.getvalue().encode()
    path = out / f"{name}-0.0.0-{tag}.whl"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for key, data in sorted(entries.items()):
            z.writestr(key, data)
    return path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--probe", type=Path, required=True)
    args = p.parse_args()
    assert sys.version_info[:2] == (3, 12)
    args.out.mkdir(parents=True, exist_ok=True)
    tag = "cp312-cp312-" + ("win_amd64" if sys.platform == "win32" else "linux_x86_64")
    wheel(args.out, args.root / "free", "voice_stt_server", "ap010_free_runtime", tag, extra=True)
    wheel(args.out, args.root / "pro", "voice_stt_kroko_pro", "ap010_pro_runtime", tag)
    envroot = args.out / "venv"
    assert not envroot.exists(), "use a new external output directory per run"
    venv.EnvBuilder(with_pip=True).create(envroot)
    py = envroot / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

    def run(*cmd):
        r = subprocess.run([str(py), *map(str, cmd)], capture_output=True, timeout=120)
        assert r.returncode == 0, r.stderr.decode(errors="replace")
        return r.stdout.decode(errors="replace")

    # NumPy is the only external Python dependency needed by these wrappers.
    run("-m", "pip", "install", "numpy")
    site = Path(run("-c", "import sysconfig; print(sysconfig.get_path('platlib'))").strip())
    run("-m", "pip", "install", "--no-index", "--find-links", args.out, "voice-stt-server==0.0.0")
    assert not (site / "ap010_pro_runtime").exists()
    free = site / "ap010_free_runtime/payload"
    before = hashes(free)
    assert before == hashes(args.root / "free")
    run("-m", "pip", "install", "--no-index", "--find-links", args.out, "voice-stt-server[kroko_pro]==0.0.0")
    pro = site / "ap010_pro_runtime/payload"
    assert hashes(pro) == hashes(args.root / "pro")
    for root in (free, pro):
        run("-I", args.probe.resolve(), "child", "--root", root)
    run("-m", "pip", "check")
    run("-m", "pip", "uninstall", "-y", "voice-stt-kroko-pro")
    assert before == hashes(free) and not pro.exists()
    run("-I", args.probe.resolve(), "child", "--root", free)
    run("-m", "pip", "check")
    report = {"tag": tag, "baseOnlyHasNoPro": True, "extraResolvedOffline": True,
        "payloadsByteIdentical": True, "freshNativeImports": 3, "pipCheck": True,
        "uninstallProPreservesFree": True, "scope": "synthetic server metadata, real native payloads"}
    (args.out / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
