"""Read-only Git identity helpers for the release orchestrator.

Nothing here mutates the repository. Tag *creation* lives outside this
module entirely for W5 (see ``release_tooling.pipeline`` - the barrier
functions only check whether creating a tag would currently be allowed).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence


class GitError(RuntimeError):
    """A read-only git probe failed or returned an unusable result."""


def _run(cmd: Sequence[str], cwd: Path) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            list(cmd),
            cwd=str(cwd),
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        # git itself is not installed/on PATH - a "cannot probe" condition
        # every caller already treats the same way as a failed git command.
        raise GitError(f"could not run git ({cmd[0]!r} not found): {exc}") from exc


@dataclass(frozen=True)
class GitIdentity:
    commit: str
    tree: str
    dirty: bool
    branch: str


def resolve_identity(repo_root: Path) -> GitIdentity:
    """The exact commit/tree/branch/cleanliness of ``repo_root`` right now."""
    commit_result = _run(["git", "rev-parse", "HEAD"], repo_root)
    if commit_result.returncode != 0:
        raise GitError(f"git rev-parse HEAD failed: {commit_result.stderr.strip()}")
    commit = commit_result.stdout.strip()

    tree_result = _run(["git", "rev-parse", "HEAD^{tree}"], repo_root)
    if tree_result.returncode != 0:
        raise GitError(f"git rev-parse HEAD^{{tree}} failed: {tree_result.stderr.strip()}")
    tree = tree_result.stdout.strip()

    if len(commit) != 40 or len(tree) != 40:
        raise GitError(f"could not resolve exact 40-character commit/tree hashes: {commit!r}/{tree!r}")

    status_result = _run(["git", "status", "--porcelain"], repo_root)
    if status_result.returncode != 0:
        raise GitError(f"git status --porcelain failed: {status_result.stderr.strip()}")

    branch_result = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else ""

    return GitIdentity(
        commit=commit,
        tree=tree,
        dirty=bool(status_result.stdout.strip()),
        branch=branch,
    )


def local_tag_commit(repo_root: Path, tag: str) -> Optional[str]:
    """The commit ``tag`` points at locally, or ``None`` if it does not exist locally."""
    result = _run(["git", "rev-parse", f"refs/tags/{tag}^{{commit}}"], repo_root)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def remote_tag_commit(repo_root: Path, remote: str, tag: str) -> Optional[str]:
    """The commit ``tag`` points at on ``remote`` right now, or ``None``.

    Read-only (``git ls-remote`` never mutates anything, local or remote).
    Raises :class:`GitError` if the remote cannot be reached at all - the
    caller must not treat "could not check" the same as "confirmed absent".
    """
    result = _run(["git", "ls-remote", "--tags", remote, f"refs/tags/{tag}"], repo_root)
    if result.returncode != 0:
        raise GitError(f"git ls-remote {remote} failed: {result.stderr.strip()}")
    line = result.stdout.strip()
    if not line:
        return None
    return line.split()[0]


def create_tag(repo_root: Path, tag: str, commit: str) -> None:
    """Creates an annotated local tag ``tag`` at ``commit``. A real write -
    never called except by the real Git tag adapter's ``publish()``."""
    result = _run(["git", "tag", "-a", tag, commit, "-m", tag], repo_root)
    if result.returncode != 0:
        raise GitError(f"git tag {tag} failed: {result.stderr.strip()}")


def push_tag(repo_root: Path, remote: str, tag: str) -> None:
    """Pushes local tag ``tag`` to ``remote``. A real write - never called
    except by the real Git tag adapter's ``publish()``. Never force-pushes."""
    result = _run(["git", "push", remote, f"refs/tags/{tag}"], repo_root)
    if result.returncode != 0:
        raise GitError(f"git push {remote} refs/tags/{tag} failed: {result.stderr.strip()}")


__all__ = [
    "GitError",
    "GitIdentity",
    "resolve_identity",
    "local_tag_commit",
    "remote_tag_commit",
    "create_tag",
    "push_tag",
]
