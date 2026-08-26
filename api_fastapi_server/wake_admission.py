"""
Server-side Wake Admission Coordinator and domain latch management.

Coordinates raw wake-word detections with the server-authoritative
ActivationController, managing the domain latch lifecycle:
- Only an accepted activation admission engages the domain latch.
- Subsequent hits during an open activation or input-close are suppressed.
- The latch is released on canonical SRV-030 safe input close (REQUIRES_FINAL_SRV_030_BINDING).
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import threading
from typing import Any, Callable, Dict, Optional, Tuple

from VoiceSTT.core.wakeword import WakeWordDetection
from .activation import (
    ActivationController,
    ActivationDecision,
    IDLE,
    WAKE_WORD_SOURCE,
)

logger = logging.getLogger("voicestt.wake_admission")


@dataclass(frozen=True)
class AcceptedWakeAdmission:
    """Represents a successfully admitted wake-word trigger."""

    decision: ActivationDecision
    detection: WakeWordDetection
    activation_id: str
    generation: int
    wake_word_id: str
    score: float


class WakeAdmissionCoordinator:
    """
    Coordinates wake-word detections with the ActivationController.
    Enforces atomic domain latch semantics across the activation lifecycle.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._latch_active = False
        self._latched_activation_id: Optional[str] = None
        self._latched_generation: int = 0
        self._latched_wake_word_id: Optional[str] = None

    @property
    def is_latched(self) -> bool:
        with self._lock:
            return self._latch_active

    @property
    def latched_activation_id(self) -> Optional[str]:
        with self._lock:
            return self._latched_activation_id

    def handle_wake_detection(
        self,
        detection: WakeWordDetection,
        activation_controller: Optional[ActivationController],
        settings_supplier: Optional[Callable[[], Any]] = None,
    ) -> Optional[AcceptedWakeAdmission]:
        """
        Evaluates a raw wake detection against domain admission rules.

        Returns AcceptedWakeAdmission if and only if the ActivationController
        accepts the wake-word trigger, engaging the domain latch.
        """
        if detection is None:
            return None

        with self._lock:
            if activation_controller is None:
                return None

            # If latch is already active:
            # Domain event suppressed, no second activation attempt.
            if self._latch_active:
                logger.debug(
                    "Wake detection for '%s' suppressed by active domain latch (activation %s)",
                    detection.wake_word_id,
                    self._latched_activation_id,
                )
                return None

            snapshot = activation_controller.snapshot()
            if snapshot.get("active", False):
                logger.debug(
                    "Wake detection for '%s' suppressed: ActivationController is active (phase '%s')",
                    detection.wake_word_id,
                    snapshot.get("phase"),
                )
                return None

            settings = settings_supplier() if settings_supplier else None
            decision = activation_controller.activate(WAKE_WORD_SOURCE, settings)

            if not decision.accepted:
                logger.debug(
                    "Wake detection for '%s' rejected by ActivationController: reason=%s",
                    detection.wake_word_id,
                    decision.reason,
                )
                return None

            # Successfully admitted: engage domain latch
            act_id = decision.snapshot.get("activationId", "")
            gen = decision.snapshot.get("generation", 0)

            self._latch_active = True
            self._latched_activation_id = act_id
            self._latched_generation = gen
            self._latched_wake_word_id = detection.wake_word_id

            logger.info(
                "Wake trigger accepted: id=%s, score=%.4f, activationId=%s (gen %d)",
                detection.wake_word_id,
                detection.score,
                act_id,
                gen,
            )

            return AcceptedWakeAdmission(
                decision=decision,
                detection=detection,
                activation_id=act_id,
                generation=gen,
                wake_word_id=detection.wake_word_id,
                score=detection.score,
            )

    def release_latch(
        self,
        activation_id: Optional[str] = None,
        generation: Optional[int] = None,
    ) -> bool:
        """
        Releases the domain latch on safe input close or unlock.
        (REQUIRES_FINAL_SRV_030_BINDING)
        """
        with self._lock:
            if not self._latch_active:
                return False

            if activation_id is not None and self._latched_activation_id is not None:
                if activation_id != self._latched_activation_id:
                    return False

            if generation is not None and generation < self._latched_generation:
                return False

            self._latch_active = False
            self._latched_activation_id = None
            self._latched_generation = 0
            self._latched_wake_word_id = None
            return True

    def reset(self):
        """Unconditionally resets domain latch state upon session close/reset."""
        with self._lock:
            self._latch_active = False
            self._latched_activation_id = None
            self._latched_generation = 0
            self._latched_wake_word_id = None
