"""Reproducible generator of the bundled wake-word build assets (AP-SRV-060).

The project ships its wake-word models as build assets under
``VoiceSTT/assets/wakeword_models/`` so that neither the server nor an
installed package needs a runtime download. This tool copies exactly the
artifacts an upstream ``models.json`` declares and writes the canonical v2
manifest next to them.

It is a build/maintenance tool, not a runtime component: the server never
calls it, and it is the only place that knows about the external model source.

Usage::

    python tools/sync_wakeword_assets.py --source S:/MODELS/openwakeword/resources/models/all_models
    python tools/sync_wakeword_assets.py --source ... --check

``--check`` verifies the committed bundle against the source without writing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import sys


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGET = REPO_ROOT / "VoiceSTT" / "assets" / "wakeword_models"

#: Every backend the bundled build ships, in manifest/output order. The
#: frozen SRV-060 contract requires a matching ONNX/TFLite pair for every
#: publicly manifested wake word and pipeline artifact; a source that only
#: offers one of the two for an entry is a sync error, not a silent
#: single-backend degrade (see ``build_manifest``).
BUNDLED_FRAMEWORKS = ("onnx", "tflite")

#: The manifest revision of the current, frozen bundle contract. This is a
#: source-controlled generator constant, not a value read back from the
#: previously generated target ``models.json`` - a reproducible rebuild must
#: not depend on its own prior output. Bump this deliberately whenever the
#: generated manifest shape or content changes.
CATALOG_REVISION = 2

#: Wake assets that are not per-wake-word classifiers or per-backend pipeline
#: components, but are still sourced deterministically from the same
#: upstream ``--source`` authority (``openwakeword_models.pipeline_models``)
#: and must round-trip byte for byte. Key: internal label used in
#: diagnostics. Value: the upstream pipeline_models key. These are synced and
#: checked exactly like every other bundle artifact; they are deliberately
#: not added as a new field to the v2 manifest JSON, since no such field is
#: part of the frozen SRV-060 manifest contract and none of the currently
#: committed artifacts are consumed through the manifest either.
AUXILIARY_ASSETS = {
    "vad": "silero_vad_onnx",
}

#: Explicit, catalogued short forms. The frozen contract forbids heuristically
#: stripping "Hey", so every short form has to be listed here or it does not
#: resolve at all.
ALIASES = {
    "hey_alfred": ["alfred"],
    "hey_billy": ["billy"],
    "hey_bro": ["bro"],
    "hey_glados": ["glados"],
    "hey_hermes": ["hermes"],
    "hey_jarvis": ["jarvis"],
    "hey_lucy": ["lucy"],
    "hey_luna": ["luna"],
    "hey_max": ["max"],
    "hey_mira": ["mira"],
    "hey_mycroft": ["mycroft"],
    "hey_nabu": ["nabu"],
    "hey_nexus": ["nexus"],
    "hey_nova": ["nova"],
    "hey_oracle": ["oracle"],
    "hey_rhasspy": ["rhasspy"],
    "hey_rocky": ["rocky"],
    "hey_rona": ["rona"],
}

#: Display names that differ from the mechanical title case of the id.
DISPLAY_NAMES = {
    "hey_glados": "Hey GLaDOS",
}


def canonical_id(raw_id: str) -> str:
    """The canonical, lower-case snake id of one upstream manifest key."""
    value = re.sub(r"[\s._\-]+", "_", str(raw_id).strip())
    return re.sub(r"_+", "_", value).strip("_").lower()


def display_name(identifier: str) -> str:
    if identifier in DISPLAY_NAMES:
        return DISPLAY_NAMES[identifier]
    return " ".join(part.capitalize() for part in identifier.split("_"))


def sha256_of(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def render_manifest(value, _indent: int = 0) -> str:
    """The committed manifest's serialization authority.

    Two-space indented, like ``json.dumps(..., indent=2)``, with one
    deliberate deviation: an array of scalars (``aliases``, deliberately kept
    short and simple) renders inline on one line instead of one element per
    line, matching every ``models.json`` committed for this bundle contract.
    An array of objects (``wakeWords`` itself) still expands normally.
    """
    pad = "  " * _indent
    pad_inner = "  " * (_indent + 1)
    if isinstance(value, dict):
        if not value:
            return "{}"
        entries = [
            f"{pad_inner}{json.dumps(key)}: {render_manifest(item, _indent + 1)}"
            for key, item in value.items()
        ]
        return "{\n" + ",\n".join(entries) + "\n" + pad + "}"
    if isinstance(value, list):
        if not value:
            return "[]"
        if all(not isinstance(item, (dict, list)) for item in value):
            return "[" + ", ".join(json.dumps(item, ensure_ascii=False) for item in value) + "]"
        entries = [f"{pad_inner}{render_manifest(item, _indent + 1)}" for item in value]
        return "[\n" + ",\n".join(entries) + "\n" + pad + "]"
    return json.dumps(value, ensure_ascii=False)


def _index_by_canonical_id(mapping):
    """Upstream ``{raw_id: filename}`` reindexed by :func:`canonical_id`."""
    indexed = {}
    for raw_id, filename in mapping.items():
        identifier = canonical_id(raw_id)
        if identifier in indexed:
            raise SystemExit(f"duplicate canonical id after normalization: {identifier}")
        indexed[identifier] = filename
    return indexed


def build_manifest(source: pathlib.Path):
    """The canonical v2 manifest plus the file list it references."""
    upstream = json.loads((source / "models.json").read_text(encoding="utf-8"))
    section = upstream["openwakeword_models"]
    classifiers_by_framework = {
        framework: _index_by_canonical_id(section[f"{framework}_models"])
        for framework in BUNDLED_FRAMEWORKS
    }
    pipeline = section["pipeline_models"]

    ids_by_framework = {
        framework: set(classifiers) for framework, classifiers in classifiers_by_framework.items()
    }
    all_ids = set().union(*ids_by_framework.values())
    for identifier in sorted(all_ids):
        missing = [
            framework for framework in BUNDLED_FRAMEWORKS
            if identifier not in ids_by_framework[framework]
        ]
        if missing:
            raise SystemExit(
                f"dual-backend mismatch for '{identifier}': "
                f"missing {', '.join(missing)} classifier upstream"
            )

    files = {}
    wake_words = []
    for identifier in sorted(all_ids):
        artifacts = {}
        for framework in BUNDLED_FRAMEWORKS:
            filename = classifiers_by_framework[framework][identifier]
            artifact = source / filename
            if not artifact.is_file():
                raise SystemExit(f"missing upstream artifact: {artifact}")
            files[filename] = artifact
            artifacts[framework] = {
                "file": filename,
                "sha256": sha256_of(artifact),
                "bytes": artifact.stat().st_size,
            }
        wake_words.append({
            "id": identifier,
            "displayName": display_name(identifier),
            "aliases": list(ALIASES.get(identifier, ())),
            # Bundle artifact revision. It is an editorial version of *this*
            # project's artifact, not an upstream training version, and is
            # raised whenever the bundled bytes are replaced. The verifiable
            # byte identity is ``sha256`` below.
            "artifactVersion": "1",
            "artifacts": artifacts,
        })

    pipeline_data = {}
    for framework in BUNDLED_FRAMEWORKS:
        pipeline_files = {}
        for role, key in (("melspectrogram", f"melspectrogram_{framework}"),
                          ("embedding", f"embedding_model_{framework}")):
            filename = pipeline[key]
            artifact = source / filename
            if not artifact.is_file():
                raise SystemExit(f"missing upstream pipeline artifact: {artifact}")
            files[filename] = artifact
            pipeline_files[role] = {
                "file": filename,
                "sha256": sha256_of(artifact),
                "bytes": artifact.stat().st_size,
            }
        pipeline_data[framework] = pipeline_files

    for label, upstream_key in AUXILIARY_ASSETS.items():
        if upstream_key not in pipeline:
            raise SystemExit(
                f"missing upstream auxiliary asset key ({label}): "
                f"pipeline_models.{upstream_key}"
            )
        filename = pipeline[upstream_key]
        artifact = source / filename
        if not artifact.is_file():
            raise SystemExit(f"missing upstream auxiliary artifact ({label}): {artifact}")
        files[filename] = artifact

    manifest = {
        "manifestVersion": 2,
        "catalogRevision": CATALOG_REVISION,
        "generatedBy": "tools/sync_wakeword_assets.py",
        "description": (
            "Kanonische Wake-Word-Catalog-Authority des v2-Pfades. "
            "AP-SRV-070 hat den früheren 'openwakeword_models'-Legacyspiegel "
            "für den v1-Pfad entfernt; dies ist die einzige Manifestquelle."
        ),
        "pipeline": pipeline_data,
        "wakeWords": wake_words,
    }
    return manifest, files


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="upstream all_models directory")
    parser.add_argument("--check", action="store_true", help="verify only, write nothing")
    args = parser.parse_args(argv)

    source = pathlib.Path(args.source).expanduser()
    manifest, files = build_manifest(source)
    rendered = render_manifest(manifest) + "\n"

    if args.check:
        problems = []
        target_manifest = TARGET / "models.json"
        if not target_manifest.is_file() or target_manifest.read_text(encoding="utf-8") != rendered:
            problems.append("models.json differs")
        for filename, artifact in sorted(files.items()):
            bundled = TARGET / filename
            if not bundled.is_file():
                problems.append(f"missing {filename}")
            elif sha256_of(bundled) != sha256_of(artifact):
                problems.append(f"changed {filename}")
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1 if problems else 0

    TARGET.mkdir(parents=True, exist_ok=True)
    for filename, artifact in sorted(files.items()):
        shutil.copyfile(artifact, TARGET / filename)
    (TARGET / "models.json").write_text(rendered, encoding="utf-8", newline="\n")
    total = sum(path.stat().st_size for path in files.values())
    print(f"{len(files)} artifacts, {total} bytes -> {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
