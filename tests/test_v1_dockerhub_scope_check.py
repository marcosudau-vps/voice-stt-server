from __future__ import annotations

import base64
import json
from unittest.mock import patch

from tools import v1_dockerhub_scope_check as scope


def token(repository: str, actions: list[str]) -> str:
    payload = {"access": [{"type": "repository", "name": repository, "actions": actions}]}
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"header.{encoded}.signature"


class Response:
    def __init__(self, value: str):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, *_):
        return json.dumps({"token": self.value}).encode()


def test_requests_scope_with_basic_auth_and_reads_grants_only():
    with patch.object(scope, "urlopen", return_value=Response(token("marcosudau/voice-stt-server", ["pull", "push"]))) as urlopen:
        assert scope.granted_actions("marcosudau", "test-secret", "voice-stt-server") == {"pull", "push"}
    request = urlopen.call_args.args[0]
    assert "scope=repository%3Amarcosudau%2Fvoice-stt-server%3Apull%2Cpush" in request.full_url
    assert request.get_header("Authorization") == "Basic " + base64.b64encode(b"marcosudau:test-secret").decode()


def test_token_for_other_repository_does_not_prove_scope():
    with patch.object(scope, "urlopen", return_value=Response(token("someone/else", ["pull", "push"]))):
        assert scope.granted_actions("marcosudau", "test-secret", "voice-stt-server") == set()


def test_main_rejects_pull_only_without_printing_secret(capsys):
    with patch.dict(scope.os.environ, {"DOCKERHUB_USERNAME": "marcosudau", "DOCKERHUB_TOKEN": "test-secret"}):
        with patch.object(scope, "granted_actions", return_value={"pull"}):
            assert scope.main() == 2
    output = capsys.readouterr()
    assert "lacks pull/push" in output.err
    assert "test-secret" not in output.err


def test_main_requires_both_repositories(capsys):
    with patch.dict(scope.os.environ, {"DOCKERHUB_USERNAME": "marcosudau", "DOCKERHUB_TOKEN": "test-secret"}):
        with patch.object(scope, "granted_actions", side_effect=[{"pull", "push"}, {"pull", "push"}]) as granted:
            assert scope.main() == 0
    assert [call.args[2] for call in granted.call_args_list] == list(scope.IMAGES)
    assert "test-secret" not in capsys.readouterr().out


def test_opaque_token_is_unverified():
    try:
        scope._jwt_claims("opaque")
    except ValueError as exc:
        assert "opaque" in str(exc)
    else:
        raise AssertionError("opaque token was incorrectly trusted")
