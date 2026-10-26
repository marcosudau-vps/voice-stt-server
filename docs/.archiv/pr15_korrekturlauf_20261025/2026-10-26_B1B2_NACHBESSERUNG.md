# PR #15 – B1/B2-Nachbesserung nach unabhängiger Endabnahme (26.10.2026)

Datierte Ergänzung zur Korrekturakte `01`–`08` (25.10.2026) sowie zu
[Plan](2026-10-26_PLAN_ABSCHLUSSKORREKTUR.md),
[Umsetzungsvergleich](2026-10-26_UMSETZUNGSVERGLEICH.md),
[Abweichungen](2026-10-26_ABWEICHUNGEN.md) und
[Abschlussnachtrag](2026-10-26_ABSCHLUSSNACHTRAG.md).
Ältere Dateien bleiben unverändert (kein Umschreiben von Historie).
Grundlage: [Unabhängige Endabnahme, HEAD `9ea176ce`](https://github.com/marcosudau-vps/voice-stt-server/pull/15#issuecomment-6411079095)
mit den zwei offenen Befunden **B1** (Admission-TOCTOU) und **B2** (gemischte
Lanes / unnötiger Native-Unload). Kein Merge, Draft unverändert, kein
Rebase/Force-Push, keine Pro-A→Pro-B-Absturzexperimente.

## B1 – Race-Condition beim Scheduler-Submit (hoch)

Befund: `_submit_scheduler_job` prüfte `_kroko_pro_revocation()` vor
`ensure_models_loaded()` und außerhalb des Scheduler-Locks; erst später kam
`scheduler.submit(job)` im Lock. Eine bestätigte Force-Community-Änderung
konnte genau in diese Lücke fallen (Check → Patch bestätigt → Submit an den
alten Pro-Scheduler). Ein bloßer zweiter unsynchroner Check schließt die
Lücke nicht.

Fix (`api_fastapi_server/server.py`, kein Wire-/Architekturwechsel):

- Neue monotone `_kroko_admission_generation`, synchron unter
  `_kroko_policy_lock` bei jedem Lizenz-Policy-Bind gebumpt (Force-, Key- und
  Grant-Invalidierungen).
- `_submit_scheduler_job` fasst die Eintrittsprüfung (Revision + Revocation)
  und – nach dem potenziell langen `ensure_models_loaded()` außerhalb jeder
  Sperre – die autoritative Prüfung mit dem tatsächlichen Enqueue in **einen
  kurzen gemeinsamen kritischen Abschnitt** (`_kroko_policy_lock` außen,
  `_scheduler_lock` innen). Eine bestätigte Force-Änderung liegt damit
  entweder strikt vor diesem Abschnitt (wird hier abgewiesen, Revision
  bewegt) oder strikt danach (Auftrag war vor der Bestätigung eingereiht).
- Der Force-PATCH-Handler (`PATCH /api/v2/settings/server`) hält denselben
  Policy-Lock über Commit + `apply_kroko_force_change()`, sodass Commit und
  Grant-Invalidierung gegenüber Submit atomar sind. Reconcile/Netz bleiben im
  Hintergrund (kein Event-Loop-Block).
- Überlast-Meldungen laufen außerhalb des kritischen Abschnitts.

Test (`tests/unit/test_kroko_pr15_b1b2_regression.py`):
`test_b1_force_patch_linearised_with_concurrent_submit` verschachtelt die
Operationen deterministisch per Barrieren (Submit in `ensure_models_loaded`
angehalten → Force-Patch synchron bestätigt bei blockiertem Reconcile →
Submit fortgesetzt): nach der Bestätigung wird abgewiesen
(`Force Community`), kein neuer Job im alten Pro-Worker. Auf dem alten Stand
reproduzierbar offen (B2-Teil unten) bzw. per Codepfad begründet; mit Fix grün.

## B2 – Kroko-Wiederverwendung bei gemischten Engines (mittel–hoch)

Befund: `_kroko_probe_reuses_live_instance()` bildete `paths` aus **allen**
`_resolved_stt_models`-Einträgen ohne Enginefilter und verglich die Menge mit
dem Kandidatenpfad. Bei legitimem Final=Faster-Whisper + Realtime=Kroko (oder
umgekehrt) schlug die Wiederverwendung fälschlich fehl; die Preflight sah die
belegte native Instanz (`CONCURRENT_IDENTITY`), der Refresh entlud unnötig
bzw. meldete bei aktiver Arbeit deferred/failed – obwohl keine zweite
Kroko-Instanz vorlag.

Fix (`api_fastapi_server/server.py`): Der Check betrachtet ausschließlich
tatsächlich aktive **Kroko**-Lanes und vergleicht die native
**Kroko-Modellidentität** (`identity_for_path(...).ident`, Fallback
normierter Pfad). Lane-Reihenfolge und fremde Engines sind damit irrelevant;
unveränderter gemischter Refresh lädt nicht neu.

Tests (selbe Datei, parametrisiert über beide Lane-Reihenfolgen):

- `test_b2_mixed_refresh_reuses_live_kroko_without_reload`: unveränderter
  Refresh ohne aktive Session – keine Unload/Load-Events, derselbe Scheduler,
  keine Probe-Konflikte, genau eine native Instanz.
- `test_b2_mixed_refresh_with_active_session_stays_put`: derselbe Refresh mit
  simulierter aktiver Arbeit (`_models_busy`) – weiterhin erfolgreich und
  zustandslos statt deferred/failed.
- Auf dem alten Stand reproduziert: Probe-`False` in beiden Reihenfolgen und
  `RuntimeError` (deferred) bei aktiver Arbeit.

## Erhalten / Nicht-Ziele

Kroko-Lizenz-, Modell- und Schedulerfunktionen unverändert; keine neue
Architektur, keine Native-Patches, keine neuen (externen) APIs, kein
V2-Vertragswandel, keine Pro-A→Pro-B-Experimente, kein Merge/Rebase/Force-Push,
Draft-Status unverändert.

## Nachweis

- Gezielt neu: `tests/unit/test_kroko_pr15_b1b2_regression.py` (5 Tests).
- `tests/unit/test_kroko_pr15_final_correction.py` und
  `tests/unit/test_kroko_license_lifecycle.py` unverändert grün.
- Vollsuite `pytest tests/unit` auf finalem Commit (lokal, Windows):
  `2321 passed, 24 skipped, 1330 subtests` in ~712 s (Basis `9ea176ce` auf
  Windows: 2316 passed / 24 skipped; +5 neue B1/B2-Tests, keine Regression).
- GitHub-CI (Ubuntu + Windows) am finalen Commit: siehe PR-Checks
  (Nachweis im Abschlusskommentar).
