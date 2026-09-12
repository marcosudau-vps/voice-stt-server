from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v1_kroko_release as kr  # noqa: E402
import v1_release_manifest as rm  # noqa: E402

COMMIT = "1" * 40
TREE = "2" * 40


def _write_file(path: Path, payload: bytes) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {"filename": path.name, "sha256": rm.sha256_file(path), "bytes": len(payload)}


def _candidate_tree(tmp_path: Path) -> Path:
    root = tmp_path / "candidate"
    py = root / "python"
    wheel = _write_file(py / "voice_stt_server-1.0.0-py3-none-any.whl", b"wheel")
    sdist = _write_file(py / "voice_stt_server-1.0.0.tar.gz", b"sdist")
    python_identity = {
        "distribution": "voice-stt-server",
        "version": "1.0.0",
        "wheel": wheel,
        "sdist": sdist,
    }
    (py / "python-artifact.json").write_text(
        json.dumps(python_identity, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    for variant in ("free", "pro"):
        kroko_dir = root / "kroko" / variant
        kroko_dir.mkdir(parents=True, exist_ok=True)
        kroko_wheel = kroko_dir / f"kroko_onnx-1.12.9-1{variant}-cp312-cp312-linux_x86_64.whl"
        kroko_wheel.write_bytes(("kroko-" + variant).encode())
        record = {
            **kr.fingerprint_payload(variant),
            "fingerprint": kr.fingerprint_for(variant),
            "wheel": {
                "filename": kroko_wheel.name,
                "sha256": kr.sha256_file(kroko_wheel),
                "bytes": kroko_wheel.stat().st_size,
            },
        }
        (kroko_dir / "artifact.json").write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        image_dir = root / "images"
        image_dir.mkdir(parents=True, exist_ok=True)
        digest = "sha256:" + ("a" if variant == "free" else "b") * 64
        image = rm.IMAGE_NAMES[variant]
        staging_tag = f"ghcr.io/marcosudau-vps/{image}-v1-staging:candidate-123"
        (image_dir / f"{variant}.json").write_text(
            json.dumps(
                {
                    "variant": variant,
                    "image": image,
                    "stagingTag": staging_tag,
                    "digest": digest,
                    "stagingReference": f"{staging_tag.split(':', 1)[0]}@{digest}",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return root


def test_candidate_schema_has_one_python_distribution_and_two_image_variants(tmp_path, monkeypatch):
    root = _candidate_tree(tmp_path)
    # Synthetic package bytes cannot be parsed by build_python_identity, so bind
    # the already written identity for this schema-level unit test.
    monkeypatch.setattr(
        rm,
        "build_python_identity",
        lambda _dist: json.loads((root / "python" / "python-artifact.json").read_text()),
    )
    manifest = rm.assemble_candidate(
        candidate_dir=root,
        candidate_id="candidate-123",
        source_commit=COMMIT,
        source_tree=TREE,
        run_url="https://github.com/example/actions/runs/123",
        evidence_ref="offline-unit-test",
    )
    assert manifest["python"]["distribution"] == "voice-stt-server"
    assert set(manifest["images"]) == {"free", "pro"}
    assert manifest["images"]["free"]["image"] == "voice-stt-server"
    assert manifest["images"]["pro"]["image"] == "voice-stt-server-pro"
    assert "voice-stt-server-pro" not in json.dumps(manifest["python"])


def test_second_pypi_distribution_is_rejected(tmp_path):
    root = _candidate_tree(tmp_path)
    manifest = {
        "schemaVersion": 1,
        "productVersion": "1.0.0",
        "sourceCommit": COMMIT,
        "sourceTree": TREE,
        "python": {
            "distribution": "voice-stt-server-pro",
            "version": "1.0.0",
            "wheel": {"sha256": "a" * 64},
            "sdist": {"sha256": "b" * 64},
        },
        "kroko": {},
        "images": {},
        "qualification": {"status": "QUALIFIED", "evidenceRef": "x", "publicWritesPerformed": False},
    }
    with pytest.raises(rm.CandidateManifestError, match="exactly one PyPI distribution"):
        rm.validate_candidate(manifest)


def test_staging_image_must_be_digest_bound_and_not_final_version_tag():
    digest = "sha256:" + "c" * 64
    record = {
        "variant": "free",
        "image": "voice-stt-server",
        "digest": digest,
        "stagingReference": f"ghcr.io/o/voice-stt-server-v1-staging@{digest}",
    }
    rm.validate_image_record("free", record)
    record["stagingReference"] = "ghcr.io/o/voice-stt-server-v1-staging:1.0.0"
    with pytest.raises(rm.CandidateManifestError):
        rm.validate_image_record("free", record)


def test_release_dockerfile_consumes_prebuilt_wheels_and_preserves_v1_model_paths():
    text = (ROOT / "build" / "v1-release.Dockerfile").read_text(encoding="utf-8")
    assert "COPY release-inputs/python/*.whl" in text
    assert "COPY release-inputs/kroko/*.whl" in text
    assert "stt-install-kroko --build" not in text
    assert "pip install -e" not in text
    assert "VOICESTT_FASTER_WHISPER_MODEL_ROOT=/models/ctranslate2" in text
    assert "VOICESTT_KROKO_MODEL_ROOT=/models/kroko" in text
    assert "--model\", \"small" in text
    assert "--realtime-model\", \"tiny" in text
    assert "build/vps" not in text


def test_inventory_contains_relative_hash_bound_paths(tmp_path):
    root = tmp_path / "candidate"
    _write_file(root / "python" / "a.whl", b"abc")
    inv = rm.build_inventory(root)
    assert inv["files"][0]["path"] == "python/a.whl"
    assert inv["files"][0]["sha256"] == rm.sha256_file(root / "python" / "a.whl")
    assert str(tmp_path) not in json.dumps(inv)
