"""Thread-safe recorder activation gates.

The legacy recorder opens on VAD (or on a detected wake word). Controlled
sessions keep the same audio/VAD pipeline, but require an explicit manual or
wake-word gate before VAD may start a recording.

In the controlled policy the gate is the *only* authority that may allow the
recorder to start a segment. The recorder deliberately does not know which
trigger source opened the gate; it only knows "open" or "closed".

Every gate operation is bound to an ``(activation_id, generation)`` pair. The
generation is a monotonically increasing counter owned by the server-side
``ActivationController``. Binding both values makes late operations from an
already-replaced activation harmless: a stale ``close`` can never close a newer
activation, and a stale ``open`` can never re-open or replace a newer one.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional


LEGACY_ACTIVATION_POLICY = "legacy"
CONTROLLED_ACTIVATION_POLICY = "controlled"
ACTIVATION_POLICIES = {
    LEGACY_ACTIVATION_POLICY,
    CONTROLLED_ACTIVATION_POLICY,
}


def initialize_activation_control(recorder):
    recorder.activation_policy = LEGACY_ACTIVATION_POLICY
    recorder._controlled_activation_lock = threading.RLock()
    recorder._controlled_activation_event = threading.Event()
    recorder._controlled_activation_id = None
    recorder._controlled_activation_generation = 0
    recorder._controlled_recording_activation_id = None
    recorder._controlled_recording_activation_generation = 0
    recorder._controlled_activation_shutdown = False


def _ensure_initialized(recorder):
    """Older recorder fakes may predate the generation fields."""
    if not hasattr(recorder, "_controlled_activation_generation"):
        recorder._controlled_activation_generation = 0
    if not hasattr(recorder, "_controlled_activation_shutdown"):
        recorder._controlled_activation_shutdown = False
    if not hasattr(recorder, "_controlled_recording_activation_id"):
        recorder._controlled_recording_activation_id = None
    if not hasattr(recorder, "_controlled_recording_activation_generation"):
        recorder._controlled_recording_activation_generation = 0


def configure_activation_policy(recorder, policy):
    normalized = str(policy or "").strip().lower()
    if normalized not in ACTIVATION_POLICIES:
        supported = ", ".join(sorted(ACTIVATION_POLICIES))
        raise ValueError(
            f"activation policy must be one of: {supported}"
        )
    with recorder._controlled_activation_lock:
        _ensure_initialized(recorder)
        recorder.activation_policy = normalized
        if normalized != CONTROLLED_ACTIVATION_POLICY:
            recorder._controlled_activation_id = None
            recorder._controlled_recording_activation_id = None
            recorder._controlled_recording_activation_generation = 0
            recorder._controlled_activation_event.clear()
    return recorder


def open_controlled_activation_gate(
    recorder,
    activation_id,
    replace=False,
    generation=None,
):
    """Opens the gate for one activation.

    Returns ``True`` when the gate is open for ``activation_id`` afterwards.

    Rejected (``False``) when:

    - another activation currently holds the gate and ``replace`` is not set;
    - the caller's ``generation`` is older than the generation that currently
      holds the gate (a stale open must never replace a newer activation);
    - the gate has been shut down.
    """
    normalized_id = str(activation_id or "").strip()
    if not normalized_id:
        raise ValueError("activation_id must be a non-empty string")
    if recorder.activation_policy != CONTROLLED_ACTIVATION_POLICY:
        raise RuntimeError(
            "controlled activation requires the controlled activation policy"
        )
    with recorder._controlled_activation_lock:
        _ensure_initialized(recorder)
        if recorder._controlled_activation_shutdown:
            return False
        existing_id = recorder._controlled_activation_id
        existing_generation = recorder._controlled_activation_generation
        if generation is not None and generation < existing_generation:
            return False
        if existing_id not in {None, normalized_id} and not replace:
            return False
        recorder._controlled_activation_id = normalized_id
        if generation is not None:
            recorder._controlled_activation_generation = generation
        recorder._controlled_activation_event.set()
        return True


def close_controlled_activation_gate(
    recorder,
    activation_id=None,
    generation=None,
):
    """Closes the gate if the caller still owns it.

    Returns ``True`` when this call actually closed an open gate. Closing an
    already closed gate is idempotent and returns ``False`` without side
    effects.
    """
    normalized_id = (
        None if activation_id is None else str(activation_id).strip()
    )
    with recorder._controlled_activation_lock:
        _ensure_initialized(recorder)
        existing_id = recorder._controlled_activation_id
        existing_generation = recorder._controlled_activation_generation
        if normalized_id is not None and existing_id != normalized_id:
            return False
        if generation is not None and generation < existing_generation:
            return False
        recorder._controlled_activation_id = None
        recorder._controlled_activation_event.clear()
        return existing_id is not None


def abort_controlled_activation_gate(recorder):
    """Unconditionally closes the gate and leaves a deterministic state."""
    with recorder._controlled_activation_lock:
        _ensure_initialized(recorder)
        was_open = recorder._controlled_activation_id is not None
        recorder._controlled_activation_id = None
        recorder._controlled_activation_event.clear()
        return was_open


def shutdown_controlled_activation_gate(recorder):
    """Closes the gate permanently; later opens are refused."""
    with recorder._controlled_activation_lock:
        _ensure_initialized(recorder)
        was_open = recorder._controlled_activation_id is not None
        recorder._controlled_activation_shutdown = True
        recorder._controlled_activation_id = None
        recorder._controlled_activation_event.clear()
        return was_open


def controlled_activation_snapshot(recorder):
    with recorder._controlled_activation_lock:
        _ensure_initialized(recorder)
        return {
            "policy": recorder.activation_policy,
            "active": recorder._controlled_activation_event.is_set(),
            "activationId": recorder._controlled_activation_id,
            "generation": recorder._controlled_activation_generation,
            "shutdown": recorder._controlled_activation_shutdown,
        }


def controlled_recording_activation_snapshot(recorder):
    """Returns the activation token latched when recording admission won."""
    with recorder._controlled_activation_lock:
        _ensure_initialized(recorder)
        return {
            "activationId": recorder._controlled_recording_activation_id,
            "generation": recorder._controlled_recording_activation_generation,
        }


def recording_activation_gate_is_open(
    recorder,
    *,
    wake_word_activation_delay_passed,
):
    """Decides whether VAD may start a recording."""
    if recorder.activation_policy == CONTROLLED_ACTIVATION_POLICY:
        with recorder._controlled_activation_lock:
            _ensure_initialized(recorder)
            if not recorder._controlled_activation_event.is_set():
                return False
            recorder._controlled_recording_activation_id = (
                recorder._controlled_activation_id
            )
            recorder._controlled_recording_activation_generation = (
                recorder._controlled_activation_generation
            )
            return True
    if recorder.wakeword_detected:
        return True
    return (
        (
            not recorder.use_wake_words
            or not wake_word_activation_delay_passed
        )
        and recorder.start_recording_on_voice_activity
    )
