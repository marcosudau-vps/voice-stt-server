# AP-SRV-070 / W4AB-C1 — Combined Root Correction

## 0. Auftrag

Führe **einen einzigen konzentrierten Korrekturlauf** auf dem bereits veröffentlichten W4B-Stand aus.

Verbindlicher Parent / aktueller Distributed-Stand:

`319ce3f29db302795beb767be910fe1aeb8609d6`

Distributed:

`feat/einheitliche-triggerarchitektur-distributed`

Canonical muss unverändert bleiben:

`feat/einheitliche-triggerarchitektur` = `c82923fc6ce889b4dfbbde1f9877b8b76481a1e8`

Ziel: die real bestätigten Ubuntu-W4A-Lücken und die W4B-Root-Findings gemeinsam schließen, vollständig testen, genau einen Korrekturcommit erzeugen und ausschließlich Fast-Forward auf Distributed publizieren. **W4C nicht beginnen.**

Der Auftrag ist self-contained. Keine externe Prompt-/Kontextdatei ist Voraussetzung.

---

## 1. Start-Gate

Vor jeder Mutation:

```text
git status --short
git branch --show-current
git rev-parse HEAD
git rev-parse "HEAD^{tree}"
git fetch github
git rev-parse github/feat/einheitliche-triggerarchitektur-distributed
git rev-parse github/feat/einheitliche-triggerarchitektur
```

Erwartung:

```text
HEAD = 319ce3f29db302795beb767be910fe1aeb8609d6
Distributed = 319ce3f29db302795beb767be910fe1aeb8609d6
Canonical = c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
worktree = clean
```

Dann normalen Branch anlegen, z. B. `work/AP-SRV-070-W4AB-C1`.

Kein Rebase, Amend, Force-Push oder History-Rewrite. Bei Start-Gate-Verletzung: STOP.

---

## 2. Finding A — Linux-Wheel korrekt als Free/Pro taggen

Realer Ubuntu-Befund: Native Kompilierung funktioniert, erzeugt aber derzeit ein ungetaggtes Wheel wie:

`kroko_onnx-1.12.9-cp312-cp312-linux_x86_64.whl`

Der Artifact Store lehnt es korrekt ab mit:

`wheel does not declare a free/pro build tag`

### Verbindliche Korrektur

Der Linux-Buildpfad muss nach erfolgreichem Upstream-Build korrekt retaggen:

- Free: `1free`
- Pro: `1pro`

Dabei müssen **Dateiname und interne `*.dist-info/WHEEL`-Metadaten (`Build:`)** konsistent geändert werden. Bloßes Umbenennen ist verboten. Der strikte Verifier bleibt unverändert streng.

Erwartete Form:

```text
kroko_onnx-1.12.9-1free-cp312-cp312-linux_x86_64.whl
kroko_onnx-1.12.9-1pro-cp312-cp312-linux_x86_64.whl
```

Pflichttests: Free/Pro-Dateiname, interne `Build:`-Zeile, Free↔Pro-Mismatch negativ, ungetaggtes Wheel negativ, Windows unverändert korrekt.

---

## 3. Finding B — Linux-Fingerprint / Host-Buildauthority schließen

Der Linux-Fingerprint berücksichtigt bereits CMake, C/C++-Compiler, Python/ABI, Flags, Make-Args, Upstream, Variant und Revisionen. Der reale Build verwendet zusätzlich zwingend OpenSSL-Development-Artefakte.

Ein Build mit normalem System-OpenSSL-Development-Stack und ein Build mit explizitem projektlokalem `OPENSSL_ROOT_DIR` dürfen nicht unter derselben effektiven Buildauthority kollidieren, wenn sie unterschiedliche Buildinputs darstellen.

### Ergebnis

Erweitere die Linux-Toolchain-Authority um die **effektiv vom Build verwendete OpenSSL-Development-Identity**. Sie muss relevante Unterschiede von Headers/Libraries, Version/Quelle bzw. effektivem Root unterscheiden.

Prüfe außerdem, ob host-native **zlib** buildwirksam in dieselbe Kategorie fällt. Falls ja, analog schließen; falls nein, kurz begründen.

Der Linux-Preflight muss fehlende Development-Voraussetzungen früh und verständlich melden. Der normale Pfad ist der dokumentierte System-Development-Stack. Ein explizites `OPENSSL_ROOT_DIR` darf unterstützt werden, muss aber in der Fingerprint-Authority sichtbar sein.

