# AP-SRV-070 / W4A-C4 — Phase 2 Executor Prompt
## Exakte Implementierung der Root-Findings L/M/N + deterministische Retention-Fixture
## Noch KEIN Native-Build, KEINE Full Regression, KEIN Commit, KEIN Push

Du arbeitest weiterhin als **streng geführter Executor** für `AP-SRV-070 / W4A-C4`.

Die Architekturentscheidung ist bereits getroffen.
Du sollst sie **nicht neu entwerfen**, sondern exakt umsetzen und mit gezielten Tests belegen.

Wenn eine konkrete Stelle im vorhandenen Code anders benannt ist als hier, darfst du die Benennung minimal an die vorhandene Struktur anpassen. Die Semantik darfst du nicht verändern.

---

# 1. Arbeitskontext / Start-Gate

Repository:

```text
P:\GithubRepos\marcosudau-vps\voice-stt-server
```

Worktree:

```text
P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070
```

Branch:

```text
work/AP-SRV-070
```

Verbindlicher Parent:

```text
16662698997b5e32980663ccb82176508d1d23dd
```

Verbindlicher Parent-Tree:

```text
9433ca78334c5906b60b1ca48f2e3ac92cb6358b
```

Distributed remote authority:

```text
github/feat/einheitliche-triggerarchitektur-distributed
= 16662698997b5e32980663ccb82176508d1d23dd
```

Canonical:

```text
feat/einheitliche-triggerarchitektur
= c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
```

Phase-1-Evidence:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4A-C4\
```

Gesamtauftrag:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prompts\AP-SRV-070_W4A_C4_FINAL_REPRODUCIBILITY_AND_GREEN_GATE.md
```

Vor jeder Mutation erneut prüfen:

```text
git rev-parse HEAD
git rev-parse "HEAD^{tree}"
git status --short
git branch --show-current
git rev-parse github/feat/einheitliche-triggerarchitektur-distributed
git rev-parse feat/einheitliche-triggerarchitektur
```

Erwartung: exakt die oben genannten Werte, Worktree sauber.

Bei Abweichung:

```text
STATUS: BLOCKED
```

und stoppen.

---

# 2. Verbindliche Phase-1-Fakten

Die folgenden Werte sind **nicht neu zu erforschen**, sondern wurden in Phase 1 aus dem realen C3-Builderzustand rekonstruiert:

## 2.1 xwin Binary

```text
xwin version:
0.6.5

xwin SHA-256:
9fd53950b064d067f42428a69453b927656cae68dbd7f8d3f86dcb81c80dd22d
```

## 2.2 Exaktes C3 Microsoft Channel Manifest

```text
xwin default channel URL for version=17, channel=release:
https://aka.ms/vs/17/release/channel

C3 cache filename:
manifest_17.json

C3 actual bytes:
91833

C3 actual SHA-256:
4c81e902fb7fe2acea779b828e6dc548fe0bbb693df50eda0224263c16686bdd

manifestName:
VisualStudio.17.Release

buildVersion:
17.14.37614.0

productDisplayVersion:
17.14.39 (August 2026)
```

## 2.3 Exaktes C3 Package Manifest

Das Channel Manifest referenziert:

```text
https://download.visualstudio.microsoft.com/download/pr/fa619120-9c0e-47e6-bfe0-3ee96fb671b2/bd98dd01efa4195cb1c11030da63b9e4a3bcec7bc406799a9db80339d6dabd79/VisualStudio.vsman
```

xwin verwendet dafür den Cache-Key / Dateinamen:

```text
pkg_manifest_bd98dd01efa4195cb1c11030da63b9e4a3bcec7bc406799a9db80339d6dabd79.vsman
```

C3 tatsächliche Package-Manifest-Datei:

```text
Bytes:
17955171

Actual SHA-256:
3891c3018a07338b3880cbb28088bb22ef7762eb9206523655b2e3972b9d527e
```

