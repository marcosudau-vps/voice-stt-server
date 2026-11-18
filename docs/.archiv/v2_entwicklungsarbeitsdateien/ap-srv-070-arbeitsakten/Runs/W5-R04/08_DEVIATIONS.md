# W5-R04 — 08 Deviations

Source reference: `docs/.archiv/einheitliche_triggerarchitektur/AP-SRV-070/2026-09-08_W5_R04_ABWEICHUNGEN.md`

This document records all material deviations from the original plan or prompt encountered during the W5-R04 implementation and closing runs. Each entry specifies deviation, rationale, impact, decision, and status.

---

## A1 — Kein sdist für die beiden öffentlichen Distributionen

- **Deviation:** Der ursprüngliche Auftrag sah die Veröffentlichung von Wheel **und** sdist vor. Es wird kein sdist für `voice-stt-server` und `voice-stt-server-pro` erzeugt oder veröffentlicht.
- **Rationale:** Das Kernmerkmal dieser Distributionen ist die Bündelung einer qualifizierten nativen Kroko-Laufzeit. Ein Source Distribution (sdist) kann diese kompilierte Laufzeit nicht transportieren. Bei Installation via sdist hätte pip entweder eine ca. 30-minütige lokale native Kompilierung versucht oder eine Installation ohne Kroko-Laufzeit erzeugt. Beides widerspricht der Produktanforderung.
- **Impact:** Für unterstützte Plattformen (CPython 3.12 auf Linux x86_64 und Windows x86_64) stehen qualifizierte Wheels bereit; auf nicht unterstützten Plattformen schlägt die Installation sofort und verständlich fehl. Das RC-Manifest Schema v2 bindet keine sdist-Identität mehr.
- **Decision:** Bewusst, autorisiert durch Abschnitt 9 der neueren verbindlichen Packaging-Autorität.
- **Status:** Umgesetzt und in `docs/release-process.md` technisch dokumentiert.

---

## A2 — Zwei Distributionen statt einer

- **Deviation:** Der ursprüngliche Auftrag ging von einem einzelnen PyPI-Projekt aus. Es werden zwei getrennte alternative Distributionen veröffentlicht: `voice-stt-server` (Kroko Free) und `voice-stt-server-pro` (Kroko Pro).
- **Rationale:** Free- und Pro-Kroko sind technisch getrennte native Laufzeiten, die zur Installationszeit feststehen müssen und nicht via Laufzeit-Schlüssel ausgetauscht werden können.
- **Impact:** Beide Distributionen stellen dasselbe Python-Importpaket (`voice_stt_server`) und dieselbe CLI (`voice-stt-server`) bereit und schließen einander in derselben Python-Umgebung aus. RC-Manifest, Release-Engine, Preflight, Workflows und Dokumentation unterstützen beide Distributionen durchgängig.
- **Decision:** Bewusst, vorgegeben durch die neuere verbindliche Packaging-Autorität.
- **Status:** Umgesetzt.

---

## A3 — `toolchain_identity("linux")` wurde nicht umgebaut

- **Deviation:** Die ursprüngliche Planung sah vor, `fingerprint.toolchain_identity("linux")` analog zu Windows auf eine deklarierte Toolchain-Autorität umzustellen. Dies wurde nicht durchgeführt.
- **Rationale:** Die Bestandsaufnahme zeigte, dass `install_kroko.fingerprint_for` auf Linux bereits eine real probierte Toolchain-Identität (`cmake`, `cc`, `c++`, OpenSSL) aus dem Buildcontainer heranzieht. Eine deklarierte Toolchain hätte diese reale Identität nicht überschrieben.
- **Impact:** Das tatsächliche Stabilitätsproblem (bewegliches Basis-Image) wurde durch Deklaration des Containers selbst (`linux_builder_declaration()`), Pinning von Basis-Image-Digest und Packaging-Werkzeugen sowie Erhöhung von `LINUX_BUILDER_REVISION` von 1 auf 2 gelöst. Die Windows-Autorität bleibt unberührt (`WINDOWS_BUILDER_REVISION` = 4).
- **Decision:** Bewusst; gezielte wirksame Korrektur statt wirkungsloser Strukturänderung.
- **Status:** Umgesetzt.

---

## A4 — `huggingface_hub` aus dem Kroko-Builder-Image entfernt

- **Deviation:** `huggingface_hub` wurde aus dem Kroko-Builder-Container entfernt.
- **Rationale:** Keine der in das Builder-Image kopierten Dateien importiert `huggingface_hub`. Es handelte sich um eine ungepinnte, ungenutzte Abhängigkeit.
- **Impact:** Das Builder-Image ist kompakter und hat einen ungepinnten Netzwerkeingang weniger.
- **Decision:** Bewusst im Rahmen der Härtung der Build-Eingänge.
- **Status:** Umgesetzt.

---

## A5 — `--dist-dir` außerhalb des Buildkontexts wird abgelehnt

