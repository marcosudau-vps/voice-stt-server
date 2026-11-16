# Bestätigte Korrekturen am V2-Client-Audit

Bezug: Audit-Commit `cc7d4996d04c5ca756be9798102629bc2713ce2f`, geprüft gegen
`f7d2b3ccd07757172a45b371829b04bcedffab4b`. Jede Korrektur ist in den Dateien
unter [`../v2-client-contract/`](../v2-client-contract/) umgesetzt; die
Fakt-IDs verweisen auf [`FACT_REVIEW_MATRIX.md`](FACT_REVIEW_MATRIX.md).

## 1. Sachliche Fehler

| # | Fundstelle(n) | Fehler | Korrektur | Fakt |
| --- | --- | --- | --- | --- |
| F-01 | MATRIX `AUD-001`; REF §9.1, §21; MIG „Audio Framing“ | 8-Byte-Header `VSTT`/Version/Flags. | `uint32` LE Metadatenlänge · UTF-8-JSON-Objekt · PCM `pcm_s16le`; `sampleRate` Pflicht, beliebige Rate. | `AUD-001`, `MIG-06` |
| F-02 | REF §9.1 | Max. 64 KB pro Frame. | 64 KiB = Metadatengrenze; PCM ≤ `max_audio_packet_bytes` (Standard 524 288 B). | `S-10` |
| F-03 | REF §9.2 | Audio bei `audioAvailable=false` wird mit `accepted=false` verworfen. | Audio wird nie quittiert und weiter eingespeist; die Sperre betrifft Activations. | `S-11` |
| F-04 | REF §1.3A, §19.2, §8.1 | Leere/teilweise Settings-Maps im Snapshot. | Vollständige 16 Session-Schlüssel. | `S-03`, `S-09` |
| F-05 | REF §13.2 | Katalog-JSON mit `serverVersion`, `serverCommit`, `unavailableReason: null`, ohne `artifactVersion`/`backends`/Eintragsrevision. | Tatsächliche Struktur eingesetzt. | `HTTP-001`, `S-16` |
| F-06 | REF §14 | `GET /api/v2/health` existiert. | Entfernt; `GET /health` beschrieben. | `S-17` |
| F-07 | REF §15 | Admin-Auth „am Gateway“. | Admin-Auth im Anwendungscode (`admin_auth_error`). | `S-18` |
| F-08 | REF §19.5 | `invalid_payload`-Ack mit `errors[]`. | `errors[]` nur bei Settings-Ergebnissen. | `S-21` |
| F-09 | REF §10.2 | Ack vor Event; `wakeword.detected` vor `activation.started` mit gleicher `stateVersion`; `reason="silence_timeout"`. | Reale Reihenfolge und Werte aus Trace/Code. | `S-13` |
| F-10 | REF §13.1 | Aliase in `wakeWord.selection` werden abgelehnt. | Im Patch akzeptiert (Befund `IMPL-01`). | `WAKE-001`, `S-15` |
| F-11 | MIG „Manual Start/Stop“ | V1 `start`/`stop` als Activation-Befehle, `trigger action start/stop`. | V1 `start`/`stop` = Stream; V1 `trigger` `activate`/`finish`. | `MIG-01`, `MIG-02` |
| F-12 | MIG „Extend“; SUMMARY §3.2 | `extend` als gültiger V1-Vertrag. | Auf beiden Transporten entfernt. | `CMD-004`, `MIG-03` |
| F-13 | MIG „Audio Availability“ | In V1 nicht vorhanden. | V1 `audio_availability` + `audio_availability_ack`. | `MIG-08` |
| F-14 | SUMMARY §2 | Keine ungelösten Widersprüche. | Drei Implementierungsbefunde dokumentiert. | `S-23` |

## 2. Unbelegte Aussagen

| # | Fundstelle | Aussage | Behandlung |
| --- | --- | --- | --- |
| U-01 | REF §15 | `/ws/v2`-Schutz erfolgt per Reverse Proxy/API-Gateway. | Als Deploymentannahme gekennzeichnet; Repository-Fakt: keine Authentisierung im Handler. |
| U-02 | REF §9.2 | Pre-Roll wird jeder Activation vorgeschaltet. | Auf Wake-Word + `wakeWord.preRollMs` eingeschränkt. |
| U-03 | REF §9.1 | „Typische“ Framegrößen 20–100 ms als Vertrag. | Als Empfehlung markiert (Browserclient nutzt `ScriptProcessor`-Puffer). |
| U-04 | MATRIX Evidenzklassen | `HS-001`, `HS-002` als `CODE+TEST+CONTRACT_VECTOR`. | `HS-001` hat keinen Vektor; Klasse korrigiert. |

