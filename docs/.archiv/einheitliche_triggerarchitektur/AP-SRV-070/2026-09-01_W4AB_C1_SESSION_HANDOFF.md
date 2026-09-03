# AP-SRV-070 / W4AB-C1 — Übergabe des unfertigen Korrekturlaufs

## Vertrauensgrenze und Sollgrundlage

Dieses Dokument wurde ausschließlich aus dem verbliebenen Arbeitsgedächtnis
der vorherigen Session erstellt. Prompt, Repository-Dateien und Testergebnisse
wurden dafür nicht erneut eingelesen. Es ist eine Arbeitsübergabe und keine
Abnahmeevidenz.

Die frische Session erhält dieses Dokument gemeinsam mit dem verbindlichen
Prompt:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prompts\AP-SRV-070_W4AB_C1_COMBINED_ROOT_CORRECTION_FINAL.md
```

Der Prompt ist die höhere Authority. Die neue Session muss ihn zuerst
vollständig lesen und bei jeder Abweichung diesem Dokument vorziehen. Kein
historischer repository-weiter Re-Audit; nur den vorhandenen W4AB-C1-Diff und
seine konkreten Callgraphs prüfen und fertigstellen.

## Unveränderliche Grenzen

- Kein SSH und keinerlei Zugriff auf VPS/Hermes.
- Keine Remote-Shell, kein Kroko-Build und keine Ubuntu-Qualification auf
  Hermes.
- Linux-Logik nur lokal über Unit-/Contract-/Adversarial-Tests validieren.
- Keine erfundene oder simulierte Real-Evidenz.
- `HERMES_REQUALIFICATION_REQUIRED: YES` bleibt im Final Return bestehen.
- W4C nicht beginnen.
- Kein Rebase, Amend, Force-Push oder History-Rewrite.
- Canonical nicht verändern.
- Verifier/Guards nicht abschwächen, um Tests grün zu bekommen.
- Erst nach vollständig grüner lokaler Abnahme den exakt vorgeschriebenen
  finalen Commit erstellen und Distributed ausschließlich Fast-Forward
  aktualisieren.

## Verbindliche Git-Basis des finalen Laufs

```text
Parent:      319ce3f29db302795beb767be910fe1aeb8609d6
Distributed: feat/einheitliche-triggerarchitektur-distributed
Canonical:   feat/einheitliche-triggerarchitektur
Canonical erwarteter SHA: c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
Final subject: AP-SRV-070 W4AB-C1: close Linux qualification and W4B root findings
```

Das Start-Gate war vor der ersten Mutation grün: HEAD und Distributed standen
auf dem Parent, Canonical auf dem genannten SHA und der Worktree war sauber.
Danach wurde lokal `work/AP-SRV-070-W4AB-C1` angelegt.

Der Branch, auf dem dieses Dokument gefunden wird, ist nur ein wegwerfbarer
WIP-Checkpoint. Sein Commit ist **nicht** der vorgeschriebene finale
Korrekturcommit und darf nicht nach Distributed gemergt werden.

## Sichere Wiederaufnahme aus dem WIP-Checkpoint

Der finale Zustand muss wieder genau einen Korrekturcommit mit dem W4B-SHA als
direktem Parent besitzen. Ohne Rebase, Amend oder History-Rewrite kann die
frische Session einen neuen Branch direkt vom Parent anlegen und den WIP-Baum
als uncommitted Arbeitsstand übernehmen:

```powershell
git fetch github
git switch -c work/AP-SRV-070-W4AB-C1-final 319ce3f29db302795beb767be910fe1aeb8609d6
git restore --source github/handoff/AP-SRV-070-W4AB-C1-dirty-20260901-01a05c77 --worktree -- .
git status --short
```

Vorher Remote-SHAs und Branchzustand selbst prüfen. Den WIP-Commit niemals als
Final-Commit verwenden. Ob dieses Handoff-Dokument im finalen Archiv verbleibt
oder vor dem finalen Commit entfernt wird, anhand des Prompt-Scope entscheiden.

## Bisher implementierter Stand aus Erinnerung

### A — Linux-Wheel-Tagging

`VoiceSTT/install_kroko.py` retaggt ein erfolgreich gebautes natives
Linux-Wheel auf `1free` oder `1pro`. Geändert werden PEP-427-Dateiname,
interne `*.dist-info/WHEEL`-Zeile `Build:` sowie Hash und Größe des WHEEL-
Eintrags in `RECORD`. Fehlende RECORD-Zeilen werden ergänzt. Die Ausgabe wird
über eine eindeutige `.part`-Datei atomar veröffentlicht. Opposite-Variant-
und unbekannte vorhandene Build-Tags werden abgelehnt. Das ungetaggte
Quell-Wheel wird erst nach erfolgreicher Publikation entfernt. Windows blieb
unverändert.

### B — Linux-Fingerprint und OpenSSL-Authority

Der Linux-Toolchain-Fingerprint enthält nun die effektiv verwendete
OpenSSL-Development-Identität: System-Stack oder expliziter Root, Version,
`opensslv.h`, `ssl.h`, `libssl` und `libcrypto` jeweils mit Pfad und SHA-256.
CLI `--openssl-root-dir` gewinnt vor `OPENSSL_ROOT_DIR`; sonst gilt der
System-Development-Stack. Ambient OpenSSL-Auswahlvariablen werden aus dem
Build-Environment entfernt und nur der autoritativ aufgelöste Root wird bei
Bedarf wieder gesetzt. Fehlende Header/Libraries sollen vor dem Build mit
Hinweis auf `libssl-dev` beziehungsweise expliziten Root scheitern.

zlib wurde nicht als eigener Fingerprint-Input aufgenommen, weil im aktuellen
Callgraph keine separat ausgewählte host-native zlib-Development-Authority als
buildwirksamer Input nachgewiesen wurde. Die Dokumentation begründet dies.

Builder-Revisionen wurden in `WINDOWS_BUILDER_REVISION = 4` und
`LINUX_BUILDER_REVISION = 1` getrennt. `BUILDER_REVISION` blieb kompatibler
Windows-Alias. `builder_revision_for(platform)` speist den Fingerprint. Der
direkt geprüfte Windows-Fingerprint blieb nach Erinnerung exakt:

```text
28594e6d201fc4a7
```

Auf diesem Host hing Python 3.12 in `platform.machine()` innerhalb einer
WMI-Abfrage. Der Kroko-Fingerprint ermittelt Windows-Architektur daher aus
`PROCESSOR_ARCHITEW6432`, `PROCESSOR_ARCHITECTURE` oder Interpreter-Bitness.

### C — Free/Pro-Koexistenz

Free und Pro bleiben in getrennten Store-Namespaces. Tests decken gemeinsames
Ablegen, unabhängiges Lookup/Verify/Reuse, isolierten Rebuild, Mismatch und
`(variant, fingerprint)`-isolierte Locks ab.

### D — Retention/GC

`VoiceSTT/kroko/artifacts.py` besitzt `cleanup_obsolete(...)` mit Default 30
Tage, CLI `--artifact-retention-days`, Environment
`VOICESTT_KROKO_ARTIFACT_RETENTION_DAYS` und `0` zum Deaktivieren. Negative
und nichtnumerische Werte werden abgelehnt. Nur direkte 16-Hex-Slots genau
einer Variante werden betrachtet. Geschützt sind aktueller Fingerprint,
neuestes verifiziertes LKG, andere Variante und gelockte Slots. Symlink- und
Traversal-Löschung werden verhindert. Cleanup ist best-effort und läuft nach
Reuse beziehungsweise Store-Publikation. `builtAt` beeinflusst den Fingerprint
nicht.

### E/F — Key- und Runtimevarianten-Authority

`kroko_pro_license_present` wurde aus `OperatorIntent` und Eligibility
entfernt. Ein Kroko-Key ist nur Runtime-Credential und entscheidet nie über
Runtimevariante, Modellklasse oder Eligibility. Die echte Load-Probe
entscheidet über Credentialfehler.

Die Variantenpräzedenz lautet:

1. `stt_engine_settings.kroko_onnx.runtime_variant`
2. Final-Kroko-Engine-Option `runtime_variant`
3. Realtime-Kroko-Engine-Option `runtime_variant`
4. `VOICESTT_KROKO_VARIANT`
5. sicherer Default `free`

Nur `free` und `pro` sind gültig. Key-Präsenz kann niemals auf Pro
hochschalten. `config.yaml` setzt den normalen Kroko-Default explizit auf
`free`.

### G — Optionen der tatsächlich aufgelösten Engine

`api_fastapi_server/server.py` besitzt
`resolved_engine_options(settings, resolved_engine, lane)`. Probe,
Final-/Realtime-Worker, Recovery, Refresh und Modellwechsel verwenden die
Engine aus `_resolved_stt_models` und erhalten nur passende Optionen:
dieselbe Lane zuerst, passende andere Lane bei Enginewechsel, danach
`engine_options`/`options` aus `stt_engine_settings`, sonst `{}`. Bei gleicher
Engine bleiben lanespezifische Optionen erhalten. Die Probe überschreibt die
konfigurierten Engine-Felder nicht mehr künstlich.

### H — Secret Boundary

Neue gemeinsame Datei: `VoiceSTT_server/credential_redaction.py`. Sie kennt
Kroko-Environment-Aliase, verschachtelte Optionskontexte und Credential-
Feldaliase. Sie bietet rekursives Redact/Drop, sammelt nur für In-Memory-
Diagnostik benötigte Secret-Werte und redigiert Exceptiontexte.

Eingebunden wurden nach Erinnerung: `ServerSettings.public_dict()`,
`RuntimeConfigStore.save()`, Modellmanager-Diagnosen, Settings-PATCH-Response
und Audit, Modell-Switch-Response/Audit/Performance, Refresh-/Worker-/Rollback-
Exceptions und zentrale Event-Sanitization einschließlich nacktem `key`.
Nichtgeheime Nachbarfelder sollen erhalten bleiben. Tests behandeln Env,
Final-Options-only, Realtime-Options-only, verschachtelte Aliase,
Exceptionredaktion, API/PATCH/Persistenz und nichtgeheime Felder. Die neue
Session muss diese Behauptung final adversarial prüfen.

### I — PATCH/Refresh-Semantik

`stt_auto_download_enabled`, `stt_engine_settings` und `stt_model_settings`
werden durch PATCH übernommen und persistiert, als `appliesTo: model_refresh`
markiert und setzen `modelRefreshRequired`/`refreshRequired`. PATCH ruft weder
Refresh noch Provisioning auf.

`POST /api/models/refresh` erzeugt neuen `OperatorIntent` und nutzt ihn nur im
Kandidatenlauf. Bei Refreshexception, nicht bereitem Snapshot gegen vorhandenes
MINIMUM_READY, Busy oder Workerfehler werden Manager-Intent, LKG und
`_resolved_stt_models` wiederhergestellt; Pending bleibt true. Erst Erfolg
löscht Pending. `/api/models`, `/api/models/management`, Health und Metrics
projizieren `refreshRequired`.

### J — Zielplattformgerechte Test-Fixtures

Der Fake-Wheel-Helper in `tests/unit/test_kroko_artifact_store.py` erzeugt
standardmäßig Wheel-Tag, Target und Architektur passend zur Zielplattform.
Explizite symmetrische Fälle bleiben streng:

```text
Windows fingerprint + Windows wheel -> PASS
Windows fingerprint + Linux wheel   -> FAIL
Linux fingerprint   + Linux wheel   -> PASS
Linux fingerprint   + Windows wheel -> FAIL
```

## Erinnerte geänderte Dateien

Diese Liste ist nur Einstiegspunkt und muss durch `git status`/`git diff`
verifiziert werden:

```text
VoiceSTT/install_kroko.py
VoiceSTT/kroko/artifacts.py
VoiceSTT/kroko/buildinputs.py
VoiceSTT/kroko/fingerprint.py
VoiceSTT_server/credential_redaction.py
VoiceSTT_server/event_logging.py
VoiceSTT_server/operations.py
VoiceSTT_server/stt_model_management.py
api_fastapi_server/server.py
build/BUILD.md
config.yaml
docs/engines/kroko-onnx.md
docs/stt-model-management.md
docs/.archiv/einheitliche_triggerarchitektur/AP-SRV-070/2026-09-01_W4AB_C1_PLAN.md
docs/.archiv/einheitliche_triggerarchitektur/AP-SRV-070/2026-09-01_W4AB_C1_SESSION_HANDOFF.md
tests/unit/test_fastapi_server_multi_user_asr_integration.py
tests/unit/test_install_kroko_cpu.py
tests/unit/test_kroko_artifact_store.py
tests/unit/test_kroko_fingerprint.py
tests/unit/test_server_operations.py
tests/unit/test_stt_model_management.py
```

## Erinnerte grüne Teilresultate

Diese Resultate müssen für das Final Gate wiederholt werden:

```text
Fingerprint + Artifact Store + Linux Installer:
169 passed, 86 subtests passed

