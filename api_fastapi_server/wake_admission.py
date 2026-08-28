"""AP-SRV-060 wake admission: the seam between detection and activation.

The wake latch does **not** belong in the ``ActivationController``. AP-SRV-010
and AP-SRV-030 stay the one source-neutral activation authority: they know
``manual`` and ``wake_word`` only as equal trigger sources and must not learn a
wake-specific state. The path is therefore::

    prediction frames
      -> WakeHitTracker            (threshold, minimum run, trailing edge)
      -> WakeDetectionEvaluator    (latch, operator cooldown)
      -> WakeAdmissionCoordinator  (this module)
      -> ActivationController.activate(source="wake_word")

Only when the activation admission actually succeeds does the coordinator

* declare the hit fachlich accepted;
* set the wake latch;
* adopt the accepted ``activationId``;
* **mint exactly one logical** ``wakeword.detected``.

On ``activation_locked``, on runtime suppression or on any other refusal there
is no event, no new latch, no second activation and no source merge. A wake
word spoken while an activation is already open therefore has no trigger,
finish, cancel or refresh effect at all - its audio is ordinary activation
audio.

The commit boundary (Root F7)
-----------------------------

``activate`` returns a :class:`WakeActivationOutcome`. Its ``committed`` flag
is the single, explicit commit point of the whole admission:

* **before** the commit nothing happened - a refusal or a guard means "no
  activation", and the coordinator answers ``None``;
* **after** the commit an activation really exists in the source-neutral
  activation authority. From that instant a failure may no longer be turned
  back into a refusal.

A raised exception is deliberately *not* trusted to mean "nothing happened".
Before treating it as a refusal the coordinator asks ``committed_probe`` what
the activation authority actually shows.

Exactly-once logical eventing (Root F13)
-----------------------------------------

C2 could keep an activation and a latch while the publish callback threw, which
left a state with an accepted detection, an activation and a latch but **zero**
logical ``wakeword.detected`` events.

C3 separates the two steps that C2 fused:

logical mint
    :class:`LogicalWakeEventLedger` reserves exactly one logical event per
    accepted wake hit. It is pure in-memory bookkeeping under the coordinator's
    lock, it cannot fail on a network, and it is idempotent per activation, so
    a retry can never mint a second event;
transport delivery
    a separate, explicitly fallible step. It may succeed, fail, or be picked up
    later by the existing resync/replay/close semantics of AP-SRV-040. Root does
    not ask for infallible networks - it asks that the *logical* event exists
    exactly once.

There is no second event authority here: the minted record is handed to the one
existing lifecycle event funnel of the session.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

LOGGER = logging.getLogger("voicestt")


@dataclass(frozen=True)
class WakeActivationOutcome:
    """What one activation attempt did, and whether it reached its commit."""

    committed: bool
    activation_id: Optional[str] = None
    error: Optional[BaseException] = None

    @classmethod
    def refused(cls) -> "WakeActivationOutcome":
        return cls(committed=False)


def _as_outcome(value: Any) -> WakeActivationOutcome:
    """Accepts an outcome, a bare activation id or ``None``."""
    if isinstance(value, WakeActivationOutcome):
        return value
    if value is None:
        return WakeActivationOutcome.refused()
    if hasattr(value, "committed"):
        return WakeActivationOutcome(
            committed=bool(getattr(value, "committed", None)),
            activation_id=getattr(value, "activation_id", None),
            error=getattr(value, "error", None),
        )
    # A plain activation id: committed by definition.
    return WakeActivationOutcome(committed=True, activation_id=str(value))


@dataclass
class LogicalWakeEvent:
    """One minted logical ``wakeword.detected``.

    ``delivered`` describes the *transport*, never the logical existence: an
    undelivered event still happened exactly once and must never be minted a
    second time.
    """

    event_id: str
    wake_word_id: str
    activation_id: str
    score: float
    sequence: int
    delivered: bool = False
    delivery_attempts: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eventId": self.event_id,
            "wakeWordId": self.wake_word_id,
            "activationId": self.activation_id,
            "score": float(self.score),
            "sequence": int(self.sequence),
            "delivered": bool(self.delivered),
            "deliveryAttempts": int(self.delivery_attempts),
        }


class LogicalWakeEventLedger:
    """The exactly-once mint of logical wake events for one session.

    Minting is keyed on the accepted ``activationId``: one accepted wake hit
    opens exactly one activation, so a second mint for the same activation is a
    duplicate by definition and returns the existing record instead.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._events: List[LogicalWakeEvent] = []
        self._by_activation: Dict[str, LogicalWakeEvent] = {}

    @property
    def events(self) -> Tuple[LogicalWakeEvent, ...]:
        with self._lock:
            return tuple(self._events)

    def count(self, activation_id: Optional[str] = None) -> int:
        """How many logical events exist, in total or for one activation."""
        with self._lock:
            if activation_id is None:
                return len(self._events)
            return 1 if str(activation_id) in self._by_activation else 0

    def get(self, activation_id: str) -> Optional[LogicalWakeEvent]:
        with self._lock:
            return self._by_activation.get(str(activation_id))

    def mint(self, detection) -> LogicalWakeEvent:
        """Reserves the one logical event of one accepted wake hit."""
        activation_id = str(detection.activation_id)
        with self._lock:
            existing = self._by_activation.get(activation_id)
            if existing is not None:
                return existing
            event = LogicalWakeEvent(
                event_id=str(uuid.uuid4()),
                wake_word_id=str(detection.canonical_wake_word_id),
                activation_id=activation_id,
                score=float(detection.score),
                sequence=len(self._events) + 1,
            )
            self._events.append(event)
            self._by_activation[activation_id] = event
            return event

    def mark_delivered(self, event: LogicalWakeEvent) -> None:
        with self._lock:
            event.delivered = True

    def mark_delivery_attempt(self, event: LogicalWakeEvent) -> None:
        with self._lock:
            event.delivery_attempts += 1

    def undelivered(self) -> Tuple[LogicalWakeEvent, ...]:
        with self._lock:
            return tuple(event for event in self._events if not event.delivered)

    def diagnostics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "logicalEventCount": len(self._events),
                "undeliveredCount": sum(
                    1 for event in self._events if not event.delivered
                ),
                "events": [event.to_dict() for event in self._events],
            }


