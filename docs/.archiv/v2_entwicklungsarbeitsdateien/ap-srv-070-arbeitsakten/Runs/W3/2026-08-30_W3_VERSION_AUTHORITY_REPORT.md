# AP-SRV-070 — W3 — Version Authority Report

**Datum:** 2026-08-30
**Teilblock:** W3-01 / W3-02 / W3-06 / W3-07 — automatische Produktversions-Authority

---

## 1. Versionsinventar (W3-01)

Repo-weite Suche nach produktrelevanten Versionsquellen vor Implementierung:

| Ort | Vorheriger Zustand | Befund |
|---|---|---|
| `setup.py` | `current_version = "1.0.2"` (Modulkonstante) | Stale, W0-Befund: inkonsistent mit der etablierten V2-Identity |
| `api_fastapi_server/protocol_v2/identity.py` | `SERVER_VERSION = "2.0.0"` (Modulkonstante) | Die tatsächlich etablierte, im Wire-Protokoll ausgelieferte v2-Serveridentity |
| `api_fastapi_server/server.py:7568` | `FastAPI(..., version="2.0.0", ...)` | Dritter, unabhängig gepflegter Literal (OpenAPI/`/docs`-Identity) — bei Audit zusätzlich gefunden, nicht im ursprünglichen W0-Befund erwähnt |
| `tools/verify_session_wakeword.ps1:82` | `Assert-Condition ($openApi.info.version -eq "2.0.0")` | Viertes Vorkommen: Live-Verifikationsskript, hartkodierter Vergleich gegen exakten Literal |
| `RELEASE_NOTES.md` | letzter datierter Abschnitt `1.0.2` (2026-05-31) | Historischer Eintrag, nie auf die V2-Identity nachgezogen |
| `build/BUILD.md` | Beschreibt `current_version` in `setup.py` als Autorität | Beschreibung war korrekt für den alten Zustand, jetzt veraltet |
| Docker-/OCI-Versionswerte | keine gefunden | `Dockerfile`, `Dockerfile.pro-upgrade`, `docker-compose.yml` enthalten keinen Versions-Literal |
| Health-Endpoint (`GET /health`) | kein Versionsfeld vorhanden | "soweit vorhanden" trifft nicht zu — keine Änderung nötig |
| Git Tags | `archive/server/prep/*`, `archive/server/transport/*`, `archive/server/review-seal/*` | Keine SemVer-Produkt-Tags vorhanden; kein Konflikt mit einer Baseline-Entscheidung |
| `api_fastapi_server/protocol_v2/schema.py` | `PROTOCOL_VERSION = 2` | Getrennter Wire-Protocol-Integer, bewusst NICHT Teil der SemVer-Produktversion (unverändert) |
| `tests/contracts/protocol-v2-vectors.json` | `"serverVersion": "2.0.0-test"` | Testvektor-Fixture, kein Produktcode-Pfad — unverändert gelassen |

Vier unabhängig gepflegte Produktversions-Literale gefunden (`setup.py`,
`identity.py`, `server.py`-FastAPI-App, `verify_session_wakeword.ps1`), nicht
nur der im W0-Befund genannte `setup.py`-Fall.

## 2. Baseline-Entscheidung (kein neuer Release-Bump)

`SERVER_VERSION = "2.0.0"` in `api_fastapi_server/protocol_v2/identity.py`
ist die bereits etablierte, im eingefrorenen v2-Handshake ausgelieferte
Serveridentity (siehe `docs/einheitliche-triggerarchitektur.md`,
`docs/fastapi-server.md`). `setup.py`s `1.0.2` ist der W0-dokumentierte,
seit AP-SRV-0xx nie nachgezogene Altwert.

**Baseline: `2.0.0`**, migriert in die neue Authority (`VERSION`-Datei).
Kein neuer Major-/Minor-/Patch-Bump — reine Konsolidierung auf den bereits
gültigen Wert.

## 3. Die eine Authority

- **`VERSION`** (Repository-Root, source-controlled): `2.0.0\n`.
- **`VoiceSTT/_version.py`**: der gemeinsame Python-Resolver.

Auflösungsreihenfolge in `resolve_version()`:

1. `VOICESTT_BUILD_VERSION` (validierter Override), falls gesetzt und nicht
   leer. Ein ungültiger Override ist ein harter Fehler (`SemVerError`) —
   nie ein stiller Fallback.
2. Die `VERSION`-Datei, sofern sie relativ zum Modul auf der Platte existiert
   (Source-Checkout, editable install). Wird bewusst VOR der installierten
   Paket-Metadata geprüft, damit ein Build niemals eine zufällig im selben
   Environment bereits installierte, potenziell veraltete `voicestt`-Version
   verwendet.
