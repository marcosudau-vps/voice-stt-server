"""Identity schema, ownership, failures and deterministic build inputs."""

from dataclasses import asdict, replace
from importlib import metadata
import json
from pathlib import Path
from unittest import mock

import pytest

from VoiceSTT import _build_identity as bi, _version
from api_fastapi_server.protocol_v2 import identity as runtime
from build_identity_support import capture_identity, match_identity, wheel_identity


@pytest.fixture
def complete_identity():
    return bi.BuildIdentity.from_dict({
        "schemaVersion": 1, "productVersion": "2.0.0-rc.1+build.5",
        "packageVersion": "2.0.0rc1+build.5", "sourceCommit": "a" * 40,
        "sourceTree": "b" * 40, "sourceDirty": False,
        "sourceDate": "2026-10-19T21:34:01Z",
        "distributionName": "voicestt", "krokoVariant": None, "provenance": "git",
    })


@pytest.mark.parametrize("product,expected", [
    ("2.0.0", "2.0.0"), ("2.0.0-rc.1", "2.0.0rc1"),
    ("2.0.0-alpha.2", "2.0.0a2"), ("2.0.0-beta.3", "2.0.0b3"),
    ("2.0.0+Build.5", "2.0.0+build.5"),
    ("2.0.0-rc.1+Build-ABC", "2.0.0rc1+build.abc"),
])
def test_explicit_semver_to_pep440_rule(product, expected):
    assert bi.package_version_for(product) == expected


@pytest.mark.parametrize("product", ["2.0.0-preview.1", "2.0.0-rc1", "2.0.0rc1", "secret"])
def test_no_free_reconstruction_or_unsupported_packaging(product):
    with pytest.raises(bi.IdentityError) as error:
        bi.package_version_for(product)
    assert product not in str(error.value)


def test_roundtrip_and_exact_deterministic_bytes(complete_identity):
    text = complete_identity.to_json()
    assert bi.parse_identity(text) == complete_identity
    assert bi.parse_identity(text).to_json() == text
    assert text.endswith("\n") and "\r" not in text
    assert complete_identity.complete
    complete_identity.require_complete()


@pytest.mark.parametrize("key,value", [
    ("schemaVersion", True), ("schemaVersion", 2), ("productVersion", None),
    ("packageVersion", "2.0.0"), ("sourceCommit", "abc"), ("sourceTree", "B" * 40),
    ("sourceDirty", 0), ("sourceDirty", "false"), ("sourceDate", "2026-10-19"),
    ("sourceDate", "2026-10-19T21:34:01+00:00"), ("sourceDate", "2026-02-30T00:00:00Z"),
    ("distributionName", "not-the-product"), ("krokoVariant", "pro"),
    ("provenance", "environment"), ("productVersion", "secret-version"),
])
def test_bad_resource_is_redacted_not_incomplete(complete_identity, key, value):
    payload = asdict(complete_identity)
    payload[key] = value
    with pytest.raises(bi.IdentityError):
        bi.BuildIdentity.from_dict(payload)


@pytest.mark.parametrize("raw", ['{}', '[]', '{"schemaVersion":1,"schemaVersion":1}', "{"])
def test_unknown_missing_duplicate_and_corrupt_schema(raw):
    with pytest.raises(bi.IdentityError):
        bi.parse_identity(raw)


@pytest.mark.parametrize("key,value", [
    ("sourceCommit", None), ("sourceTree", None), ("sourceDirty", None),
    ("sourceDirty", True), ("sourceDate", None), ("provenance", "manual"),
])
def test_incomplete_manual_identity_is_not_an_official_candidate(complete_identity, key, value):
    partial = replace(complete_identity, **{key: value})
    assert bi.BuildIdentity.from_dict(asdict(partial)) == partial
    assert not partial.complete
    with pytest.raises(bi.IdentityError, match="official candidate"):
        partial.require_complete()


@pytest.mark.parametrize("name,variant", [
    ("voice-stt-server", "free"), ("voice-stt-server-pro", "pro"),
])
def test_public_package_variant_is_bound(complete_identity, name, variant):
    payload = asdict(replace(complete_identity, distributionName=name, krokoVariant=variant))
    assert bi.BuildIdentity.from_dict(payload).krokoVariant == variant
    payload["krokoVariant"] = "pro" if variant == "free" else "free"
    with pytest.raises(bi.IdentityError):
        bi.BuildIdentity.from_dict(payload)


def test_manual_without_git_does_not_discover_foreign_parent(tmp_path, complete_identity):
    (tmp_path / ".git").mkdir()
    manual = tmp_path / "manual"
    manual.mkdir()
    # Stale files in a manual source tree have no authority.
    (manual / "VoiceSTT").mkdir()
    (manual / "VoiceSTT" / bi.RESOURCE_NAME).write_text(complete_identity.to_json())
    with mock.patch("subprocess.run", side_effect=AssertionError):
        result = capture_identity(manual, "2.0.0", "voicestt")
    assert result.sourceCommit is None and result.sourceDirty is None
    assert result.provenance == "manual"


