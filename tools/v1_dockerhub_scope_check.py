"""Read-only proof that the release secret grants Docker Hub pull and push.

The registry token endpoint intersects requested and granted permissions.  We
inspect only the resulting access claims; neither credentials nor tokens are
printed, and no registry write is attempted.
"""

from __future__ import annotations

import base64
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


IMAGES = ("voice-stt-server", "voice-stt-server-pro")


def _jwt_claims(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("registry returned an opaque token; scope cannot be proved")
    payload = parts[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


def granted_actions(username: str, secret: str, image: str) -> set[str]:
    repository = f"{username}/{image}"
    query = urlencode({
        "service": "registry.docker.io",
        "scope": f"repository:{repository}:pull,push",
    })
    credential = base64.b64encode(f"{username}:{secret}".encode()).decode()
    request = Request(
        f"https://auth.docker.io/token?{query}",
        headers={"Authorization": f"Basic {credential}", "Accept": "application/json"},
    )
    with urlopen(request, timeout=30) as response:
        token = json.load(response).get("token")
    if not isinstance(token, str):
        raise ValueError("registry response has no token")
    claims = _jwt_claims(token)
    access = claims.get("access", [])
    if not isinstance(access, list):
        raise ValueError("registry token has no readable access claims")
    actions: set[str] = set()
    for entry in access:
        if isinstance(entry, dict) and entry.get("type") == "repository" and entry.get("name") == repository:
            values = entry.get("actions", [])
            if isinstance(values, list):
                actions.update(x for x in values if isinstance(x, str))
    return actions


def main() -> int:
    username = os.environ.get("DOCKERHUB_USERNAME", "").strip()
    secret = os.environ.get("DOCKERHUB_TOKEN", "")
    if not username or not secret:
        print("Docker Hub scope check: username or token missing", file=sys.stderr)
        return 2
    for image in IMAGES:
        try:
            actions = granted_actions(username, secret, image)
        except (HTTPError, URLError, OSError, ValueError, KeyError, TypeError):
            print(f"Docker Hub scope check: {username}/{image} unverified", file=sys.stderr)
            return 2
        if not {"pull", "push"} <= actions:
            print(f"Docker Hub scope check: {username}/{image} lacks pull/push", file=sys.stderr)
            return 2
        print(f"Docker Hub scope check: {username}/{image} pull/push confirmed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
