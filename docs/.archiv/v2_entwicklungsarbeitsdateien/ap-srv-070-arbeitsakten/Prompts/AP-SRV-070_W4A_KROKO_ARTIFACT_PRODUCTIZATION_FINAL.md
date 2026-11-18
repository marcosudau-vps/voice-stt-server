# AP-SRV-070 — W4A
# Kroko Runtime / License Variant / Model Productization / Persistent Build Artifacts

## Auftrag

Entkopple den teuren nativen Kroko-Build vollständig vom normalen VoiceSTT-Server-Build.

Nach W4A darf eine normale Änderung am Servercode keinen vollständigen Kroko-Neubau mehr auslösen, wenn für die gewünschte Variante bereits ein passendes, verifiziertes Kroko-Artefakt existiert.

W4A umfasst:

- immutable Kroko-Upstream-Pinning
- reproduzierbaren Build-Fingerprint
- persistente Free-/Pro-Artefakte
- Reuse-by-default
- expliziten Force-Rebuild
- kontrollierte Kroko-Modellauthority
- sichere Lizenz-/Secret-Grenzen
- Schnittstellen für W4B und spätere CI-/Release-Automation

Noch NICHT:

- finaler Production-Docker-Stack
- GHCR-/Docker-Hub-Publish
- GitHub Release
- PyPI Publish
- vollständige Release-State-Machine

---

## Authorities / Ausgangslage

