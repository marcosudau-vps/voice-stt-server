# VoiceSTT Server V2 — Abschluss-Masterplan / Handoff
## Stand nach AP-SRV-070 W4AB-C1

**Stand:** 2026-09-05
**Projekt:** `marcosudau-vps/voice-stt-server`
**Zweck:** Vollständiger Übergabe-, Restarbeits- und Releaseplan für die Server-V2-Linie.
**Geltungsbereich:** **nur Server**. Der Client ist ausdrücklich nicht Teil dieses Dokuments.

---

# 0. Executive Summary

Der fachliche Server-V2-Umbau ist weitgehend abgeschlossen. Die wesentlichen Architekturpakete AP-SRV-010 bis AP-SRV-060 sind bereits kanonisch abgeschlossen. AP-SRV-070 hat inzwischen zusätzlich Legacy-Cleanup, Packaging, Kroko-Productization und STT-Model-Management umgesetzt.

Der aktuell veröffentlichte **Distributed-Stand** enthält den abgeschlossenen kombinierten W4A/W4B-Korrekturlauf:

```text
PARENT:
319ce3f29db302795beb767be910fe1aeb8609d6

FINAL W4AB-C1 COMMIT:
b2ec1657d40b4015cf8cf92c17eef1371b127b78

TREE:
a26f17a83aeff9743ad40950e12699c47ac3edf4

DISTRIBUTED:
b2ec1657d40b4015cf8cf92c17eef1371b127b78

CANONICAL:
c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
```

W4AB-C1 ist auf Windows vollständig grün:

```text
1513 passed
14 skipped
974 subtests passed
0 failed
0 errors

compileall: PASS
git diff --check: PASS
secret scan: PASS
scope gate: PASS
```

Die Findings A–J sind `IMPLEMENTED / TESTED / PASS`.

**Noch nicht begonnen:** W4C Production Deployment.

**Noch real auszuführen:** Hermes/Ubuntu-Requalification des finalen W4AB-C1-Commits.

Danach ist der verbleibende Weg:

```text
Hermes Ubuntu Requalification
        ↓
W4C Production Docker / Deployment
        ↓
W5 Release Candidate Qualification
        ↓
Final Root-PASS AP-SRV-070
        ↓
Canonical AP-SRV-070 Close
        ↓
W6 Release Preparation / Publication
        ↓
Fresh External Verification
        ↓
SERVER V2 RELEASE COMPLETE
```

---

# 1. Autoritativer Git- und Governance-Vertrag

## 1.1 Zwei-Ebenen-Historie

Die Server-Initiative verwendet weiterhin zwei getrennte Linien:

### Distributed

```text
feat/einheitliche-triggerarchitektur-distributed
```

Zweck:

- ein Commit pro abgeschlossenem Agenten-/Korrekturlauf;
- lineare, nachvollziehbare Run-Historie;
- keine History-Rewrites;
- kein Force-Push;
- neue Runs nur per Fast-Forward.

Aktueller Stand:

```text
b2ec1657d40b4015cf8cf92c17eef1371b127b78
```

### Canonical

```text
feat/einheitliche-triggerarchitektur
```

Zweck:

- genau ein kanonischer Gesamtcommit pro Root-abgenommenem AP;
- bleibt während AP-SRV-070 bewusst unverändert;
- wird erst nach finalem Root-PASS von AP-SRV-070 aktualisiert.

Aktueller Stand:

```text
c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
```

Das ist weiterhin der kanonische Abschluss von AP-SRV-060.

## 1.2 Bis zum finalen Root-PASS verboten

- Canonical vorzeitig aktualisieren;
- Distributed umschreiben;
- Rebase/Amend bereits veröffentlichter Run-Commits;
- Force-Push;
- Release-Tag erzeugen;
- PyPI/GHCR/Docker-Hub-Publish;
- GitHub Release erzeugen.

---

# 2. Was fachlich bereits abgeschlossen ist

## 2.1 AP-SRV-010 bis AP-SRV-060

Diese Pakete gelten als bereits Root-abgeschlossen und sollen ohne konkreten reproduzierbaren Defekt **nicht erneut grundsätzlich auditiert** werden.

Enthalten sind insbesondere:

