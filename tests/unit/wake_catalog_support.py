"""Shared helpers for AP-SRV-060 wake-word catalog tests.

The helpers build a *real* bundle on disk - manifest plus artifact files - so
the tests exercise the production loader, the production resolver and the
production availability rules instead of a hand-written stand-in.

Since AP-SRV-060 C3 a bundle may declare more than one inference backend. The
``backends`` argument writes the artifacts and the pipeline models of every
named backend, so a test can build an ONNX-only bundle (the historical case),
a TFLite-only bundle or a dual-format bundle without hand-writing a manifest.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from VoiceSTT.core.wakeword_catalog import WakeWordCatalogAuthority


#: File suffix of one inference backend's artifacts.
BACKEND_SUFFIX = {"onnx": ".onnx", "tflite": ".tflite"}

PIPELINE_STEMS = ("melspectrogram", "embedding_model")

PIPELINE_FILES = tuple(f"{stem}.onnx" for stem in PIPELINE_STEMS)


def backend_file_name(file_name: str, backend: str) -> str:
    """The artifact file name of ``file_name``'s wake word in ``backend``."""
    return Path(file_name).stem + BACKEND_SUFFIX[backend]


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


def build_bundle(
    root,
    entries,
    *,
    catalog_revision=1,
    with_pipeline=True,
    backends=("onnx",),
):
    """Writes a manifest bundle and returns the asset root.

    ``entries`` is a sequence of ``(id, displayName, aliases, file_name)``.
    ``backends`` names the inference backends the bundle declares; the file
    name of a non-ONNX artifact is derived from the ONNX file stem.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    backends = tuple(backends)

    pipeline = {}
    for backend in backends:
        names = {
            stem: stem + BACKEND_SUFFIX[backend] for stem in PIPELINE_STEMS
        }
        if with_pipeline:
            for name in names.values():
                write_artifact(root, name)
            pipeline[backend] = {
                "melspectrogram": artifact_spec(root, names["melspectrogram"]),
                "embedding": artifact_spec(root, names["embedding_model"]),
            }
        else:
            pipeline[backend] = {
                "melspectrogram": {"file": names["melspectrogram"]},
                "embedding": {"file": names["embedding_model"]},
            }

    wake_words = []
    for identifier, display_name, aliases, file_name in entries:
        artifacts = {}
        for backend in backends:
            name = backend_file_name(file_name, backend)
            if not (root / name).is_file():
                write_artifact(root, name)
            artifacts[backend] = artifact_spec(root, name)
        wake_words.append({
            "id": identifier,
            "displayName": display_name,
            "aliases": list(aliases),
            "artifactVersion": "1",
            "artifacts": artifacts,
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
    """A real catalog authority over a freshly written test bundle.

    The bundle contains placeholder bytes rather than real ONNX models, so the
    default loadability probe is replaced with a permissive one. Tests that
    care about the probe itself (Root F3/F12) pass their own ``artifact_prober``
    or ``artifact_probers``.
    """
    backends = kwargs.pop("backends", ("onnx",))
    asset_root = build_bundle(root, entries, backends=backends)
    if "artifact_probers" not in kwargs:
        kwargs.setdefault("artifact_prober", lambda path: None)
    return WakeWordCatalogAuthority(asset_root=asset_root, **kwargs)


class FakeCatalogService:
    """The minimal service surface the v2 ports read."""

    def __init__(self, catalog):
        self.wakeword_catalog = catalog
