"""Builds one complete public VoiceSTT distribution wheel (AP-SRV-070 W5-R04).

Free and Pro Kroko are technically different, mutually non-interchangeable
native runtimes, so VoiceSTT ships two complete alternative distributions
rather than one distribution plus an end-user native build:

.. code-block:: text

    Kroko Free native wheel  +  VoiceSTT source  ->  voice-stt-server
    Kroko Pro  native wheel  +  VoiceSTT source  ->  voice-stt-server-pro

Both expose the same import package (``voice_stt_server``) and the same CLI
(``voice-stt-server``), so nothing in a user's application changes when an
installation moves between Free and Pro. There is deliberately **no** separate
public ``kroko-onnx-free``/``kroko-onnx-pro`` distribution: the qualified Kroko
wheel stays an internal, fingerprint- and hash-bound intermediate artifact that
is merged into the distribution that ships it.

Why a merge rather than a setuptools build that "includes" Kroko
---------------------------------------------------------------

The Kroko wheel's payload is a compiled artifact that was qualified by
fingerprint and SHA-256 (``VoiceSTT.kroko.*``). Release authority requires that
the exact qualified bytes are what reaches the user, so this module copies them
verbatim out of the qualified wheel instead of asking setuptools to rebuild or
re-vendor them. The merged wheel records the fingerprint and the source
artifact's SHA-256, so the identity chain
``Kroko artifact -> distribution wheel -> PyPI`` is unbroken and checkable.

Determinism
-----------

Every entry in the produced wheel is written with a fixed, source-derived
timestamp and fixed permissions, and the entry order is sorted, so building the
same inputs twice produces byte-identical output. That is what lets a resumed
release re-derive rather than re-invent a candidate.
"""

from __future__ import annotations

import argparse
import hashlib
import base64
import csv
import io
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from VoiceSTT.kroko import buildinputs as kroko_buildinputs  # noqa: E402

#: Must stay identical to ``setup.py``'s mapping - a guard test enforces it.
DISTRIBUTION_VARIANT_ENV = "VOICESTT_DISTRIBUTION_VARIANT"
DISTRIBUTION_NAMES = {
    "free": "voice-stt-server",
    "pro": "voice-stt-server-pro",
}

#: Where the embedded-runtime provenance lands inside the merged wheel.
EMBEDDED_PACKAGE = "voice_stt_server"
EMBEDDED_MANIFEST_NAME = "_embedded_kroko.json"
EMBEDDED_MANIFEST_SCHEMA = 1

#: The Kroko wheel's own ``.dist-info`` is deliberately *not* copied into the
#: merged wheel: shipping another project's installed-distribution metadata
#: inside ours would make ``pip``/``importlib.metadata`` believe a
#: ``kroko-onnx`` distribution is installed that pip never installed and cannot
#: uninstall. The runtime identity is carried by the provenance file instead
#: (see ``voice_stt_server._embedded``). Its licence text *is* copied, because
#: dropping a dependency's licence would be a redistribution defect.
KROKO_LICENSE_DIRNAME = "licenses"

_WHEEL_NAME_RE = re.compile(
    r"^(?P<name>[^-]+)-(?P<version>[^-]+)"
    r"(?:-(?P<build>[^-]+))?"
    r"-(?P<python>[^-]+)-(?P<abi>[^-]+)-(?P<platform>[^-]+)\.whl$"
)


class DistributionBuildError(RuntimeError):
    """A distribution wheel could not be produced, or an input was invalid."""


def normalize_variant(variant: str) -> str:
    value = str(variant or "").strip().lower()
    if value not in DISTRIBUTION_NAMES:
        raise DistributionBuildError(
            f"unknown distribution variant {variant!r}; "
            f"expected one of {sorted(DISTRIBUTION_NAMES)}"
        )
    return value


def distribution_name_for(variant: str) -> str:
    """The public PyPI distribution name for one Kroko variant."""
    return DISTRIBUTION_NAMES[normalize_variant(variant)]


def escaped_name(distribution: str) -> str:
    """The PEP 427 escaped distribution name used inside a wheel filename."""
    return re.sub(r"[^\w\d.]+", "_", distribution, flags=re.UNICODE)


