"""Deterministic package-data authority for the bundled wake-word assets.

The source tree under ``VoiceSTT/assets/wakeword_models/`` carries more files
than the product publicly manifests: historical/experimental wake-word
variants that were never wired into ``models.json`` (see
``tools/sync_wakeword_assets.py`` and the AP-SRV-070 W2-C2 root correction).
``setup.py`` used to select package data with broad ``*.onnx`` / ``*.tflite``
globs, which would silently sweep those unmanifested files into the public
wheel/sdist right along with the real, supported catalog.

This module is the single place that turns the already-synced, committed
``models.json`` manifest into the exact file list Python packaging is allowed
to ship. It only reads the target manifest that
``tools/sync_wakeword_assets.py`` produces; it never talks to that tool's
upstream ``--source`` authority, and it never hand-lists model filenames -
that would just be a second, independently maintained model catalog.

Kept at the repository root, next to ``setup.py``, so both a normal
``python setup.py ...`` invocation and a PEP 517 build (which executes
``setup.py`` from the unpacked project/sdist root) can import it as a plain
sibling module without any packaging of its own.
"""

from __future__ import annotations

import json
import pathlib
from typing import List

MANIFEST_NAME = "models.json"

#: Wake assets that are bundled but intentionally not part of the
#: ``models.json`` manifest (see ``AUXILIARY_ASSETS`` in
#: ``tools/sync_wakeword_assets.py`` for why, and for their upstream
#: provenance). These filenames are the committed, target-side counterpart.
AUXILIARY_ASSET_FILENAMES = ("silero_vad.onnx",)


def manifested_filenames(models_json_path: pathlib.Path) -> List[str]:
    """Every classifier/pipeline filename the manifest actually declares."""
    payload = json.loads(pathlib.Path(models_json_path).read_text(encoding="utf-8"))
    filenames = set()
    for entry in payload.get("wakeWords", []):
        for artifact in (entry.get("artifacts") or {}).values():
            filename = (artifact or {}).get("file")
            if filename:
                filenames.add(str(filename))
    for framework_section in (payload.get("pipeline") or {}).values():
        for role_section in (framework_section or {}).values():
            filename = (role_section or {}).get("file")
            if filename:
                filenames.add(str(filename))
    return sorted(filenames)


def bundled_package_data_files(asset_dir: pathlib.Path) -> List[str]:
    """The exact, authority-based package-data file list (relative names).

    Includes the manifest itself, every manifested classifier/pipeline
    artifact, and the known auxiliary assets - and deliberately nothing else.
    A file physically present in ``asset_dir`` that is not in this list (a
    historical/experimental variant) is excluded, not swept in by extension.
    """
    asset_dir = pathlib.Path(asset_dir)
    manifest_path = asset_dir / MANIFEST_NAME
    files = {MANIFEST_NAME, *manifested_filenames(manifest_path), *AUXILIARY_ASSET_FILENAMES}
    missing = sorted(name for name in files if not (asset_dir / name).is_file())
    if missing:
        raise FileNotFoundError(
            "wake-word package-data authority references missing bundled "
            f"assets under {asset_dir}: {', '.join(missing)}"
        )
    return sorted(files)


__all__ = [
    "AUXILIARY_ASSET_FILENAMES",
    "MANIFEST_NAME",
    "bundled_package_data_files",
    "manifested_filenames",
]
