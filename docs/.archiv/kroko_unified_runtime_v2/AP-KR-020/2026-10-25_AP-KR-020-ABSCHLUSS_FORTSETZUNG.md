# AP-KR-020 Abschluss – Ergänzung zur isolierten Nachfolgeintegration

Datum: 2026-10-25. Fortsetzungslauf „Agentenauftrag 04". Eigener Branch
`work/ap-kr-020-abschluss`, eigener Worktree
`voice-stt-server-ap020-abschluss`. Diese Datei schreibt keine historische
AP-Akte um; sie ergänzt sie.

Status dieses Laufs: Integration konfliktbereinigt gemergt, fokussierte
Tests lokal PASS, Push + Draft-Nachfolge-PR + CI siehe unten.

## 1. Originalprompt 1:1

```text
# Agentenauftrag 04 – PR #12 isoliert zur prüfbaren Nachfolgeintegration vorbereiten

**Repository:** `https://github.com/marcosudau-vps/voice-stt-server`  
**Ausgangsbasis:** `origin/feat/v2-unified-kroko` (nach Merge von PR #13; zuletzt `d8d6efc3843235a9e11bdf7d75ffde8d61ecc02f`)  
**Zu integrierender Quellbranch:** `origin/work/ap-kr-020-restintegration` (zuletzt `03b813f27b4f707758ca14bdd1cf5d7d59edeb88`)  
**Neuer Branch:** `work/ap-kr-020-abschluss`  
**Neuer separater Worktree:** `P:/GithubRepos/marcosudau-vps/voice-stt-server/workspaces/kroko-umbau/voice-stt-server-ap020-abschluss`  
**Bestehender Integrations-Worktree – nur als Git-Verwaltungsstartpunkt, NICHT ändern:** `P:/GithubRepos/marcosudau-vps/voice-stt-server/workspaces/kroko-umbau/voice-stt-server-sttm-integration`  
**Bestehender gesicherter Integrationsbranch:** `work/v2-stt-model-management-integration` (zuletzt `220a7191bbbbfb2002f7221894976f27b03a40f2`, Linux-/Windows-CI grün).  
**Auftragstyp:** Enger Git-/Integrations-/Testauftrag für Kroko AP-KR-020. Keine neue Server- oder STT-Modellverwaltung; kein Pro-Entitlement erfinden.

## Warum dieser Auftrag und nicht PR #12 blind mergen?

PR #12 (`feat/v2-unified-kroko-ap020`, HEAD `454e497fff4c0b1f466de03f536a13cf7bce522a`) ist ein alter, als `BLOCKED` ausgewiesener Draft. Dessen Commit ist ein Vorfahr von `work/ap-kr-020-restintegration`, der **sieben zusätzliche Commits** für Native-Status, Besitzerprozess/Generation, Supervisor und Sicherheitsgates enthält. Der inzwischen gemergte PR #13 hat den Zielbranch weiterbewegt. Der größere STTM-Integrationsbranch enthält zwar beide Arbeiten, aber auch umfangreiche und für AP-KR-020 unabhängige neue Modell-, Download-, Settings- und HTTP-Funktionen. **Die Restintegration soll deshalb separat und reviewbar gegen den aktuellen Zielbranch gestellt werden, ohne den großen STTM-Umfang mitzuschleppen.**

Die fehlende unabhängige Kroko-Lizenz-/Modellrechte-/Widerrufs-/Aktualitätsqualifikation bleibt ein **echter externer Blocker**. Ein erfolgreicher Unit-Test, ein Native-Mock, eine Portalkatalogliste oder ein Server-Key allein sind kein Pro-Entitlement. Eine spätere Übernahme darf ausschließlich nachweislich fail-closed bleiben und keine unqualifizierte Pro-Aktivierung ermöglichen.

## A. Zuerst nur lesen und Ist-Zustand sichern

1. Lies `AGENTS.md`, `docs/.archiv/README.md`, `docs/.archiv/kroko_unified_runtime_v2/AP-KR-020/2026-10-22_SCHNITTSTELLEN_LIFECYCLE.md`, `docs/.archiv/kroko_unified_runtime_v2/AP-KR-020/2026-10-23_FORTSETZUNG_LIZENZENTSCHEIDUNG.md`, `docs/.archiv/kroko_unified_runtime_v2/AP-KR-020/2026-10-24_RESTINTEGRATION_PLAN.md` sowie die aktuellen Kroko-API-/Build-Regeln und relevanten Tests.
2. Prüfe `git fetch origin`, `git status`, `git worktree list`, aktuelle SHAs und die Abstammung (`git merge-base --is-ancestor origin/feat/v2-unified-kroko-ap020 origin/work/ap-kr-020-restintegration`). GitHub-Stand hat Vorrang vor obigen Orientierungsshas.
3. **Keine bestehenden Worktrees, Branches oder PRs überschreiben, resetten, umbenennen, rebasen oder löschen.** Falls der angegebene neue Arbeitsbranch/Worktree bereits existiert: zuerst Identität, Zustand und Inhalt prüfen; niemals blind neu anlegen oder hart zurücksetzen.
4. Lege im neuen Worktree auf Basis des aktuellen `origin/feat/v2-unified-kroko` zunächst eine kleine datierte Plan-/Startakte an und committe sie **vor** fachlicher Integrationsarbeit, falls dies mit `docs/.archiv/README.md` verlangt wird. Dokumentiere explizit den Stand nach PR #13.

## B. Enge, nachvollziehbare Integration

1. Integriere `origin/work/ap-kr-020-restintegration` **mit erhaltener Commit-Historie** in `work/ap-kr-020-abschluss` (normaler Merge ohne Rebase/Cherry-Pick-Doppelung). Weil PR #12 ein Vorfahr ist, **nicht** zusätzlich dessen Head separat mergen. Falls Konflikte bestehen: nur belegbar auflösen; bei unklaren Produkt-/Sicherheitskonflikten abbrechen, genaue Stellen dokumentieren und `BLOCKED` melden. Keine eigenmächtige Neuimplementierung.
2. Stelle per `git merge-base --is-ancestor` sicher, dass sowohl der Zielbranch nach PR #13 als auch der vollständige Restintegrations-HEAD Vorfahren des resultierenden Arbeitsbranches sind.
3. Ermittle und dokumentiere per `git diff --name-status origin/feat/v2-unified-kroko...HEAD` und `git log` genau, was der Nachfolge-PR umfasst. Er darf **keine** STTM-Neuentwicklungen wie `voice_stt_server/models/`, `tests/unit/test_stt_download_jobs.py`, `tests/unit/test_stt_management_v2.py` oder neue STT-HTTP-Routen enthalten. Das ist ein harter Scope-Check.
4. Keine Änderungen an `/ws/v2`-Wire-Schema, Produktrechten, Modellmanifest, unautorisierten Lizenzaufrufen oder sonstigen Native-Buildinputs. Die schon im Restintegrationsbranch enthaltenen Buildinput-/Fingerprintänderungen unverfälscht übernehmen und mit den bestehenden Guardtests nachweisen.

## C. Verbindliche technische Nachweise

Führe in einem möglichst sauberen Projekt-Testenv die vorhandenen fokussierten Tests aus (Dateien nur, soweit im aktuellen Baum vorhanden):

- `python -m pytest -q tests/unit/test_kroko_unified_runtime.py tests/unit/test_kroko_restintegration.py tests/unit/test_kroko_fingerprint.py tests/unit/test_kroko_model_authority.py tests/unit/test_realtime_streaming_transcription.py --tb=short`
- `python -m pytest -q tests/unit/test_install_kroko_cpu.py tests/unit/test_release_candidate.py --tb=short` (soweit unterstützt)
- `python -m compileall -q VoiceSTT/kroko VoiceSTT/transcription_engines api_fastapi_server`
- `git diff --check`

Lass danach die normalen GitHub-CI-Checks für diesen **neuen** Arbeitsbranch laufen und erfasse ihren echten Status unter Windows und Linux. Keine Lizenz-/Portal-/Produktivkontakte, keine realen Pro-Tests ohne ausdrücklich genehmigten Testzugang. Falls umfangreiche Tests ressourcenseitig nicht möglich sind, `NOT_RUN` statt `PASS`; keine Testresultate behaupten, die nicht gelaufen sind.

Prüfe besonders die Fälle: fehlender Server-Key, Force-Community, fehlender/ungültiger/abgelaufener/entzogener Pro-Nachweis, Ein-Prozess-Owner, Generationswechsel, sichere Abweisung unqualifizierter Pro-Modelle, keine Secret-Leaks, keine Nebenwirkung auf Faster-Whisper oder die eingefrorene V2-Wire-Schnittstelle. Bestehende Mocks sind nur synthetische Evidenz.

## D. Arbeitsakte und PR

1. Führe unter `docs/.archiv/kroko_unified_runtime_v2/AP-KR-020/` eine **neue, datierte** Ergänzung für diesen konkreten Fortsetzungslauf: Originalprompt 1:1, kurze Ablaufchronik, tatsächliche Git-/Testnachweise, geprüfte Teilfunktionen, exakte externe Blocker und Soll-/Ist-Abweichungen. Historische AP-Akten nicht nachträglich umschreiben. Archivregister `docs/.archiv/README.md` nach Projektregel ergänzen.
2. Nach erfolgreicher konfliktfreier Integration und fokussierten Prüfungen: Commit und Push **nur** `work/ap-kr-020-abschluss`, ohne Force. Erstelle einen **Draft-Nachfolge-PR** gegen `feat/v2-unified-kroko` mit Verweisen auf den alten PR #12, die sieben Restintegrationscommits, den CI-Status und die noch offenen Lizenzgates.
3. **PR #12 nicht selbst schließen, nicht mergen, nicht als COMPLETE deklarieren.** Der Nachfolge-PR ist zunächst die prüfbare Grundlage für unsere unabhängige Abnahme. Erst danach können wir den alten Draft ausdrücklich als „durch Nachfolge-PR ersetzt“ schließen – diese Entscheidung trifft der Auftraggeber.
4. Falls einer der Belege fehlt oder Konflikte unklar sind: keinen PR schönreden, sondern `PARTIAL`/`BLOCKED` mit exakten Ursachen melden. Der vorhandene STTM-Branch muss unverändert bleiben.

## E. Abschlussmeldung

Melde `READY_FOR_REVIEW` erst nach überprüftem Push und angelegtem Draft-PR (oder `BLOCKED` bei realem Hindernis). Gib Branch, vollständige HEAD-SHA, GitHub-PR-URL, unveränderte Ausgangsrefs, Merge-Ancestry, alle betroffenen Dateien, Testkommandos mit echten Ergebnissen, CI-URL/Status sowie Pfade zur Originalprompt-/Evidenz-/Abschlussakte an. Benenne weiterhin fehlende echte Pro-/Lizenznachweise ausdrücklich und trenne sie von erfolgreich geprüften, aber fail-closed bleibenden Runtime-Komponenten.

**Jetzt ausschließlich diesen isolierten AP-KR-020-Nachfolgeintegrationsauftrag ausführen.**
```

## 2. Ablaufchronik (tatsächlich)

1. Pflichtakten gelesen: `AGENTS.md`, `docs/.archiv/README.md`,
   `2026-10-22_GESAMTPLAN.md`, AP-KR-020-Akten aus dem
   Restintegrations-Worktree (`2026-10-22_SCHNITTSTELLEN_LIFECYCLE.md`,
   `2026-10-23_FORTSETZUNG_LIZENZENTSCHEIDUNG.md`,
   `2026-10-24_RESTINTEGRATION_PLAN.md`), `build/BUILD.md`.
2. `git fetch origin`: alle Orientierungs-SHAs bestätigt
   (`d8d6efc`, `454e497`, `03b813f`, `220a719`). Ancestry PR #12 →
   Restintegration: Exit 0.
3. Lokaler Branch `work/ap-kr-020-abschluss` existierte bereits auf exakt
   der geforderten Basis `d8d6efc` (sauber, ohne Remote); kein hartes
   Zurücksetzen. Aktuellen Checkout per `git checkout --detach HEAD`
   freigegeben und danach den angeforderten separaten Worktree
   `voice-stt-server-ap020-abschluss` auf diesen Branch angelegt.
   STTM-Worktree/Branch unverändert (nur gelesen).
4. Startakte `2026-10-25_AP-KR-020-ABSCHLUSS_START.md` angelegt und **vor**
   der Integration committet (`1aade3d`).
5. Normaler Merge `origin/work/ap-kr-020-restintegration` → zwei
   Dokukonflikte (`docs/.archiv/README.md`,
   `docs/stt-model-management.md`), belegbar aufgelöst (siehe 4.),
   Mergecommit `4ea28a4`. Kein Rebase/Cherry-Pick, PR-#12-Head nicht
   separat gemergt.
6. Ancestry, `diff --name-status`, Scope-Check, fokussierte Tests,
   `compileall`, `diff --check` ausgeführt (siehe 3.).
7. Diese Ergänzungsakte angelegt, Register ergänzt, committet, gepusht
   (ohne Force), Draft-Nachfolge-PR erstellt (siehe Abschlussmeldung).

## 3. Tatsächliche Git-/Testnachweise

- Basis: `origin/feat/v2-unified-kroko` =
  `d8d6efc3843235a9e11bdf7d75ffde8d61ecc02f`.
- Quelle: `origin/work/ap-kr-020-restintegration` =
  `03b813f27b4f707758ca14bdd1cf5d7d59edeb88`.
- STTM-Referenz unverändert: `220a7191bbbbfb2002f7221894976f27b03a40f2`.
- Ancestry nach Merge (alle Exit 0): `origin/feat/v2-unified-kroko`,
  `origin/work/ap-kr-020-restintegration` und
  `origin/feat/v2-unified-kroko-ap020` sind Vorfahren von HEAD.
- `git diff --name-status origin/feat/v2-unified-kroko...HEAD`: 41 Pfade
  (Kroko-Runtime/Supervisor/Tests/Doku, siehe Merge-Scope); kein
  `voice_stt_server/models/`, kein `test_stt_download_jobs.py`, kein
  `test_stt_management_v2.py`, keine neuen STT-HTTP-Routen
  (Grep über `api_fastapi_server/server.py`-Diff ohne Routentreffer).
- `python -m pytest -q tests/unit/test_kroko_unified_runtime.py tests/unit/test_kroko_restintegration.py tests/unit/test_kroko_fingerprint.py tests/unit/test_kroko_model_authority.py tests/unit/test_realtime_streaming_transcription.py --tb=short` →
  **213 passed, 121 subtests passed** (Windows, CPython 3.12.10).
- `python -m pytest -q tests/unit/test_install_kroko_cpu.py tests/unit/test_release_candidate.py --tb=short` →
  **38 passed, 2 subtests passed**.
- `python -m compileall -q VoiceSTT/kroko VoiceSTT/transcription_engines api_fastapi_server` → Exit 0.
- `git diff --check` → Exit 0.
- Keine Lizenz-/Portal-/Produktivkontakte, keine realen Pro-Tests.
- GitHub-CI für den neuen Branch: siehe Draft-PR (URL/Status in der
  Abschlussmeldung; Windows- und Linux-Checks werden dort erfasst).

## 4. Konfliktauflösung (belegbar, keine Neuimplementierung)

1. `docs/.archiv/README.md`: HEAD (PR #13) brachte die Zeile
   „Unabhängige Vorarbeit: Kroko-Modellkatalog", die Quelle drei Zeilen
   (AP-KR-020 Restintegration / AP-KR-020 Fortsetzung CONDITIONAL /
   AP-KR-025). Belegbar unterschiedliche Aktionen → **Vereinigung**: alle
   vier Zeilen behalten, keine gelöscht.
2. `docs/stt-model-management.md`: Zielbranch (Basis `d8d6efc`, PR #13)
   enthält den Abschnitt „Kroko-Katalogmetadaten"; die Quelle (ältere
   Basis) ersetzte ihn durch den damals korrekten, inzwischen überholten
   Satz „noch nicht implementiert; Arbeitsschritt A blockiert". Nach dem
   Merge wäre dieser Satz falsch (der Merge implementiert gerade die
   Runtime, CONDITIONAL) und würde PR-#13-Doku revertieren → **HEAD
   behalten**, Quellabsatz verworfen. Begründung steht nur hier, die
   Datei selbst wurde nicht neu formuliert.

## 5. Geprüfte Teilfunktionen (synthetische Evidenz, fail-closed)

Abgedeckt durch die grüne Suite (Mocks, kein Live-Nachweis): fehlender
Server-Key (`test_no_key_means_no_check_and_no_pro`), Force-Community
(`test_force_community_*`), fehlender/ungültiger/abgelaufener/entzogener
Nachweis (`test_native_rejection_is_distinct_from_technical_failure`,
`test_authority_refuses_unbounded_or_invalid_ttl`,
`test_rejection_is_authoritative_until_intent_changes`),
Ein-Prozess-Owner (`test_unconfirmed_exit_retains_handle_and_never_spawns_second_owner`,
`test_concurrent_starts_confirm_previous_real_exit`),
Generationswechsel (`test_intent_change_bumps_generation_and_discards_proof`,
`test_model_and_owner_change_invalidate_success`,
`test_stale_generation_verdict_is_discarded`), Abweisung unqualifizierter
Pro-Modelle (`test_unqualified_product_default_never_grants`,
`test_verifier_cannot_grant_unrequested_rights`,
`test_native_adapter_fails_closed_for_unqualified_snapshot`), keine
Secret-Leaks (`test_snapshot_never_carries_secret_material`,
`test_config_fingerprint_ignores_key_material_by_construction`,
`test_verifier_exception_and_reason_never_expose_raw_data`,
`test_supervisor_spawn_error_redacts_environment_and_arguments`),
Faster-Whisper/V2-Wire unberührt (keine Wire-Änderung im Diff;
`test_realtime_streaming_transcription.py` grün).

## 6. Exakte externe Blocker (unverändert, nicht durch Tests geheilt)

- Unabhängige Kroko-Lizenz-/Modellrechte-/Widerrufs-/Aktualitätsqualifikation
  fehlt (kein versionierter nativer Statusvertrag aus Folgeauftrag A, keine
  autorisierte Testumgebung, keine realen Linux-/Windows-Native-Wheels).
- Unit-Grün, Native-Mocks, Portalkatalogliste und Server-Key sind **kein**
  Pro-Entitlement; produktiver `VALID`-Nachweis erfordert den qualifizierten
  Backend plus autorisierte Umgebung.
- Echte RC-/Deployment-/Reconnect-Qualifikation: NOT_RUN.

## 7. Soll-/Ist-Abweichungen

1. Neuer Branch existierte lokal bereits auf korrekter Basis (ohne Remote);
   statt blindem Neuanlegen Identität geprüft (`d8d6efc`, clean) und den
   angeforderten P-Worktree darauf angelegt. Keine fremden Refs verändert.
2. `docs/stt-model-management.md`: Quellabsatz („noch nicht
   implementiert") zugunsten der neueren PR-#13-Katalogdoku nicht
   übernommen (Begründung in 4.). Materiell: kein Codeeinfluss.
3. `docs/.archiv/README.md`: zusätzlich eine Registerzeile für genau
   diesen Abschlusslauf ergänzt (Prüfung offen).
4. Testenv: Windows CPython 3.12.10 lokal; GitHub-CI (Windows/Linux) läuft
   auf dem neuen Branch und wird per PR nachgewiesen, nicht vorab behauptet.
5. Keine unqualifizierte Pro-Aktivierung: produktiver Verifier bleibt
   `UnqualifiedLicenseVerifier` (vergibt nichts).
