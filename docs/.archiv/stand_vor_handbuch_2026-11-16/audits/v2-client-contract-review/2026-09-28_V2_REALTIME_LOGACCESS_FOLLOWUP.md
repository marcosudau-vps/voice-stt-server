# V2 contract follow-up: realtime transcripts and session log access

**Date:** 2026-09-28
**Baseline reviewed by the original audit:** `f7d2b3ccd07757172a45b371829b04bcedffab4b`
**Follow-up action:** AP-SRV-080

## Purpose

The independent review in this directory correctly documented the V2
implementation at its stated baseline: `/ws/v2` did not project realtime text
and did not return a session-scoped log token. Those reports remain historical
evidence for that commit and are not rewritten.

AP-SRV-080 deliberately changes the two findings below after that baseline.

## Contract changes

### Realtime text

The existing internal `realtime_transcript` signal is now projected onto the
canonical V2 connection as `transcription.interim`. The event:

- carries the normal V2 envelope and the segment identity;
- requires `text` and may carry the existing stabilizer's richer optional
  fields;
- is ordered by `eventSeq`;
- does not advance `stateVersion`;
- is a revisable preview that is superseded by the segment terminal.

There is still no V2 domain-event replay. A snapshot contains neither segments
nor transcript text.

### Session-scoped logs

The earlier implementation finding `IMPL-03` is resolved. On successful V2
admission, `hello.accepted.logAccess` is created by the same authority already
used by legacy V1. If available, the token is restricted to its own session
and the `audit`, `transcription`, and `performance` channels. It does not grant
the `system` channel or cross-session access. Global retained history remains
an Admin-Key capability.

`logAccess` is bootstrap entitlement material and is intentionally absent from
later `session.snapshot` responses. When live logging is disabled or the
canonical store is unavailable, the object remains present with
`available: false`, no `accessToken`, and a machine-readable `code`.

## Verification authority

The active contract is maintained in `docs/client-development/`, the wire
schema in `api_fastapi_server/protocol_v2/`, and the machine-readable vector in
`tests/contracts/protocol-v2-vectors.json`. The AP-SRV-080 implementation
comparison records final local and public-CI evidence.
