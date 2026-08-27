# AP-SRV-060 – Umsetzungsvergleich (Stand C1)

Soll-/Ist-Prüfung des verbindlichen Auftrags
`runs/01_IMPLEMENTATION/2026-08-27_PROMPT.md` gegen den tatsächlich in diesem
Worktree umgesetzten Stand. Bewertung ausschließlich **VOLLSTÄNDIG**,
**TEILWEISE** oder **NICHT** – nichts teilweise Umgesetztes wird als PASS
dargestellt.

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
| §8 | Genau ein toleranter Resolver, nur explizite Aliase, kollisionsfrei | VOLLSTÄNDIG | `normalize_wake_word_token`, `WakeWordCatalogSnapshot.resolve`, `claim()` | `NormalisationTests`, 4 Kollisionsfälle, `test_explicit_alias_resolves_but_an_unlisted_short_form_does_not` | – |
| §9 | Genau eine threadsichere serverweite Catalog Authority, `catalogRevision` getrennt | VOLLSTÄNDIG | `VoiceSTTService.wakeword_catalog`, `WakeWordCatalogAuthority`, `WakeWordPort` als Adapter | `test_the_catalog_revision_is_separate_from_the_settings_revision`; `ports.py` ohne Konstante | – |
| §10 | `GET /api/v2/wake-words` (SET-13b) inkl. Global Disable in Availability | VOLLSTÄNDIG | `server.py::wake_words_v2`, `public_payload` | `test_wakeword_catalog_api.py::CatalogHttpContractTests`, `GlobalDisableProjectionTests` | – |
| §11 | `POST /api/v2/wake-words/refresh`, dieselbe Auth, atomar, last-known-good, Revision, Event | VOLLSTÄNDIG | `refresh_wake_words_v2`, `VoiceSTTService.refresh_wake_word_catalog`, `_commit_locked` | `CatalogRefreshTests` (3), `test_a_broken_manifest_keeps_the_last_known_good_catalog`, `test_an_availability_change_reaches_live_sessions_as_an_event` | – |
| §11 | Refresh verändert keine bestehende Session | VOLLSTÄNDIG | Selection ist pro Session gelatcht (`session_config.wake_word_selection`) | `test_a_refresh_does_not_disturb_an_already_admitted_session` | – |
| §12 | AP-SRV-050-Settings verwenden, keine zweite Registry/Revision/Persistenz | VOLLSTÄNDIG | zwei Keys in `settings_control.builtin_definitions()` | `test_schema_is_deterministic_and_complete` | – |
| §12 | `wakeWord.cooldownMs` / `wakeWord.preRollMs` mit Serverdefault, `next_activation` | VOLLSTÄNDIG | `WAKE_WORD_COOLDOWN_MS`, `WAKE_WORD_PRE_ROLL_MS`, `has_server_default=True` | Schema-Test, `_wake_word_runtime_values` | – |
| §12 | Defaults/Bereiche nicht erfinden, `0 ms` Pre-Roll zulässig | **TEILWEISE** | Bereiche aus gemessenen Empfangsfenstern (1960/3400 ms), Defaults `0` | Evidence §4 (`artifacts`-Messung) | **EVIDENCE_PENDING (WW-18/WW-19):** reale positive Wake-Word-Aufnahmen fehlen im Repository; ein davon abhängiger anderer Default wurde bewusst nicht erfunden |
| §13 | Atomare Sessionadmission, alle Problem-IDs maschinenlesbar, kein Partial/Fallback | VOLLSTÄNDIG | `resolve_selection`, `handshake.admit_requested_session`, `resolve_session_wake_word_config`-Kurzschluss | `test_one_unknown_id_rejects_the_whole_selection`, `test_every_problematic_id_is_named_machine_readably`, `SelectionAdmissionTests` | – |
| §13 | Vor Admission kein Audio/Trigger/Wake | VOLLSTÄNDIG | unveränderte AP-SRV-040-Handshakesequenz; Refusal vor Sessionaufbau | `test_protocol_v2_e2e.py` (Bestand) + `AdmissionTests` | – |
| §14 | Selected-only Modellinitialisierung, Tests prüfen Loaderargumente | VOLLSTÄNDIG | `wakeword.setup_wakeword_detection(..., wake_word_selection=…)` | `test_wakeword_selected_only.py::SelectedOnlyLoaderTests` (1/3/Alias/Pipeline) | – |
| §14 | Ownership der gemeinsamen Pipelineassets dokumentiert | VOLLSTÄNDIG | Docstring `WakeWordPipeline` | `docs/wake-words.md`, `docs/einheitliche-triggerarchitektur.md` §14.5 | – |
| §15 | `RawWakeCandidate` vs. `AcceptedWakeDetection`, Tie-Regel, Rohscores nur Diagnose | VOLLSTÄNDIG | `VoiceSTT/core/wake_detection.py` | `SelectCandidateTests`, `test_raw_collection_applies_no_threshold`, `test_diagnostics_expose_raw_scores_without_publishing_them` | – |
| §16 | Latch außerhalb `ActivationController`, Pfad über Wake Admission Coordinator | VOLLSTÄNDIG | `api_fastapi_server/wake_admission.py`, `_activate_from_wake_candidate` | `test_wake_admission.py` (13 Fälle) | `activation.py` unverändert quellenneutral |
| §16 | Genau ein `wakeword.detected` mit `activationId`/`wakeWordId`/`score`/`primarySource` | VOLLSTÄNDIG | `_publish_accepted_wake_detection`, `events._build_wakeword_detected` | `test_an_accepted_hit_publishes_exactly_one_wakeword_detected` | – |
| §16 | Ablehnung: kein Event, kein Latch, keine zweite Activation, kein Merge | VOLLSTÄNDIG | `_on_wakeword_detected` v2-Zweig; alter unbedingter Publish entfernt | `RefusedAdmissionTests`, `test_a_wake_word_during_an_open_activation_has_no_effect` | – |
| §16 | Latch bis sicherer Eingabeschluss | VOLLSTÄNDIG | `_release_wake_latch` an der `activation_closed`-Seam | `test_the_latch_survives_until_the_input_close_of_its_activation`, `test_the_latch_is_released_at_the_safe_input_close`, `test_a_latched_detector_is_not_released_by_the_legacy_timeout` | – |
| §17 | FIND-011 behoben, Cooldown/Rearm ist Detektorhygiene | VOLLSTÄNDIG | Guard in `recording.py`, `WakeDetectionEvaluator` | `test_wakeword_recording_path.py::test_the_detector_is_not_run_again_while_latched` (40 Chunks → 1 predict) | – |
| §17 | Keine erfundene Mehrfach-Chunk-Regel | VOLLSTÄNDIG | keine solche Regel implementiert | Evidence §5: 0 Rohkandidaten über 63.99 s Negativmaterial | Bedarf einer Positivmessung bleibt EVIDENCE_PENDING |
| §18 | Getrennte Audiogrenzen, keine pauschale Fixed-Duration als Endzustand | VOLLSTÄNDIG | `wake_audio_boundary.py`, Boundary-Zweig in `recording.py` | `test_wake_audio_boundary.py`, `test_an_accepted_hit_stores_the_boundary_for_the_audio_release` | Legacy-Fixed-Duration nur noch im v1-Pfad (AP-SRV-070) |
| §18 | Wake Word nicht im Nutztranskript, erstes Nutzerwort erhalten, `0 ms` korrekt | VOLLSTÄNDIG | `resolve_wake_audio_boundary`, `trim_frames_to_boundary` | `test_the_wake_word_leaves_and_the_first_user_word_survives` | – |
| §19 | Reproduzierbares Score-/Audio-Harness mit realem Backend | VOLLSTÄNDIG | `tools/wakeword_calibration.py` (`artifacts`/`resources`/`scores`) | Evidence §4/§5 mit realen Messwerten | – |
| §19 | Positive und negative Audiosamples, danach Defaults entscheiden | **TEILWEISE** | Harness unterstützt beides | Evidence §5: nur Negativmaterial vorhanden | **EVIDENCE_PENDING:** positive Wake-Word-Aufnahmen fehlen; nicht simuliert |
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
| WW-04 erster akzeptierter Treffer latched, höchstens ein Ereignis | VOLLSTÄNDIG (Zusatzregel: nicht nötig laut Negativmessung) | `test_wake_admission.py`, Evidence §5 |
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
| WW-18 Cooldown-Default aus Score-Evidence | **TEILWEISE / EVIDENCE_PENDING** | Bereich gemessen, Default `0`; Positivmaterial fehlt |
| WW-19 Pre-Roll-Default aus Audio-Grenztest | **TEILWEISE / EVIDENCE_PENDING** | Bereich gemessen, Default `0`; Positivmaterial fehlt |
| WIRE-02 atomare Validierung vor Audio-/Triggerfreigabe | VOLLSTÄNDIG | `admit_requested_session` |
| WIRE-04 `session.rejected` mit feldbezogenen Fehlern | VOLLSTÄNDIG | Reject-Tests |
| WIRE-07 Snapshot enthält Wake-Capabilities | VOLLSTÄNDIG | `test_a_bundled_wake_word_is_admitted_and_mirrored_in_the_snapshot` |
| SET-13b `GET /api/v2/wake-words` | VOLLSTÄNDIG | HTTP-Contract-Tests |
| FIND-011 Mehrfachsignalpfad | VOLLSTÄNDIG | `test_wakeword_recording_path.py` |

## Zusammenfassung

Von 38 geprüften Requirementblöcken sind 35 **VOLLSTÄNDIG** und 3
**TEILWEISE**. Alle drei Teilbewertungen betreffen denselben, im Auftrag
ausdrücklich vorgesehenen Fall: die von realer positiver Wake-Word-Sprache
abhängigen Kalibrierentscheidungen (`WW-18`, `WW-19`, Bedarf einer
Mehrfach-Chunk-Regel). Die Bereiche sind gemessen, die Defaults sind
konservativ und begründet, und der offene Anteil ist als
`EVIDENCE_PENDING` gekennzeichnet statt simuliert zu werden. Kein Requirement
ist **NICHT** umgesetzt.
