# AP-SRV-060 – Umsetzungsvergleich (Stand C3)

Soll-/Ist-Prüfung des verbindlichen Auftrags
`runs/01_IMPLEMENTATION/2026-08-27_PROMPT.md` gegen den tatsächlich in diesem
Worktree umgesetzten Stand. Bewertung ausschließlich **VOLLSTÄNDIG**,
**TEILWEISE** oder **NICHT** – nichts teilweise Umgesetztes wird als PASS
dargestellt.

## Fortschreibung nach Root FAIL / C2

Root hat C1 mit den Findings **F1–F10** abgelehnt. Der Vergleich unten war
damit an mehreren Stellen zu positiv; die betroffenen Zeilen sind auf den
C2-Stand korrigiert. Die vollständige Root-Korrektur ist in
`runs/02_ROOT_CORRECTION/2026-08-28_REPORT.md` beschrieben.

| Root-Finding | betroffener Requirementblock | Bewertung in C1 | Bewertung nach C2 |
|---|---|---|---|
| F1 v2-Wire akzeptierte Aliase | §8, §13 | fälschlich VOLLSTÄNDIG | VOLLSTÄNDIG (Wire kanonisch, Config tolerant) |
| F2 `next_activation` ohne Runtimebindung | §12 | fälschlich VOLLSTÄNDIG | VOLLSTÄNDIG (reale Bindung nachgewiesen) |
| F3 „unloadable" nicht validiert | §13 | fälschlich VOLLSTÄNDIG | VOLLSTÄNDIG (Ladbarkeitsprobe vor `hello.accepted`) |
| F4 Detection-Sample als bewiesene Grenze | §18 | fälschlich VOLLSTÄNDIG | **TEILWEISE / EVIDENCE_BLOCKED** |
| F5 Kalibrierwerte als finaler Vertrag | §12, §19 | TEILWEISE (EVIDENCE_PENDING) | **TEILWEISE / EVIDENCE_BLOCKED**, Schlüssel als vorläufig publiziert |
| F6 Rearm als versteckter zweiter Lock | §16, §17 | fälschlich VOLLSTÄNDIG | VOLLSTÄNDIG (getrennte Fenster) |
| F7 Fault nach Activation-Commit | §16 | fälschlich VOLLSTÄNDIG | VOLLSTÄNDIG (explizite Commitgrenze) |
| F8 Revision ohne Event | §11 | fälschlich VOLLSTÄNDIG | VOLLSTÄNDIG (jede sichtbare Änderung meldet) |
| F9 Entry ohne `catalogRevision` | §10 | fälschlich VOLLSTÄNDIG | VOLLSTÄNDIG |
| F10 Refreshantwort mischte Zustände | §11 | fälschlich VOLLSTÄNDIG | VOLLSTÄNDIG (eine atomare Projektion) |

Ergebnis nach C2: **34 VOLLSTÄNDIG, 4 TEILWEISE, 0 NICHT.** Alle vier
Teilbewertungen hängen an genau einer Ursache – fehlende reale positive
Wake-Word-Aufnahmen – und sind als `EVIDENCE_BLOCKED` gekennzeichnet.

## Fortschreibung nach Root FAIL / C3

Root hat C2 mit den Findings **F11–F15** abgelehnt und zusätzlich die
Detection-Semantik verbindlich präzisiert. Der Vergleich oben war damit an
zwei Stellen zu positiv (F4, F6 hatten die falsche Lesart festgeschrieben);
außerdem sind mit C3 neue Requirementblöcke hinzugekommen. Die vollständige
Root-Korrektur ist in `runs/03_ROOT_CORRECTION/2026-08-28_REPORT.md`
beschrieben.

