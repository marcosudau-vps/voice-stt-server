"""Persistence adapter of the settings control plane.

The adapter reuses the existing :class:`RuntimeConfigStore` and its single
runtime JSON document. Server-setting overlay and the monotonic
``settingsRevision`` are stored as additive top-level fields of the very same
file; no second JSON document or database is introduced.
"""

import json
import os
import uuid
from typing import Dict, Optional

from VoiceSTT_server.operations import RuntimeConfigStore, _utc_now


class RuntimeSettingsStore(RuntimeConfigStore):
    """Atomic persistence of settings overlay and revision in one file."""

    OVERLAY_FIELD = "settingsOverlay"
    REVISION_FIELD = "settingsRevision"

    def load_overlay(self) -> Dict[str, object]:
        if self.path is None or not self.path.is_file():
            return {}
        payload = self._read_payload()
        overlay = payload.get(self.OVERLAY_FIELD)
        return dict(overlay) if isinstance(overlay, dict) else {}

    def load_revision(self) -> int:
        if self.path is None or not self.path.is_file():
            return 0
        payload = self._read_payload()
        revision = payload.get(self.REVISION_FIELD, 0)
        if isinstance(revision, bool) or not isinstance(revision, int):
            return 0
        return revision if revision >= 0 else 0

    def save_overlay_and_revision(
        self,
        overlay: Dict[str, object],
        revision: int,
    ) -> Optional[str]:
        """Atomically adds overlay and revision to the runtime config file.

        The legacy ``settings`` field written by the existing service
        persistence is preserved untouched.
        """
        if self.path is None:
            return None
        payload = self._read_payload() if self.path.is_file() else {}
        payload[self.OVERLAY_FIELD] = dict(overlay)
        payload[self.REVISION_FIELD] = int(revision)
        payload.setdefault("version", 1)
        payload["updatedAt"] = _utc_now()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(
            f".{self.path.name}.{uuid.uuid4().hex}.tmp"
        )
        with self._lock:
            temporary.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            os.replace(temporary, self.path)
        return str(self.path.resolve())

    def _read_payload(self) -> dict:
        try:
            payload = json.loads(
                self.path.read_text(encoding="utf-8", errors="replace")
            )
        except (OSError, ValueError):
            return {}
        return payload if isinstance(payload, dict) else {}