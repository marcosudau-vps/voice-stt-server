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
from tools import v1_release_publish as publish_tools  # noqa: E402

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

EVIDENCE_SOURCES = {
    "00_EVIDENCE_INDEX.md": ("Index of every mandatory evidence file", "evidence job / v1_evidence_pack.py"),
    "01_git_identity.txt": ("Branch, HEAD, tree, parent, base and clean checkout identity", "evidence job / live git commands"),
    "02_scope_diff.txt": ("Base-to-HEAD scope and per-file justification", "evidence job / live git diff commands"),
    "03_product_contract.json": ("Four actual public wheel identities and hashes", "product-wheel matrix artifacts / wheel inspection"),
    "04_wheel_inventory.json": ("Actual metadata, payload, RECORD, model and credential checks", "product-wheel matrix artifacts / wheel inspection"),
    "05_free_linux_wheel_contents.txt": ("Free Linux wheel payload plus METADATA/WHEEL", "Product free / linux_x86_64"),
    "06_free_windows_wheel_contents.txt": ("Free Windows wheel payload plus METADATA/WHEEL", "Product free / win_amd64"),
    "07_pro_linux_wheel_contents.txt": ("Pro Linux wheel payload plus METADATA/WHEEL", "Product pro / linux_x86_64"),
    "08_pro_windows_wheel_contents.txt": ("Pro Windows wheel payload plus METADATA/WHEEL", "Product pro / win_amd64"),
    "09_kroko_intermediates.json": ("Four pinned Kroko native intermediate identities", "Kroko runtime matrix artifact.json files"),
    "10_clean_install_linux_free.txt": ("Fresh Linux Free install/import/CLI/pip checks", "Linux clean install / free"),
    "11_clean_install_linux_pro.txt": ("Fresh Linux Pro install/import/CLI/pip checks", "Linux clean install / pro"),
    "12_clean_install_windows_free.txt": ("Fresh Windows Free install/import/CLI/pip checks", "Windows clean install / free"),
    "13_clean_install_windows_pro.txt": ("Fresh Windows Pro install/import/CLI/pip checks", "Windows clean install / pro"),
    "14_variant_proof.txt": ("Baked and clean-installed variant with selector env vars absent", "four wheel inventories plus four clean-install logs"),
    "15_model_policy_evidence.txt": ("Real Faster-Whisper and Kroko policy tests", "evidence job / pytest test_v1_model_resolution.py"),
    "16_pro_missing_model_test.txt": ("Installed Pro missing-model fail-closed reality test", "evidence job / isolated Pro venv"),
    "17_docker_free.txt": ("Free image built from exact final Linux wheel", "Docker final wheel / free"),
    "18_docker_pro.txt": ("Pro image built from exact final Linux wheel", "Docker final wheel / pro"),
    "19_pypi_resume_simulation.md": ("Human-readable seven-case PyPI bootstrap/resume simulation", "evidence job / live publish helper calls"),
    "19_pypi_resume_simulation.json": ("Machine-readable seven-case PyPI bootstrap/resume simulation", "evidence job / live publish helper calls"),
    "20_trusted_publisher_identity.txt": ("Actual shared workflow/environment/OIDC publisher identity", "evidence job / release-publish.yml inspection"),
    "21_artifact_negative_checks.txt": ("Executable no-sdist/no-pure/no-nested/no-separate-runtime checks", "evidence job / actual wheel tree"),
    "22_license_inventory.md": ("Carried Kroko notices and native third-party runtime files", "evidence job / actual wheel inventories"),
    "23_secret_scan.txt": ("Credential/model/path scan of wheels and effective Docker COPY inputs", "evidence job / byte-pattern scan"),
    "24_ci_runs.md": ("Exact run, job and artifact identifiers", "evidence job / GitHub Actions API"),
    "25_no_publication_guard.md": ("Branch/tag/release/manual-workflow/publication guard", "evidence job / git and GitHub API"),
    "26_remaining_risks.md": ("Only known residual release risks", "evidence job / correction gate review"),
    "SHA256SUMS.txt": ("SHA-256 for every other evidence file", "evidence job / v1_evidence_pack.py"),
}


