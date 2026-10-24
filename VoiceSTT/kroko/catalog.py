"""Offline Kroko discovery metadata. Never an integrity or license authority.

Only the cleaned probe-v1 schema is accepted. Unknown fields are rejected,
not retained in a raw payload, to keep portal credentials out of objects,
diagnostics and CLI output. No function in this module contacts the network.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Protocol
from urllib.parse import urlsplit
from uuid import UUID

from .models import KrokoModelManifest, load_manifest

Edition = Literal["Community", "Pro"]
ModelSize = Literal["S", "M", "L"]
SCHEMA = "kroko-catalog-probe-v1"
NOTE = "Catalog only; NOT a license/entitlement proof"
MAX_CATALOG_BYTES = 4 * 1024 * 1024
_NAME = re.compile(
    r"Kroko-(?P<language>[A-Z]{2,5})-(?P<edition>Community|Pro)-"
    r"(?P<chunk>[1-9][0-9]{0,5})-(?P<size>S|M|L)-"
    r"(?P<mode>Streaming)-(?P<revision>[0-9]{3})\.data", re.ASCII
)
_REQUIRED = frozenset({
    "model_id", "name", "language", "edition", "chunk", "size", "mode", "revision",
})
_OPTIONAL = frozenset({"download_url", "source", "parse_ok"})


@dataclass(frozen=True)
class CatalogDiagnostic:
    """Safe location/code/message: never contains untrusted field values."""

    index: int | None
    code: str
    message: str


class CatalogValidationError(ValueError):
    def __init__(self, diagnostics: tuple[CatalogDiagnostic, ...]):
        self.diagnostics = diagnostics
        super().__init__("; ".join(
            f"entry {d.index if d.index is not None else 'root'}: {d.code}: {d.message}"
            for d in diagnostics
        ))


def _fail(code: str, message: str) -> None:
    raise CatalogValidationError((CatalogDiagnostic(None, code, message),))


def validate_download_url(url: object, filename: str) -> str | None:
    """Validate only syntax/source identity; this does not attest to URL safety.

    Exact hosts, paths and public query parameters only. Credentials, ports,
    encoding tricks, fragments and redirects cannot enter a download plan.
    A future downloader must separately validate each redirect before contact.
    """
    if _NAME.fullmatch(filename) is None:
        _fail("unknown_name", "download filename must be a validated Kroko model name")
    if url is None:
        return None
    if not isinstance(url, str) or not url or any(ord(c) <= 32 or ord(c) >= 127 for c in url):
        _fail("invalid_url", "download_url must be a public HTTPS model URL or null")
    try:
        parts = urlsplit(url)
    except ValueError:
        _fail("invalid_url", "download_url cannot be parsed")
    if (
        parts.scheme != "https"
        or parts.netloc not in {"huggingface.co", "download.kroko.ai"}
        or parts.fragment or "#" in url or "%" in url or "\\" in url
    ):
        _fail("invalid_url", "download_url has a forbidden origin or URL component")
    if parts.netloc == "download.kroko.ai":
        valid = parts.path == f"/models/{filename}" and "?" not in url
    else:
        valid = bool(re.fullmatch(
            r"/Banafo/Kroko-ASR/resolve/(?:main|[0-9a-f]{40})/" + re.escape(filename),
            parts.path,
        )) and (parts.query == "download=true" or "?" not in url)
    if not valid:
        _fail("invalid_url", "download_url must identify this model on an allowed source path")
    return url


@dataclass(frozen=True)
class CatalogEntry:
    model_id: str
    name: str
    language: str
    edition: Edition
    chunk: int
    size: ModelSize
    mode: Literal["Streaming"]
    revision: str
    download_url: str | None = None
    source: Literal["offline-file"] | None = None
    parse_ok: bool | None = None

    @property
    def streaming(self) -> bool:
        return self.mode == "Streaming"

    def public_dict(self) -> dict[str, object]:
        return asdict(self)


def parse_entry(raw: object) -> CatalogEntry:
    """Preserve original approved values; compare every derived name component."""
    if not isinstance(raw, dict):
        _fail("invalid_entry", "model must be an object")
    if raw.keys() - (_REQUIRED | _OPTIONAL):
        _fail("unknown_fields", "unrecognized fields; supply cleaned model metadata only")
    for field in sorted(_REQUIRED):
        if field not in raw:
            _fail("missing_field", f"missing required field {field}")
    name = raw["name"]
    if not isinstance(name, str) or (match := _NAME.fullmatch(name)) is None:
        _fail("unknown_name", "name must match Kroko-LANGUAGE-EDITION-CHUNK-SIZE-Streaming-NNN.data (S/M/L)")
    model_id = raw["model_id"]
    try:
        valid_id = isinstance(model_id, str) and str(UUID(model_id)) == model_id
    except ValueError:
        valid_id = False
    if not valid_id:
        _fail("invalid_id", "model_id must be an exact canonical Kroko UUID")
    for field in ("language", "edition", "size", "mode", "revision"):
        if raw[field] != match[field]:
            _fail("metadata_conflict", f"{field} disagrees with the model name")
    if type(raw["chunk"]) is not int or raw["chunk"] != int(match["chunk"]):
        _fail("metadata_conflict", "chunk must be an integer matching the model name")
    if raw.get("source") not in (None, "offline-file"):
        _fail("invalid_metadata", "unsupported source metadata")
    if raw.get("parse_ok") is not None and raw["parse_ok"] is not True:
        _fail("invalid_metadata", "parse_ok must be true when supplied")
    return CatalogEntry(
        model_id=model_id, name=name, language=raw["language"],
        edition=raw["edition"], chunk=raw["chunk"], size=raw["size"],
        mode=raw["mode"], revision=raw["revision"],
        download_url=validate_download_url(raw.get("download_url"), name),
        source=raw.get("source"), parse_ok=raw.get("parse_ok"),
    )


def sort_entries(entries: tuple[CatalogEntry, ...]) -> tuple[CatalogEntry, ...]:
    return tuple(sorted(entries, key=lambda e: (
        e.language, e.edition, e.chunk, {"S": 0, "M": 1, "L": 2}[e.size],
        int(e.revision), e.revision, e.name, e.model_id,
    )))


@dataclass(frozen=True)
class KrokoCatalog:
    entries: tuple[CatalogEntry, ...]

    @classmethod
    def from_payload(cls, payload: object) -> KrokoCatalog:
        if not isinstance(payload, dict) or payload.keys() - {"schema", "note", "models"}:
            _fail("invalid_schema", "expected cleaned catalog object without extra fields")
        if payload.get("schema") != SCHEMA or not isinstance(payload.get("models"), list):
            _fail("invalid_schema", "expected probe-v1 schema and models array")
        if "note" in payload and payload["note"] != NOTE:
            _fail("invalid_metadata", "unsupported catalog note")
        entries: list[CatalogEntry] = []
        diagnostics: list[CatalogDiagnostic] = []
        ids: dict[str, CatalogEntry] = {}
        names: dict[str, CatalogEntry] = {}
        urls: dict[str, str] = {}
        for index, raw in enumerate(payload["models"]):
            try:
                entry = parse_entry(raw)
                previous = ids.get(entry.model_id)
                if previous is not None:
                    if previous.download_url != entry.download_url:
                        _fail("url_conflict", "same model_id has conflicting download URLs")
                    _fail("duplicate_id" if previous == entry else "id_conflict",
                          "model_id must identify exactly one catalog entry")
                if entry.name in names:
                    _fail("name_conflict", "same model name is assigned to different model IDs")
                if entry.download_url is not None and entry.download_url in urls:
                    _fail("url_conflict", "download URL is assigned to different model IDs")
                ids[entry.model_id] = entry
                names[entry.name] = entry
                if entry.download_url is not None:
                    urls[entry.download_url] = entry.model_id
                entries.append(entry)
            except CatalogValidationError as exc:
                diagnostics.extend(CatalogDiagnostic(index, d.code, d.message) for d in exc.diagnostics)
        if diagnostics:
            raise CatalogValidationError(tuple(diagnostics))
        return cls(sort_entries(tuple(entries)))

    @property
    def languages(self) -> tuple[str, ...]:
        return tuple(sorted({e.language for e in self.entries}))

    def get(self, model_id: str) -> CatalogEntry | None:
        """Exact portal-ID lookup only; no filename/path/manifest-ID coercion."""
        return next((e for e in self.entries if e.model_id == model_id), None)

    def filter(
        self, *, language: str | None = None, edition: Edition | None = None,
        chunk: int | None = None, size: ModelSize | None = None,
        streaming: bool | None = None,
    ) -> tuple[CatalogEntry, ...]:
        return sort_entries(tuple(e for e in self.entries if (
            (language is None or e.language == language)
            and (edition is None or e.edition == edition)
            and (chunk is None or e.chunk == chunk)
            and (size is None or e.size == size)
            and (streaming is None or e.streaming == streaming)
        )))

    def summary(self) -> dict[str, object]:
        return {
            "total": len(self.entries), "languages": self.languages,
            "editions": dict(sorted(Counter(e.edition for e in self.entries).items())),
            "sizes": dict(sorted(Counter(e.size for e in self.entries).items())),
        }


class CatalogSource(Protocol):
    """Future verified adapters must return this same strictly validated catalog."""

    def load(self) -> KrokoCatalog: ...


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate_field", "JSON object contains a repeated field")
        result[key] = value
    return result


@dataclass(frozen=True)
class OfflineCatalogSource:
    path: Path

    def load(self) -> KrokoCatalog:
        try:
            with self.path.open("rb") as handle:
                data = handle.read(MAX_CATALOG_BYTES + 1)
            if len(data) > MAX_CATALOG_BYTES:
                _fail("catalog_too_large", "catalog exceeds 4 MiB")
            payload = json.loads(data.decode("utf-8-sig"), object_pairs_hook=_unique_object)
        except (OSError, UnicodeError, json.JSONDecodeError, RecursionError):
            # Do not echo a path, JSON excerpt, URL, secret or chained exception.
            raise CatalogValidationError((CatalogDiagnostic(
                None, "unreadable_catalog", "cannot read a valid UTF-8 JSON catalog",
            ),)) from None
        return KrokoCatalog.from_payload(payload)


def load_catalog(path: str | Path) -> KrokoCatalog:
    return OfflineCatalogSource(Path(path)).load()


@dataclass(frozen=True)
class DownloadPlan:
    model_id: str
    expected_name: str
    local_filename: str
    catalog_source: str | None
    download_source: str | None
    manifest_model_id: str | None
    expected_sha256: str | None
    expected_bytes: int | None
    integrity_evidence: Literal["manifest", "missing"]
    catalog_visible: bool
    download_url_present: bool
    technical_access: Literal["not_checked"]
    download_integrity_verified: bool
    manifest_automatic_install_allowed: bool
    product_license_activation: Literal["not_checked"]
    automatic_provisioning_ready: bool
    blockers: tuple[str, ...]

    def public_dict(self) -> dict[str, object]:
        return asdict(self)


def create_download_plan(
    entry: CatalogEntry, *, manifest: KrokoModelManifest | None = None,
) -> DownloadPlan:
    """Prepare metadata only; no I/O beyond loading the existing local manifest.

    The manifest gate describes product facts, not operator intent or runtime
    permission. No API in this module can install or activate a model.
    """
    entry = parse_entry(entry.public_dict())
    manifest = manifest if manifest is not None else load_manifest()
    matches = tuple(e for e in manifest.entries if e.filename == entry.name)
    if len(matches) > 1:
        _fail("manifest_conflict", "model filename is ambiguous in the manifest")
    trusted = matches[0] if matches else None
    if trusted and (
        trusted.language.upper() != entry.language
        or trusted.tier != entry.edition.lower()
        or trusted.requires_runtime_variant != ("pro" if entry.edition == "Pro" else "free")
    ):
        _fail("manifest_conflict", "catalog metadata disagrees with the manifest")
    integrity = bool(trusted and re.fullmatch(r"[0-9a-fA-F]{64}", trusted.sha256)
                     and type(trusted.bytes) is int and trusted.bytes > 0)
    source = entry.download_url
    authoritative_source = False
    if trusted and trusted.tier == "community":
        upstream = manifest.upstream
        revision = upstream.get("communityRevision")
        if (upstream.get("communityRepoId") == "Banafo/Kroko-ASR"
                and isinstance(revision, str) and re.fullmatch(r"[0-9a-f]{40}", revision)
                and trusted.provenance.get("kind") == "upstream-verified"
                and trusted.provenance.get("revision") == revision):
            source = validate_download_url(
                f"https://huggingface.co/Banafo/Kroko-ASR/resolve/{revision}/{entry.name}",
                entry.name,
            )
            authoritative_source = True
    manifest_allowed = bool(trusted and trusted.redistributable and integrity and authoritative_source)
    blockers = ["technical_access_not_checked", "download_bytes_not_verified",
                "operator_intent_and_runtime_not_checked", "product_license_activation_not_checked"]
    if not integrity:
        blockers.append("authoritative_integrity_missing")
    if source is None:
        blockers.append("download_source_missing")
    if not authoritative_source:
        blockers.append("immutable_authoritative_source_missing")
    if not trusted or not trusted.redistributable:
        blockers.append("manifest_product_rights_not_granted")
    return DownloadPlan(
        model_id=entry.model_id, expected_name=entry.name, local_filename=entry.name,
        catalog_source=entry.download_url, download_source=source,
        manifest_model_id=trusted.id if trusted else None,
        expected_sha256=trusted.sha256 if integrity and trusted else None,
        expected_bytes=trusted.bytes if integrity and trusted else None,
        integrity_evidence="manifest" if integrity else "missing",
        catalog_visible=True, download_url_present=source is not None,
        technical_access="not_checked", download_integrity_verified=False,
        manifest_automatic_install_allowed=manifest_allowed,
        product_license_activation="not_checked", automatic_provisioning_ready=False,
        blockers=tuple(blockers),
    )