def test_sdist_retains_origin_not_the_enclosing_git(tmp_path, complete_identity):
    (tmp_path / "PKG-INFO").touch()
    (tmp_path / "VoiceSTT").mkdir()
    (tmp_path / "VoiceSTT" / bi.RESOURCE_NAME).write_text(complete_identity.to_json())
    with mock.patch("subprocess.run", side_effect=AssertionError):
        assert capture_identity(tmp_path, complete_identity.productVersion, "voicestt") == complete_identity
        with pytest.raises(bi.IdentityError):
            capture_identity(tmp_path, "3.0.0", "voicestt")


@pytest.mark.parametrize("version,commit,valid", [
    ("", "", True), ("  ", "  ", True),
    ("2.0.0-rc.1+build.5", "a" * 40, True),
    ("3.0.0", "", False), ("", "b" * 40, False),
    ("", "unknown", False), ("", "short", False),
])
def test_packaged_overrides_cannot_replace_identity(
    monkeypatch, complete_identity, version, commit, valid
):
    monkeypatch.setenv("VOICESTT_BUILD_VERSION", version)
    monkeypatch.setenv("VOICESTT_SERVER_COMMIT", commit)
    with mock.patch.object(bi, "load_build_identity", return_value=complete_identity), \
         mock.patch.object(bi, "installed_distribution",
                           return_value=("voicestt", complete_identity.packageVersion)), \
         mock.patch.object(bi, "package_root", return_value=Path("Z:\\not-source")):
        if valid:
            assert _version.resolve_version() == complete_identity.productVersion
            assert runtime.server_commit() == complete_identity.sourceCommit
        else:
            with pytest.raises(bi.IdentityError):
                _version.resolve_version()


def test_resource_wins_over_random_parent_version(tmp_path, complete_identity):
    (tmp_path / "VERSION").write_text("9.9.9\n")
    with mock.patch.object(bi, "package_root", return_value=tmp_path), \
         mock.patch.object(bi, "load_build_identity", return_value=complete_identity), \
         mock.patch.object(bi, "installed_distribution",
                           return_value=("voicestt", complete_identity.packageVersion)):
        assert _version.resolve_version() == complete_identity.productVersion


def test_used_resource_metadata_mismatch_is_fatal(complete_identity):
    with mock.patch.object(bi, "load_build_identity", return_value=complete_identity), \
         mock.patch.object(bi, "package_root", return_value=Path("Z:\\not-source")), \
         mock.patch.object(bi, "installed_distribution", return_value=("voice-stt-server-pro", "2.0.0")):
        with pytest.raises(bi.IdentityError, match="metadata"):
            bi.validated_build_identity()


@pytest.mark.parametrize("name", bi.PRODUCT_DISTRIBUTIONS)
def test_stable_legacy_fallback_has_actual_owner(name):
    with mock.patch.object(bi, "load_build_identity", return_value=None), \
         mock.patch.object(bi, "package_root", return_value=Path("Z:\\not-source")), \
         mock.patch.object(bi, "installed_distribution", return_value=(name, "2.0.0")):
        assert _version.resolve_version() == "2.0.0"


def test_old_rc_without_original_spelling_is_explicit_error():
    with mock.patch.object(bi, "load_build_identity", return_value=None), \
         mock.patch.object(bi, "package_root", return_value=Path("Z:\\not-source")), \
         mock.patch.object(bi, "installed_distribution", return_value=("voice-stt-server", "2.0.0rc1")):
        with pytest.raises(_version.SemVerError):
            _version.resolve_version()


def test_ambiguous_owners_are_not_ordered_by_version(tmp_path):
    entry = metadata.PackagePath("VoiceSTT/_version.py")
    owner = mock.Mock(files=[entry], version="2.0.0")
    owner.locate_file.return_value = tmp_path / str(entry)
    owner.read_text.return_value = None
    owner.metadata = {"Name": "voicestt"}
    with mock.patch.object(bi, "package_root", return_value=tmp_path), \
         mock.patch.object(bi.metadata, "distributions",
                           side_effect=lambda **kwargs: [owner, owner] if kwargs["name"] == "voicestt" else []):
        with pytest.raises(bi.IdentityError, match="multiple"):
            bi.installed_distribution()


