# VoiceSTT V2 Server Contract Audit Summary

**Audit-Datum:** 2026-09-28 (Erstfassung, Commit `cc7d4996d04c5ca756be9798102629bc2713ce2f`)
**Korrigiert:** 2026-09-28 durch die unabhängige Prüfung in [`../v2-client-contract-review/`](../v2-client-contract-review/INDEPENDENT_REVIEW.md)
**Audit-Branch:** `audit/v2-client-contract-9436684549960924324` (abgeleitet von `feat/einheitliche-triggerarchitektur-distributed`)
**Baseline Commit SHA:** `f7d2b3ccd07757172a45b371829b04bcedffab4b`
**Tree SHA:** `731c22d872ab3a3897886bcd6bec582e8332be75`
**Ziel:** Rekonstruktion des tatsächlich implementierten V2-Serververtrages aus Sicht eines neuen Desktop-Clients.

> Die gepflegte, kanonische V2-Client-Dokumentation ist
> [`docs/client-development/`](../../client-development/README.md). Dieses
> Audit hält den geprüften Stand von `f7d2b3cc` fest.

---

## 1. Zusammenfassung der Ergebnisse

Der V2-Vertrag auf `/ws/v2` unterscheidet sich grundlegend vom
Legacy-V1-Protokoll auf `/ws/transcribe`:

1. **Client-first Handshake (`hello` → `hello.accepted`).**
   Ohne angenommenes `hello` existiert keine Session. Ein ungültiges erstes
   Frame oder Binäraudio vor `hello.accepted` schließt mit `4400`; ohne erstes
   Frame binnen 10,0 s schließt der Server mit `4408`.
2. **Kanonische UUID-Identitäten.**
   `clientRunId`, `sessionId`, `commandId`, `activationId`, `segmentId` und
   `eventId` sind kleingeschriebene, bindestrich-getrennte UUID-Strings. Der
   Server erzeugt uuid4; geprüft wird nur die kanonische Schreibweise, nicht
   die UUID-Version. Kompakte Hex- oder großgeschriebene Formen werden
   abgelehnt.
3. **5 Client-Commands, 15 Result-Codes.**
   `activation.command`, `trigger_suppression.set`, `audio_availability.set`,
   `session_settings.patch`, `session.snapshot.request`. Jeder erkennbare
   Command mit kanonischer `commandId` erhält pro Empfang genau ein
   `command.ack`; `accepted: true` gilt ausschließlich für `applied` und
   `no_change`. Commands ohne kanonische `commandId`, unbekannte Typen und
   nicht parsebares JSON bleiben ohne Antwort.
4. **Strenge `activation.command`-Regeln.**
   `activate` nur mit `source = "manual"` und ohne `activationId`-Schlüssel;
   `refresh`/`finish`/`cancel` nur mit `activationId` und ohne
   `source`-Schlüssel. `extend` existiert weder auf V2 noch – seit AP-SRV-070 –
   auf V1.
5. **Sequenzierte Events und `stateVersion`.**
   17 Eventtypen mit lückenlosem `eventSeq` ab 1. `stateVersion` steigt bei
   jeder sichtbaren Zustandsänderung, auch bei solchen ohne Event
   (`closing_input`-Eintritt, Suppression, Audioverfügbarkeit); die
   diagnostischen Events `watchdog.warning` und
   `activation.trigger_suppressed` erhöhen sie nicht. Events eines Commands
   werden vor seinem Ack gesendet.
6. **Snapshot als Resynchronisierungsanker.**
   Bei Lücken fordert der Client `session.snapshot.request` an (Ack `applied`,
   danach `session.snapshot`) und ersetzt seinen Zustand vollständig.
7. **Wake-Word-Admission.**
   `hello.requestedSession.wakeWordIds` akzeptiert nur kanonische IDs
   (`hey_jarvis`); Aliase/Anzeigenamen lehnen die Session ab
   (`wake_word_unavailable`, `reason = not_canonical`). Abweichend davon
   akzeptiert `session_settings.patch` für `wakeWord.selection` Aliase
   (Implementierungsbefund `IMPL-01`).
8. **Audio-Transport.**
   Ein Binärframe = `uint32` Little-Endian-Metadatenlänge · UTF-8-JSON
   (`sampleRate` Pflicht) · PCM `pcm_s16le`. V1 und V2 teilen den Decoder.
   Die Erstfassung dieses Audits beschrieb fälschlich einen 8-Byte-`VSTT`-Header.
9. **Keine Realtime-Transkripte, kein `logAccess` auf V2.**

---

## 2. Evidenz-Statistik (nach Korrektur)

| Evidenzklasse | Anzahl Fakten |
| --- | ---: |
| `CODE+TEST+CONTRACT_VECTOR` | 8 |
| `CODE+TEST` | 11 |
| `UNRESOLVED_CONFLICT` (Implementierungsbefunde) | 3 |
| **Fakten in `V2_CLIENT_FACT_MATRIX.md`** | **19** |

Die Urteile der unabhängigen Prüfung über die 19 Fakten: 16 `CORRECT`,
2 `PARTIALLY_CORRECT`, 1 `INCORRECT` (Audio-Framing, inzwischen korrigiert),
0 `UNPROVEN`. Details:
[`FACT_REVIEW_MATRIX.md`](../v2-client-contract-review/FACT_REVIEW_MATRIX.md).

---

## 3. Dokumentations-Diskrepanzen & Findings

1. **`docs/client-development/` war V1-zentriert.** Die Seiten beschrieben
   `/ws/transcribe` (Server-`hello`, `ready`, `start`/`stop`/`clear`,
   `trigger_ack`). Sie wurden im Zuge der Prüfung auf V2 umgestellt; die
   V1-Fassung liegt als Legacy unter
   [`docs/client-development/legacy-v1/`](../../client-development/legacy-v1/README.md).
2. **`extend`** ist auf beiden Transporten entfernt; V1 antwortet mit
   `trigger_ack.reason = invalid_action`, V2 mit `invalid_payload`.
3. **Handshake-Timeout.** `4408` stand bereits in
   `docs/einheitliche-triggerarchitektur.md` §12.2, der Wert 10 s nicht.
4. **Offene Implementierungsbefunde** (keine Doku-Fehler, nicht in diesem
   Audit behoben): `IMPL-01` tolerante Wake-Word-Auswahl im Session-Patch,
   `IMPL-02` Activation-Terminal kann vor `activation.input_closed`
   eintreffen, `IMPL-03` kein `logAccess` für V2-Sessions. Siehe
   [`INDEPENDENT_REVIEW.md`](../v2-client-contract-review/INDEPENDENT_REVIEW.md).

---

## 4. Ausgeführte Tests und Verifikation

Erstfassung:

* `python3 -m pytest tests/unit/test_protocol_v2_contract.py` → 66 passed, 1 skipped.
* `python3 -m pytest tests/unit/test_wake_admission.py` → 14 passed.

Die unabhängige Prüfung hat beide Ergebnisse reproduziert und weitere Suites
ausgeführt; siehe
[`TEST_EVIDENCE.md`](../v2-client-contract-review/TEST_EVIDENCE.md).

Keine produktiven Code- oder Testdateien wurden während des Audits oder der
Prüfung geändert.
