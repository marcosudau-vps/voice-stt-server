"""Server-authoritative foreground activation state machine and timer policy.

One session owns exactly one controller. The controller serialises trigger
commands, recorder callbacks and timeout callbacks and exposes the five
canonical foreground phases. Final transcription work is deliberately not a
phase of this machine: after input has been closed safely, the foreground is
idle and may admit the next activation while older work drains in the
background.

Identity and revisions
----------------------

``activationSequence`` (also exposed as the compatibility field
``generation``) increases only when a new activation is admitted. ``version``
increases on every state change. ``timerRevision`` increases only when an
*effective* timer change happens, and together with the activation identity,
the phase and the segment token it forms the :class:`TimerToken` that a
scheduled callback has to present. A callback whose token no longer matches is
inert - it can neither end a newer activation nor resurrect an older one.

Deadlines are monotonic. Wall-clock jumps therefore cannot expire or extend a
phase; wall-clock time is used for logs and public timestamps only.

Timer contract (AP-SRV-030)
---------------------------

======================  ====================================================
Deadline kind           Rule
======================  ====================================================
``initial_speech``      ``now + initial_speech_timeout`` on admission.
                        ``refresh`` is ``invalid_phase`` here.
``followup``            ``now + followup_timeout`` after a regular segment
                        end and again on every ``refresh``. Never cumulative.
``segment_watchdog``    ``now + segment_watchdog_initial`` when a segment
                        starts; ``refresh`` sets
                        ``max(current_deadline, now + watchdog_refresh)``.
                        A warning becomes due ``segment_watchdog_warning``
                        before the deadline. VAD does not reset it.
``closing_recovery``    ``now + closing_recovery_timeout`` when
                        ``closing_input`` is entered, so a stuck input close
                        can never hang the foreground.
======================  ====================================================

Close semantics (AP-SRV-030 C2)
-------------------------------

Entering ``closing_input`` creates exactly one immutable :class:`CloseContext`
that keeps the close identity alive until the input close has really
completed. The controller itself never claims ``idle`` before gate and
recorder have been cleaned up (F1): ``_recover_closing_locked`` consumes the
recovery deadline but keeps the phase at ``closing_input``, and only the
identity-bound :meth:`input_closed` completes the transition to ``idle``.
Control commands (``refresh|finish|cancel``) are source-neutral (F6): only
``activate`` is tied to a trigger source.
"""

from copy import deepcopy
from dataclasses import dataclass
import threading
import time
from types import MappingProxyType
import uuid


IDLE = "idle"
WAITING_FIRST_SPEECH = "waiting_first_speech"
SEGMENT_ACTIVE = "segment_active"
FOLLOWUP_WAIT = "followup_wait"
CLOSING_INPUT = "closing_input"

# Compatibility import for callers that used the old constant name. It is an
# alias, not a sixth phase value.
INACTIVE = IDLE

#: Phases in which the recorder gate must be open.
OPEN_WINDOW_PHASES = frozenset(
    {WAITING_FIRST_SPEECH, SEGMENT_ACTIVE, FOLLOWUP_WAIT}
)

MANUAL_SOURCE = "manual"
WAKE_WORD_SOURCE = "wake_word"
ACTIVATION_SOURCES = frozenset({MANUAL_SOURCE, WAKE_WORD_SOURCE})

#: The four canonical deadline kinds of the frozen timer contract.
INITIAL_SPEECH_DEADLINE = "initial_speech"
FOLLOWUP_DEADLINE = "followup"
SEGMENT_WATCHDOG_DEADLINE = "segment_watchdog"
CLOSING_RECOVERY_DEADLINE = "closing_recovery"

#: Contract defaults in seconds. The millisecond values of the contract are
#: the same numbers; the settings control plane (AP-SRV-050) owns the public
#: schema, ranges and apply policies.
DEFAULT_INITIAL_SPEECH_TIMEOUT = 15.0
DEFAULT_FOLLOWUP_TIMEOUT = 3.0
DEFAULT_SEGMENT_WATCHDOG_INITIAL = 600.0
DEFAULT_SEGMENT_WATCHDOG_REFRESH = 180.0
DEFAULT_SEGMENT_WATCHDOG_WARNING = 30.0
DEFAULT_CLOSING_RECOVERY_TIMEOUT = 5.0