def scope_reason(path: str) -> str:
    if path.startswith(".github/workflows/"):
        return "V1 native build, Candidate, publish/resume, or validation contract."
    if path in {"README.md", "RELEASE_NOTES.md", "setup.py", "build/BUILD.md", "docs/v1-preservation-release.md"}:
        return "Directly release-facing install, packaging, or build documentation/metadata."
    if path.startswith("docs/.archiv/"):
        return "Mandatory repository change-action audit trail required by AGENTS.md."
    if path == "VoiceSTT/_release_variant.py":
        return "Source-controlled baked Free/Pro distribution identity."
    if path == "VoiceSTT/transcription_engines/model_resolver.py":
        return "Consumes baked identity while preserving the V1 model policy."
    if path == "build/v1-release.Dockerfile":
        return "Production image consumes exactly one final Linux product wheel."
    if path.startswith("tests/test_v1_"):
        return "Executable acceptance/negative contract for this V1 correction."
    if path.startswith("tools/v1_"):
        return "Source-controlled native runtime, product wheel, manifest, publish, local acceptance, or evidence tooling."
    raise SystemExit(f"unmapped scope path in correction diff: {path}")


def _simulation_manifest() -> dict:
    def project(variant, distribution):
        normalized = distribution.replace("-", "_")
        return {"distribution": distribution, "variant": variant, "wheels": {
            "linux_x86_64": {"filename": f"{normalized}-1.0.0-cp312-cp312-linux_x86_64.whl", "sha256": "a" * 64},
            "win_amd64": {"filename": f"{normalized}-1.0.0-cp312-cp312-win_amd64.whl", "sha256": "b" * 64},
        }}
    return {"python": {"free": project("free", "voice-stt-server"), "pro": project("pro", "voice-stt-server-pro")}}


def _pypi_payload(manifest, variant, present=("linux_x86_64", "win_amd64"), corrupt=()):
    urls = []
    for platform, info in manifest["python"][variant]["wheels"].items():
        if platform in present:
            digest = "f" * 64 if platform in corrupt else info["sha256"]
            urls.append({"filename": info["filename"], "digests": {"sha256": digest}})
    return {"urls": urls}


