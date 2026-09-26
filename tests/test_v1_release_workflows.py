from __future__ import annotations

import re
from pathlib import Path

import yaml

from tools.v1_evidence_pack import scope_reason

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / '.github' / 'workflows'


def read(name):
    return (WF / name).read_text(encoding='utf-8')


def refs(text):
    return re.findall(r'(?m)^\s*-\s*uses:\s*[^\s@]+@([^\s#]+)', text)


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
    assert 'PYPI_PRO_PUBLISHER_SETUP_WINDOW: 240 seconds' in text
    assert "if: steps.state.outputs.bootstrap_probe == 'true'" in text
    assert 'sleep 240' in text
    assert '::notice title=PyPI Pro setup window::' in text
    assert 'EXPECTED BOOTSTRAP STOP' not in text
    assert 'SAME candidate_run_id' in text
    assert 'voice-stt-server-pro' in text
    assert 'id-token: write' in text


def test_publish_order_free_pro_dockerhub_ghcr_aliases_verify_tag_release():
    text = read('release-publish.yml')
    positions = [
        text.index('  pypi-free:'),
        text.index('  pypi-pro:'),
        text.index('  dockerhub:'),
        text.index('  ghcr:'),
        text.index('  aliases:'),
        text.index('  pre-tag-verify:'),
        text.index('  tag:'),
        text.index('  github-release:'),
    ]
    assert positions == sorted(positions)
    assert text.index('Verify both Free wheels MATCH') < text.index('sleep 240') < text.index('  pypi-pro:')
    assert "needs: [preflight, pypi-pro]" in text
    assert "needs: [preflight, dockerhub]" in text
    assert "needs: [preflight, ghcr]" in text
    assert "needs: [preflight, aliases]" in text
    assert "needs: [preflight, pre-tag-verify]" in text
    assert "needs: [preflight, tag]" in text
    assert text.index('Confirm candidate, four PyPI wheels, and all image digests') < text.index('git tag -a')
    for tag in ('1.0.0', '1.0', '1', 'latest'):
        assert tag in text
    assert 'GitHub Release last + final verification' in text


def test_publish_dependency_graph_guards_all_external_writes_before_git_tag():
    jobs = yaml.safe_load(read('release-publish.yml'))['jobs']

    def ancestors(job):
        needs = jobs[job].get('needs', [])
        if isinstance(needs, str):
            needs = [needs]
        return set(needs).union(*(ancestors(parent) for parent in needs))

    required_chain = (
        'pypi-free', 'pypi-pro', 'dockerhub', 'ghcr', 'aliases',
        'pre-tag-verify', 'tag', 'github-release',
    )
    for earlier, later in zip(required_chain, required_chain[1:]):
        assert earlier in ancestors(later), (earlier, later)
    assert 'registry-preflight' in ancestors('pypi-free')
    registry_preflight = jobs['registry-preflight']
    assert registry_preflight['environment'] == 'release'
    assert sum('docker/login-action@' in step.get('uses', '') for step in registry_preflight['steps']) == 2
    assert any('v1_dockerhub_scope_check.py' in step.get('run', '') for step in registry_preflight['steps'])
    assert 'v1_registry_probe.py' in registry_preflight['steps'][-1]['run']
    assert '--require-match' in registry_preflight['steps'][-1]['run']
    assert 'tag' not in ancestors('pypi-free')
    preflight = jobs['preflight']['steps']
    tag_guard = next(
        step for step in preflight
        if step.get('name') == 'Reject a conflicting Git tag before any publication'
    )['run']
    assert 'git rev-list -n1 "$TAG"' in tag_guard
    assert "git rev-parse 'HEAD^{tree}'" in tag_guard
    assert 'CONFLICT' in tag_guard
    assert any(
        'release-state --tag "$TAG"' in step.get('run', '')
        for step in preflight
    )
    pause = next(
        step for step in jobs['pypi-free']['steps']
        if 'sleep 240' in step.get('run', '')
    )
    assert pause['if'] == "steps.state.outputs.bootstrap_probe == 'true'"
    verify = next(
        step for step in jobs['pre-tag-verify']['steps']
        if 'Confirm candidate, four PyPI wheels' in step.get('name', '')
    )['run']
    assert '--variant free' in verify and '--variant pro' in verify
    assert 'docker.io/' in verify and 'ghcr.io/' in verify
    assert 'for tag in 1.0.0 1.0 1 latest' in verify


