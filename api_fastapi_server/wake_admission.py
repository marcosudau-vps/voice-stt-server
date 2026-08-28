"""AP-SRV-060 wake admission: the seam between detection and activation.

The wake latch does **not** belong in the ``ActivationController``. AP-SRV-010
and AP-SRV-030 stay the one source-neutral activation authority: they know
``manual`` and ``wake_word`` only as equal trigger sources and must not learn a
wake-specific state. The path is therefore::

    RawWakeCandidate
      -> WakeDetectionEvaluator (detector hygiene)
      -> WakeAdmissionCoordinator (this module)
      -> ActivationController.activate(source="wake_word")

Only when the activation admission actually succeeds does the coordinator

* declare the detection fachlich accepted;
* set the wake latch;
* adopt the accepted ``activationId``;
* report exactly one ``wakeword.detected``.

On ``activation_locked``, on runtime suppression or on any other refusal there
is no event, no new latch, no second activation and no source merge. A wake
word spoken while an activation is already open therefore has no trigger,
finish, cancel or refresh effect at all - its audio is ordinary activation
audio.

The latch is released at the *safe input close* of the same activation - not at
VAD end, not at segment end, not when a final inference starts or ends, and not
when a cooldown expires.

The commit boundary (Root F7)
-----------------------------

``activate`` returns a :class:`WakeActivationOutcome`. Its ``committed`` flag
is the single, explicit commit point of the whole admission:

* **before** the commit nothing happened - a refusal or a guard means "no
  activation", and the coordinator answers ``None``;
* **after** the commit an activation really exists in the source-neutral
  activation authority. From that instant a failure may no longer be turned
  back into a refusal, because that would leave an open activation with no
  latch, no accepted detection and no event. Post-commit errors are carried in
  ``WakeActivationOutcome.error``, reported, and the admission still completes.

A raised exception is deliberately *not* trusted to mean "nothing happened".
Before treating it as a refusal the coordinator asks ``committed_probe`` what
the activation authority actually shows. If an activation is open, the commit
did happen and the admission completes as a post-commit failure - the crash
window Root described cannot leave an open activation without a latch.

The same rule applies to the ``wakeword.detected`` publication: a transport
failure after the latch was set must not unlatch it or invent a second
activation.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any, Optional

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
    committed = bool(getattr(value, "committed", None))
    if hasattr(value, "committed"):
        return WakeActivationOutcome(
            committed=committed,
            activation_id=getattr(value, "activation_id", None),
            error=getattr(value, "error", None),
        )
    # A plain activation id: committed by definition.
    return WakeActivationOutcome(committed=True, activation_id=str(value))


class WakeAdmissionCoordinator:
    """Turns one offered raw candidate into at most one accepted detection."""

    def __init__(self, *, evaluator, activate, publish=None,
                 committed_probe=None):
        #: The session's detector hygiene (threshold/tie/re-arm/latch state).
        self._evaluator = evaluator
        #: ``activate(candidate, boundary) -> WakeActivationOutcome``. The
        #: caller performs the real ``ActivationController.activate`` under the
        #: session lock; this module never touches activation state itself. The
        #: callable must not raise after its commit point - it reports a
        #: post-commit problem through ``WakeActivationOutcome.error``.
        self._activate = activate
        #: ``publish(AcceptedWakeDetection)`` - the single ``wakeword.detected``
        #: emission, routed through the existing lifecycle event funnel.
        self._publish = publish
        #: ``committed_probe() -> activation_id or None``. Asked only when
        #: ``activate`` raised, to find out whether the commit happened anyway.
        self._committed_probe = committed_probe
        self._lock = threading.RLock()
        self._accepted = None

    @property
    def evaluator(self):
        return self._evaluator

    @property
    def accepted_detection(self):
        with self._lock:
            return self._accepted

    def admit(self, candidate, boundary=None):
        """Runs one candidate through the activation admission.

        Returns the :class:`AcceptedWakeDetection`, or ``None`` when the
        admission refused it. ``None`` deliberately leaves *no* trace in the
        domain: the detector is only re-armed so the same utterance is not
        offered again chunk after chunk.
        """
        if candidate is None:
            return None
        with self._lock:
            try:
                outcome = _as_outcome(self._activate(candidate, boundary))
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
                self._evaluator.refuse(candidate)
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
                candidate,
                activation_id=outcome.activation_id,
                boundary=boundary,
            )
            self._accepted = detection
            if self._publish is not None:
                try:
                    self._publish(detection)
                except Exception:  # noqa: BLE001
                    # The detection happened and the latch belongs to a real
                    # activation; a transport failure must not undo either.
                    LOGGER.exception(
                        "wakeword.detected konnte für %s nicht veröffentlicht "
                        "werden; Activation und Latch bleiben bestehen",
                        outcome.activation_id,
                    )
            return detection

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

        Root F6: the implicit de-duplication window goes with it. A close
        without a latched detection (a refused hit) still clears that window,
        so an old refusal can never keep blocking a new legitimate utterance.
        """
        with self._lock:
            released = self._evaluator.release_latch(activation_id=activation_id)
            if released:
                self._accepted = None
            else:
                self._evaluator.clear_dedupe_window()
            return released

    def reset(self) -> int:
        """Starts a new detector generation; older callbacks become stale."""
        with self._lock:
            self._accepted = None
            return self._evaluator.new_generation()

    def diagnostics(self) -> dict:
        with self._lock:
            payload: dict[str, Any] = {"evaluator": self._evaluator.diagnostics()}
            payload["acceptedDetection"] = (
                self._accepted.event_fields() if self._accepted is not None else None
            )
            return payload
