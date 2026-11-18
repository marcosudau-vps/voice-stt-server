# AP-SRV-070 / W4A-C3 — Root Correction Report (Findings I–K)

**Run:** W4A-C3 — Final Root Correction + Real Artifact Qualification
**Datum:** 2026-09-01
**Parent:** `c8db0f5687dc535e0fe9974fba0445b8fd10f2e1` (W4A-C2)
**Parent-Tree:** `5fc61b069f70ad98565eecb90a7b22858ebe695b`
**Scope:** ausschließlich Kroko Builder / Fingerprint / Artifact Store + zugehörige
Buildinput-Authority, deren Tests und die direkt betroffene Kroko-Builddoku.
W4B wurde nicht begonnen.

---

## 0. Start-Gates

| Gate | Erwartet | Vorgefunden | Status |
| --- | --- | --- | --- |
| Worktree | `…\voice-stt-server\workspaces\ap-srv-070` | identisch, `git status` sauber | OK |
| Branch | `work/AP-SRV-070` | identisch | OK |
| Parent HEAD | `c8db0f5687dc535e0fe9974fba0445b8fd10f2e1` | identisch | OK |
| Parent Tree | `5fc61b069f70ad98565eecb90a7b22858ebe695b` | identisch | OK |
| Distributed vor Beginn | `c8db0f5687dc535e0fe9974fba0445b8fd10f2e1` | `github/feat/einheitliche-triggerarchitektur-distributed` = `c8db0f56…` (per `git ls-remote` gegen die Live-Remote bestätigt) | OK |
| Canonical unverändert | `c82923fc6ce889b4dfbbde1f9877b8b76481a1e8` | `github/feat/einheitliche-triggerarchitektur` = `c82923fc…` | OK |

