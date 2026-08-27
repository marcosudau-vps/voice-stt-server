"""``session.snapshot`` - the server-authoritative resync view.

The snapshot is a pure projection. Every value it publishes is read from the
authority that already owns it:

``input``
    the AP-SRV-030 :class:`~api_fastapi_server.activation.ActivationController`
    snapshot;
``pendingActivations``
    the AP-SRV-020 :class:`~api_fastapi_server.segment_ledger.SegmentLedger`
    background records - never a global "current activation" pointer, so an
    idle foreground with older draining activations is representable;
``trigger``
    the controller's configured/suppressed/effective trigger state;
``audioAvailable``
    the session's generic device flag;
``effectiveSettings`` / ``wakeWordCapabilities``
    the AP-SRV-050 / AP-SRV-060 ports.

Timer projection
----------------

The domain deadline is monotonic and stays that way. Only here is it
translated into the wire's ``deadlineAtUnixMs``/``remainingMs``, by measuring
the remaining monotonic distance once and anchoring it to the wall clock at
the same instant. No new wall-clock timer authority is created.
"""

import time

from . import schema


def build_snapshot(
    *,
    state,
    controller,
    ledger,
    audio_available,
    settings_port,
    wake_word_port,
    server_version,
    server_commit,
    monotonic=None,
    wall_clock=None,
):
    """The complete ``session.snapshot`` payload, including its ``type``."""
    monotonic = monotonic or time.monotonic
    wall_clock = wall_clock or time.time

    controller_snapshot = controller.snapshot() if controller is not None else {}
    state_version, settings_revision = state.versions()

    payload = {
        "type": schema.SESSION_SNAPSHOT,
        "protocolVersion": state.protocol_version,
        "serverVersion": server_version,
        "serverCommit": server_commit,
        "sessionId": state.session_id,
        "stateVersion": state_version,
        "lastEventSeq": state.last_event_seq,
        "settingsRevision": settings_revision,
        "input": build_input(
            controller_snapshot, monotonic=monotonic, wall_clock=wall_clock
        ),
        "pendingActivations": build_pending_activations(ledger),
        "trigger": build_trigger(controller),
        "audioAvailable": bool(audio_available),
        "settingsRevision": settings_revision,
        "requestedSettings": settings_port.requested_settings(),
        "effectiveSettings": settings_port.effective_settings(),
        "wakeWordCapabilities": wake_word_port.capabilities(),
    }
    return payload


def embedded_snapshot(payload):
    """The same payload as it is embedded in ``hello.accepted``.

    Only the inner ``type`` is dropped, exactly as the frozen schema says.
    """
    embedded = dict(payload)
    embedded.pop("type", None)
    return embedded


def build_input(controller_snapshot, *, monotonic=None, wall_clock=None):
    """The ``input`` block. In ``idle`` every optional value is ``null``."""
    monotonic = monotonic or time.monotonic
    wall_clock = wall_clock or time.time

    phase = controller_snapshot.get("phase") or schema.IDLE
    if phase not in schema.INPUT_PHASES:
        phase = schema.IDLE

    if phase == schema.IDLE:
        return {
            "phase": schema.IDLE,
            "activationId": None,
            "primarySource": None,
            "deadlineAtUnixMs": None,
            "remainingMs": None,
            "closeRequested": False,
        }

    deadline_at, remaining = project_deadline(
        controller_snapshot.get("deadline"),
        monotonic=monotonic,
        wall_clock=wall_clock,
    )
    return {
        "phase": phase,
        "activationId": controller_snapshot.get("activationId"),
        "primarySource": controller_snapshot.get("primarySource"),
        "deadlineAtUnixMs": deadline_at,
        "remainingMs": remaining,
        "closeRequested": phase == schema.CLOSING_INPUT,
    }


def project_deadline(deadline, *, monotonic=None, wall_clock=None):
    """``(deadlineAtUnixMs, remainingMs)`` for one monotonic deadline.

    The monotonic distance and the wall clock are sampled together, so the two
    published values always describe the same instant.
    """
    if deadline is None:
        return None, None
    monotonic = monotonic or time.monotonic
    wall_clock = wall_clock or time.time
    now_monotonic = monotonic()
    now_wall_ms = int(round(wall_clock() * 1000))
    remaining_ms = int(round(max(0.0, float(deadline) - now_monotonic) * 1000))
    return now_wall_ms + remaining_ms, remaining_ms


def build_pending_activations(ledger):
    """Background activations, strictly ordered by ``activationSequence``.

    Only activations whose input is already closed are pending: the open
    foreground activation is reported by ``input``. Several pending
    activations can coexist with an idle foreground.
    """
    if ledger is None:
        return []
    snapshot = ledger.snapshot() or {}
    entries = []
    for record in snapshot.get("activations") or []:
        if not record.get("inputClosed"):
            continue
        entries.append({
            "activationId": record.get("activationId"),
            "activationSequence": int(record.get("activationSequence") or 0),
            "inputClosedReason": record.get("inputClosedReason"),
            "processingState": record.get("state") or "draining",
            "acceptedSegmentCount": int(record.get("acceptedSegmentCount") or 0),
            "terminalSegmentCount": int(record.get("terminalSegmentCount") or 0),
        })
    entries.sort(key=lambda entry: entry["activationSequence"])
    return entries


def build_trigger(controller):
    """The ``configured``/``suppressed``/``effective`` trigger projection."""
    if controller is None:
        empty = {"manual": False, "wakeWord": False}
        return {
            "configured": dict(empty),
            "suppressed": dict(empty),
            "effective": dict(empty),
        }
    state = controller.trigger_state()
    return {
        section: {
            "manual": bool(values.get(schema.MANUAL_SOURCE, False)),
            "wakeWord": bool(values.get(schema.WAKE_WORD_SOURCE, False)),
        }
        for section, values in state.items()
    }
