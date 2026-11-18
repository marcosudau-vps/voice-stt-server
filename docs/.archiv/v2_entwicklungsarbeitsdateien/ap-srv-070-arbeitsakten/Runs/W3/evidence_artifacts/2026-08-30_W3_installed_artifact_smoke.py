"""AP-SRV-070 W3-05 - installed-distribution wake smoke.

Runs against an ALREADY pip-installed voicestt distribution, from a working
directory that contains no VoiceSTT/api_fastapi_server source at all (the
container only has the installed site-packages copy on sys.path). This is
deliberate: importing the source checkout on sys.path would prove nothing
about what an end user who ran ``pip install voicestt`` actually gets.

Prints one JSON object with every checked fact so the calling shell script
can capture it as evidence without re-deriving anything.
"""

import hashlib
import json
import os
import subprocess
import sys
import traceback

RESULT = {"ok": True, "checks": {}, "errors": []}


def check(name):
    def decorator(fn):
        try:
            value = fn()
            RESULT["checks"][name] = {"ok": True, "value": value}
        except Exception as exc:  # noqa: BLE001 - smoke must report, not crash
            RESULT["ok"] = False
            RESULT["checks"][name] = {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
            }
        return fn
    return decorator


# -- source-checkout guard ---------------------------------------------------

@check("source_not_on_sys_path")
def _source_not_on_sys_path():
    import VoiceSTT

    module_path = os.path.abspath(VoiceSTT.__file__)
    forbidden = os.environ.get("SMOKE_FORBIDDEN_SOURCE_PATH", "").strip()
    if forbidden and module_path.lower().startswith(os.path.abspath(forbidden).lower()):
        raise AssertionError(
            f"VoiceSTT imported from the source checkout, not the installed "
            f"distribution: {module_path}"
        )
    if "site-packages" not in module_path.replace("\\", "/"):
        raise AssertionError(
            f"VoiceSTT was not imported from an installed site-packages copy: {module_path}"
        )
    return module_path


# -- 1/2. package import + version -------------------------------------------

@check("package_version")
def _package_version():
    import VoiceSTT

    return VoiceSTT.get_version()


@check("distribution_metadata_version")
def _distribution_metadata_version():
    from importlib import metadata

    return metadata.version("voicestt")


# -- 3. default_asset_root resolves into the installed distribution ---------

@check("asset_root_in_site_packages")
def _asset_root_in_site_packages():
    from VoiceSTT.core import wakeword_catalog

    root = wakeword_catalog.default_asset_root()
    root_str = str(root)
    if "site-packages" not in root_str.replace("\\", "/"):
        raise AssertionError(f"asset root not inside site-packages: {root_str}")
    if not root.is_dir():
        raise AssertionError(f"asset root does not exist: {root_str}")
    return root_str


# -- 4/5/6. models.json, manifest revision, 25 wake words --------------------

_SNAPSHOT = {}


@check("manifest_loads_and_validates")
def _manifest_loads_and_validates():
    from VoiceSTT.core import wakeword_catalog

    snapshot = wakeword_catalog.load_snapshot()
    _SNAPSHOT["snapshot"] = snapshot
    return {
        "catalogRevision": snapshot.catalog_revision,
        "wakeWordCount": len(snapshot.entries),
        "unmanagedArtifacts": snapshot.diagnostics.get("unmanagedArtifacts"),
    }


@check("exactly_25_public_wake_words")
def _exactly_25_public_wake_words():
    snapshot = _SNAPSHOT["snapshot"]
    if len(snapshot.entries) != 25:
        raise AssertionError(f"expected 25 wake words, found {len(snapshot.entries)}")
    return len(snapshot.entries)


# -- 7/8. onnx/tflite artifacts + pipeline for both backends -----------------

@check("every_entry_declares_both_backends")
def _every_entry_declares_both_backends():
    snapshot = _SNAPSHOT["snapshot"]
    missing = [
        entry.id for entry in snapshot.entries
        if set(entry.declared_backends) != {"onnx", "tflite"}
    ]
    if missing:
        raise AssertionError(f"entries missing a declared backend: {missing}")
    return "all 25 entries declare onnx+tflite"


@check("pipeline_declares_both_backends")
def _pipeline_declares_both_backends():
    snapshot = _SNAPSHOT["snapshot"]
    backends = set(snapshot.pipeline.backends)
    if backends != {"onnx", "tflite"}:
        raise AssertionError(f"pipeline backends: {backends}")
    if not snapshot.pipeline.files_present("onnx"):
        raise AssertionError("onnx pipeline files missing on disk")
    if not snapshot.pipeline.files_present("tflite"):
        raise AssertionError("tflite pipeline files missing on disk")
    return sorted(backends)


# -- 9. silero_vad.onnx present ----------------------------------------------

@check("silero_vad_present")
def _silero_vad_present():
    from VoiceSTT.core import wakeword_catalog

    root = wakeword_catalog.default_asset_root()
    path = root / "silero_vad.onnx"
    if not path.is_file():
        raise AssertionError(f"missing {path}")
    return {"path": str(path), "bytes": path.stat().st_size}


# -- 10. hash/byte integrity of the whole bundle -----------------------------