- **Deviation:** `--dist-dir` außerhalb des Repository-Wurzelverzeichnisses wird sofort mit Fehler abgelehnt.
- **Rationale:** Das Produktions-Dockerfile kopiert Distributions-Wheels relativ zum Buildkontext (`COPY dist/...`). Ein Verzeichnis außerhalb des Kontexts führte nach 25 Minuten Build-Laufzeit zu einem harten Docker-Fehler.
- **Impact:** Fail-closed Validierung vor Start des teuren nativen Builds.
- **Decision:** Bewusst; frühzeitiges Abfangen ungültiger Parameter.
- **Status:** Umgesetzt.

---

## A6 — Registry-Identität ist der Manifest-Digest

- **Deviation:** Die Identitätsprüfung von Images im Remote-Registry-Check prüft nun den Manifest-Digest statt der lokalen Docker-Image-ID.
- **Rationale:** Lokale Image-IDs (Config-Blob-Hashes) stimmen konstruktionsbedingt nie mit Remote-Manifest-Digests überein; dies führte zuvor zu fälschlichen `CONFLICT`-Meldungen.
- **Impact:** RC-Manifest (Schema v2) bindet `images.<variante>.digest`; Promotion und Verifikation arbeiten durchgängig mit Manifest-Digests.
- **Decision:** Bewusst; Korrektur eines bestehenden Fehlers.
- **Status:** Umgesetzt.

---

## A7 — Redaktion in `remote_checks`

- **Deviation:** Automatische Redaktion sensibler Daten an der Grenze in `remote_checks.py`.
- **Rationale:** Fehlgeschlagene Registry-Abfragen können im stderr Zugangsdaten oder Tokens enthalten, die unredigiert in Logs oder Artefakte gelangen könnten.
- **Impact:** Redaktion verhindert Secret-Leaks in Exceptions und Logausgaben (Gate W5R4-G49).
- **Decision:** Bewusst zur Wahrung der Sicherheitsgrenzen.
- **Status:** Umgesetzt.

---

## B1–B4 + E1 — Root Review Korrekturen (08.09.2026)

Der externe Root Review lehnte den vorherigen lokalen Commit `5a87ad837a9f078c59a37bd7a1e1134b59117a97` wegen vier konkreter Releaseblocker (B1–B4) sowie einer Evidenz-Inkonsistenz (E1) ab. Die folgenden gezielten Korrekturen wurden im selben W5-R04-Workspace umgesetzt und ersetzen den abgelehnten Stand via Amend:

### B1 — Berechtigungen im Publish-Workflow (`.github/workflows/release-publish.yml`)
- **Finding:** Jobs mit expliziten Berechtigungsblöcken verloren `actions: read` (Download von Artefakten des Kandidaten-Runs) und `contents: read` (Checkout).
- **Korrektur:** Jeder Job erhielt minimal notwendige Berechtigungen: Cross-Run-Artifact-Downloadjobs haben `actions: read`, Checkout-Jobs mindestens `contents: read`, Tag/Release `contents: write`, PyPI isoliert `id-token: write`.
- **Status:** Umgesetzt und in `tests/unit/test_release_workflows.py` getestet.

### B2 — Windows- und Linux-Distributions-Wheels im Kandidaten-Build
- **Finding:** Der Kandidaten-Workflow baute ausschließlich Linux-Wheels; Windows AMD64 Distributions-Wheels fehlten im Build und Manifest, wodurch `pip install voice-stt-server[-pro]` auf Windows unvollständig gewesen wäre.
- **Korrektur:** Candidate-Workflow in 3 Jobs unterteilt: `candidate-linux` (Ubuntu 24.04), `candidate-windows` (Windows-latest) und `candidate` (Zusammenführung/Qualifikation). `rc_manifest.py` erzwingt `REQUIRED_PLATFORMS = ("linux_x86_64", "win_amd64")` (4 Wheels gesamt: Free Linux, Free Windows, Pro Linux, Pro Windows). `tools/release_candidate.py` unterstützt `--platform {linux,windows,all}`.
- **Status:** Umgesetzt und in `tests/unit/test_release_candidate.py` und `test_release_rc_manifest.py` getestet.

### B3 — Publikationsbarriere für `NOT_QUALIFIED` / `REJECTED` Kandidaten
- **Finding:** Manifeste mit `releaseReadiness != "QUALIFIED"` konnten syntaktisch den realen Veröffentlichungspfad erreichen.
- **Korrektur:** Release-Engine (`release_tooling/engine.py`), Preflight (`release_tooling/preflight.py`) und CLI (`release_tooling/cli.py`) erzwingen im `REAL`-Modus `releaseReadiness == "QUALIFIED"` und eine gültige Evidenz-Referenz. `manifest qualify` führt die kontrollierte Qualifikation durch.
- **Status:** Umgesetzt und in `test_release_engine.py`, `test_release_preflight.py` und `test_release_cli.py` getestet.

