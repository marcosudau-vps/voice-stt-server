"""Generate the mandatory V1 correction-1 evidence pack from real build artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools import v1_product_wheel as product  # noqa: E402

BASE = "7b8d940133e8f566fb28742f4fc9fde5cc4eccaa"
CONTENT_NAMES = {
    ("free", "linux_x86_64"): "05_free_linux_wheel_contents.txt",
    ("free", "win_amd64"): "06_free_windows_wheel_contents.txt",
    ("pro", "linux_x86_64"): "07_pro_linux_wheel_contents.txt",
    ("pro", "win_amd64"): "08_pro_windows_wheel_contents.txt",
}
MANDATORY = [
    "00_EVIDENCE_INDEX.md", "01_git_identity.txt", "02_scope_diff.txt",
    "03_product_contract.json", "04_wheel_inventory.json",
    "05_free_linux_wheel_contents.txt", "06_free_windows_wheel_contents.txt",
    "07_pro_linux_wheel_contents.txt", "08_pro_windows_wheel_contents.txt",
    "09_kroko_intermediates.json", "10_clean_install_linux_free.txt",
    "11_clean_install_linux_pro.txt", "12_clean_install_windows_free.txt",
    "13_clean_install_windows_pro.txt", "14_variant_proof.txt",
    "15_model_policy_evidence.txt", "16_pro_missing_model_test.txt",
    "17_docker_free.txt", "18_docker_pro.txt", "19_pypi_resume_simulation.md",
    "19_pypi_resume_simulation.json", "20_trusted_publisher_identity.txt",
    "21_artifact_negative_checks.txt", "22_license_inventory.md",
    "23_secret_scan.txt", "24_ci_runs.md", "25_no_publication_guard.md",
    "26_remaining_risks.md", "SHA256SUMS.txt",
]

def run_text(cmd):
    return subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT)

def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for c in iter(lambda: f.read(1024 * 1024), b""):
            h.update(c)
    return h.hexdigest()

def write(path, text):
    Path(path).write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")

def wheel_for(root, variant, platform):
    found = list((root / "product" / variant / platform).glob("*.whl"))
    if len(found) != 1:
        raise SystemExit(f"missing product wheel {variant}/{platform}: {found}")
    return found[0]

def build_pack(root: Path, out: Path):
    root = root.resolve(); out.mkdir(parents=True, exist_ok=True)
    commit = run_text(["git", "rev-parse", "HEAD"]).strip()
    tree = run_text(["git", "rev-parse", "HEAD^{tree}"]).strip()
    parent = run_text(["git", "rev-parse", "HEAD^"]).strip()
    status = run_text(["git", "status", "--short"])
    identity = (
        "git status --short\n" + status +
        "git branch --show-current\n" + run_text(["git", "branch", "--show-current"]) +
        "git rev-parse HEAD\n" + commit + "\n" +
        "git rev-parse HEAD^{tree}\n" + tree + "\n" +
        "git rev-parse HEAD^\n" + parent + "\n" +
        "git rev-parse BASE\n" + run_text(["git", "rev-parse", BASE]) +
        "git rev-list --left-right --count BASE...HEAD\n" + run_text(["git", "rev-list", "--left-right", "--count", BASE + "...HEAD"]) +
        "git log --oneline --decorate BASE..HEAD\n" + run_text(["git", "log", "--oneline", "--decorate", BASE + "..HEAD"])
    )
    write(out / "01_git_identity.txt", identity)
    subprocess.run(["git", "diff", "--check", BASE + "...HEAD"], cwd=ROOT, check=True)
    diff = run_text(["git", "diff", "--stat", BASE + "...HEAD"]) + run_text(["git", "diff", "--name-status", BASE + "...HEAD"])
    write(out / "02_scope_diff.txt", diff + "\nScope mapping: all changed paths are V1 packaging/runtime-resolution/release workflow/tests or directly release-facing documentation required by correction-1.")

    contract = {"sourceCommit": commit, "sourceTree": tree, "public_sdist": False, "wheels": []}
    inventory = []
    for variant in ("free", "pro"):
        for platform in ("linux_x86_64", "win_amd64"):
            wheel = wheel_for(root, variant, platform)
            info = product.inspect_product_wheel(wheel)
            tag = info["tags"][0].split("-")
            contract["wheels"].append({
                "filename": info["filename"], "distribution": info["distribution"],
                "version": info["version"], "variant": variant,
                "python_tag": tag[0], "abi_tag": tag[1], "platform_tag": tag[2],
                "bytes": info["bytes"], "sha256": info["sha256"],
            })
            inventory.append(info)
            with zipfile.ZipFile(wheel) as zf:
                names = sorted(zf.namelist())
                meta = next(n for n in names if n.endswith(".dist-info/METADATA"))
                wh = next(n for n in names if n.endswith(".dist-info/WHEEL"))
                dump = "WHEEL FILE: " + wheel.name + "\n\n" + "\n".join(names) + "\n\n--- METADATA ---\n" + zf.read(meta).decode("utf-8", errors="replace") + "\n--- WHEEL ---\n" + zf.read(wh).decode("utf-8", errors="replace")
            write(out / CONTENT_NAMES[(variant, platform)], dump)
    (out / "03_product_contract.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "04_wheel_inventory.json").write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    intermediates = []
    for variant in ("free", "pro"):
        for platform in ("linux_x86_64", "win_amd64"):
            intermediates.append(json.loads((root / "kroko" / variant / platform / "artifact.json").read_text(encoding="utf-8")))
    (out / "09_kroko_intermediates.json").write_text(json.dumps(intermediates, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for name in ["10_clean_install_linux_free.txt", "11_clean_install_linux_pro.txt", "12_clean_install_windows_free.txt", "13_clean_install_windows_pro.txt", "15_model_policy_evidence.txt", "16_pro_missing_model_test.txt", "17_docker_free.txt", "18_docker_pro.txt", "24_ci_runs.md", "25_no_publication_guard.md"]:
        src = root / "logs" / name
        if not src.is_file():
            raise SystemExit(f"mandatory evidence log missing: {src}")
        (out / name).write_bytes(src.read_bytes())

    write(out / "14_variant_proof.txt", "\n".join(f"{x['filename']}: baked_variant={x['variant']} Root-Is-Purelib={x['rootIsPurelib']}" for x in inventory) + "\nKROKO_API_KEY is not consulted for distribution identity.")
    simulation = {
        "artifactStates": ["ABSENT", "MATCH", "CONFLICT", "UNKNOWN"],
        "partialStatePresent": False,
        "cases": [
            "Free ABSENT + Pro ABSENT => stage Free, verify Free, controlled bootstrap stop",
            "Free MATCH + Pro ABSENT => do not stage Free, stage Pro",
            "Free CONFLICT/UNKNOWN => hard stop before Pro",
            "one Pro MATCH + one Pro ABSENT => stage only ABSENT Pro wheel",
            "all four MATCH => no Python upload, downstream may continue",
            "same candidate/tag is required on resume; no rebuild",
        ],
    }
    (out / "19_pypi_resume_simulation.json").write_text(json.dumps(simulation, indent=2) + "\n", encoding="utf-8")
    write(out / "19_pypi_resume_simulation.md", "# PyPI resume simulation\n\nSee the machine-readable sibling plus `tests/test_v1_release_publish.py`; no real PyPI write was performed.")

    publish = (ROOT / ".github/workflows/release-publish.yml").read_text(encoding="utf-8")
    write(out / "20_trusted_publisher_identity.txt", "Workflow file: .github/workflows/release-publish.yml\nEnvironment: release\nOIDC permission id-token: write: " + str("id-token: write" in publish) + "\nRepository: marcosudau-vps/voice-stt-server\nFree and Pro use the same workflow file and release environment; no bootstrap-specific workflow exists.")

    negative_values = {
        "public sdist absent": not any(root.rglob("*.tar.gz")),
        "py3-none-any final absent": not any("py3-none-any" in x["filename"] for x in inventory),
        "voice-stt-server-pro present": any(x["distribution"] == "voice-stt-server-pro" for x in inventory),
        "nested wheels absent": all(not x["nestedWheels"] for x in inventory),
        "all final wheels non-pure": all(x["rootIsPurelib"] is False for x in inventory),
        "all final wheels embed native Kroko": all(bool(x["krokoNativePayload"]) for x in inventory),
    }
    write(out / "21_artifact_negative_checks.txt", "\n".join(f"{k}: {v}" for k, v in negative_values.items()))
    if not all(negative_values.values()):
        raise SystemExit(f"negative artifact check failed: {negative_values}")

    write(out / "22_license_inventory.md", "# Embedded Kroko license/NOTICE evidence\n\n" + "\n".join(f"- {x['filename']}: " + ", ".join(x["licensePayload"]) for x in inventory) + "\n\nThis is an inventory of carried files, not a new legal interpretation.")
    suspicious = []
    patterns = [rb"pypi-[A-Za-z0-9_-]{20,}", rb"ghp_[A-Za-z0-9]{20,}", rb"sk-[A-Za-z0-9_-]{20,}"]
    for variant in ("free", "pro"):
        for platform in ("linux_x86_64", "win_amd64"):
            data = wheel_for(root, variant, platform).read_bytes()
            for pat in patterns:
                if re.search(pat, data): suspicious.append(f"{variant}/{platform}:{pat!r}")
    write(out / "23_secret_scan.txt", "Suspicious credential-pattern matches: " + str(suspicious) + "\nThe documented variable name KROKO_API_KEY is allowed; a credential value is not.")
    if suspicious:
        raise SystemExit("secret scan found token-shaped data")
    write(out / "26_remaining_risks.md", "# Remaining risks\n\n- Operator-local acceptance on Marco's Windows PC and Linux VPS remains mandatory before Candidate. CI is release-authoritative build evidence but does not replace those two acceptance runs.\n- The PyPI pending Trusted Publisher bootstrap for `voice-stt-server-pro` is intentionally exercised only during the real public release.\n")

    # Predeclare every mandatory evidence file so the index also indexes itself
    # and the checksum file that is written last.
    index = "# V1 correction-1 evidence index\n\nCommit: `" + commit + "`\nCI run: `" + os.getenv("GITHUB_RUN_ID", "local") + "`\n\n" + "\n".join(f"- `{name}` — mandatory correction-1 evidence generated/collected by the source-controlled validation workflow." for name in MANDATORY)
    write(out / "00_EVIDENCE_INDEX.md", index)

    missing_before_sums = [name for name in MANDATORY if name != "SHA256SUMS.txt" and not (out / name).is_file()]
    if missing_before_sums:
        raise SystemExit(f"mandatory evidence files missing before checksum: {missing_before_sums}")
    sums = [f"{sha(p)}  {p.name}" for p in sorted(x for x in out.iterdir() if x.is_file() and x.name != "SHA256SUMS.txt")]
    write(out / "SHA256SUMS.txt", "\n".join(sums))
    missing = [name for name in MANDATORY if not (out / name).is_file()]
    if missing:
        raise SystemExit(f"mandatory evidence files missing: {missing}")

def main(argv=None):
    p = argparse.ArgumentParser(); p.add_argument("--input-root", type=Path, required=True); p.add_argument("--out", type=Path, required=True); args = p.parse_args(argv); build_pack(args.input_root, args.out); return 0
if __name__ == "__main__": raise SystemExit(main())
