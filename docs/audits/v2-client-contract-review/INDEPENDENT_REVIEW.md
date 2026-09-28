# Unabhängige Prüfung des VoiceSTT-V2-Client-Audits

| | |
| --- | --- |
| **Prüfdatum** | 2026-09-28 |
| **Implementierung** | `feat/einheitliche-triggerarchitektur-distributed` @ `f7d2b3ccd07757172a45b371829b04bcedffab4b` (Tree `731c22d872ab3a3897886bcd6bec582e8332be75`) |
| **Geprüftes Audit** | `audit/v2-client-contract-9436684549960924324` @ `cc7d4996d04c5ca756be9798102629bc2713ce2f` (einziger Commit über `f7d2b3cc`, fügt nur die vier Dateien unter `docs/audits/v2-client-contract/` hinzu) |
| **Prüfbranch** | `review/v2-contract-and-docs` (von `cc7d4996` abgezweigt) |

## 1. Umfang

* Alle Aussagen der vier Audit-Dateien in [`../v2-client-contract/`](../v2-client-contract/AUDIT_SUMMARY.md).
* Der gesamte clientsichtbare V2-Vertrag: `/ws/v2`, Handshake, Identitäten,
  fünf Commands, `command.ack`, Replay, 17 Events, `eventSeq`/`stateVersion`,
  Snapshot, Reconnect, Audio-Transport, Wake Words, Settings-Control-Plane,
  HTTP-APIs, Authentifizierung.
* Anschließend (Phase B) die Dokumentation des Repositorys; siehe
  [`DOCUMENTATION_IMPACT.md`](DOCUMENTATION_IMPACT.md).

## 2. Methodik

Autoritätsreihenfolge: Produktionscode → ausführbare Tests →
Vertragsvektoren → Schema/Konfiguration → Dokumentation → Audit.

1. Git-Beziehung geprüft (`git merge-base`, `git diff --stat f7d2b3cc cc7d4996`).
2. Vertrag unabhängig aus dem Code rekonstruiert:
   `api_fastapi_server/protocol_v2/*`, `api_fastapi_server/protocol.py`,
   `activation.py`, `activation_commands.py`, `segment_ledger.py`,
   `settings_control.py`, `server.py` (`/ws/v2`-, `/ws/transcribe`- und
   HTTP-Handler, Session), `VoiceSTT/core/wakeword_catalog.py`,
   `tests/contracts/protocol-v2-vectors.json`.
3. Jede zitierte Quelle des Audits geöffnet; nicht existierende Tests und
   Symbole festgehalten.
4. Tests ausgeführt ([`TEST_EVIDENCE.md`](TEST_EVIDENCE.md)).
5. Wo Code allein Reihenfolgen oder Payloads nicht eindeutig belegt, wurden
   Wire-Traces über die echte `/ws/v2`-Route mit dem Referenz-Harness der
   Testsuite aufgezeichnet.
6. Jede Aussage klassifiziert ([`FACT_REVIEW_MATRIX.md`](FACT_REVIEW_MATRIX.md)),
   Korrekturen in [`AUDIT_CORRECTIONS.md`](AUDIT_CORRECTIONS.md) gesammelt und
   in die Audit-Dateien eingearbeitet.

## 3. Gesamtergebnis

| Menge | `CORRECT` | `PARTIALLY_CORRECT` | `INCORRECT` | `UNPROVEN` |
| --- | ---: | ---: | ---: | ---: |
| 19 Fakten der Original-Matrix | 16 | 2 | 1 | 0 |
| 32 zusätzliche Aussagen aus Summary, Referenz, Migrationsmatrix | 3 | 12 | 16 | 1 |

Die Fakt-Matrix des Audits war im Kern belastbar; ihre Quellenangaben waren es
nicht (vier zitierte Tests existieren nicht, einer liegt in einer anderen
Datei, ein Codesymbol ist falsch benannt, ein Audiobeleg enthält keinen
Audiotest). Die ausführlichere Contract-Reference und die Migrationsmatrix
enthielten dagegen zahlreiche erfundene oder falsche Details – ausgerechnet
dort, wo ein Cliententwickler implementiert.

## 4. Wesentliche Korrekturen

1. **Audio-Wire-Format (`AUD-001`, `INCORRECT`).** Nicht „8-Byte-Header
   `VSTT`/Version/Flags“, sondern:

   ```text
   uint32 Little-Endian N (≤ 65 536) · N Bytes UTF-8-JSON-Objekt · PCM s16le
   ```

   Pflicht-Metadatum `sampleRate` (beliebige positive Rate, Server resampelt
   auf 16 kHz), optional `channels` (1–8), `format` (`pcm_s16le`), `frames`.
   PCM-Nutzlast ≤ `max_audio_packet_bytes` (524 288). Kein Magic, keine
   Version, keine Flags. Ungültige Frames werden auf V2 still verworfen. Alle
   Vorkommen des falschen Formats sind entfernt (Repository-weite Suche nach
   `VSTT`/`0x56535454`: nur noch in Korrekturberichten als zitierter Fehler).
2. **Reihenfolgen.** Events eines Commands kommen vor seinem Ack; das Ack von
   `finish`/`cancel` trägt die ältere Version des `closing_input`-Eintritts;
   `activation.started` kommt vor `wakeword.detected`; das Activation-Terminal
   kann vor `activation.input_closed` kommen.