**WICHTIG:** Der `bd98...`-Wert im URL-/Cache-Namen ist NICHT als tatsächlicher Datei-SHA zu behandeln.

Die gepinnte xwin-Version 0.6.5 lädt das Package Manifest intern ausdrücklich mit `checksum=None`, weil der im Channel Manifest enthaltene Payload-SHA laut xwin-Quellcode nicht dem tatsächlichen Dateiinhalt entspricht.

Deshalb muss **VoiceSTT selbst** die tatsächlichen Package-Manifest-Bytes gegen:

```text
3891c3018a07338b3880cbb28088bb22ef7762eb9206523655b2e3972b9d527e
```

verifizieren, bevor xwin diese Datei aus seinem Cache liest.

## 2.4 Exakte C3 SDK-/CRT-Auswahl

```text
Windows SDK:
10.0.26100

xwin --crt-version:
14.44.17.14

realer CRT Header-Build:
14.44.35220
```

Der Phase-1-Proof zeigte, dass:

```text
xwin --accept-license
     --cache-dir /tmp/.xwin-cache
     --manifest /tmp/.xwin-cache/dl/manifest_17.json
     --sdk-version 10.0.26100
     --crt-version 14.44.17.14
     list
```

gegen den vorhandenen C3-Cache exakt die 11 C3-Pakete auswählt.

---

# 3. Finding L/M — exakte Windows xwin/MSVC Authority schließen

## 3.1 `VoiceSTT/kroko/buildinputs.py`

Erweitere die bestehende source-controlled Windows Toolchain Authority.

Verwende klare Konstanten. Die Benennung darf minimal an die bestehende Datei angepasst werden, die Semantik muss exakt sein.

Mindestens deklarieren:

```python
WINDOWS_XWIN_MANIFEST_URL = "https://aka.ms/vs/17/release/channel"
WINDOWS_XWIN_MANIFEST_CACHE_NAME = "manifest_17.json"
WINDOWS_XWIN_MANIFEST_BYTES = 91833
WINDOWS_XWIN_MANIFEST_SHA256 = "4c81e902fb7fe2acea779b828e6dc548fe0bbb693df50eda0224263c16686bdd"

WINDOWS_XWIN_PACKAGE_MANIFEST_URL = (
    "https://download.visualstudio.microsoft.com/download/pr/"
    "fa619120-9c0e-47e6-bfe0-3ee96fb671b2/"
    "bd98dd01efa4195cb1c11030da63b9e4a3bcec7bc406799a9db80339d6dabd79/"
    "VisualStudio.vsman"
)

WINDOWS_XWIN_PACKAGE_MANIFEST_CACHE_KEY = (
    "bd98dd01efa4195cb1c11030da63b9e4a3bcec7bc406799a9db80339d6dabd79"
)

WINDOWS_XWIN_PACKAGE_MANIFEST_CACHE_NAME = (
    "pkg_manifest_"
    + WINDOWS_XWIN_PACKAGE_MANIFEST_CACHE_KEY
    + ".vsman"
)

WINDOWS_XWIN_PACKAGE_MANIFEST_BYTES = 17955171
WINDOWS_XWIN_PACKAGE_MANIFEST_SHA256 = (
    "3891c3018a07338b3880cbb28088bb22ef7762eb9206523655b2e3972b9d527e"
)

WINDOWS_XWIN_SDK_VERSION = "10.0.26100"
WINDOWS_XWIN_CRT_VERSION = "14.44.17.14"
```

Falls die Datei bestehende Helper-Funktionen für URLs/Declarations bevorzugt, nutze diese Struktur. Keine dynamische Netzwerkerkennung.

## 3.2 `windows_toolchain_declaration()`

Die vollständige Authority muss mindestens logisch enthalten:

```json
{
  "xwin": {
    "version": "0.6.5",
    "url": "...",
    "sha256": "...",
    "channelManifest": {
      "url": "https://aka.ms/vs/17/release/channel",
      "cacheName": "manifest_17.json",
      "bytes": 91833,
      "sha256": "4c81..."
    },
    "packageManifest": {
      "url": "https://download.visualstudio.microsoft.com/.../VisualStudio.vsman",
      "cacheKey": "bd98...",
      "cacheName": "pkg_manifest_bd98....vsman",
      "bytes": 17955171,
      "sha256": "3891..."
    },
    "sdkVersion": "10.0.26100",
    "crtVersion": "14.44.17.14"
  }
}
```

Die konkrete JSON-Schachtelung darf zum bestehenden Stil passen.

Harte Semantik:

- Channel Manifest URL + echter SHA + Bytes fingerprint-wirksam.
- Package Manifest URL + Cache-Key + echter SHA + Bytes fingerprint-wirksam.
- SDK-Version fingerprint-wirksam.
- CRT-Version fingerprint-wirksam.
- keine Runtime-/Secret-Werte.
- `fingerprint_for()` / `describe_artifact()` bleiben reine Offline-Berechnung über Konstanten.

---

# 4. Windows Dockerfile-Patch exakt ändern

In `VoiceSTT/install_kroko.py` den bestehenden xwin-Patch so erweitern, dass der erzeugte Dockerfile-Build **vor** `xwin splat` folgende Dinge tut:

1. gepinnte xwin-Binary herunterladen;
2. xwin-Binary gegen bestehenden xwin-SHA verifizieren;
3. `/tmp/.xwin-cache/dl` explizit anlegen;
4. das gepinnte Channel Manifest explizit herunterladen;
5. Größe und SHA-256 des Channel Manifests prüfen;
6. das gepinnte Package Manifest explizit herunterladen;
7. Größe und **echten** SHA-256 `3891...` prüfen;
8. erst danach xwin mit explizitem Manifest, SDK und CRT aufrufen.

Der resultierende Befehl muss logisch dieser Form entsprechen:

```bash
mkdir -p /tmp/.xwin-cache/dl

curl -sLf "<CHANNEL_MANIFEST_URL>" \
  -o /tmp/.xwin-cache/dl/manifest_17.json

test "$(stat -c %s /tmp/.xwin-cache/dl/manifest_17.json)" = "91833"

echo "<CHANNEL_SHA>  /tmp/.xwin-cache/dl/manifest_17.json" \
  | sha256sum -c -

curl -sLf "<PACKAGE_MANIFEST_URL>" \
  -o /tmp/.xwin-cache/dl/pkg_manifest_bd98....vsman

test "$(stat -c %s /tmp/.xwin-cache/dl/pkg_manifest_bd98....vsman)" = "17955171"

echo "<PACKAGE_ACTUAL_SHA>  /tmp/.xwin-cache/dl/pkg_manifest_bd98....vsman" \
  | sha256sum -c -

xwin \
  --accept-license \
  --cache-dir /tmp/.xwin-cache \
  --manifest /tmp/.xwin-cache/dl/manifest_17.json \
  --sdk-version 10.0.26100 \
  --crt-version 14.44.17.14 \
  --arch x86_64 \
  splat \
  --output /opt/xwin
```

Die konkrete Shell-Formatierung soll zum vorhandenen Dockerfile-Patch passen.

## 4.1 Sehr wichtige Details

### A. Kein `latest`-Fallback

Der generierte Dockerfile darf **keinen** xwin-Aufruf mehr enthalten, der:

```text
--manifest
--sdk-version
--crt-version
```

auslässt.

### B. Package Manifest muss vor xwin validiert sein

Nicht darauf vertrauen, dass xwin 0.6.5 das Package Manifest selbst validiert. Das tut diese Version gerade nicht.

### C. Tatsächliche SDK-/CRT-Payloads nicht erneut in VoiceSTT duplizieren

xwin liest die Paketliste aus dem von VoiceSTT verifizierten Package Manifest.