- Server-/Session-Grundarchitektur;
- serverautoritativer Activation-/Trigger-Lifecycle;
- Commands und Timer;
- Protocol v2;
- Settings-Control-Plane;
- Logging/Event-/Replay-/Retention-Grundlagen;
- Wake-Word-Katalog, Detection und Assets;
- negative v1/v2-Protokollgrenzen;
- relevante Legacy-Kompatibilitätsanker.

## 2.2 AP-SRV-070 W1/W2

Abgeschlossen:

- Dead-Code-/Legacy-Cut;
- Wake-Katalog-Migration;
- Protocol-Boundary-Hardening;
- Repository-/Doku-Hygiene;
- stale Wake-Generatoren bereinigt;
- kanonischer Wake-Asset-Generator gehärtet.

## 2.3 AP-SRV-070 W3

Abgeschlossen:

- zentrale Versionsautorität;
- Python-Wheel/sdist-Produktisierung;
- Package-Assets;
- Wake-Word-Assets im Distribution-Paket;
- Isolated-Install-/Packaging-Gates;
- Basis für späteren Release-Workflow.

## 2.4 AP-SRV-070 W4A — Kroko Artifact/Productization

Abgeschlossen wurden u. a.:

- persistenter Kroko-Artifact-Store;
- Free-/Pro-Varianten;
- Build-Fingerprint;
- Windows-/Linux-Toolchain-Authority;
- SHA-/Wheel-/ABI-/Platform-Prüfung;
- Reuse-by-default;
- expliziter Rebuild;
- Secret-Grenzen im Buildpfad;
- crash-/race-resistenter Store;
- Free/Pro-Koexistenz;
- Artifact-Retention/GC;
- Linux `1free`/`1pro` Wheel-Tagging;
- OpenSSL-Development-Identity im Linux-Fingerprint.

## 2.5 AP-SRV-070 W4B — STT Model Management

Der W4B-Stand ist bereits implementiert und durch W4AB-C1 korrigiert/härtet worden.

Aktuell abgenommen sind insbesondere:

- STT Model Authority / Management;
- Engine-/Model-Intent;
- deterministische Kroko-Runtime-Variante;
- Key ist nur Runtime-Credential und **kein** Lizenz-/Varianten-Entscheider;
- resolved-engine-spezifische Options;
- Secret-Redaction;
- Model-PATCH ohne überraschenden großen Download;
- expliziter `POST /api/models/refresh`;
- transaktionale Refresh-Semantik;
- LKG-Erhalt bei Fehler;
- Pending/Refresh-Required-Semantik.

---

# 3. W4AB-C1 — finaler aktueller Stand

## 3.1 Findings A–J

| Ref | Thema | Stand |
|---|---|---|
| A | Linux variant tagging | PASS |
| B | Linux OpenSSL/toolchain fingerprint | PASS |
| C | Free+Pro coexistence | PASS |
| D | Artifact retention/GC | PASS |
| E | Key != license/runtime authority | PASS |
| F | deterministic runtime variant | PASS |
| G | resolved-engine options | PASS |
| H | secret boundary | PASS |
| I | refresh semantics | PASS |
| J | cross-platform wheel fixtures | PASS |

## 3.2 Verbindliche fachliche Details

### Kroko Linux Wheel

Free:

```text
...-1free-cp312-cp312-linux_x86_64.whl
```

Pro:

```text
...-1pro-cp312-cp312-linux_x86_64.whl
```

Dateiname und interne `*.dist-info/WHEEL`-Metadaten müssen denselben Build-Tag tragen. `RECORD` bleibt konsistent.

### Runtime-Variante

Precedence:

```text
STT Engine Settings
→ Final Engine Options
→ Realtime Engine Options
→ VOICESTT_KROKO_VARIANT
→ Default free
```

`pro` nur explizit.

Ein vorhandener Key darf niemals automatisch auf `pro` hochschalten.

### Secret Boundary

Kroko-Credentials dürfen nicht im Klartext erscheinen in:

- `/api/config`;
- `/api/models`;
- Model-Management-/Status-Daten;
- Health;
- Audit Events;
- persistierter Runtime Config;
- Exceptions/Rollback-Diagnostik;
- Run-Metadaten.

### Model-Refresh

Settings-PATCH:

- übernimmt/persistiert Operator-Intent;
- startet nicht allein überraschend einen großen Model-Download;
- markiert `modelRefreshRequired`/Pending.

`POST /api/models/refresh`:

