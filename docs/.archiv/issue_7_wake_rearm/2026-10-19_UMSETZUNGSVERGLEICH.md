# Issue #7: Soll-/Ist-Vergleich und Impact-Audit

Stand: 2026-10-19. Implementierungsnachweis, keine unabhaengige Abnahme.

## Identitaet und Veroeffentlichungsgrenze

Repository: `marcosudau-vps/voice-stt-server`.
Basis und unveraenderter Zielbranch-HEAD:
`ada13b011e1d3829f78e7f389e3b927795a2b3be`,
`feat/einheitliche-triggerarchitektur-distributed`.

Vorher-Nachweiscommit: `4da6c0e`.
Gepruefter Produktcommit:
`f0eac1883ed82bd32afef0b5623a0ec74b58592a`.
Arbeits-/Abgabebranch: `marcosudau-wake-rearm-reset`.
Spaetere Commits dieser Aktion dokumentieren Ergebnisse, nicht weitere
Produktveraenderungen. Abgabe erfolgt als PR genau gegen den Zielbranch.
Der Produktcommit wurde auf diesen Arbeitsbranch gepusht und mit dem
GitHub-Branch-HEAD abgeglichen; der Zielbranch blieb auf dem genannten
Basiscommit. Der abschliessende Dokumentations-HEAD und die PR-Basis werden
bei der Abgabe nochmals kontrolliert. Kein Produktserver, VPS, Release oder
Deployment geaendert. Der Registerstatus bleibt `Pruefung offen`, bis die
gesonderte unabhaengige Pruefung erfolgt ist.

## G0-G4 und Pflichtfaelle

| Soll | Ist / Evidenz | Status |
| --- | --- | --- |
| G0 sauberer korrekter Ausgang | Ziel-HEAD bestaetigt, Regeln gelesen, Lifecycle/Locks und enger Scope vor Implementierung dokumentiert | PASS |
| G1 urspruenglichen Fehler reproduzieren | Roter produktiver Worker-Test: zwei statt einer Admission; echtes Alexa-Replay bestaetigt denselben Stillehit | PASS |
| G2 Modellzustand vor Rearm bereinigen | Upstreamreset vor Latchfreigabe, Fail-closed-Engine, bestehende Locks und Generationen | PASS |
| R1 Stille nach Close | `test_input_close_then_digital_silence_never_opens_a_second_activation` vor Fix FAIL, nach Fix PASS | PASS |
| R2/R3 neue Phrase und wiederholte Zyklen | 12 Closezyklen plus sofortige 13. Detection; keine zusaetzliche Zeitfortschaltung | PASS |
| R4 Finish/Cancel/Timeout | Finish, Cancel, Initial- und Followup-Timeout mit echtem Controller; idempotente Freigabe; Finish/Cancel zusaetzlich auf dem v2 Wire | PASS |
| R5 In-flight/Generationen | Event-gesteuerte Threads fuer Inferenz gegen Generationenreset und Engineinferenz gegen Rearm; alte Hits/Close-IDs und Callback-Rueckkehr nach Close | PASS |
| R6 absolute Sampleposition | Produktionsworker, 100 pausierte Chunks, zweiter Nullpunkt exakt bei Sample `103 * 1280` | PASS |
| R7 Pre-Roll/Nutzsprache | Echte Worker-Trimmung mit 0, 10 und 10000 ms; History-Clamp; zwei folgende Nutzsprachchunks bytegenau erhalten | PASS |
| R8 Framebuchhaltung | 20/40/80 ms, ausstehende alte 320 Samples verworfen, nur frische Frames zaehlen | PASS |
| R9 Resetfehler | Fehlender/werfender Upstreamreset sperrt Wake; kein Wiederverwenden alter Hits; manuelle Activation und sicherer Input-Close funktionieren weiter | PASS |
| R10 Events/Admission | Genau ein logisches Event je angenommenem Hit; exakter Score `0.91` in Wire und Log, korrekte unterschiedliche IDs, gleiche Felder und geordnete Sequenzen | PASS |
| R11 andere Trigger/Sessions/Modelle | Manuell trotz Wakefehler nutzbar; Streamstop/restart, Clear, Audioverlust und Sessionclose invalidieren alte Hits; generischer Rearm fuer alle 25 Katalog-IDs | PASS |
| R12 Konfiguration | Cooldown ueberlebt Close; neue Threshold-/Min-Frames-/Pre-Roll-/Revisionssnapshots; bestehende Gain-/Sensitivity-/Settings-Suites | PASS |
| G3 gezielte Pflichtsuite | 354 Tests, 312.102 s, keine Fehler und keine Skips | PASS |
| G4 finaler Impact-Audit | Produktdiff je Datei begruendet; keine Protokoll-, Client-, V1-, Build-, Release- oder Deploymentdatei geaendert | PASS |
| Vollstaendige Fast-Suite | 1980 PASS, 14 bestehende SKIP, 1296 Subtests PASS; 623.05 s auf eingefrorenem finalem Produktquelltext | PASS |
| Reale ONNX-Replays | Alexa/Hey Jarvis, sechs Vergleichsreihen; portabler archivierter Helfer identische Ergebnisse und Exitcode 0 | PASS |
| Physische Mikrofonpruefung | Kein neuer Hardwarelauf | NOT RUN |
| Clientqualifikation AP-IV2-020 | Gesonderter Auftrag/Freigabe erforderlich | BLOCKED |
| CI | PR-gebundene externe Pruefung ausstehend | NOT RUN |