def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@check("bundle_hash_integrity")
def _bundle_hash_integrity():
    import json as _json

    from VoiceSTT.core import wakeword_catalog

    root = wakeword_catalog.default_asset_root()
    manifest = _json.loads((root / "models.json").read_text(encoding="utf-8"))
    checked = 0
    for entry in manifest["wakeWords"]:
        for artifact in entry["artifacts"].values():
            path = root / artifact["file"]
            digest = _sha256(path)
            if digest != artifact["sha256"]:
                raise AssertionError(f"hash mismatch for {artifact['file']}")
            if path.stat().st_size != artifact["bytes"]:
                raise AssertionError(f"size mismatch for {artifact['file']}")
            checked += 1
    for framework in manifest["pipeline"].values():
        for role in framework.values():
            path = root / role["file"]
            digest = _sha256(path)
            if digest != role["sha256"]:
                raise AssertionError(f"hash mismatch for {role['file']}")
            checked += 1
    return {"filesChecked": checked}


# -- 11. no unmanifested historical variants leaked --------------------------

@check("no_unmanifested_historical_variants_leaked")
def _no_unmanifested_historical_variants_leaked():
    from VoiceSTT.core import wakeword_catalog

    root = wakeword_catalog.default_asset_root()
    forbidden = (
        "Jarvis.onnx", "Jarvis.tflite",
        "jarvis_v1.onnx", "jarvis_v1.tflite",
        "hey_jarvis_v0.1.onnx", "hey_jarvis_v0.1.tflite",
    )
    present = [name for name in forbidden if (root / name).is_file()]
    if present:
        raise AssertionError(f"leaked unmanifested variants: {present}")
    all_files = sorted(p.name for p in root.iterdir() if p.is_file())
    return {"forbiddenChecked": list(forbidden), "installedFileCount": len(all_files)}


# -- 12. /api/v2/wake-words from the installed server ------------------------

@check("wake_words_api_from_installed_server")
def _wake_words_api_from_installed_server():
    from fastapi.testclient import TestClient

    from api_fastapi_server.server import create_app

    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/v2/wake-words")
        response.raise_for_status()
        payload = response.json()
    if len(payload["wakeWords"]) != 25:
        raise AssertionError(f"expected 25 wakeWords, got {len(payload['wakeWords'])}")
    return {
        "protocolVersion": payload["protocolVersion"],
        "catalogRevision": payload["catalogRevision"],
        "wakeWordCount": len(payload["wakeWords"]),
    }


@check("fastapi_app_version_matches_package_version")
def _fastapi_app_version_matches_package_version():
    import VoiceSTT
    from api_fastapi_server.server import create_app

    app = create_app()
    if app.version != VoiceSTT.get_version():
        raise AssertionError(f"{app.version} != {VoiceSTT.get_version()}")
    return app.version


# -- 13. at least one real backend can really be initialized -----------------

@check("at_least_one_backend_really_loads")
def _at_least_one_backend_really_loads():
    from VoiceSTT.core import wakeword_catalog

    probers = wakeword_catalog.default_artifact_probers()
    available = {b: (p is not None) for b, p in probers.items()}
    if not any(available.values()):
        raise AssertionError(f"no inference runtime available at all: {available}")

    snapshot = wakeword_catalog.load_snapshot()
    snapshot = snapshot.with_backend_health(probers)
    healthy_backend = None
    for backend, present in available.items():
        if not present:
            continue
        if any(backend in entry.healthy_backends for entry in snapshot.entries):
            healthy_backend = backend
            break
    if healthy_backend is None:
        raise AssertionError(f"no wake word initialized under any available backend: {available}")

    selection, errors = snapshot.admit_selection(
        [next(e.id for e in snapshot.entries if healthy_backend in e.healthy_backends)],
        requested_backend=healthy_backend,
    )
    if selection is None:
        raise AssertionError(f"admission failed: {errors}")
    return {
        "runtimesAvailable": available,
        "backendInitialized": healthy_backend,
        "selectedWakeWordId": selection.wake_word_ids[0],
    }


# -- 14. no runtime downloads --------------------------------------------
# The preferred proof is operational: run this whole smoke in a container
# started with networking disabled (`docker run --network none`), so every
# check above - including the manifest load and the two real backend probes
# - only ever succeeds if it never needed the network. Docker itself was
# unusable in this environment for this run (see the packaging report), so
# this falls back to reporting whether that operational proof actually ran;
# the compensating evidence is the static no-network-import test
# (tests/unit/test_wakeword_asset_integrity.py::NoRuntimeDownloadTests) plus
# every check above succeeding purely from local files under asset_root.

@check("network_disabled_for_this_run")
def _network_disabled_for_this_run():
    declared = os.environ.get("SMOKE_NETWORK_DISABLED", "")
    if declared == "1":
        return "operationally enforced: process ran under --network none"
    return {
        "operationallyEnforced": False,
        "reason": (
            "Docker was unavailable in this environment for this run; "
            "see the W3 packaging/installed-artifact reports"
        ),
        "compensatingEvidence": (
            "tests/unit/test_wakeword_asset_integrity.py::NoRuntimeDownloadTests "
            "(static: no network-capable import in VoiceSTT.core.wakeword_catalog) "
            "plus every asset/catalog check above succeeding from local files only"
        ),
    }


if __name__ == "__main__":
    print(json.dumps(RESULT, indent=2, sort_keys=True))
    sys.exit(0 if RESULT["ok"] else 1)
