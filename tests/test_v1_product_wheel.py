from __future__ import annotations

import zipfile
from pathlib import Path
import pytest
from tools import v1_product_wheel as pw


def _wheel(path: Path, dist: str, tag: str, files: dict[str, bytes]) -> Path:
    info=f"{dist}.dist-info"; payload={f"{info}/METADATA":b"Metadata-Version: 2.1\nName: voice-stt-server\nVersion: 1.0.0\nRequires-Python: >=3.11\n\nbase\n",f"{info}/WHEEL":f"Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: {tag}\n".encode(),f"{info}/entry_points.txt":b"[console_scripts]\nstt-server = VoiceSTT_server.server:main\n",f"{info}/RECORD":b"",**files}
    with zipfile.ZipFile(path,"w") as zf:
        for name,data in payload.items(): zf.writestr(name,data)
    return path


def _base(tmp: Path) -> Path:
    return _wheel(tmp/"base.whl","voice_stt_server-1.0.0","py3-none-any",{"VoiceSTT/__init__.py":b"","VoiceSTT/_release_variant.py":b'KROKO_VARIANT = "free"\n',"VoiceSTT_server/server.py":b"def main(): pass\n","api_fastapi_server/__init__.py":b""})


def _kroko(tmp: Path, platform: str) -> Path:
    native="kroko_onnx/_sherpa_onnx.pyd" if platform=="win_amd64" else "kroko_onnx/_sherpa_onnx.so"; dist="kroko_onnx-1.12.9"
    return _wheel(tmp/f"kroko-{platform}.whl",dist,f"cp312-cp312-{platform}",{"kroko_onnx/__init__.py":b"OnlineRecognizer = object\n",native:b"native",f"{dist}.dist-info/LICENSE":b"Apache-2.0 test license"})

@pytest.mark.parametrize("variant,distribution",[("free","voice-stt-server"),("pro","voice-stt-server-pro")])
@pytest.mark.parametrize("platform",["linux_x86_64","win_amd64"])
def test_final_product_wheel_embeds_runtime_and_native_tag(monkeypatch,tmp_path,variant,distribution,platform):
    base=_base(tmp_path); kroko=_kroko(tmp_path,platform); monkeypatch.setattr(pw,"_build_base_wheel",lambda _tmp:base)
    report=pw.build_product_wheel(variant,platform,kroko,tmp_path/"out")
    assert report["distribution"]==distribution and report["variant"]==variant
    assert report["rootIsPurelib"] is False
    assert report["tags"]==[f"cp312-cp312-{platform}"]
    assert report["krokoNativePayload"] and report["licensePayload"]
    assert report["nestedWheels"]==[] and report["krokoDistInfoEntries"]==[]
    assert not report["filename"].endswith("py3-none-any.whl")

def test_rejects_pure_kroko_tag(tmp_path):
    kroko=_wheel(tmp_path/"bad.whl","kroko_onnx-1.0","py3-none-any",{"kroko_onnx/a.py":b""})
    with pytest.raises(pw.ProductWheelError): pw.parse_native_tag(kroko,"linux_x86_64")