### Plattform-spezifische Revision/Guard-Semantik

Die Linux-only-Korrektur darf das bereits real qualifizierte Windows-Artefakt nicht unnötig invalidieren.

Prüfe die heutige gemeinsame `BUILDER_REVISION`-/Guard-Struktur und löse sie sauber, falls nötig. Ziel:

```text
Linux build-effective change -> Linux fingerprint changes
unchanged Windows builder     -> Windows fingerprint bleibt stabil
ordinary VoiceSTT change      -> beide bleiben stabil
```

Guards nicht abschwächen und nicht nur erwartete Digests austauschen. Wenn eine kleine Trennung in shared/windows/linux Builderauthority bzw. platform-spezifische Revisionen sinnvoll ist, implementiere sie.

---

## 4. Finding C — Free und Pro gleichzeitig im Artifact Store

Der persistente Store muss Free und Pro gleichzeitig und unabhängig halten:

```text
<store>/free/<free-fingerprint>/...
<store>/pro/<pro-fingerprint>/...
```

Ein Free-Build/Rebuild/Lookup darf Pro nicht überschreiben/löschen; umgekehrt genauso. `--variant free` und `--variant pro` müssen jeweils ihren eigenen Reuse-Hit finden.

Wichtig: Nicht versuchen, zwei `kroko-onnx`-Distributionen gleichzeitig in **dieselbe Python-Umgebung** zu installieren. Koexistenz betrifft den persistenten Store.

Pflichttests:

1. Free + Pro in denselben Store;
2. beide danach vorhanden;
3. beide unabhängig lookup-/verify-/reuse-fähig;
4. Free-Rebuild verändert Pro nicht;
5. Pro-Rebuild verändert Free nicht;
6. Mismatch bleibt negativ;
7. Locks bleiben `(variant, fingerprint)`-isoliert.

---

## 5. Finding D — Artifact-Retention / GC

Ergänze eine kleine Builder-/Store-Retention.

Empfohlener Default: **30 Tage**.

Konfigurierbar über die bestehende Builder-Konfigurationsgrenze, z. B. sinngemäß:

```text
--artifact-retention-days
VOICESTT_KROKO_ARTIFACT_RETENTION_DAYS
```

`0` deaktiviert automatische Bereinigung. Negative/nichtnumerische Werte sauber ablehnen.

### Semantik

Retention ist **kein künstliches Wheel-Verfallsdatum**. Ein technisch aktuelles, verifiziertes Artifact soll nicht alle 30 Tage neu gebaut werden.

Gelöscht werden nur alte **überholte Store-Slots**.

Schütze mindestens:

- aktuellen gültigen Fingerprint;
- mindestens das neueste verifizierte LKG je Variante;
- die jeweils andere Variante;
- aktuell gelockte/in Benutzung befindliche Slots;
- Store-Root und Lock-Infrastruktur.

`builtAt`/Alter gehört nicht in den Fingerprint.

Cleanup ist best-effort: ein erfolgreicher Lookup/Build darf nicht scheitern, nur weil ein alter Slot wegen Rechten nicht gelöscht werden kann. Fehler diagnostisch sichtbar machen. Keine Symlink-/Traversal-Löschung außerhalb des Store-Roots.

Pflichttests: jung bleibt; alter obsolete Slot weg; aktueller alter Slot bleibt; je Variante mindestens ein LKG; Free-GC lässt Pro in Ruhe; Pro-GC lässt Free in Ruhe; `0` aus; ungültige Werte negativ; Cleanupfehler zerstört Reuse nicht; bestehende Lock/Crash/Backup/Staging-Tests bleiben grün.

---

## 6. Finding E — Key ist kein Lizenz-/Varianten-Entscheider

W4B leitet aktuell eine `kroko_pro_license_present`-Voraussetzung u. a. aus Engine-Option `key` und Kroko-Key-Environmentvariablen ab. Das ist die falsche Autoritätsgrenze.

### Vertrag

Der Key ist ausschließlich **Runtime-Credential**. Er bestimmt niemals:

- Free oder Pro Runtime;
- Community oder Pro Modell;
- Runtime-Variantenauswahl;
- Produkt-/Lizenzklasse.

Modellklasse kommt aus Manifest/Product Authority. Runtime-Variante kommt aus expliziter Runtime-/Build-Konfiguration. Key-Präsenz darf niemals „hochschalten“.

Pflichtfälle:

```text
Free runtime + Free model + kein Key -> zulässig
Free runtime + Pro model + Key -> weiterhin Variant mismatch
Pro runtime + Pro model + kein vorab erkannter Key -> nicht schon in Model-Authority blocken
Pro runtime + Pro model + Runtime-Credential -> echte Load-Probe entscheidet
```

Wenn die echte Engine einen Credentialfehler liefert: diagnostizieren, aber Secret vollständig redigieren.

---

## 7. Finding F — Kroko Runtime-Variante deterministisch auflösen

Aktuell kann `kroko_runtime_variant` ohne Env/Engine-Option `None` bleiben und damit sogar den normalen Free-Pfad blockieren.

### Ergebnis

Genau eine nachvollziehbare effektive Runtime-Variant-Authority:

- sicherer Default = `free`;
- `pro` nur explizit;
- niemals durch Key-Präsenz;
- derselbe Wert für Eligibility, Status/Diagnostik und Runtime-Pfad;
- keine zweite konkurrierende Config-Registry;
- eindeutige dokumentierte Precedence vorhandener expliziter Konfigurations-/Environmentquellen.

W4C darf später Produktionswiring übernehmen; hier keinen Production-Docker-Umbau vorziehen.

Pflichttests: Default Free; explizit Free; explizit Pro; Key allein ändert Free nicht; Konflikt folgt dokumentierter Precedence; Community-Free-Modell ist im normalen Free-Default eligibility-seitig erreichbar.

---

## 8. Finding G — Resolved Engine muss die richtigen Engine-Options erhalten

Wenn der Manager eine andere Engine als die ursprünglich konfigurierte Lane resolved, dürfen Probe und Worker nicht die Options der alten Engine erben.

Das gilt für:

- `LOAD_VERIFIED`-Probe;
- final Worker;
- realtime Worker;
- Recovery mit Enginewechsel;
- Model-Switch/Refresh.

Beispiel:

```text
configured final = faster_whisper
configured realtime = kroko_onnx
resolved recovery = kroko_onnx
```

Dann dürfen keine Faster-Whisper-Options in den Kroko-Konstruktor gelangen.

Implementiere eine kleine gemeinsame engine-spezifische Options-Auflösung, falls sinnvoll.

Adversarial tests mit absichtlich inkompatiblen Sentinel-Feldern:

- Final Faster + Realtime Kroko, Kroko-Probe -> nur Kroko-Options;
- Final Kroko + Realtime Faster, Faster-Probe -> nur Faster-Options;
- Recovery wechselt Engine -> Worker bekommt resolved-engine Options;
- Same-Engine-Pfad unverändert.

---

## 9. Finding H — Secret Boundary vollständig schließen

Ein Kroko-Key darf nie im Klartext erscheinen in:

- `/api/config`;
- `/api/models`;
- `/api/models/management`;
- Health;
- Model-Status/Diagnostics;
- Audit-Events;
- Runtime-Config-Persistenz;
- Exception-/Rollback-Meldungen;
- Run-Metadaten.

Prüfe besonders verschachtelte:

```text
transcription_engine_options
realtime_transcription_engine_options
{"key": "..."}
```

und bekannte Kroko-Key-Aliase.

Credential-Nutzung darf bestehen bleiben, aber öffentliche/persistente Projektionen müssen Secrets entfernen/redigieren. Wenn ein Konfigurationsweg unsicher ist, darf er sauber abgelehnt und auf Environment/Secret-Management verwiesen werden.

Pflichttests:

- Secret nur Env;
- Secret nur final engine options;
- Secret nur realtime engine options;
- Exception enthält Secret -> nur `[REDACTED]`;
- config update + Audit;
- Persistenz;
- Health/Modelstatus;
- nichtgeheime Engine-Options bleiben funktional.

---

## 10. Finding I — Model-Management-Settings / Refresh-Semantik eindeutig machen

Betroffen:

```text
stt_auto_download_enabled
stt_engine_settings
stt_model_settings
POST /api/models/refresh
```

Ein Settings-PATCH darf nicht behaupten, eine Model-Management-Änderung sei bereits aktiv, während der Manager noch den alten Snapshot nutzt. Gleichzeitig soll ein normaler PATCH nicht überraschend einen großen Download starten.

Bevorzugt:

- Settings sicher übernehmen/persistieren;
- Response/Status zeigt, dass ein Model-Refresh erforderlich ist;
- kein großer Auto-Download allein durch PATCH;
- `POST /api/models/refresh` übernimmt neue Intent transaktional;
- LKG bleibt bei Fehler.

