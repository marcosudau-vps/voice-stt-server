"""Verify the complete non-commercial V1 wake-word payload in a product wheel."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


PREFIX = "VoiceSTT/assets/wakeword_models/"


def verify_wakeword_bundle(wheel: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        manifest = json.loads(archive.read(PREFIX + "models.json"))[
            "openwakeword_models"
        ]
        classifiers = manifest["onnx_models"]
        pipeline = manifest["pipeline_models"]
        expected = set(classifiers.values()) | set(pipeline.values())
        present = {
            name.removeprefix(PREFIX)
            for name in names
            if name.startswith(PREFIX) and name.endswith(".onnx")
        }
        if len(classifiers) != 14 or len(pipeline) != 2:
            raise ValueError("V1 requires 14 classifiers and two pipeline models")
        if manifest.get("default_model") not in classifiers:
            raise ValueError("V1 default wake word is absent")
        if len(expected) != 16 or present != expected:
            raise ValueError("bundled ONNX files differ from the V1 manifest")
        if set(manifest["sha256"]) != expected:
            raise ValueError("V1 wake-word hash list differs from the manifest")
        if len(names) != len(set(names)) or PREFIX + "wakeword_models.zip" in names:
            raise ValueError("duplicate entries or source archive in product wheel")
        for filename in expected:
            data = archive.read(PREFIX + filename)
            if hashlib.sha256(data).hexdigest() != manifest["sha256"][filename]:
                raise ValueError(f"wake-word checksum mismatch: {filename}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheels", nargs="+", type=Path)
    args = parser.parse_args()
    for wheel in args.wheels:
        verify_wakeword_bundle(wheel)
        print(f"{wheel.name}: 14 classifiers, 2 pipeline models, hashes OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