Die einzelnen ausgewählten SDK-/CRT-Payloads enthalten dort SHA-256-Werte; xwin reicht diese beim eigentlichen Download an seinen `get_and_validate(..., Some(payload.sha256), ...)`-Pfad weiter.

Daher:

- Package Manifest explizit durch VoiceSTT verifizieren;
- darin enthaltene Payload-Hashes weiterhin durch xwin verwenden;
- nicht 11 SDK-/CRT-Payload-Hashes redundant in `buildinputs.py` kopieren.

### D. Keine Vendor-Datei von 18 MB ins Repository aufnehmen

Weder das 17.9-MB-vsman noch die SDK-/CRT-Pakete in VoiceSTT committen.

Der Build darf die exakt deklarierten Quellen herunterladen, muss aber bei abweichenden Bytes hart fehlschlagen.

---

# 5. Finding M — Dependency Closure klassifizieren

Phase 1 hat für die übrigen real beobachteten Windows-Build-Dependencies bereits Hash-Verifikation nachgewiesen.

Erzeuge jetzt:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4A-C4\07_WINDOWS_DEPENDENCY_CLOSURE.md
```

Klassifiziere mindestens:

```text
kaldi-native-fbank
kissfft
kaldi-decoder
kaldifst
openfst
eigen
onnxruntime
simple-sentencepiece
websocketpp
asio
cppjieba
hclust_cpp
pybind11
xwin binary
xwin channel manifest
xwin package manifest
Windows SDK/CRT payloads
```

Erlaubte Status:

```text
CLOSED_BY_PINNED_UPSTREAM
CLOSED_BY_VOICESTT_AUTHORITY
```

Erwartete Einstufung nach Phase-1-Fakten:

- `kaldi-native-fbank` → CLOSED_BY_PINNED_UPSTREAM
- `kissfft` → CLOSED_BY_PINNED_UPSTREAM
- `kaldi-decoder` → CLOSED_BY_PINNED_UPSTREAM
- `kaldifst` → CLOSED_BY_PINNED_UPSTREAM
- `eigen` → CLOSED_BY_PINNED_UPSTREAM
- `onnxruntime` → CLOSED_BY_PINNED_UPSTREAM
- `simple-sentencepiece` → CLOSED_BY_PINNED_UPSTREAM
- `websocketpp` → CLOSED_BY_PINNED_UPSTREAM
- `asio` → CLOSED_BY_PINNED_UPSTREAM
- `cppjieba` → CLOSED_BY_PINNED_UPSTREAM
- `hclust_cpp` → CLOSED_BY_PINNED_UPSTREAM
- `pybind11` → CLOSED_BY_PINNED_UPSTREAM
- `openfst` → CLOSED_BY_VOICESTT_AUTHORITY (zusätzlich upstream gehasht)
- `xwin binary` → CLOSED_BY_VOICESTT_AUTHORITY
- `xwin channel manifest` → CLOSED_BY_VOICESTT_AUTHORITY nach dieser Phase
- `xwin package manifest` → CLOSED_BY_VOICESTT_AUTHORITY nach dieser Phase
- `Windows SDK/CRT payloads` → CLOSED durch:
  1. von VoiceSTT verifiziertes exaktes Package Manifest,
  2. explizite SDK-/CRT-Auswahl,
  3. xwin-Payload-downloads mit den SHA-256-Werten des verifizierten Package Manifests.

Wenn du bei einem Eintrag objektiv feststellst, dass diese Erwartung nicht stimmt:
- nicht improvisieren;
- in `PHASE2_STATE.md` `DEPENDENCY_CLOSURE: BLOCKED` setzen;
- genaue Datei/Codepfad nennen;
- danach stoppen.

---

# 6. Patch-/Builder-Revision

Diese Änderung verändert real den generierten Windows Builder-Patch.

Daher:

```text
PATCH_SET_REVISION: 2 -> 3
```

`BUILDER_REVISION` soll **4 bleiben**, sofern du nicht außerhalb der bestehenden Patch-Surface eine buildwirksame Builderfunktion ändern musst.

Warum:

- xwin Manifest-/SDK-/CRT-Werte sind eigenständige Fingerprint-Inputs;
- der geänderte Dockerfile-Output gehört zur Patch-Surface;
- die Checkout-/Source-Authority-Builderlogik aus C3 ändert sich nicht.

Falls du glaubst, `BUILDER_REVISION` müsse trotzdem geändert werden:
- nicht eigenmächtig ändern;
- in Evidence begründen und `STATUS: BLOCKED` melden.

## 6.1 Guard

Die bestehende Patch-Guard-Surface muss die buildwirksame xwin-Patchlogik vollständig abdecken.

Wenn du eine neue Helper-Funktion für den xwin-Patch einführst:
- diese Helper-Funktion in die Patch-Guard-Surface aufnehmen;
- `EXPECTED_PATCH_SOURCE_DIGEST` erst nach finalem Codezustand neu berechnen;
- Guard nicht schwächen.

Negativtest:

```text
simulierte buildwirksame Änderung im xwin-Patch
→ Guard RED