def parse_wheel_filename(filename: str) -> Dict[str, str]:
    """The name/version/build/tag components of a wheel filename."""
    match = _WHEEL_NAME_RE.match(str(filename))
    if not match:
        raise DistributionBuildError(f"not a valid wheel filename: {filename!r}")
    return {key: (value or "") for key, value in match.groupdict().items()}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record_hash(data: bytes) -> str:
    """The ``sha256=<urlsafe-b64-nopad>`` form a wheel RECORD uses."""
    digest = hashlib.sha256(data).digest()
    encoded = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return f"sha256={encoded}"


# --------------------------------------------------------------------------
# 1. The pure base wheel
# --------------------------------------------------------------------------


def build_base_wheel(
    *,
    variant: str,
    out_dir: Path,
    runner=None,
    repo_root: Path = REPO_ROOT,
) -> Path:
    """Builds the variant-named, still platform-independent VoiceSTT wheel.

    ``setup.py`` reads :data:`DISTRIBUTION_VARIANT_ENV` and picks the public
    distribution name, dependency set, CLI entry points and
    ``python_requires`` from it. The native runtime is not involved yet - that
    is :func:`merge_kroko_runtime`'s job.
    """
    variant = normalize_variant(variant)
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    env = dict(os.environ)
    env[DISTRIBUTION_VARIANT_ENV] = variant
    cmd = [sys.executable, "-m", "build", "--wheel", "--outdir", str(out_dir)]
    if runner is None:
        completed = subprocess.run(
            cmd, cwd=str(repo_root), env=env, text=True, capture_output=True,
            encoding="utf-8", errors="replace",
        )
        if completed.returncode != 0:
            raise DistributionBuildError(
                f"base wheel build failed for variant {variant!r} "
                f"(exit {completed.returncode}): {completed.stderr.strip()}"
            )
    else:
        runner(cmd, cwd=repo_root, env=env)

    wheels = sorted(out_dir.glob("*.whl"))
    if len(wheels) != 1:
        raise DistributionBuildError(
            f"expected exactly one base wheel for variant {variant!r}, got {wheels}"
        )
    return wheels[0]


# --------------------------------------------------------------------------
# 2. The merge
# --------------------------------------------------------------------------


def _dist_info_dir(names: Sequence[str], *, what: str) -> str:
    candidates = sorted({
        name.split("/")[0]
        for name in names
        if "/" in name and name.split("/")[0].endswith(".dist-info")
    })
    if len(candidates) != 1:
        raise DistributionBuildError(
            f"expected exactly one .dist-info directory in the {what} wheel, "
            f"got {candidates}"
        )
    return candidates[0]


def kroko_payload_names(kroko_names: Sequence[str], kroko_dist_info: str) -> List[str]:
    """Everything in the Kroko wheel that is actually runtime payload.

    That is the whole wheel except its own ``.dist-info`` - which means the
    ``kroko_onnx`` and ``sherpa_onnx`` packages *and* the top-level
    ``_sherpa_onnx...`` extension module that sits beside them.
    """
    return [
        name
        for name in kroko_names
        if not name.startswith(kroko_dist_info + "/") and not name.endswith("/")
    ]


def build_embedded_manifest(
    *,
    variant: str,
    kroko_wheel: Path,
    kroko_wheel_sha256: str,
    fingerprint: Optional[str],
    product_version: str,
) -> Dict[str, Any]:
    """The provenance document the merged wheel carries.

    This is what makes "the installed distribution decides the runtime" a
    checkable fact rather than a claim, and it is what
    ``VoiceSTT.kroko.artifacts.verify_installed_runtime`` reads first.
    """
    parsed = parse_wheel_filename(Path(kroko_wheel).name)
    return {
        "schemaVersion": EMBEDDED_MANIFEST_SCHEMA,
        "variant": normalize_variant(variant),
        "distribution": distribution_name_for(variant),
        "productVersion": product_version,
        "kroko": {
            "name": parsed["name"],
            "version": parsed["version"],
            "buildTag": parsed["build"],
            "wheelFilename": Path(kroko_wheel).name,
            "wheelSha256": kroko_wheel_sha256,
            "fingerprint": fingerprint or "",
            "upstreamRepo": kroko_buildinputs.KROKO_UPSTREAM_REPO,
            "upstreamRevision": kroko_buildinputs.KROKO_UPSTREAM_REVISION,
        },
        "pythonTag": parsed["python"],
        "abiTag": parsed["abi"],
        "platformTag": parsed["platform"],
        # Stated explicitly so nothing downstream is tempted to reintroduce
        # key-driven runtime selection (new authority section 13).
        "runtimeSelectedBy": "installed-distribution",
        "licenseKeyIsRuntimeCredentialOnly": True,
    }