## Ausgefuehrte Pflichtsuite

```powershell
python -m unittest -v tests.unit.test_wake_detection tests.unit.test_wakeword_recording_path tests.unit.test_wake_audio_boundary tests.unit.test_wake_admission tests.unit.test_wakeword_root_findings_c2 tests.unit.test_wakeword_root_findings_c3 tests.unit.test_wakeword_session_e2e tests.unit.test_protocol_v2_e2e tests.unit.test_protocol_v2_races tests.unit.test_protocol_v2_settings tests.unit.test_settings_control_plane
python -m pytest -q -rs tests\unit
```

Baseline vor Fix: 338 bestehende Pflichtmodultests PASS (251.020 s).
Finale Pflichtsuite: 354 PASS (312.102 s). Dazwischen wurden fehlgeschlagene
Testentwicklungslaeufe korrigiert, ohne vorhandene Assertions abzumildern.
`git diff --check` und Python-Kompilation der fuenf Produktmodule bestanden.
Rohlogs/XML bleiben im Sessionartefaktverzeichnis, nicht im Repository.

Die vollstaendige Fast-Suite bestand mit 1980 PASS, 14 SKIP und 1296
bestandenen Subtests (623.05 s). Keine neuen Skips wurden eingefuehrt.
Zusaetzlich bestanden die bestehenden Dokumentationsguards
`test_docs_surface.py` und `F15ContractDocumentationTests` mit 35 PASS und
42 bestandenen Subtests; alle 25 relativen Links der betroffenen aktuellen
und archivierten Markdown-Dokumente wurden auf vorhandene Ziele geprueft.

| Bestehender Skipgrund | Anzahl |
| --- | --- |
| Opt-in-Modellsmokes Cohere, Granite, Moonshine, Parakeet, Qwen3 nicht aktiviert | 5 |
| Opt-in-Goldentranskription faster-whisper/LJ Speech nicht aktiviert | 1 |
| Opt-in-Realmultiuser-ASR/Performance nicht aktiviert | 1 |
| Opt-in-Kroko-ONNX-Replay nicht aktiviert | 1 |
| Opt-in-OpenAI-Whisper-Goldentest nicht aktiviert | 1 |
| Externe Planungsvektoren fuer `VOICESTT_PROTOCOL_V2_VECTORS` fehlen | 1 |
| Opt-in-sherpa-ONNX-Smokes Moonshine und Parakeet nicht aktiviert | 2 |
| Silero-Integration: erforderliche Kombination aus `silero-vad`, `onnxruntime` und `torch` nicht vollstaendig vorhanden | 1 |
| Opt-in-whisper.cpp-Goldentest nicht aktiviert | 1 |

Diese 14 Faelle sind SKIP, keine bestandenen Modell-/Integrationspruefungen.
Der korrigierte Zwischenlauf ist getrennt in der
[Abweichungsdatei](2026-10-19_ABWEICHUNGEN.md) dokumentiert.

## Echte Modelle und reproduzierbare Eingaben

Windows/Python 3.12.10, NumPy 1.26.4, OpenWakeWord 0.6.0,
ONNX Runtime 1.28.0, CPU, `OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1`,
Seed 0, 40-ms-Chunks, Sensitivity 0.5, kein Cooldown.
Unveraenderte gebuendelte Alexa- und Hey-Jarvis-ONNX-Modelle,
keine Modelldownloads und keine laufende Serversession.

Die [Inputidentitaeten und Originalfreigabe](2026-10-19_REPRODUKTION.md)
verweisen auf den im Issue gepinnten Clientcommit. WAVs nur ausserhalb des
Serverrepositories ablegen. Der portable Helfer verlangt die Originalhashes:

```powershell
$env:OPENBLAS_NUM_THREADS = "1"
$env:OMP_NUM_THREADS = "1"
python docs\.archiv\issue_7_wake_rearm\2026-10-19_ONNX_REPLAY.py --audio-dir <autorisierter-WAV-Ordner> --out <externe-Ergebnisdatei.json>
```

| Replay | Vorher | Nachher |
| --- | --- | --- |
| Alexa, erster Treffer | `0.9997421503067017` | identisch |
| Alexa, digitale Stille nach Rearm | falscher Hit `0.8239456415176392` nach 240 ms | kein Hit in 5 s; maximal `0.0000404417514801` |
| Alexa, WAV sofort erneut starten | alter Kontext konnte schon nach 240 ms triggern | neue Phrase `0.9997421503067017` nach 1760 ms WAV-Audio |
| Hey Jarvis, erster Treffer | `0.9871283769607544` | identisch |
| Hey Jarvis, digitale Stille nach Rearm | kein Hit fuer diese Aufnahme | kein Hit in 5 s |
| Hey Jarvis, WAV sofort erneut starten | neuer Hit moeglich | `0.9871283769607544` nach 1520 ms WAV-Audio |

