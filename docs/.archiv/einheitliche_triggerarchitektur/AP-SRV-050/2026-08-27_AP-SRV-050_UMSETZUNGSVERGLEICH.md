# AP-SRV-050 – Umsetzungsvergleich (Soll/Ist)

**Datum:** 2026-08-27
**Geprüfter Stand:** Branch `review/AP-SRV-050/run-01`, **Stand C3**
(Implementierung C1 `489ac23a` + Root-Korrekturen C2 + C3)
**Abnahmestatus:** **ROOT PASS** (F1–F6 PASS), Root-PASS Source C3
`18b65216433329456946afd3c41d8df6bbd07d44`; siehe `ABNAHME.md`
**Basis:** `c0806e5bc5d503580070f2dacc88831d51447938`

Prüfgegenstand ist der veröffentlichte Stand (C1+C2+C3) gegen jeden
wesentlichen Punkt des Auftrags einschließlich der Root-Findings der C2- und
C3-Korrektur. Statuswerte: ✅ vollständig, 🟡 teilweise, ⛔ nicht umgesetzt.

| # | Requirement (Prompt) | Status | Nachweis (Code/Test) | Abweichung |
|---|---|---|---|---|
| 5/6 | Registry veröffentlicht key/scope/auth/type/constraints/defaultValue/requestedValue/effectiveValue/applyPolicy/settingsRevision je Einstellung | ✅ | `settings_control.py`; Schema/REST in `server.py`; Tests `test_settings_control_plane.py` | – |
| 6 | Scopes session/server/client_local; Server nur session/server | ✅ | Registry Konstanten | – |
| 6 | Apply-Policies live/next_activation/next_session/server_restart; keine Synonyme | ✅ | `APPLY_POLICIES`, Registry; Test „no private synonyms“ | – |
| 7.1 | Sechs Activation-Timings, exakte Keys/Default/Bereiche, scope/auth/apply | ✅ | Registry; Tests alle sechs | – |
| 7.1 | Cross-Field gegen finalen Candidate, warning<initial und <refresh | ✅ | `validate_timing_bundle`; Pflichttests §30 | – |
| 7.2 | Wake-Sensitivity session/Serverdefault 0.5, next_activation | ✅ | Registry + Tests | – |
| 7.3 | Wake-Auswahl session/next_session atomar; leer nur wenn kein WW; unbekannte IDs maschinenlesbar; laufende Session nicht umgebaut | ✅ | Registry + Session-Validator; Tests | – |
| 7.4 | Runtime-Suppression nur Registry-/Metadaten; kein zweiter Write-Pfad | ✅ | `writable=False`; Session-Patch lehnt ab; `trigger_suppression.set` bleibt Autorität | – |
| 7.5 | Server-Restregistry für Serverdefaults, Sensitivity-Default, Global-Disable | ✅ | `ServerSettingsState`, Keys | – |
| 9 | Donor-Konzepte portierbar (Registry, Timingkeys, Sensitivität, Auswahl, Suppression-Darstellung, Disable, monotone Revision, optimistic concurrency, no_change, requested/effective, REST, Admin-Guard) | ✅ | Donor-Traceability im REPORT | – |
| 10.2 | Genau eine Settings-Domainautorität; ProtocolSessionState Wire-Spiegel; SettingsPort Adapter | ✅ | `connection._activate_session`, `ports.py`, `settings_control.py` | – |
| 10.3 | next_activation reale Timerwirkung | ✅ | `ActivationTimingPolicy`; §28/§29 Tests mit exakten Deadlines | – |
| 11.1 | Timingwerte pro Activation latchen; immutable Repräsentation | ✅ | `ActivationTimingPolicy`, `_timing_locked()` | – |
| 11.2 | Keine rückwirkende Mutation bei Patch während offener Activation | ✅ | §28 Wire-Test (Deadline unverändert) | – |
| 11.3 | Manual und Wake gleiche Seam | ✅ | `_new_activation_inputs()` in beiden Admission-Pfaden | – |
| 12 | Eine Quelle für effectiveSettings (snapshot/event/controller/ledger/Timer/Metadaten) | ✅ | `settings_effective_for_wire()`; Konsistenztest §33 | – |
| 13 | Requested/Effective-Semantik live/next_activation/next_session/server_restart | ✅ | Tests Verhalten je Policy | – |
| 14.1 | Optimistic concurrency; stale → settings_revision_conflict; keine Effekte | ✅ | Domain- + Wire-Tests | – |
| 14.2 | Atomare Validierung; settings_rejected; sortierte Errors; 0 Effekte | ✅ | Domain- + Wire-Tests | – |
| 14.3 | no_change ohne Bump/Event | ✅ | Domain- + Wire-Tests | – |
| 14.4 | Revision N→N+1 genau einmal pro Transaktion | ✅ | Tests Multi-Key/Multi-Policy | – |
| 15 | Multi-Policy-Patch: eine Revision, Gruppen live/next_activation/next_session/server_restart, changedKeys lexikographisch, stateVersion +1 genau einmal | ✅ | `_emit_settings_changed`; Tests | – |
| 16 | settings.changed über AP-040-Dispatch-Seam | ✅ | `_dispatch_events(produce)` | – |
| 17 | Command-Replay unverändert; identisches Ack; kein zweites Event; command_id_conflict | ✅ | Wire-Tests | – |
| 18 | REST `/api/v2/settings/schema` + `/server` + PATCH | ✅ | `server.py` Endpunkte; REST-Tests | – |
| 18 | vorhandener Wake-Endpunkt bleibt | ✅ | `GET /api/wake-word` bleibt; kein neuer Katalogendpunkt | Root-entschiedene Paketzuordnung: `GET /api/v2/wake-words` = AP-SRV-060 (SET-13b). Siehe Abweichungsnotiz |
| 19 | Bestehender Admin-Guard; X-Admin-Key als Alias; öffentliche Reads; nie Secrets | ✅ | `admin_auth_error`; REST-/Secret-Leak-Tests | – |
| 20 | Server-PATCH: 409 conflict, atomic reject, Erfolg persistiert, no_change kein Bump | ✅ | REST-Tests + Persistenz-Tests | – |
| 21/53 | Neue Session: Serverdefault + Session-Overrides; bestehende Sessions nicht rückwirkend | ✅ | Admission-Seeding; Domain-Test | – |
| 22–25 | RuntimeConfigStore-Koexistenz; beide Schreibreihenfolgen; atomar; eine Lock-Seam | ✅ | `operations.py`; Persistenz-Tests A–F | – |
| 26 | Pflichttests A–F | ✅ | `test_settings_runtime_persistence.py` | – |
| 27 | keine Secrets persisieren | ✅ | Registry `secret`; Server-Patch lehnt Secrets ab | – |
| 28 | Pflicht-E2E Follow-up 3000→8000, laufende unverändert, nächste real 8.0s | ✅ | `test_protocol_v2_settings.py` | – |
| 29 | Alle sechs Timings real gebunden | ✅ | Controller-Level exakte Deadlines | – |
| 30 | Watchdog-Cross-Field-Pflichttests | ✅ | 4 Szenarien + final-Candidate | – |
| 31 | Session-Revision-/Event-Matrix 1–9 | ✅ | Domain- + Wire-Tests inkl. 20x Race | – |
| 32 | settings.changed + Domain-Ordering deterministisch (eventSeq monoton, keine Lücke/Duplikat) | ✅ | 20 Iterationen Barrier-getrieben | – |
| 33 | Snapshot-Konsistenz aller Revisionen/effectiveSettings | ✅ | `test_session_snapshot_consistency` | – |
| 34 | Public Settings Schema, sortiert, keine Secrets/Interna | ✅ | REST-Test | – |
| 35 | Server Settings Read öffentlich, nicht geheim, Revision, requested/effective | ✅ | REST-Test | – |
| 36 | Server Settings Patch: Adminauth, atomic, base revision, nur server-default-writable, Session-Key abgelehnt, Secrets nie | ✅ | REST-Tests | – |
| 37 | HTTP-Auth-Pflichttests + Secret-Leaktests | ✅ | REST-Klasse | – |
| 38 | v1/Legacy-Isolation; Legacy-Endpunkte funktional | ✅ | v1-Tests grün; kein Legacyumbau | – |
| 39/40 | AP-060 nicht vorwegnehmen; keine Cooldown-/Pre-Roll-Werte | ✅ | Keine AP-060-Fachlogik | – |
| 41–44 | Archive-Akte (PLAN/README/runs/REPORT/evidence/UMSETZUNGSVERGLEICH) | ✅ | Ordner angelegt | – |
| 42 | Originalprompt byteidentisch + SHA256 | ✅ | Gleich `2F64EB44...` | – |
| 45 | Produktdokumentation aktualisiert | ✅ | siehe Abschnitt 4 REPORT | – |
| 46 | Archive-Register der Gesamtaktion bleibt „In Umsetzung“ | ✅ | `docs/.archiv/README.md` unverändert | – |
| 47 | Kleine Module statt server-Monolith | ✅ | `settings_control.py` + Adapter | – |
| 48 | Fehlerformate field/code/message; frozen result codes | ✅ | `FieldError`; Wire nutzt RESULT_CODES | – |
| 49 | Determinsmus (Sortierung) | ✅ | Keys/Errors/changedKeys/Gruppen sortiert | – |
| 50 | Thread Safety; Barrier/Event statt sleep | ✅ | RLock + Barrier-Szenarien | – |
| 51 | stateVersion +1 je sichtbarer Settings-Transaktion; nicht bei no_change/reject/replay/conflict | ✅ | Wire-Tests | – |
| 52 | Server- vs Session-Settingsrevision getrennt | ✅ | Zwei Revision-Streams; Separationstests | – |
| 54 | Pflicht-Testdateien | ✅ | drei neue Dateien | – |
| 55–58 | Testbefehle und Ergebnisse | ✅ | REPORT + Evidence | – |
| 59/61/64 | diff check, Worktree, genau ein C1-Commit, Parent exakt, kein Push | ✅ | Abschlussprüfung | – |

