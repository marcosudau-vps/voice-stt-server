"""Assemble the four public V1 product wheels from VoiceSTT + Kroko runtime.

The final wheel directly embeds every non-dist-info payload file from exactly
one Kroko native wheel. There is no wheel-in-wheel installation and no runtime
pip invocation. The final wheel receives the Kroko wheel's CPython/ABI/platform
tag and a rebuilt RECORD.
"""
from __future__ import annotations

import argparse
import base64
import csv
import email
import hashlib
import io
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.0.0"
DISTRIBUTIONS = {"free": "voice-stt-server", "pro": "voice-stt-server-pro"}
PLATFORMS = {"linux_x86_64", "win_amd64"}
SERVER_REQUIREMENTS = [
    "fastapi>=0.115", "uvicorn[standard]>=0.30", "python-multipart",
    "sse-starlette", "httpx", "PyYAML>=6.0", "tzdata", "numpy",
]
CREDENTIAL_PATTERNS = {
    "pypi-token": re.compile(rb"pypi-[A-Za-z0-9_-]{20,}"),
    "github-token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"),
    "openai-style-token": re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),
}

class ProductWheelError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _record_hash(data: bytes) -> str:
    value = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode("ascii").rstrip("=")
    return "sha256=" + value


def _wheel_tags(wheel: Path) -> list[str]:
    with zipfile.ZipFile(wheel) as zf:
        wheel_name = next(n for n in zf.namelist() if n.endswith(".dist-info/WHEEL"))
        text = zf.read(wheel_name).decode("utf-8")
    return [line.split(":", 1)[1].strip() for line in text.splitlines() if line.startswith("Tag:")]


def parse_native_tag(kroko_wheel: Path, platform: str) -> tuple[str, str, str]:
    if platform not in PLATFORMS:
        raise ProductWheelError(f"unsupported target platform {platform!r}")
    tags = _wheel_tags(kroko_wheel)
    candidates = []
    for tag in tags:
        parts = tag.split("-")
        if len(parts) == 3 and parts[0] == "cp312" and parts[2] == platform:
            candidates.append(tuple(parts))
    if not candidates:
        raise ProductWheelError(f"Kroko wheel {kroko_wheel.name} does not expose cp312/*/{platform}; tags={tags}")
    python_tag, abi_tag, platform_tag = candidates[0]
    if abi_tag == "none":
        raise ProductWheelError("native Kroko wheel unexpectedly advertises ABI 'none'")
    return python_tag, abi_tag, platform_tag


def _build_base_wheel(temp: Path) -> Path:
    out = temp / "base"; out.mkdir()
    subprocess.run([sys.executable, "-m", "build", "--wheel", "--outdir", str(out)], cwd=ROOT, check=True)
    wheels = list(out.glob("*.whl"))
    if len(wheels) != 1:
        raise ProductWheelError(f"expected one base VoiceSTT wheel, got {wheels}")
    return wheels[0]


def _metadata_bytes(raw: bytes, distribution: str) -> bytes:
    text = raw.decode("utf-8")
    header, _sep, body = text.partition("\n\n")
    lines = []; existing = set()
    for line in header.splitlines():
        if line.startswith("Name:"):
            line = f"Name: {distribution}"
        if line.startswith("Requires-Dist:"):
            existing.add(line.split(":", 1)[1].strip().lower())
        lines.append(line)
    for req in SERVER_REQUIREMENTS:
        if req.lower() not in existing:
            lines.append("Requires-Dist: " + req)
    guide = (
        "\n\nV1.0.0 published-wheel install:\n\n"
        f"    pip install {distribution}\n\n"
        "The matching Kroko native runtime is embedded in this platform wheel. "
        "No separate Kroko wheel/build is required for normal consumers. Kroko "
        ".data model files remain separate. Source developers may still use "
        "stt-install-kroko --build.\n"
    )
    return ("\n".join(lines) + "\n\n" + body + guide).encode("utf-8")