Restore
→ Guard GREEN
```

---

# 7. Finding N — Lookup-Race exakt schließen

Aktuelles Problem:

```text
Reader:
_verify_slot_dir(final) -> MISS

Writer:
final -> backup
staging -> final
backup cleanup

Reader:
replaced_backups() -> []
return alter MISS
```

## 7.1 Verbindliche Implementierung

Ändere `KrokoArtifactStore.lookup()` semantisch auf folgenden Ablauf:

```python
record, problems = self._verify_slot_dir(
    self.slot_dir(variant, fingerprint),
    variant=variant,
    fingerprint=fingerprint,
    inputs=inputs,
)

# Gesunder Hit bleibt vollständig lock-frei.
if record is not None:
    return record, problems

# store() benutzt recover=False bereits innerhalb des Slot-Locks.
if not recover:
    return record, problems

# Nur der MISS-Pfad wird stabilisiert.
with self._slot_lock(variant, fingerprint):
    self._recover_slot_locked(
        variant,
        fingerprint,
        inputs,
    )
    return self._verify_slot_dir(
        self.slot_dir(variant, fingerprint),
        variant=variant,
        fingerprint=fingerprint,
        inputs=inputs,
    )
```

Die tatsächliche Formatierung darf zum Code passen.

Wichtig:

- Kein vorheriges ungesperrtes `replaced_backups()` mehr als Entscheidung, ob ein initialer MISS sofort zurückgegeben wird.
- Jeder normale gesunde HIT bleibt lock-frei.
- Jeder `recover=True` MISS wird unter demselben Slot-Lock nochmals stabil beurteilt.
- `_recover_slot_locked()` entscheidet weiterhin:
  - valid final → stale backups cleanup;
  - missing final + valid backup → restore;
  - corrupt final → nicht überschreiben.
- `recover=False` bleibt erhalten, damit `store()` innerhalb seines bereits gehaltenen Locks keinen Lock rekursiv nimmt.
- `recover_slot()` nicht unnötig entfernen; bestehende API/Tests erhalten.

---

# 8. Finding N — deterministischer Concurrency-Test

In:

```text
tests/unit/test_kroko_artifact_store.py
```

einen gezielten Regressionstest ergänzen.

Der Test muss mit `threading.Event`, Barrier oder gleichwertigen deterministischen Synchronisationspunkten exakt beweisen:

1. gültiger final-Slot existiert;
2. Writer hält den Slot-Lock;
3. Writer führt `final -> backup` aus;
4. Writer wird exakt dort angehalten;
5. Reader startet `lookup(recover=True)`;
6. Reader sieht initial `final` als fehlend und muss anschließend am Slot-Lock warten;
7. Writer darf weiterlaufen:
   - `staging -> final`
   - Backup cleanup
   - Lock release
8. Reader erwirbt danach Lock;
9. Reader revalidiert;
10. Reader liefert gültigen ArtifactRecord;
11. Reader liefert **keinen MISS**.

Zusätzlich:

- Timeout verwenden, damit kein Test hängen kann.
- Thread-Exceptions sicher an Hauptthread zurückreichen.
- Nach Test keine Backup-/Staging-Leichen.
- bestehende Crash-/Recovery-/Concurrent-Store-/Force-Rebuild-Tests nicht verändern.

## 8.1 Cheap-Hit-Regression

Bestehenden Test verwenden oder ergänzen:

```text
gesunder final-Slot
→ lookup()
→ kein _slot_lock-Aufruf
```

Keinen Timing-Test als alleinigen Nachweis verwenden; direkt Lock-Aufruf zählen/patchen.

---

# 9. Retention-Fixture ausschließlich testseitig korrigieren

Datei:

```text
tests/unit/test_fastapi_server_multi_user.py
```

Test:

```text
FastAPIMultiUserWebSocketTests.test_admin_replay_reports_retention_gap
```

Nur die Fixture ändern, die ausdrücklich **innerhalb** des 30-Tage-Fensters bleiben soll:

```text
retention-transcription-session-b
```

Die beiden absichtlich alten `2020-01-01`-Events bleiben unverändert.

## 9.1 Umsetzung

Importiere testseitig:

```python
from datetime import datetime, timedelta, timezone
```

Erzeuge den `session-b`-Timestamp relativ zur Testlaufzeit mit einem deutlichen Sicherheitsabstand, z. B.:

```python
inside_retention_timestamp = (
    datetime.now(timezone.utc) - timedelta(days=1)
).isoformat(timespec="milliseconds").replace("+00:00", "Z")
```

und verwende diesen statt:

```text
2026-08-02T00:00:00.000Z
```

Damit bleibt das Event an jedem Kalenderdatum innerhalb des 30-Tage-Fensters.

Keine Produktdatei dafür ändern.

## 9.2 Future-clock-Proof

Füge einen kleinen **test-only** Regressionstest/Helper hinzu, der die Fixture-Erzeugung gegen mindestens zwei Referenzzeitpunkte beweist:

```text
2026-09-01
2036-09-01
```

Der Test soll beweisen:

```text
generated_inside_timestamp > reference_now - 30 days
generated_inside_timestamp < reference_now
```

Bevorzugt eine kleine test-only Helper-Funktion, damit der eigentliche WebSocket-Test und der Future-Proof **dieselbe** Timestamp-Erzeugungslogik verwenden.

Beispielsemantik:

```python
def _inside_retention_timestamp(now):
    return (
        now - timedelta(days=1)
    ).isoformat(timespec="milliseconds").replace("+00:00", "Z")