### B4 — PyPI-Vorabprüfung vor öffentlichem OIDC-Schreibvorgang
- **Finding:** Trusted Publishing schrieb vor der Verifikation auf PyPI; ein Namens-/Hash-Konflikt wurde erst post-write erkannt.
- **Korrektur:** `precheck_pypi` und CLI-Befehl `release-tooling precheck-pypi` prüfen beide Distributionen und alle 4 Plattform-Wheels vor dem OIDC-Upload read-only ab. Bei `CONFLICT` oder `UNKNOWN` wird vor dem Schreibvorgang hart abgebrochen. Bei `MATCH`/`ABSENT` wird sicher und selektiv weitergearbeitet.
- **Status:** Umgesetzt und in `test_release_cli.py` und `test_release_adapters.py` getestet.

### E1 — Richtigstellung widersprüchlicher Staging-Evidenz
- **Finding:** Gate G17 in `07_GATE_INDEX.md` behauptete fälschlicherweise, dass Kandidaten-Images bereits in eine private Staging-GHCR gepusht wurden, während der Abschlussbericht korrekterweise null Staging-Pushes bestätigte.
- **Korrektur:** Wording in G17 und Abschlussdokumentation präzisiert: Die lokale W5-R04-Implementierung beweist die Staging-Architektur strukturell; reale Staging-Registry-Writes erfolgen erst im post-Root-PASS GitHub-Kandidatenrun. Null lokale Staging-Pushes durchgeführt.
- **Status:** Richtiggestellt.

---

## B5 + B6 — Zweite Root Review Korrekturen (08.09.2026)

Der erneute externe Root Review akzeptierte die Korrekturen B1, B2, B3 und E1. Der vorherige Commit `202bedadd4a2448e7ab11fb11b2567053b46a2e1` wurde wegen zweier konkreter Releaseblocker (B5, B6) abgelehnt (`FAIL`). Die folgenden eng begrenzten Korrekturen wurden im selben W5-R04-Workspace umgesetzt und ersetzen den abgelehnten Stand via Amend:

### B5 — PyPI Read-Only Precheck & Verification gemäß aktueller Release-spezifischer JSON API
- **Finding:** `inspect_pypi_release` forderte `https://pypi.org/pypi/<project>/<version>/json` an, las Dateien jedoch aus `payload.get("releases", {}).get(version, [])`. Der offizielle aktuelle PyPI Release-Endpoint liefert `releases` nicht mehr aus; die Dateien für das Release liegen stattdessen im Top-Level-Feld `"urls": [...]`. Dadurch erschienen existierende Releases fälschlicherweise als leer/absent, was die B4-Konflikterkennung sowie die Post-Write-Verifikation hemmte.
- **Korrektur:** `release_tooling/remote_checks.py` angepasst: `inspect_pypi_release` liest nun direkt `payload.get("urls")`. Für jedes Element werden `filename` und `digests.sha256` extrahiert. Fehlt `urls` oder ist es keine Liste, schlägt die Prüfung fail-closed mit `VerificationUnavailableError` fehl. Eine leere Liste `[]` signalisiert einen bekannten Zustand ohne hochgeladene Dateien (`ABSENT`). 404 bleibt genuine `ABSENT`. Precheck und Post-Write-Verifikation nutzen dieselbe Parser-Logik.
- **Status:** Umgesetzt und in `tests/unit/test_release_remote_checks.py` (23 Tests) sowie `tests/unit/test_release_adapters.py` getestet.

### B6 — Validierung des Workflow-Inputs `version` gegen Kandidaten-Manifest
- **Finding:** `.github/workflows/release-publish.yml` definierte `concurrency.group: release-publish-${{ inputs.version }}`, validierte jedoch nicht, ob der Workflow-Eingabeparameter `version` mit `productVersion` im heruntergeladenen `rc-manifest.json` übereinstimmt. Ein Tippfehler im Dispatch-Input hätte dazu geführt, dass die Release-Serialisierung umgangen wird.
- **Korrektur:**
  1. In `.github/workflows/release-publish.yml` (`tag`-Job) vor der ersten mutativen Aktion (Git-Tag-Erstellung) einen Validierungsschritt eingefügt:
     ```bash
     python release.py preflight \
       --manifest "$CANDIDATE_DIR/rc-manifest.json" \
       --version "${{ inputs.version }}" \
       --require-qualified
     ```
  2. `--version` zu `publish`-CLI-Parser hinzugefügt; `_cmd_publish` validiert `args.version == manifest["productVersion"]` fail-closed mit Fehlerausstieg vor jeglicher Mutation.
  3. In allen `release.py publish`-Aufrufen in `release-publish.yml` wird `--version "${{ inputs.version }}"` übergeben.
  4. In `release_tooling/preflight.py` prüft `_check_manifest_version` (`rc_manifest_version_matches`), ob `manifest.productVersion == expected_version`.
- **Status:** Umgesetzt und in `test_release_preflight.py`, `test_release_cli.py` und `test_release_workflows.py` getestet.