Die erhaltene-Historie-Kontrolle reproduziert Alexa weiterhin mit `0.8239456`;
der Produktpfad tut das nicht. Die Pause ist emuliert, kein 15-s-Wandzeitlauf.
WAV-Neustart ist Replay, keine neue menschliche Wakephrase, und die Laufzeit
bis zum Treffer ist kein eingefuehrter Cooldown. Keine Aussage ueber die
historische Mikrofonakustik oder Soundrueckkopplung.

## Datei-fuer-Datei-Audit

| Geaenderte Datei | Technische Notwendigkeit |
| --- | --- |
| `VoiceSTT/core/openwakeword_engine.py` | Resetfehler nicht mehr verschlucken, weitere Inferenz sperren; absolute Chunk-Endposition fuer Frames uebernehmen |
| `VoiceSTT/core/wake_detection.py` | Reset vor Latchfreigabe; Inferenz/Tracker gegen Reset serialisieren; alte Detektorgeneration invalidieren |
| `VoiceSTT/core/recording.py` | Vorhandenen Absolutcursor weiterreichen; autoritative v2 Latch lesen; alte Grenzen nicht in spaetere Aufnahme tragen |
| `api_fastapi_server/wake_admission.py` | Alte Generation oder weiterhin gelatchte Detection vor Activationcommit ablehnen |
| `api_fastapi_server/server.py` | Vorhandene Lifecyclegrenzen ausserhalb von Session-/Ledgerlocks an Detektorgeneration binden; Close ohne passende ID ist kein Rearm |
| `tests/unit/test_wakeword_recording_path.py` | Zustandsbehafteter roter/gruener Repro plus deterministische R1-R9/R11/R12, keine Modelle/Hardware noetig |
| `tests/unit/test_wakeword_session_e2e.py` | Produktive Closepfade/Streamwechsel, v2 Events/Score/IDs/Reihenfolge und manuelle Activation trotz Resetfehler |
| `tests/unit/test_wakeword_root_findings_c3.py` | Bestehendes Evaluator-Testdouble bildet nun den tatsaechlich geprueften Generationenvertrag ab; keine Assertion entfernt |
| `docs/wake-words.md` | Dauerhafte Fachdokumentation fuer Rearm, Fehlergrenze und absolute Audiopositionen |
| `docs/.archiv/README.md` | Pflichtregistrierung und offener unabhaengiger Pruefstatus |
| `2026-10-19_PLAN.md` in diesem Ordner | G0 und Gesamtplanung vor Produktimplementierung |
| `2026-10-19_REPRODUKTION.md` | Getrennter historischer ROT-Nachweis und Ausgangsmessungen |
| `2026-10-19_ONNX_REPLAY.py` | Portabler nachpruefbarer Realmodellvergleich ohne Containerbindung und ohne binaere Inputs |
| `2026-10-19_ABWEICHUNGEN.md` | Branchabweichung, begruendeter Umfang, Testgrenzen und Zwischenlauf transparent erhalten |
| `2026-10-19_UMSETZUNGSVERGLEICH.md` | Dieser getrennte Gegenvergleich, Testergebnisse und Impact-Audit |

## Unveraenderte Invarianten und Restrisiken

Keine Threshold-/Score-/Min-Frames-Kalibrierung, kein neuer Cooldown,
kein zusaetzliches Wire-/Logfeld, keine neue Settingsautoritaet und kein
Umbau von ActivationController, Boundaryformel, VAD oder Transkription.
Engine-, Evaluator-, Coordinator- und Sessionlocks bleiben die bestehenden.
Inferenz haelt keine Session-/Admissioncallbacks; Sessionreset wartet
ausserhalb von Session- und Ledgerlocks auf die Wake-Pipeline.
Andere Sessions besitzen weiterhin eigene Engine-/Evaluatorinstanzen.
V1 laeuft ohne v2 Evaluator durch den unveraenderten Legacyzweig.

Ein Resetfehler bleibt sichtbar im Logger und in internen Diagnosen, ohne
erfolgreiches Rearm vorzutaeuschen. Die neue Fehlerzustandsvariable ist auf
eine Engine begrenzt. Ein Stream-/Sessionneustart kann explizit erneut resetten.

Nicht bewiesen sind absolute Abwesenheit aller moeglichen Races,
akustische Qualitaet aller Modelle, neue physische Mikrofon-/Soundtests und
die externe Clientqualifikation. Siehe
[Abweichungen/offene Qualifikation](2026-10-19_ABWEICHUNGEN.md).

Unabhaengige Reviewer sollen Resetzeitpunkt und Vollstaendigkeit,
Lockreihenfolge, stale Hit-/Close-Verhalten, Cursor nach Pause, reale
Workertrimmung und Pre-Roll, fail-closed Fehlerpfad sowie unveraenderte
v2 Eventvertraege nachpruefen. Kein Merge-/Release-/Promotionsvotum enthalten.