## C2 – sechs Root-Findings (Stand C2)

| Finding | Status | Nachweis (Code/Test) | Abweichung |
|---|---|---|---|
| F1 sequential cross-field bypass geschlossen | ✅ | `validate_timing_bundle` (`WATCHDOG_CROSS_FIELD_KEYS`); `TestSequentialCrossFieldBypass` | – |
| F2 Wake-Auswahl fail-closed (leeres Catalog-Set, Katalog-Exception) | ✅ | `_validate_wake_selection_key`; `TestWakeSelectionFailClosed` | – |
| F3 eine atomare Admission-Seam (effective+timmings aus einer Revision) | ✅ | `activation_admission_settings()` + `_new_activation_inputs()`; `AtomicAdmissionTests` + Race 20× | – |
| F4 persisted Control beim Startup strikt validiert (fail fast) | ✅ | `ServerSettingsState.__init__` + `load_control()`; `TestStartupPersistenceValidation` | – |
| F5 prepare→persist→commit; Persistenzfehler ohne RAM-/Revisions-Mutation; HTTP 500 | ✅ | `patch_server`; `TestServerSettingsCommitOnFailure`; REST 500-Tests | – |
| F6 `session.snapshot.requestedSettings` additiv; SettingsPort Adapter | ✅ | `snapshot.py` + `settings_requested_for_wire()`; `RequestedSettingsWireTests` | – |