| Root-Finding | betroffener Requirementblock | Bewertung nach C2 | Bewertung nach C3 |
|---|---|---|---|
| F11 ein Wake-Attempt mischte Settingsrevisionen | C3 §13 | fälschlich VOLLSTÄNDIG (F2) | VOLLSTÄNDIG (`WakeAttemptPolicy`, Barriertest) |
| F12 Runtime-/Loadability-Authority | C3 §14 | fälschlich VOLLSTÄNDIG (F3) | VOLLSTÄNDIG (per-Backend-Health, `runtime_unavailable`, Common-Backend-Gate) |
| F13 genau ein logisches `wakeword.detected` | C3 §15 | fälschlich VOLLSTÄNDIG (F7) | VOLLSTÄNDIG (`LogicalWakeEventLedger`, Faulttests A–D) |
| F14 echte state-changing Refresh-Races | C3 §16 | fälschlich VOLLSTÄNDIG (F10) | VOLLSTÄNDIG (A→B, 20/20, ohne Sleeps) |
| F15 Contract-/Dokumentationskorrektur | C3 §17 | fälschlich VOLLSTÄNDIG | VOLLSTÄNDIG (Detection-Semantik korrigiert, zurückgezogene Aussagen markiert) |

Neu bewertete C3-Requirementblöcke:

| C3-Block | Stand | Nachweis |
|---|---|---|
| §5 Wake-Hit-Modell (Schwelle, Mindestframezahl, Qualifikation, Finalisierung) | VOLLSTÄNDIG | `WakeHitTrackerTests` (11 Matrixfälle + Prompt-Beispielfolge) |
| §6 Multi-Wake-Word-Arbitration, First-finalized-wins, Tie-Breaker | VOLLSTÄNDIG | `test_7…`, `test_8…`, `test_9…`, `test_10…` |
| §7 operationaler Nullpunkt / Pre-Roll | VOLLSTÄNDIG | `OperationalZeroPointTests`, Recordingpfad-Tests |
| §8 Prediction-Frames statt Recorderchunks | VOLLSTÄNDIG | `PredictionFrameTests` (20/40 ms, gecachter Score) |
| §9 Settings-Plane vollständig verdrahtet | VOLLSTÄNDIG | `C3SettingsPlaneTests`, `test_schema_is_deterministic_and_complete` |
| §10 Dual Backend, ein gemeinsames Backend je Engine | VOLLSTÄNDIG | `F12BackendPolicyTests`, `F12CatalogAdmissionTests` |
| §11 Catalog Loadability bei Load und Refresh | VOLLSTÄNDIG | `C3CatalogLoadabilityTests` |
| §12 dünner OpenWakeWord-Adapter, kein Fork | VOLLSTÄNDIG | `openwakeword_engine.py`, `WakeDetectorVadTests` |
| §19 VAD-Architekturgate | VOLLSTÄNDIG | `WakeDetectorVadTests`, Lifecycle-Tests |
| §20 Gain-Gate, Originalaudio unverändert | VOLLSTÄNDIG | `DetectorGainTests` (bytegenau, sättigend) |
| §18 empirische Kalibrierung | **TEILWEISE** | `EVIDENCE_BLOCKED` (WW-18/WW-19) |
| §10 `.tflite`-Artefakte im ausgelieferten Bundle | **TEILWEISE** | Kette implementiert und getestet; Artefakte sind ein Deploymentschritt, keine Runtime-Downloads |

Damit korrigiert C3 zwei frühere Bewertungen ausdrücklich nach unten und
anschließend wieder nach oben:

* **F4/§18 Audiogrenze:** C2 bewertete sie als „TEILWEISE / EVIDENCE_BLOCKED",
  weil die Wake-Endgrenze als unbekannte Größe galt. Root hat den operationalen
  Nullpunkt seither als Produktentscheidung definiert; die **Grenze selbst** ist
  damit **VOLLSTÄNDIG**, `EVIDENCE_BLOCKED` bleibt nur die Kalibrierung.
* **F6/§16 Entprellung:** die C2-Lösung (implizites Entprellfenster) beruhte auf
  der falschen Lesart „ein Scoreframe ist ein Wake Word". Sie ist
  zurückgezogen; die Gruppierung leistet jetzt der `WakeHitTracker` ohne Timer.