def _copy_kroko_payload(zf: zipfile.ZipFile, files: dict[str, bytes]) -> list[str]:
    licenses = []
    for name in zf.namelist():
        if name.endswith("/"):
            continue
        if ".dist-info/" in name:
            lower = name.lower()
            if lower.endswith(("license", "license.txt", "notice", "notice.txt")) or "/licenses/" in lower:
                leaf = Path(name).name
                files[f"__voicestt_third_party__/kroko_onnx/{leaf}"] = zf.read(name)
                licenses.append(leaf)
            continue
        if name.lower().endswith(".whl"):
            raise ProductWheelError("Kroko runtime wheel contains nested wheel payload")
        files[name] = zf.read(name)
    if not any(name.startswith("kroko_onnx/") for name in files):
        raise ProductWheelError("Kroko runtime payload has no kroko_onnx package")
    native = [n for n in files if n.endswith((".so", ".pyd", ".dll")) or ".libs/" in n]
    if not native:
        raise ProductWheelError("Kroko runtime payload contains no native extension/library")
    if not licenses:
        raise ProductWheelError("Kroko wheel carries no license/NOTICE payload to preserve")
    return licenses


def _rewrite_dist_info(files: dict[str, bytes], variant: str, tag: tuple[str, str, str]) -> str:
    old_dist = next((n.split("/", 1)[0] for n in files if n.endswith(".dist-info/METADATA")), None)
    if not old_dist:
        raise ProductWheelError("base wheel has no dist-info/METADATA")
    distribution = DISTRIBUTIONS[variant]
    normalized = distribution.replace("-", "_")
    new_dist = f"{normalized}-{VERSION}.dist-info"
    moved = {}
    for name, data in list(files.items()):
        if name.startswith(old_dist + "/"):
            moved[new_dist + name[len(old_dist):]] = data
            del files[name]
    files.update(moved)
    metadata_name = f"{new_dist}/METADATA"
    files[metadata_name] = _metadata_bytes(files[metadata_name], distribution)
    wheel_name = f"{new_dist}/WHEEL"
    wheel_text = files[wheel_name].decode("utf-8")
    wheel_lines = [line for line in wheel_text.splitlines() if not line.startswith("Root-Is-Purelib:") and not line.startswith("Tag:")]
    py, abi, plat = tag
    wheel_lines.extend(["Root-Is-Purelib: false", f"Tag: {py}-{abi}-{plat}"])
    files[wheel_name] = ("\n".join(wheel_lines) + "\n").encode("utf-8")
    files["VoiceSTT/_release_variant.py"] = (
        '"""Baked V1 product variant. Generated by tools/v1_product_wheel.py."""\n\n'
        f'KROKO_VARIANT = "{variant}"\n'
    ).encode("utf-8")
    return new_dist


def _write_wheel(files: dict[str, bytes], dist_info: str, out: Path) -> None:
    record_name = f"{dist_info}/RECORD"; files.pop(record_name, None)
    rows = [[name, _record_hash(files[name]), str(len(files[name]))] for name in sorted(files)]
    rows.append([record_name, "", ""])
    sio = io.StringIO(newline=""); csv.writer(sio, lineterminator="\n").writerows(rows)
    files[record_name] = sio.getvalue().encode("utf-8")
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for name in sorted(files): zf.writestr(name, files[name])


def _record_is_valid(zf: zipfile.ZipFile, record_name: str) -> bool:
    names = {name for name in zf.namelist() if not name.endswith("/")}
    rows = list(csv.reader(io.StringIO(zf.read(record_name).decode("utf-8"))))
    if {row[0] for row in rows} != names:
        return False
    for row in rows:
        if len(row) != 3:
            return False
        name, digest, size = row
        if name == record_name:
            if digest or size:
                return False
            continue
        data = zf.read(name)
        if digest != _record_hash(data) or size != str(len(data)):
            return False
    return True