3. **Payloads.** Snapshot-Settings-Maps sind vollständig (16 Schlüssel), nicht
   leer; `invalid_payload`-Acks haben kein `errors[]`; Katalog-JSON ohne
   `serverVersion`/`serverCommit`, mit `artifactVersion`, `backends` und
   Eintragsrevision.
4. **Nicht existierende Oberflächen.** `GET /api/v2/health` existiert nicht.
5. **Authentifizierung.** Admin-Auth ist im Anwendungscode implementiert, nicht
   „am Gateway“; `/ws/v2` hat keine Auth; V2 erhält keinen `logAccess`.
6. **IDs.** Kanonische UUID-Schreibweise wird geprüft, nicht die Version.
7. **Wake Words.** Handshake nur kanonisch; Session-Patch akzeptiert Aliase.
8. **Migrationsmatrix.** V1-`start`/`stop` sind Streambefehle, nicht
   Activation-Befehle; `extend` ist auch auf V1 entfernt; V1 hat
   `audio_availability`.
9. **Fehlende Kernaussage.** V2 hat keine Realtime-/Zwischentranskripte.
10. **Metadaten.** Audit-Datum 2025-05-20 → 2026-09-28; Branchname ergänzt.

## Implementierungsbefunde

Diese Punkte sind Eigenschaften oder mögliche Mängel der **Implementierung**.
Sie wurden dokumentiert, aber gemäß Auftrag **nicht** behoben.

| ID | Befund | Schwere | Client-Auswirkung | Evidenz |
| --- | --- | --- | --- | --- |
| `IMPL-01` | `session_settings.patch` validiert `wakeWord.selection` über den toleranten Resolver (`WakeWordCatalogAuthority.resolve`) und speichert den Rohwert. `"Hey Jarvis"`/`"jarvis"` → `applied`, `requestedSettings["wakeWord.selection"] = ["jarvis"]`. Das widerspricht der Wire-Regel „nur kanonische IDs“ (Root F1), der Handshake-Admission (`not_canonical`) und dem Docstring von `resolve` („Never used for the v2 wire“). Kein Test deckt Aliase im Patch ab. | niedrig | Gering: der Schlüssel ist `next_session` und wird in der laufenden Session nie wirksam; Session-Settings werden nicht in neue Sessions übernommen. Ein Client könnte aber inkonsistente IDs in `requestedSettings` sehen. | `server.py:_validate_wake_selection_key`; `wakeword_catalog.py:resolve`; Trace in `TEST_EVIDENCE.md` §3 |
| `IMPL-02` | Beim Eingabeschluss wird das Ledger geschlossen, bevor das bereits registrierte `activation.input_closed` publiziert wird. Sind zu diesem Zeitpunkt alle Segmente terminal, erscheint `activation.completed`/`.cancelled` mit kleinerem `eventSeq` **vor** `activation.input_closed` derselben Activation. Kein Test legt die Reihenfolge fest. | niedrig–mittel | Clients, die `input_closed` → Terminal annehmen, verarbeiten das Terminal einer „noch offenen“ Activation. Dokumentierte Clientregel: beide Events unabhängig behandeln. | `server.py:_apply_ledger_update`, `_publish_registered_input_close_event`; Traces `manual`/`cancel` |
| `IMPL-03` | `/ws/v2` stellt keinen `logAccess`-Token aus (`create_log_access` wird nur im `/ws/transcribe`-Handler aufgerufen). V2-Clients können `/ws/logs` und `/api/logs/*` nur mit Admin-Key lesen. | niedrig (Funktionslücke) | Kein sessionbezogener Logzugriff für V2-Desktop-Clients. | `server.py` `/ws/v2`- und `/ws/transcribe`-Handler |
| `IMPL-04` | Veralteter Docstring in `api_fastapi_server/activation_commands.py` („`extend` is normalised to `refresh`“), obwohl der Alias entfernt ist. | trivial | keine | `activation_commands.py:74`; `test_protocol_v1_v2_boundary.py::test_the_deprecated_v1_extend_spelling_is_unknown_on_both_wires` |

Widersprüche zwischen Implementierung und Tests wurden nicht gefunden; alle
V2-Suites sind grün.

## 5. Bewertung

**Ist das korrigierte Audit belastbar genug, um als V2-Implementierungsvertrag
für den Client zu dienen?** Ja, mit folgender Einordnung: Nach der Korrektur
stimmen alle clientrelevanten Aussagen der vier Audit-Dateien mit Code, Tests,
Vektoren und Traces überein. Als **gepflegter** Vertrag gilt jedoch
[`docs/client-development/`](../../client-development/README.md); das Audit
bleibt die belegte Momentaufnahme für `f7d2b3cc`. Die offenen Befunde
`IMPL-01` bis `IMPL-03` sind dort als Clientregeln bzw. Einschränkungen
beschrieben und sollten in einem separaten Produktcode-PR entschieden werden.

Die Erstfassung (`cc7d4996`) wäre ohne diese Korrekturen **nicht** geeignet
gewesen: ein danach gebauter Client hätte kein verwertbares Audio gesendet und
mehrere Reihenfolgen und Payloads falsch erwartet.

Dieser Prüfbranch ersetzt den Inhalt von
[marcosudau-vps/voice-stt-server#1](https://github.com/marcosudau-vps/voice-stt-server/pull/1)
vollständig (er enthält dessen Commit plus Korrekturen).