- übernimmt neuen Intent;
- führt Discovery/Recovery/Provisioning aus;
- ist transaktional;
- erhält bei Fehlern den letzten guten Zustand.

---

# 4. Noch offen — Phase H: Hermes / Ubuntu Requalification

## 4.1 Zweck

Dies ist **kein neuer Entwicklungsblock**, sondern reale Linux-Abnahme des finalen W4AB-C1-Commits.

Verbindlicher Commit:

```text
b2ec1657d40b4015cf8cf92c17eef1371b127b78
```

## 4.2 Muss nachgewiesen werden

1. Checkout exakt dieses Commits.
2. Ubuntu/Linux Development Dependencies vorhanden.
3. Linux-Fingerprint enthält echte OpenSSL-Development-Authority.
4. Genau ein nativer **Free**-Build.
5. Wheel-Dateiname enthält `1free`.
6. Internes `WHEEL` enthält `Build: 1free`.
7. Artifact Store akzeptiert das Wheel.
8. Zweiter identischer Aufruf ist **REUSE**, kein Native-Build.
9. Disposable venv kann Wheel installieren.
10. `import kroko_onnx` funktioniert.
11. Free positiv.
12. Pro gegen Free-Wheel negativ.
13. Kleiner VoiceSTT/Kroko-Smoke.
14. Targeted Linux-Tests 0 failures.
15. Repo-Hygiene sauber.

## 4.3 Vorgesehene Hermes-Kommandos

```bash
cd /opt/voice-stt-server
git fetch origin
git checkout b2ec1657d40b4015cf8cf92c17eef1371b127b78
git status

sudo apt-get update
sudo apt-get install -y cmake g++ libssl-dev pkg-config python3-dev
pkg-config --modversion openssl

python3 VoiceSTT/install_kroko.py --print-fingerprint

python3 VoiceSTT/install_kroko.py --variant free --rebuild-kroko

STORE_DIR="${VOICESTT_KROKO_ARTIFACT_STORE:-$HOME/.cache/voicestt/kroko-artifacts}"
ls -la "$STORE_DIR/free"/*/*.whl
unzip -p "$STORE_DIR/free"/*/*.whl "*.dist-info/WHEEL" | grep "Build: 1free"

python3 VoiceSTT/install_kroko.py --describe-artifact
python3 VoiceSTT/install_kroko.py --variant free

TEST_VENV=$(mktemp -d /tmp/kroko-venv-XXXXXX)
python3 -m venv "$TEST_VENV"
"$TEST_VENV/bin/pip" install "$STORE_DIR/free"/*/*.whl
"$TEST_VENV/bin/python" -c "import kroko_onnx; print('kroko_onnx import ok')"

python3 VoiceSTT/install_kroko.py --describe-artifact --variant pro

"$TEST_VENV/bin/python" -c "
import VoiceSTT
from VoiceSTT.kroko import artifacts, buildinputs, fingerprint
print('VoiceSTT kroko modules ok')
"

python3 -m pytest -q \
  tests/unit/test_install_kroko_cpu.py \
  tests/unit/test_kroko_artifact_store.py \
  tests/unit/test_kroko_fingerprint.py

rm -rf "$TEST_VENV"
```

## 4.4 Entscheidungsregel

Wenn Hermes einen **realen Linux-Correctness-/Runtime-/Security-Fehler** findet:

- enger Linux-Korrekturlauf;
- targeted Tests;
- Full Unit nur wenn Produktcode geändert wurde;
- genau ein neuer Distributed-Commit.

Wenn Hermes nur zusätzliche theoretische Härtungsmöglichkeiten findet:

- kein Blocker;
- Post-V2-Hardening-Backlog;
- W4C darf weiterlaufen.

---

# 5. Noch offen — Phase W4C: Production Docker / Deployment

## 5.1 Ziel

Aus dem inzwischen paketierbaren Server und den qualifizierten Kroko-/Model-Authorities ein **wirklich produktionsfähiges Ubuntu-Deployment** machen.

W4C ist der letzte größere Implementierungsblock vor der Release-Qualification.

## 5.2 Dockerfile

Verbindliches Zielbild:

```text
Source
  ↓
Builder Stage
  ↓
VoiceSTT Wheel
  ↓
Runtime Stage
  ↓
pip install <wheel>
  ↓
Production Runtime
```

Hard Requirements:

- Multi-Stage-Build;
- kein Editable Install;
- kein `pip install -e`;
- kein Source-Checkout als Runtime-Abhängigkeit;
- finaler Container konsumiert das gebaute VoiceSTT-Wheel;
- unprivilegierter Runtime-User;
- Healthcheck;
- sauberer SIGTERM-/Shutdown-Pfad;
- OCI-Labels;
- Version/Commit nachvollziehbar;
- keine Build-Secrets in Image-Layern;
- kein Kroko-Key im Build;
- Kroko-Artifact wird konsumiert, **nicht beim normalen Containerstart kompiliert**.

## 5.3 Kroko in Production

- Free/Pro Runtime bleibt explizit.
- Default bleibt `free`.
- `pro` nur explizit.
- Pro-Credential ausschließlich Runtime-Secret.
- kein Key in:
  - Image;
  - Layer;
  - Labels;
  - Fingerprint;
  - Buildcache;
  - Logs;
  - Metadaten.

W4C soll die bereits implementierte Runtime-Variant-Authority **nur verdrahten**, nicht neu erfinden.

## 5.4 STT Model Store

Große STT-Modelle bleiben externe persistente Assets.

Geplantes Modell:

```text
<runtime>/models/stt/fasterwhisper
<runtime>/models/stt/kroko_asr
```

Custom Model Paths bleiben primäre Discovery-Quellen.

Read-only Custom Paths sind zulässig.

Wenn Provisioning erforderlich ist:

- writable bevorzugtes Model-Dir verwenden;
- andernfalls Default Runtime Model Store;
- temporär `.part`/Staging im Zielverzeichnis;
- Verify;
- Atomic Rename;
- kein separates permanentes Download-Cache-System.

## 5.5 Compose

Zu prüfen/aktualisieren:

```text
docker-compose.yml
build/vps/docker-compose.yml
```

Deployment muss u. a. korrekt verdrahten:

- Runtime Data Root;
- Model Volumes;
- Kroko Artifact Store / konsumierbares Artifact;
- ggf. Secret Mounts;
- Healthcheck;
- Restart-Verhalten;
- Ports;
- Offline-/Download-Verhalten;
- Free/Pro Runtime-Konfiguration.

## 5.6 W4C Acceptance Gates

Mindestens:

1. `docker build` erfolgreich.
2. Runtime-Image enthält kein Source-/Editable-Install.
3. Prozess läuft non-root.
4. OCI Version + Commit stimmen.
5. Healthcheck wird grün.
6. Server startet.
7. `/health` bzw. kanonischer Health-Endpunkt grün.
8. `/ws/v2` Handshake möglich.
9. Wake-Word-Assets verfügbar.
10. STT Model Management startet ohne Crash-Loop.
11. fehlendes Modell führt zu administrierbarem `NOT_READY`, nicht zu Restart-Loop.
12. persistente Daten/Modelle über Container-Recreate erhalten.
13. SIGTERM beendet sauber.
14. kein Secret-Leak.
15. Kroko startet ohne Native-Rebuild im normalen Production-Startpfad.

---

# 6. Noch offen — Phase W5: Release Candidate Qualification

## 6.1 Grundsatz

W5 ist **keine neue Architekturphase**.

In W5 wird nichts „noch schöner“ gemacht.

W5 beantwortet nur:

> Ist der exakte Release Candidate als Gesamtprodukt funktionsfähig und veröffentlichbar?

## 6.2 Freeze

Vor W5:

```text
RC_COMMIT = exakt festlegen
```

Alle Tests, Package-Builds, Docker-Builds und Smokes referenzieren denselben Commit.

Kein weiterer Feature-Scope während W5.

## 6.3 Testmatrix

### A. Python / Unit

```text
python -m pytest -q tests/unit
```

0 failures / 0 errors.

Zusätzlich explizit:

- Protocol v1/v2 Boundary;
- Protocol v2 Contract;
- Settings;
- Wake Word;
- Model Management;
- Kroko;
- Multi-User;
- Scheduler/ASR Integration.

### B. Packaging

- Wheel bauen;
- sdist bauen;
- Hashes berechnen;
- `twine check` bzw. äquivalenter Package-Metadata-Check;
- frische disposable venv;
- Installation aus Wheel;
- Import;
- Serverstart;
- Package-Assets;
- Wake-Word-Katalog;
- keine unerwarteten Runtime-Downloads.

### C. Kroko

