"""Verified atomic installations in administrator-owned model directories.

External discovery roots are never passed to this component. Reparse points,
hardlinks and unsafe names are refused before mutation, including cleanup.
"""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import urllib.parse
import urllib.request
import uuid

from .downloads import ModelManagementError


@dataclass(frozen=True)
class ArtifactFile:
    path: str
    sha256: str
    bytes: int

    def __post_init__(self):
        safe_name(self.path)
        if (not re.fullmatch(r"[0-9a-f]{64}", self.sha256)
                or type(self.bytes) is not int or self.bytes <= 0):
            raise ValueError("invalid immutable file identity")


def safe_name(name):
    # Single-level names deliberately keep directory traversal, NTFS ADS and
    # case/trailing-dot/device-name aliases out of installation manifests.
    if (not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name)
            or name.endswith((".", " ")) or name in {".", ".."}
            or re.fullmatch(r"(?i)(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\..*)?", name)):
        raise ModelManagementError("unsafe_installation_name", 422)
    return name


def _signature(path):
    info = path.lstat()
    if (stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & 0x400
            or (stat.S_ISREG(info.st_mode) and info.st_nlink != 1)):
        raise ModelManagementError("unsafe_storage_link", 409)
    if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
        raise ModelManagementError("unsafe_storage_type", 409)
    return info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode)


def check_path(path):
    """Check every existing lexical ancestor before resolving or creating it."""
    path = Path(os.path.abspath(path))
    for item in [*reversed(path.parents), path]:
        if item.exists() or item.is_symlink():
            _signature(item)
    return path


def tree_signature(path):
    entries = {".": _signature(path)}
    if path.is_dir():
        for parent, dirs, files in os.walk(path, followlinks=False):
            for name in dirs + files:
                item = Path(parent) / name
                entries[str(item.relative_to(path))] = _signature(item)
    return entries


# Exact HTTPS file/CDN hosts from the provider's documented download surface:
# https://huggingface.co/docs/hub/models-downloading#downloading-behind-a-proxy-or-firewall
# No suffix wildcard and no dynamic expansion from an untrusted redirect.
_CDN_HOSTS = frozenset({"huggingface.co", "us.aws.cdn.hf.co", "us.gcp.cdn.hf.co",
                        "cdn-lfs-us-1.hf.co", "cdn-lfs-eu-1.hf.co"})


def _safe_url(url):
    try:
        parsed = urllib.parse.urlsplit(url)
        allowed = (parsed.scheme == "https" and parsed.hostname in _CDN_HOSTS
                   and not parsed.username and not parsed.password
                   and parsed.port in {None, 443} and not parsed.fragment
                   and not any(ord(c) <= 32 or ord(c) >= 127 for c in url)
                   and "\\" not in url)
    except ValueError:
        allowed = False
    if not allowed:
        raise ModelManagementError("download_source_rejected", 422)


class _Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _safe_url(newurl)  # before a second network contact, not after download
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_file(source, destination, expected_bytes, progress):
    _safe_url(source)
    opener = urllib.request.build_opener(_Redirects())
    count = 0
    # No credentials, cookies, cache, Range or exception text cross this port.
    with opener.open(source, timeout=30) as response, destination.open("xb") as output:
        _safe_url(response.geturl())
        while chunk := response.read(1024 * 1024):
            count += len(chunk)
            if count > expected_bytes:
                raise ModelManagementError("download_size_mismatch", 422)
            output.write(chunk)
            progress(count)
        output.flush()
        os.fsync(output.fileno())
    return source


def verified_file(path, digest, size):
    _signature(path)
    if not path.is_file() or path.stat().st_size != size:
        return False
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest().lower() == digest.lower()


class VerifiedModelStorage:
    def __init__(self, mutation_lock, *, fetcher=None):
        self._lock = mutation_lock
        self._fetcher = fetcher

    def install(self, product, root, transition, progress, gate):
        safe_name(product.filename)
        root = check_path(root)
        root.mkdir(parents=True, exist_ok=True)
        check_path(root)
        root_identity = _signature(root)
        target = root / product.filename
        staging = root / f".{product.filename}.{uuid.uuid4().hex}.part"
        directory = product.artifact_kind == "directory"
        files = product.files if directory else (
            ArtifactFile(product.filename, str(product.sha256).lower(), product.bytes),)
        try:
            with self._lock:
                check_path(target)
                if target.exists():
                    raise ModelManagementError("installation_already_exists", 409)
                if directory:
                    staging.mkdir()
            transferred = 0
            for item in files:
                path = staging / item.path if directory else staging
                source = product.source.rstrip("/") + "/" + item.path if directory else product.source
                if self._fetcher is None:
                    observed = download_file(source, path, item.bytes,
                                             lambda count: progress(transferred + count))
                else:
                    observed = self._fetcher(source, path)
                    progress(transferred + path.stat().st_size)
                expected = source if directory else (product.source_identity or product.source)
                if observed != expected:
                    raise ModelManagementError("download_source_mismatch", 422)
                transferred += item.bytes
            transition("verifying")
            for item in files:
                path = staging / item.path if directory else staging
                if not verified_file(path, item.sha256, item.bytes):
                    raise ModelManagementError("download_integrity_mismatch", 422)
            with self._lock:
                gate(product.id)  # current product/right/intent gates, before commit
                check_path(root)
                if _signature(root) != root_identity:
                    raise ModelManagementError("storage_changed", 409)
                check_path(target)
                if target.exists():
                    raise ModelManagementError("installation_already_exists", 409)
                tree_signature(staging)
                transition("installing")
                os.replace(staging, target)
            return target
        finally:
            if staging.exists() or staging.is_symlink():
                # Refuse unsafe trees; never follow attacker-provided leftovers.
                check_path(root)
                if _signature(root) == root_identity:
                    tree_signature(staging)
                    if directory:
                        shutil.rmtree(staging)
                    else:
                        staging.unlink()

    def cleanup(self, root):
        """Restart A: only our named partials, never completed installations."""
        with self._lock:
            root = check_path(root)
            if not root.is_dir():
                return
            for path in root.iterdir():
                if re.fullmatch(r"\.[A-Za-z0-9][A-Za-z0-9_.-]*\.[0-9a-f]{32}\.part", path.name):
                    tree_signature(path)
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()

    def delete(self, path, root, guard):
        with self._lock:
            root = check_path(root)
            path = check_path(path)
            if path.parent != root or not path.exists() or path.name.startswith("."):
                raise ModelManagementError("installation_not_managed", 409)
            guard()
            original = tree_signature(path)
            root_identity = _signature(root)
            quarantine = root / f".{path.name}.{uuid.uuid4().hex}.staging"
            os.replace(path, quarantine)
            try:
                guard()
                check_path(root)
                if _signature(root) != root_identity or tree_signature(quarantine) != original:
                    raise ModelManagementError("storage_changed", 409)
                if quarantine.is_dir():
                    shutil.rmtree(quarantine)
                else:
                    quarantine.unlink()
            except Exception:
                try:
                    check_path(root)
                    unchanged = _signature(root) == root_identity
                except (OSError, ModelManagementError):
                    unchanged = False
                if unchanged and not path.exists() and quarantine.exists():
                    os.replace(quarantine, path)
                raise