3. `importlib.metadata.version("voicestt")` — für eine Laufzeitumgebung ohne
   Source-Baum (z. B. ein installiertes Wheel in einem Container).

Konsumenten, die jetzt ausschließlich über diese Authority laufen:

- `setup.py` (`current_version = resolve_version()`)
- `VoiceSTT.__version__` / `VoiceSTT.get_version()`
- `api_fastapi_server/protocol_v2/identity.py::server_version()`
- `api_fastapi_server/server.py::create_app()` (`FastAPI(version=...)`)
- `tools/verify_session_wakeword.ps1` (jetzt SemVer-Formprüfung statt
  Literal-Vergleich)

## 4. SemVer-Utility (W3-02)

`VoiceSTT/_version.py` implementiert, wiederverwendbar für das spätere
`release.py` (W5/W6):

- `parse_semver` / `is_valid_semver` / `validate_semver` — vollständige
  SemVer-2.0.0-Grammatik (inkl. Prerelease/Build-Metadata für Validierung).
- `bump(version, kind)` — `patch`/`minor`/`major`, mit den geforderten
  Reset-Regeln; ein Prerelease/Build-Suffix im Input wird akzeptiert, im
  Output aber nie übernommen (ein Release-Bump erzeugt immer eine reine
  `MAJOR.MINOR.PATCH`).
- `resolve_bump_kind(*, minor, major)` — reine Flag-Auflösung für den
  künftigen `python release.py [--minor|--major]`-Vertrag; wirft bei
  gleichzeitig gesetzten Flags. Keine Ableitung aus Commit-Message-Konventionen
  irgendwo im Modul.

`release.py` selbst (Tag setzen, Publish, State Machine) ist **nicht** Teil
von W3 — nur die Bausteine, die es später ohne weitere Versionslogik
verwenden kann.

## 5. Build-/Release-Override ohne Versionsverbrauch (W3-07)

`VOICESTT_BUILD_VERSION` erlaubt einen validierten Kandidatenwert, ohne die
`VERSION`-Datei dauerhaft zu ändern:

- Ein Kandidaten-Build (`VOICESTT_BUILD_VERSION=9.9.9-candidate.1 python -m build`)
  erzeugt Wheel/Sdist mit exakt diesem Wert in den Metadaten (siehe
  Packaging-Report), ohne `VERSION` im Source-Baum zu berühren — bytegenau
  geprüft (`diff` vor/nach dem Kandidaten-Build im Build-Container, siehe
  Packaging-Report §Build-Log).
- Wiederholte Auflösung ohne dazwischenliegenden echten Release ist
  deterministisch (`test_repeated_resolution_without_a_release_in_between_is_deterministic`).
- Ein ungültiger Override verbraucht nichts — er bricht sofort mit
  `SemVerError` ab, bevor irgendein Build-Schritt beginnt.
- Kein Tag, kein Release wurde in diesem Lauf erzeugt (Scope-Grenze W3
  eingehalten).

## 6. Konsistenznachweis (W3-06)

`tests/unit/test_version_authority.py::RuntimeConsistencyTests` beweist:

- `VoiceSTT.get_version()`, `VoiceSTT.__version__` und
  `identity.server_version()` liefern denselben Wert wie
  `_version.resolve_version()`.
- Ein gesetzter `VOICESTT_BUILD_VERSION`-Override propagiert identisch in
  Paket und Handshake (`test_build_override_propagates_to_package_and_handshake_identically`).
- Die FastAPI-App (`create_app().version`) liest dieselbe Authority
  (`test_fastapi_app_version_reads_the_same_authority`).
- Statische Prüfung, dass weder `identity.py` noch `setup.py` einen zweiten
  literal zugewiesenen SemVer-String enthalten
  (`test_no_second_hardcoded_semver_literal_in_*`).

Alle Tests: siehe `2026-08-30_W3_TEST_REPORT.md`.

## 7. Nicht angefasst (bewusst außerhalb des Scopes)

- `tests/contracts/protocol-v2-vectors.json` (`"2.0.0-test"`) und
  `docs/client-development/README.md` (Prosa-Erwähnung `2.0.0`) sind
  Test-Fixtures bzw. Dokumentationstext, keine Produktcode-Pfade. Ein
  vollständiger Doku-Versionsabgleich ist keine "minimale direkt betroffene
  Packaging-/Release-Doku" und daher nicht Teil dieses Laufs.
- `release.py` (State Machine, Tag, Publish) bleibt W5/W6.