- qualifiziertes Windows-Verhalten bereits vorhanden;
- Hermes/Linux-Proof vorhanden;
- Artifact Store Lookup;
- REUSE;
- Free-/Pro-Mismatch negativ;
- keine Secrets.

### D. Production Docker

- exaktes RC-Image bauen;
- Start;
- Health;
- non-root;
- OCI-Metadata;
- Model-/Data-Persistenz;
- Restart/Recreate;
- SIGTERM;
- kein Native Kroko Build beim normalen Start.

### E. Live Server E2E

Mindestens:

```text
start server
→ /ws/v2 hello
→ hello.accepted
→ Session
→ Streaming Audio
→ Events / transcription path
→ sauber schließen
→ Server SIGTERM
→ clean shutdown
```

### F. Negative / Security

- v1/v2 Cross-Transport bleibt isoliert;
- ungültige Session IDs negativ;
- falsche Wheel-Plattform negativ;
- Kroko Variant mismatch negativ;
- Secret Scan;
- keine Credentials in Config/Health/Models/Audit/Persistenz;
- keine fremden Build-/Temp-Artefakte.

## 6.4 W5 Hard Gate

Nur zwei Ergebnisse:

```text
W5 PASS
```

oder

```text
W5 BLOCKED
```

Keine Veröffentlichung bei `BLOCKED`.

## 6.5 Wichtig

Während W5:

- kein Tag;
- kein PyPI;
- kein GHCR;
- kein Docker Hub;
- kein GitHub Release.

So wird verhindert, dass bereits eine Versionsnummer / ein immutable Tag verbraucht wird, bevor alle vorhersehbaren Fehler gefunden sind.

---

# 7. Final Root-PASS AP-SRV-070

Nach W5 PASS erfolgt ein finaler Root-Review.

Review-Schwelle:

Blockierend sind nur realistische:

- Correctness-Fehler;
- Security-/Secret-Leaks;
- Datenverlust;
- Runtime-/Deployment-Fehler;
- Release-Blocker;
- klare Contract-Verletzungen.

**Nicht blockierend:**

- rein theoretische Supply-Chain-Härtung;
- kosmetische Refactorings;
- alternative Architekturen ohne realen Defekt;
- zusätzliche Tests ohne konkrete Risikohypothese;
- „könnte noch eleganter sein“.

Ziel ist ein eindeutiges:

```text
AP-SRV-070 ROOT PASS
```

---

# 8. Canonical Close von AP-SRV-070

Erst nach Root PASS.

## 8.1 Ziel

Canonical bekommt genau **einen** AP-SRV-070-Gesamtabschluss.

Der resultierende kanonische Tree muss exakt dem Root-abgenommenen finalen Server-Tree entsprechen.

Distributed bleibt mit seiner vollständigen Run-Historie erhalten.

## 8.2 Invarianten

```text
TREE(Canonical AP-SRV-070)
==
TREE(finaler Root-PASS Distributed Stand)
```

Keine Distributed-History wird gesquasht oder umgeschrieben.

Canonical und Distributed erfüllen unterschiedliche Zwecke:

```text
Canonical   = ein sauberer AP-Abschluss
Distributed = vollständige Agenten-/Korrekturprovenienz
```

---

# 9. W6 — Release Preparation und Publication

## 9.1 Release-Ziel

W6 soll möglichst deterministisch und automatisiert sein.

Der Nutzer soll die Release-Version **nicht manuell verwalten oder erraten müssen**.

Bereits vorhandene zentrale Versionsautorität aus W3 ist die Basis.

## 9.2 Automatische Versionsbestimmung

Vor Veröffentlichung:

1. exakten Release-Commit bestimmen;
2. aktuelle Versionsautorität lesen;
3. nach verbindlicher Release-Policy nächste Version automatisch bestimmen;
4. alle daraus resultierenden Package-/Image-/Release-Versionen aus **einer** Authority ableiten;
5. Konsistenz prüfen;
6. erst danach Tagging zulassen.

Falls die endgültige automatische Increment-Policy noch nicht als Code vorliegt, wird sie in W6-Prep einmal implementiert und danach nicht mehr manuell bedient.

## 9.3 Preflight muss VOR dem Tag passieren

Der wichtigste Release-Vertrag:

```text
Preflight
    ↓
alles grün?
    ↓ JA
Version finalisieren
    ↓
Tag erzeugen
    ↓
Publish
```

Nicht:

```text
Tag erzeugen
    ↓
dann erst feststellen, dass Docker/Package kaputt ist
```

Preflight soll möglichst alles prüfen, was ohne irreversible Veröffentlichung prüfbar ist:

- clean exact commit;
- Canonical/Root-PASS-Invariante;
- Full Tests;
- Package build;
- package metadata check;
- Docker build;
- Container smoke;
- Health;
- artifact hashes;
- version consistency;
- registry credentials vorhanden;
- target repositories erreichbar;
- Release Notes vorhanden;
- keine Secrets;
- GitHub Actions / Release Workflow syntaktisch gültig.

## 9.4 Release-Artefakte

Mindestens:

### Python

```text
Wheel
sdist
SHA-256
PyPI
```

### Container

```text
Production Image
immutable version tag
commit traceability
GHCR
Docker Hub
```

### GitHub

```text
Git Tag
GitHub Release
Release Notes
Artifact references / hashes
```

## 9.5 Veröffentlichungsreihenfolge

Geplanter Ablauf:

```text
1. Preflight / RC Verification
2. Version Freeze
3. Immutable Git Tag
4. Python Artifacts → PyPI
5. Production Image → GHCR
6. Production Image → Docker Hub
7. GitHub Release als letzter Veröffentlichungsschritt
8. Fresh external verification
```

GitHub Release kommt bewusst zuletzt, weil es die öffentlich sichtbare „Release komplett“-Marke bildet.

## 9.6 Resume / Recovery

Release-Publishing muss **resumierbar** sein.

Beispiel:

```text
PyPI        = published
GHCR        = published
Docker Hub  = failed
GitHub      = not released
```

Dann:

- keine neue Version erfinden;
- keinen zweiten Tag erzeugen;
- bereits erfolgreiche irreversible Schritte erkennen;
- denselben Release-State fortsetzen;
- Docker Hub erneut versuchen;
- erst nach vollständigem Erfolg GitHub Release erzeugen.

Ein Release-State muss deshalb mindestens unterscheiden:

```text
PRECHECKED
TAGGED
PYPI_PUBLISHED
GHCR_PUBLISHED
DOCKERHUB_PUBLISHED
GITHUB_RELEASED
EXTERNAL_VERIFIED
COMPLETE
```

## 9.7 Keine Versionsverschwendung

Wenn ein Fehler **vor Tag/Publish** erkannt werden kann, muss er vor dem Tag erkannt werden.

Wenn ein externer Fehler **nach einem irreversiblen Publish** eintritt, wird derselbe Release fortgesetzt statt eine neue Versionsnummer zu verbrauchen.

---

# 10. Fresh External Verification nach Veröffentlichung

Ein Release gilt noch nicht allein deshalb als vollständig, weil Registry-Uploads erfolgreich waren.

Danach frische externe Verbraucher-Sicht testen.

## 10.1 PyPI

In frischer Umgebung:

```text
pip install <released version>
import VoiceSTT
version prüfen
Server-Smoke
```

## 10.2 GHCR

Fresh Pull:

```text
pull immutable release tag
inspect labels
start
health
version/commit
```

## 10.3 Docker Hub

Dasselbe für Docker Hub.

## 10.4 GitHub Release

Prüfen:

- richtiger Tag;
- richtige Version;
- Release Notes;
- Hashes;
- Links/Referenzen;
- keine falschen oder fehlenden Artefakte.

Erst dann:

```text
RELEASE_COMPLETE
```

---

# 11. Release Notes / Changelog / Archivabschluss

Vor bzw. während W6:

## 11.1 Release Notes

`RELEASE_NOTES.md` bzw. kanonische Release Notes sollen zusammenfassen:

- AP-SRV-010 bis AP-SRV-070;
- Protocol v2;
- Trigger-/Activation-Architektur;
- Settings Control;
- Wake Word;
- Model Management;
- Kroko Free/Pro;
- Packaging;
- Production Deployment;
- Breaking Changes;
- relevante Legacy-Kompatibilität;
- Upgrade-Hinweise;
- bekannte bewusste Grenzen.

## 11.2 AP-SRV-070 Archiv

Nach Abschluss:

```text
docs/.archiv/einheitliche_triggerarchitektur/AP-SRV-070/
```

soll enthalten:

- finalen Scope-/Soll-Ist-Abgleich;
- relevante Root-/Qualification-Evidence;
- finale Commits/Trees;
- Abweichungen;
- W4/W5/W6-Ergebnisse.