def test_existing_github_release_resumes_only_with_identical_assets():
    jobs = yaml.safe_load(read('release-publish.yml'))['jobs']
    step = next(
        step for step in jobs['github-release']['steps']
        if step.get('name') == 'Create/resume release from exact hashed assets'
    )
    script = step['run']
    assert 'git fetch origin --tags' in script
    assert 'git rev-list -n1 "$TAG"' in script
    assert 'gh release download "$TAG"' in script
    assert 'gh release upload "$TAG" "$f"' in script
    assert 'cmp -s "$f" "$verify_dir/$name"' in script
    assert 'release-state --tag "$TAG"' in script
    assert 'gh release create "$TAG" "${assets[@]}" --verify-tag' in script
    assert '--clobber' not in script
    assert '|| true' not in script


def test_registry_writes_stop_on_unknown_and_verify_each_digest():
    jobs = yaml.safe_load(read('release-publish.yml'))['jobs']
    for job_name in ('dockerhub', 'ghcr', 'aliases'):
        script = '\n'.join(step.get('run', '') for step in jobs[job_name]['steps'])
        assert 'v1_registry_probe.py' in script
        assert '--require-match' in script
        assert '|| true' not in script
        assert '2>/dev/null' not in script
    assert '|| true' not in read('release-publish.yml')


def test_build_validation_is_real_native_linux_windows_and_evidence_pack():
    text = read('v1-release-build-validation.yml')
    assert 'review/v1-release-prep-correction-1' in text
    assert 'release/v1.0.0-prep' in text
    assert 'review/v1-release-prep-final-clean*' in text
    assert 'branch=$branch_q' in text
    assert 'urllib.parse.quote' in text
    assert 'linux_x86_64' in text and 'win_amd64' in text
    assert 'windows-latest' in text
    assert 'python tools/v1_kroko_release.py build' in text
    assert 'docker version' in text
    assert 'python tools/v1_product_wheel.py build' in text
    assert 'pip install "$wheel"' in text
    assert '& $stt --help' in text
    assert text.count('selector_env_absent=true') == 2
    assert text.count('v1-clean-install-${{ matrix.variant }}') == 2
    assert text.count("print('package='+VoiceSTT.__file__)") == 2
    assert text.count('not in VoiceSTT.__file__') == 2
    assert 'Remove-Item Env:KROKO_API_KEY' in text
    assert 'unset VOICESTT_KROKO_VARIANT KROKO_API_KEY' in text
    assert 'build/v1-release.Dockerfile' in text
    assert 'v1-correction-1-evidence' in text


def test_preparation_ci_runs_on_current_release_preparation_branch():
    text = read('v1-release-prep-ci.yml')
    assert "- 'release/v1.0.0-prep'" in text
    assert 'review/v1-release-prep-*|release/v1.0.0-prep' in text


def test_clean_history_plan_keeps_main_and_v2_behind_separate_gates():
    from tools.v1_evidence_pack import BASE, scope_reason

    plan = (ROOT / 'docs' / 'v1-release-final-plan.md').read_text(encoding='utf-8')
    assert BASE == '13c162950b944dc715fdd81983a7465f8eb0fd79'
    assert '18 Arbeitscommits' in plan
    assert 'TREE(Main nach V2-Merge) == TREE(final qualifizierter V2 Canonical)' in plan
    index = (ROOT / 'docs' / 'README.md').read_text(encoding='utf-8')
    assert 'v1-release-final-plan.md' in index
    assert 'v1-v2-history-transition.md' in index
    transition = (ROOT / 'docs' / 'v1-v2-history-transition.md').read_text(encoding='utf-8')
    assert 'TREE(Main nach V2-Merge) == TREE(final qualifizierter V2 Canonical)' in transition
    for path in ('VERSION', 'build/v1-kroko-builder.Dockerfile', 'tools/check_v1_release_package.py'):
        assert scope_reason(path)


