"""Path-free projections of the existing model manager, never a registry."""
import hashlib
import os
from pathlib import Path


def installation_id(candidate):
    identity = "\0".join((candidate.engine, candidate.product_id or candidate.id,
                            os.path.normcase(os.path.abspath(candidate.path))))
    return "installation-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]


def managed(candidate, manager):
    root = manager.default_root(candidate.engine).absolute()
    path = Path(candidate.path).absolute()
    # Discovery resolves links; a resolved external path cannot become managed
    # merely because discovery began in the managed directory.
    return path.parent == root and root.resolve() == root


def project_inventory(manager, *, admin=False):
    with manager._state_lock:
        snapshot = manager.snapshot()
        products = manager.authority
        intent = manager.intent
        installations = []
        for candidate in snapshot.candidates:
            item = {
                "installationId": installation_id(candidate),
                "modelId": candidate.product_id or candidate.id,
                "engine": candidate.engine, "validationState": candidate.state,
                "origin": "managed" if managed(candidate, manager) else "external",
                "eligible": manager.candidate_eligible(candidate),
                "effectiveRoles": sorted(role for role, active in snapshot.active.items()
                                         if active.path == candidate.path),
            }
            if admin:
                item["path"] = candidate.path
            installations.append(item)
        catalog = []
        for product in products:
            catalog.append({
                "modelId": product.id, "catalogId": product.catalog_id,
                "engine": product.engine, "language": product.language,
                "licenseClass": product.license_class, "revision": product.revision,
                "downloadAllowed": bool(product.provisioning_allowed),
                "rightsStatus": product.rights_status,
                "operatorEnabled": intent.engine_enabled(product.engine) and intent.model_enabled(product),
                "autoDownloadSelected": intent.effective_auto_download(product),
                "installed": any(item["modelId"] == product.id for item in installations),
            })
        return {"inventoryRevision": snapshot.revision, "models": catalog,
                "installations": installations, "minimumReady": snapshot.minimum_ready}
