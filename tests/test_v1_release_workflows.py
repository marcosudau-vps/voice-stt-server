from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def _read(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def _action_refs(text: str):
    return re.findall(r"(?m)^\s*uses:\s*[^\s@]+@([^\s#]+)", text)


def test_candidate_is_manual_only_and_never_targets_public_release_surfaces():
    text = _read("release-candidate.yml")
    assert "workflow_dispatch:" in text
    assert re.search(r"(?m)^\s{2}push:\s*$", text) is None
    assert "staging_private_confirmed" in text
    assert "-v1-staging" in text
    assert "pypa/gh-action-pypi-publish" not in text
    assert "docker.io/" not in text
    assert "git tag" not in text
    assert "gh release create" not in text
    assert "name: v1-release-candidate" in text


def test_publish_is_manual_only_protected_and_rebuild_free():
    text = _read("release-publish.yml")
    assert "workflow_dispatch:" in text
    assert re.search(r"(?m)^\s{2}push:\s*$", text) is None
    assert text.count("environment: release") >= 6
    assert "name: v1-release-candidate" in text
    assert "merge-multiple" not in text
    assert "python -m build" not in text
    assert re.search(r"(?m)^\s*docker build(?:\s|\\)", text) is None
    assert text.count("pypa/gh-action-pypi-publish@") == 1
    assert "packages-dir: upload" in text
    assert "id-token: write" in text
    assert "voice-stt-server-pro to PyPI" not in text


def test_publish_order_is_tag_pypi_dockerhub_ghcr_aliases_github_release():
    text = _read("release-publish.yml")
    positions = [
        text.index("  tag:"),
        text.index("  pypi:"),
        text.index("  dockerhub:"),
        text.index("  ghcr:"),
        text.index("  aliases:"),
        text.index("  github-release:"),
    ]
    assert positions == sorted(positions)
    assert "GitHub Release last + final verification" in text


def test_all_third_party_actions_are_pinned_to_full_commit_shas():
    for name in ("v1-release-prep-ci.yml", "release-candidate.yml", "release-publish.yml"):
        refs = _action_refs(_read(name))
        assert refs, name
        for ref in refs:
            assert re.fullmatch(r"[0-9a-f]{40}", ref), (name, ref)


def test_release_authority_has_no_operator_local_or_vps_dependency():
    combined = "\n".join(
        [
            _read("release-candidate.yml"),
            _read("release-publish.yml"),
            (ROOT / "build" / "v1-release.Dockerfile").read_text(encoding="utf-8"),
            (ROOT / "build" / "v1-kroko-builder.Dockerfile").read_text(encoding="utf-8"),
        ]
    )
    assert "build/vps" not in combined
    assert re.search(r"[A-Za-z]:\\", combined) is None


def test_publish_uses_same_candidate_digest_for_dockerhub_and_ghcr():
    text = _read("release-publish.yml")
    assert 'source="docker.io/${DOCKERHUB_USERNAME}/${image}@${expected}"' in text
    assert 'docker buildx imagetools create --tag "$final" "$source"' in text
    assert 'test "$(inspect_digest "$final")" = "$expected"' in text