`docs/.archiv/README.md` auf abgeschlossen aktualisieren.

---

# 12. Empfohlene verbleibende Gewichtung

Ab aktuellem Stand `b2ec1657...`:

| Restphase | Anteil des verbleibenden Aufwands | Charakter |
|---|---:|---|
| Hermes Ubuntu Requalification | 8 % | reale Plattform-Evidence |
| W4C Production Docker/Deployment | 30 % | letzter größerer Implementierungsblock |
| W5 Release Candidate Qualification | 27 % | Gesamtintegration / Quality Gate |
| Final Root + Canonical Close | 10 % | Review / Governance |
| W6 Release Prep + Publication | 20 % | Automatisierung / irreversible Publish-Schritte |
| Fresh External Verification + Archive Close | 5 % | Abschluss |

Das sind **Prozente des Restes**, nicht des Gesamtprojekts.

---

# 13. Empfohlene Agentenstrategie für den Rest

## 13.1 Grundsatz

Keine neuen Agenten erhalten die komplette Projektgeschichte zum erneuten Audit.

Jeder Auftrag enthält:

```text
1. exakten Start-Commit
2. betroffenen Scope
3. geschlossene Verträge
4. konkrete Acceptance Gates
5. relevante Dateien
6. Stop-Regel
```

## 13.2 Geschlossene Contracts nicht neu prüfen

Ohne konkreten reproduzierbaren Defekt nicht wieder aufrollen:

- Protocol v2 Grundvertrag;
- Activation Lifecycle;
- Wake-Word-Architektur;
- W3 Package Authority;
- W4A Kroko Artifact Authority;
- W4B Model-Management-Authority;
- W4AB-C1 A–J.

## 13.3 Review-Regel

Ein Review erzeugt nur dann eine Correction-Runde, wenn ein echter harter Fehler vorliegt.

Maximal:

```text
Implementation Run
→ Root Review
→ höchstens eine eng begrenzte Correction
```

Kein automatisches:

```text
Phase 1
→ Phase 2
→ Phase 2R
→ Phase 2S
→ ...
```

für theoretische Härtung.

## 13.4 Modellwahl

- **Hermes:** Ubuntu-/VPS-Requalification, reale Host-Evidence.
- **Gemini 3.8 / günstiger Executor:** klar definierte Implementierung, Tests, Docker-Wiring, Evidence.
- **Codex / GPT-5.6 Sol:** nur für wirklich komplexe Integrations-/Debugging-Fälle, bei denen höhere Modellqualität mehrere Korrekturrunden vermeiden kann.
- **Koordination/Root:** entscheidet Scope, Contracts, PASS/FAIL.

---

# 14. Emergency-/Context-Limit-Regel

Wenn ein Agent oder Chat in Token-/Context-Limits läuft:

Sofort stoppen und einen Handoff erzeugen mit:

```text
CURRENT_BRANCH
CURRENT_HEAD
PARENT
REMOTE DISTRIBUTED
CANONICAL
git status --short
geänderte Dateien
bereits erledigte Requirements
bereits gelaufene Tests + Ergebnisse
offene Tests
offene TODOs
exakter nächster Schritt
bekannte Blocker
```

Keine unnötigen großen Dateien mehr lesen.

Keine Cleanups/Rebuilds nur für den Handoff.

Wenn nötig einen **separaten WIP-Handoff-Branch** erzeugen, ohne Distributed/Canonical zu verändern.

WIP-Handoff ist Transport/Sicherung, kein Root-PASS und kein finaler Run-Commit.

---

# 15. Bekannte lokale Test-/Host-Hinweise

## Windows pytest

Auf diesem Host gab es historisch Probleme mit dem Default-Pytest-Temp-Verzeichnis.

Bei Bedarf explizit:

```powershell
--basetemp="$env:LOCALAPPDATA\Temp\<run-name>"
```

verwenden.

Der finale W4AB-C1-Full-Run benötigte keinen WMI-Hack und lief nativ vollständig grün.

## Linux

Für Kroko-Build mindestens vorgesehen:

```text
cmake
g++
libssl-dev
pkg-config
python3-dev
```

OpenSSL-Development-Identity ist jetzt Build-/Fingerprint-relevant.

---

# 16. Kritischer Pfad ab jetzt

## Sofort