## C3 – Wire-Atomicity / Snapshot-Consistency

| Punkt | Status | Nachweis (Code/Test) | Abweichung |
|---|---|---|---|
| passiver Settings-Wire-Block (Mutation → Mirror → `settings.changed`) unter `_event_dispatch_lock` | ✅ | `connection._apply_settings_patch()` | – |
| Snapshot unter derselben `_event_dispatch_lock`-Grenze | ✅ | `connection._snapshot_payload()` | – |
| atomarer Projection-Bundle-Read (`SessionSettingsProjection` / `settings_projection()`) | ✅ | `settings_control.py` + `ports.py` | – |
| Snapshot-Build aus dem Bundle (revision/requested/effective), stateVersion/lastEventSeq bei `ProtocolSessionState` | ✅ | `snapshot.py` | – |
| doppelter `settingsRevision`-Eintrag entfernt | ✅ | `snapshot.py` | – |
| deterministische RED-FIRST-Tests (Patch vs. Snapshot, Patch vs. Domainevent) | ✅ | `WireLinearizationTests` (Test A/B, je 20× grün) | – |

## Abweichungsnotizen

1. **Wake-Endpunkt (Punkt 18).** Der Frozen Contract nennt `GET /api/v2/
   wake-words`. Die kanonische Basis besitzt stattdessen `GET /api/wake-word`
   (Admin-guarded, v1-Pfad). Nach dem Root-Review gilt die **Root-entschiedene
   Paketzuordnung**:

   ```text
   SET-13a: /api/v2/settings/schema, /server, PATCH -> AP-SRV-050
   SET-13b: /api/v2/wake-words                       -> AP-SRV-060
   ```

   `GET /api/v2/wake-words` wird in AP-SRV-050/C2 nicht implementiert
   (`ROOT_TRACKING_ACTION_REQUIRED`: SET-13 später in SET-13a/SRV-050 und
   SET-13b/SRV-060 aufteilen).
2. **Fokus-Befehl Umgebungsmitigation.** `python -m pytest` läuft auf dieser
   Maschine wegen eines blockierenden WMI-Zugriffs im torch-Import nur mit
   einem out-of-tree `sitecustomize`-Mitigationspfad. Testbefehle und
   Sollbefunde unverändert; Nachweis im REPORT/Evidence.

## Abschluss

```text
Status              ROOT PASS (F1–F6)
Root-PASS Source    C3 18b65216433329456946afd3c41d8df6bbd07d44
                    Tree b0dec32ddde90052956165c249b313478c267773
Kanonische Basis    c0806e5bc5d503580070f2dacc88831d51447938
Kanonisierung       erfolgt im Abschlusscommit als genau ein Commit
Root-Abnahme        ABNAHME.md
Next                AP-SRV-060
```

Die Abweichungsnotiz 1 ist mit der Root-Entscheidung abschließend geklärt:
`SET-13` wird im Clienttracking in `SET-13a` (AP-SRV-050) und `SET-13b`
(AP-SRV-060) aufgeteilt. `GET /api/v2/wake-words` gehört AP-SRV-060.
