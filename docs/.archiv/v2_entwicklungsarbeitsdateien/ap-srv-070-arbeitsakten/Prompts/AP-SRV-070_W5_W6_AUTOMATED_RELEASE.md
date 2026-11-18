# AP-SRV-070 — W5/W6
# Release Candidate Qualification + Root-Gated Automated Publication

## Grundprinzip
Eine Versionsnummer darf vor dem Git-Tag nicht verbraucht werden.

Vor dem Tag wird alles geprüft, was deterministisch vorab prüfbar ist.
Nach dem Tag wird ein partiell fehlgeschlagener Release unter derselben Version fortgesetzt.

Ziele:
- PyPI
- GHCR
- Docker Hub
- GitHub Release

Versionsverwaltung: vollautomatisch.
Benutzereingabe ausschließlich: `patch | minor | major`.

---

# W5 — Release Candidate Audit

## Startbedingungen
Nur nach W4B Root-PASS, Remote Distributed == W4B SHA, cleanem Worktree und unverändertem Canonical.

## Full Regression
Mindestens:
- vollständige Unit-Suite
- v1/v2 Boundary
- Session/Activation Lifecycle
- Command/Timer/Races
- Settings
- Wake Runtime
- Kroko Artifact Contracts
- Packaging/Version Authority
- Installed Distribution Smoke
- Production Container Smoke
- Health/Shutdown
- `git diff --check`

## Kandidatenversion
Noch keinen Tag erzeugen.
Automation berechnet aus letztem gültigem Release + `patch|minor|major` die Kandidatenversion.

## Pre-Tag Artifact Build
Vor Tag erzeugen und qualifizieren:

Python:
- wheel
- sdist
- Metadata
- SHA256
- twine check
- installierter Smoke

Container:
- Production Image
- Version/Commit/OCI-Metadaten
- Wake/Kroko Smoke
- Image ID/Digest soweit lokal verfügbar

Diese Kandidatenartefakte müssen exakt der später veröffentlichten Version entsprechen.

## External Preflight
Soweit reversibel prüfen:
- PyPI Publishing-Konfiguration / Projektname / Metadaten
- GHCR Auth/Permissions/Ziel
- Docker Hub Auth/Permissions/Ziel
- GitHub Actions Permissions/Secrets/Environments

Keine Secrets ausgeben.

## Release State Machine
Mindestens Zustände:
- candidate_computed
- artifacts_built
- artifacts_qualified
- canonicalized
- ci_passed_on_exact_sha
- tag_created
- pypi_published
- ghcr_published
- dockerhub_published
- immutable_artifacts_verified
- github_release_created
- moving_aliases_updated
- release_complete

Wiederholte Läufe müssen erfolgreiche Zustände erkennen, verifizieren und überspringen.

## W5 Evidence
`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5\`

Mindestens:
- `W5_RC_AUDIT.md`
- `W5_ARTIFACT_MANIFEST.md`
- `W5_RELEASE_PREFLIGHT.md`
- `W5_RELEASE_STATE_MACHINE.md`
- `W5_STATE.md`

Am Ende nur:
`READY_FOR_ROOT` oder `BLOCKED`

Kein Tag. Kein Publish.

---

# ROOT GATE
Root prüft adversarial:
- Chain-of-custody
- finalen Distributed Diff
- Requirement Traceability W0-W5
- Race/Stale Callback/Close/Replay/Atomicity
- Package Resources
- Kroko Free/Pro/Secret-Grenzen
- Container-Inhalt/Shutdown
- Release State Machine
- Pre-Tag-Sicherheitsprinzip
- Resume-Semantik
- Repo-Hygiene

Nur bei ROOT PASS darf W6 starten.

---

# W6 — Canonicalization + Automated Publication

## Canonical Aggregate
Genau ein AP-SRV-070 Aggregate Commit auf Canonical.
Parent: kanonischer SRV-060 Stand.
Tree: exakt finaler Root-geprüfter Distributed Source Tree.

## Exact-SHA CI
Vor Tag muss CI auf exakt dem Canonical SHA grün sein:
- Tests
- Package Build/Smoke
- RC Artifact Qualification
- Production Container Qualification
- Version Consistency

Wenn FAIL: kein Tag. Kandidatenversion bleibt verfügbar.

## Kandidatenversion
Automation übernimmt die bereits W5-qualifizierte Kandidatenversion.
Kein manuelles Editieren.

Vor Tag prüfen:
- Kandidatenversion stimmt
- Tag existiert nicht
- PyPI-Version nicht widersprüchlich belegt
- qualifizierte Artefakte vorhanden
- exact-SHA CI grün

## Tag
Erst jetzt `v<version>` auf exakt dem qualifizierten Canonical SHA.
Kein Re-Tagging auf anderen Commit.

## Publication
Semantische Reihenfolge:
1. PyPI immutable Version
2. GHCR immutable Version
3. Docker Hub immutable Version
4. Verifikation aller drei Ziele
5. GitHub Release
6. bewegliche Container-Aliase
7. finale Verifikation
8. release_complete

## Resume-Regel
Wenn z. B. `v2.4.0` existiert, PyPI und GHCR erfolgreich sind, Docker Hub aber fehlschlägt:
- keine 2.4.1 berechnen
- `2.4.0` wieder aufnehmen
- Tag/SHA verifizieren
- erfolgreiche Ziele verifizieren/überspringen
- fehlenden Schritt erneut ausführen
- danach fortsetzen

Ein Schritt gilt nur als erledigt, wenn das externe Ziel das erwartete immutable Artefakt nachprüfbar enthält.

## Container Tags
Immutable:
- `<version>`
- optional Commit SHA

Beweglich erst ganz am Ende:
- `latest`
- optional Major
- optional Major.Minor

## PyPI
Exakt die qualifizierten wheel/sdist-Artefakte veröffentlichen.
Danach Fresh Install aus echtem PyPI außerhalb des Sourcebaums:
- Version
- Package Resources
- Wake Catalog
- Server Import/Entry Point

## GHCR + Docker Hub
Publish des qualifizierten Production Images.
Danach frischer Pull über immutable Version:
- Digest
- Version/Commit
- Health
- Wake endpoint
- Kroko Runtime
- Shutdown

## GitHub Release
Erst nach erfolgreichen/verifizierten immutable Publishes.
Enthält mindestens:
- Version
- Canonical SHA
- wheel/sdist SHA256
- PyPI
- GHCR Digest
- Docker Hub Digest
- Release Notes
- bekannte Grenzen, z. B. Wake calibration pending falls weiterhin blockiert

## Abschluss
Finale Zustände nur:
- `RELEASE_COMPLETE`
- `RELEASE_INCOMPLETE_RESUMABLE`

Nie eine neue Version starten, solange ein getaggter Release resumierbar unvollständig ist.

## Rückgabe
Schick mir alle Evidence-Dateien aus den jeweiligen W5/W6-Ordnern.