def _freeze(value):
    """Returns a recursively immutable, detached settings value."""
    if isinstance(value, dict):
        return MappingProxyType(
            {key: _freeze(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return deepcopy(value)


def _thaw(value):
    """Returns a defensive plain-data copy of a frozen settings value."""
    if isinstance(value, MappingProxyType):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, frozenset):
        return {_thaw(item) for item in value}
    return deepcopy(value)


@dataclass(frozen=True)
class TimerToken:
    """The complete identity a scheduled callback has to present.

    Checking ``timerRevision`` alone would not be enough: the counter restarts
    its meaning with every activation, so an old callback of activation *A*
    could coincidentally match a revision of activation *B*. The token
    therefore also carries the activation identity, the phase it was armed for
    and - for the segment watchdog - the segment token.
    """

    activation_id: str
    activation_sequence: int
    timer_revision: int
    phase: str
    kind: str
    segment_token: int


@dataclass(frozen=True)
class ActivationDecision:
    accepted: bool
    reason: str
    snapshot: dict
    changed: bool = False


@dataclass(frozen=True)
class CloseContext:
    """Immutable close identity held for the whole ``closing_input``.

    The context is created when the close barrier is entered and kept until
    ``input_closed()`` really ends the activation (or a reset discards it).
    ``requested_by_action``/``requested_by_command_id`` stay ``None`` for
    timer, watchdog, device and recovery closes, so the server-side wire
    correlation can be derived from the *actual* completion cause (F2/F7).
    """

    reason: str
    cause: str
    requested_by_command_id: str | None = None
    requested_by_action: str | None = None


@dataclass(frozen=True)
class ActivationTimingPolicy:
    """Immutable timing snapshot one activation latches at admission (AP-SRV-050).

    A settings patch that arrives while an activation is open must never mutate
    the armed timers of that activation. New values are latched exactly once at
    the next successful activation admission; until then this activation keeps
    the policy it started with. Values are wall-clock-independent seconds for
    the :class:`ActivationController`, exactly like the legacy constructor
    defaults they replace.
    """

    initial_speech_timeout: float
    followup_timeout: float
    segment_watchdog_initial: float
    segment_watchdog_refresh: float
    segment_watchdog_warning: float
    closing_recovery_timeout: float


class ActivationController:
    """Thread-safe authority for one session's foreground activation."""

    def __init__(
        self,
        *,
        manual_trigger_enabled=None,
        wake_word_trigger_enabled=None,
        initial_speech_timeout=DEFAULT_INITIAL_SPEECH_TIMEOUT,
        followup_timeout=DEFAULT_FOLLOWUP_TIMEOUT,
        segment_watchdog_initial=DEFAULT_SEGMENT_WATCHDOG_INITIAL,
        segment_watchdog_refresh=DEFAULT_SEGMENT_WATCHDOG_REFRESH,
        segment_watchdog_warning=DEFAULT_SEGMENT_WATCHDOG_WARNING,
        closing_recovery_timeout=DEFAULT_CLOSING_RECOVERY_TIMEOUT,
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
        # Runtime suppression of the *configured* sources. It only gates the
        # admission of a new activation; a running activation keeps its source
        # and is never ended by a suppression change (contract 8.1).
        self._suppressed = {MANUAL_SOURCE: False, WAKE_WORD_SOURCE: False}
        self.initial_speech_timeout = self._positive(
            "initial_speech_timeout", initial_speech_timeout
        )
        self.followup_timeout = self._positive(
            "followup_timeout", followup_timeout
        )
        self.segment_watchdog_initial = self._positive(
            "segment_watchdog_initial", segment_watchdog_initial
        )
        self.segment_watchdog_refresh = self._positive(
            "segment_watchdog_refresh", segment_watchdog_refresh
        )
        self.segment_watchdog_warning = self._positive(
            "segment_watchdog_warning", segment_watchdog_warning
        )
        self.closing_recovery_timeout = self._positive(
            "closing_recovery_timeout", closing_recovery_timeout
        )
        self._clock = clock or time.monotonic
        self._id_factory = id_factory or (lambda: uuid.uuid4().hex)
        self._lock = threading.RLock()

        self._activation_sequence = 0
        self._version = 0
        self._timer_revision = 0
        self._segment_token = 0
        self._activation_id = None
        self._primary_source = None
        self._effective_settings = _freeze({})
        #: The immutable timing policy the *current* activation latched at
        #: admission. ``None`` keeps the legacy constructor defaults for paths
        #: that do not resolve settings yet (AP-SRV-050 prompt 11).
        self._timing_policy = None
        self._phase = IDLE
        self._deadline = None
        self._deadline_kind = None
        self._warning_deadline = None
        self._warning_fired = False
        self._segment_count = 0
        self._close_context = None
        self._recovery_requested = False

    @staticmethod
    def _positive(name, value):
        number = float(value)
        if number <= 0:
            raise ValueError(f"{name} must be > 0")
        return number

    def _timing_locked(self):
        """The timing policy the running activation latched, or the legacy fallback.

        Every timer site reads through this single seam: a settings patch can
        therefore never retarget an already armed activation. New values are
        only picked up at the next activation admission via ``timing_policy``.
        """
        if self._timing_policy is not None:
            return self._timing_policy
        return ActivationTimingPolicy(
            initial_speech_timeout=self.initial_speech_timeout,
            followup_timeout=self.followup_timeout,
            segment_watchdog_initial=self.segment_watchdog_initial,
            segment_watchdog_refresh=self.segment_watchdog_refresh,
            segment_watchdog_warning=self.segment_watchdog_warning,
            closing_recovery_timeout=self.closing_recovery_timeout,
        )

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

    def _configured(self, source):
        if source == MANUAL_SOURCE:
            return bool(self.manual_trigger_enabled)
        if source == WAKE_WORD_SOURCE:
            return bool(self.wake_word_trigger_enabled)
        return False

    def _source_enabled(self, source):
        """The effective admission gate: configured and not suppressed."""
        if not self._configured(source):
            return False
        return not self._suppressed.get(source, False)

    def set_runtime_suppression(self, *, manual=None, wake_word=None):
        """Live suppression mask for new admissions. Returns whether it moved.

        Suppression never merges sources, never changes a running activation
        and never ends one; it only decides whether the *next* trigger of that
        source is admitted.
        """
        with self._lock:
            changed = False
            for source, value in (
                (MANUAL_SOURCE, manual),
                (WAKE_WORD_SOURCE, wake_word),
            ):
                if value is None:
                    continue
                value = bool(value)
                if self._suppressed[source] != value:
                    self._suppressed[source] = value
                    changed = True
            return changed

    def trigger_state(self):
        """The frozen ``configured``/``suppressed``/``effective`` projection."""
        with self._lock:
            configured = {
                MANUAL_SOURCE: self._configured(MANUAL_SOURCE),
                WAKE_WORD_SOURCE: self._configured(WAKE_WORD_SOURCE),
            }
            suppressed = dict(self._suppressed)
            return {
                "configured": configured,
                "suppressed": suppressed,
                "effective": {
                    source: configured[source] and not suppressed[source]
                    for source in configured
                },
            }

    # -- timer ownership -----------------------------------------------------

    def _clear_timer_locked(self):
        """Drops the armed deadline. Every drop is an effective timer change."""
        if self._deadline is None and self._deadline_kind is None:
            return
        self._deadline = None
        self._deadline_kind = None
        self._warning_deadline = None
        self._warning_fired = False
        self._timer_revision += 1

    def _set_timer_locked(self, kind, deadline, *, warning_after=None):
        """Arms one deadline and raises ``timerRevision``.

        Only the controller creates and invalidates deadlines, and every path
        goes through this one place. A scheduled callback can therefore never
        keep a revision that some other code path forgot to raise.
        """
        self._deadline = float(deadline)
        self._deadline_kind = kind
        if warning_after is None:
            self._warning_deadline = None
        else:
            # A warning window wider than the remaining time makes the warning
            # due immediately instead of silently dropping it.
            self._warning_deadline = max(
                self._clock(), float(deadline) - float(warning_after)
            )
        self._warning_fired = False
        self._timer_revision += 1

    def _timer_token_locked(self):
        return TimerToken(
            activation_id=self._activation_id,
            activation_sequence=self._activation_sequence,
            timer_revision=self._timer_revision,
            phase=self._phase,
            kind=self._deadline_kind,
            segment_token=self._segment_token,
        )

    def _token_is_current_locked(self, token):
        if not isinstance(token, TimerToken):
            return False
        return token == self._timer_token_locked()

    # -- snapshots -----------------------------------------------------------

    def _snapshot_locked(self):
        sources = [self._primary_source] if self._primary_source else []
        snapshot = {
            "activationId": self._activation_id,
            "activationSequence": self._activation_sequence,
            # Gate generation is retained until the v2 wire migration. It is
            # the same session-increasing activation identity.
            "generation": self._activation_sequence,
            "version": self._version,
            "timerRevision": self._timer_revision,
            "segmentToken": self._segment_token,
            "primarySource": self._primary_source,
            "sources": sources,
            "effectiveSettings": _thaw(self._effective_settings),
            "phase": self._phase,
            "state": self._phase,
            "deadline": self._deadline,
            "deadlineKind": self._deadline_kind,
            "warningDeadline": (
                None if self._warning_fired else self._warning_deadline
            ),
            "warningFired": self._warning_fired,
            "segments": self._segment_count,
            "windowOpen": self._phase in OPEN_WINDOW_PHASES,
            "active": self._phase != IDLE,
            "timerToken": self._timer_token_locked(),
        }
        context = self._close_context
        if context is not None:
            snapshot["closeReason"] = context.reason
            snapshot["closeCause"] = context.cause
            snapshot["closeRequestedByCommandId"] = (
                context.requested_by_command_id
            )
            snapshot["closeRequestedByAction"] = context.requested_by_action
        snapshot["recoveryRequested"] = bool(self._recovery_requested)
        return snapshot

    def snapshot(self):
        with self._lock:
            return self._snapshot_locked()

    def timer_token(self):
        with self._lock:
            return self._timer_token_locked()

    # -- command surface -----------------------------------------------------

    def _activation_mismatch_locked(self, activation_id):
        """``stale_activation`` guard for the observed activation id.

        ``None`` means "the caller observed no id" and stays allowed for the
        server-internal transitions that are not command driven and for the
        not-yet-migrated v1 transport. A *wrong* id is always refused, which
        is what keeps a command aimed at activation *A* from acting on the
        newer activation *B*.
        """
        if activation_id is None:
            return False
        return str(activation_id) != str(self._activation_id)

    def activate(self, source, effective_settings=None, *, activation_id=None,
                 timing_policy=None):
        """Admits a new activation only while the foreground is idle.

        ``timing_policy`` is the (immutable) :class:`ActivationTimingPolicy`
        resolved by the session settings control at admission. It is latched
        exactly once here; a later settings patch cannot change this
        activation. ``None`` keeps the legacy constructor timing defaults.
        """
        with self._lock:
            if source not in ACTIVATION_SOURCES:
                return ActivationDecision(
                    False, "trigger_disabled", self._snapshot_locked()
                )
            if self._phase != IDLE:
                return ActivationDecision(
                    False, "activation_locked", self._snapshot_locked()
                )
            if not self._source_enabled(source):
                return ActivationDecision(
                    False, "trigger_disabled", self._snapshot_locked()
                )
            if activation_id is not None:
                # ``activate`` never addresses an existing activation.
                return ActivationDecision(
                    False, "invalid_payload", self._snapshot_locked()
                )

            self._activation_id = self._id_factory()
            self._activation_sequence += 1
            self._primary_source = source
            self._effective_settings = _freeze(effective_settings or {})
            self._timing_policy = timing_policy
            self._phase = WAITING_FIRST_SPEECH
            self._segment_count = 0
            self._close_context = None
            self._recovery_requested = False
            timing = self._timing_locked()
            self._set_timer_locked(
                INITIAL_SPEECH_DEADLINE,
                self._clock() + timing.initial_speech_timeout,
            )
            self._version += 1
            return ActivationDecision(
                True, "activated", self._snapshot_locked(), True
            )

    def refresh(self, *, activation_id, command_id=None):
        """The contract ``refresh``: source-neutral, never cumulative.

        * ``waiting_first_speech`` - ``invalid_phase``; the initial-speech
          window is not refreshable.
        * ``segment_active`` - watchdog refresh to
          ``max(current_deadline, now + watchdog_refresh)``.
        * ``followup_wait`` - the deadline becomes ``now + followup_timeout``.
        * ``closing_input`` - ``closing_input``, no effect.
        * ``idle`` - ``not_active``.

        The observed ``activationId`` is mandatory; a missing or wrong id
        always refuses the command (F5).
        """
        with self._lock:
            if not activation_id:
                return ActivationDecision(
                    False, "invalid_payload", self._snapshot_locked()
                )
            if self._phase == IDLE:
                return ActivationDecision(
                    False, "not_active", self._snapshot_locked()
                )
            if self._activation_mismatch_locked(activation_id):
                return ActivationDecision(
                    False, "stale_activation", self._snapshot_locked()
                )
            if self._phase == WAITING_FIRST_SPEECH:
                return ActivationDecision(
                    False, "invalid_phase", self._snapshot_locked()
                )
            if self._phase == CLOSING_INPUT:
                return ActivationDecision(
                    False, "closing_input", self._snapshot_locked()
                )

            now = self._clock()
            timing = self._timing_locked()
            if self._phase == SEGMENT_ACTIVE:
                current = self._deadline if self._deadline is not None else now
                target = max(current, now + timing.segment_watchdog_refresh)
                if target <= current:
                    # An early refresh must not shorten a longer remaining
                    # deadline, and a no-op must not churn the armed timer.
                    return ActivationDecision(
                        True, "refreshed", self._snapshot_locked(), False
                    )
                self._set_timer_locked(
                    SEGMENT_WATCHDOG_DEADLINE,
                    target,
                    warning_after=timing.segment_watchdog_warning,
                )
            else:
                self._set_timer_locked(
                    FOLLOWUP_DEADLINE, now + timing.followup_timeout
                )
            self._version += 1
            return ActivationDecision(
                True, "refreshed", self._snapshot_locked(), True
            )

    def recording_started(self):
        with self._lock:
            if self._phase not in OPEN_WINDOW_PHASES:
                return ActivationDecision(
                    False, "not_active", self._snapshot_locked()
                )
            if self._phase == SEGMENT_ACTIVE:
                # Continued voice activity inside the same segment. The
                # watchdog is explicitly *not* reset by VAD (TIME-06).
                return ActivationDecision(
                    True, "already_recording", self._snapshot_locked()
                )
            self._phase = SEGMENT_ACTIVE
            self._segment_count += 1
            self._segment_token += 1
            timing = self._timing_locked()
            self._set_timer_locked(
                SEGMENT_WATCHDOG_DEADLINE,
                self._clock() + timing.segment_watchdog_initial,
                warning_after=timing.segment_watchdog_warning,
            )
            self._version += 1
            return ActivationDecision(
                True, "recording_started", self._snapshot_locked(), True
            )

    def recording_ended(self):
        with self._lock:
            if self._phase == CLOSING_INPUT:
                return ActivationDecision(
                    True, "input_closing", self._snapshot_locked()
                )
            if self._phase != SEGMENT_ACTIVE:
                return ActivationDecision(
                    False, "not_active", self._snapshot_locked()
                )
            self._phase = FOLLOWUP_WAIT
            self._set_timer_locked(
                FOLLOWUP_DEADLINE,
                self._clock() + self._timing_locked().followup_timeout,
            )
            self._version += 1
            return ActivationDecision(
                True, "followup_started", self._snapshot_locked(), True
            )

    def finish(self, *, activation_id, command_id=None):
        """Contract ``finish``: source-neutral, carries the command identity."""
        return self._begin_input_close(
            "finished",
            "finish",
            activation_id=activation_id,
            command_id=command_id,
            requested_by_action="finish",
        )

    def cancel(self, *, activation_id, command_id=None, cause="cancel"):
        """Contract ``cancel``: source-neutral, carries the command identity."""
        return self._begin_input_close(
            "cancelled",
            cause,
            activation_id=activation_id,
            command_id=command_id,
            requested_by_action="cancel",
        )

    def _begin_input_close(
        self,
        reason,
        cause,
        *,
        activation_id,
        command_id=None,
        requested_by_action=None,
    ):
        with self._lock:
            if not activation_id:
                return ActivationDecision(
                    False, "invalid_payload", self._snapshot_locked()
                )
            if self._phase == IDLE:
                return ActivationDecision(
                    False, "not_active", self._snapshot_locked()
                )
            if self._activation_mismatch_locked(activation_id):
                return ActivationDecision(
                    False, "stale_activation", self._snapshot_locked()
                )
            if self._phase == CLOSING_INPUT:
                # Idempotent state answer: the input close is already running,
                # so the requested effect is in place. There is no second
                # transition, no second lifecycle event and no second ledger
                # operation.
                return ActivationDecision(
                    True, "no_change", self._closing_snapshot_locked(), False
                )
            return self._enter_close_barrier_locked(
                reason,
                cause,
                requested_by_command_id=command_id,
                requested_by_action=requested_by_action,
            )

    def _closing_snapshot_locked(self):
        return self._snapshot_locked()

    def _enter_close_barrier_locked(
        self,
        reason,
        cause,
        *,
        requested_by_command_id=None,
        requested_by_action=None,
    ):
        self._phase = CLOSING_INPUT
        self._close_context = CloseContext(
            reason=reason,
            cause=cause,
            requested_by_command_id=requested_by_command_id,
            requested_by_action=requested_by_action,
        )
        self._recovery_requested = False
        self._set_timer_locked(
            CLOSING_RECOVERY_DEADLINE,
            self._clock() + self._timing_locked().closing_recovery_timeout,
        )
        self._version += 1
        snapshot = self._snapshot_locked()
        return ActivationDecision(True, reason, snapshot, True)

    def audio_unavailable(self):
        """A generic loss of the input device cancels the open activation.

        The session itself and the background ledger survive; only the open
        foreground window is cancelled (DEVICE-03). The close is deliberately
        not command correlated (F7).
        """
        with self._lock:
            if self._phase == IDLE:
                return ActivationDecision(
                    False, "not_active", self._snapshot_locked()
                )
            if self._phase == CLOSING_INPUT:
                return ActivationDecision(
                    True, "no_change", self._closing_snapshot_locked(), False
                )
            return self._enter_close_barrier_locked(
                "cancelled", "audio_unavailable"
            )

    def input_closed(self, *, activation_id, activation_sequence):
        """Completes the close barrier after gate/recorder input is closed.

        Identity-bound: a stale close/recovery follow-up can never end the
        activation that now runs instead (F1/CMD identity). On mismatch no
        state is touched.
        """
        with self._lock:
            if self._phase != CLOSING_INPUT:
                return ActivationDecision(
                    False, "not_closing_input", self._snapshot_locked()
                )
            if (
                str(activation_id) != str(self._activation_id)
                or int(activation_sequence) != self._activation_sequence
            ):
                return ActivationDecision(
                    False, "stale_activation", self._snapshot_locked()
                )
            snapshot = self._clear_locked(close_context=self._close_context)
            return ActivationDecision(True, "input_closed", snapshot, True)

    # -- timer callbacks -----------------------------------------------------

    def tick(self, token):
        """The single entry point for every scheduled activation timer.

        A callback presents the token it was armed with. Anything that is not
        the current token - an older activation, an older revision, a phase
        that has moved on or a segment that has ended - is inert.
        """
        with self._lock:
            if not self._token_is_current_locked(token):
                return ActivationDecision(
                    False, "stale_timer", self._snapshot_locked()
                )
            if self._deadline is None:
                return ActivationDecision(
                    False, "not_expirable", self._snapshot_locked()
                )

            now = self._clock()
            if (
                self._warning_deadline is not None
                and not self._warning_fired
                and now >= self._warning_deadline
                and now < self._deadline
            ):
                # The warning moves no deadline, so it deliberately does not
                # raise ``timerRevision``: the same token stays valid for the
                # expiry that follows it.
                self._warning_fired = True
                self._version += 1
                return ActivationDecision(
                    True, "watchdog_warning", self._snapshot_locked(), True
                )

            if now < self._deadline:
                return ActivationDecision(
                    False, "not_due", self._snapshot_locked()
                )

            kind = self._deadline_kind
            if kind == CLOSING_RECOVERY_DEADLINE:
                return self._recover_closing_locked()
            if kind == SEGMENT_WATCHDOG_DEADLINE:
                # Recorded audio is processed regularly, the whole activation
                # is closed and no follow-up window is opened (TIME-08).
                return self._enter_close_barrier_locked(
                    "segment_watchdog_timeout", "segment_watchdog_timeout"
                )
            cause = (
                "initial_speech_timeout"
                if kind == INITIAL_SPEECH_DEADLINE
                else "followup_timeout"
            )
            return self._enter_close_barrier_locked("timed_out", cause)

    def _recover_closing_locked(self):
        """``closing_input`` must never hang - but the phase must not lie.

        The recovery deadline is consumed here, yet the foreground stays in
        ``closing_input`` with the same :class:`CloseContext`. The session
        runs the actual gate/recorder cleanup outside the lock and completes
        this close with the identity-bound :meth:`input_closed`; only that
        call transitions to ``idle`` (F1).
        """
        if self._phase != CLOSING_INPUT:
            return ActivationDecision(
                False, "not_closing_input", self._snapshot_locked()
            )
        self._clear_timer_locked()
        self._recovery_requested = True
        return ActivationDecision(
            True, "closing_recovery_due", self._snapshot_locked(), True
        )

    def reset(self):
        """Drops foreground state during stop, close or reconnect."""
        with self._lock:
            if self._phase == IDLE:
                return ActivationDecision(
                    True, "already_idle", self._snapshot_locked()
                )
            snapshot = self._clear_locked()
            return ActivationDecision(True, "reset", snapshot, True)

    def _clear_locked(self, close_context=None):
        closed_id = self._activation_id
        closed_primary = self._primary_source
        closed_settings = _thaw(self._effective_settings)
        closed_segments = self._segment_count
        closed_sequence = self._activation_sequence
        context = self._close_context if close_context is None else close_context

        self._activation_id = None
        self._primary_source = None
        self._effective_settings = _freeze({})
        self._timing_policy = None
        self._phase = IDLE
        self._clear_timer_locked()
        self._segment_count = 0
        self._close_context = None
        self._recovery_requested = False
        self._version += 1

        snapshot = self._snapshot_locked()
        snapshot.update(
            {
                "closedActivationId": closed_id,
                "closedActivationSequence": closed_sequence,
                "closedPrimarySource": closed_primary,
                "closedSources": [closed_primary] if closed_primary else [],
                "closedEffectiveSettings": closed_settings,
                "closedSegments": closed_segments,
            }
        )
        if context is not None:
            snapshot["closeReason"] = context.reason
            snapshot["closeCause"] = context.cause
            snapshot["closeRequestedByCommandId"] = (
                context.requested_by_command_id
            )
            snapshot["closeRequestedByAction"] = context.requested_by_action
        return snapshot