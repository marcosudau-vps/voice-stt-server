from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / '.github' / 'workflows'


def read(name):
    return (WF / name).read_text(encoding='utf-8')


def refs(text):
    return re.findall(r'(?m)^\s*uses:\s*[^\s@]+@([^\s#]+)', text)


def test_candidate_manual_only_four_product_matrix_no_sdist():
    text = read('release-candidate.yml')
    assert 'workflow_dispatch:' in text and re.search(r'(?m)^\s{2}push:\s*$', text) is None
    assert 'platform: [linux_x86_64, win_amd64]' in text
    assert 'variant: [free, pro]' in text
    assert 'candidate-product-${{ matrix.variant }}-${{ matrix.platform }}' in text
    assert '--sdist' not in text and '*.tar.gz' in text  # negative guard only
    assert 'py3-none-any' in text  # negative guard only
    assert 'windows-latest' in text and 'kroko_onnx' in text
    assert 'name: v1-release-candidate' in text
    assert 'pypa/gh-action-pypi-publish' not in text
    assert 'git tag' not in text and 'gh release create' not in text


def test_publish_manual_protected_rebuild_free_two_projects_and_bootstrap():
    text = read('release-publish.yml')
    assert 'workflow_dispatch:' in text and re.search(r'(?m)^\s{2}push:\s*$', text) is None
    assert text.count('environment: release') >= 7
    assert 'python -m build' not in text
    assert re.search(r'(?m)^\s*docker build(?:\s|\\)', text) is None
    assert text.count('pypa/gh-action-pypi-publish@') == 2
    assert '--variant free' in text and '--variant pro' in text
    assert 'PYPI_PRO_PUBLISHER_SETUP_REQUIRED' in text
    assert 'EXPECTED BOOTSTRAP STOP' in text
    assert 'voice-stt-server-pro' in text
    assert 'id-token: write' in text


def test_publish_order_tag_free_pro_dockerhub_ghcr_aliases_release():
    text = read('release-publish.yml')
    positions = [
        text.index('  tag:'),
        text.index('  pypi-free:'),
        text.index('  pypi-pro:'),
        text.index('  dockerhub:'),
        text.index('  ghcr:'),
        text.index('  aliases:'),
        text.index('  github-release:'),
    ]
    assert positions == sorted(positions)
    assert 'GitHub Release last + final verification' in text


def test_build_validation_is_real_native_linux_windows_and_evidence_pack():
    text = read('v1-release-build-validation.yml')
    assert 'review/v1-release-prep-correction-1' in text
    assert 'linux_x86_64' in text and 'win_amd64' in text
    assert 'windows-latest' in text
    assert 'python tools/v1_kroko_release.py build' in text
    assert 'python tools/v1_product_wheel.py build' in text
    assert 'pip install product/*.whl' in text
    assert 'stt-server.exe --help' in text
    assert 'build/v1-release.Dockerfile' in text
    assert 'v1-correction-1-evidence' in text


def test_all_third_party_actions_are_full_sha_pinned():
    for name in (
        'v1-release-prep-ci.yml',
        'v1-release-build-validation.yml',
        'release-candidate.yml',
        'release-publish.yml',
    ):
        values = refs(read(name))
        assert values, name
        for value in values:
            assert re.fullmatch(r'[0-9a-f]{40}', value), (name, value)


def test_release_authority_does_not_depend_on_vps_or_operator_paths():
    combined = '\n'.join(
        read(x)
        for x in (
            'v1-release-build-validation.yml',
            'release-candidate.yml',
            'release-publish.yml',
        )
    )
    assert 'build/vps' not in combined
    assert re.search(r'[A-Za-z]:\\', combined) is None


def test_dockerfile_consumes_only_final_product_wheel():
    text = (ROOT / 'build' / 'v1-release.Dockerfile').read_text(encoding='utf-8')
    assert 'COPY release-inputs/python/*.whl' in text
    assert 'release-inputs/kroko' not in text
    assert 'pip install /tmp/kroko' not in text
    assert 'stt-install-kroko --build' not in text
