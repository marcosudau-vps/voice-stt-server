"""Offline discovery must never enlarge the existing Kroko trust boundary."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from VoiceSTT.kroko.catalog import (
    CatalogValidationError, KrokoCatalog, MAX_CATALOG_BYTES, SCHEMA,
    create_download_plan, load_catalog, parse_entry,
)
from VoiceSTT.kroko.models import KrokoModelManifest, default_manifest_path, load_manifest
from tools.kroko_catalog_cli import main

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures" / "kroko_catalog"
CATALOG = FIXTURES / "catalog_124.json"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("catalog operations must remain offline")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr("urllib.request.urlopen", forbidden)


@pytest.fixture
def raw():
    return json.loads((FIXTURES / "synthetic.json").read_text(encoding="utf-8"))["models"][0]


def payload(*rows):
    return {"schema": SCHEMA, "models": list(rows)}


def codes(exc):
    return {d.code for d in exc.value.diagnostics}


def test_all_provided_models_and_original_values():
    original = json.loads(CATALOG.read_text(encoding="utf-8"))
    catalog = load_catalog(CATALOG)
    assert len(catalog.entries) == 124
    assert catalog.summary() == {
        "total": 124,
        "languages": ("DE", "EN", "ES", "FR", "IT", "IW", "JP", "NL", "PL", "PT", "SV", "TR"),
        "editions": {"Community": 19, "Pro": 105},
        "sizes": {"S": 20, "M": 28, "L": 76},
    }
    for record in original["models"]:
        entry = catalog.get(record["model_id"])
        assert entry is not None
        assert entry.public_dict() == record
        assert entry.name == (
            f"Kroko-{entry.language}-{entry.edition}-{entry.chunk}-"
            f"{entry.size}-{entry.mode}-{entry.revision}.data"
        )
        assert entry.streaming
    assert {e.chunk for e in catalog.entries} == {16, 32, 64, 128}
    assert {e.revision for e in catalog.entries} == {"001", "002"}
    assert len(catalog.filter(language="IW")) == 6
    assert catalog.filter(language="HE") == ()


def test_filter_combinations_and_deterministic_sort():
    catalog = load_catalog(CATALOG)
    rows = json.loads(CATALOG.read_text(encoding="utf-8"))["models"]
    assert KrokoCatalog.from_payload(payload(*reversed(rows))).entries == catalog.entries
    filtered = catalog.filter(language="DE", edition="Pro", chunk=16, size="M", streaming=True)
    assert len(filtered) == 1
    assert filtered[0].name == "Kroko-DE-Pro-16-M-Streaming-001.data"
    for kwargs, expected in [({"language": "DE"}, 10), ({"edition": "Community"}, 19),
                             ({"chunk": 32}, 26), ({"size": "S"}, 20),
                             ({"streaming": False}, 0), ({"streaming": True}, 124)]:
        assert len(catalog.filter(**kwargs)) == expected
    # Numeric chunk/revision order and size order are deliberate, not lexical.
    keys = [(e.language, e.edition, e.chunk, {"S": 0, "M": 1, "L": 2}[e.size],
             int(e.revision), e.revision, e.name, e.model_id) for e in catalog.entries]
    assert keys == sorted(keys)


@pytest.mark.parametrize("name", [
    "", "other.data", "../Kroko-DE-Pro-16-M-Streaming-001.data",
    "..\\Kroko-DE-Pro-16-M-Streaming-001.data",
    "/Kroko-DE-Pro-16-M-Streaming-001.data", "C:\\Kroko-DE-Pro-16-M-Streaming-001.data",
    "Kroko-DE-Pro-16-XL-Streaming-001.data", "Kroko-DE-Pro-16-M-Offline-001.data",
    "Kroko-DE-Pro-0-M-Streaming-001.data", "Kroko-DE-Pro-16-M-Streaming-001.data\n",
    "Kroko-DE-Pro-16-M-Streaming-001.data:secret", "Kroko-DE-Pro-16-M-Streaming-001.data.part",
    "Kroko-DE-Pro-16-M-Streaming-001.data%2f..", "Kroko-DE-Pro-16-M-Streaming-1.data",
])
def test_invalid_names_and_paths(raw, name):
    raw["name"] = name
    with pytest.raises(CatalogValidationError) as exc:
        parse_entry(raw)
    assert "unknown_name" in codes(exc)


@pytest.mark.parametrize("field", ["model_id", "name", "language", "edition", "chunk", "size", "mode", "revision"])
def test_required_fields(raw, field):
    del raw[field]
    with pytest.raises(CatalogValidationError) as exc:
        parse_entry(raw)
    assert "missing_field" in codes(exc)


@pytest.mark.parametrize("field,value", [
    ("language", "de"), ("edition", "Community"), ("chunk", "16"), ("chunk", True),
    ("chunk", 16.0), ("chunk", 32), ("size", "L"), ("mode", "Offline"),
    ("revision", 1), ("revision", "002"), ("parse_ok", False), ("source", "unverified"),
    ("model_id", "not-a-uuid"), ("model_id", None), ("model_id", 123),
])
def test_invalid_or_conflicting_metadata(raw, field, value):
    raw[field] = value
    with pytest.raises(CatalogValidationError):
        parse_entry(raw)


def test_duplicate_ids_names_and_conflicting_urls(raw):
    cases = [
        (deepcopy(raw), "duplicate_id"),
        ({**raw, "download_url": None}, "url_conflict"),
        ({**raw, "source": None}, "id_conflict"),
        ({**raw, "model_id": "00000000-0000-4000-8000-000000000002"}, "name_conflict"),
    ]
    for second, expected in cases:
        with pytest.raises(CatalogValidationError) as exc:
            KrokoCatalog.from_payload(payload(raw, second))
        assert expected in codes(exc)
        assert exc.value.diagnostics[0].index == 1
    second = deepcopy(raw)
    second["name"] = second["name"].replace("-001.data", "-002.data")
    second["revision"] = "002"
    second["download_url"] = second["download_url"].replace("-001.data", "-002.data")
    with pytest.raises(CatalogValidationError) as exc:
        KrokoCatalog.from_payload(payload(raw, second))
    assert "url_conflict" in codes(exc)


@pytest.mark.parametrize("url", [
    "", 42, "http://download.kroko.ai/models/{name}", "file:///tmp/{name}",
    "https://evil.test/models/{name}", "https://download.kroko.ai.evil.test/models/{name}",
    "https://user:password@download.kroko.ai/models/{name}",
    "https://download.kroko.ai:443/models/{name}", "https://download.kroko.ai./models/{name}",
    "https://download.kroko.ai/models/../models/{name}",
    "https://download.kroko.ai/models/%2e%2e/models/{name}",
    "https://download.kroko.ai/models/{name}?token=secret", "https://download.kroko.ai/models/{name}#secret",
    "https://download.kroko.ai/models/{name}#", "https://download.kroko.ai/models/other.data",
    "https://download.kroko.ai\\@evil.test/models/{name}",
    "https://huggingface.co/evil/repo/resolve/main/{name}",
    "https://huggingface.co/Banafo/Kroko-ASR/resolve/main/{name}?redirect=https://evil.test",
    "https://huggingface.co/Banafo/Kroko-ASR/resolve/main/{name}?download=true&token=secret",
    "https://huggingface.co/Banafo/Kroko-ASR/resolve/main/{name}?",
    " https://download.kroko.ai/models/{name}", "https://download.kroko.ai/\nmodels/{name}",
])
def test_untrusted_download_urls(raw, url):
    raw["download_url"] = url.format(name=raw["name"]) if isinstance(url, str) else url
    with pytest.raises(CatalogValidationError) as exc:
        parse_entry(raw)
    assert "invalid_url" in codes(exc)


def test_download_plan_has_no_implicit_trust(raw):
    entry = parse_entry(raw)
    plan = create_download_plan(entry)
    assert plan.model_id == entry.model_id
    assert plan.expected_name == plan.local_filename == entry.name
    assert plan.download_url_present
    assert plan.integrity_evidence == "missing"
    assert plan.expected_sha256 is plan.expected_bytes is None
    assert not plan.manifest_automatic_install_allowed
    assert not plan.automatic_provisioning_ready
    assert not plan.download_integrity_verified
    assert plan.technical_access == plan.product_license_activation == "not_checked"
    assert "authoritative_integrity_missing" in plan.blockers
    missing = create_download_plan(replace(entry, download_url=None))
    assert not missing.download_url_present
    assert "download_source_missing" in missing.blockers
    with pytest.raises(CatalogValidationError):
        create_download_plan(replace(entry, name="../../unsafe.data"))
    with pytest.raises(FrozenInstanceError):
        entry.name = "unsafe.data"


def test_manifest_hashes_rights_and_product_authority_unchanged():
    from VoiceSTT_server.stt_model_management import default_product_authority
    before_bytes = default_manifest_path().read_bytes()
    before_authority = default_product_authority()
    manifest = load_manifest()
    assert len(manifest.entries) == 12
    plans = [create_download_plan(e) for e in load_catalog(CATALOG).entries]
    assert sum(p.integrity_evidence == "manifest" for p in plans) == 12
    for plan in plans:
        assert not plan.manifest_automatic_install_allowed
        assert not plan.automatic_provisioning_ready
        assert not plan.download_integrity_verified
        if plan.manifest_model_id:
            trusted = manifest.get(plan.manifest_model_id)
            assert (plan.expected_sha256, plan.expected_bytes) == (trusted.sha256, trusted.bytes)
            assert plan.model_id != trusted.id
            if trusted.tier == "community":
                assert f"/resolve/{manifest.upstream['communityRevision']}/" in plan.download_source
                assert "/resolve/main/" in plan.catalog_source
    assert default_manifest_path().read_bytes() == before_bytes
    assert default_product_authority() == before_authority
    assert all(not e.provisioning_allowed for e in before_authority if e.engine == "kroko_onnx")


def test_manifest_conflicts_and_incomplete_evidence():
    entry = load_catalog(CATALOG).filter(language="DE", edition="Community", chunk=64)[0]
    data = json.loads(default_manifest_path().read_text(encoding="utf-8"))
    row = data["models"][0]
    row["language"] = "en"
    with pytest.raises(CatalogValidationError):
        create_download_plan(entry, manifest=KrokoModelManifest(data))
    row["language"] = "de"
    row["sha256"] = ""
    assert create_download_plan(entry, manifest=KrokoModelManifest(data)).integrity_evidence == "missing"
    row["sha256"] = "a" * 64
    row["redistributionStatus"] = "ALLOWED"
    plan = create_download_plan(entry, manifest=KrokoModelManifest(data))
    assert plan.manifest_automatic_install_allowed  # synthetic authority only
    assert not plan.automatic_provisioning_ready
    data["upstream"]["communityRevision"] = "main"
    assert not create_download_plan(entry, manifest=KrokoModelManifest(data)).manifest_automatic_install_allowed


def test_unknown_metadata_cannot_supply_trust(raw):
    for field, value in (("sha256", "a" * 64), ("bytes", 123),
                         ("provisioning_allowed", True), ("license_key", "SYNTHETIC_ONLY")):
        with pytest.raises(CatalogValidationError) as exc:
            parse_entry({**raw, field: value})
        assert "unknown_fields" in codes(exc)
    # Multiple invalid rows yield locations, never a partial catalog.
    with pytest.raises(CatalogValidationError) as exc:
        KrokoCatalog.from_payload(payload({**raw, "chunk": 999}, {**raw, "size": "XL"}))
    assert [d.index for d in exc.value.diagnostics] == [0, 1]


def test_authoritative_source_can_exist_without_catalog_link():
    entry = load_catalog(CATALOG).filter(language="DE", edition="Community", chunk=64)[0]
    plan = create_download_plan(replace(entry, download_url=None))
    assert plan.catalog_source is None
    assert plan.download_url_present
    assert plan.download_source.startswith("https://huggingface.co/Banafo/Kroko-ASR/resolve/")
    assert not plan.manifest_automatic_install_allowed


def test_ambiguous_manifest_name_is_rejected():
    entry = load_catalog(CATALOG).filter(language="DE", edition="Community", chunk=64)[0]
    data = json.loads(default_manifest_path().read_text(encoding="utf-8"))
    data["models"].append({**data["models"][0], "id": "synthetic-duplicate"})
    with pytest.raises(CatalogValidationError) as exc:
        create_download_plan(entry, manifest=KrokoModelManifest(data))
    assert "manifest_conflict" in codes(exc)


@pytest.mark.parametrize("position", ["root", "row", "url", "name", "source", "note"])
def test_secrets_never_in_diagnostics_or_cli(tmp_path, raw, capsys, position):
    secret = "SYNTHETIC_SECRET_SENTINEL_ONLY"
    data = payload(raw)
    if position == "root":
        data["license_key"] = {"model_password": secret}
    elif position == "row":
        raw["model_password"] = secret
    elif position == "note":
        data["note"] = secret
    else:
        raw[{"url": "download_url", "name": "name", "source": "source"}[position]] = secret
    path = tmp_path / "input.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(CatalogValidationError) as exc:
        load_catalog(path)
    assert secret not in str(exc.value)
    assert secret not in repr(exc.value.diagnostics)
    for command in ("summary", "validate", "list", "inspect", "plan"):
        args = ["--catalog", str(path), command]
        if command in ("inspect", "plan"):
            args += ["--model-id", secret]
        assert main(args) == 2
        captured = capsys.readouterr()
        assert secret not in captured.out + captured.err
        assert not captured.out


@pytest.mark.parametrize("data", [
    b'{"models": "SYNTHETIC_SECRET_SENTINEL_ONLY",', b"\xff",
    b'{"schema":"one","schema":"two","models":[]}', b"[1,2]",
    json.dumps({"schema": SCHEMA, "models": {}}).encode(),
    b"[" * 1100, b" " * (MAX_CATALOG_BYTES + 1),
], ids=["truncated", "encoding", "duplicate_field", "array", "models_not_array", "depth", "size"])
def test_malformed_json_and_schema(tmp_path, data):
    path = tmp_path / "input.json"
    path.write_bytes(data)
    with pytest.raises(CatalogValidationError) as exc:
        load_catalog(path)
    assert "SYNTHETIC_SECRET_SENTINEL_ONLY" not in str(exc.value)


def test_cli_commands_and_exact_lookup(capsys):
    catalog = load_catalog(CATALOG)
    entry = catalog.entries[0]
    prefix = ["--catalog", str(CATALOG)]
    for command in ("summary", "languages", "list", "validate"):
        assert main(prefix + [command]) == 0
        assert json.loads(capsys.readouterr().out)
    assert main(prefix + ["list", "--language", "DE", "--edition", "Pro", "--chunk", "16", "--size", "M", "--streaming", "yes"]) == 0
    assert len(json.loads(capsys.readouterr().out)) == 1
    for command in ("inspect", "plan"):
        assert main(prefix + [command, "--model-id", entry.model_id]) == 0
        assert json.loads(capsys.readouterr().out)["model_id"] == entry.model_id
        assert main(prefix + [command, "--model-id", "SYNTHETIC_UNKNOWN_ID"]) == 1
        assert json.loads(capsys.readouterr().err) == {"error": "model_not_found"}
    assert catalog.get(entry.name) is None
    assert catalog.get(entry.model_id.upper()) is None


def test_cli_script_outside_checkout(tmp_path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools/kroko_catalog_cli.py"), "--catalog", str(CATALOG), "summary"],
        cwd=tmp_path, capture_output=True, text=True, check=True,
    )
    assert json.loads(result.stdout)["total"] == 124
    assert result.stderr == ""


def test_missing_file_has_safe_diagnostic(tmp_path, capsys):
    assert main(["--catalog", str(tmp_path / "SYNTHETIC_SECRET_SENTINEL_ONLY"), "summary"]) == 2
    assert "SYNTHETIC_SECRET_SENTINEL_ONLY" not in capsys.readouterr().err
