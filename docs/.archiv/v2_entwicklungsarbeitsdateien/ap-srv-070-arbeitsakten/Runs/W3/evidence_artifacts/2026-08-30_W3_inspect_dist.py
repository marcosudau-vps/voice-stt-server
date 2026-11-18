"""Host-side inspection of the built wheel/sdist (no install needed).

Run with the *worktree's* python so wakeword_package_resources.py is
importable, from the worktree root, e.g.:

    python /path/to/inspect_dist.py /path/to/dist_out
"""

import hashlib
import json
import sys
import tarfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve()
sys.path.insert(0, str(Path.cwd()))

from wakeword_package_resources import bundled_package_data_files  # noqa: E402


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_wheel(path: Path):
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
    asset_names = sorted(
        n.split("VoiceSTT/assets/wakeword_models/", 1)[1]
        for n in names
        if "VoiceSTT/assets/wakeword_models/" in n
    )
    dist_info = sorted(n for n in names if ".dist-info/" in n)
    metadata_name = next(n for n in dist_info if n.endswith("METADATA"))
    with zipfile.ZipFile(path) as zf:
        metadata = zf.read(metadata_name).decode("utf-8")
    entry_points_name = next((n for n in dist_info if n.endswith("entry_points.txt")), None)
    entry_points = None
    if entry_points_name:
        with zipfile.ZipFile(path) as zf:
            entry_points = zf.read(entry_points_name).decode("utf-8")
    version_line = next(l for l in metadata.splitlines() if l.startswith("Version:"))
    name_line = next(l for l in metadata.splitlines() if l.startswith("Name:"))
    return {
        "file": path.name,
        "sha256": sha256_of(path),
        "bytes": path.stat().st_size,
        "metadataVersion": version_line,
        "metadataName": name_line,
        "wakeAssetFiles": asset_names,
        "wakeAssetFileCount": len(asset_names),
        "entryPoints": entry_points,
        "totalFileCount": len(names),
    }


def inspect_sdist(path: Path):
    with tarfile.open(path, "r:gz") as tf:
        names = tf.getnames()
    # sdist entries are prefixed with "<name>-<version>/"
    prefix = names[0].split("/", 1)[0] + "/"
    asset_names = sorted(
        n.split(prefix + "VoiceSTT/assets/wakeword_models/", 1)[1]
        for n in names
        if (prefix + "VoiceSTT/assets/wakeword_models/") in n
        and not n.endswith("/VoiceSTT/assets/wakeword_models")
    )
    has_version_file = (prefix + "VERSION") in names
    has_resource_helper = (prefix + "wakeword_package_resources.py") in names
    pkg_info = None
    with tarfile.open(path, "r:gz") as tf:
        for member in tf.getmembers():
            if member.name == prefix + "PKG-INFO":
                pkg_info = tf.extractfile(member).read().decode("utf-8")
    version_line = next(l for l in pkg_info.splitlines() if l.startswith("Version:")) if pkg_info else None
    return {
        "file": path.name,
        "sha256": sha256_of(path),
        "bytes": path.stat().st_size,
        "pkgInfoVersion": version_line,
        "wakeAssetFiles": asset_names,
        "wakeAssetFileCount": len(asset_names),
        "hasVersionFile": has_version_file,
        "hasWakewordPackageResourcesHelper": has_resource_helper,
        "totalFileCount": len(names),
    }


def main():
    dist_dir = Path(sys.argv[1])
    expected_assets = set(bundled_package_data_files("VoiceSTT/assets/wakeword_models"))
    result = {"expectedWakeAssetFiles": sorted(expected_assets), "builds": {}}

    for subdir in ("baseline", "candidate", "baseline-repeat"):
        folder = dist_dir / subdir
        if not folder.is_dir():
            continue
        entry = {}
        for whl in sorted(folder.glob("*.whl")):
            info = inspect_wheel(whl)
            info["wakeAssetsMatchAuthority"] = set(info["wakeAssetFiles"]) == expected_assets
            entry["wheel"] = info
        for sdist in sorted(folder.glob("*.tar.gz")):
            info = inspect_sdist(sdist)
            info["wakeAssetsMatchAuthority"] = set(info["wakeAssetFiles"]) == expected_assets
            entry["sdist"] = info
        result["builds"][subdir] = entry

    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