class WakeAdmissionCoordinator:
    """Turns one finalized wake hit into at most one accepted detection."""

    def __init__(self, *, evaluator, activate, deliver=None, publish=None,
                 committed_probe=None, ledger=None):
        #: The session's wake gate (tracker, latch, operator cooldown).
        self._evaluator = evaluator
        #: ``activate(hit, boundary) -> WakeActivationOutcome``. The caller
        #: performs the real ``ActivationController.activate`` under the session
        #: lock; this module never touches activation state itself.
        self._activate = activate
        #: ``deliver(LogicalWakeEvent, AcceptedWakeDetection)`` - the fallible
        #: transport step, routed through the existing lifecycle event funnel.
        #: ``publish(detection)`` is the historical single-argument form.
        if deliver is None and publish is not None:
            deliver = lambda event, detection: publish(detection)  # noqa: E731
        self._deliver = deliver
        #: ``committed_probe() -> activation_id or None``. Asked only when
        #: ``activate`` raised, to find out whether the commit happened anyway.
        self._committed_probe = committed_probe
        self._ledger = ledger if ledger is not None else LogicalWakeEventLedger()
        self._lock = threading.RLock()
        self._accepted = None
        self._minted: Optional[LogicalWakeEvent] = None

    @property
    def evaluator(self):
        return self._evaluator

    @property
    def ledger(self) -> LogicalWakeEventLedger:
        return self._ledger

    @property
    def accepted_detection(self):
        with self._lock:
            return self._accepted

    def logical_event_count(self, activation_id: Optional[str] = None) -> int:
        return self._ledger.count(activation_id)

    def admit(self, hit, boundary=None):
        """Runs one finalized wake hit through the activation admission.

        Returns the ``AcceptedWakeDetection``, or ``None`` when the admission
        refused it. ``None`` deliberately leaves *no* trace in the domain: no
        latch, no activation, no logical event.
        """
        if hit is None:
            return None
        with self._lock:
            try:
                outcome = _as_outcome(self._activate(hit, boundary))
            except Exception as exc:  # noqa: BLE001
                # Never assume a raise means "nothing happened": ask the
                # activation authority what it really shows.
                committed_id = self._probe_committed()
                if committed_id:
                    LOGGER.exception(
                        "Wake-Admission hat nach dem Commit von %s geworfen; "
                        "die Activation bleibt bestehen",
                        committed_id,
                    )
                    outcome = WakeActivationOutcome(
                        committed=True, activation_id=committed_id, error=exc
                    )
                else:
                    LOGGER.exception(
                        "Wake-Admission ist vor dem Commit fehlgeschlagen: %s",
                        exc,
                    )
                    outcome = WakeActivationOutcome.refused()

            if not outcome.committed or not outcome.activation_id:
                self._evaluator.refuse(hit)
                self._accepted = None
                return None

            if outcome.error is not None:
                # Post-commit problem: the activation exists and stays. It is
                # reported, never converted into a refusal.
                LOGGER.error(
                    "Wake-Activation %s wurde übernommen, aber ein Folgeschritt "
                    "ist fehlgeschlagen: %s",
                    outcome.activation_id,
                    outcome.error,
                )

            detection = self._evaluator.accept(
                hit,
                activation_id=outcome.activation_id,
                boundary=boundary,
            )
            self._accepted = detection
            # --- exactly-once logical mint --------------------------------
            # This happens before any fallible transport and cannot fail, so an
            # accepted hit can never end up with zero logical events.
            event = self._ledger.mint(detection)
            self._minted = event
            self._attempt_delivery(event, detection)
            return detection

    def _attempt_delivery(self, event: LogicalWakeEvent, detection) -> bool:
        """One fallible transport attempt of an already minted event."""
        if self._deliver is None:
            return False
        self._ledger.mark_delivery_attempt(event)
        try:
            self._deliver(event, detection)
        except Exception:  # noqa: BLE001
            # The logical event happened and the latch belongs to a real
            # activation; a transport failure must not undo either, and it must
            # not mint a second event on the retry.
            LOGGER.exception(
                "wakeword.detected konnte für %s nicht zugestellt werden; "
                "Activation, Latch und das logische Event bleiben bestehen",
                event.activation_id,
            )
            return False
        self._ledger.mark_delivered(event)
        return True

    def redeliver(self) -> bool:
        """Retries the transport of the already minted event.

        Returns ``True`` when this call delivered the event. It never mints,
        and an already delivered event is a no-op rather than a duplicate.
        """
        with self._lock:
            event = self._minted
            detection = self._accepted
            if event is None or event.delivered:
                return False
            return self._attempt_delivery(event, detection)

    def _probe_committed(self) -> Optional[str]:
        """The activation the authority really shows, if any."""
        probe = self._committed_probe
        if probe is None:
            return None
        try:
            value = probe()
        except Exception:  # noqa: BLE001 - a probe must not mask the original
            LOGGER.exception("Commit-Probe der Wake-Admission ist gescheitert")
            return None
        return str(value) if value else None

    def release(self, activation_id: Optional[str] = None) -> bool:
        """Releases the latch at the safe input close of that activation.

        The minted logical events stay in the ledger: closing a session does
        not un-happen an event that already existed, and it must not open the
        door to a second one for the same wake hit.
        """
        with self._lock:
            released = self._evaluator.release_latch(activation_id=activation_id)
            if released:
                self._accepted = None
            return released

    def reset(self) -> int:
        """Starts a new detector generation; older callbacks become stale."""
        with self._lock:
            self._accepted = None
            self._minted = None
            return self._evaluator.new_generation()

    def diagnostics(self) -> dict:
        with self._lock:
            payload: Dict[str, Any] = {"evaluator": self._evaluator.diagnostics()}
            payload["acceptedDetection"] = (
                self._accepted.event_fields() if self._accepted is not None else None
            )
            payload["logicalEvents"] = self._ledger.diagnostics()
            return payload
