"""Real Python packaging/installations, not native Kroko qualification.

Run explicitly with pytest on a host with build/setuptools/wheel installed.
Fresh consumer venvs install only packaging plus the real product wheel with
--no-deps. Native fixtures test provenance plumbing, never native correctness.
The RC gate separately installs the full dependency/native product on each OS.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import venv
import zipfile

import pytest

from VoiceSTT._build_identity import RESOURCE_NAME
from build_identity_support import wheel_identity
from tools.build_distribution import merge_kroko_runtime
from tests.unit.test_build_distribution import make_kroko_wheel

ROOT = Path(__file__).resolve().parents[2]
PRODUCTS = [("voicestt", None), ("voice-stt-server", "free"), ("voice-stt-server-pro", "pro")]
VERSIONS = ["2.0.0", "2.0.0-alpha.2", "2.0.0-beta.3", "2.0.0-rc.1", "2.0.0-rc.1+Build.5"]


def record_evidence(record):
    location = os.environ.get("VOICESTT_IDENTITY_EVIDENCE_DIR")
    if location:
        directory = Path(location)
        directory.mkdir(parents=True, exist_ok=True)
        content = json.dumps(record, sort_keys=True, indent=2) + "\n"
        (directory / f"{hashlib.sha256(content.encode()).hexdigest()}.json").write_text(
            content, encoding="utf-8"
        )


def run(args, cwd, *, env=None, success=True):
    result = subprocess.run(
        [str(arg) for arg in args], cwd=cwd, env=env, text=True,
        encoding="utf-8", errors="replace", capture_output=True,
    )
    if success:
        assert result.returncode == 0, result.stdout + result.stderr
    return result


def build_env(version=None, variant=None):
    env = dict(os.environ)
    for key in ("PYTHONPATH", "VOICESTT_BUILD_VERSION", "VOICESTT_SERVER_COMMIT",
                "VOICESTT_DISTRIBUTION_VARIANT", "SOURCE_DATE_EPOCH"):
        env.pop(key, None)
    if version:
        env["VOICESTT_BUILD_VERSION"] = version
    if variant:
        env["VOICESTT_DISTRIBUTION_VARIANT"] = variant
    env["SOURCE_DATE_EPOCH"] = "1792445641"
    return env


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    root = tmp_path_factory.mktemp("identity-source")
    for name in ("VoiceSTT", "VoiceSTT_server", "api_fastapi_server", "voice_stt_server"):
        shutil.copytree(
            ROOT / name, root / name,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", RESOURCE_NAME),
        )
    for name in ("setup.py", "build_identity_support.py", "wakeword_package_resources.py",
                 "VERSION", "requirements.txt", "README.md", "RELEASE_NOTES.md", "LICENSE",
                 "MANIFEST.in"):
        shutil.copy2(ROOT / name, root / name)
    (root / ".gitignore").write_text(
        "build/\n*.egg-info/\n__pycache__/\n*.pyc\nVoiceSTT/_build_identity.json\n"
    )
    run(["git", "init", "-q"], root)
    run(["git", "add", "."], root)
    run(["git", "-c", "user.name=Identity test", "-c", "user.email=identity@example.invalid",
         "-c", "commit.gpgsign=false", "commit", "-qm", "isolated identity source"], root)
    return root


def build(source, destination, *, version=None, variant=None, sdist=False, isolated=False):
    run([sys.executable, "-m", "build", *([] if isolated else ["--no-isolation"]),
         "--sdist" if sdist else "--wheel", "--outdir", destination],
        source, env=build_env(version, variant))
    artifact = next(destination.glob("*.tar.gz" if sdist else "*.whl"))
    if sdist:
        with tarfile.open(artifact) as archive:
            resource = next(item for item in archive.getmembers()
                            if item.name.endswith("/VoiceSTT/" + RESOURCE_NAME))
            identity = json.loads(archive.extractfile(resource).read())
    else:
        identity = json.loads(wheel_identity(artifact).to_json())
    record_evidence({
        "kind": "sdist" if sdist else "wheel", "filename": artifact.name,
        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "bytes": artifact.stat().st_size, "identity": identity,
    })
    return artifact


@pytest.fixture
def consumer(tmp_path):
    root = tmp_path / "consumer"
    venv.EnvBuilder(with_pip=True).create(root)
    python = root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    run([python, "-m", "pip", "install", "--quiet", "packaging>=24.0"], tmp_path)
    return python


def test_real_editable_install_accepts_its_own_source_egg_info(source, consumer, tmp_path):
    run([consumer, "-m", "pip", "install", "--quiet", "--no-deps", "-e", source],
        tmp_path, env=build_env())
    result = run([consumer, "-c",
                  "import json; from VoiceSTT._build_identity import installed_distribution; "
                  "print(json.dumps(installed_distribution()))"], source, env=build_env())
    assert json.loads(result.stdout) == ["voicestt", "2.0.0"]
    assert not (source / "VoiceSTT" / RESOURCE_NAME).exists()


def install(python, wheel, cwd):
    run([python, "-m", "pip", "install", "--quiet", "--no-deps", wheel], cwd)


def inspect_installed(python, cwd, *, env=None, success=True):
    result = run([python, "-I", "-c", """
