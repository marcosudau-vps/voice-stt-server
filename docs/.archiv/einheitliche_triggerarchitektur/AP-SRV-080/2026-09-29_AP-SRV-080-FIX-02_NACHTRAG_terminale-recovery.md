# AP-SRV-080-FIX-02: Nachtrag Terminale Recovery → V2-Transport (PR #4)

**Datum:** 29.09.2026
**Art:** Datierter Nachtrag zu einer bereits erfolgten Implementierung
(keine neue Planung vor Umsetzung; keine neue Änderungsaktion im Sinne von
`docs/.archiv/README.md`, daher kein neuer Registereintrag — Ergänzung zur
registrierten, abgeschlossenen Akte
[AP-SRV-080](2026-09-28_AP-SRV-080_PLAN.md)).
**Status:** Implementiert, Review-Nachbesserung eingearbeitet, PR offen
(nicht gemergt)

## 1. Anlass und Abgrenzung zur Audit-Baseline

Die kanonische Audit-Momentaufnahme
[`docs/audits/v2-client-contract/V2_CLIENT_CONTRACT_REFERENCE.md`](../../../audits/v2-client-contract/V2_CLIENT_CONTRACT_REFERENCE.md)
(Dokument Version 1.1.0, Baseline-SHA
`f7d2b3ccd07757172a45b371829b04bcedffab4b`, dort §17 „Close-Codes und stille
Verwerfungen“) beschreibt den Stand eines bestimmten Commits und wird
bewusst **nicht** rückwirkend um neues Verhalten ergänzt. Dieser Nachtrag
hält fest, wie sich der aktuelle Code gegenüber jener Baseline verhält.

## 2. Verhaltensdelta gegenüber der Baseline

Der Server besaß in `api_fastapi_server/server.py` bereits
`RecorderBackedRealtimeSession.fail_closed_for_recovery()`: Kann der
Eingabepfad nicht mehr sicher geschlossen werden, wird die Domain-Session
über `self.close()` terminal beendet. In der Baseline erfuhr die
V2-Connection davon nicht zuverlässig (V2 ist absichtlich nicht im
Legacy-ConnectionManager registriert; der Endpoint wartete nach dem
Handshake unbegrenzt auf `await websocket.receive()`), sodass eine intern
geschlossene Session mit äußerlich noch verbundenem WebSocket zurückbleiben
konnte.

Seit FIX-02 (Branch `fix/v2-terminal-recovery`, PR #4 gegen
`feat/einheitliche-triggerarchitektur-distributed`) gilt:

- Terminaler interner Marker `__session_terminal__` am Ende von
  `fail_closed_for_recovery()` via Protocol-Observer (`finally`,
  außerhalb der Domain-Locks). Kein öffentliches Domain-Event, kein
  Legacy-Publish, keine neue State-Machine.
- `ProtocolV2Connection._on_domain_event()` fängt den Marker vor der
  Projektion ab und ruft `request_close(1011)` (bestehender Code,
  idempotent). Keine neue Wire-Nachricht, kein neuer Close-Code.
- Die Receive-Schleife von `websocket_protocol_v2()` wartet nach dem
  Handshake gleichzeitig auf `websocket.receive()` und ein
  endpointlokales Transport-Close-Signal (`asyncio.wait`,
  `FIRST_COMPLETED`); beim Signal wird der Receive-Task sauber abgebrochen
  und der bestehende Cleanup-Pfad durchlaufen. Handshake-Timeout (`4408`)
  unverändert; kein Polling. Bei äußerer Task-Cancellation werden
  Receive-/Close-Task abgebrochen und awaitet (keine verwaisten Tasks).
  Ein fataler Writerfehler setzt ebenfalls Close-Code `1011` und weckt den
  Cleanup-Pfad. Der finale Close-Code wird nach `request_close` erneut
  gelesen, damit ein konkurrierender terminaler Close (1011) nicht durch
  einen veralteten lokalen Wert verloren geht.
- Der Session-Slot wird freigegeben; Weiterarbeit erfordert ein neues
  `hello` mit neuer `sessionId`.

Der öffentliche Wire-Vertrag ist unverändert
(`tests/contracts/protocol-v2-vectors.json` unangetastet).

## 3. Kanonische Stellen für den aktuellen Stand

- [`docs/einheitliche-triggerarchitektur.md`](../../../einheitliche-triggerarchitektur.md)
  (Recovery-Abschnitt; Close-Tabelle: `1011` einschließlich terminaler
  Recovery; Handshake-Fälle ohne `sessionId` vs. angenommene Session)
- [`docs/client-development/02-websocket-protokoll.md`](../../../client-development/02-websocket-protokoll.md)
  (§8 Close-Codes)
- Reconnect bleibt wie dokumentiert: `1011` → Backoff + Jitter, neue
  Session (`05-client-zustandsmodell.md`, `07-robustheit-grenzen-und-sicherheit.md`).

## 4. Nachweis

- Regressionstest
  `tests/unit/test_protocol_v2_terminal_recovery.py` (echter `/ws/v2`,
  echte Session): Test A weist den Fehler ohne weitere Clientnachricht
  nach (vor Fix `None != 1011`); Tests B–D: Ressourcenfreigabe,
  Idempotenz, keine Regression; zusätzlich gezielte Tests für äußere
  Endpoint-Cancellation und fatalen Writerfehler.
- Relevante Regressionen: `test_protocol_v2_e2e`,
  `test_protocol_v2_races`, `test_server_command_timer_e2e`,
  `test_protocol_v2_contract` (kein Vektor-Drift).
