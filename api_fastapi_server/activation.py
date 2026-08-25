"""Server-authoritative activation state machine.

One session owns exactly one controller. It is the single authority that
decides when an activation window is open, which trigger sources contributed to
it, and when it ends. The recorder gate, the timeout scheduler and the emitted
activation events all follow this object; none of them may decide on their own.

Two counters are deliberately kept apart:

``generation``
    Increases only when a **new** activation opens. It stays stable for the
    whole life of one activation and is therefore what belongs into events and
    into the recorder gate binding.

``version``
    Increases on **every** state change, including merges and phase changes. It
    is what a scheduled timeout carries so that any state change invalidates a
    timer that was armed earlier.

All deadlines use ``time.monotonic``. Wall-clock time must never influence a
timeout, so that a system clock change cannot end or prolong an activation.
"""

from dataclasses import dataclass
import threading
import time
import uuid


INACTIVE = "inactive"
WAITING_FIRST_SPEECH = "waiting_first_speech"
SEGMENT_ACTIVE = "segment_active"
FOLLOWUP_WAIT = "followup_wait"
FINALIZING = "finalizing"

#: Phases in which the recorder gate must be open.
OPEN_WINDOW_PHASES = frozenset(
    {WAITING_FIRST_SPEECH, SEGMENT_ACTIVE, FOLLOWUP_WAIT}
)

MANUAL_SOURCE = "manual"
WAKE_WORD_SOURCE = "wake_word"
ACTIVATION_SOURCES = frozenset({MANUAL_SOURCE, WAKE_WORD_SOURCE})


@dataclass(frozen=True)
class ActivationDecision:
    accepted: bool
    reason: str
    snapshot: dict
    changed: bool = False


