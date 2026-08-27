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
    """Read-only projection of the settings a v2 session must publish.

    The port never stores a value. ``effective_settings`` reads the activation
    configuration AP-SRV-030 resolved for this session, so a running
    activation keeps exactly the snapshot it started with.
    """

    binding = REQUIRES_AP_SRV_050_BINDING

    #: The session settings revision until AP-SRV-050 owns it.
    INITIAL_REVISION = 0

    def __init__(self, session):
        self._session = session

    @property
    def revision(self):
        return self.INITIAL_REVISION

    def effective_settings(self):
        """The activation timings that are in force for this session."""
        config = getattr(self._session, "activation_config", None)
        if config is None:
            return {}
        return {
            "activation.initialSpeechTimeoutMs": _ms(
                config.initial_speech_timeout
            ),
            "activation.followupTimeoutMs": _ms(config.followup_timeout),
            "activation.segmentWatchdogInitialMs": _ms(
                config.segment_watchdog_initial
            ),
            "activation.segmentWatchdogRefreshMs": _ms(
                config.segment_watchdog_refresh
            ),
            "activation.segmentWatchdogWarningMs": _ms(
                config.segment_watchdog_warning
            ),
            "activation.closingRecoveryTimeoutMs": _ms(
                config.closing_recovery_timeout
            ),
        }

    def patch(self, base_revision, changes):
        """Refuses every patch until AP-SRV-050 owns the control plane.

        Returns ``(result, errors)``. A stale base revision is reported as a
        revision conflict so the client learns the correct distinction even
        before the control plane exists.
        """
        if int(base_revision) != self.revision:
            return "settings_revision_conflict", [{
                "field": "baseSettingsRevision",
                "code": "stale_settings_revision",
                "message": (
                    "Die angegebene Settings-Revision ist nicht die aktuelle."
                ),
            }]
        return "settings_rejected", [{
            "field": key,
            "code": "settings_control_plane_unavailable",
            "message": (
                "Die serverautoritative Settings-Control-Plane wird mit "
                "AP-SRV-050 bereitgestellt."
            ),
        } for key in sorted(str(name) for name in changes)]


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


def _ms(seconds):
    if seconds is None:
        return None
    return int(round(float(seconds) * 1000))
