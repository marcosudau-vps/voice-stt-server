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

AP_SRV_060_BINDING
    ``wakeWordCapabilities``, the wake-word selection admission and
    ``wakeword.detected``. Since AP-SRV-060 the port reads the one server-wide
    :class:`~VoiceSTT.core.wakeword_catalog.WakeWordCatalogAuthority`; it holds
    no catalog, no revision and no resolver of its own.

    The port is the **wire** side, so it admits canonical ids only. The
    tolerant human resolver of the catalog is deliberately not reachable from
    here: a client that sends an alias or a display name in
    ``requestedSession.wakeWordIds`` is rejected, because the frozen wire
    contract says those ids are canonical (Root F1).
"""

REQUIRES_AP_SRV_050_BINDING = "REQUIRES_AP_SRV_050_BINDING"
AP_SRV_060_BINDING = "AP_SRV_060_BINDING"
#: Historical name of the AP-SRV-060 marker, kept so an external reader of the
#: module constant does not break at the binding commit.
REQUIRES_AP_SRV_060_BINDING = AP_SRV_060_BINDING


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

    def settings_projection(self):
        """One atomic snapshot settings bundle (AP-SRV-050 C3).

        revision/requested/effective come from the session settings authority
        as a single atomic read; the port never stores anything.
        """
        return self._session.settings_projection_for_wire()

    def patch(self, base_revision, changes):
        """Binds ``session_settings.patch`` to the session settings control.

        Returns a ``PatchResult``; the connection handler decides the ack
        result and the settings.changed emission.
        """
        return self._session.apply_settings_patch(base_revision, changes)


class WakeWordPort:
    """Thin adapter of the AP-SRV-060 catalog authority to the v2 wire.

    The port stores nothing. ``catalogRevision``, availability, the resolver
    and the atomic admission all live in the one server-wide
    :class:`~VoiceSTT.core.wakeword_catalog.WakeWordCatalogAuthority`; this
    class only answers what the handshake and the snapshot ask for.
    """

    binding = AP_SRV_060_BINDING

    def __init__(self, service):
        self._service = service

    @property
    def catalog(self):
        """The one catalog authority, or ``None`` on a service without one."""
        return getattr(self._service, "wakeword_catalog", None)

    def capabilities(self):
        catalog = self.catalog
        if catalog is None:
            return {"catalogRevision": 0, "availableWakeWordIds": []}
        return catalog.capabilities()

    def catalog_revision(self):
        catalog = self.catalog
        return catalog.catalog_revision if catalog is not None else 0

    def available_ids(self):
        catalog = self.catalog
        if catalog is None:
            return []
        return list(catalog.available_ids())

    def resolve_selection(self, wake_word_ids):
        """``(selection, errors)`` of one atomic **wire** admission.

        Canonical ids only, and every selected artifact is really probed for
        loadability before the session may be accepted.
        """
        catalog = self.catalog
        if catalog is None:
            return None, [{
                "field": "requestedSession.wakeWordIds",
                "code": "wake_word_unavailable",
                "reason": "catalog_unavailable",
                "message": (
                    "Der Wake-Word-Katalog ist auf diesem Server nicht "
                    "verfügbar."
                ),
            }]
        selection, errors = catalog.admit_selection(wake_word_ids)
        return selection, [error.to_dict() for error in errors]

    def validate_selection(self, wake_word_ids):
        """Atomic admission of one requested selection.

        A single non-canonical, unknown, globally disabled, missing or
        unloadable id rejects the whole selection and every problematic id is
        named - there is no partial catalog, no default fallback and no silent
        removal.
        """
        _selection, errors = self.resolve_selection(wake_word_ids)
        return errors
