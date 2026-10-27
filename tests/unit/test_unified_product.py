"""Unified V2 regression gates; synthetic wheels never qualify native execution."""
import json
from pathlib import Path
import zipfile

import pytest

from release_tooling import config, rc_manifest
from release_tooling.engine import ExecutionMode, run_engine
from release_tooling.errors import ManifestError
from release_tooling.preflight import _check_redistribution
from tests.unit.release_support import make_manifest, make_state
from tests.unit.test_build_distribution import make_base_wheel, make_kroko_wheel
from tools import build_distribution as bd, build_production as bp


def test_only_one_official_product_and_native_input():
    assert bd.DISTRIBUTION_NAMES == {"pro": "voice-stt-server"}
    assert bp.IMAGE_NAMES == {"pro": "voice-stt-server"}
    assert rc_manifest.VARIANTS == ("pro",)
    assert bp.variants_for_target("all") == ["pro"]
    with pytest.raises(bd.DistributionBuildError):
        bd.distribution_name_for("free")
    with pytest.raises(bp.BuildError):
        bp.image_name_for("free")


@pytest.mark.parametrize("platform", ["linux_x86_64", "win_amd64"])
def test_product_retains_notices_one_owner_and_relocates_native_data(tmp_path, platform):
    base = make_base_wheel(tmp_path, "voice-stt-server")
    native = make_kroko_wheel(tmp_path, "pro", platform)
    with zipfile.ZipFile(native, "a") as archive:
        archive.writestr("kroko_onnx-1.12.9.data/platlib/native-dependency.dll", b"native-input")
        archive.writestr("kroko_onnx-1.12.9.dist-info/licenses/nested/NOTICE", b"original notice")
    result = bd.merge_kroko_runtime(base_wheel=base, kroko_wheel=native, variant="pro",
                                   out_dir=tmp_path / "out", fingerprint="synthetic")
    with zipfile.ZipFile(result["path"]) as archive:
        names = archive.namelist()
        assert archive.read("native-dependency.dll") == b"native-input"
        assert not any(n.startswith("kroko_onnx-1.12.9.data/") for n in names)
        owners = {n.split("/")[0] for n in names if ".dist-info/" in n}
        assert owners == {"voice_stt_server-2.0.0.dist-info"}
        assert len(names) == len(set(names))
        assert archive.read("voice_stt_server-2.0.0.dist-info/licenses/KROKO-ORIGINAL/licenses/nested/NOTICE") == b"original notice"
        notices = bd.verify_bundled_notices(archive)
        assert "KROKO-ONNX-LICENSE" in notices["files"]
        assert "ONNXRUNTIME-ThirdPartyNotices.txt" in notices["files"]
        assert "OPENSSL-WINDOWS-LICENSE" in notices["files"]


def test_relocated_native_payload_collision_is_refused(tmp_path):
    base = make_base_wheel(tmp_path, "voice-stt-server")
    native = make_kroko_wheel(tmp_path)
    with zipfile.ZipFile(native, "a") as archive:
        archive.writestr("kroko_onnx-1.12.9.data/platlib/voice_stt_server/__init__.py", b"collision")
    with pytest.raises(bd.DistributionBuildError, match="duplicate"):
        bd.merge_kroko_runtime(base_wheel=base, kroko_wheel=native, variant="pro", out_dir=tmp_path / "out")


def test_old_candidate_schema_and_additional_distribution_are_refused():
    manifest = make_manifest()
    manifest["schemaVersion"] = 2
    with pytest.raises(ManifestError, match="schemaVersion"):
        rc_manifest.validate_rc_manifest(manifest)
    manifest = make_manifest()
    manifest["distributions"]["free"] = dict(manifest["distributions"]["pro"])
    with pytest.raises(ManifestError, match="exactly"):
        rc_manifest.validate_rc_manifest(manifest)


def test_technical_qualification_never_grants_redistribution(tmp_path):
    manifest = make_manifest()
    manifest["redistributionApproval"] = config.redistribution_approval()
    assert manifest["releaseReadiness"] == "QUALIFIED"
    assert manifest["redistributionApproval"]["status"] == "BLOCKED"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert _check_redistribution(path, require_qualified=True).status == "FAIL"
    # An empty adapter bundle proves refusal occurs before a public operation.
    with pytest.raises(ManifestError, match="redistribution"):
        run_engine(make_state(manifest=manifest), manifest, adapters={}, mode=ExecutionMode.REAL)


def test_non_object_unified_product_is_a_manifest_error():
    manifest = make_manifest()
    manifest["distributions"]["pro"] = []
    with pytest.raises(ManifestError, match="distributions.pro"):
        rc_manifest.validate_rc_manifest(manifest)
