"""Fail-closed V1 publication prechecks and resumable two-project PyPI staging."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
import v1_kroko_release as kroko  # noqa: E402
import v1_release_manifest as manifest_tools  # noqa: E402

ABSENT = "ABSENT"; MATCH = "MATCH"; CONFLICT = "CONFLICT"; UNKNOWN = "UNKNOWN"
STATES = {ABSENT, MATCH, CONFLICT, UNKNOWN}
VERSION = "1.0.0"; TAG = "v1.0.0"

class PublicationPrecheckError(RuntimeError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PublicationPrecheckError(f"could not read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PublicationPrecheckError(f"{path} is not an object")
    return value


def verify_candidate_dir(candidate_dir: Path) -> dict[str, Any]:
    candidate_dir = Path(candidate_dir).resolve()
    manifest = _load_json(candidate_dir / "rc-manifest.json")
    try:
        manifest_tools.validate_candidate(manifest)
    except manifest_tools.CandidateManifestError as exc:
        raise PublicationPrecheckError(str(exc)) from exc
    for variant in ("free", "pro"):
        for platform in manifest_tools.PLATFORMS:
            identity = manifest["python"][variant]["wheels"][platform]
            path = candidate_dir / "python" / variant / platform / identity["filename"]
            if not path.is_file() or manifest_tools.sha256_file(path) != identity["sha256"]:
                raise PublicationPrecheckError(f"candidate product wheel mismatch: {variant}/{platform}")
            try:
                verified = kroko.verify_artifact(variant, candidate_dir / "kroko" / variant / platform, platform)
            except kroko.ReleaseKrokoError as exc:
                raise PublicationPrecheckError(str(exc)) from exc
            if verified != manifest["kroko"][variant][platform]:
                raise PublicationPrecheckError(f"Kroko provenance mismatch: {variant}/{platform}")
    if _load_json(candidate_dir / "sha256-inventory.json") != manifest_tools.build_inventory(candidate_dir):
        raise PublicationPrecheckError("candidate inventory mismatch")
    return manifest

PyPIFetcher = Callable[[str], dict[str, Any] | None]

def _fetch_pypi(url: str) -> dict[str, Any] | None:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def expected_project_files(manifest: dict[str, Any], variant: str) -> dict[str, str]:
    wheels = manifest["python"][variant]["wheels"]
    return {wheels[p]["filename"]: wheels[p]["sha256"] for p in manifest_tools.PLATFORMS}


def inspect_pypi_project(manifest: dict[str, Any], variant: str, *, fetch: PyPIFetcher = _fetch_pypi) -> dict[str, Any]:
    project = manifest["python"][variant]["distribution"]
    expected = expected_project_files(manifest, variant)
    url = f"https://pypi.org/pypi/{project}/{VERSION}/json"
    try:
        payload = fetch(url)
    except Exception as exc:
        return {"project": project, "artifacts": {n: UNKNOWN for n in expected}, "reason": str(exc)}
    if payload is None:
        return {"project": project, "artifacts": {n: ABSENT for n in expected}}
    urls = payload.get("urls") if isinstance(payload, dict) else None
    if not isinstance(urls, list):
        return {"project": project, "artifacts": {n: UNKNOWN for n in expected}, "reason": "invalid PyPI urls"}
    remote = {}
    malformed = False
    for item in urls:
        if not isinstance(item, dict) or not item.get("filename") or not (item.get("digests") or {}).get("sha256"):
            malformed = True; continue
        remote[str(item["filename"])] = str(item["digests"]["sha256"]).lower()
    if malformed:
        return {"project": project, "artifacts": {n: UNKNOWN for n in expected}, "reason": "malformed PyPI file metadata"}
    states = {}
    for name, expected_sha in expected.items():
        states[name] = ABSENT if name not in remote else MATCH if remote[name] == expected_sha.lower() else CONFLICT
    unexpected = sorted(set(remote) - set(expected))
    if unexpected:
        # An unexpected file under the same immutable 1.0.0 release means the
        # remote version is not byte-equivalent to our qualified candidate.
        for name in states:
            if states[name] == ABSENT:
                states[name] = CONFLICT
    return {"project": project, "artifacts": states, "unexpected": unexpected}


def validate_publishable(report: dict[str, Any]) -> None:
    states = set((report.get("artifacts") or {}).values())
    if UNKNOWN in states or CONFLICT in states or not states <= STATES:
        raise PublicationPrecheckError(f"PyPI hard-stop: {report}")


def stage_absent_project_files(candidate_dir: Path, stage_dir: Path, manifest: dict[str, Any], variant: str,
                               report: dict[str, Any]) -> list[str]:
    validate_publishable(report)
    stage_dir = Path(stage_dir)
    if stage_dir.exists(): shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True)
    staged = []
    wheels = manifest["python"][variant]["wheels"]
    for platform in manifest_tools.PLATFORMS:
        info = wheels[platform]
        if report["artifacts"].get(info["filename"]) == ABSENT:
            src = Path(candidate_dir) / "python" / variant / platform / info["filename"]
            shutil.copy2(src, stage_dir / info["filename"]); staged.append(info["filename"])
    return staged


def project_complete(report: dict[str, Any]) -> bool:
    return bool(report.get("artifacts")) and all(v == MATCH for v in report["artifacts"].values())


def bootstrap_phase1_required(free_before: dict[str, Any], free_after: dict[str, Any], pro_before: dict[str, Any]) -> bool:
    """Controlled first-release pause after establishing Free, before Pro publisher setup."""
    free_was_absent = all(v == ABSENT for v in free_before.get("artifacts", {}).values())
    pro_is_absent = all(v == ABSENT for v in pro_before.get("artifacts", {}).values())
    return free_was_absent and pro_is_absent and project_complete(free_after)


def classify_digest(actual: str | None, expected: str) -> str:
    if not actual: return ABSENT
    return MATCH if actual.strip().lower() == expected.strip().lower() else CONFLICT


def aliases_for(version: str = VERSION) -> list[str]:
    parts = version.split(".")
    if len(parts) != 3 or not all(x.isdigit() for x in parts):
        raise PublicationPrecheckError(f"invalid SemVer {version!r}")
    return [f"{parts[0]}.{parts[1]}", parts[0], "latest"]


def main(argv=None):
    p = argparse.ArgumentParser(); sub = p.add_subparsers(dest="command", required=True)
    v = sub.add_parser("verify-candidate"); v.add_argument("--candidate-dir", type=Path, required=True)
    pc = sub.add_parser("precheck-pypi"); pc.add_argument("--candidate-dir", type=Path, required=True); pc.add_argument("--variant", choices=("free","pro"), required=True); pc.add_argument("--stage-dir", type=Path, required=True); pc.add_argument("--out", type=Path, required=True)
    pv = sub.add_parser("verify-pypi"); pv.add_argument("--candidate-dir", type=Path, required=True); pv.add_argument("--variant", choices=("free","pro"), required=True)
    d = sub.add_parser("classify-digest"); d.add_argument("--actual", default=""); d.add_argument("--expected", required=True)
    a = sub.add_parser("aliases"); a.add_argument("--version", default=VERSION)
    args = p.parse_args(argv)
    try:
        if args.command == "verify-candidate": verify_candidate_dir(args.candidate_dir); print(MATCH)
        elif args.command in {"precheck-pypi", "verify-pypi"}:
            manifest = verify_candidate_dir(args.candidate_dir)
            report = inspect_pypi_project(manifest, args.variant)
            validate_publishable(report)
            if args.command == "precheck-pypi":
                args.out.parent.mkdir(parents=True, exist_ok=True); args.out.write_text(json.dumps(report, indent=2, sort_keys=True)+"\n")
                staged = stage_absent_project_files(args.candidate_dir, args.stage_dir, manifest, args.variant, report)
                print(json.dumps({"staged": staged, "complete": project_complete(report)}))
            elif not project_complete(report):
                raise PublicationPrecheckError(f"PyPI {args.variant} verification incomplete: {report}")
            else: print(MATCH)
        elif args.command == "classify-digest": print(classify_digest(args.actual or None, args.expected))
        else: print("\n".join(aliases_for(args.version)))
    except PublicationPrecheckError as exc:
        print(f"ERROR: {exc}", file=sys.stderr); return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