```

Dann:

```python
inside_retention_timestamp = _inside_retention_timestamp(
    datetime.now(timezone.utc)
)
```

und separater Test mit festen zukünftigen `now`-Werten.

Keine Production-Time-Injection nur für diesen Test einführen.

---

# 10. Gezielte Tests für Finding L/M

In:

```text
tests/unit/test_kroko_fingerprint.py
```

die bestehende C3-Windows-Toolchain-Testklasse erweitern bzw. eine eng benannte C4-Klasse ergänzen.

Mindestens beweisen:

## 10.1 Declaration

- Channel Manifest URL vorhanden.
- Channel Manifest Bytes vorhanden.
- Channel Manifest SHA exakt.
- Package Manifest URL vorhanden.
- Package Manifest Cache-Key vorhanden.
- Package Manifest Bytes vorhanden.
- Package Manifest echter SHA exakt.
- SDK-Version exakt `10.0.26100`.
- CRT-Version exakt `14.44.17.14`.

## 10.2 Fingerprint-Invalidation

Jeweils einzeln ändern und beweisen, dass Windows Toolchain Authority / Fingerprint sich ändert:

- Channel Manifest SHA
- Channel Manifest URL
- Package Manifest SHA
- Package Manifest URL
- Package Manifest Cache-Key
- SDK-Version
- CRT-Version

## 10.3 Generated Dockerfile

Beweisen:

- Channel Manifest wird explizit heruntergeladen.
- Channel Manifest SHA wird vor xwin geprüft.
- Channel Manifest Bytezahl wird geprüft.
- Package Manifest wird explizit heruntergeladen.
- Package Manifest echter SHA `3891...` wird vor xwin geprüft.
- Package Manifest Bytezahl wird geprüft.
- xwin erhält `--cache-dir /tmp/.xwin-cache`.
- xwin erhält `--manifest .../manifest_17.json`.
- xwin erhält `--sdk-version 10.0.26100`.
- xwin erhält `--crt-version 14.44.17.14`.
- kein availability/latest-Fallback.
- keine zweite ungesicherte xwin-splat-Zeile.

## 10.4 Offline-Gate

Bestehender Offline-Test bleibt grün:

```text
fingerprint_for()
describe_artifact()
```

dürfen wegen der neuen Werte **keine** Netzwerk-/Docker-/Subprocess-Probe benötigen.

## 10.5 Negative Pin Proof

Die Unit-Tests sollen mindestens beweisen:

- falscher Channel-Manifest-SHA würde die generierte `sha256sum -c`-Prüfung scheitern lassen;
- falscher Package-Manifest-SHA ebenso;
- fehlender Upstream-Anker für den xwin-Block → `KrokoInstallError`, kein stiller Fallback.

Dafür kein realer Netzwerkzugriff erforderlich.

---

# 11. In dieser Phase ausdrücklich NICHT ausführen

Noch nicht:

```text
kein nativer Kroko-Build
kein docker build
kein xwin download gegen das Netz
keine Full Regression
kein Artifact-Requalification
kein Commit
kein Push
```

Gezielte Unit-/Regressionstests sind erlaubt und erforderlich.

Das vorhandene C3-Builder-Image nicht löschen oder verändern.

Das vorhandene C3-Artifact nicht löschen oder verschieben.

---

# 12. Erlaubte Source-/Test-Dateien

Erwarteter Scope:

```text
VoiceSTT/kroko/buildinputs.py
VoiceSTT/install_kroko.py
VoiceSTT/kroko/artifacts.py
tests/unit/test_kroko_fingerprint.py
tests/unit/test_kroko_artifact_store.py
tests/unit/test_fastapi_server_multi_user.py
```

Optional:

```text
docs/engines/kroko-onnx.md
```

aber nur wenn die bestehende C3-Doku sonst nach dieser Änderung sachlich falsch wäre.

Keine weiteren Produktbereiche.

---

# 13. Targeted Test Gate

Nach Implementierung mindestens:

```text
python -m pytest -q tests/unit/test_kroko_fingerprint.py
python -m pytest -q tests/unit/test_kroko_artifact_store.py
python -m pytest -q tests/unit/test_fastapi_server_multi_user.py -k "retention_gap or retention"
```

Danach die komplette bestehende Kroko-W4A-Testgruppe:

```text
python -m pytest -q \
  tests/unit/test_kroko_fingerprint.py \
  tests/unit/test_kroko_artifact_store.py \
  tests/unit/test_kroko_onnx_engine.py \
  tests/unit/test_kroko_model_authority.py \
  tests/unit/test_install_kroko_cpu.py