W0:
`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prep\W0\`

W3:
`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W3\`

Aktueller verbindlicher W3-Stand:

Distributed HEAD:
`421bc5df6233bfd969890185792c1857fc38a27f`

Distributed TREE:
`5a2b969ee09ae614a679f0e3be3ce7f3ecf66631`

Canonical:
`c82923fc6ce889b4dfbbde1f9877b8b76481a1e8`

W3-Verträge, die W4A nicht brechen darf:

- Produktversion kommt aus `VERSION` / `VoiceSTT._version`
- Build-Kandidaten können über den etablierten Build-Version-Mechanismus gestempelt werden
- Wheel/Sdist enthalten nur authority-freigegebene Wake-Ressourcen
- kein PyPI-Publish / kein Tag in W4A
- installierte Distribution ist der spätere Produktpfad, nicht editable/source install

Aktuelle Kroko-/Build-Authority im Repo mindestens prüfen:

- `Dockerfile`
- `Dockerfile.pro-upgrade`
- `VoiceSTT/install_kroko.py`
- `VoiceSTT/transcription_engines/kroko_onnx.py`
- `VoiceSTT/transcription_engines/model_resolver.py`
- `build/BUILD.md`
- `build/vps/**`
- `docs/engines/kroko-onnx.md`
- vorhandene Kroko-Tests

Nur starten wenn:

- Remote `github/feat/einheitliche-triggerarchitektur-distributed` exakt auf `421bc5df6233bfd969890185792c1857fc38a27f` steht
- Worktree clean
- Canonical unverändert und clean
- W3 STATE meldet `W4A ready: JA`

Sonst:
`STATUS: BLOCKED`

---

## Git / Worktree

Branch:
`work/AP-SRV-070`

Worktree:
`P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070`

Keinen neuen Worktree anlegen.
Kein Amend alter Runs.
Kein Force-Push.
Canonical unverändert lassen.

Keine neue persistente lokale venv anlegen. Falls für isolierte Prüfungen eine temporäre Umgebung notwendig ist, vollständig außerhalb des Worktrees anlegen und nach dem Lauf entfernen.

W3 dokumentiert einen temporären Docker-Runtime-Ausfall. W4A darf nicht allein deshalb blockieren, wenn die Kroko-Artefaktlogik und mindestens ein realer Build auf einem anderen belastbaren lokalen Weg qualifiziert werden können. Docker-spezifische Produktqualifikation gehört W4B. Wenn Docker wieder funktioniert, darf er selbstverständlich für geeignete W4A-Prüfungen verwendet werden.

---

# W4A-01 — Free/Pro-Lizenzgrenze

Community und Pro sind getrennte Runtime-Buildvarianten.

Community:

- Buildvariante `free`
- kein Pro-Key notwendig
- Community-Modell nur entsprechend belegter Lizenz-/Redistributionsrechte integrieren

Pro:

- Buildvariante `pro`
- Runtime muss Pro-fähig gebaut sein
- Lizenz-Key ausschließlich zur Laufzeit als Secret
- Pro/private Modelle niemals ohne eindeutige Redistributionsberechtigung öffentlich bündeln

## HARTE SECRET-REGEL

Der Kroko-Key darf niemals in:

- Git
- Python Wheel/Sdist
- Kroko Build-Wheel
- Docker Layer
- Build Cache
- persistentes Build Artifact
- GitHub Actions Artifact
- Log
- Evidence-Datei

enthalten oder ausgegeben werden.

Der Build der Pro-Runtime darf den Runtime-Key nicht benötigen, sofern das reale Kroko-Buildsystem das nicht zwingend verlangt. Falls es ihn überraschend doch verlangt: `STATUS: BLOCKED` und genaue Diagnose statt Secret in den Buildpfad zu ziehen.

Ein Key allein darf eine Free-Runtime niemals implizit zu Pro machen.

---

# W4A-02 — Kroko-Upstream immutable pinnen

Der bisherige lose Branchbezug wie `cross-platform-builds` reicht als reproduzierbare Authority nicht aus.

Vor Änderung:

1. tatsächliche aktuell verwendete Kroko-Upstream-Quelle ermitteln;
2. Branch/Revision/Remote dokumentieren;
3. den exakt aktuell qualifizierten Upstream-Commit bestimmen;
4. prüfen, ob Submodule/LFS/weitere Buildinputs existieren;
5. aktuellen Buildweg Free/Pro nachvollziehen.

Danach eine immutable, source-controlled Revision als Authority etablieren.

Kein normales Build darf einfach "latest branch head" ziehen.

Ein bewusstes Upstream-Upgrade muss eine explizite Änderung der Revision sein und damit automatisch einen neuen Build-Fingerprint erzeugen.

---

# W4A-03 — Build-Fingerprint

Definiere einen kanonischen Kroko-Build-Fingerprint.

Mindestens einbeziehen:

- immutable Kroko-Upstream-Revision
- Variante `free|pro`
- Zielbetriebssystem / Plattform
- Architektur
- Python Major/Minor + ABI/Interpreter-Tag
- relevante Compiler-/CMake-Version soweit buildwirksam
- relevante CMake-/Compiler-Flags
- Free-/Pro-Schalter
- VoiceSTT-spezifische Patches oder andere source-controlled Kroko-Buildinputs
- Buildsystem-/Wheel-ABI-relevante Inputs

Nicht einbeziehen:

- normale Änderungen an FastAPI
- Serverlogik
- Docs
- Wake-Word-Code
- README
- Produktversion `VERSION`, sofern sie den nativen Kroko-Binaryinhalt nicht verändert
- sonstige VoiceSTT-Dateien ohne Einfluss auf Kroko

Eine reine Server-Versionserhöhung darf Kroko nicht neu kompilieren.

Fingerprint muss:

- deterministisch serialisiert werden
- stabil über Wiederholungen sein
- menschenlesbare Metadaten besitzen
- zusätzlich einen kompakten Hash/ID für Dateinamen/Cachekey liefern

---

# W4A-04 — Persistentes Artifact Store / Reuse-by-default

Ziel:

```text
Build Inputs
  -> Fingerprint
  -> passendes verifiziertes Artifact vorhanden?
       JA -> REUSE, keine Kompilierung
       NEIN -> BUILD ONCE -> VERIFY -> STORE
```

Persistent bedeutet: nicht bloß ein zufälliger Docker-Layer-Cache, der bei einer normalen Image-Neuerstellung verschwinden oder invalidiert werden kann.

Die Implementierung soll einen konfigurierbaren Artifact-Store besitzen, der außerhalb des Source-Repositories liegen kann und für lokale Builds, VPS/CI und spätere W4B-Container-Builds geeignet ist.

Keine persönlichen absoluten Pfade als Produktvertrag hardcoden.

Free und Pro erhalten strikt getrennte Namespaces/Artifacts.

Ein Wechsel:

`free -> pro -> free`

muss die jeweils bereits vorhandenen, gültigen Artefakte wiederverwenden können.

## Artifact-Metadaten mindestens

- schemaVersion
- fingerprint
- upstream revision
- variant
- target platform
- architecture
- Python ABI/tag
- build flags / relevante Toolchain-Identität
- wheel filename
- wheel SHA256
- wheel bytes
- build timestamp nur informativ, niemals Teil des Fingerprints

---

# W4A-05 — Expliziter Force-Rebuild

Es muss einen bewussten Weg geben, ein vorhandenes passendes Artefakt neu zu bauen.

Beispielsemantik:

`--rebuild-kroko`

Default:

`REUSE`

Force:

`REBUILD -> VERIFY -> ATOMICALLY REPLACE/STORE`

Der Force-Weg muss:

- ausdrücklich ausgelöst werden
- vorhandenes Artifact nicht als Build-Erfolg zählen
- tatsächlich den Builder aufrufen
- das neue Artifact vollständig verifizieren
- bei Fehlschlag das zuvor bekannte gute Artifact nicht zerstören
- keine Secrets persistieren

---

# W4A-06 — Artifact Integrity / Consumption Contract

Ein Kroko-Artefakt darf nur konsumiert werden, wenn mindestens geprüft wurde:

- Fingerprint passt exakt
- SHA256 passt
- Bytes/Datei vollständig
- erwartete `free|pro`-Variante
- Plattform/Architektur
- Python ABI / Wheel-Tags kompatibel
- Wheel installierbar
- Kroko-Modul importierbar
- Runtime-Variante stimmt mit erwarteter Modellklasse überein

Keine stillen Fallbacks Free <-> Pro.

Ein beschädigtes, falsches oder fremdes Artifact ist ein harter Cache-Miss/Fehler, nie ein "best effort"-Treffer.

W4B muss später ein bereits qualifiziertes Artifact konsumieren können, ohne Kroko als normalen Bestandteil des Server-Image-Builds erneut zu kompilieren.

---

# W4A-07 — Kroko-Modellauthority

Aktuell werden Kroko-Modelle überwiegend über externe Pfade wie `VOICESTT_KROKO_MODEL_ROOT` aufgelöst.

W4A soll daraus eine kontrollierte Modellauthority machen, ohne Lizenzgrenzen zu verletzen.

## Modellmanifest mindestens

- Modell-ID
- Dateiname
- Sprache
- Community oder Pro/private
- Herkunft
- immutable Revision / konkrete Source-Version soweit bestimmbar
- SHA256
- Bytes
- Lizenzklasse
- erwartete Runtime-Variante `free|pro`
- Redistributionsstatus
- lokaler Verfügbarkeitsstatus

Die Runtime soll nicht mehr einen unbekannten Ordnerinhalt als Produkt-Authority behandeln.

Kompatible explizite externe Modellpfade können als Operator-Override erhalten bleiben, aber dann mit klarer Validierung und ohne stille Netzwerkabhängigkeit.

## Community

Prüfe die tatsächliche Lizenz / Model Card / Repository-Regeln.

Wenn öffentliche Redistribution eindeutig erlaubt ist:

- kontrolliert integrieren oder provisionieren
- Lizenz-/Attributionspflichten dokumentieren
- Hash/Revision pinnen

Wenn nicht eindeutig:

- NICHT in öffentliches Git/PyPI/Image aufnehmen
- kontrollierten, hashverifizierten Provisioning-Pfad definieren
- Status `POLICY_REQUIRED` oder gleichwertig dokumentieren

## Pro/private

Nicht öffentlich in:

- Git
- PyPI
- GHCR
- Docker Hub

integrieren, solange keine eindeutige Redistributionsberechtigung vorliegt.

Private lokale/VPS-Provisionierung darf unterstützt werden, aber nur mit manifestierter Identität/Hash und klarer Secret-/Lizenzgrenze.

---

# W4A-08 — Offline-/Runtime-Vertrag

Produktionsmodus muss deterministisch sein.

- kein spontaner Modell-Download beim normalen Serverstart
- kein spontaner Kroko-Source-Build beim normalen Serverstart
- kein spontaner Kroko-Compile beim normalen Docker-App-Build, wenn gültiges Artifact vorhanden
- fehlendes Modell/Artifact -> klarer Fehler oder expliziter Provisioning-Schritt
- Variant-/Model-Mismatch -> klarer Fehler

Keine stille Netzwerkabhängigkeit.

---

# W4A-09 — Tests / Qualification

Automatisiert mindestens beweisen:

1. Fingerprint bei identischen Inputs stabil.
2. Änderung normaler VoiceSTT-Anwendungsdatei ändert Fingerprint NICHT.
3. Änderung des Produktversionswerts allein ändert Fingerprint NICHT, sofern Kroko-Binaryinput unverändert.
4. Kroko-Upstream-Revision ändert Fingerprint.
5. Free/Pro ändert Fingerprint und Namespace.
6. Python ABI/Plattform/Architektur ändern Fingerprint.
7. erster Free-Build erzeugt verifiziertes Artifact.
8. zweiter identischer Free-Lauf kompiliert nicht erneut.
9. vorhandenes Free-Artifact nach einem zwischenzeitlichen Pro-Lauf wiederverwendbar.
10. Pro und Free können nicht verwechselt werden.
11. Force-Rebuild ruft Builder real erneut auf.
12. fehlgeschlagener Force-Rebuild zerstört kein vorhandenes gutes Artifact.
13. falsches/korruptes Artifact wird abgelehnt.
14. SHA/Metadaten/ABI-Tags werden geprüft.
15. Modellmanifest erkennt Hash-/Variant-Mismatch.
16. Offline-Modus startet keinen versteckten Download.
17. kein Secret in Artifact/Metadaten/Logs/Evidence.
18. `git diff --check` sauber.

## Realer Build

Ein 30-Minuten-Nativbuild darf nicht unnötig mehrfach real ausgeführt werden.

Mindestens **ein echter Kroko-Artefakt-Build** muss qualifiziert werden, soweit die benötigte Toolchain in dieser Umgebung verfügbar ist.

Danach Reuse/Invalidierung/Force-Verhalten bevorzugt über kontrollierte Tests, Instrumentierung und gezielte Builder-Smokes verifizieren, statt dieselbe teure Kompilierung mehrfach blind zu wiederholen.

Wenn ein echter Build wegen eines nachweisbaren externen Toolchain-/Umgebungsausfalls nicht möglich ist:

- nicht vortäuschen
- genaue Ursache dokumentieren
- Architektur-/Unit-Gates trotzdem vollständig ausführen
- W4B readiness nur dann `JA`, wenn W4B ein bereits existierendes qualifiziertes Artifact sicher konsumieren kann; sonst `BLOCKED`

---

# W4A-10 — W3-Integration

W4A darf die in W3 geschaffene Python-Produktdistribution nicht wieder vermischen.

Insbesondere:

- `VERSION` bleibt VoiceSTT-Produktversion, nicht Kroko-Fingerprintinput
- `VOICESTT_BUILD_VERSION` darf Kroko nicht neu kompilieren, solange die nativen Inputs gleich sind
- Kroko-Artifactversion/Fingerprint ist eigene technische Identität
- VoiceSTT Wheel/Sdist darf keinen Pro-Key enthalten
- Kroko Native Wheel/Artifact darf keinen Pro-Key enthalten
- W4B muss später VoiceSTT-Wheel + qualifiziertes Kroko-Artifact kombinieren können

Der in W3 dokumentierte Docker-Ausfall bleibt ein Carry für W4B/W5. Er ist kein Anlass, W4A künstlich in einen Docker-only-Testpfad umzubauen.

---

# W4A-11 — CI-/Release-Schnittstelle vorbereiten

Noch keine finale GitHub-Release-Automation implementieren.

W4A muss aber klare Maschinen-Schnittstellen liefern, sodass W4B/W5/W6 später:

- Fingerprint berechnen
- Artifact existence prüfen
- Artifact verifizieren
- Free/Pro auswählen
- Cache/Artifact-Pfad konfigurieren
- bei Miss explizit Builder ausführen
- optional Force-Rebuild auslösen
- Build-Ergebnis maschinenlesbar erfassen

können.

GitHub Actions muss später persistente Artefakte oder einen geeigneten Artifact-/Registry-Store verwenden können; ein ephemerer Layercache allein reicht nicht.

---

# Scope

Erlaubt:

- Kroko Builder / Install-Skripte
- Kroko Artifact-/Fingerprint-/Cache-Logik
- Kroko Model Authority
- Kroko Runtime Resolution, soweit für klare Modell-/Variant-Grenzen nötig
- direkte Tests
- minimale direkt betroffene Kroko-Build-/Modelldoku
- Hilfsdateien für maschinenlesbare Kroko-Metadaten

Nicht erlaubt:

- finaler Production-Docker-Umbau
- Registry Publish
- PyPI Publish
- Git Tag
- GitHub Release
- vollständige Release-State-Machine
- Client-Code
- unrelated Server-/Wake-Architekturänderungen

---

# Commit / Distributed

Bei erfüllten Implementierungs-, Scope- und Test-Gates genau EIN Agentenrun-Commit.

Parent:
`421bc5df6233bfd969890185792c1857fc38a27f`

Subject:
`build(kroko): productize reusable runtime artifacts`

Danach:

- SHA/TREE erfassen
- Worktree clean
- Canonical unverändert
- Remote Distributed vor Push weiterhin `421bc5d...`

Distributed ausschließlich per Fast-Forward aktualisieren:

`feat/einheitliche-triggerarchitektur-distributed`

Kein Force.
Kein Amend alter Runs.

W4A SHA ist Basis für W4B.

---

# Evidence

Unter:

`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4A\`

mindestens:

- `2026-08-31_W4A_KROKO_ARCHITECTURE.md`
- `2026-08-31_W4A_ARTIFACT_CACHE_REPORT.md`
- `2026-08-31_W4A_MODEL_MANIFEST_REPORT.md`
- `2026-08-31_W4A_TEST_REPORT.md`
- `2026-08-31_W4A_STATE.md`

STATE muss enthalten:

- W3 Parent `421bc5d...`
- W4A SHA/TREE
- Kroko Upstream Revision
- Fingerprint-Schema
- Artifact-Store-Vertrag
- Free Artifact + SHA/Metadaten
- Pro Artifact Status + Begründung
- Reuse Proof
- Force-Rebuild Proof
- Model Authority
- Lizenz-/Redistributionsstatus
- Secret Leakage Check
- realer Build Status
- Docker-Umgebungsstatus nur informativ
- Tests
- Distributed before/after
- Canonical unchanged
- W4B readiness

## Stop-Gates

`STATUS: BLOCKED` wenn:

- Distributed nicht auf W3 HEAD steht
- Worktree dirty/unexpected
- Canonical verändert
- Kroko-Upstream nicht reproduzierbar pinbar
- Free/Pro-Artefakte nicht sicher unterscheidbar
- Cache ein falsches/korruptes Artifact akzeptieren kann
- Pro-Key oder anderes Secret in Build/Artifact/Log/Evidence gelangt
- Modellredistribution ohne belastbare Lizenzgrundlage vorgenommen würde
- notwendiger realer Artifact-Vertrag nicht qualifizierbar ist
- Tests rot
- Force-Push nötig

## Abschluss

Lege die Evidence vollständig unter

`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4A\`

ab und beende den Lauf mit einer kurzen Zusammenfassung sowie dem Hinweis, dass der Evidence-Ordner fertig ist.
