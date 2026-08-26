"""Server metadata used by the settings v2 surface.

The commit resolution only reads the repository state; it never executes a
subprocess. When no commit can be resolved safely the wire value is
``"unknown"``, matching the v2 wire schema.
"""

from pathlib import Path

#: Matches the FastAPI application version in ``create_app``.
APP_VERSION = "2.0.0"


def resolve_server_commit() -> str:
    """Best-effort short git commit of the running checkout."""
    head = _read_head()
    if head is None:
        return "unknown"
    value = head.strip()
    if value.startswith("ref:"):
        ref_path = value[len("ref:") :].strip()
        raw = _read_file(Path(ref_path))
        if raw is not None:
            return raw.strip()[:12] or "unknown"
        return "unknown"
    if value and value != "0000000000000000000000000000000000000000":
        return value[:12]
    return "unknown"


def _git_directory() -> Path:
    git_path = Path(".git")
    if git_path.is_file():
        for line in git_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("gitdir:"):
                target = line[len("gitdir:") :].strip()
                return Path(target).resolve()
        return git_path
    return git_path


def _read_head():
    git_dir = _git_directory()
    if not git_dir.is_dir():
        return None
    return _read_file(git_dir / "HEAD")


def _read_file(path: Path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None