## 3. Formulierungs- und Präzisionsmängel

| # | Fundstelle | Mangel | Korrektur |
| --- | --- | --- | --- |
| W-01 | `HS-002`, REF §2 | „UUIDv4“ statt „kanonische UUID“. | Präzisiert, v4 als Empfehlung. |
| W-02 | REF §2 | `clientId` als Protokollidentität. | Als optionales Transportmetadatum beschrieben. |
| W-03 | REF §4.2 | Bedeutungen von `activation_locked`, `invalid_phase`, `closing_input`, `stale_session`, `trigger_suppressed`, `audio_unavailable`. | Nach Controller-Logik neu formuliert. |
| W-04 | REF §6.1, `EVT-002` | `stateVersion` „zählt bei jedem fachlichen Zustandswechsel um +1“ ohne Hinweis auf eventlose Änderungen. | Ergänzt. |
| W-05 | REF §6.2 | Resync ohne Puffern nachfolgender Events. | Regel „Events mit `eventSeq > lastEventSeq` nach dem Snapshot anwenden“ ergänzt. |
| W-06 | REF §7.1 | Phasendiagramm ohne `followup_wait → segment_active`. | Ergänzt. |
| W-07 | REF §16 | Reconnect-Formulierung zu `eventSeq`. | Präzisiert; Server kennt keine Wiederaufnahme. |
| W-08 | REF §17 | `1011` nur Handshake. | Ergänzt. |
| W-09 | alle | Fehlende Aussage: keine Realtime-Transkripte auf V2. | Ergänzt (`S-25`). |
| W-10 | alle | Fehlende Aussage: kein `logAccess` auf V2. | Ergänzt (`S-26`). |
| W-11 | REF §5, §10 | Reihenfolge `input_closed` vor Terminal als garantiert dargestellt. | Als nicht garantiert markiert (`IMPL-02`). |

## 4. Falsche Quellenverweise

| Fakt | Zitiert | Tatsächlich |
| --- | --- | --- |
| `HS-001` | `test_protocol_v2_contract.py:test_first_message_must_be_hello` | `test_protocol_v2_e2e.py::test_first_message_must_be_hello` |
| `HS-004` | `test_handshake_timeout` | `test_protocol_v2_e2e.py::test_a_silent_client_hits_the_handshake_timeout` |
| `CMD-004` | `test_command_extend_rejected_on_v2` | `test_protocol_v2_contract.py::test_extend_alias_does_not_exist_in_v2` u. a. |
| `ACK-001` | `test_command_ack_accepted_set` | `test_protocol_v2_contract.py::test_accepted_is_true_for_exactly_two_results` |
| `EVT-001` | `test_event_sequencing` | `test_protocol_v2_contract.py::test_event_seq_is_strictly_monotonic` |
| `AUD-001` | `test_protocol_v1_v2_boundary.py` (kein Audiotest) | `test_browser_client_contract.py`, V2-E2E über `speech_packet()` |
| `HTTP-001` | `server.py:get_wake_words_v2` | `server.py` Route-Funktion `wake_words_v2` |
| `EVT-003` | `events.py:LEGACY_EVENT_TYPES` als Primärbeleg | `events.py` `_observe_phase`/`_project_drained`, `snapshot.py` `build_pending_activations` |

## 5. Metadatenfehler

| # | Fundstelle | Fehler | Korrektur |
| --- | --- | --- | --- |
| M-01 | SUMMARY Kopf | `Audit Datum: 2025-05-20` – liegt vor jedem geprüften Commit; der Audit-Commit stammt vom 2026-09-28 (`git log -1 --format=%ad cc7d499`: `Mon Sep 28 00:04:00 2026 +0000`). | Auf 2026-09-28 gesetzt, Korrekturdatum ergänzt. |
| M-02 | SUMMARY Kopf | Branch `audit/v2-client-contract` | Tatsächlicher Branch `audit/v2-client-contract-9436684549960924324`. |
| M-03 | REF Kopf | `Document Version: 1.0.0`, Status „Rekonstruierte Wahrheit“ | Version 1.1.0 (korrigiert), Status mit Verweis auf die kanonische Doku. |
| M-04 | SUMMARY §2 | Evidenzstatistik | Neu berechnet nach korrigierten Klassen. |