def test_unrelated_installed_metadata_cannot_describe_source(tmp_path):
    owner = mock.Mock(files=[metadata.PackagePath("VoiceSTT/_version.py")], version="9.9.9")
    owner.locate_file.return_value = tmp_path / "elsewhere" / "_version.py"
    owner.read_text.return_value = None
    with mock.patch.object(bi, "package_root", return_value=tmp_path), \
         mock.patch.object(bi.metadata, "distributions", return_value=[owner]):
        assert bi.installed_distribution() == (None, None)


@pytest.mark.parametrize("source_version,installed_copies,valid", [
    ("2.0.0", 1, True), ("3.0.0", 1, False), ("2.0.0", 2, False),
])
def test_editable_source_metadata_alias_is_not_a_second_installation(
    tmp_path, source_version, installed_copies, valid
):
    (tmp_path / "setup.py").touch()
    (tmp_path / ".git").mkdir()
    source = mock.Mock(files=[metadata.PackagePath("VoiceSTT/_version.py")],
                       version=source_version, metadata={"Name": "voicestt"})
    source.locate_file.side_effect = lambda entry: tmp_path / str(entry)
    source.read_text.side_effect = lambda key: "source metadata" if key == "PKG-INFO" else None
    installed = mock.Mock(files=[], version="2.0.0", metadata={"Name": "voicestt"})
    installed.locate_file.return_value = tmp_path / "site-packages"
    installed.read_text.side_effect = lambda key: json.dumps({
        "url": tmp_path.as_uri(), "dir_info": {"editable": True},
    }) if key == "direct_url.json" else None
    with mock.patch.object(bi, "package_root", return_value=tmp_path), \
         mock.patch.object(bi.metadata, "distributions", side_effect=lambda **kwargs: (
             [source, *([installed] * installed_copies)] if kwargs["name"] == "voicestt" else []
         )):
        if valid:
            assert bi.installed_distribution() == ("voicestt", "2.0.0")
        else:
            with pytest.raises(bi.IdentityError, match="multiple"):
                bi.installed_distribution()


def test_owning_metadata_name_cannot_disagree_with_distribution_lookup(tmp_path):
    owner = mock.Mock(files=[metadata.PackagePath("VoiceSTT/_version.py")], version="2.0.0")
    owner.locate_file.return_value = tmp_path / "VoiceSTT" / "_version.py"
    owner.read_text.return_value = None
    owner.metadata = {"Name": "voice-stt-server-pro"}
    with mock.patch.object(bi, "package_root", return_value=tmp_path), \
         mock.patch.object(bi.metadata, "distributions",
                           side_effect=lambda **kwargs: [owner] if kwargs["name"] == "voicestt" else []):
        with pytest.raises(bi.IdentityError, match="metadata"):
            bi.installed_distribution()


def test_duplicate_search_paths_are_not_duplicate_installed_products(tmp_path, monkeypatch):
    owner = mock.Mock(files=[metadata.PackagePath("VoiceSTT/_version.py")], version="2.0.0")
    owner.locate_file.return_value = tmp_path / "VoiceSTT" / "_version.py"
    owner.read_text.return_value = None
    owner.metadata = {"Name": "voicestt"}
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(bi.sys, "path", ["", str(tmp_path), str(tmp_path)])
    with mock.patch.object(bi, "package_root", return_value=tmp_path), \
         mock.patch.object(bi.metadata, "distributions", side_effect=lambda **kwargs: (
             [owner for path in kwargs["path"]] if kwargs["name"] == "voicestt" else []
         )):
        assert bi.installed_distribution() == ("voicestt", "2.0.0")


def test_stale_source_resource_is_ignored(tmp_path):
    (tmp_path / "setup.py").touch()
    (tmp_path / "VoiceSTT").mkdir()
    (tmp_path / "VoiceSTT" / bi.RESOURCE_NAME).write_text("corrupt")
    with mock.patch.object(bi, "package_root", return_value=tmp_path):
        assert bi.load_build_identity() is None


def test_source_mismatch_never_becomes_a_candidate(complete_identity):
    with pytest.raises(bi.IdentityError, match="provenance"):
        match_identity(replace(complete_identity, sourceTree="c" * 40), complete_identity)


def test_new_official_wheel_requires_resource(tmp_path):
    import zipfile
    path = tmp_path / "old.whl"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("old.dist-info/METADATA", "Name: voicestt\nVersion: 2.0.0\n")
    assert wheel_identity(path, required=False) is None
    with pytest.raises(bi.IdentityError, match="lacks"):
        wheel_identity(path)


@pytest.mark.parametrize("tag", ["1freepro", "pro", "1enterprise"])
def test_ambiguous_or_invalid_native_variant_is_error(tag):
    dist = mock.Mock()
    dist.read_text.return_value = f"Build: {tag}\n"
    with mock.patch.object(runtime.metadata, "distribution", return_value=dist):
        with pytest.raises(bi.IdentityError, match="variant"):
            runtime.runtime_variant()