```text
[1] Hermes Ubuntu Requalification auf b2ec1657...
```

Parallel kann W4C vorbereitet werden.

## Danach

```text
[2] W4C implementieren
[3] W4C Review / harter Smoke
[4] RC Commit einfrieren
[5] W5 komplette Qualification
[6] Final Root-PASS
[7] Canonical AP-SRV-070 Close
[8] W6 Release Preflight/Automation
[9] Tag + Publish
[10] Fresh External Verification
[11] Archive Close
```

---

# 17. Definition „Server V2 fertig“

Der Server gilt erst dann als vollständig fertig, wenn **alle** folgenden Punkte erfüllt sind:

```text
[ ] Hermes Ubuntu Requalification PASS
[ ] W4C Production Deployment PASS
[ ] Full W5 RC Qualification PASS
[ ] AP-SRV-070 ROOT PASS
[ ] Canonical AP-SRV-070 geschlossen
[ ] Release-Version automatisch/konsistent bestimmt
[ ] Preflight PASS vor immutable Tag
[ ] Release-Tag veröffentlicht
[ ] PyPI veröffentlicht
[ ] GHCR veröffentlicht
[ ] Docker Hub veröffentlicht
[ ] GitHub Release veröffentlicht
[ ] Fresh external PyPI install PASS
[ ] Fresh GHCR pull/run PASS
[ ] Fresh Docker Hub pull/run PASS
[ ] Release-State COMPLETE
[ ] AP-SRV-070 Archiv/Register abgeschlossen
```

---

# 18. Aktuelle Quellen / Evidence

## W4AB-C1 final

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4AB-C1\Final\
```

Enthält:

```text
01_W4AB_C1_REQUIREMENT_MATRIX.md
02_W4AB_C1_FINAL_TESTS.md
03_HERMES_UBUNTU_REQUALIFICATION.md
W4AB_C1_FINAL_STATE.md
```

## Verbindlicher finaler Stand

```text
Distributed:
b2ec1657d40b4015cf8cf92c17eef1371b127b78

Tree:
a26f17a83aeff9743ad40950e12699c47ac3edf4

Canonical:
c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
```

## Historische AP-SRV-070 Authority

Die ursprünglichen W0-Unterlagen bleiben als historische Scope-/Backlog-Authority relevant:

```text
2026-08-29_W0_DELTA_REVALIDATION.md
2026-08-29_W0_SCOPE_MATRIX.md
2026-08-29_W0_EXECUTION_BACKLOG.md
```

Der heutige Plan erweitert den ursprünglichen W4–W6-Scope um die inzwischen entschiedenen Productization-/Release-Anforderungen, ersetzt aber keine bereits Root-abgenommenen Produktverträge.

---

# 19. Nächster Auftrag

**Nächster operativer Schritt:**

```text
Hermes / Ubuntu Requalification
Commit: b2ec1657d40b4015cf8cf92c17eef1371b127b78
```

Danach:

```text
AP-SRV-070 / W4C — Production Docker / Deployment
```

W4C soll sich auf die bereits vorhandenen Authorities stützen und **keine** Kroko-/Model-Management-Architektur erneut entwerfen.

---

# 20. Kurz-Handoff für eine neue Koordinationssession

Falls nur wenige Sekunden zur Übergabe bleiben, reicht dieser Block:

```text
VOICE STT SERVER V2 — CURRENT STATE

Distributed:
b2ec1657d40b4015cf8cf92c17eef1371b127b78

Tree:
a26f17a83aeff9743ad40950e12699c47ac3edf4

Canonical:
c82923fc6ce889b4dfbbde1f9877b8b76481a1e8

W4AB-C1:
PASS
1513 passed / 14 skipped / 974 subtests
0 failed / 0 errors
A–J PASS
W4C NOT STARTED

Immediate next:
1. Hermes Ubuntu requalification of b2ec1657...
2. W4C Production Docker / Deployment
3. W5 RC Qualification
4. Final Root PASS
5. Canonical AP-SRV-070 Close
6. W6 automated Release:
   preflight before tag
   → tag
   → PyPI
   → GHCR
   → Docker Hub
   → GitHub Release last
   → fresh external verification
7. Archive close

Review rule:
Only real correctness/security/data-loss/runtime/deployment/release defects block.
No renewed theoretical hardening loops.

Source evidence:
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4AB-C1\Final\
```
