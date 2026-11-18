# AP-SRV-070 / W4A-C4 — Phase 1: Kalenderabhängiger Retention-Test

Dieses Dokument kartiert den kalenderabhängigen Testfehler in `test_admin_replay_reports_retention_gap`.

Gemäß Phase-1-Vorgaben wurden **weder Test- noch Produktcode geändert**.

## 1. Test-Identifikation

- **Testdatei:** `tests/unit/test_fastapi_server_multi_user.py`
- **Testklasse:** `FastAPIMultiUserWebSocketTests` (Zeile 1378)
- **Testmethode:** `test_admin_replay_reports_retention_gap` (Zeilen 1862–1981)

## 2. Zeitwerte und Uhr-Verhalten

- **Retention-Fenster:** `30` Tage (`events._store.set_retention({"transcription": 30})`, Zeile 1908)
- **Verwendete Uhr:**
  - Der Server und EventStore (`SQLiteEventStore`) verwenden für `events.emit(...)` und für die Berechnung des Retention-Cutoffs in `set_retention()` die reale Systemzeit (`datetime.now(timezone.utc)`).
  - Es wurde keine simulierte Testuhr und kein Freeze-Mechanismus im Test verwendet.

### Absolute Fixture-Zeitstempel im Test

1. `retention-system-old`:
   - Timestamp: `"2020-01-01T00:00:00.000Z"`
   - Cursor: `system_cursor` (Zeile 1884)
2. `retention-transcription-old`:
   - Timestamp: `"2020-01-01T00:00:00.000Z"`
   - Cursor: `removed_cursor` (Zeile 1892)
3. `retention-transcription-session-b`:
   - Timestamp: `"2026-08-02T00:00:00.000Z"`
   - Cursor: `session_b_cursor` (Zeile 1900)

## 3. Beabsichtigte Semantik jedes Zeitwerts

| Event-ID | Fixture-Timestamp | Beabsichtigte Semantik | Tatsächliches Verhalten am 2026-09-01 |
|---|---|---|---|
| `retention-transcription-old` (`removed_cursor`) | `"2020-01-01T00:00:00.000Z"` | **Außerhalb** des 30-Tage-Fensters. Soll durch Retention gelöscht werden, um die Gap-Erkennung (`retentionCursor`, `log.gap`) zu prüfen. | Wird wie beabsichtigt gelöscht. |
| `retention-transcription-session-b` (`session_b_cursor`) | `"2026-08-02T00:00:00.000Z"` | **Innerhalb** des 30-Tage-Fensters. Soll für `session-b` erhalten bleiben; der Test erwartet `retentionCursor == 0` und Replay des Events. | **Fehlschlag:** Am 2026-09-01 ist der 2026-08-02 älter als 30 Tage (August hat 31 Tage). Das Event wird unerwartet gelöscht. |

## 4. Ursache des Kalendersprungs

- Am **2026-08-31** (Tag des W4A-C2-Laufs):
  - Differenz zwischen `2026-08-02T00:00:00Z` und `2026-08-31` beträgt 29 Tage.
  - Das Event lag **innerhalb** der 30 Tage Retention.
  - Testergebnis: **PASS**.
- Am **2026-09-01**:
  - Differenz zwischen `2026-08-02T00:00:00Z` und `2026-09-01` beträgt 30 Tage (exakt 30 Tage und 0 Stunden bei Mitternacht bzw. >30 Tage während des Tages).
  - Das Event liegt **außerhalb** des 30-Tage-Fensters und wird von `set_retention({"transcription": 30})` gelöscht.
  - Assertion in Zeile 1976 (`self.assertEqual(hello["retentionCursor"], 0)`) schlägt fehl.
  - Testergebnis: **FAIL**.

## 5. Unmittelbar benachbarte Tests / Fixtures

Untersuchung auf vergleichbare absolute Datumsangaben:

- `tests/unit/test_server_operations.py`:
  - `test_sqlite_retention_watermarks_are_channel_and_session_scoped` (Zeilen 716–775):
    Setzt für das erhalten bleibende Event dynamisch:
    `timestamp=datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")`.
    Dieser Test ist kalenderunabhängig stabil.
  - `test_calendar_and_sqlite_retention_are_opt_in_and_channel_scoped` (Zeilen 661–675):
    Verwendet `CalendarJsonlSink`, welches die relative Retention basierend auf dem Timestamp des geschriebenen Events berechnet, nicht auf Basis der Systemzeit.
- Weitere Tests in der Testsuite mit diesem Konstrukt wurden nicht gefunden. Das Problem beschränkt sich exakt auf die absolute Datums-Fixture in `test_admin_replay_reports_retention_gap`.
