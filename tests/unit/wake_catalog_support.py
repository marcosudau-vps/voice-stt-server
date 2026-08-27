"""Shared helpers for AP-SRV-060 wake-word catalog tests.

The helpers build a *real* bundle on disk - manifest plus artifact files - so
the tests exercise the production loader, the production resolver and the
production availability rules instead of a hand-written stand-in.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from VoiceSTT.core.wakeword_catalog import WakeWordCatalogAuthority


PIPELINE_FILES = ("melspectrogram.onnx", "embedding_model.onnx")


def write_artifact(root: Path, name: str, payload: bytes = b"onnx-test-artifact") -> Path:
    path = root / name
    path.write_bytes(payload)
    return path


def artifact_spec(root: Path, name: str) -> dict:
    path = root / name
    data = path.read_bytes()
    return {
        "file": name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
    }


def build_bundle(root, entries, *, catalog_revision=1, with_pipeline=True):
    """Writes a manifest bundle and returns the asset root.

    ``entries`` is a sequence of ``(id, displayName, aliases, file_name)``.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    if with_pipeline:
        for name in PIPELINE_FILES:
            write_artifact(root, name)
        pipeline = {
            "onnx": {
                "melspectrogram": artifact_spec(root, "melspectrogram.onnx"),
                "embedding": artifact_spec(root, "embedding_model.onnx"),
            }
        }
    else:
        pipeline = {"onnx": {
            "melspectrogram": {"file": "melspectrogram.onnx"},
            "embedding": {"file": "embedding_model.onnx"},
        }}

    wake_words = []
    for identifier, display_name, aliases, file_name in entries:
        if not (root / file_name).is_file():
            write_artifact(root, file_name)
        wake_words.append({
            "id": identifier,
            "displayName": display_name,
            "aliases": list(aliases),
            "artifactVersion": "1",
            "artifacts": {"onnx": artifact_spec(root, file_name)},
        })

    manifest = {
        "manifestVersion": 2,
        "catalogRevision": catalog_revision,
        "pipeline": pipeline,
        "wakeWords": wake_words,
    }
    (root / "models.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return root


DEFAULT_ENTRIES = (
    ("hey_jarvis", "Hey Jarvis", ("jarvis",), "jarvis_v2.onnx"),
    ("alexa", "Alexa", (), "alexa.onnx"),
)


def build_authority(root, entries=DEFAULT_ENTRIES, **kwargs):
    """A real catalog authority over a freshly written test bundle."""
    asset_root = build_bundle(root, entries)
    return WakeWordCatalogAuthority(asset_root=asset_root, **kwargs)


class FakeCatalogService:
    """The minimal service surface the v2 ports read."""

    def __init__(self, catalog):
        self.wakeword_catalog = catalog
