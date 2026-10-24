"""Offline, versioned source metadata. No runtime metadata/network discovery."""
import hashlib
import json
from pathlib import Path
import re

from .storage import ArtifactFile, safe_name


def faster_whisper_sources():
    payload = json.loads(Path(__file__).with_name("faster_whisper_manifest.json").read_text(encoding="utf-8"))
    if payload["schemaVersion"] != 1:
        raise ValueError("unsupported model source manifest")
    result = {}
    for item in payload["models"]:
        name = item["modelId"]
        safe_name(name)
        if (not re.fullmatch(r"[0-9a-f]{40}", item["revision"])
                or item["repository"] != "Systran/" + name or item["license"] != "mit"):
            raise ValueError("unqualified model source")
        files = tuple(ArtifactFile(**file) for file in item["files"])
        paths = {file.path for file in files}
        if len(paths) != len(files) or not {"config.json", "model.bin", "tokenizer.json"} <= paths:
            raise ValueError("incomplete model file manifest")
        canonical = json.dumps(item["files"], sort_keys=True, separators=(",", ":")).encode()
        result[name] = {
            "revision": item["revision"], "filename": name, "files": files,
            "sha256": hashlib.sha256(canonical).hexdigest(),
            "bytes": sum(file.bytes for file in files),
            "source": "https://huggingface.co/" + item["repository"] + "/resolve/" + item["revision"],
            "provisioning_allowed": True, "rights_status": "UPSTREAM_MIT_PINNED",
        }
    return result


def kroko_catalog():
    from VoiceSTT.kroko.catalog import KrokoCatalog
    return KrokoCatalog.from_payload(json.loads(
        Path(__file__).with_name("kroko_catalog.json").read_text(encoding="utf-8")))
