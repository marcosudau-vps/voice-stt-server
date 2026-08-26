# AP-SRV-050 – Soll-/Ist-Prüfung nach der Umsetzung

**Datum:** 2026-08-27
**Geprüft gegen:** `2026-08-27_PLAN.md` und den tatsächlich veröffentlichten
Stand im lokalen Prep-Commit dieses Branches.

## 1. Registry und Schema (Plan 1, 4)

| Planpunkt | Stand | Befund |
|---|---|---|
| Sechs Trigger-Timingkeys exakt (Defaults/Bereiche/Scope/Apply) | umgesetzt | `activation.*Ms` mit 100–3600000/15000 usw., Scope Session, Apply `next_activation`, Serverdefault-Facet admin-managed. 53+10 Tests grün. |
| Wake-Word-Sensitivity 0.0–1.0, Default 0.5 | umgesetzt | `wakeWord.sensitivity` float, getestet. |
| Schema ohne Secrets, ohne Requested/Effective | umgesetzt | `schema_payload()` enthält nur Metadaten. |
| Keine zweite lose Keyliste in `server.py` | umgesetzt | nur `settings_control` definiert Keys; `server.py` importiert die alleinige Registry. |

## 2. Validation

| Planpunkt | Stand |
|---|---|
| Min/Max-Grenzen aller Timings | umgesetzt und parametrisiert getestet (unter/über/auf Grenze). |
| Watchdog-Warning < wirksame Frist | umgesetzt über `validate_timing_bundle` (Initial + Refresh), getestet. |
| Falsche Typen, Unknown Keys, Bool-Ausschluss für Zahlen | umgesetzt und getestet. |

## 3. Revision und Atomicität

| Planpunkt | Stand |
|---|---|
| `baseSettingsRevision` prüft aktuelle Revision | umgesetzt; stale → `settings_revision_conflict` (REST 409). |
| Irgendein Feld ungültig → ganzer Patch abgelehnt | umgesetzt; kein Key angewendet, Memory, Persistenz und Revision unverändert (getestet). |
| Revision steigt genau einmal pro logischer Transaktion | umgesetzt; `no_change` erhöht nicht. |
| Zwei konkurrierende Patches → genau einer gewinnt | umgesetzt und per Thread-Lock getestet; Retry auf neuer Revision. |

## 4. Apply Policies / Requested-Effective

| Planpunkt | Stand |
|---|---|
| Laufende Activation behält Snapshot | umgesetzt: `freeze_activation()` immutabel; Test verifiziert Unveränderbarkeit nach Patch. |
| Nächste Activation erhält `next_activation`-Werte | umgesetzt (neuer Freeze nach Patch). |
| `next_session` nicht als live | umgesetzt; erst `realize_next_session()` zieht nach. |
| `server_restart` nicht als live | umgesetzt; `requires_restart`, Requested≠Effective bis `realize_after_restart()`. |

## 5. Persistenz

| Planpunkt | Stand |
|---|---|
| Wiederverwendung `RuntimeConfigStore` | umgesetzt; `RuntimeSettingsStore` ist Subklasse, nutzt `_lock`, Pfad, `os.replace`-Atomik und `_utc_now`. |
| Keine zweite JSON-Datei/Datenbank | bestätigt; additive Top-Level-Felder in derselben `runtime.json`. |
| Round-trip, atomarer Write, Restart-Leseweg | getestet (inkl. Werte/Revision über zwei App-Instanzen). |

## 6. REST / Auth / Secret

| Planpunkt | Stand |
|---|---|
| GETs öffentlich ohne Admin-Key | umgesetzt (200). |
| PATCH ohne/falscher Key abgelehnt | umgesetzt (401, bestehender Admin-Guard). |
| PATCH mit korrektem Key | umgesetzt (200 applied). |
| Secret-Redaction in Schema/Read/Patch | umgesetzt: `redacted: true`, Werte entfernt; getestet. |

## 7. Session-Patch-Port

| Planpunkt | Stand |
|---|---|
| Parserfreie Domain-Operation | umgesetzt: `SessionSettingsState.apply_patch`. |
| Strukturiertes Ergebnis für `command.ack`-Projektion | umgesetzt: `PatchResult.to_command_ack_parts()`. |

## 8. Bereiche / Markierungen

| Planpunkt | Stand |
|---|---|
| SRV-040-Port dünn | `REQUIRES_FINAL_SRV_040_BINDING` nicht nötig, da kein v2-Wire in diesem Paket. |
| SRV-030-Bindung | `ActivationSettingsProvider` als Port bereitgestellt; Abnahme in Controller-Konstruktor bleibt der finalen SRV-030-Korrektur: `REQUIRES_FINAL_SRV_030_BINDING`. |

## 9. Validierung

- Neue Tests: 63 (53 Planungen + 10 REST).
- Relevante Bestandstests: grün (264 inkl. Settings).
- Volle Serversuite: `630 passed, 13 skipped, 152 subtests passed`.
- `git diff --check`: leer.
- Baseline vor dem Paket: `567 passed, 13 skipped, 152 subtests passed`;
  Differenz = genau die 63 neuen Tests.

**Gesamtbefund:** vollständig im Sinne des Planungs-/Prep-Umfangs.