**Hinweis zu einer lokalen Ref-Altlast (keine Gate-Verletzung, keine Mutation
vorgenommen):** im Worktree existiert zusätzlich eine *lokale* Branch-Ref
`feat/einheitliche-triggerarchitektur-distributed` auf `07b5bc0`, die kein
Upstream-Tracking hat und seit W3 nicht mehr nachgezogen wurde. Autoritativ für
das Distributed-Gate ist — wie schon in W4A-C1/C2 dokumentiert („Remote
Distributed vor/nach Push") — die Remote-Ref, und die stand und steht exakt auf
dem geforderten Parent. Die verwaiste lokale Ref wurde bewusst **nicht**
angefasst.

---

## 1. Root Finding I — `--repo`-Override und wiederverwendeter Checkout

### Befund

W4A-C1 hat `args.repo`/`args.revision` korrekt an den Fingerprint gekoppelt, der
reale Checkout-Pfad blieb aber source-agnostisch: `prepare_checkout()` hat einen
bereits vorhandenen `<work_dir>/kroko-onnx` unbesehen weiterverwendet. Dessen
`origin` zeigte weiterhin auf das Repo, aus dem er ursprünglich geklont wurde,
und `ensure_pinned_revision()` fetcht fehlende Commits genau über dieses
`origin`. Fingerprint-Authority und Fetch-/Checkout-Authority konnten damit
auseinanderlaufen.

### Korrektur

`VoiceSTT/install_kroko.py`:

* neu `checkout_origin_url(repo_dir)` — liest die `origin`-URL eines vorhandenen
  Checkouts; `None`, wenn das Verzeichnis kein lesbares git-Repo ist oder kein
  `origin` hat;
* neu `normalize_repo_authority(repo)` — faltet ausschließlich kosmetische
  Schreibweisen (abschließender Separator, abschließendes `.git`, bei lokalen
  Pfad-Authorities die plattformeigene Pfadschreibweise). Alles, was eine
  *andere* Quelle bezeichnen könnte, bleibt signifikant;
* neu `checkout_matches_repo_authority(repo_dir, repo)` — vergleicht beides;
  ein nicht identifizierbarer Checkout gilt als **nicht** zugehörig;
* `prepare_checkout()` entfernt einen Checkout, der nicht zur effektiven
  `args.repo`-Authority gehört, und klont neu aus `args.repo`. Danach wie bisher
  exakte `revision` pinnen und pristine materialisieren.

Die Entfernung läuft weiterhin über `remove_tree_inside(repo_dir, work_dir)` und
ist damit auf den validierten Kroko-Builder-Workroot beschränkt. Der
VoiceSTT-Projektworktree wird nie berührt.

### RED-/Regression-Proof

`tests/unit/test_kroko_artifact_store.py::RootFindingISourceAuthorityTests`
fährt zwei echte, wegwerfbare lokale git-Repos (nie der VoiceSTT-Worktree, nie
das echte Kroko-Upstream):

| Prompt-Anforderung | Test |
| --- | --- |
| 1.–4. Repo A zuerst, dann `--repo B` + nur in B existierender Full-SHA; Checkout und reale Fetch-Authority sind danach B | `test_reused_checkout_from_another_repo_is_reclaimed_for_the_requested_one` |
| 5. Fingerprint / describe / realer Checkout dokumentieren dieselbe Repo-/Revision-Authority | `test_fingerprint_describe_and_checkout_agree_on_the_same_authority` |
| 6. Reuse-Hit benötigt überhaupt keinen Checkout | `test_reuse_hit_needs_no_checkout_at_all_regression` (auch `checkout_matches_repo_authority` wird nicht aufgerufen) |
| Guard darf nicht jeden normalen Rerun zum Neuklon machen | `test_matching_authority_still_reuses_the_existing_checkout` |
| Unidentifizierbarer Checkout wird nie vertraut | `test_a_checkout_without_a_readable_origin_is_never_trusted` |
| Nur kosmetische Schreibweisen werden gefaltet | `test_authority_comparison_folds_only_cosmetic_spellings` |

`BUILDER_REVISION` 3 → 4; die drei neuen Funktionen sind Teil der geguardeten
Builder-Surface.

---

## 2. Root Finding J — Windows-Toolchain ist jetzt wirklich immutable

### Befund

Der Windows-Fingerprint behauptete `"definedBy": "upstream-revision+patch-set"`.
Das war unzutreffend: das Builder-Image zog ein gleitendes `ubuntu:24.04`-Tag,
löste `apt` gegen das *Live*-Archiv auf, installierte ungepinnte
Python-Packaging-Tools, lud mehrere Binaries ohne Content-Hash und wählte —
am kritischsten — OpenSSL über eine Verfügbarkeitsschleife („erste noch
erreichbare Version gewinnt"). Derselbe Fingerprint konnte damit materiell
verschiedene kompilierte Bytes bezeichnen.

### Korrektur — Variante A (Buildinputs vollständig pinnen)

`VoiceSTT/kroko/buildinputs.py` deklariert die vollständige Windows-Toolchain
source-controlled:

| Input | Pin |
| --- | --- |
| Base-Image | `ubuntu:24.04@sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517` |
| apt-Auflösung | `https://snapshot.ubuntu.com/ubuntu/20260825T000000Z`, Suites `noble noble-updates noble-security`, Komponenten `main restricted universe multiverse`, GPG-verifiziert über `ubuntu-archive-keyring.gpg` |
| clang / NSIS | `19` / `3.10` (aus dem Snapshot aufgelöst) |
| CMake | `3.30.5`, SHA-256 `f747d9b23e1a252a8beafb4ed2bc2ddf78cff7f04a8e4de19f4ff88e9b51dc9d` |
| xwin | `0.6.5`, SHA-256 `9fd53950b064d067f42428a69453b927656cae68dbd7f8d3f86dcb81c80dd22d` |
| Windows-CPython-Target | `3.12.7` (`cp312`), SHA-256 `149dd298e0b7a82250ca019471770fff079874088a4e8501ca20922d7df3a6ac` |
| VC++ Redistributable | immutable versionierte MS-URL, SHA-256 `cc0ff0eb1dc3f5188ae6300faef32bf5beeba4bdd6e8e445a9184072096b713b` (ersetzt den rollierenden `aka.ms`-Alias) |
| **OpenSSL** | **genau eine** Version `3.6.4` (conda-forge `hf411b9b_0`), SHA-256 `9dddb559ba49744d5d94092d8d13cb0567f5c3b3f439f3acf28433d1f4256acc` |
| openfst | Tag `sherpa-onnx-2024-06-19`, SHA-256 `5c98e82cc509c5618502dde4860b8ea04d843850ed57e6d6b590b644b268853d` |
| Packaging-Tools | `setuptools==75.8.2 wheel==0.45.1 delvewheel==1.10.1 pefile==2024.8.26` |

**Warum conda-forge für OpenSSL:** die harte Regel des Prompts verlangt „exakt
deklarierte Source-Version + exakt deklarierter SHA-256, und wenn die Source
nicht mehr verfügbar ist: BUILD ERROR". Slproweb erfüllt den Buchstaben, aber
rotiert Patch-Versionen aktiv weg (genau das war der beobachtete Ausfall), ein
Pin dort wäre also binnen Wochen tot. conda-forge veröffentlicht unveränderliche,
content-adressierte Pakete mit publiziertem SHA-256: die Datei ist entweder
byte-identisch oder sie ist weg — und „weg" muss den Build brechen.

**Warum `wheel` unter 0.46 gepinnt ist:** upstream `cmake/cmake_extension.py`
importiert `wheel.bdist_wheel`, das 0.46 entfernt hat, und fällt bei
ImportError still auf `bdist_wheel = None` zurück — das ändert, wie das Wheel
getaggt wird. Der Pin ist damit build-effektiv begründet, nicht kosmetisch.

**ca-certificates-Bootstrap (eine bewusst dokumentierte Ausnahme):** das
Base-Image bringt keinen CA-Bundle mit, und der Snapshot-Dienst ist
HTTPS-only (`http://` redirectet auf `https://`). Ein Trust Store ist kein
Build-Input — nichts daraus kann in das erzeugte Wheel gelangen — deshalb wird
`ca-certificates` einmalig aus den bildeigenen Default-Quellen gebootstrappt,
*bevor* die Quellen auf den Snapshot umgestellt werden. Jedes Paket, das die
erzeugten Bytes beeinflussen kann (Compiler, Linker, Build-Tooling), kommt
ausschließlich aus dem Snapshot. Der Snapshot-Zeitpunkt (2026-08-25) liegt nach
dem Erstellungsdatum des gepinnten Base-Images (2026-08-17), es sind also nur
Upgrades und keine Downgrades nötig.

### Fingerprint-Seite

`VoiceSTT/kroko/fingerprint.py`:

* neu `windows_toolchain_authority()` — SHA-256 über die kanonisierte
  Deklaration, gekürzt auf 16 Hex;
* `toolchain_identity("windows")` liefert jetzt
  `{"kind": "kroko-docker-windows-crossbuild", "definedBy":
  "pinned-windows-builder-inputs", "authority": <id>, "inputs": <Deklaration>}`.

Das ist **reine Berechnung über Konstanten**: kein Docker-Build, kein
Registry-Lookup, kein Netzwerk. Ein normaler REUSE-/`--describe-artifact`-Pfad
bleibt damit offline, wie vom Prompt ausdrücklich gefordert.

Effektiver Windows/free-Fingerprint dieses Stands:
`b2483a5a5c488f59`, Toolchain-Authority `5c93d37146d3dd23`.

### RED-/Regression-Proof

`tests/unit/test_kroko_fingerprint.py::RootFindingJWindowsToolchainAuthorityTests`:

| Prompt-Anforderung | Test |
| --- | --- |
| 1. konkrete immutable Toolchain-Authority statt `definedBy: upstream-revision+patch-set` | `test_windows_fingerprint_names_a_concrete_immutable_authority` |
| 2. Änderung der Authority ändert den Fingerprint | `test_changing_any_pinned_input_changes_the_windows_fingerprint` (je ein Vertreter pro Input-Klasse als Subtest) |
| 3. keine availability-basierte OpenSSL-Auswahl im generierten Build | `test_generated_windows_build_has_no_availability_based_openssl_choice` |
| 4. OpenSSL-Content wird vor Verwendung gegen deklarierten SHA-256 geprüft | `test_generated_windows_build_verifies_openssl_against_a_declared_hash` (inkl. Reihenfolge Download → Hash → Entpacken) |
| 5. mutable Base-Image-/Packaging-Tool-Inputs geschlossen | `test_generated_windows_build_closes_the_mutable_image_inputs` (inkl. openfst im Container-Skript) |
| 6. `fingerprint_for()`/`describe_artifact()` bleiben offline | `test_describe_and_fingerprint_stay_offline_for_windows` |
| 7. normale VoiceSTT-/Produktversionsänderungen bewegen den Fingerprint nicht | `test_ordinary_voicestt_changes_still_leave_the_windows_fingerprint_alone` |
| Deklaration ist die einzige Quelle des generierten Builds | `test_declared_pins_are_the_only_source_of_the_generated_build` |
| Ein nicht anwendbarer Pin scheitert laut | `test_a_missing_upstream_anchor_fails_loudly` |

`PATCH_SET_REVISION` 1 → 2; die beiden neuen Deklarationsfunktionen
(`_pinned_windows_dockerfile_edits`, `_pinned_windows_openssl_block`) sind Teil
der geguardeten Patch-Surface.

---

## 3. Root Finding K — crash-atomarer Force-Rebuild-Swap

### Befund

`store()` ersetzt einen belegten Slot mit zwei Moves (`final -> backup`,
`staging -> final`) und rollt bei einer Python-Exception zurück. Bei einem
**harten Prozessabbruch** zwischen den beiden Moves läuft dieser Recovery-Code
nicht: `final` fehlt, das Last-Known-Good liegt nur noch unter seinem
Backup-Namen, und der nächste `lookup()` meldete schlicht Cache-Miss — also
~30 Minuten Neubau für ein Artifact, das noch auf der Platte lag. Zusätzlich
konnte ein Abbruch nach dem zweiten Move `.replaced-*`-Leichen hinterlassen.

### Korrektur

`VoiceSTT/kroko/artifacts.py`:

* neue Konstante `REPLACED_SUFFIX = ".replaced-"` (vorher ein Inline-Literal),
  damit der Backup-Name ein benanntes Slot-Artefakt ist;
* `read_metadata_in(slot_dir)` / `_verify_slot_dir(...)` — dieselbe vollständige
  Verifikation (Fingerprint, Variante, Inputs, Bytes, SHA-256, Wheel-Tags) für
  den Live-Slot **und** für ein Backup. Ein Backup wird nie über seinen Namen
  geglaubt;
* `replaced_backups(variant, fingerprint)` — ein einzelner Directory-Glob, ohne
  Hashing;
* `_recover_slot_locked(...)` — trifft beide Entscheidungen unter demselben
  per-Slot-OS-Lock: verifizierter `final` ⇒ Backups aufräumen; fehlender `final`
  + vollständig verifiziertes Backup ⇒ Backup zurückschieben. Ein vorhandener,
  aber nicht verifizierender `final` wird bewusst **nicht** überschrieben
  (`os.replace` ist atomar, das ist nicht dieses Crash-Fenster);
* `recover_slot(...)` — nimmt den Lock und ruft obiges;
* `lookup(..., recover=True)` — nimmt den Lock **nur**, wenn tatsächlich
  Backups neben dem Slot liegen. Der normale Reuse-Pfad bleibt lock-frei;
* `store()` ruft `_recover_slot_locked()` als erstes innerhalb seines Locks
  (so sieht `adopt_existing` den realen Slot-Zustand statt eines scheinbaren
  Miss) und räumt nach erfolgreichem Swap **alle** Backups des Slots ab, nicht
  nur das selbst erzeugte.

`adopt_existing`- und `--rebuild-kroko`-Semantik bleiben unverändert; es gibt
kein Journal, keine DB und keinen Scheduler.

### RED-/Regression-Proof

`tests/unit/test_kroko_artifact_store.py::RootFindingKCrashAtomicSwapTests`:

| Prompt-Anforderung | Test |
| --- | --- |
| 1./2. Abbruch nach `final -> backup`, vor `staging -> final`; nächster Lookup stellt das bekannte gute Artifact ohne Native-Rebuild bereit | `test_known_good_artifact_survives_a_kill_between_the_two_moves`, `test_a_run_after_the_crash_reuses_instead_of_rebuilding` (End-to-End über `install_kroko.main`, Builder wird nachweislich nicht aufgerufen) |
| 3. Abbruch nach `staging -> final` vor Cleanup: neues final bleibt aktiv, Backup wird später sicher bereinigt | `test_crash_after_the_second_move_keeps_the_new_artifact_and_cleans_up` |
| 4. korruptes/fremdes Backup wird nie aktiviert | `test_a_corrupt_backup_is_never_activated`, `test_a_foreign_backup_is_never_activated` |
| 5. zwei gleichzeitige Recovery-Aufrufer, keine Korruption, genau ein gültiger Slot | `test_two_concurrent_recoverers_converge_on_one_valid_slot` |
| 6. bestehende Lock-, concurrent-store- und force-rebuild-Tests bleiben grün | `RootFindingHCrashRecoverableLockTests` und `RootHardeningConcurrentSlotAccessTests` unverändert grün; zusätzlich `test_force_rebuild_semantics_are_unchanged_regression` |
| store() darf nach dem Crash nicht clobbern | `test_store_recovers_before_deciding_what_to_adopt` |
| gesunder Slot nimmt den Recovery-Lock nicht | `test_healthy_slot_never_takes_the_recovery_lock` |

---

## 4. Guard-/Revision-Vertrag

| Guard | vorher | nachher |
| --- | --- | --- |
| `PATCH_SET_REVISION` | 1 | **2** (Dockerfile-/Container-Patch-Ausgabe ändert sich real) |
| `BUILDER_REVISION` | 3 | **4** (Checkout-/Source-Authority-Logik geändert) |
| `EXPECTED_PATCH_SOURCE_DIGEST` | `0d716f36…` | `17cbc1dd927d74fc10477579a9475920d0ebfa7df8ddb777d92344aa07e183b5` |
| `EXPECTED_BUILDER_SOURCE_DIGEST` | `5d4baea1…` | `4df7ea655259e01e9e1443212d427c9f82c9b98738a0ce0853402923e502b705` |

Beide geguardeten Surfaces wurden **erweitert**, nicht abgeschwächt:

* Patch-Surface `+ _pinned_windows_dockerfile_edits`, `+ _pinned_windows_openssl_block`,
  `+ _packaging_tool_assertion`
* Builder-Surface `+ checkout_origin_url`, `+ normalize_repo_authority`,
  `+ checkout_matches_repo_authority`

Beide Guards wurden negativ verifiziert (simulierte buildwirksame Drift → RED,
Restore → GREEN, Datei byte-identisch wiederhergestellt):
`evidence_artifacts/2026-09-01_W4A_C3_guard_negative_verification.txt`.

Die neuen Windows-Toolchain-Konstanten sind echte Fingerprint-Inputs; dass ihre
Änderung den Fingerprint bewegt, ist per Subtest pro Input-Klasse bewiesen
(Finding J, RED-Proof 2).

---

## 5. Scope- und Hygiene-Nachweis

Geänderte Dateien (vollständig):

```text
VoiceSTT/install_kroko.py
VoiceSTT/kroko/artifacts.py
VoiceSTT/kroko/buildinputs.py
VoiceSTT/kroko/fingerprint.py
docs/engines/kroko-onnx.md
tests/unit/test_kroko_artifact_store.py
tests/unit/test_kroko_fingerprint.py
```

Nicht angefasst: W4B-Modellregistry/Discovery/Auto-Download, W4C Production
Docker, Community-Modell-Lizenzentscheidung, Pro-Modell-Publish,
PyPI/Registry/GitHub-Release, Wakeword-Architektur, allgemeine
Server-Refactorings, Client-Code. Die Doku-Änderung beschränkt sich auf einen
Abschnitt zu den gepinnten Builder-Inputs in der Kroko-Builddoku.

`git diff --check`: sauber.

Run-Commit: `16662698997b5e32980663ccb82176508d1d23dd`, Tree `9433ca78334c5906b60b1ca48f2e3ac92cb6358b`.