import json, pathlib, sys
from importlib import metadata
import VoiceSTT
from VoiceSTT._build_identity import validated_build_identity, installed_distribution
assert pathlib.Path(VoiceSTT.__file__).is_relative_to(pathlib.Path(sys.prefix))
identity = validated_build_identity()
distribution = installed_distribution()
url = json.loads(metadata.distribution(distribution[0]).read_text("direct_url.json"))
print(json.dumps({"version": VoiceSTT.get_version(), "distribution": installed_distribution(),
                  "installedWheelSha256": url["archive_info"]["hashes"]["sha256"],
                  "identity": json.loads(identity.to_json()) if identity else None}))
"""], cwd, env=env or build_env(), success=success)
    if result.returncode == 0:
        record_evidence({"kind": "installed", **json.loads(result.stdout)})
    return result


@pytest.mark.parametrize("name,variant", PRODUCTS)
@pytest.mark.parametrize("version", VERSIONS)
def test_real_installed_metadata_preserves_original_semver(
    source, tmp_path, consumer, name, variant, version
):
    wheel = build(source, tmp_path / "dist", version=version, variant=variant)
    original = wheel_identity(wheel)
    assert original.complete
    assert original.productVersion == version and original.distributionName == name
    assert not (source / "VoiceSTT" / RESOURCE_NAME).exists()
    assert run(["git", "status", "--porcelain"], source).stdout == ""
    install(consumer, wheel, tmp_path)
    observed = json.loads(inspect_installed(consumer, tmp_path).stdout)
    assert observed["version"] == version
    assert observed["distribution"] == [name, original.packageVersion]
    assert observed["identity"] == json.loads(original.to_json())


@pytest.mark.parametrize("variant", [None, "free", "pro"])
@pytest.mark.parametrize("foreign_git", [False, True])
def test_sdist_to_wheel_preserves_identity_without_git_and_under_foreign_git(
    source, tmp_path, consumer, variant, foreign_git
):
    sdist = build(source, tmp_path / "sdist", version="2.0.0-rc.1", variant=variant, sdist=True)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    if foreign_git:
        run(["git", "init", "-q"], foreign)
    (foreign / "VERSION").write_text("99.0.0\n")
    with tarfile.open(sdist) as archive:
        archive.extractall(foreign, filter="data")
    unpacked = next(path for path in foreign.iterdir() if path.is_dir() and path.name != ".git")
    assert not (unpacked / ".git").exists()
    expected = (unpacked / "VoiceSTT" / RESOURCE_NAME).read_bytes()
    wheel = build(unpacked, tmp_path / "wheel")
    with zipfile.ZipFile(wheel) as archive:
        assert archive.read("VoiceSTT/" + RESOURCE_NAME) == expected
    install(consumer, wheel, foreign)
    observed = json.loads(inspect_installed(consumer, foreign).stdout)
    assert observed["version"] == "2.0.0-rc.1"
    assert observed["identity"] == json.loads(expected)


def test_isolated_pep517_backend_builds_source_and_extracted_sdist(source, tmp_path, consumer):
    original = build(source, tmp_path / "direct", version="2.0.0-rc.1", isolated=True)
    sdist = build(source, tmp_path / "sdist", version="2.0.0-rc.1", sdist=True, isolated=True)
    unpacked = tmp_path / "unpacked"
    with tarfile.open(sdist) as archive:
        archive.extractall(unpacked, filter="data")
    rebuilt = build(next(unpacked.iterdir()), tmp_path / "rebuilt", isolated=True)
    assert wheel_identity(rebuilt) == wheel_identity(original)
    install(consumer, rebuilt, tmp_path)
    assert json.loads(inspect_installed(consumer, tmp_path).stdout)["version"] == "2.0.0-rc.1"


def test_repeat_wheels_have_identical_bytes_and_ignore_stale_source_resource(source, tmp_path):
    first = build(source, tmp_path / "one", version="2.0.0-rc.1")
    stale = source / "VoiceSTT" / RESOURCE_NAME
    stale.write_text('{"productVersion":"99.0.0"}')
    try:
        second = build(source, tmp_path / "two", version="2.0.0-rc.1")
        assert first.read_bytes() == second.read_bytes()
        assert stale.read_text() == '{"productVersion":"99.0.0"}'
    finally:
        stale.unlink()
    assert run(["git", "status", "--porcelain"], source).stdout == ""


@pytest.mark.parametrize("variant", ["free", "pro"])
def test_installed_public_native_provenance_with_explicit_synthetic_runtime_fixture(
    source, tmp_path, consumer, variant
):
    base = build(source, tmp_path / "base", version="2.0.0-rc.1", variant=variant)
    kroko = make_kroko_wheel(tmp_path, variant, platform="win_amd64" if os.name == "nt" else "linux_x86_64")
    result = merge_kroko_runtime(
        base_wheel=base, kroko_wheel=kroko, variant=variant,
        out_dir=tmp_path / "merged", fingerprint="synthetic-fixture-not-native-qualification",
    )
    install(consumer, result["path"], tmp_path)
    observed = json.loads(inspect_installed(consumer, tmp_path).stdout)
    assert observed["version"] == "2.0.0-rc.1"
    assert observed["identity"]["krokoVariant"] == variant
    assert result["embedded"]["productVersion"] == "2.0.0-rc.1"
    script = """