def test_all_third_party_actions_are_full_sha_pinned():
    for name in (
        'v1-release-prep-ci.yml',
        'v1-release-build-validation.yml',
        'release-candidate.yml',
        'release-publish.yml',
        'v1-release-infrastructure-preflight.yml',
    ):
        values = refs(read(name))
        assert values, name
        for value in values:
            assert re.fullmatch(r'[0-9a-f]{40}', value), (name, value)


def test_manual_infrastructure_check_uses_release_secret_without_publish_write():
    text = read('v1-release-infrastructure-preflight.yml')
    jobs = yaml.safe_load(text)['jobs']
    assert 'workflow_dispatch:' in text and re.search(r'(?m)^\s{2}push:\s*$', text) is None
    assert len(jobs) == 1
    step = jobs['dockerhub-scope']['steps'][-1]
    assert jobs['dockerhub-scope']['environment'] == 'release'
    assert 'secrets.DOCKERHUB_TOKEN' in step['env']['DOCKERHUB_TOKEN']
    assert step['run'] == 'python tools/v1_dockerhub_scope_check.py'
    assert 'docker push' not in text and 'imagetools create' not in text


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


def test_evidence_scope_maps_native_kroko_installer():
    reason = scope_reason('VoiceSTT/install_kroko.py')
    assert 'Kroko' in reason
    assert 'native' in reason


def test_final_release_plan_is_mandatory_checksums_and_scope_mapped():
    from tools.v1_evidence_pack import EVIDENCE_SOURCES, MANDATORY

    assert '27_release_plan.md' in MANDATORY
    assert '27_release_plan.md' in EVIDENCE_SOURCES
    plan = ROOT / 'docs/v1-release-final-plan.md'
    content = plan.read_text(encoding='utf-8')
    assert '240-Sekunden-Fenster' in content
    assert 'workflow_dispatch' in content and 'Default-Branch' in content
    assert content.index('**PyPI Free:**') < content.index('**Docker Hub exact:**')
    assert content.index('**Docker Hub exact:**') < content.index('**GHCR exact:**')
    assert content.index('**Pre-Tag-Gate:**') < content.index('**GitHub Release zuletzt:**')
    assert 'release-facing' in scope_reason('docs/v1-release-final-plan.md')
    assert 'Wake Word' in scope_reason('VoiceSTT/assets/wakeword_models/Jarvis.onnx')


def test_dockerfile_consumes_only_final_product_wheel():
    text = (ROOT / 'build' / 'v1-release.Dockerfile').read_text(encoding='utf-8')
    assert 'COPY release-inputs/python/*.whl' in text
    assert 'release-inputs/kroko' not in text
    assert 'pip install /tmp/kroko' not in text
    assert 'stt-install-kroko --build' not in text


def test_cpu_only_torch_bootstrap_precedes_wheel_install():
    cpu_index = 'https://download.pytorch.org/whl/cpu'

    dockerfile = (ROOT / 'build' / 'v1-release.Dockerfile').read_text(encoding='utf-8')
    assert dockerfile.count(cpu_index) == 1
    assert "'torch==2.9.1+cpu'" in dockerfile
    assert "'torchaudio==2.9.1+cpu'" in dockerfile
    assert dockerfile.index(cpu_index) < dockerfile.index('python -m pip install "/tmp/voicestt/$(basename')
    assert 'CPU_ONLY_OK=true' in dockerfile

    build_validation = read('v1-release-build-validation.yml')
    assert build_validation.count(cpu_index) == 2
    assert build_validation.index(cpu_index) < build_validation.index('pip install "$wheel"')
    assert build_validation.rindex(cpu_index) < build_validation.index('pip install $wheel')
    assert build_validation.count('CPU_ONLY_OK=true') == 2

    candidate = read('release-candidate.yml')
    assert candidate.count(cpu_index) == 2
    assert candidate.index(cpu_index) < candidate.index('pip install product/*.whl')
    assert candidate.rindex(cpu_index) < candidate.index('pip install $wheel')
    assert candidate.count('CPU_ONLY_OK=true') == 2
