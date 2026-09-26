"""Build and inspect the V1 preservation Python artifacts without installing deps."""
from __future__ import annotations

import email
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.0.0"
DISTRIBUTION = "voice-stt-server"


def _run(*args: str, cwd: Path = ROOT) -> None:
    subprocess.run([sys.executable, *args], cwd=cwd, check=True)


def main() -> int:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if version != VERSION:
        raise SystemExit(f"VERSION must be {VERSION}, got {version!r}")

    work = Path(tempfile.mkdtemp(prefix="voicestt-v1-package-"))
    dist = work / "dist"
    try:
        _run("-m", "build", "--wheel", "--sdist", "--outdir", str(dist))
        _run("-m", "twine", "check", *[str(path) for path in sorted(dist.iterdir())])

        wheels = list(dist.glob("*.whl"))
        sdists = list(dist.glob("*.tar.gz"))
        if len(wheels) != 1 or len(sdists) != 1:
            raise SystemExit(f"expected one wheel and one sdist, got {wheels=} {sdists=}")

        wheel = wheels[0]
        expected_wheel = f"voice_stt_server-{VERSION}-py3-none-any.whl"
        if wheel.name != expected_wheel:
            raise SystemExit(f"unexpected wheel filename: {wheel.name!r}")

        with zipfile.ZipFile(wheel) as archive:
            names = set(archive.namelist())
            metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
            metadata = email.message_from_bytes(archive.read(metadata_name))
            entry_points_name = next(name for name in names if name.endswith(".dist-info/entry_points.txt"))
            entry_points = archive.read(entry_points_name).decode("utf-8")

        if metadata.get("Name") != DISTRIBUTION:
            raise SystemExit(f"wheel Name is {metadata.get('Name')!r}")
        if metadata.get("Version") != VERSION:
            raise SystemExit(f"wheel Version is {metadata.get('Version')!r}")
        if metadata.get("Requires-Python") != ">=3.11":
            raise SystemExit(f"wheel Requires-Python is {metadata.get('Requires-Python')!r}")
        if "VoiceSTT/__init__.py" not in names or "VoiceSTT_server/server.py" not in names:
            raise SystemExit("wheel is missing the historical V1 import/server packages")
        if any(name.startswith("kroko_onnx/") for name in names):
            raise SystemExit("V1 Python wheel must not embed the Kroko native runtime")
        if "stt-install-kroko = VoiceSTT.install_kroko:main" not in entry_points:
            raise SystemExit("historical stt-install-kroko entry point is missing")
        if "stt-server = VoiceSTT_server.server:main" not in entry_points:
            raise SystemExit("historical stt-server entry point is missing")

        expected_sdist = f"voice_stt_server-{VERSION}.tar.gz"
        if sdists[0].name != expected_sdist:
            raise SystemExit(f"unexpected sdist filename: {sdists[0].name!r}")
        with tarfile.open(sdists[0], "r:gz") as archive:
            sdist_names = set(archive.getnames())
        prefix = f"voice_stt_server-{VERSION}/"
        for required in ("VERSION", "setup.py", "requirements.txt", "VoiceSTT/install_kroko.py"):
            if prefix + required not in sdist_names:
                raise SystemExit(f"sdist is missing {required}")

        print(f"PASS wheel: {wheel.name}")
        print(f"PASS sdist: {sdists[0].name}")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
