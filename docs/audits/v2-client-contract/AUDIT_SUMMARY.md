# VoiceSTT V2 Server Contract Audit Summary

**Audit Datum:** 2025-05-20
**Geprüfter Branch:** `audit/v2-client-contract` (abgeleitet von `feat/einheitliche-triggerarchitektur-distributed`)
**Baseline Commit SHA:** `f7d2b3ccd07757172a45b371829b04bcedffab4b`
**Tree SHA:** `731c22d872ab3a3897886bcd6bec582e8332be75`
**Ziel:** Rekonstruktion des tatsächlich implementierten V2-Serververtrages aus Sicht eines neuen Desktop-Clients.

---

## 1. Zusammenfassung der Ergebnisse

Der tatsächlich implementierte VoiceSTT-V2-Serververtrag auf `/ws/v2` unterscheidet sich grundlegend von dem legacy V1-Protokoll auf `/ws/transcribe`. Der V2-Vertrag ist ein streng versionierter, genauigkeitsgehärteter State-Machine-Vertrag, der auf folgenden Hauptsäulen ruht:

1. **Explicit Handshake First (`hello` -> `hello.accepted`):**
   Ohne erfolgreichen Handshake existiert keine Session auf dem Server. Binäraudio oder Commands vor `hello.accepted` führen zum sofortigen Verbindungsabbruch (`4400`). Handshake-Timeout beträgt exakt 10.0s (`4408`).
2. **Kanonische UUID-Identitäten:**
   Alle Identitäten (`clientRunId`, `sessionId`, `commandId`, `activationId`, `segmentId`, `eventId`) sind zwingend kleingeschriebene, bindestrich-getrennte UUIDv4-Strings. Kompakte Hex-Strings werden strikt abgelehnt.
3. **5 Client Commands & 15 Closed Ack Codes:**
   Akzeptierte Commands: `activation.command`, `trigger_suppression.set`, `audio_availability.set`, `session_settings.patch`, `session.snapshot.request`.
   Jedes Command erzeugt genau ein `command.ack`. `accepted: true` gilt **ausschließlich** für `applied` und `no_change`.
4. **Strict `activation.command` Rules:**
   - `action = "activate"`: Akzeptiert ausschließlich `source = "manual"` und verbietet `activationId`. `source = "wake_word"` ist dem Server intern vorbehalten.
   - Control Actions (`refresh`, `finish`, `cancel`): Benötigen zwingend `activationId` und verbieten `source`. Der V1-Alias `extend` existiert auf V2 nicht mehr (`refresh` ist vorgeschrieben).
5. **Sequenced Domain Events & State Versioning:**
   Jedes Event besitzt eine globale Session-Sequenz `eventSeq` zur Lückenerkennung und ein `stateVersion`-Feld. Diagnostische Events (`watchdog.warning`, `activation.trigger_suppressed`) erhöhen `stateVersion` nicht.
6. **Snapshot als Resynchronisierungsanker:**
   Bei Event-Lücken fordert der Client `session.snapshot.request` an. Der Server-Snapshot ist 100% autoritativ.
7. **Strict Wake-Word Wire Admission:**
   Der V2-Wire akzeptiert ausschließlich kanonische Wake-Word-IDs (z.B. `"hey_jarvis"`). Aliase oder Display-Namen führen zur sofortigen Session-Ablehnung (`session.rejected`).

---

## 2. Evidenz-Statistik

| Evidenzklasse | Anzahl Fakten | Beschreibung |
| --- | --- | --- |
| `CODE+TEST+CONTRACT_VECTOR` | 8 | Durch Code, automatisierte Tests und Repository-Vertragsvektoren (`protocol-v2-vectors.json`) dreifach abgesichert. |
| `CODE+TEST` | 11 | Durch ausführbaren Python-Quellcode und automatisierte Pytest-Unittests abgesichert. |
| `UNRESOLVED_CONFLICT` | 0 | Keine ungelösten Widersprüche in der V2-Implementierung gefunden. |
| **Gesamt verifizierte Fakten** | **19** | Sämtliche zentralen Wire-Anforderungen in `V2_CLIENT_FACT_MATRIX.md` abgebildet. |

---

## 3. Dokumentations-Diskrepanzen & Findings

1. **`docs/client-development/` ist überwiegend V1-zentriert:**
   Dokumente wie `01-session-und-server-scope.md` und `02-websocket-protokoll.md` beschreiben primär das V1-Protokoll `/ws/transcribe` (z.B. unaufgefordertes Server-Hello, `trigger_ack`, `start`/`stop`/`clear` Commands). Für V2-Desktop-Clients müssen diese Dokumente als `STALE_V1` markiert und stattdessen `V2_CLIENT_CONTRACT_REFERENCE.md` verwendet werden.
2. **Legacy `extend` Alias:**
   Ältere Dokumente erwähnten den V1-Alias `extend`. Dieser ist auf V2 vollständig entfernt und wird als `invalid_payload` abgelehnt (`refresh` ist der kanonische V2-Command).
3. **Nicht dokumentiertes Handshake Timeout:**
   Der Close-Code `4408` (`CLOSE_HANDSHAKE_TIMEOUT`) bei Überschreitung des 10.0s Limit war im Code implementiert und getestet, aber in der bestehenden Client-Dokumentation nicht explizit aufgeführt.

---

## 4. Ausgeführte Tests und Verifikation

Im Rahmen der Auditerstellung wurden folgende Testsuites erfolgreich ausgeführt:

* `python3 -m pytest tests/unit/test_protocol_v2_contract.py`
  **Resultat:** 66 passed, 1 skipped. (Deckt Handshake, Envelope, Ack-Projektion, Command Replay und Snapshot Invarianten ab).
* `python3 -m pytest tests/unit/test_wake_admission.py`
  **Resultat:** 14 passed. (Deckt atomare Wake-Word-Selection Admission und Fehlercodes ab).

Keine produktiven Code- oder Testdateien wurden während dieses Audits geändert. Sämtliche Befunde wurden ausschließlich in den neuen Audit-Dokumenten in `docs/audits/v2-client-contract/` persistiert.