| # | Requirement | Stand | Code-Nachweis | Test-/Evidence-Nachweis | Abweichung / EVIDENCE_PENDING |
|---|---|---|---|---|---|
| §2 | Isolierter C1-Worktree auf kanonischer AP-SRV-050-Basis | VOLLSTÄNDIG | `work/AP-SRV-060/C1` in `workspaces/ap-srv-060`, angelegt aus `c901cda…` | Report §Provenienz; Vorbedingung HEAD/Tree/clean verifiziert | – |
| §3 | Git-/Sicherheitsregeln, kein Push, kein Clientcode | VOLLSTÄNDIG | keine Änderung außerhalb des Server-Worktrees | `git status --short` im Report | – |
| §4 | Pflichtlektüre Server + Koordinationsworkspace | VOLLSTÄNDIG | – | Report §Grundlagen; WW-01…WW-19, WIRE-02/04/07, SET-13b, FIND-011 ausgewertet | – |
| §5 | Gemini-Prep nur selektiv als Donor | VOLLSTÄNDIG | keine Datei übernommen | Donor-Tabelle im Report | – |
| §6 | Build-Assets ins Projekt, Packaging Windows + Ubuntu, keine Runtime-Downloads | VOLLSTÄNDIG | `VoiceSTT/assets/wakeword_models/`, `setup.py::package_data`, `MANIFEST.in`, `wakeword_catalog.default_asset_root()` über `importlib.resources` | Evidence §3 (Inventar, 29 Dateien, 15.910.749 B); `test_wakeword_catalog.py::BundledAssetTests` | tflite bewusst nicht gebündelt (dokumentiert) |
| §7 | `models.json` ist kanonische Catalog Authority, Auto-Discovery nur Diagnose | VOLLSTÄNDIG | `wakeword_catalog.load_snapshot`, `diagnostics["unmanagedArtifacts"]` | `test_an_undeclared_file_is_diagnostics_only`, `test_public_projection_carries_no_paths_or_sources` | – |
| §7 | Manifest leitet `id`/`displayName`/`aliases`/`artifactVersion`/Artifacts/Pipeline ab | VOLLSTÄNDIG | `_parse_entries`, `_parse_pipeline` | `test_wakeword_catalog.py` (Schema-, Kollisions- und Availabilityfälle) | – |
| §7 | Öffentliche Payload ohne Pfade/`source`/`paths`/Secrets | VOLLSTÄNDIG | `WakeWordEntry.public_dict` | `test_the_payload_never_exposes_internal_paths` | – |
| §8 | Genau ein toleranter Resolver, nur explizite Aliase, kollisionsfrei | VOLLSTÄNDIG | `normalize_wake_word_token`, `WakeWordCatalogSnapshot.resolve`, `claim()` | `NormalisationTests`, 4 Kollisionsfälle, `test_explicit_alias_resolves_but_an_unlisted_short_form_does_not` | **C2/F1:** Toleranz gilt nur noch für menschliche Konfiguration; der v2-Wire nimmt ausschließlich kanonische IDs (`F1WireCanonicalityTests`) |
| §9 | Genau eine threadsichere serverweite Catalog Authority, `catalogRevision` getrennt | VOLLSTÄNDIG | `VoiceSTTService.wakeword_catalog`, `WakeWordCatalogAuthority`, `WakeWordPort` als Adapter | `test_the_catalog_revision_is_separate_from_the_settings_revision`; `ports.py` ohne Konstante | – |
| §10 | `GET /api/v2/wake-words` (SET-13b) inkl. Global Disable in Availability | VOLLSTÄNDIG | `server.py::wake_words_v2`, `public_payload` | `test_wakeword_catalog_api.py::CatalogHttpContractTests`, `GlobalDisableProjectionTests`, `F9EntryRevisionTests` | **C2/F9:** jeder Eintrag trägt jetzt `catalogRevision` |
| §11 | `POST /api/v2/wake-words/refresh`, dieselbe Auth, atomar, last-known-good, Revision, Event | VOLLSTÄNDIG | `refresh_wake_words_v2`, `VoiceSTTService.refresh_wake_word_catalog`, `_commit_locked` | `CatalogRefreshTests` (3), `F8CatalogEventTests`, `F10AtomicRefreshTests` | **C2/F8:** jede sichtbare Änderung meldet; **C2/F10:** Refresh und Global Disable sind eine atomare Operation, die Antwort stammt aus dem committeten Snapshot |
| §11 | Refresh verändert keine bestehende Session | VOLLSTÄNDIG | Selection ist pro Session gelatcht (`session_config.wake_word_selection`) | `test_a_refresh_does_not_disturb_an_already_admitted_session` | – |
| §12 | AP-SRV-050-Settings verwenden, keine zweite Registry/Revision/Persistenz | VOLLSTÄNDIG | zwei Keys in `settings_control.builtin_definitions()` | `test_schema_is_deterministic_and_complete` | – |
| §12 | `wakeWord.cooldownMs` / `wakeWord.preRollMs` mit Serverdefault, `next_activation` **real wirksam** | VOLLSTÄNDIG | `WAKE_WORD_COOLDOWN_MS`, `WAKE_WORD_PRE_ROLL_MS`, `WakeRuntimePolicy`, `_wake_runtime_policy` | `F2RuntimeBindingTests`, `F2SessionBindingTests` (reale Evaluator-/Boundarywerte) | **C2/F2:** in C1 wirkte ein Patch nur im Schema, nicht im Detector |
| §12 | Defaults/Bereiche nicht erfinden, `0 ms` Pre-Roll zulässig | **TEILWEISE** | Bereiche als vorläufige Eingabegrenzen, Defaults `0`, `constraints.calibration = "pending"` | `F5ProvisionalCalibrationTests`, C1-Evidence §4 | **EVIDENCE_BLOCKED (WW-18/WW-19).** **C2/F5:** ein Empfangsfenster ist kein kalibrierter Betriebsbereich; beide Schlüssel werden deshalb ausdrücklich als vorläufig veröffentlicht statt als finaler Vertrag |
| §13 | Atomare Sessionadmission, alle Problem-IDs maschinenlesbar, kein Partial/Fallback | VOLLSTÄNDIG | `admit_selection` (kanonisch + Ladbarkeitsprobe), `handshake.admit_requested_session`, `resolve_session_wake_word_config`-Kurzschluss | `test_one_unknown_id_rejects_the_whole_selection`, `F1WireCanonicalityTests`, `F3UnloadableAdmissionTests`, `F3UnloadableSessionTests` | **C2/F1+F3:** zusätzlich `not_canonical` und `artifact_unloadable`; „ladbar" ist jetzt eine reale Probe, keine Dateiexistenzprüfung |
| §13 | Vor Admission kein Audio/Trigger/Wake | VOLLSTÄNDIG | unveränderte AP-SRV-040-Handshakesequenz; Refusal vor Sessionaufbau | `test_protocol_v2_e2e.py` (Bestand) + `AdmissionTests` | – |
| §14 | Selected-only Modellinitialisierung, Tests prüfen Loaderargumente | VOLLSTÄNDIG | `wakeword.setup_wakeword_detection(..., wake_word_selection=…)` | `test_wakeword_selected_only.py::SelectedOnlyLoaderTests` (1/3/Alias/Pipeline) | – |
| §14 | Ownership der gemeinsamen Pipelineassets dokumentiert | VOLLSTÄNDIG | Docstring `WakeWordPipeline` | `docs/wake-words.md`, `docs/einheitliche-triggerarchitektur.md` §14.5 | – |
| §15 | `RawWakeCandidate` vs. `AcceptedWakeDetection`, Tie-Regel, Rohscores nur Diagnose | VOLLSTÄNDIG | `VoiceSTT/core/wake_detection.py` | `SelectCandidateTests`, `test_raw_collection_applies_no_threshold`, `test_diagnostics_expose_raw_scores_without_publishing_them` | – |
| §16 | Latch außerhalb `ActivationController`, Pfad über Wake Admission Coordinator | VOLLSTÄNDIG | `api_fastapi_server/wake_admission.py`, `_activate_from_wake_candidate` | `test_wake_admission.py` (13 Fälle) | `activation.py` unverändert quellenneutral |
| §16 | Genau ein `wakeword.detected` mit `activationId`/`wakeWordId`/`score`/`primarySource` | VOLLSTÄNDIG | `_publish_accepted_wake_detection`, `events._build_wakeword_detected`, `WakeActivationOutcome` | `test_an_accepted_hit_publishes_exactly_one_wakeword_detected`, `F7FaultBoundaryTests`, `F7SessionFaultTests` | **C2/F7:** explizite Commitgrenze; ein Fehler nach dem Commit wird nie mehr als Refusal behandelt |
| §16 | Ablehnung: kein Event, kein Latch, keine zweite Activation, kein Merge | VOLLSTÄNDIG | `_on_wakeword_detected` v2-Zweig; alter unbedingter Publish entfernt | `RefusedAdmissionTests`, `test_a_wake_word_during_an_open_activation_has_no_effect` | – |
| §16 | Latch bis sicherer Eingabeschluss | VOLLSTÄNDIG | `_release_wake_latch` an der `activation_closed`-Seam | `test_the_latch_survives_until_the_input_close_of_its_activation`, `test_the_latch_is_released_at_the_safe_input_close`, `test_a_latched_detector_is_not_released_by_the_legacy_timeout` | – |
| §17 | FIND-011 behoben, Cooldown/Rearm ist Detektorhygiene | VOLLSTÄNDIG | Guard in `recording.py`, getrennte Entprell-/Cooldownfenster im `WakeDetectionEvaluator` | `test_the_detector_is_not_run_again_while_latched` (40 Chunks → 1 predict), `F6RearmTests` | **C2/F6:** die implizite Entprellung endet am sicheren Eingabeschluss und bildet keine zweite Vordergrundsperre mehr |
| §17 | Keine erfundene Mehrfach-Chunk-Regel | VOLLSTÄNDIG | keine solche Regel implementiert | Evidence §5: 0 Rohkandidaten über 63.99 s Negativmaterial | Bedarf einer Positivmessung bleibt EVIDENCE_PENDING |
| §18 | Getrennte Audiogrenzen, keine pauschale Fixed-Duration als Endzustand | VOLLSTÄNDIG | `wake_audio_boundary.py`, Boundary-Zweig in `recording.py` | `test_wake_audio_boundary.py`, `test_an_accepted_hit_stores_the_boundary_for_the_audio_release` | Legacy-Fixed-Duration nur noch im v1-Pfad (AP-SRV-070) |
| §18 | Wake-Endgrenze belastbar bestimmt | **TEILWEISE** | `estimated_wake_end_sample`, `boundary_basis`, `boundary_measured` | `F4BoundaryHonestyTests` | **EVIDENCE_BLOCKED (WW-19).** **C2/F4:** der Detection-Samplepunkt ist eine konservative Schätzung, keine gemessene akustische Grenze; das Produkt weist das selbst aus |
| §18 | Wake Word nicht im Nutztranskript, erstes Nutzerwort erhalten, `0 ms` korrekt | VOLLSTÄNDIG | `resolve_wake_audio_boundary`, `trim_frames_to_boundary` | `test_the_wake_word_leaves_and_the_first_user_word_survives` | – |
| §19 | Reproduzierbares Score-/Audio-Harness mit realem Backend | VOLLSTÄNDIG | `tools/wakeword_calibration.py` (`artifacts`/`resources`/`scores`) | Evidence §4/§5 mit realen Messwerten | – |
| §19 | Positive und negative Audiosamples, danach Defaults entscheiden | **TEILWEISE** | Harness unterstützt beides | C1-Evidence §5 (Negativmaterial), C2-Evidence §8 (vollständige Suche) | **EVIDENCE_BLOCKED:** im lokalen Umfeld existiert nachweislich kein positives Wake-Word-Material; nichts simuliert, nichts erfunden |
| §20 | Resource Evidence 1 / 3 / Maximum mit realen Modellen | VOLLSTÄNDIG | `tools/wakeword_calibration.py resources` | Evidence §6 (Init, RSS, Peak, Latenz, OS/Python/oww/ort) | – |
| §21 | Deterministische Concurrency-/Fehlerfälle ohne Sleeps | VOLLSTÄNDIG | – | Evidence §8 (Tabelle aller geforderten Fälle) | – |
| §22 | AP-Akte vor Produktcode, kein selbst gesetztes PASS | VOLLSTÄNDIG | `docs/.archiv/…/AP-SRV-060/` | `ABNAHME.md` ausdrücklich `PENDING ROOT REVIEW` | – |
| §23 | Prompt byteidentisch archiviert, Hash/Bytes dokumentiert | VOLLSTÄNDIG | `runs/01_IMPLEMENTATION/2026-08-27_PROMPT.md` | Evidence §2 (SHA256 identisch, 26172 Bytes) | zusätzlich `-text` in `.gitattributes` |
| §24 | Kompakter AP-Plan mit allen geforderten Abschnitten | VOLLSTÄNDIG | `2026-08-27_PLAN.md` | – | – |
| §25 | Umsetzungsvergleich | VOLLSTÄNDIG | dieses Dokument | – | – |
| §26 | Produktdokumentation als hartes Gate, Code↔Doku gegengeprüft | VOLLSTÄNDIG | 8 Dokumente aktualisiert | Report §Produktdokumentation (Gegenprüfungstabelle) | `docs/.archiv/README.md` bleibt `In Umsetzung` |
| §27 | Tracking-Handoff vorbereitet, zentrale Dateien nicht selbst geändert | VOLLSTÄNDIG | `2026-08-27_TRACKING_HANDOFF.md` | keine Änderung im Clientworkspace | – |
| §28 | Server-Archivregister spiegelt AP-Aktenstand, Gesamtaktion `In Umsetzung` | VOLLSTÄNDIG | `docs/.archiv/README.md` | – | – |
| §29 | Testumfang 1–14 inkl. Vollsuite, kein neues venv | VOLLSTÄNDIG | 8 neue Testdateien | Evidence §7 (exakte Befehle und Ergebnisse) | `openwakeword` in die *bestehende* Umgebung nachinstalliert (deklarierte Projektabhängigkeit), kein venv |
| §30 | Diff-/Worktree-Check, Assetinventar | VOLLSTÄNDIG | – | Evidence §3/§9, Report | keine unerklärten untracked Artefakte |
| §31 | Genau ein lokaler C1-Run-Commit mit Parent `c901cda…` | VOLLSTÄNDIG | – | Report §Provenienz | kein Push, kein Merge, kein Rebase |
| §32 | Abschlussreport mit allen Pflichtabschnitten | VOLLSTÄNDIG | `runs/01_IMPLEMENTATION/2026-08-27_REPORT.md` | – | – |