def inspect_product_wheel(path: Path) -> dict:
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        metadata_name = next(n for n in names if n.endswith(".dist-info/METADATA"))
        wheel_name = next(n for n in names if n.endswith(".dist-info/WHEEL"))
        metadata = email.message_from_bytes(zf.read(metadata_name))
        wheel_text = zf.read(wheel_name).decode("utf-8")
        marker = zf.read("VoiceSTT/_release_variant.py").decode("utf-8")
        record_name = next(n for n in names if n.endswith(".dist-info/RECORD"))
        nested = [n for n in names if n.lower().endswith(".whl")]
        kroko_dist_infos = [n for n in names if re.search(r"(^|/)kroko_onnx-.*\.dist-info/", n, re.I)]
        natives = [n for n in names if n.endswith((".so", ".pyd", ".dll")) or ".libs/" in n]
        licenses = [n for n in names if n.startswith("__voicestt_third_party__/kroko_onnx/")]
        models = [n for n in names if n.lower().endswith(".data")]
        credential_matches = []
        for name in names:
            data = zf.read(name)
            for label, pattern in CREDENTIAL_PATTERNS.items():
                if pattern.search(data):
                    credential_matches.append({"entry": name, "pattern": label})
        record_valid = _record_is_valid(zf, record_name)
    tags = [line.split(":", 1)[1].strip() for line in wheel_text.splitlines() if line.startswith("Tag:")]
    pure_line = next((line.split(":", 1)[1].strip().lower() for line in wheel_text.splitlines() if line.startswith("Root-Is-Purelib:")), None)
    root_is_purelib = pure_line == "true"
    variant = "pro" if 'KROKO_VARIANT = "pro"' in marker else "free" if 'KROKO_VARIANT = "free"' in marker else "unknown"
    return {
        "filename": path.name, "distribution": metadata.get("Name"), "version": metadata.get("Version"),
        "variant": variant, "tags": tags, "rootIsPurelib": root_is_purelib,
        "bytes": path.stat().st_size, "sha256": sha256_file(path),
        "krokoNativePayload": sorted(natives), "licensePayload": sorted(licenses),
        "nestedWheels": nested, "krokoDistInfoEntries": kroko_dist_infos,
        "variantMarkerPresent": variant != "unknown",
        "embeddedKrokoRuntimePackage": any(n.startswith("kroko_onnx/") for n in names),
        "embeddedKrokoNativePayload": bool(natives),
        "modelPayloadEntries": sorted(models),
        "obviousCredentialPatternMatches": credential_matches,
        "recordValid": record_valid,
        "topLevel": sorted({n.split("/", 1)[0] for n in names}),
    }


def build_product_wheel(variant: str, platform: str, kroko_wheel: Path, out_dir: Path) -> dict:
    variant = variant.lower()
    if variant not in DISTRIBUTIONS:
        raise ProductWheelError("variant must be free|pro")
    tag = parse_native_tag(kroko_wheel, platform)
    with tempfile.TemporaryDirectory(prefix="v1-product-wheel-") as tmp_name:
        tmp = Path(tmp_name); base = _build_base_wheel(tmp); files = {}
        with zipfile.ZipFile(base) as zf:
            for name in zf.namelist():
                if not name.endswith("/"): files[name] = zf.read(name)
        with zipfile.ZipFile(kroko_wheel) as zf:
            _copy_kroko_payload(zf, files)
        dist_info = _rewrite_dist_info(files, variant, tag)
        out_dir.mkdir(parents=True, exist_ok=True)
        distribution = DISTRIBUTIONS[variant].replace("-", "_"); py, abi, plat = tag
        out = out_dir / f"{distribution}-{VERSION}-{py}-{abi}-{plat}.whl"
        _write_wheel(files, dist_info, out)
    report = inspect_product_wheel(out)
    if report["variant"] != variant or report["distribution"] != DISTRIBUTIONS[variant]:
        raise ProductWheelError(f"final product identity mismatch: {report}")
    if (report["rootIsPurelib"] or report["nestedWheels"] or
            report["krokoDistInfoEntries"] or not report["krokoNativePayload"] or
            not report["variantMarkerPresent"] or not report["recordValid"] or
            report["modelPayloadEntries"] or
            report["obviousCredentialPatternMatches"]):
        raise ProductWheelError(f"invalid embedded Kroko payload/metadata: {report}")
    return report


def main(argv=None):
    p = argparse.ArgumentParser(); sub = p.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build"); b.add_argument("--variant", choices=sorted(DISTRIBUTIONS), required=True); b.add_argument("--platform", choices=sorted(PLATFORMS), required=True); b.add_argument("--kroko-wheel", type=Path, required=True); b.add_argument("--out-dir", type=Path, required=True); b.add_argument("--report", type=Path)
    i = sub.add_parser("inspect"); i.add_argument("wheel", type=Path)
    args = p.parse_args(argv)
    try:
        report = build_product_wheel(args.variant, args.platform, args.kroko_wheel, args.out_dir) if args.command == "build" else inspect_product_wheel(args.wheel)
        if args.command == "build" and args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True); args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
    except (ProductWheelError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr); return 1
    return 0

if __name__ == "__main__": raise SystemExit(main())
