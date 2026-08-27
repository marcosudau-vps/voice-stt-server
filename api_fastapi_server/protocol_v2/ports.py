"""Narrow ports for the authorities AP-SRV-040 does not own.

AP-SRV-040 owns the wire. It does **not** own the settings control plane
(AP-SRV-050) and it does **not** own the wake-word catalog, detection or
audio boundary (AP-SRV-060). Both are needed on the wire today, so they are
represented as thin read/validate ports with an explicit marker instead of a
second registry or a second wake engine.

REQUIRES_AP_SRV_050_BINDING
    ``settingsRevision``, ``effectiveSettings``, ``settings.changed`` and
    ``session_settings.patch``. Until AP-SRV-050 the revision is the session
    constant ``0``, ``effectiveSettings`` mirrors the immutable activation
    settings AP-SRV-030 already resolves, and a patch is refused as
    ``settings_rejected`` with a machine-readable reason.

REQUIRES_AP_SRV_060_BINDING
    ``wakeWordCapabilities``, the wake-word selection admission and
    ``wakeword.detected``. Until AP-SRV-060 the port reports the build catalog
    the server already knows and validates the requested selection against it.
    The event model carries ``wakeWordId``/``score``/``primarySource`` so no
    anonymous boolean wake semantics are frozen into the wire.
"""

REQUIRES_AP_SRV_050_BINDING = "REQUIRES_AP_SRV_050_BINDING"
REQUIRES_AP_SRV_060_BINDING = "REQUIRES_AP_SRV_060_BINDING"


class SettingsPort:
    """Adapter of the AP-SRV-050 session settings control to the v2 wire.

    The port never stores a value and holds no settings authority; it reads the
    session's one :class:`SessionSettingsState` and lets the wire layer
    (``connection``) project the transaction result into ``command.ack`` and
    ``settings.changed`` through the existing AP-SRV-040 event dispatch seam.
    """

    binding = REQUIRES_AP_SRV_050_BINDING

    def __init__(self, session):
        self._session = session

    @property
    def revision(self):
        """The revision of *this* v2 session only (never the server revision)."""
        return self._session.settings_state.settings_revision

    def effective_settings(self):
        """The flat, latch-consistent effective settings of this session."""
        return self._session.settings_effective_for_wire()

    def requested_settings(self):
        """The requested settings of this session (additive snapshot field).

        Reads exclusively from the session settings authority; the port stores
        nothing (AP-SRV-050 C2 F6).
        """
        return self._session.settings_requested_for_wire()

    def patch(self, base_revision, changes):
        """Binds ``session_settings.patch`` to the session settings control.

        Returns a ``PatchResult``; the connection handler decides the ack
        result and the settings.changed emission.
        """
        return self._session.apply_settings_patch(base_revision, changes)


class WakeWordPort:
    """Catalog and selection admission for wake words.

    The catalog itself belongs to the server; the selected-only initialisation
    and the detection latch belong to AP-SRV-060. This port only answers
    "which ids exist" and "is this selection admissible", which is what the
    handshake and the snapshot need.
    """

    binding = REQUIRES_AP_SRV_060_BINDING

    def __init__(self, service):
        self._service = service

    def capabilities(self):
        available = self.available_ids()
        return {
            # A real, monotone catalog revision arrives with AP-SRV-060; until
            # then the catalog is a build constant, so the revision is too.
            "catalogRevision": 1,
            "availableWakeWordIds": list(available),
        }

    def available_ids(self):
        capabilities = {}
        try:
            capabilities = self._service.session_capabilities() or {}
        except Exception:
            return []
        wake_word = capabilities.get("wakeWord") or {}
        entries = wake_word.get("availableWakeWords") or []
        ids = []
        for entry in entries:
            identifier = (entry or {}).get("id")
            if isinstance(identifier, str) and identifier:
                ids.append(identifier)
        return sorted(set(ids))

    def validate_selection(self, wake_word_ids):
        """Atomic admission of one requested selection.

        Every unknown id rejects the whole selection, as the frozen wake-word
        contract demands - there is no partial catalog.
        """
        available = set(self.available_ids())
        errors = []
        for identifier in wake_word_ids:
            if identifier not in available:
                errors.append({
                    "field": "requestedSession.wakeWordIds",
                    "code": "wake_word_unavailable",
                    "message": (
                        f"Das Wake Word '{identifier}' ist für diesen Server "
                        "nicht verfügbar."
                    ),
                })
        return errors