## Traceability der IDs

| ID | Stand | Nachweis |
|---|---|---|
| WW-01 Build-Katalog, atomare Auswahl, nur Auswahl geladen | VOLLSTÄNDIG | `wakeword_catalog.py`, `test_wakeword_selected_only.py` |
| WW-02 kanonische IDs, tolerante explizite Aliase | VOLLSTÄNDIG | `normalize_wake_word_token`, `NormalisationTests` |
| WW-03 mehrere aktive Wake Words, gemeinsame Sensitivity | VOLLSTÄNDIG | `WakeDetectionEvaluator(threshold=wakeWord.sensitivity)` |
| WW-04 erster akzeptierter Treffer latched, höchstens ein Ereignis | VOLLSTÄNDIG (Zusatzregel bleibt messdatenabhängig offen) | `test_wake_admission.py`, `F6RearmTests`, `F7FaultBoundaryTests` |
| WW-05 Wake Word während Activation ohne Wirkung | VOLLSTÄNDIG | `test_a_wake_word_during_an_open_activation_has_no_effect` |
| WW-08 Wake Word nicht transkribieren, Folgesprache erhalten | VOLLSTÄNDIG | `test_the_wake_word_leaves_and_the_first_user_word_survives` |
| WW-09 versionierter abfragbarer Katalog | VOLLSTÄNDIG | `GET /api/v2/wake-words` |
| WW-10 Aliasnormalisierung und Kollisionsregel | VOLLSTÄNDIG | 4 Kollisionstests |
| WW-11 problematische ID lehnt gesamte Auswahl ab | VOLLSTÄNDIG | `SelectionAdmissionTests` |
| WW-12 nur gewählte Modelle initialisiert | VOLLSTÄNDIG | Loaderargument-Tests |
| WW-13 `wakeword.detected` mit ID/Score/`activationId` | VOLLSTÄNDIG | `test_an_accepted_hit_publishes_exactly_one_wakeword_detected` |
| WW-14 gemeinsame Sensitivity, Zusatzregel nur nach Messdaten | VOLLSTÄNDIG (keine Zusatzregel) | Evidence §5 |
| WW-15 Cooldown/Pre-Roll serverautoritativ, `0 ms` zulässig | VOLLSTÄNDIG | Registry + `test_wake_audio_boundary.py` |
| WW-16 Latch bis Eingabeschluss, kein Mehrfachereignis | VOLLSTÄNDIG | Latch-Tests |
| WW-17 leere Auswahl nur bei `wakeWord=false` | VOLLSTÄNDIG | `test_an_empty_selection_with_wake_enabled_is_rejected` |
| WW-18 Cooldown-Default aus Score-Evidence | **EVIDENCE_BLOCKED** | Bereich nur vorläufige Eingabegrenze, Default `0`, Schema als `calibration: pending` publiziert; Positivmaterial existiert nicht |
| WW-19 Pre-Roll-Default aus Audio-Grenztest | **EVIDENCE_BLOCKED** | zusätzlich: die Wake-Endgrenze selbst ist eine Schätzung (`boundaryMeasured = false`); Positivmaterial existiert nicht |
| WIRE-02 atomare Validierung vor Audio-/Triggerfreigabe | VOLLSTÄNDIG | `admit_requested_session` |
| WIRE-04 `session.rejected` mit feldbezogenen Fehlern | VOLLSTÄNDIG | Reject-Tests |
| WIRE-07 Snapshot enthält Wake-Capabilities | VOLLSTÄNDIG | `test_a_bundled_wake_word_is_admitted_and_mirrored_in_the_snapshot` |
| SET-13b `GET /api/v2/wake-words` | VOLLSTÄNDIG | HTTP-Contract-Tests |
| FIND-011 Mehrfachsignalpfad | VOLLSTÄNDIG | `test_wakeword_recording_path.py` |

