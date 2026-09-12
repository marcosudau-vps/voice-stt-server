from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v1_release_publish as pub  # noqa: E402


def _manifest():
    return {
        "python": {
            "distribution": "voice-stt-server",
            "version": "1.0.0",
            "wheel": {"filename": "voice_stt_server-1.0.0-py3-none-any.whl", "sha256": "a" * 64},
            "sdist": {"filename": "voice_stt_server-1.0.0.tar.gz", "sha256": "b" * 64},
        }
    }


def test_pypi_absent_match_partial_and_conflict_are_distinct():
    manifest = _manifest()
    absent = pub.inspect_pypi(manifest, fetch=lambda _url: None)
    assert absent["status"] == pub.ABSENT
    assert len(absent["absent"]) == 2

    def exact(_url):
        return {
            "urls": [
                {"filename": manifest["python"]["wheel"]["filename"], "digests": {"sha256": "a" * 64}},
                {"filename": manifest["python"]["sdist"]["filename"], "digests": {"sha256": "b" * 64}},
            ]
        }

    assert pub.inspect_pypi(manifest, fetch=exact)["status"] == pub.MATCH

    def partial(_url):
        return {
            "urls": [
                {"filename": manifest["python"]["wheel"]["filename"], "digests": {"sha256": "a" * 64}}
            ]
        }

    report = pub.inspect_pypi(manifest, fetch=partial)
    assert report["status"] == "PARTIAL"
    assert report["absent"] == [manifest["python"]["sdist"]["filename"]]

    def conflict(_url):
        return {
            "urls": [
                {"filename": manifest["python"]["wheel"]["filename"], "digests": {"sha256": "f" * 64}},
                {"filename": "unexpected.whl", "digests": {"sha256": "e" * 64}},
            ]
        }

    assert pub.inspect_pypi(manifest, fetch=conflict)["status"] == pub.CONFLICT


def test_pypi_unavailable_is_unknown_not_absent():
    def broken(_url):
        raise TimeoutError("network unavailable")

    report = pub.inspect_pypi(_manifest(), fetch=broken)
    assert report["status"] == pub.UNKNOWN


def test_registry_digest_classification_is_fail_closed():
    digest = "sha256:" + "a" * 64
    assert pub.classify_digest(None, digest) == pub.ABSENT
    assert pub.classify_digest(digest, digest) == pub.MATCH
    assert pub.classify_digest("sha256:" + "b" * 64, digest) == pub.CONFLICT


def test_v1_aliases_are_exactly_minor_major_latest():
    assert pub.aliases_for("1.0.0") == ["1.0", "1", "latest"]
