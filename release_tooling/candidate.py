"""Assembling one canonical RC manifest from real build outputs.

AP-SRV-070 W5-R04. A release candidate is produced by three existing
authorities, each of which already writes a machine-readable result:

.. code-block:: text

    tools/build_production.py   -> build-manifest-<variant>.json
    tools/build_distribution.py -> distribution-<variant>.json
    the candidate workflow      -> staging-<variant>.json

This module is the one place those results are turned into the canonical RC
manifest, so ``tools/release_candidate.py`` (which runs on a GitHub runner) and
``release.py manifest build`` (which an operator can run by hand over an
already-produced candidate directory) can never assemble it two subtly
different ways.

It computes no identity of its own. Every hash, digest and fingerprint here is
read from the producing authority's own output; if something is missing, the
assembly fails closed rather than substituting a plausible value.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from . import rc_manifest
from .errors import ManifestError

#: The per-variant files a candidate output directory must contain.
BUILD_MANIFEST_TEMPLATE = "build-manifest-{variant}.json"
DISTRIBUTION_MANIFEST_TEMPLATE = "distribution-{variant}.json"
STAGING_MANIFEST_TEMPLATE = "staging-{variant}.json"


def _read_json(path: Path, what: str) -> Dict[str, Any]:
    if not path.is_file():
        raise ManifestError(f"candidate is incomplete: missing {what} at {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ManifestError(f"{what} at {path} is not valid JSON: {exc}") from exc


def _require(value: Any, what: str) -> Any:
    if value in (None, "", {}, []):
        raise ManifestError(f"candidate is incomplete: {what} is missing or empty")
    return value


def kroko_artifact_sha256(build_manifest: Dict[str, Any], variant: str) -> str:
    """One variant's Kroko artifact SHA-256 from a production build manifest.

    AP-SRV-070 W5-R02-C1 (D3): the real producer writes the canonical field
    ``wheelSha256`` inside ``variants.<variant>.kroko.artifact``. A legacy
    ``sha256`` at the same location is still tolerated as a fallback, but if
    both are present they must agree - silently choosing between two
    disagreeing hashes would defeat the entire point of an RC manifest, so
    this fails closed instead.
    """
    try:
        artifact = build_manifest["variants"][variant]["kroko"]["artifact"]
    except (KeyError, TypeError) as exc:
        raise ManifestError(
            f"production build manifest has no variants.{variant}.kroko.artifact block"
        ) from exc
    canonical = artifact.get("wheelSha256")
    legacy = artifact.get("sha256")
    if canonical and legacy and canonical != legacy:
        raise ManifestError(
            f"kroko {variant} artifact manifest has conflicting hashes: "
            f"wheelSha256={canonical!r} != sha256={legacy!r}"
        )
    resolved = canonical or legacy
    if not resolved:
        raise ManifestError(
            f"kroko {variant} artifact manifest is missing both 'wheelSha256' "
            "(canonical) and the legacy 'sha256' fallback field"
        )
    return resolved


def _wheel_record_from_dict(d: Dict[str, Any], variant: str) -> Dict[str, Any]:
    embedded = d.get("embedded") or {}
    kroko = embedded.get("kroko") or {}
    record = {
        "filename": _require(d.get("filename"), f"{variant} wheel filename"),
        "sha256": _require(d.get("sha256"), f"{variant} wheel sha256"),
        "pythonTag": _require(d.get("pythonTag"), f"{variant} python tag"),
        "abiTag": _require(d.get("abiTag"), f"{variant} abi tag"),
        "platformTag": _require(d.get("platformTag"), f"{variant} platform tag"),
    }
    fp = d.get("krokoFingerprint") or kroko.get("fingerprint")
    if fp:
        record["krokoFingerprint"] = fp
    sha = d.get("krokoArtifactSha256") or kroko.get("wheelSha256")
    if sha:
        record["krokoArtifactSha256"] = sha
    return record


def distribution_block(
    distribution_manifest: Any,
    build_manifest: Dict[str, Any],
    variant: str,
    *,
    wheels: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """The RC-manifest ``distributions.<variant>`` block for one variant."""
    kroko_payload = build_manifest.get("variants", {}).get(variant, {}).get("kroko", {})
    default_fp = kroko_payload.get("fingerprint") or ""
    default_sha = kroko_artifact_sha256(build_manifest, variant)

    if wheels is None:
        if isinstance(distribution_manifest, dict) and "wheels" in distribution_manifest:
            wheels = [_wheel_record_from_dict(w, variant) for w in distribution_manifest["wheels"]]
        elif isinstance(distribution_manifest, list):
            wheels = [_wheel_record_from_dict(w, variant) for w in distribution_manifest]
        elif isinstance(distribution_manifest, dict) and distribution_manifest.get("filename"):
            wheels = [_wheel_record_from_dict(distribution_manifest, variant)]
        else:
            wheels = []

    enriched_wheels = []
    for w in wheels:
        rec = dict(w)
        if "krokoFingerprint" not in rec and default_fp:
            rec["krokoFingerprint"] = default_fp
        if "krokoArtifactSha256" not in rec and default_sha:
            rec["krokoArtifactSha256"] = default_sha
        enriched_wheels.append(rec)

    dist_name = (
        distribution_manifest.get("distribution")
        or distribution_manifest.get("name")
        if isinstance(distribution_manifest, dict)
        else None
    )
    if not dist_name:
        dist_name = "voice-stt-server-pro" if variant == "pro" else "voice-stt-server"

    return {
        "name": _require(dist_name, f"{variant} distribution name"),
        "krokoVariant": variant,
        "krokoFingerprint": _require(default_fp, f"{variant} Kroko fingerprint"),
        "krokoArtifactSha256": default_sha,
        "wheels": enriched_wheels,
    }


def image_block(
    build_manifest: Dict[str, Any],
    staging_manifest: Dict[str, Any],
    variant: str,
) -> Dict[str, Any]:
    """The RC-manifest ``images.<variant>`` block for one variant."""
    return {
        "tag": _require(
            build_manifest["variants"][variant]["image"]["versionTag"],
            f"{variant} image version tag",
        ),
        "digest": _require(staging_manifest.get("digest"), f"{variant} staging manifest digest"),
        "staging": _require(staging_manifest.get("reference"), f"{variant} staging reference"),
    }


def assemble_rc_manifest(
    *,
    candidate_dir: Path,
    candidate_id: str,
    source_tree: str,
    qualification_timestamp_utc: str,
    qualification_context: str,
    qualification_evidence_ref: str,
    candidate_run: Optional[Dict[str, Any]] = None,
    release_readiness: str = rc_manifest.READINESS_NOT_QUALIFIED,
) -> Dict[str, Any]:
    """Builds one canonical RC manifest from a candidate output directory."""
    candidate_dir = Path(candidate_dir)
    builds: Dict[str, Dict[str, Any]] = {}
    stagings: Dict[str, Dict[str, Any]] = {}
    distributions_out: Dict[str, Dict[str, Any]] = {}

    for variant in rc_manifest.VARIANTS:
        build_path = candidate_dir / BUILD_MANIFEST_TEMPLATE.format(variant=variant)
        staging_path = candidate_dir / STAGING_MANIFEST_TEMPLATE.format(variant=variant)
        dist_path = candidate_dir / DISTRIBUTION_MANIFEST_TEMPLATE.format(variant=variant)

        builds[variant] = _read_json(build_path, f"{variant} production build manifest")
        stagings[variant] = _read_json(staging_path, f"{variant} staging manifest")

        wheels: List[Dict[str, Any]] = []
        seen_platforms = set()
        main_dist: Dict[str, Any] = {}

        if dist_path.is_file():
            main_dist = _read_json(dist_path, f"{variant} distribution manifest")
            if "wheels" in main_dist and isinstance(main_dist["wheels"], list):
                for w in main_dist["wheels"]:
                    wheels.append(_wheel_record_from_dict(w, variant))
                    seen_platforms.add(w.get("platformTag"))
            elif "platformTag" in main_dist:
                wheels.append(_wheel_record_from_dict(main_dist, variant))
                seen_platforms.add(main_dist.get("platformTag"))

        for path in sorted(candidate_dir.glob(f"distribution-{variant}-*.json")):
            plat_data = _read_json(path, f"{variant} platform distribution manifest")
            ptag = plat_data.get("platformTag")
            if ptag and ptag not in seen_platforms:
                wheels.append(_wheel_record_from_dict(plat_data, variant))
                seen_platforms.add(ptag)

        if not wheels:
            raise ManifestError(f"candidate is incomplete: missing {variant} distribution manifest at {dist_path}")

        missing_platforms = [p for p in rc_manifest.REQUIRED_PLATFORMS if p not in seen_platforms]
        if missing_platforms:
            raise ManifestError(
                f"candidate is incomplete: {variant} distribution is missing "
                f"required platform wheel for {missing_platforms} (found: {sorted(seen_platforms)})"
            )

        distributions_out[variant] = distribution_block(
            main_dist, builds[variant], variant, wheels=wheels
        )

    commits = {variant: builds[variant].get("gitCommit") for variant in rc_manifest.VARIANTS}
    if len(set(commits.values())) != 1 or not all(commits.values()):
        raise ManifestError(
            f"the Free and Pro halves of this candidate were built from different "
            f"commits: {commits}"
        )
    source_commit = commits["free"]

    versions = {
        variant: builds[variant].get("voicesttVersion") for variant in rc_manifest.VARIANTS
    }
    if len(set(versions.values())) != 1 or not all(versions.values()):
        raise ManifestError(
            f"the Free and Pro halves of this candidate declare different product "
            f"versions: {versions}"
        )
    product_version = versions["free"]

    dirty = [v for v in rc_manifest.VARIANTS if builds[v].get("gitDirty")]
    if dirty:
        raise ManifestError(
            f"refusing to assemble a release candidate from a dirty working tree "
            f"(variants: {dirty}) - a candidate must bind an exact committed source"
        )

    return rc_manifest.build_rc_manifest(
        candidate_id=candidate_id,
        product_version=product_version,
        source_commit=source_commit,
        source_tree=source_tree,
        distributions=distributions_out,
        images={
            variant: image_block(builds[variant], stagings[variant], variant)
            for variant in rc_manifest.VARIANTS
        },
        oci_version=product_version,
        oci_revision=source_commit,
        qualification_timestamp_utc=qualification_timestamp_utc,
        qualification_context=qualification_context,
        qualification_evidence_ref=qualification_evidence_ref,
        candidate_run=candidate_run,
        release_readiness=release_readiness,
    )


__all__ = [
    "BUILD_MANIFEST_TEMPLATE",
    "DISTRIBUTION_MANIFEST_TEMPLATE",
    "STAGING_MANIFEST_TEMPLATE",
    "kroko_artifact_sha256",
    "distribution_block",
    "image_block",
    "assemble_rc_manifest",
]