## Zusammenfassung (Stand C3)

Von den geprüften Requirementblöcken ist keiner **NICHT** umgesetzt.
**TEILWEISE** bleiben genau zwei Sachverhalte:

1. die **empirische Kalibrierung** (`WW-18`, `WW-19`) – abhängig von realer
   positiver Wake-Word-Sprache, im Produkt über
   `constraints.calibration = "pending"` gekennzeichnet;
2. die **`.tflite`-Artefakte** des ausgelieferten Bundles – die Dual-Backend-
   Kette ist implementiert und gegen echte Zweiformat-Bundles getestet, das
   Nachliefern der Artefakte ist ein Deployment-/Assetschritt ohne
   Runtime-Downloads.

Ausdrücklich **nicht** mehr teilweise ist die algorithmische Detection- und
Boundary-Semantik: Trefferregion, Qualifikation, Finalisierung, Exactly-once
Event, operationaler Nullpunkt und Pre-Roll-Mathematik sind vollständig
implementiert und getestet. Die Audiogrenze weist sich nicht mehr als Schätzung
aus, sondern als definierte Produktentscheidung (`boundaryBasis =
operational_zero_point`, `boundaryDefined = true`).

Die fünfzehn Root-Findings F1–F15 sind geschlossen und jeweils durch einen
RED-first nachgewiesenen Regressiontest abgesichert.