import json
from api_fastapi_server.protocol_v2.identity import resolve_runtime_identity
print(json.dumps(resolve_runtime_identity().public_info("synthetic-native-fixture")))
"""
    runtime = json.loads(run([consumer, "-I", "-c", script], tmp_path, env=build_env()).stdout)
    assert runtime["distribution"]["name"] == observed["distribution"][0]
    assert runtime["runtime"]["krokoVariant"] == variant
    assert runtime["serverVersion"] == "2.0.0-rc.1"
    corrupt = """
import json
from pathlib import Path
import voice_stt_server
path = Path(voice_stt_server.__file__).with_name("_embedded_kroko.json")
data = json.loads(path.read_text())
data["variant"] = "pro" if data["variant"] == "free" else "free"
path.write_text(json.dumps(data))
"""
    run([consumer, "-I", "-c", corrupt], tmp_path, env=build_env())
    failed = run([consumer, "-I", "-c", script], tmp_path, env=build_env(), success=False)
    assert failed.returncode != 0 and "IdentityError" in failed.stderr


def test_manual_build_without_git_remains_incomplete_and_installable(source, tmp_path, consumer):
    manual = tmp_path / "manual"
    shutil.copytree(source, manual, ignore=shutil.ignore_patterns(".git", "build", "*.egg-info"))
    wheel = build(manual, tmp_path / "dist")
    resource = wheel_identity(wheel)
    assert not resource.complete and resource.sourceDirty is None
    assert resource.sourceCommit is None and resource.sourceTree is None
    install(consumer, wheel, tmp_path)
    assert json.loads(inspect_installed(consumer, tmp_path).stdout)["version"] == "2.0.0"


def test_installed_identical_and_blank_overrides_preserve_resource(source, tmp_path, consumer):
    wheel = build(source, tmp_path / "dist", version="2.0.0-rc.1")
    identity = wheel_identity(wheel)
    install(consumer, wheel, tmp_path)
    for value in (
        {}, {"VOICESTT_BUILD_VERSION": ""}, {"VOICESTT_SERVER_COMMIT": " "},
        {"VOICESTT_BUILD_VERSION": identity.productVersion},
        {"VOICESTT_SERVER_COMMIT": identity.sourceCommit},
    ):
        env = build_env()
        env.update(value)
        result = json.loads(inspect_installed(consumer, tmp_path, env=env).stdout)
        assert result["identity"] == json.loads(identity.to_json())


@pytest.mark.parametrize("variable,value", [
    ("VOICESTT_BUILD_VERSION", "9.9.9"), ("VOICESTT_SERVER_COMMIT", "c" * 40),
    ("VOICESTT_SERVER_COMMIT", "unknown"), ("VOICESTT_SERVER_COMMIT", "short"),
])
def test_installed_overrides_fail_before_runtime_success(source, tmp_path, consumer, variable, value):
    wheel = build(source, tmp_path / "dist")
    install(consumer, wheel, tmp_path)
    env = build_env()
    env[variable] = value
    result = inspect_installed(consumer, tmp_path, env=env, success=False)
    assert result.returncode != 0 and "IdentityError" in result.stderr


def test_installed_resource_corruption_is_not_unknown(source, tmp_path, consumer):
    wheel = build(source, tmp_path / "dist")
    install(consumer, wheel, tmp_path)
    script = """