```

Unter Windows die vorhandene PowerShell-/pytest-Syntax entsprechend korrekt verwenden.

Falls `Temp\pytest-of-marco` weiterhin unlesbar ist, darf der bereits dokumentierte eigene `--basetemp` außerhalb des Worktrees verwendet werden.

Keine neue persistente venv.

Zusätzlich:

```text
git diff --check
```

---

# 14. Evidence Phase 2

Alle Dateien weiterhin nach:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4A-C4\
```

Erzeuge:

## `07_WINDOWS_DEPENDENCY_CLOSURE.md`

Wie in §5.

## `08_PHASE2_IMPLEMENTATION_REPORT.md`

Enthält:

- geänderte Dateien
- Finding L konkrete Lösung
- Package-Manifest-Sonderfall
- Finding M Closure
- Finding N konkrete Lösung
- Retention-Testkorrektur
- PATCH_SET_REVISION vorher/nachher
- BUILDER_REVISION vorher/nachher
- Guard-Surface vorher/nachher
- keine Native-/Docker-Builds

## `09_PHASE2_TEST_REPORT.md`

Enthält:

- exakte Commands
- Ergebnisse
- neue Tests
- bestehende relevante Tests
- Guard-Negativproof
- `git diff --check`
- eventuelle skips mit Begründung