Dokumentation und Tests müssen exakt dieselbe Semantik behaupten.

---

## 11. Ubuntu-Testfixture-Portabilität

Die Ubuntu-Qualification fand 27 Fehler, weil ein Fake-Wheel-Helper standardmäßig `cp312-cp312-win_amd64` erzeugt.

Keine simple Umstellung des Defaults auf Linux.

Target-aware/symmetrisch:

```text
Windows fingerprint + Windows wheel -> PASS
Windows fingerprint + Linux wheel   -> FAIL
Linux fingerprint   + Linux wheel   -> PASS
Linux fingerprint   + Windows wheel -> FAIL
```

Relevante Free/Pro-Fälle ergänzen. Strikte Plattformprüfung bleibt unverändert.

---

## 12. Reale Linux-Abnahme nach dem Commit

Windows-/Claude-Lauf darf keine Linux-Evidenz erfinden.

Der neue Commit muss danach auf Hermes/Ubuntu bestehen:

1. normale System OpenSSL-/zlib-Development-Voraussetzungen;
2. neue Linux-Fingerprint/Toolchain-Authority korrekt;
3. genau ein realer nativer Free-Build;
4. Wheel hat `1free` intern + im Dateinamen;
5. Store akzeptiert;
6. zweiter identischer normaler Aufruf = Reuse-Hit, **kein Native-Build**;
7. Disposable venv: Install, `import kroko_onnx`, Free positiv, Pro negativ;
8. basic VoiceSTT/Kroko smoke ohne großes ASR-Modell;
9. targeted Linux tests 0 failed;
10. Repo-Hygiene sauber.

Am Ende exakte Hermes-Requalification-Commands für den neuen Commit ausgeben. Nicht ausgeführte Real-Evidenz als `HERMES_REQUALIFICATION_REQUIRED: YES`, nicht als PASS.

---

## 13. Mandatory Validation

Mindestens vorhandene betroffene Suiten:

```text
tests/unit/test_kroko_fingerprint.py
tests/unit/test_kroko_artifact_store.py
tests/unit/test_kroko_model_authority.py
tests/unit/test_kroko_onnx_engine.py
tests/unit/test_install_kroko_cpu.py
tests/unit/test_stt_model_management.py
```

Direkt betroffene Server-/Settings-/Model-API-/Scheduler-Tests anhand echten Callgraphs ergänzen. Keine Testdateinamen erfinden.

Danach verbindlich:

```text
python -m pytest -q tests/unit
python -m compileall -q VoiceSTT VoiceSTT_server api_fastapi_server tests/unit
git diff --check
git status --short
```

Auf Windows bei Bedarf sauberes explizites `--basetemp`.

Erwartung: 0 failures, 0 errors.

Vor Commit Soll/Ist-Matrix:

```text
A Linux variant tagging
B Linux OpenSSL/toolchain fingerprint
C Free+Pro coexistence
D Retention/GC
E Key != license/runtime authority
F deterministic runtime variant
G resolved-engine options
H secret boundary
I refresh semantics
J cross-platform wheel fixtures
```

Jeder Punkt: `IMPLEMENTED / TESTED / PASS|FAIL`.

Kein Wheel, Modellblob, venv, Buildcache, `.part`, Secret oder Hermes-Evidence committen.

---

## 14. Scope

Nicht Teil: W4C Production Deployment, W5/W6, Release/Publish, Wake Word, Protocol V2, neue DB, neue Schedulerarchitektur, Kroko-Upstream-Fork, erneute Community-Lizenzentscheidung, große Fremdrefactorings.

---

## 15. Commit / Push

Nur bei grünen lokalen Gates genau **einen** Commit:

Parent:

`319ce3f29db302795beb767be910fe1aeb8609d6`

Subject:

`AP-SRV-070 W4AB-C1: close Linux qualification and W4B root findings`

Vor Push Parent/HEAD/Tree/status/diff-check prüfen.

Dann ausschließlich:

```text
git push github HEAD:feat/einheitliche-triggerarchitektur-distributed
```

Kein Force.

Danach:

```text
Distributed = neuer Commit
Canonical = c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
```

---

## 16. Final Return

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

HERMES_REQUALIFICATION_REQUIRED:
HERMES_COMMANDS:

W4C_STARTED: NO
```

Bei echtem Blocker: stoppen, Zustand erhalten, nichts umschreiben und exakt benennen, welches Gate nicht erfüllt werden konnte.
