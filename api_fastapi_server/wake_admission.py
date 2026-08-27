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
"""

from __future__ import annotations

import threading
from typing import Any, Optional


class WakeAdmissionCoordinator:
    """Turns one offered raw candidate into at most one accepted detection."""

    def __init__(self, *, evaluator, activate, publish=None):
        #: The session's detector hygiene (threshold/tie/re-arm/latch state).
        self._evaluator = evaluator
        #: ``activate(candidate, boundary) -> activation_id or None``. The
        #: caller performs the real ``ActivationController.activate`` under the
        #: session lock; this module never touches activation state itself.
        self._activate = activate
        #: ``publish(AcceptedWakeDetection)`` - the single ``wakeword.detected``
        #: emission, routed through the existing lifecycle event funnel.
        self._publish = publish
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
            activation_id = None
            try:
                activation_id = self._activate(candidate, boundary)
            except Exception:  # noqa: BLE001 - a detector must not break the session
                activation_id = None
            if not activation_id:
                self._evaluator.refuse(candidate)
                self._accepted = None
                return None

            detection = self._evaluator.accept(
                candidate, activation_id=activation_id, boundary=boundary
            )
            self._accepted = detection
            if self._publish is not None:
                self._publish(detection)
            return detection

    def release(self, activation_id: Optional[str] = None) -> bool:
        """Releases the latch at the safe input close of that activation."""
        with self._lock:
            released = self._evaluator.release_latch(activation_id=activation_id)
            if released:
                self._accepted = None
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