from pathlib import Path
import VoiceSTT
path = Path(VoiceSTT.__file__).with_name("_build_identity.json")
path.write_text('{"productVersion":"SECRET_SENTINEL"}')
"""
    run([consumer, "-I", "-c", script], tmp_path)
    result = inspect_installed(consumer, tmp_path, success=False)
    assert result.returncode != 0 and "IdentityError" in result.stderr
    assert "SECRET_SENTINEL" not in result.stderr


@pytest.mark.parametrize("name,variant", PRODUCTS)
def test_old_resource_free_stable_install_remains_usable(source, tmp_path, consumer, name, variant):
    wheel = build(source, tmp_path / "original", variant=variant)
    rewritten = tmp_path / wheel.name
    with zipfile.ZipFile(wheel) as original, zipfile.ZipFile(rewritten, "w") as target:
        for entry in original.infolist():
            if entry.filename == "VoiceSTT/" + RESOURCE_NAME:
                continue
            data = original.read(entry)
            if entry.filename.endswith(".dist-info/RECORD"):
                rows = csv.reader(io.StringIO(data.decode()))
                output = io.StringIO()
                writer = csv.writer(output, lineterminator="\n")
                writer.writerows(row for row in rows if row[0] != "VoiceSTT/" + RESOURCE_NAME)
                data = output.getvalue().encode()
            target.writestr(entry, data)
    install(consumer, rewritten, tmp_path)
    (tmp_path / "VERSION").write_text("99.0.0\n")
    observed = json.loads(inspect_installed(consumer, tmp_path).stdout)
    assert observed["version"] == "2.0.0"
    assert observed["distribution"] == [name, "2.0.0"]
    assert observed["identity"] is None


def test_actual_multiple_installed_products_are_rejected(source, tmp_path, consumer):
    legacy = build(source, tmp_path / "legacy")
    free = build(source, tmp_path / "free", variant="free")
    install(consumer, legacy, tmp_path)
    install(consumer, free, tmp_path)
    result = inspect_installed(consumer, tmp_path, success=False)
    assert result.returncode != 0 and "multiple product distributions" in result.stderr


@pytest.mark.parametrize("field,value", [("Version", "9.9.9"), ("Name", "voice-stt-server-pro")])
def test_actual_installed_metadata_mismatch_is_rejected(source, tmp_path, consumer, field, value):
    wheel = build(source, tmp_path / "dist")
    install(consumer, wheel, tmp_path)
    run([consumer, "-I", "-c", """
from importlib import metadata
import sys
dist = metadata.distribution("voicestt")
path = next(dist.locate_file(p) for p in dist.files if str(p).endswith(".dist-info/METADATA"))
field, value = sys.argv[1:]
old = "Version: 2.0.0" if field == "Version" else "Name: voicestt"
path.write_text(path.read_text().replace(old, field + ": " + value))
""", field, value], tmp_path)
    result = inspect_installed(consumer, tmp_path, success=False)
    assert result.returncode != 0 and "metadata" in result.stderr


def test_actual_duplicate_same_named_distributions_are_rejected(source, tmp_path, consumer):
    wheel = build(source, tmp_path / "dist")
    install(consumer, wheel, tmp_path)
    run([consumer, "-I", "-c", """
from importlib import metadata
from pathlib import Path
import shutil
dist = metadata.distribution("voicestt")
path = next(dist.locate_file(p) for p in dist.files if str(p).endswith(".dist-info/METADATA")).parent
duplicate = path.with_name("voicestt-9.9.9.dist-info")
shutil.copytree(path, duplicate)
meta = duplicate / "METADATA"
meta.write_text(meta.read_text().replace("Version: 2.0.0", "Version: 9.9.9"))
"""], tmp_path)
    result = inspect_installed(consumer, tmp_path, success=False)
    assert result.returncode != 0 and "multiple product distributions" in result.stderr


@pytest.mark.parametrize("variant,version,error", [
    ("free", "2.0.0", "PackageNotFoundError"),
    ("pro", "2.0.0", "PackageNotFoundError"),
    (None, "2.0.0-rc.1", "SemVerError"),
])
def test_real_installed_baseline_reproduces_f02_f03(
    source, tmp_path, consumer, variant, version, error
):
    baseline = run(
        ["git", "show", "e761b97334f263a6c51e84314bf3688599b84169:VoiceSTT/_version.py"],
        ROOT,
    ).stdout
    version_file = source / "VoiceSTT" / "_version.py"
    original = version_file.read_bytes()
    version_file.write_text(baseline, encoding="utf-8")
    try:
        wheel = build(source, tmp_path / "dist", variant=variant, version=version)
    finally:
        version_file.write_bytes(original)
    install(consumer, wheel, tmp_path)
    result = inspect_installed(consumer, tmp_path, success=False)
    assert result.returncode != 0 and error in result.stderr