def merge_kroko_runtime(
    *,
    base_wheel: Path,
    kroko_wheel: Path,
    variant: str,
    out_dir: Path,
    fingerprint: Optional[str] = None,
    timestamp: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Merges the qualified Kroko runtime into the base wheel.

    Produces a platform-tagged wheel whose tag comes from the Kroko wheel
    itself, because the Kroko wheel is the only part of the result that is
    genuinely platform- and interpreter-specific. Returns the resulting
    identity (path, filename, sha256, tags, embedded manifest).
    """
    variant = normalize_variant(variant)
    base_wheel = Path(base_wheel)
    kroko_wheel = Path(kroko_wheel)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    kroko_tags = parse_wheel_filename(kroko_wheel.name)
    base_tags = parse_wheel_filename(base_wheel.name)
    distribution = distribution_name_for(variant)
    version = base_tags["version"]

    target_name = (
        f"{escaped_name(distribution)}-{version}"
        f"-{kroko_tags['python']}-{kroko_tags['abi']}-{kroko_tags['platform']}.whl"
    )
    target_path = out_dir / target_name

    stamp = timestamp or datetime(1980, 1, 1, tzinfo=timezone.utc)
    zip_date = (stamp.year, stamp.month, stamp.day, stamp.hour, stamp.minute, stamp.second)

    with zipfile.ZipFile(base_wheel) as base_zip, zipfile.ZipFile(kroko_wheel) as kroko_zip:
        base_names = base_zip.namelist()
        kroko_names = kroko_zip.namelist()
        base_dist_info = _dist_info_dir(base_names, what="base")
        kroko_dist_info = _dist_info_dir(kroko_names, what="Kroko")

        payload_names = kroko_payload_names(kroko_names, kroko_dist_info)
        collisions = sorted(set(payload_names) & set(base_names))
        if collisions:
            raise DistributionBuildError(
                "the Kroko runtime and the VoiceSTT wheel both provide "
                f"{collisions[:5]} - refusing to silently overwrite payload"
            )

        entries: List[Tuple[str, bytes]] = []

        # 1. Everything from the base wheel except the files the merge rewrites.
        rewritten = {
            f"{base_dist_info}/WHEEL",
            f"{base_dist_info}/RECORD",
        }
        for name in base_names:
            if name.endswith("/") or name in rewritten:
                continue
            entries.append((name, base_zip.read(name)))

        # 2. The qualified Kroko runtime payload, byte for byte.
        for name in payload_names:
            entries.append((name, kroko_zip.read(name)))

        # 3. Kroko's licence text, so redistribution stays correct.
        for name in kroko_names:
            if name.startswith(f"{kroko_dist_info}/{KROKO_LICENSE_DIRNAME}/"):
                leaf = name.rsplit("/", 1)[-1]
                entries.append((
                    f"{base_dist_info}/{KROKO_LICENSE_DIRNAME}/KROKO-ONNX-{leaf}",
                    kroko_zip.read(name),
                ))

        # 4. The embedded-runtime provenance.
        embedded = build_embedded_manifest(
            variant=variant,
            kroko_wheel=kroko_wheel,
            kroko_wheel_sha256=sha256_of(kroko_wheel),
            fingerprint=fingerprint,
            product_version=version,
        )
        entries.append((
            f"{EMBEDDED_PACKAGE}/{EMBEDDED_MANIFEST_NAME}",
            (json.dumps(embedded, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        ))

        # 5. A WHEEL file that tells the truth about the merged result.
        wheel_metadata = _rewrite_wheel_metadata(
            base_zip.read(f"{base_dist_info}/WHEEL").decode("utf-8"),
            tag=f"{kroko_tags['python']}-{kroko_tags['abi']}-{kroko_tags['platform']}",
        )
        entries.append((f"{base_dist_info}/WHEEL", wheel_metadata.encode("utf-8")))

    entries.sort(key=lambda item: item[0])

    record_rows = [
        (name, _record_hash(data), str(len(data))) for name, data in entries
    ]
    record_rows.append((f"{base_dist_info}/RECORD", "", ""))
    record_buffer = io.StringIO()
    writer = csv.writer(record_buffer, lineterminator="\n")
    for row in record_rows:
        writer.writerow(row)
    entries.append((f"{base_dist_info}/RECORD", record_buffer.getvalue().encode("utf-8")))

    with zipfile.ZipFile(target_path, "w", zipfile.ZIP_DEFLATED) as out_zip:
        for name, data in entries:
            info = zipfile.ZipInfo(name, date_time=zip_date)
            info.external_attr = (0o644 & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            out_zip.writestr(info, data)

    return {
        "variant": variant,
        "distribution": distribution,
        "version": version,
        "path": str(target_path),
        "filename": target_name,
        "sha256": sha256_of(target_path),
        "bytes": target_path.stat().st_size,
        "pythonTag": kroko_tags["python"],
        "abiTag": kroko_tags["abi"],
        "platformTag": kroko_tags["platform"],
        "embedded": embedded,
    }


def _rewrite_wheel_metadata(text: str, *, tag: str) -> str:
    """Rewrites a base wheel's ``WHEEL`` file for the merged, impure result."""
    lines = [
        line
        for line in text.splitlines()
        if not line.lower().startswith(("tag:", "root-is-purelib:"))
    ]
    lines.append("Root-Is-Purelib: false")
    lines.append(f"Tag: {tag}")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# 3. CLI
# --------------------------------------------------------------------------


def build_distribution(
    *,
    variant: str,
    kroko_wheel: Path,
    out_dir: Path,
    work_dir: Path,
    fingerprint: Optional[str] = None,
    timestamp: Optional[datetime] = None,
    runner=None,
) -> Dict[str, Any]:
    """Builds one complete public distribution wheel end to end."""
    variant = normalize_variant(variant)
    base_wheel = build_base_wheel(
        variant=variant, out_dir=Path(work_dir) / f"base-{variant}", runner=runner
    )
    return merge_kroko_runtime(
        base_wheel=base_wheel,
        kroko_wheel=Path(kroko_wheel),
        variant=variant,
        out_dir=Path(out_dir),
        fingerprint=fingerprint,
        timestamp=timestamp,
    )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="build_distribution.py",
        description=(
            "AP-SRV-070 W5-R04: build one complete public VoiceSTT "
            "distribution wheel with its qualified Kroko runtime embedded."
        ),
    )
    parser.add_argument("variant", choices=sorted(DISTRIBUTION_NAMES))
    parser.add_argument("--kroko-wheel", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--work-dir", default=None, type=Path)
    parser.add_argument("--fingerprint", default=None)
    parser.add_argument(
        "--source-date", default=None,
        help="ISO-8601 timestamp stamped on every wheel entry (default: a "
             "fixed epoch, so the result is reproducible).",
    )
    parser.add_argument("--manifest-out", default=None, type=Path)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    timestamp = (
        datetime.fromisoformat(args.source_date).astimezone(timezone.utc)
        if args.source_date
        else None
    )
    try:
        result = build_distribution(
            variant=args.variant,
            kroko_wheel=args.kroko_wheel,
            out_dir=args.out_dir,
            work_dir=args.work_dir or (args.out_dir / "work"),
            fingerprint=args.fingerprint,
            timestamp=timestamp,
        )
    except DistributionBuildError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    if args.manifest_out:
        args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_out.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
