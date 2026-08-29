"""Thread-safe background ledger for accepted final-transcription segments.

The foreground activation controller deliberately returns to ``idle`` as soon
as input is closed.  This module owns the independent, longer-lived accounting
for final jobs and releases useful results in session-wide segment order.
"""

from copy import deepcopy
from dataclasses import dataclass, field
import threading
import time
import uuid


SEGMENT_TERMINALS = frozenset({"completed", "discarded", "cancelled", "failed"})
ACTIVATION_TERMINALS = frozenset({"completed", "cancelled", "failed"})


def freeze_value(value):
    """Return detached immutable plain data suitable for a frozen context."""
    if isinstance(value, dict):
        return tuple(
            (str(key), freeze_value(item))
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        )
    if isinstance(value, (list, tuple)):
        return tuple(freeze_value(item) for item in value)
    if isinstance(value, set):
        return frozenset(freeze_value(item) for item in value)
    return deepcopy(value)


def thaw_value(value):
    if isinstance(value, tuple):
        if all(
            isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str)
            for item in value
        ):
            return {key: thaw_value(item) for key, item in value}
        return [thaw_value(item) for item in value]
    if isinstance(value, frozenset):
        return {thaw_value(item) for item in value}
    return deepcopy(value)


def normalize_segment_id(value):
    """The opaque segment identity, exactly as its owner created it.

    The ledger used to coerce to ``int`` because the only owner was the v1
    counter. A protocol v2 session creates canonical UUID segment ids at the
    same authoritative source, so the ledger keeps whatever that source
    produced and only refuses an empty identity. Integers and numeric strings
    keep their historical ``int`` form, so v1 correlation is unchanged.
    """
    if value is None or isinstance(value, bool):
        raise ValueError("segment_id must be a non-empty identity")
    if isinstance(value, int):
        return value
    text = str(value)
    if not text.strip():
        raise ValueError("segment_id must be a non-empty identity")
    try:
        return int(text)
    except ValueError:
        return text


@dataclass(frozen=True)
class SegmentContext:
    session_id: str
    activation_id: str
    activation_sequence: int
    #: ``int`` for the v1 counter, canonical UUID ``str`` for protocol v2.
    segment_id: object
    segment_sequence: int
    effective_settings: tuple
    request_id: str
    created_at: float


@dataclass(frozen=True)
class SegmentPublication:
    context: SegmentContext
    text: str


@dataclass(frozen=True)
class SegmentResolution:
    context: SegmentContext
    state: str
    reason: str


@dataclass(frozen=True)
class ActivationTerminal:
    activation_id: str
    activation_sequence: int
    state: str
    reason: str
    accepted_segment_count: int
    terminal_segment_count: int


@dataclass(frozen=True)
class LedgerUpdate:
    changed: bool = False
    resolutions: tuple = ()
    publications: tuple = ()
    activation_terminals: tuple = ()


@dataclass
class _SegmentRecord:
    context: SegmentContext
    prepared_text: str | None = None
    terminal_state: str | None = None
    terminal_reason: str = ""
    drained: bool = False


@dataclass
class _ActivationRecord:
    activation_id: str
    activation_sequence: int
    effective_settings: tuple
    accepted_sequences: list = field(default_factory=list)
    input_closed: bool = False
    close_reason: str = ""
    requested_terminal: str | None = None
    terminal_state: str | None = None


