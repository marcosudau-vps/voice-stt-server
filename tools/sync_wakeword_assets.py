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

#: The framework the bundled build ships. tflite artifacts are deliberately not
#: bundled: the server default is ONNX and doubling the bundle would add no
#: capability the v2 catalog exposes.
BUNDLED_FRAMEWORK = "onnx"

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


def build_manifest(source: pathlib.Path):
    """The canonical v2 manifest plus the file list it references."""
    upstream = json.loads((source / "models.json").read_text(encoding="utf-8"))
    section = upstream["openwakeword_models"]
    classifiers = section["onnx_models"]
    pipeline = section["pipeline_models"]

    files = {}
    wake_words = []
    for raw_id, filename in sorted(classifiers.items(), key=lambda item: canonical_id(item[0])):
        artifact = source / filename
        if not artifact.is_file():
            raise SystemExit(f"missing upstream artifact: {artifact}")
        identifier = canonical_id(raw_id)
        files[filename] = artifact
        wake_words.append({
            "id": identifier,
            "displayName": display_name(identifier),
            "aliases": list(ALIASES.get(identifier, ())),
            # Bundle artifact revision. It is an editorial version of *this*
            # project's artifact, not an upstream training version, and is
            # raised whenever the bundled bytes are replaced. The verifiable
            # byte identity is ``sha256`` below.
            "artifactVersion": "1",
            "artifacts": {
                BUNDLED_FRAMEWORK: {
                    "file": filename,
                    "sha256": sha256_of(artifact),
                    "bytes": artifact.stat().st_size,
                },
            },
        })

    pipeline_files = {}
    for role, key in (("melspectrogram", "melspectrogram_onnx"),
                      ("embedding", "embedding_model_onnx")):
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

    manifest = {
        "manifestVersion": 2,
        "catalogRevision": 1,
        "generatedBy": "tools/sync_wakeword_assets.py",
        "description": (
            "Kanonische Wake-Word-Catalog-Authority des v2-Pfades. Der "
            "Abschnitt 'openwakeword_models' ist nur ein Legacyspiegel fuer "
            "den v1-Pfad bis AP-SRV-070."
        ),
        "pipeline": {BUNDLED_FRAMEWORK: pipeline_files},
        "wakeWords": wake_words,
        # Legacy mirror: the AP-SRV-050 era OpenWakeWordCatalog still reads
        # this shape. It is explicitly NOT the v2 authority.
        "openwakeword_models": {
            "path": ".",
            "default_model": canonical_id(section.get("default_model") or ""),
            "pipeline_models": {
                "melspectrogram_onnx": pipeline["melspectrogram_onnx"],
                "embedding_model_onnx": pipeline["embedding_model_onnx"],
            },
            "onnx_models": {
                entry["id"]: entry["artifacts"][BUNDLED_FRAMEWORK]["file"]
                for entry in wake_words
            },
        },
    }
    return manifest, files


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="upstream all_models directory")
    parser.add_argument("--check", action="store_true", help="verify only, write nothing")
    args = parser.parse_args(argv)

    source = pathlib.Path(args.source).expanduser()
    manifest, files = build_manifest(source)
    rendered = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=False) + "\n"

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
