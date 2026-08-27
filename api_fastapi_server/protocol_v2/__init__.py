"""Protocol v2 - wire, session and projection layer of AP-SRV-040.

The package adds the frozen ``protocolVersion = 2`` contract on top of the
already accepted AP-SRV-020/AP-SRV-030 authorities. It owns the WebSocket
envelope, the handshake, the protocol session state, the ack/event projection
and the snapshot - and nothing else. There is no second activation state
machine, no second timer, no second ledger and no second input-close
authority here.

Layering::

    /ws/v2
      -> handshake / admission        (handshake.py, connection.py)
      -> ProtocolSessionState         (session.py)
      -> strict v2 envelope           (commands.py)
      -> AP-SRV-030 command authority (activation.py, activation_commands.py)
      -> AP-SRV-020 segment ledger    (segment_ledger.py)
      -> event projection + snapshot  (events.py, snapshot.py)

The v1 transport stays untouched and isolated until AP-SRV-070.
"""

from . import commands, events, handshake, identity, ports, schema, snapshot
from .connection import ProtocolV2Connection
from .session import ProtocolSessionState

__all__ = [
    "ProtocolSessionState",
    "ProtocolV2Connection",
    "commands",
    "events",
    "handshake",
    "identity",
    "ports",
    "schema",
    "snapshot",
]