Kroko Model Authority + Kroko Engine + STT Model Management:
100 passed, 1 skipped, 32 subtests passed

Scheduler/ASR integration:
8 passed, 1 skipped

Zentraler Event-Secret-Test:
1 passed

compileall:
exit 0
```

Die sechs Mandatory-Kernsuites waren seriell grün. Ein Parallelversuch war
wegen pytest-Temp-/WMI-Ressourcenkollision nicht verwertbar und ist keine
Evidenz.

## Noch offener Testpunkt

Die volle Unit-Regression hat noch keinen verwertbaren Endstatus. Python 3.12
hing reproduzierbar in `platform.py -> _wmi_query`, ausgelöst beim Import von
`torch` beziehungsweise `onnxruntime`. Stack-Dumps zeigten diesen Host-Hänger,
keinen identifizierten Produktfehler. Einzeltests liefen, nachdem der
Testprozess die auf diesem Rechner feste Identität `Windows/AMD64` explizit
setzte.

Zuerst normal, seriell und mit eindeutigem `--basetemp` testen. Keine
parallelen pytest-Prozesse. Falls WMI weiter hängt, darf ausschließlich für den
lokalen Testprozess vor `pytest.main(...)` `platform.machine` und
`platform.system` auf `AMD64`/`Windows` gesetzt werden. Diese transparente
Host-Umgehung verändert weder Produktcode noch Tests und ist niemals
Linux-/Hermes-Evidenz. Keine WMI-, Torch- oder Wake-Word-Fremdrefactorings und
keine Manipulation fremder Prozesse/Systemdienste.

## Restarbeiten bis zur Fertigstellung

1. Verbindlichen Prompt vollständig lesen.
2. WIP-Diff und Branchzustand vollständig prüfen.
3. Finalen Arbeitsbranch direkt vom W4B-Parent anlegen und WIP nur als
   uncommitted Baum übernehmen.
4. Produktcode adversarial reviewen: Wheel/RECORD-Sonderfälle,
   OpenSSL-Auflösung, Linux-Guard und Windows-Stabilität, Retention-LKG/Locks/
   Symlinks/Varianten, Key-unabhängige Eligibility, Variantenpräzedenz,
   Optionen bei Probe/Recovery/Refresh/Switch, Secretgrenzen und
   Refresh-Transaktionalität.
5. Direkt betroffene Server-/Settings-/Model-API-/Scheduler-Suites vollständig
   ausführen und Fehler innerhalb des Scopes beheben.
6. Die sechs Mandatory-Suites erneut seriell ausführen.
7. Full Unit Regression mit `0 failed`, `0 errors`:

   ```powershell
   python -m pytest -q --basetemp=.pytest-tmp/w4ab-c1-full tests/unit
   ```

8. Compileall:

   ```powershell
   python -m compileall -q VoiceSTT VoiceSTT_server api_fastapi_server tests/unit
   ```

9. Final `git diff --check`, `git status --short`, Secret-Scan, Scope-Scan und
   Hygiene-Scan. Keine Wheels, Modellblobs, venvs, Buildcaches, `.part`,
   pytest-Temps, Secrets oder Hermes-Evidenz committen.
10. Archivierten Soll-/Ist-Vergleich zum Plan erstellen und A–J jeweils als
    `IMPLEMENTED / TESTED / PASS|FAIL` belegen.
11. Exakte spätere Hermes-Requalification-Kommandos anhand des finalen Codes
    vorbereiten, aber nicht ausführen.
12. Vor Commit Parent, Distributed, Canonical, Tests, Diff, Secret und Scope
    erneut prüfen.
13. Genau einen finalen Commit erzeugen:

    ```text
    AP-SRV-070 W4AB-C1: close Linux qualification and W4B root findings
    ```

14. Ausschließlich Fast-Forward publizieren:

    ```powershell
    git push github HEAD:feat/einheitliche-triggerarchitektur-distributed
    ```

15. Distributed und Canonical danach prüfen und Abschnitt 16 des Prompts
    vollständig zurückgeben.

## Vor-Commit-Matrix

```text
A Linux variant tagging                 IMPLEMENTED / TESTED / PASS|FAIL
B Linux OpenSSL/toolchain fingerprint   IMPLEMENTED / TESTED / PASS|FAIL
C Free+Pro coexistence                  IMPLEMENTED / TESTED / PASS|FAIL
D Retention/GC                          IMPLEMENTED / TESTED / PASS|FAIL
E Key != license/runtime authority      IMPLEMENTED / TESTED / PASS|FAIL
F deterministic runtime variant         IMPLEMENTED / TESTED / PASS|FAIL
G resolved-engine options               IMPLEMENTED / TESTED / PASS|FAIL
H secret boundary                       IMPLEMENTED / TESTED / PASS|FAIL
I refresh semantics                     IMPLEMENTED / TESTED / PASS|FAIL
J cross-platform wheel fixtures         IMPLEMENTED / TESTED / PASS|FAIL
```

## Final-Return-Schablone

```text
START_GATE:
CORRECTION_RESULT:

PARENT_SHA:
COMMIT_SHA:
TREE_SHA:
DISTRIBUTED_SHA:
CANONICAL_SHA:

LINUX_TAGGING:
LINUX_FINGERPRINT_AUTHORITY:
WINDOWS_FINGERPRINT_STABILITY:
FREE_PRO_STORE_COEXISTENCE:
ARTIFACT_RETENTION:
KROKO_VARIANT_AUTHORITY:
ENGINE_OPTION_ISOLATION:
SECRET_BOUNDARY:
MODEL_REFRESH_SEMANTICS:
CROSS_PLATFORM_TEST_FIXTURES:

TARGETED_TESTS:
FULL_UNIT_REGRESSION:
COMPILEALL:
GIT_DIFF_CHECK:
SECRET_SCAN:
SCOPE_GATE:

HERMES_REQUALIFICATION_REQUIRED: YES
HERMES_COMMANDS:

W4C_STARTED: NO
```

Keine lokale Windows-Prüfung als reale Ubuntu-/Hermes-Requalification
ausgeben.
