# PR #8 / P1: Gegenpruefung der Clear-/Admission-Korrektur

Stand: 2026-10-19. Nachtrag zum unabhaengigen Reviewbefund, keine
selbsterteilte Review- oder Mergefreigabe.

## Gepruefte Identitaeten

- Repository: `marcosudau-vps/voice-stt-server`.
- Bestehender [PR #8](https://github.com/marcosudau-vps/voice-stt-server/pull/8),
  Branch `marcosudau-wake-rearm-reset`, Ziel
  `feat/einheitliche-triggerarchitektur-distributed`.
- Vom Review beanstandeter Stand:
  `3475f1d43dab945443e8c38d8c877a25d32528d8`.
- Vorab registrierte [P1-Planung](2026-10-19_P1_CLEAR_PLAN.md).
- Separater ROT-Commit:
  `0a57c43`, Produktcode darin weiterhin unveraendert.
- Gepruefter Korrekturcommit:
  `629a912551e4a7e6fb8c8def9d01177b079d6e9b`.
- Danach nur Nachweisdokumentation; Produkt- und Testquellen wurden waehrend
  der vollstaendigen Fast-Suite nicht mehr veraendert.

Der urspruengliche Soll-/Ist-Vergleich bleibt historische Evidenz des
beanstandeten Stands. Seine damalige Aussage zur Clear-Invalidierung bewies
noch nicht die jetzt erzwungene konkurrierende Admission. Dieser Nachtrag
berichtigt diese Nachweisluecke, ohne die Originalberichte umzuschreiben.

## Exakte Root Cause und Korrekturgrenze

Vorher setzte `clear()` die Sessiongeneration und Activation unter dem
Sessionlock zurueck. Anschliessend wurde dieses Lock freigegeben, bevor
`_reset_wake_detector()` das Coordinatorlock nahm und die Detektorgeneration
wechselte. Die Session war bereits wieder fuer eine Activation frei, aber
ein schon berechneter Hit besass noch die aktuelle Detektorgeneration.
`admit()` konnte daher Generation/Latch erfolgreich pruefen und danach
unter dem Sessionlock eine falsche neue Activation committen. Die
unveraenderte Lifecycleepoche verhinderte das nicht.

Jetzt umschliesst das **vorhandene Coordinator-RLock** Sessionreset und
anschliessenden Detektorreset. Der kleine Contextmanager
`suspend_admission()` erzeugt weder einen neuen Lock noch neuen Zustand.
`clear()` betritt ihn vor dem Sessionlock und gibt den Sessionlock frei,
bevor es auf Evaluator/Engine wartet.

Die eindeutige Grenze ist der Sessionreset innerhalb dieses exklusiven
Coordinatorabschnitts: Eine zuvor bereits zugelassene Admission muss zuerst
vollstaendig beendet sein und wird dann durch Clear regulaer geschlossen.
Eine spaeter eintretende Admission wartet bis zur Detektorinvalidierung und
verwirft den alten Hit anhand seiner Generation. Auch bereits vor Clear
wartende Admissionthreads duerfen nach dieser Grenze nicht mehr mit der
alten Generation committen. Neue Hits nach abgeschlossenem Clear werden
normal angenommen.

Lockpfade:

```text
Admission: Coordinator -> Evaluatorpruefung (freigegeben) -> Session
           -> Evaluatoraccept -> Eventledger/Delivery
Clear:     Coordinator -> Sessionreset -> Sessionfreigabe
           -> Evaluator -> Engine -> Coordinatorfreigabe
Inferenz:  Evaluator -> Engine, keine Session-/Admissioncallbacks
```

Alle bisherigen Clear-Aufrufstellen wurden auf ein bereits gehaltenes
Sessionlock geprueft; die produktive WebSocket-Aufrufstelle haelt keines.
Der Policyread benutzt den eigenen Settingslock, nicht das Sessionlock.
Der neue Code fuehrt somit keinen Session -> Coordinator/Evaluator-Zyklus
ein. Der Legacyfall ohne Coordinator verwendet `nullcontext()`.

## G1/G2: Tatsaechliches ROT und GRUEN

Unveraendert wiederholter Regressionstest:

```powershell
python -m pytest -q tests\unit\test_wakeword_session_e2e.py::WakeEventTests::test_clear_serializes_pending_hit_admission_until_detector_invalidation tests\unit\test_wakeword_session_e2e.py::WakeEventTests::test_clear_waits_for_inflight_inference_without_holding_session_lock
```

Der erste Test wurde allein vor dem Produktfix ausgefuehrt:
**1 FAIL in 8.70 s**, Exitcode 1. Er erhielt eine echte
`AcceptedWakeDetection` mit Score `0.91`, alter Generation 0 und neuer
Activation-ID statt `None`. Vollstaendiger Ablauf im separaten
[historischen ROT-Nachweis](2026-10-19_P1_CLEAR_REPRODUKTION.md).

Nach Fix: beide Tests **2 PASS in 4.00 s**, Exitcode 0. Sie bestanden auch
erneut in Pflichtsuite und vollstaendiger Fast-Suite.

Der erste Test haelt Clear direkt vor dem Detektorreset an und bietet
parallel den zuvor berechneten Hit an. Ein transparenter Wrapper prueft das
echte Coordinator-RLock nichtblockierend und signalisiert den Versuch per
Event. Vorher wird der falsche Commit vollstaendig abgewartet, bevor Clear
weiterlaeuft; nachher muss Admission bis nach Reset warten. Das Ergebnis
wird fachlich geprueft, nicht nur ein Methodenaufruf oder Lockflag.
Danach bleiben derselbe alte Hit und digitale Stille wirkungslos; eine
frische Phrase oeffnet genau eine Activation und ein passendes Wakeevent.

Der zweite Test haelt echte Engineinferenz innerhalb des Evaluatorlocks an.
Clear erreicht den Reset und wartet, ohne das Sessionlock zu halten.
Ein anderer Thread kann dieses Sessionlock erwerben. Nach dem
eventgesteuerten Fortsetzen terminieren beide Threads; der alte Hit ist
stale, ein neuer Hit wird genau einmal angenommen. Keine Sleeps und keine
verschluckten Threadexceptions.

## G3/G4: Erneute Ergebnisse

| Pruefung | Ergebnis | Tatsaechlicher Nachweis |
| --- | --- | --- |
| Konkurrierender alter Hit nach Sessionreset | PASS | Kein Commit und kein logisches Event vor/nach Detektorinvalidierung |
| Alter Hit nach beendetem Clear | PASS | Wiederholte Admission bleibt `None` |
| Neue Phrase nach Clear | PASS | Erfolgreiche Detection, Wire-Activation-ID identisch, Score exakt `0.91` |
| In-flight-Inferenz gegen Clear | PASS | Events erzwingen Ueberlappung; Sessionlock frei; beide Threads beendet |
| Exactly-once / Eventidentitaeten | PASS | Wiederangebot erzeugt kein zweites Event; logischer Count und Wirecount jeweils 1 |
| Finish-/Cancel-/Initial-/Followup-Timeout-Rearm | PASS | Bestehende Worker-/Controller-/v2 Regressionen der Pflichtsuite |
| Samplepositionen / Pre-Roll / Nutzsprache | PASS | Bestehende absoluten Worker-/Boundaryregressionen unveraendert bestanden |
| Elf Pflichtmodule | PASS | **356 Tests**, keine Fehler/Skips, **254.887 s**, Exitcode 0 |
| Vollstaendige verfuegbare Fast-Suite | PASS mit bestehenden SKIP | **1982 PASS, 14 SKIP, 1296 Subtests PASS**, **640.23 s**, Exitcode 0 |
| Syntax / Whitespace | PASS | `compileall` fuer beide Produktmodule und Testdatei; `git diff --check` |
| Dokumentation | PASS | 29 relative Links vorhanden; bestehende Guards 35 PASS / 42 Subtests PASS in 0.43 s |
| Erneute PR-CI | Bei Erstellung dieses Nachtrags noch NOT RUN | Aktuelle Ergebnisse werden nach Push am bestehenden PR ausgewiesen; alte gruene Checks gelten nicht fuer den Fix |
| Neue physische Modell-/Hardwareprobe | NOT RUN | Keine Aenderung an Modell-/Audioberechnung, kein neuer Hardwareauftrag |
| Clientqualifikation AP-IV2-020 | BLOCKED | Gesonderte unabhaengige Freigabe weiterhin erforderlich |

Ausgefuehrte Pflicht- und Gesamtsuite:

```powershell
python -m unittest -v tests.unit.test_wake_detection tests.unit.test_wakeword_recording_path tests.unit.test_wake_audio_boundary tests.unit.test_wake_admission tests.unit.test_wakeword_root_findings_c2 tests.unit.test_wakeword_root_findings_c3 tests.unit.test_wakeword_session_e2e tests.unit.test_protocol_v2_e2e tests.unit.test_protocol_v2_races tests.unit.test_protocol_v2_settings tests.unit.test_settings_control_plane
python -m pytest -q -rs tests\unit
```

Die 14 Skipgruende sind gegen den vorherigen Lauf unveraendert: zwoelf
optionale Realmodell-/Golden-/Multiuser-Pruefungen nicht aktiviert, externe
Protokollvergleichsvektoren nicht gesetzt und die optionale Silero-
Abhaengigkeitskombination nicht vollstaendig vorhanden. Keine neuen Skips,
keine deaktivierten Tests und keine abgeschwaechten Assertions.
Rohlogs/XML liegen als `p1-clear-*` nur im externen Sessionartefaktverzeichnis.

## Enger Dateiaudit und Abweichungen

| Geaenderte Datei relativ zum beanstandeten Stand | Notwendigkeit |
| --- | --- |
| `api_fastapi_server/server.py` | Nur Clear-Sessionreset und vorhandenen Detektorreset gemeinsam gegen Wakeadmission schuetzen; bestehender Block sonst nur eingerueckt |
| `api_fastapi_server/wake_admission.py` | Kleiner Contextmanager fuer das bereits vorhandene Coordinator-RLock, ohne neues Lock/Zustandsfeld |
| `tests/unit/test_wakeword_session_e2e.py` | Zwei produktpfadnahe deterministische Interleavingtests samt frischer Phrase und Eventidentitaeten |
| `docs/wake-words.md` | Dauerhafte Dokumentation der Cleargrenze und Lockreihenfolge |
| `docs/.archiv/README.md` | P1-Nachtrag vor Umsetzung registrieren; unabhaengigen Pruefstatus offenhalten |
| `2026-10-19_P1_CLEAR_PLAN.md` | Vorabplanung im vorhandenen Aktionsordner |
| `2026-10-19_P1_CLEAR_REPRODUKTION.md` | Separater unveraenderlicher ROT-Nachweis |
| `2026-10-19_P1_CLEAR_UMSETZUNGSVERGLEICH.md` | Dieser Nachtrag mit geprueftem Commit, Ergebnissen und Scope |

Keine materielle Abweichung vom P1-Plan, daher keine weitere
Abweichungsdatei. Die bereits dokumentierte appbedingte Branchbenennung und
externen Qualifikationsgrenzen bleiben bestehen.

Keine Aenderung an `WakeDetectionEvaluator.new_generation()`, Engine,
Recorder, ActivationController, Audio-Zeitbasis, Pre-Roll, Scoring, Gain,
Cooldown, Settings oder Eventfeldern. Die bisherige Issue-7-Korrektur bleibt
erhalten. Kein neuer PR, Merge, Release oder Deployment.

Restrisiko: Clear wartet wie Admission auf laufende Inferenz/Modellreset;
ein upstream dauerhaft haengender Modellaufruf wird hier nicht mit einer
neuen Timeout-/Recoveryarchitektur umgangen. Tests belegen die erzwungenen
Interleavings, nicht absolute Freiheit von jedem moeglichen Race.
Ein unabhaengiger Reviewer muss diese Lockgrenze und die tatsaechlichen
neuen PR-Checks erneut pruefen. Bis dahin keine Mergefreigabe.
