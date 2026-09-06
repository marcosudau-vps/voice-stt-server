"""The canonical RC manifest format (AP-SRV-070 W5, section 12).

W5-R02 freezes exactly one RC manifest per candidate (``W5-RC1``, ``W5-RC2``,
...) and W6 refuses to publish anything that does not match it. This module
only defines the format, validates it, and assembles one from the artifact
identities that already exist elsewhere (the VoiceSTT wheel/sdist, and the
Free/Pro ``tools/build_production.py`` build manifests) - it does not
recompute or second-guess any of those identities itself.

No secret ever belongs in an RC manifest: it is meant to be evidence,
checked into the run archive next to the qualification gates it backs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

from .errors import ManifestError
from .redaction import assert_no_secrets

SCHEMA_VERSION = 1

READINESS_NOT_QUALIFIED = "NOT_QUALIFIED"
READINESS_QUALIFIED = "QUALIFIED"
READINESS_REJECTED = "REJECTED"
READINESS_STATES = (READINESS_NOT_QUALIFIED, READINESS_QUALIFIED, READINESS_REJECTED)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def _require(condition: bool, message: str, problems: list) -> None:
    if not condition:
        problems.append(message)


def _require_artifact_block(block: Any, name: str, problems: list) -> None:
    if not isinstance(block, dict):
        problems.append(f"{name} must be an object")
        return
    filename = block.get("filename")
    sha256 = block.get("sha256")
    _require(isinstance(filename, str) and filename.strip() != "", f"{name}.filename must be a non-empty string", problems)
    _require(isinstance(sha256, str) and bool(_SHA256_RE.match(sha256 or "")), f"{name}.sha256 must be a 64-character lowercase hex sha256", problems)


def _require_kroko_block(block: Any, name: str, problems: list) -> None:
    if not isinstance(block, dict):
        problems.append(f"{name} must be an object")
        return
    fingerprint = block.get("fingerprint")
    artifact_sha256 = block.get("artifactSha256")
    _require(isinstance(fingerprint, str) and fingerprint.strip() != "", f"{name}.fingerprint must be a non-empty string", problems)
    _require(isinstance(artifact_sha256, str) and bool(_SHA256_RE.match(artifact_sha256 or "")), f"{name}.artifactSha256 must be a 64-character lowercase hex sha256", problems)


def _require_image_block(block: Any, name: str, problems: list) -> None:
    if not isinstance(block, dict):
        problems.append(f"{name} must be an object")
        return
    tag = block.get("tag")
    image_id = block.get("imageId")
    _require(isinstance(tag, str) and tag.strip() != "", f"{name}.tag must be a non-empty string", problems)
    _require(isinstance(image_id, str) and image_id.strip() != "", f"{name}.imageId must be a non-empty string", problems)


def validate_rc_manifest(data: Dict[str, Any]) -> None:
    """Raises :class:`ManifestError` listing every problem found in ``data``.

    Validates shape/identity completeness only - it never checks the
    identities against the real filesystem/registries; that is
    ``release_tooling.remote_checks``'s job at preflight/publish time.
    """
    problems: list = []
    if not isinstance(data, dict):
        raise ManifestError("RC manifest must be a JSON object")

    _require(data.get("schemaVersion") == SCHEMA_VERSION, f"schemaVersion must be {SCHEMA_VERSION}", problems)
    _require(isinstance(data.get("candidateId"), str) and bool(re.match(r"^W5-RC\d+$", data.get("candidateId") or "")), "candidateId must look like 'W5-RC<n>'", problems)
    _require(isinstance(data.get("productVersion"), str) and data.get("productVersion", "").strip() != "", "productVersion must be a non-empty string", problems)
    _require(bool(_COMMIT_RE.match(data.get("sourceCommit") or "")), "sourceCommit must be a 40-character lowercase hex commit hash", problems)
    _require(bool(_COMMIT_RE.match(data.get("sourceTree") or "")), "sourceTree must be a 40-character lowercase hex tree hash", problems)

    _require_artifact_block(data.get("wheel"), "wheel", problems)
    _require_artifact_block(data.get("sdist"), "sdist", problems)

    kroko = data.get("kroko")
    if not isinstance(kroko, dict):
        problems.append("kroko must be an object with 'free' and 'pro' entries")
    else:
        _require_kroko_block(kroko.get("free"), "kroko.free", problems)
        _require_kroko_block(kroko.get("pro"), "kroko.pro", problems)

    images = data.get("images")
    if not isinstance(images, dict):
        problems.append("images must be an object with 'free' and 'pro' entries")
    else:
        _require_image_block(images.get("free"), "images.free", problems)
        _require_image_block(images.get("pro"), "images.pro", problems)

    oci = data.get("oci")
    if not isinstance(oci, dict):
        problems.append("oci must be an object with 'version' and 'revision'")
    else:
        _require(isinstance(oci.get("version"), str) and oci.get("version", "").strip() != "", "oci.version must be a non-empty string", problems)
        _require(bool(_COMMIT_RE.match(oci.get("revision") or "")), "oci.revision must be a 40-character lowercase hex commit hash", problems)

    qualification = data.get("qualification")
    if not isinstance(qualification, dict):
        problems.append("qualification must be an object with 'timestampUtc', 'context' and 'evidenceRef'")
    else:
        _require(isinstance(qualification.get("timestampUtc"), str) and qualification.get("timestampUtc", "").strip() != "", "qualification.timestampUtc must be a non-empty string", problems)
        _require(isinstance(qualification.get("context"), str) and qualification.get("context", "").strip() != "", "qualification.context must be a non-empty string", problems)
        _require(isinstance(qualification.get("evidenceRef"), str) and qualification.get("evidenceRef", "").strip() != "", "qualification.evidenceRef must be a non-empty string", problems)

    _require(data.get("releaseReadiness") in READINESS_STATES, f"releaseReadiness must be one of {READINESS_STATES}", problems)

    if problems:
        raise ManifestError("RC manifest is invalid: " + "; ".join(problems))

    # Shape is valid; now the one cross-cutting content rule that is not a
    # per-field shape check: no secret-shaped field anywhere in the document.
    assert_no_secrets(data)


def build_rc_manifest(
    *,
    candidate_id: str,
    product_version: str,
    source_commit: str,
    source_tree: str,
    wheel_path: Path,
    wheel_sha256: str,
    sdist_path: Path,
    sdist_sha256: str,
    kroko_free_fingerprint: str,
    kroko_free_artifact_sha256: str,
    kroko_pro_fingerprint: str,
    kroko_pro_artifact_sha256: str,
    free_image_tag: str,
    free_image_id: str,
    pro_image_tag: str,
    pro_image_id: str,
    oci_version: str,
    oci_revision: str,
    qualification_timestamp_utc: str,
    qualification_context: str,
    qualification_evidence_ref: str,
    release_readiness: str = READINESS_NOT_QUALIFIED,
) -> Dict[str, Any]:
    """Assembles one canonical RC manifest document from already-resolved identities."""
    manifest: Dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "candidateId": candidate_id,
        "productVersion": product_version,
        "sourceCommit": source_commit,
        "sourceTree": source_tree,
        "wheel": {"filename": Path(wheel_path).name, "sha256": wheel_sha256},
        "sdist": {"filename": Path(sdist_path).name, "sha256": sdist_sha256},
        "kroko": {
            "free": {"fingerprint": kroko_free_fingerprint, "artifactSha256": kroko_free_artifact_sha256},
            "pro": {"fingerprint": kroko_pro_fingerprint, "artifactSha256": kroko_pro_artifact_sha256},
        },
        "images": {
            "free": {"tag": free_image_tag, "imageId": free_image_id},
            "pro": {"tag": pro_image_tag, "imageId": pro_image_id},
        },
        "oci": {"version": oci_version, "revision": oci_revision},
        "qualification": {
            "timestampUtc": qualification_timestamp_utc,
            "context": qualification_context,
            "evidenceRef": qualification_evidence_ref,
        },
        "releaseReadiness": release_readiness,
    }
    validate_rc_manifest(manifest)
    return manifest


def load_rc_manifest(path: Path) -> Dict[str, Any]:
    """Loads, validates, and returns one RC manifest from disk."""
    path = Path(path)
    if not path.is_file():
        raise ManifestError(f"RC manifest not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ManifestError(f"RC manifest at {path} is not valid JSON: {exc}") from exc
    validate_rc_manifest(data)
    return data


def write_rc_manifest(path: Path, manifest: Dict[str, Any]) -> None:
    """Validates and atomically writes ``manifest`` to ``path``."""
    validate_rc_manifest(manifest)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def find_expected_wheel_sdist(
    manifest: Dict[str, Any],
) -> Dict[str, Dict[str, str]]:
    """The ``{filename: sha256}`` pairs a PyPI conflict check needs."""
    return {
        manifest["wheel"]["filename"]: manifest["wheel"]["sha256"],
        manifest["sdist"]["filename"]: manifest["sdist"]["sha256"],
    }


def expected_image_digest(manifest: Dict[str, Any], variant: str) -> Optional[str]:
    """The recorded image identity for one variant ('free'/'pro'), or ``None``."""
    block = manifest.get("images", {}).get(variant)
    if not block:
        return None
    return block.get("imageId")


__all__ = [
    "SCHEMA_VERSION",
    "READINESS_NOT_QUALIFIED",
    "READINESS_QUALIFIED",
    "READINESS_REJECTED",
    "READINESS_STATES",
    "validate_rc_manifest",
    "build_rc_manifest",
    "load_rc_manifest",
    "write_rc_manifest",
    "find_expected_wheel_sdist",
    "expected_image_digest",
]