## `PHASE2_STATE.md`

Exaktes Schema:

```text
START_GATE: PASS|BLOCKED

FINDING_L_IMPLEMENTED: YES|NO
XWIN_CHANNEL_MANIFEST_PINNED: YES|NO
XWIN_PACKAGE_MANIFEST_PINNED: YES|NO
XWIN_SDK_PINNED: YES|NO
XWIN_CRT_PINNED: YES|NO

DEPENDENCY_CLOSURE: PASS|BLOCKED
OPEN_BUILD_DEPENDENCIES_REMAINING: 0|<count>

FINDING_N_IMPLEMENTED: YES|NO
LOOKUP_RACE_TEST: PASS|FAIL
HEALTHY_HIT_LOCK_FREE_TEST: PASS|FAIL

RETENTION_FIXTURE_FIXED: YES|NO
RETENTION_CURRENT_DATE_TEST: PASS|FAIL
RETENTION_FUTURE_DATE_TEST: PASS|FAIL

PATCH_SET_REVISION: <value>
BUILDER_REVISION: <value>
PATCH_GUARD_NEGATIVE_PROOF: PASS|FAIL

TARGETED_TESTS: PASS|FAIL
KROKO_W4A_TEST_GROUP: PASS|FAIL
GIT_DIFF_CHECK: PASS|FAIL

NATIVE_BUILD_STARTED: NO
DOCKER_BUILD_STARTED: NO
FULL_REGRESSION_STARTED: NO
ARTIFACT_REQUALIFICATION_STARTED: NO

GIT_COMMIT_CREATED: NO
GIT_PUSH_PERFORMED: NO
```

---

# 15. Harte Stop-Regel

Nach erfolgreicher Phase 2:

```text
STOP
```

Keine Artifact-Requalification.
Kein Native-Build.
Keine Full Regression.
Kein Commit.
Kein Push.

Die Änderungen bleiben bewusst uncommitted im `work/AP-SRV-070`-Worktree, damit anschließend ein externer Review der konkreten Diff-/Test-Evidence erfolgt.

---

# 16. Abschlussantwort

Nur:

```text
PHASE 2 COMPLETE

FINDING_L_IMPLEMENTED: <YES|NO>
DEPENDENCY_CLOSURE: <PASS|BLOCKED>
OPEN_BUILD_DEPENDENCIES_REMAINING: <count>
FINDING_N_IMPLEMENTED: <YES|NO>
RETENTION_FIXTURE_FIXED: <YES|NO>
TARGETED_TESTS: <PASS|FAIL>
KROKO_W4A_TEST_GROUP: <PASS|FAIL>

Evidence:
- 07_WINDOWS_DEPENDENCY_CLOSURE.md
- 08_PHASE2_IMPLEMENTATION_REPORT.md
- 09_PHASE2_TEST_REPORT.md
- PHASE2_STATE.md

Changed files:
- <Liste>

Blocker:
- <keine oder kurz>

STOPPED BEFORE:
- native build
- artifact requalification
- full regression
- commit
- push
```