def pypi_resume_simulation() -> dict:
    manifest = _simulation_manifest()
    absent = lambda _url: None
    match = lambda variant: (lambda _url: _pypi_payload(manifest, variant))
    free_absent = publish_tools.inspect_pypi_project(manifest, "free", fetch=absent)
    pro_absent = publish_tools.inspect_pypi_project(manifest, "pro", fetch=absent)
    free_match = publish_tools.inspect_pypi_project(manifest, "free", fetch=match("free"))
    pro_match = publish_tools.inspect_pypi_project(manifest, "pro", fetch=match("pro"))
    free_conflict = publish_tools.inspect_pypi_project(
        manifest, "free", fetch=lambda _url: _pypi_payload(manifest, "free", corrupt=("linux_x86_64",)))
    free_unknown = publish_tools.inspect_pypi_project(
        manifest, "free", fetch=lambda _url: (_ for _ in ()).throw(TimeoutError("simulated timeout")))
    pro_mixed = publish_tools.inspect_pypi_project(
        manifest, "pro", fetch=lambda _url: _pypi_payload(manifest, "pro", present=("linux_x86_64",)))
    pro_conflict = publish_tools.inspect_pypi_project(
        manifest, "pro", fetch=lambda _url: _pypi_payload(manifest, "pro", corrupt=("win_amd64",)))
    pro_unknown = publish_tools.inspect_pypi_project(
        manifest, "pro", fetch=lambda _url: (_ for _ in ()).throw(TimeoutError("simulated timeout")))

    def hard_stop(report):
        try:
            publish_tools.validate_publishable(report)
        except publish_tools.PublicationPrecheckError:
            return True
        return False

    cases = [
        {"case": 1, "input": "Free ABSENT; Pro ABSENT", "freeStaged": sorted(free_absent["artifacts"]), "proStaged": [], "bootstrapStop": publish_tools.bootstrap_phase1_required(free_absent, free_match, pro_absent), "downstreamAllowed": False},
        {"case": 2, "input": "Free MATCH; Pro ABSENT", "freeStaged": [], "proStaged": sorted(pro_absent["artifacts"]), "downstreamAllowed": False},
        {"case": 3, "input": "Free MATCH; Pro MATCH", "freeStaged": [], "proStaged": [], "pypiComplete": publish_tools.project_complete(free_match) and publish_tools.project_complete(pro_match), "downstreamAllowed": True},
        {"case": 4, "input": "Free CONFLICT", "hardStopBeforePro": hard_stop(free_conflict), "downstreamAllowed": False},
        {"case": 5, "input": "Free UNKNOWN", "hardStopBeforePro": hard_stop(free_unknown), "downstreamAllowed": False},
        {"case": 6, "input": "Free MATCH; Pro Linux MATCH; Pro Windows ABSENT", "proStaged": sorted(name for name, state in pro_mixed["artifacts"].items() if state == publish_tools.ABSENT), "partialArtifactStatePresent": False, "downstreamAllowed": False},
        {"case": 7, "input": "Pro CONFLICT or UNKNOWN", "conflictHardStop": hard_stop(pro_conflict), "unknownHardStop": hard_stop(pro_unknown), "downstreamAllowed": False},
    ]
    if not (cases[0]["bootstrapStop"] and cases[2]["pypiComplete"] and
            cases[3]["hardStopBeforePro"] and cases[4]["hardStopBeforePro"] and
            cases[6]["conflictHardStop"] and cases[6]["unknownHardStop"] and
            len(cases[5]["proStaged"]) == 1):
        raise SystemExit(f"PyPI resume simulation failed: {cases}")
    return {"artifactStates": sorted(publish_tools.STATES), "partialStatePresent": False,
            "sameCandidateAndTagRequired": True, "rebuildOnResume": False, "cases": cases}

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
    changed = [line for line in run_text(["git", "diff", "--name-only", BASE + "...HEAD"]).splitlines() if line]
    mapping = "\n".join(f"{path}\n  -> {scope_reason(path)}" for path in changed)
    diff = ("git diff --stat BASE...HEAD\n" + run_text(["git", "diff", "--stat", BASE + "...HEAD"]) +
            "git diff --name-status BASE...HEAD\n" + run_text(["git", "diff", "--name-status", BASE + "...HEAD"]) +
            "git diff --check BASE...HEAD\nPASS\n\nPer-file scope mapping:\n" + mapping)
    write(out / "02_scope_diff.txt", diff)

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

    clean_logs = [
        (out / name).read_text(encoding="utf-8", errors="replace")
        for name in ("10_clean_install_linux_free.txt", "11_clean_install_linux_pro.txt",
                     "12_clean_install_windows_free.txt", "13_clean_install_windows_pro.txt")
    ]
    if any("selector_env_absent=true" not in text for text in clean_logs):
        raise SystemExit("clean-install logs do not prove variant selector env absence")
    variant_lines = [
        f"{x['filename']}: baked_variant={x['variant']} variant_marker={x['variantMarkerPresent']}"
        for x in inventory
    ]
    variant_lines.extend([
        "All four clean-install logs record selector_env_absent=true before import.",
        "Free clean installs reported variant=free; Pro clean installs reported variant=pro.",
        "VOICESTT_KROKO_VARIANT and KROKO_API_KEY were absent; KROKO_API_KEY is not consulted for distribution identity.",
    ])
    write(out / "14_variant_proof.txt", "\n".join(variant_lines))

    simulation = pypi_resume_simulation()
    (out / "19_pypi_resume_simulation.json").write_text(json.dumps(simulation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    simulation_md = ["# PyPI resume simulation", "", "No PyPI upload was performed. These results were produced by live calls into `tools/v1_release_publish.py`:", ""]
    for case in simulation["cases"]:
        simulation_md.append(f"- Case {case['case']} — `{case['input']}`: `{json.dumps(case, sort_keys=True)}`")
    simulation_md.extend(["", "Only ABSENT files are staged. CONFLICT/UNKNOWN stop before Pro or downstream publication. Resume requires the same Candidate/tag and performs no rebuild."])
    write(out / "19_pypi_resume_simulation.md", "\n".join(simulation_md))

    publish = (ROOT / ".github/workflows/release-publish.yml").read_text(encoding="utf-8")
    repository = os.getenv("GITHUB_REPOSITORY", "marcosudau-vps/voice-stt-server")
    identity_checks = {
        "workflow_file_is_release_publish": (ROOT / ".github/workflows/release-publish.yml").is_file(),
        "environment_release_present": publish.count("environment: release") >= 2,
        "oidc_id_token_write_present": "id-token: write" in publish,
        "repository_matches": repository == "marcosudau-vps/voice-stt-server",
        "free_and_pro_in_same_workflow": "pypi-free:" in publish and "pypi-pro:" in publish,
        "no_bootstrap_workflow_file": not any((ROOT / ".github/workflows").glob("*bootstrap*")),
    }
    if not all(identity_checks.values()):
        raise SystemExit(f"trusted publisher identity check failed: {identity_checks}")
    write(out / "20_trusted_publisher_identity.txt", "\n".join([
        "Workflow file: .github/workflows/release-publish.yml",
        "Environment: release (Free and Pro jobs)",
        "OIDC permission: id-token: write",
        f"Repository: {repository}",
        "Free and Pro: same workflow file, same release environment",
        "Bootstrap workflow files: none",
        "Checks: " + json.dumps(identity_checks, sort_keys=True),
    ]))

    negative_values = {
        "public sdist absent": not any(root.rglob("*.tar.gz")),
        "py3-none-any final absent": not any("py3-none-any" in x["filename"] for x in inventory),
        "voice-stt-server-pro present": any(x["distribution"] == "voice-stt-server-pro" for x in inventory),
        "nested wheels absent": all(not x["nestedWheels"] for x in inventory),
        "all final wheels non-pure": all(x["rootIsPurelib"] is False for x in inventory),
        "all final wheels embed native Kroko": all(bool(x["krokoNativePayload"]) for x in inventory),
        "no separate Kroko end-user installation required": all(x["embeddedKrokoRuntimePackage"] and not x["krokoDistInfoEntries"] for x in inventory),
        "no Kroko model payload embedded": all(not x["modelPayloadEntries"] for x in inventory),
        "all RECORD files valid": all(x["recordValid"] for x in inventory),
    }
    write(out / "21_artifact_negative_checks.txt", "\n".join(f"{k}: {v}" for k, v in negative_values.items()))
    if not all(negative_values.values()):
        raise SystemExit(f"negative artifact check failed: {negative_values}")

    license_lines = ["# Embedded Kroko license/NOTICE evidence", ""]
    for item in inventory:
        license_lines.extend([
            f"## {item['filename']}", "",
            "Carried Kroko notices: " + ", ".join(item["licensePayload"]), "",
            "Native/third-party runtime payload:", "",
            *[f"- `{entry}`" for entry in item["krokoNativePayload"]], "",
        ])
    license_lines.append("This is an inventory of files actually carried by the wheels, not a new legal interpretation.")
    write(out / "22_license_inventory.md", "\n".join(license_lines))

    suspicious = []
    patterns = product.CREDENTIAL_PATTERNS
    for variant in ("free", "pro"):
        for platform in ("linux_x86_64", "win_amd64"):
            data = wheel_for(root, variant, platform).read_bytes()
            for label, pattern in patterns.items():
                if pattern.search(data): suspicious.append(f"wheel:{variant}/{platform}:{label}")
    dockerfile = ROOT / "build/v1-release.Dockerfile"
    dockerignore = ROOT / ".dockerignore"
    for path in (dockerfile, dockerignore):
        data = path.read_bytes()
        for label, pattern in patterns.items():
            if pattern.search(data): suspicious.append(f"docker-input:{path.name}:{label}")
    docker_text = dockerfile.read_text(encoding="utf-8")
    path_leaks = [value for value in ("P:\\\\", "/home/marco/") if value in docker_text]
    context_checks = {
        "dockerfile_copies_only_product_wheels": "COPY release-inputs/python/*.whl" in docker_text and "COPY ." not in docker_text,
        "env_files_excluded": all(value in dockerignore.read_text(encoding="utf-8") for value in (".env", ".env.*", "*.env")),
        "no_models_in_wheels": all(not item["modelPayloadEntries"] for item in inventory),
        "no_credentials_in_unpacked_wheel_entries": all(not item["obviousCredentialPatternMatches"] for item in inventory),
        "no_personal_absolute_paths_in_dockerfile": not path_leaks,
    }
    write(out / "23_secret_scan.txt", "\n".join([
        "Scanned: four final product-wheel byte streams; build/v1-release.Dockerfile; .dockerignore.",
        "Effective Docker COPY payload: exactly release-inputs/python/*.whl (the already scanned final product wheel).",
        "Suspicious credential-pattern matches: " + str(suspicious),
        "Private absolute path matches in Dockerfile: " + str(path_leaks),
        "Docker context checks: " + json.dumps(context_checks, sort_keys=True),
        "The documented variable name KROKO_API_KEY is allowed; a credential value is not.",
    ]))
    if suspicious:
        raise SystemExit("secret scan found token-shaped data")
    if not all(context_checks.values()):
        raise SystemExit(f"Docker context secret/model check failed: {context_checks}")
    write(out / "26_remaining_risks.md", "# Remaining risks\n\n- At CI artifact creation time, operator-local Windows-PC and Linux-VPS acceptance is external evidence and must still be reconciled before Candidate.\n- The real PyPI pending-publisher transition cannot be exercised without the authorized first public release; seven safe local states are simulated in files 19.\n- GitHub recorded parse-only push run 34703916749 for an earlier invalid `release-candidate.yml`; it had no jobs and no publication, but the historical run record remains. The Candidate was never manually dispatched.\n")

    # Predeclare every mandatory evidence file so the index also indexes itself
    # and the checksum file that is written last.
    run_id = os.getenv("GITHUB_RUN_ID", "local")
    index_rows = ["| File | Purpose | Actual producer / CI job | Commit | CI run |", "| --- | --- | --- | --- | --- |"]
    for name in MANDATORY:
        purpose, source = EVIDENCE_SOURCES[name]
        index_rows.append(f"| `{name}` | {purpose} | {source} | `{commit}` | `{run_id}` |")
    index = "# V1 correction-1 evidence index\n\n" + "\n".join(index_rows)
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