class SegmentLedger:
    """One session's activation/segment ledger and publication reorder buffer."""

    def __init__(self, session_id, clock=None, request_id_factory=None):
        self.session_id = session_id
        self._clock = clock or time.monotonic
        self._request_id_factory = request_id_factory or (lambda: uuid.uuid4().hex)
        self._lock = threading.RLock()
        self._next_segment_sequence = 1
        self._next_publish_sequence = 1
        self._activations = {}
        self._segments = {}
        self._accepted_segment_count = 0
        self._terminal_segment_count = 0
        self._terminal_activation_count = 0
        self._highest_activation_sequence = 0

    def open_activation(
        self,
        activation_id,
        activation_sequence,
        effective_settings=None,
    ):
        with self._lock:
            existing = self._activations.get(activation_id)
            if existing is not None:
                return False
            activation_sequence = int(activation_sequence)
            if activation_sequence <= self._highest_activation_sequence:
                return False
            self._activations[activation_id] = _ActivationRecord(
                activation_id=str(activation_id),
                activation_sequence=activation_sequence,
                effective_settings=freeze_value(effective_settings or {}),
            )
            self._highest_activation_sequence = activation_sequence
            return True

    def mark_cancel_requested(self, activation_id, reason):
        """Sets the per-activation cancel publication barrier.

        This is the *fachliche Annahme* of a cancel: from this instant on a
        later segment of this activation can never publish useful text, and
        text that was already computed but silently waiting behind a sequence
        hole is neutralised and terminalised as ``cancelled``.

        The method deliberately does **not** publish anything and does not
        call back into the session or the manager. It is expected to run under
        the caller's external ``_ledger_dispatch_lock``, and the returned
        :class:`LedgerUpdate` is applied visibly by the session under that same
        dispatch boundary *after* the foreground lock has been released.

        ``input_closed`` stays ``False`` here: the physical input close and the
        activation terminal are the responsibility of
        :meth:`close_activation` once the barrier has been set.
        """
        with self._lock:
            activation = self._activations.get(activation_id)
            if activation is None:
                return LedgerUpdate()
            if activation.requested_terminal == "cancelled":
                # Idempotent: the barrier is already set (F-cancel idempotency).
                return LedgerUpdate()
            activation.requested_terminal = "cancelled"
            cancel_reason = str(reason or "cancelled")
            if not activation.close_reason:
                activation.close_reason = cancel_reason

            changed = False
            resolutions = []
            for sequence in activation.accepted_sequences:
                segment = self._segments[sequence]
                if segment.drained:
                    continue
                if (
                    segment.terminal_state is None
                    or segment.prepared_text is not None
                ):
                    segment.prepared_text = None
                    if segment.terminal_state is None:
                        self._terminal_segment_count += 1
                    segment.terminal_state = "cancelled"
                    segment.terminal_reason = cancel_reason
                    resolutions.append(
                        SegmentResolution(
                            segment.context, "cancelled", cancel_reason
                        )
                    )
                    changed = True

            publications = self._drain_locked()
            terminals = self._terminalize_activations_locked()
            return LedgerUpdate(
                changed=changed,
                resolutions=tuple(resolutions),
                publications=tuple(publications),
                activation_terminals=tuple(terminals),
            )

    def accept_segment(self, activation_id, segment_id):
        with self._lock:
            activation = self._activations.get(activation_id)
            if activation is None:
                raise KeyError(f"unknown activation: {activation_id}")
            if activation.input_closed:
                raise RuntimeError("activation input is already closed")
            if activation.requested_terminal == "cancelled":
                # A recorder callback that loses the cancel race must not
                # register a new segment behind the barrier (C2). The physical
                # close may still be running, so ``input_closed`` can be False
                # while the barrier is already effective.
                raise RuntimeError("activation input is cancelled")
            sequence = self._next_segment_sequence
            self._next_segment_sequence += 1
            context = SegmentContext(
                session_id=self.session_id,
                activation_id=activation.activation_id,
                activation_sequence=activation.activation_sequence,
                segment_id=normalize_segment_id(segment_id),
                segment_sequence=sequence,
                effective_settings=activation.effective_settings,
                request_id=self._request_id_factory(),
                created_at=self._clock(),
            )
            self._segments[sequence] = _SegmentRecord(context=context)
            activation.accepted_sequences.append(sequence)
            self._accepted_segment_count += 1
            return context

    def close_activation(
        self,
        activation_id,
        reason,
        *,
        requested_terminal=None,
        cancel_pending=False,
    ):
        if (
            requested_terminal is not None
            and requested_terminal not in ACTIVATION_TERMINALS
        ):
            raise ValueError(f"invalid activation terminal: {requested_terminal}")
        with self._lock:
            activation = self._activations.get(activation_id)
            if activation is None:
                return LedgerUpdate()
            changed = not activation.input_closed
            activation.input_closed = True
            activation.close_reason = activation.close_reason or str(
                reason or "input_closed"
            )
            if requested_terminal is not None:
                activation.requested_terminal = requested_terminal
            resolutions = []
            if cancel_pending:
                for sequence in activation.accepted_sequences:
                    segment = self._segments[sequence]
                    if segment.drained:
                        continue
                    if (
                        segment.terminal_state is None
                        or segment.prepared_text is not None
                    ):
                        segment.prepared_text = None
                        if segment.terminal_state is None:
                            self._terminal_segment_count += 1
                        segment.terminal_state = "cancelled"
                        segment.terminal_reason = activation.close_reason
                        resolutions.append(
                            SegmentResolution(
                                segment.context, "cancelled", segment.terminal_reason
                            )
                        )
                        changed = True
            publications = self._drain_locked()
            terminals = self._terminalize_activations_locked()
            return LedgerUpdate(
                changed=changed,
                resolutions=tuple(resolutions),
                publications=tuple(publications),
                activation_terminals=tuple(terminals),
            )

    def resolve_completed(self, context, text):
        text = str(text or "").strip()
        if not text:
            return self.resolve_terminal(context, "discarded", "empty_final")
        with self._lock:
            segment = self._matching_pending_locked(context)
            if segment is None or segment.prepared_text is not None:
                return LedgerUpdate()
            activation = self._activations.get(context.activation_id)
            if activation is not None and activation.requested_terminal == "cancelled":
                # The cancel barrier is already set. Text that finishes after
                # the cancel must never be prepared or published: it is
                # terminalised exactly once as ``cancelled`` (C2). The segment
                # itself is still pending, so this also keeps drain correct.
                segment.prepared_text = None
                self._terminal_segment_count += 1
                segment.terminal_state = "cancelled"
                segment.terminal_reason = activation.close_reason or "cancelled"
                resolution = SegmentResolution(
                    context, "cancelled", segment.terminal_reason
                )
                publications = self._drain_locked()
                terminals = self._terminalize_activations_locked()
                return LedgerUpdate(
                    changed=True,
                    resolutions=(resolution,),
                    publications=tuple(publications),
                    activation_terminals=tuple(terminals),
                )
            segment.prepared_text = text
            publications = self._drain_locked()
            terminals = self._terminalize_activations_locked()
            return LedgerUpdate(
                changed=True,
                resolutions=(),
                publications=tuple(publications),
                activation_terminals=tuple(terminals),
            )

    def resolve_terminal(self, context, state, reason):
        if state not in SEGMENT_TERMINALS - {"completed"}:
            raise ValueError(f"invalid non-publication terminal: {state}")
        with self._lock:
            segment = self._matching_pending_locked(context)
            if segment is None or segment.prepared_text is not None:
                return LedgerUpdate()
            segment.terminal_state = state
            segment.terminal_reason = str(reason or state)
            self._terminal_segment_count += 1
            resolution = SegmentResolution(context, state, segment.terminal_reason)
            publications = self._drain_locked()
            terminals = self._terminalize_activations_locked()
            return LedgerUpdate(
                changed=True,
                resolutions=(resolution,),
                publications=tuple(publications),
                activation_terminals=tuple(terminals),
            )

    def cancel_all(self, reason):
        resolutions = []
        changed = False
        with self._lock:
            terminal_reason = str(reason or "cancelled")
            # This is one session-wide abort barrier: first mark every
            # activation and every unpublished/prepared segment cancelled.
            # Only then may the reorder head move. Per-activation draining
            # would let prepared text from a later activation escape between
            # two cancellation steps.
            for activation in self._activations.values():
                changed = changed or not activation.input_closed
                activation.input_closed = True
                activation.close_reason = terminal_reason
                activation.requested_terminal = "cancelled"

            for segment in self._segments.values():
                if segment.drained:
                    continue
                if (
                    segment.terminal_state is None
                    or segment.prepared_text is not None
                ):
                    segment.prepared_text = None
                    if segment.terminal_state is None:
                        self._terminal_segment_count += 1
                    segment.terminal_state = "cancelled"
                    segment.terminal_reason = terminal_reason
                    resolutions.append(
                        SegmentResolution(
                            segment.context,
                            "cancelled",
                            terminal_reason,
                        )
                    )
                    changed = True

            publications = self._drain_locked()
            terminals = self._terminalize_activations_locked()
            return LedgerUpdate(
                changed=changed,
                resolutions=tuple(resolutions),
                publications=tuple(publications),
                activation_terminals=tuple(terminals),
            )

    def context_for_request(self, request_id):
        with self._lock:
            for record in self._segments.values():
                if record.context.request_id == request_id:
                    return record.context
        return None

    def snapshot(self):
        with self._lock:
            pending = [
                record for record in self._segments.values()
                if record.terminal_state is None
            ]
            return {
                "nextSegmentSequence": self._next_segment_sequence,
                "nextPublishSequence": self._next_publish_sequence,
                "pendingSegmentCount": len(pending),
                "acceptedSegmentCount": self._accepted_segment_count,
                "terminalSegmentCount": self._terminal_segment_count,
                "terminalActivationCount": self._terminal_activation_count,
                "pendingActivationCount": len(self._activations),
                "activations": [
                    {
                        "activationId": record.activation_id,
                        "activationSequence": record.activation_sequence,
                        "inputClosed": record.input_closed,
                        # Exported for the v2 snapshot: the reason is already
                        # recorded by ``close_activation``; the projection only
                        # needs to read it.
                        "inputClosedReason": record.close_reason or None,
                        "acceptedSegmentCount": len(record.accepted_sequences),
                        "terminalSegmentCount": sum(
                            self._segments[sequence].terminal_state is not None
                            for sequence in record.accepted_sequences
                        ),
                        "state": record.terminal_state or "draining",
                    }
                    for record in self._activations.values()
                ],
            }

    def accepted_segment_count(self, activation_id):
        """Accepted segments of one activation, or ``0`` when it is unknown.

        Read before an activation is closed, so the exactly-once input-close
        record can carry the count even when closing terminalises the
        activation immediately and drops its record.
        """
        with self._lock:
            record = self._activations.get(activation_id)
            if record is None:
                return 0
            return len(record.accepted_sequences)

    def _matching_pending_locked(self, context):
        if (
            not isinstance(context, SegmentContext)
            or context.session_id != self.session_id
        ):
            return None
        segment = self._segments.get(context.segment_sequence)
        if (
            segment is None
            or segment.context != context
            or segment.terminal_state is not None
        ):
            return None
        return segment

    def _drain_locked(self):
        publications = []
        while True:
            segment = self._segments.get(self._next_publish_sequence)
            if segment is None:
                break
            if segment.terminal_state is None:
                if segment.prepared_text is None:
                    break
                segment.terminal_state = "completed"
                segment.terminal_reason = "published"
                self._terminal_segment_count += 1
            segment.drained = True
            if segment.terminal_state == "completed":
                text = segment.prepared_text or ""
                publications.append(
                    SegmentPublication(segment.context, text)
                )
                segment.prepared_text = None
            self._next_publish_sequence += 1
        return publications

    def _terminalize_activations_locked(self):
        terminals = []
        finished_ids = []
        for activation in self._activations.values():
            if activation.terminal_state is not None or not activation.input_closed:
                continue
            records = [
                self._segments[sequence]
                for sequence in activation.accepted_sequences
            ]
            if any(
                record.terminal_state is None or not record.drained
                for record in records
            ):
                continue
            state = activation.requested_terminal
            if state is None:
                states = {record.terminal_state for record in records}
                if "failed" in states:
                    state = "failed"
                elif "cancelled" in states:
                    state = "cancelled"
                else:
                    state = "completed"
            activation.terminal_state = state
            self._terminal_activation_count += 1
            terminals.append(
                ActivationTerminal(
                    activation.activation_id,
                    activation.activation_sequence,
                    state,
                    activation.close_reason,
                    len(records),
                    len(records),
                )
            )
            finished_ids.append(activation.activation_id)
        for activation_id in finished_ids:
            activation = self._activations.pop(activation_id)
            for sequence in activation.accepted_sequences:
                self._segments.pop(sequence, None)
        return terminals
