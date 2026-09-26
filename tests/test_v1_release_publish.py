from __future__ import annotations

import pytest

from tools import v1_release_publish as pub


def _manifest():
    def project(variant, dist):
        return {"distribution":dist,"version":"1.0.0","variant":variant,"wheels":{
            "linux_x86_64":{"filename":dist.replace('-','_')+"-1.0.0-cp312-cp312-linux_x86_64.whl","sha256":"a"*64},
            "win_amd64":{"filename":dist.replace('-','_')+"-1.0.0-cp312-cp312-win_amd64.whl","sha256":"b"*64},
        }}
    return {"python":{"free":project("free","voice-stt-server"),"pro":project("pro","voice-stt-server-pro")}}


def _payload(manifest, variant, present=("linux_x86_64","win_amd64"), corrupt=()):
    urls=[]
    for platform, info in manifest["python"][variant]["wheels"].items():
        if platform in present:
            sha = "f"*64 if platform in corrupt else info["sha256"]
            urls.append({"filename":info["filename"],"digests":{"sha256":sha}})
    return {"urls":urls}


def test_only_four_canonical_artifact_states_exist():
    assert pub.STATES == {pub.ABSENT,pub.MATCH,pub.CONFLICT,pub.UNKNOWN}
    assert "PARTIAL" not in pub.STATES


def test_first_run_free_absent_pro_absent_then_controlled_bootstrap_pause():
    m=_manifest(); free_before=pub.inspect_pypi_project(m,"free",fetch=lambda _u:None); pro=pub.inspect_pypi_project(m,"pro",fetch=lambda _u:None)
    free_after=pub.inspect_pypi_project(m,"free",fetch=lambda _u:_payload(m,"free"))
    assert all(v==pub.ABSENT for v in free_before["artifacts"].values())
    assert pub.bootstrap_phase1_required(free_before,free_after,pro)


def test_resume_free_match_pro_absent_stages_only_pro():
    m=_manifest(); free=pub.inspect_pypi_project(m,"free",fetch=lambda _u:_payload(m,"free")); pro=pub.inspect_pypi_project(m,"pro",fetch=lambda _u:None)
    assert pub.project_complete(free); assert set(pro["artifacts"].values())=={pub.ABSENT}


def test_free_conflict_or_unknown_hard_stops():
    m=_manifest(); conflict=pub.inspect_pypi_project(m,"free",fetch=lambda _u:_payload(m,"free",corrupt=("linux_x86_64",)))
    with pytest.raises(pub.PublicationPrecheckError): pub.validate_publishable(conflict)
    unknown=pub.inspect_pypi_project(m,"free",fetch=lambda _u:(_ for _ in ()).throw(TimeoutError()))
    with pytest.raises(pub.PublicationPrecheckError): pub.validate_publishable(unknown)


def test_one_pro_wheel_match_one_absent_is_resumable_without_partial_state():
    m=_manifest(); report=pub.inspect_pypi_project(m,"pro",fetch=lambda _u:_payload(m,"pro",present=("linux_x86_64",)))
    assert sorted(report["artifacts"].values()) == [pub.ABSENT,pub.MATCH]
    pub.validate_publishable(report); assert not pub.project_complete(report)


def test_all_four_match_means_pypi_complete():
    m=_manifest(); assert pub.project_complete(pub.inspect_pypi_project(m,"free",fetch=lambda _u:_payload(m,"free")))
    assert pub.project_complete(pub.inspect_pypi_project(m,"pro",fetch=lambda _u:_payload(m,"pro")))


def test_registry_digest_and_aliases():
    d="sha256:"+"a"*64
    assert pub.classify_digest(None,d)==pub.UNKNOWN and pub.classify_digest(d,d)==pub.MATCH
    assert pub.aliases_for("1.0.0")==["1.0","1","latest"]


def test_unexpected_pypi_file_conflicts_even_when_both_expected_match():
    m = _manifest()
    payload = _payload(m, "free")
    payload["urls"].append({"filename": "unqualified-extra.whl", "digests": {"sha256": "c" * 64}})
    report = pub.inspect_pypi_project(m, "free", fetch=lambda _u: payload)
    assert set(report["artifacts"].values()) == {pub.CONFLICT}
    with pytest.raises(pub.PublicationPrecheckError):
        pub.validate_publishable(report)


def test_github_release_read_error_is_unknown_not_absent():
    assert pub.inspect_github_release("v1.0.0", fetch=lambda _tag: None) == pub.ABSENT
    assert pub.inspect_github_release("v1.0.0", fetch=lambda tag: {"id": 123, "tag_name": tag}) == pub.MATCH
    assert pub.inspect_github_release("v1.0.0", fetch=lambda _tag: {}) == pub.UNKNOWN
    assert pub.inspect_github_release("v1.0.0", fetch=lambda _tag: (_ for _ in ()).throw(TimeoutError())) == pub.UNKNOWN