class ActivationController:
    """Serial state machine for server-authoritative activation windows.

    The object synchronises itself. It is reached from the WebSocket coroutine,
    from recorder callback threads and from the activation timeout thread, so
    relying on the caller to serialise access would be a race waiting to
    happen.
    """

    def __init__(
        self,
        *,
        manual_trigger_enabled=None,
        wake_word_trigger_enabled=None,
        initial_speech_timeout=15.0,
        followup_timeout=3.0,
        extension_seconds=5.0,
        clock=None,
        id_factory=None,
    ):
        if manual_trigger_enabled is None and wake_word_trigger_enabled is None:
            manual_trigger_enabled = True
            wake_word_trigger_enabled = False

        manual_trigger_enabled = bool(manual_trigger_enabled)
        wake_word_trigger_enabled = bool(wake_word_trigger_enabled)

        if not manual_trigger_enabled and not wake_word_trigger_enabled:
            raise ValueError("at least one activation trigger must be enabled")

        self.manual_trigger_enabled = manual_trigger_enabled
        self.wake_word_trigger_enabled = wake_word_trigger_enabled

        self.initial_speech_timeout = self._positive(
            "initial_speech_timeout", initial_speech_timeout
        )
        self.followup_timeout = self._positive(
            "followup_timeout", followup_timeout
        )
        self.extension_seconds = self._positive(
            "extension_seconds", extension_seconds
        )

        self._clock = clock or time.monotonic
        self._id_factory = id_factory or (lambda: uuid.uuid4().hex)
        self._lock = threading.RLock()

        self._generation = 0
        self._version = 0
        self._activation_id = None
        self._primary_source = None
        self._phase = INACTIVE
        self._sources = []
        self._deadline = None
        self._pending_extension = 0.0
        self._segment_count = 0

    # -- construction helpers ------------------------------------------------

    @staticmethod
    def _positive(name, value):
        number = float(value)
        if number <= 0:
            raise ValueError(f"{name} must be > 0")
        return number

    # -- read-only views -----------------------------------------------------

    @property
    def manual_enabled(self):
        return self.manual_trigger_enabled

    @property
    def wake_word_enabled(self):
        return self.wake_word_trigger_enabled

    @property
    def window_open(self):
        with self._lock:
            return self._phase in OPEN_WINDOW_PHASES

    def _source_enabled(self, source):
        if source == MANUAL_SOURCE:
            return self.manual_trigger_enabled
        if source == WAKE_WORD_SOURCE:
            return self.wake_word_trigger_enabled
        return False

    def _snapshot_locked(self):
        return {
            "activationId": self._activation_id,
            "generation": self._generation,
            "version": self._version,
            "primarySource": self._primary_source,
            "sources": list(self._sources),
            "phase": self._phase,
            "state": self._phase,
            "deadline": self._deadline,
            "pendingExtensionSeconds": self._pending_extension,
            "segments": self._segment_count,
            "windowOpen": self._phase in OPEN_WINDOW_PHASES,
            "active": self._activation_id is not None,
        }

    def snapshot(self):
        with self._lock:
            return self._snapshot_locked()

    # -- transitions ---------------------------------------------------------

    def activate(self, source):
        """Opens an activation, or merges an additional source into a running one.

        The collision rule of the specification lives here: the *first* trigger
        owns ``primarySource`` and a second trigger inside the same window must
        never create a second activation.
        """
        with self._lock:
            if not self._source_enabled(source):
                return ActivationDecision(
                    False, "trigger_disabled", self._snapshot_locked()
                )

            if self._phase in OPEN_WINDOW_PHASES:
                changed = source not in self._sources
                if changed:
                    self._sources.append(source)
                    self._version += 1
                return ActivationDecision(
                    True,
                    "merged" if changed else "already_active",
                    self._snapshot_locked(),
                    changed,
                )

            # inactive, or finalizing a previous activation: a trigger opens a
            # genuinely new activation with a new id and a new generation.
            self._activation_id = self._id_factory()
            self._primary_source = source
            self._phase = WAITING_FIRST_SPEECH
            self._sources = [source]
            self._deadline = self._clock() + self.initial_speech_timeout
            self._pending_extension = 0.0
            self._segment_count = 0
            self._generation += 1
            self._version += 1
            return ActivationDecision(
                True, "activated", self._snapshot_locked(), True
            )

    def extend(self, source):
        with self._lock:
            if not self._source_enabled(source):
                return ActivationDecision(
                    False, "trigger_disabled", self._snapshot_locked()
                )
            if self._phase not in OPEN_WINDOW_PHASES:
                return ActivationDecision(
                    False, "not_active", self._snapshot_locked()
                )
            if source not in self._sources:
                self._sources.append(source)
            if self._phase == SEGMENT_ACTIVE:
                # While speech is being recorded there is no deadline to move;
                # the extension is banked and applied to the follow-up window.
                self._pending_extension += self.extension_seconds
            else:
                now = self._clock()
                base = self._deadline if self._deadline is not None else now
                self._deadline = max(now, base) + self.extension_seconds
            self._version += 1
            return ActivationDecision(
                True, "extended", self._snapshot_locked(), True
            )

    def recording_started(self):
        with self._lock:
            if self._phase not in OPEN_WINDOW_PHASES:
                return ActivationDecision(
                    False, "not_active", self._snapshot_locked()
                )
            if self._phase == SEGMENT_ACTIVE:
                return ActivationDecision(
                    True, "already_recording", self._snapshot_locked()
                )
            self._phase = SEGMENT_ACTIVE
            self._deadline = None
            self._segment_count += 1
            self._version += 1
            return ActivationDecision(
                True, "recording_started", self._snapshot_locked(), True
            )

    def recording_ended(self):
        with self._lock:
            if self._phase not in OPEN_WINDOW_PHASES:
                return ActivationDecision(
                    False, "not_active", self._snapshot_locked()
                )
            timeout = self.followup_timeout + self._pending_extension
            self._pending_extension = 0.0
            self._phase = FOLLOWUP_WAIT
            self._deadline = self._clock() + timeout
            self._version += 1
            return ActivationDecision(
                True, "followup_started", self._snapshot_locked(), True
            )

    def finish(self, source):
        with self._lock:
            if not self._source_enabled(source):
                return ActivationDecision(
                    False, "trigger_disabled", self._snapshot_locked()
                )
            if self._phase not in OPEN_WINDOW_PHASES:
                return ActivationDecision(
                    False, "not_active", self._snapshot_locked()
                )
            snapshot = self._close_window_locked("finished")
            return ActivationDecision(True, "finished", snapshot, True)

    def cancel(self, source):
        with self._lock:
            if not self._source_enabled(source):
                return ActivationDecision(
                    False, "trigger_disabled", self._snapshot_locked()
                )
            if self._phase not in OPEN_WINDOW_PHASES:
                return ActivationDecision(
                    False, "not_active", self._snapshot_locked()
                )
            # A cancel discards the turn, so nothing is left to finalize.
            snapshot = self._close_window_locked("cancelled", finalize=False)
            return ActivationDecision(True, "cancelled", snapshot, True)

    def expire(self, expected_version):
        """Fires a scheduled timeout, if it is still the current one.

        The caller passes the ``version`` it armed the timer with. Any state
        change in between raises the version, so a stale timer is rejected
        instead of ending an activation it never belonged to.
        """
        with self._lock:
            if expected_version != self._version:
                return ActivationDecision(
                    False, "stale_timer", self._snapshot_locked()
                )
            if self._phase not in OPEN_WINDOW_PHASES or self._deadline is None:
                return ActivationDecision(
                    False, "not_expirable", self._snapshot_locked()
                )
            if self._clock() < self._deadline:
                return ActivationDecision(
                    False, "not_due", self._snapshot_locked()
                )
            snapshot = self._close_window_locked("timed_out")
            return ActivationDecision(True, "timed_out", snapshot, True)

    def finalized(self):
        """Marks the trailing transcription work of an activation as done."""
        with self._lock:
            if self._phase != FINALIZING:
                return ActivationDecision(
                    False, "not_finalizing", self._snapshot_locked()
                )
            snapshot = self._clear_locked()
            return ActivationDecision(True, "finalized", snapshot, True)

    def reset(self):
        """Drops any activation, whatever phase it is in.

        Used for stream stop, session close and reconnect: an activation must
        never survive into a new connection.
        """
        with self._lock:
            if self._phase == INACTIVE and self._activation_id is None:
                return ActivationDecision(
                    True, "already_inactive", self._snapshot_locked()
                )
            snapshot = self._clear_locked()
            return ActivationDecision(True, "reset", snapshot, True)

    # -- internals -----------------------------------------------------------

    def _close_window_locked(self, reason, finalize=True):
        """Closes the activation window; the gate must close with it.

        If the activation produced at least one segment, the activation stays
        alive in ``finalizing`` so that the trailing final transcription can
        still be correlated to its ``activationId``.
        """
        closed_id = self._activation_id
        closed_primary = self._primary_source
        closed_sources = list(self._sources)
        segments = self._segment_count

        self._deadline = None
        self._pending_extension = 0.0

        if finalize and segments > 0:
            self._phase = FINALIZING
            self._version += 1
            snapshot = self._snapshot_locked()
        else:
            snapshot = self._clear_locked()

        snapshot["closedActivationId"] = closed_id
        snapshot["closedPrimarySource"] = closed_primary
        snapshot["closedSources"] = closed_sources
        snapshot["closedSegments"] = segments
        snapshot["closeReason"] = reason
        return snapshot

    def _clear_locked(self):
        closed_id = self._activation_id
        closed_primary = self._primary_source
        closed_sources = list(self._sources)
        segments = self._segment_count

        self._activation_id = None
        self._primary_source = None
        self._phase = INACTIVE
        self._sources = []
        self._deadline = None
        self._pending_extension = 0.0
        self._segment_count = 0
        self._version += 1

        snapshot = self._snapshot_locked()
        snapshot["closedActivationId"] = closed_id
        snapshot["closedPrimarySource"] = closed_primary
        snapshot["closedSources"] = closed_sources
        snapshot["closedSegments"] = segments
        return snapshot
