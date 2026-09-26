from __future__ import annotations
import pytest
from tools import v1_release_manifest as rm

def _wheel(variant,platform):
    dist=rm.DISTRIBUTIONS[variant]; name=dist.replace('-','_')+f"-1.0.0-cp312-cp312-{platform}.whl"
    return {"filename":name,"distribution":dist,"version":"1.0.0","variant":variant,"tags":[f"cp312-cp312-{platform}"],"rootIsPurelib":False,"bytes":123,"sha256":"a"*64,"krokoNativePayload":["kroko_onnx/native"],"licensePayload":["license"],"nestedWheels":[],"krokoDistInfoEntries":[],"variantMarkerPresent":True,"recordValid":True,"modelPayloadEntries":[],"obviousCredentialPatternMatches":[],"topLevel":[]}

def _manifest():
    python={}; kroko={}; images={}
    for variant in ("free","pro"):
        python[variant]={"distribution":rm.DISTRIBUTIONS[variant],"version":"1.0.0","variant":variant,"wheels":{p:_wheel(variant,p) for p in rm.PLATFORMS}}
        kroko[variant]={p:{"variant":variant,"platform":p} for p in rm.PLATFORMS}
        digest="sha256:"+("a" if variant=="free" else "b")*64
        images[variant]={"variant":variant,"image":rm.IMAGE_NAMES[variant],"digest":digest,"stagingReference":f"ghcr.io/o/{rm.IMAGE_NAMES[variant]}-v1-staging@{digest}"}
    return {"schemaVersion":2,"productVersion":"1.0.0","sourceCommit":"1"*40,"sourceTree":"2"*40,"python":python,"publicSdist":False,"kroko":kroko,"images":images,"qualification":{"status":"QUALIFIED","evidenceRef":"test","publicWritesPerformed":False}}

def test_manifest_requires_two_distributions_and_four_native_wheels():
    m=_manifest(); rm.validate_candidate(m); assert m["python"]["free"]["distribution"]=="voice-stt-server"; assert m["python"]["pro"]["distribution"]=="voice-stt-server-pro"; assert sum(len(v["wheels"]) for v in m["python"].values())==4; assert m["publicSdist"] is False

def test_missing_pro_or_pure_wheel_is_rejected():
    m=_manifest(); del m["python"]["pro"]
    with pytest.raises(rm.CandidateManifestError): rm.validate_candidate(m)
    m=_manifest(); m["python"]["pro"]["wheels"]["win_amd64"]["recordValid"]=False
    with pytest.raises(rm.CandidateManifestError): rm.validate_candidate(m)
    m=_manifest(); m["python"]["free"]["wheels"]["linux_x86_64"]["filename"]="x-py3-none-any.whl"
    with pytest.raises(rm.CandidateManifestError): rm.validate_candidate(m)
