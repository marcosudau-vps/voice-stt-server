"""The canonical release-candidate manifest (AP-SRV-070 W5-R04, schema v2).

One frozen manifest describes exactly one qualified candidate, and publication
refuses to touch anything that does not match it. This module only defines the
format, validates it, and assembles one from identities that already exist
elsewhere - it never recomputes or second-guesses an identity itself.

What changed in schema v2
-------------------------

Schema v1 described a single ``voicestt`` wheel plus an sdist. That no longer
describes the product. VoiceSTT now publishes **two complete alternative
distributions**, each embedding a different, non-interchangeable native Kroko
runtime:

.. code-block:: text

    voice-stt-server      <- Kroko Free native runtime
    voice-stt-server-pro  <- Kroko Pro native runtime

So the manifest binds a ``distributions`` block with one entry per public
distribution, each carrying its own wheel set (filename, SHA-256, interpreter
and platform tags), the Kroko variant it embeds, and that variant's fingerprint
and embedded artifact SHA-256. The identity chain
``Kroko artifact -> distribution wheel -> PyPI`` is therefore checkable end to
end from this one document.

Two further v2 corrections:

* ``images.<variant>.digest`` records the **OCI manifest digest**. v1 recorded
  only a local ``docker inspect`` image ``Id``, which is not the identity a
  registry can be checked against and not the identity
  ``docker buildx imagetools create`` promotes.
* ``staging`` records where the qualified image bytes live between
  qualification and publication, so publication consumes the qualified
  manifest instead of rebuilding it.

**No sdist.** See ``docs/release-process.md``: an sdist of a distribution whose
defining property is an embedded native runtime cannot carry that runtime, so
installing from it would either trigger a ~30-minute local native build or
silently produce an installation with no Kroko runtime at all. Publishing a
wheel for every documented platform is what keeps ``pip install
voice-stt-server`` complete without a local build.

No secret ever belongs in an RC manifest: it is evidence, archived next to the
qualification gates it backs.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .errors import ManifestError
from .redaction import assert_no_secrets

SCHEMA_VERSION = 2

READINESS_NOT_QUALIFIED = "NOT_QUALIFIED"
READINESS_QUALIFIED = "QUALIFIED"
READINESS_REJECTED = "REJECTED"
READINESS_STATES = (READINESS_NOT_QUALIFIED, READINESS_QUALIFIED, READINESS_REJECTED)

#: The two build-time product variants. Free/Pro is decided at build time and
#: is never influenced by a runtime Kroko license key.
VARIANTS = ("free", "pro")

#: The binding packaging authority requires both Linux and Windows wheels for
#: CPython 3.12 (AP-SRV-070 W5-R04, B2).
REQUIRED_PLATFORMS = ("linux_x86_64", "win_amd64")

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
#: Candidate ids come from two places: a manual ``W5-RC<n>`` freeze, and a
#: GitHub candidate workflow run (``gh-<run-id>-<attempt>``). Both must be
#: stable, filesystem-safe and unambiguous.
_CANDIDATE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$")


def _require(condition: bool, message: str, problems: List[str]) -> None:
    if not condition:
        problems.append(message)


def _require_wheel_block(block: Any, name: str, problems: List[str]) -> None:
    if not isinstance(block, dict):
        problems.append(f"{name} must be an object")
        return
    _require(
        isinstance(block.get("filename"), str) and block.get("filename", "").endswith(".whl"),
        f"{name}.filename must be a wheel filename",
        problems,
    )
    _require(
        bool(_SHA256_RE.match(block.get("sha256") or "")),
        f"{name}.sha256 must be a 64-character lowercase hex sha256",
        problems,
    )
    for field in ("pythonTag", "abiTag", "platformTag"):
        _require(
            isinstance(block.get(field), str) and block.get(field, "").strip() != "",
            f"{name}.{field} must be a non-empty string",
            problems,
        )
    ptag = block.get("platformTag")
    if ptag is not None:
        _require(
            ptag in REQUIRED_PLATFORMS,
            f"{name}.platformTag must be one of {REQUIRED_PLATFORMS}, got {ptag!r}",
            problems,
        )
    if "krokoFingerprint" in block:
        _require(
            isinstance(block.get("krokoFingerprint"), str) and block.get("krokoFingerprint", "").strip() != "",
            f"{name}.krokoFingerprint must be a non-empty string",
            problems,
        )
    if "krokoArtifactSha256" in block:
        _require(
            bool(_SHA256_RE.match(block.get("krokoArtifactSha256") or "")),
            f"{name}.krokoArtifactSha256 must be a 64-character lowercase hex sha256",
            problems,
        )


def _require_distribution_block(block: Any, name: str, variant: str, problems: List[str]) -> None:
    if not isinstance(block, dict):
        problems.append(f"{name} must be an object")
        return
    _require(
        isinstance(block.get("name"), str) and block.get("name", "").strip() != "",
        f"{name}.name must be a non-empty PyPI distribution name",
        problems,
    )
    _require(
        block.get("krokoVariant") == variant,
        f"{name}.krokoVariant must be {variant!r}",
        problems,
    )
    _require(
        isinstance(block.get("krokoFingerprint"), str) and block.get("krokoFingerprint", "").strip() != "",
        f"{name}.krokoFingerprint must be a non-empty string",
        problems,
    )
    _require(
        bool(_SHA256_RE.match(block.get("krokoArtifactSha256") or "")),
        f"{name}.krokoArtifactSha256 must be a 64-character lowercase hex sha256",
        problems,
    )
    wheels = block.get("wheels")
    if not isinstance(wheels, list) or not wheels:
        problems.append(f"{name}.wheels must be a non-empty list")
        return
    for index, wheel in enumerate(wheels):
        _require_wheel_block(wheel, f"{name}.wheels[{index}]", problems)
    filenames = [w.get("filename") for w in wheels if isinstance(w, dict)]
    _require(
        len(filenames) == len(set(filenames)),
        f"{name}.wheels must not list the same filename twice",
        problems,
    )
    platforms = [w.get("platformTag") for w in wheels if isinstance(w, dict) and w.get("platformTag")]
    _require(
        len(platforms) == len(set(platforms)),
        f"{name}.wheels must not list duplicate platform tags: {platforms}",
        problems,
    )
    for req_platform in REQUIRED_PLATFORMS:
        _require(
            req_platform in platforms,
            f"{name}.wheels must include a wheel for platform {req_platform!r}",
            problems,
        )


def _require_image_block(block: Any, name: str, problems: List[str]) -> None:
    if not isinstance(block, dict):
        problems.append(f"{name} must be an object")
        return
    _require(
        isinstance(block.get("tag"), str) and block.get("tag", "").strip() != "",
        f"{name}.tag must be a non-empty string",
        problems,
    )
    _require(
        bool(_DIGEST_RE.match(block.get("digest") or "")),
        f"{name}.digest must be an OCI manifest digest (sha256:<64 hex>)",
        problems,
    )
    staging = block.get("staging")
    _require(
        isinstance(staging, str) and "@sha256:" in (staging or ""),
        f"{name}.staging must be a digest-pinned staging reference",
        problems,
    )


def validate_rc_manifest(data: Dict[str, Any]) -> None:
    """Raises :class:`ManifestError` listing every problem found in ``data``.

    Validates shape and identity completeness only - it never checks the
    identities against the real filesystem or a registry; that is
    ``release_tooling.remote_checks``'s job at preflight/publish time.
    """
    problems: List[str] = []
    if not isinstance(data, dict):
        raise ManifestError("RC manifest must be a JSON object")

    _require(data.get("schemaVersion") == SCHEMA_VERSION, f"schemaVersion must be {SCHEMA_VERSION}", problems)
    _require(
        bool(_CANDIDATE_ID_RE.match(data.get("candidateId") or "")),
        "candidateId must be a stable identifier such as 'W5-RC1' or 'gh-<run-id>-<attempt>'",
        problems,
    )
    _require(
        isinstance(data.get("productVersion"), str) and data.get("productVersion", "").strip() != "",
        "productVersion must be a non-empty string",
        problems,
    )
    _require(bool(_COMMIT_RE.match(data.get("sourceCommit") or "")), "sourceCommit must be a 40-character lowercase hex commit hash", problems)
    _require(bool(_COMMIT_RE.match(data.get("sourceTree") or "")), "sourceTree must be a 40-character lowercase hex tree hash", problems)

    distributions = data.get("distributions")
    if not isinstance(distributions, dict):
        problems.append("distributions must be an object with 'free' and 'pro' entries")
    else:
        for variant in VARIANTS:
            _require_distribution_block(
                distributions.get(variant), f"distributions.{variant}", variant, problems
            )
        names = [
            block.get("name")
            for block in distributions.values()
            if isinstance(block, dict)
        ]
        _require(
            len(names) == len(set(names)),
            "the Free and Pro distributions must have different PyPI names",
            problems,
        )

    images = data.get("images")
    if not isinstance(images, dict):
        problems.append("images must be an object with 'free' and 'pro' entries")
    else:
        for variant in VARIANTS:
            _require_image_block(images.get(variant), f"images.{variant}", problems)
        digests = [
            block.get("digest")
            for block in images.values()
            if isinstance(block, dict)
        ]
        _require(
            len(digests) == len(set(digests)),
            "the Free and Pro images must not share one manifest digest",
            problems,
        )

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
        for field in ("timestampUtc", "context", "evidenceRef"):
            _require(
                isinstance(qualification.get(field), str) and qualification.get(field, "").strip() != "",
                f"qualification.{field} must be a non-empty string",
                problems,
            )

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
    distributions: Dict[str, Dict[str, Any]],
    images: Dict[str, Dict[str, Any]],
    oci_version: str,
    oci_revision: str,
    qualification_timestamp_utc: str,
    qualification_context: str,
    qualification_evidence_ref: str,
    candidate_run: Optional[Dict[str, Any]] = None,
    release_readiness: str = READINESS_NOT_QUALIFIED,
) -> Dict[str, Any]:
    """Assembles one canonical RC manifest from already-resolved identities."""
    manifest: Dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "candidateId": candidate_id,
        "productVersion": product_version,
        "sourceCommit": source_commit,
        "sourceTree": source_tree,
        "distributions": {
            variant: dict(distributions[variant]) for variant in VARIANTS
        },
        "images": {variant: dict(images[variant]) for variant in VARIANTS},
        "oci": {"version": oci_version, "revision": oci_revision},
        "candidateRun": dict(candidate_run or {}),
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


def manifest_sha256(manifest: Dict[str, Any]) -> str:
    """The SHA-256 of the manifest's canonical serialization.

    Used as the candidate-binding fingerprint in the release state, so a
    resume can prove it is continuing the exact qualified candidate rather
    than a look-alike (AP-SRV-070 W5-R04, section 13).
    """
    import hashlib

    canonical = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def distribution_names(manifest: Dict[str, Any]) -> Dict[str, str]:
    """``{variant: pypi distribution name}`` for both public distributions."""
    return {
        variant: manifest["distributions"][variant]["name"] for variant in VARIANTS
    }


def state_identity(manifest: Dict[str, Any]) -> Dict[str, Dict[str, Dict[str, str]]]:
    """The compact artifact identity a :class:`ReleaseState` binds.

    One authority for "what identity does this candidate have", so the state
    file, a resume check and the publish CLI can never derive it three
    slightly different ways. Deliberately flattened to plain strings: a
    release state is evidence that gets diffed by humans, and a stable,
    sorted ``file=sha256;file=sha256`` summary compares far more usefully
    than a nested list whose order could drift.
    """
    distributions = {}
    for variant in VARIANTS:
        block = manifest["distributions"][variant]
        wheels = ";".join(
            f"{wheel['filename']}={wheel['sha256']}"
            for wheel in sorted(block["wheels"], key=lambda w: w["filename"])
        )
        distributions[variant] = {"name": block["name"], "wheels": wheels}
    images = {
        variant: {
            "tag": manifest["images"][variant]["tag"],
            "digest": manifest["images"][variant]["digest"],
        }
        for variant in VARIANTS
    }
    return {"distributions": distributions, "images": images}


def candidate_identity(manifest: Dict[str, Any]) -> Dict[str, str]:
    """The candidate binding a resume must match (section 13).

    Ties a release state to the exact qualified candidate that produced it:
    the candidate id, the workflow run behind it, and the SHA-256 of the
    manifest document itself. A second candidate run for the same version
    produces a different manifest hash, so a resume against it fails closed
    instead of silently continuing with a look-alike rebuild.
    """
    run = manifest.get("candidateRun") or {}
    return {
        "candidateId": manifest["candidateId"],
        "manifestSha256": manifest_sha256(manifest),
        "runId": str(run.get("runId", "")),
        "runAttempt": str(run.get("runAttempt", "")),
    }


def expected_pypi_files(manifest: Dict[str, Any], variant: str) -> Dict[str, str]:
    """The ``{filename: sha256}`` pairs a PyPI check needs for one variant."""
    block = manifest["distributions"][variant]
    return {wheel["filename"]: wheel["sha256"] for wheel in block["wheels"]}


def expected_image_digest(manifest: Dict[str, Any], variant: str) -> Optional[str]:
    """The recorded OCI manifest digest for one variant, or ``None``."""
    block = manifest.get("images", {}).get(variant)
    if not block:
        return None
    return block.get("digest")


def staging_reference(manifest: Dict[str, Any], variant: str) -> Optional[str]:
    """The digest-pinned private staging reference for one variant."""
    block = manifest.get("images", {}).get(variant)
    if not block:
        return None
    return block.get("staging")


def qualify_manifest(
    manifest: Dict[str, Any],
    *,
    evidence_ref: str,
    context: Optional[str] = None,
    timestamp_utc: Optional[str] = None,
) -> Dict[str, Any]:
    """Transitions a candidate manifest to QUALIFIED status (Option A).

    Binds the exact candidate artifact identities without rebuild.
    """
    if not evidence_ref or not str(evidence_ref).strip():
        raise ManifestError("evidence_ref must be a non-empty string to qualify a candidate")
    updated = json.loads(json.dumps(manifest))
    updated["releaseReadiness"] = READINESS_QUALIFIED
    qualification = updated.setdefault("qualification", {})
    qualification["evidenceRef"] = str(evidence_ref).strip()
    qualification["timestampUtc"] = (
        timestamp_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    if context:
        qualification["context"] = str(context).strip()
    validate_rc_manifest(updated)
    return updated


__all__ = [
    "SCHEMA_VERSION",
    "VARIANTS",
    "REQUIRED_PLATFORMS",
    "READINESS_NOT_QUALIFIED",
    "READINESS_QUALIFIED",
    "READINESS_REJECTED",
    "READINESS_STATES",
    "validate_rc_manifest",
    "build_rc_manifest",
    "qualify_manifest",
    "load_rc_manifest",
    "write_rc_manifest",
    "manifest_sha256",
    "state_identity",
    "candidate_identity",
    "distribution_names",
    "expected_pypi_files",
    "expected_image_digest",
    "staging_reference",
]
