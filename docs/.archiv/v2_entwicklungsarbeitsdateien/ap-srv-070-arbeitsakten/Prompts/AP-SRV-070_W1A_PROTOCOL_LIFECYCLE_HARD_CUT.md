# AP-SRV-070 — W1A
# Protocol / Session / Activation / Lifecycle Hard Cut

## 0. Auftrag

Führe den ersten produktiven Teilblock von AP-SRV-070 aus.

W1A ist ausschließlich zuständig für:

- Protocol-v1/v2-Grenzen
- Session-/Activation-/Command-/Timer-Lifecycle
- bestätigte Legacy-/Compatibility-Seams in diesem Bereich
- Version-/Commit-/Protocol-Metadaten, soweit runtime-relevant
- negative Boundary-Regressionen

Nicht zuständig:

- Wake-Word-spezifische Runtime-Bereinigung außer zwingender Abhängigkeit
- Packaging
- Docker
- große Dokumentationsreorganisation
- Release/Publication

W0 ist die Scope Authority.

## 1. W0 muss abgeschlossen sein

Lies vollständig:

P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prep\W0\

Pflichtdateien:

2026-08-29_W0_DELTA_REVALIDATION.md
2026-08-29_W0_SCOPE_MATRIX.md
2026-08-29_W0_EXECUTION_BACKLOG.md

Wenn W0 nicht eindeutig COMPLETED ist oder W1 nicht planbar ist:

STATUS: BLOCKED

Nicht improvisieren.

## 2. Git-Ausgangslage

Server Feature/Common-Dir Repository:

P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\einheitliche-triggerarchitektur

Permanent Distributed:

feat/einheitliche-triggerarchitektur-distributed

Ausgangs-SHA vor AP-SRV-070:

1e74fec3096778d78c4f91e3916ef272c762ebd3

Canonical:

feat/einheitliche-triggerarchitektur
c82923fc6ce889b4dfbbde1f9877b8b76481a1e8

Ausgangs-TREE beider permanenten Linien:

de6fe364545b508a47a87ead67a01c5732477e71

Vor Arbeit:

- Remote-Refs prüfen.
- Distributed muss noch auf 1e74fec... stehen.
- Canonical muss noch auf c82923f... stehen.
- TREE equality muss gelten.
- Canonical-Workspace muss clean sein.

Abweichung => STATUS: BLOCKED.

## 3. Arbeitsbranch / Worktree

Für AP-SRV-070 genau EIN temporärer Arbeitsworktree:

Branch:

work/AP-SRV-070

Worktree:

P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070

Falls weder Branch noch Worktree existieren:

- Branch exakt von Distributed 1e74fec... erzeugen.
- Worktree daran anlegen.

Falls bereits vorhanden:

- Identität prüfen.
- Keine Löschung / kein Reset.
- Unerklärte Abweichung => STATUS: BLOCKED.

Dieser Worktree soll später für W1B/W2/... weiterverwendet werden.

Kein neuer separater Worktree pro Teilblock.

## 4. Scope-Ermittlung aus W0

Nimm aus W0 ausschließlich Aufgaben, deren Zielbereich inhaltlich zu W1A gehört:

- Protocol
- WebSocket/HTTP Protocol Boundary
- v1/v2 Routing
- Session Identity
- Activation Lifecycle
- Command/Timer Lifecycle
- terminal/finalized/closing seams
- server/protocol/version metadata
- runtime Compatibility-Seams in diesen Bereichen

W0-Klassifikation beachten:

CONFIRMED_REMOVE:
  darf entfernt werden, aber erneut konkrete Referenzen prüfen.

MIGRATE_BEFORE_REMOVE:
  Migration zuerst vollständig implementieren und testen.

KEEP_REQUIRED:
  nicht entfernen.

NEEDS_RUNTIME_PROOF:
  erst Proof/Test herstellen; ohne Beweis nicht entfernen.

SUPERSEDED_ALREADY:
  keine unnötige Änderung.

OUT_OF_SCOPE:
  nicht anfassen.

Keine eigene Scope-Ausweitung.

## 5. Pflichtprüfung: ActivationController.finalized()

Falls W0 diesen Punkt als offen/relevant klassifiziert:

- alle direkten/indirekten Caller bestimmen
- Lifecycle-Verantwortung bestimmen
- prüfen, ob Entfernung semantisch sicher ist
- RED-Test für tatsächlich zu schließende Lücke
- erst danach entfernen/ersetzen

Falls KEEP_REQUIRED:
nicht ändern.

## 6. Protocol Hard Boundary

W1A muss die von W0 geforderten negativen Fälle umsetzen bzw. beweisen.

Mindestens prüfen, soweit aktuelle Architektur diese Trennung vorsieht:

- v1 erhält keine v2-Envelopes
- v2 erhält keine v1-Wire-Messages
- v1/v2 Session-Identifier werden nicht vermischt
- falsche/inkompatible Protocol-Version wird deterministisch behandelt
- Command-/Event-Routing kann nicht auf falsche Protocolwelt leaken
- Version-/Commit-/Protocol-Metadaten widersprechen sich nicht

Tests bevorzugt RED-FIRST, wenn ein Defekt/Leak existiert.

Kein künstlicher RED-Test für bereits korrektes Verhalten.
Dann bestehendes Verhalten durch Regressionstest festschreiben.

## 7. Legacy Hard Cut

Nur durch W0 bestätigte runtime-relevante Altpfade in diesem Bereich bearbeiten.

Vor jeder Entfernung:

1. Symbol-/Pfadsuche
2. direkte Caller
3. indirekte Registrierung
4. Reflection/dynamische Nutzung
5. Imports/Side Effects
6. Tests
7. Doku-/Config-Abhängigkeit, soweit runtime-relevant

Entfernung ohne Reachability-Beweis verboten.

Keine historischen Archive ändern.

## 8. Tests / adversarial validation

Mindestens:

- alle neu/angepassten gezielten Tests
- relevante Protocol-v2 Tests
- Session-/Activation-Lifecycle Tests
- Command-/Timer Tests
- Fehler-/Close-/Replay-Fälle, wenn betroffen
- Race-Tests, wenn Nebenläufigkeitsseams betroffen sind
- git diff --check

Bei Race-Fixes:
deterministische Synchronisation bevorzugen, keine Sleeps als Hauptbeweis.

Keine komplette Release-/Packaging-/Docker-Prüfung in W1A.

## 9. Dokumentation

Nur unmittelbar notwendige aktive technische Doku anpassen, wenn Runtimevertrag
sonst falsch wäre.

Keine große W2-Dokumentationsreorganisation.

Historische Akten unverändert.

## 10. Commit / Distributed Publication

Wenn alle W1A-Gates PASS:

- genau EIN Commit für diesen Agentenrun
- auf work/AP-SRV-070

Commit subject:

feat(server): finalize protocol and lifecycle boundaries

Danach:

- Commit SHA/TREE erfassen
- Working tree clean
- Canonical unverändert prüfen
- Remote Distributed erneut prüfen

Push diesen Commit direkt und ausschließlich als FAST-FORWARD auf:

feat/einheitliche-triggerarchitektur-distributed

Kein Force.

Der neue Distributed HEAD ist damit der eingereichte W1A-Agentenrun und
Ausgangsbasis für W1B.

Canonical bleibt unverändert.

## 11. Evidence

Erzeuge ausschließlich außerhalb des Produktrepos unter:

P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W1A\

mindestens:

2026-08-29_W1A_IMPLEMENTATION_REPORT.md
2026-08-29_W1A_TEST_REPORT.md
2026-08-29_W1A_SCOPE_TRACE.md
2026-08-29_W1A_STATE.md

STATE muss enthalten:

- W0 IDs umgesetzt / nicht umgesetzt / warum
- Parent Distributed SHA
- W1A SHA
- W1A TREE
- Remote Distributed SHA nach Push
- Canonical SHA unverändert
- Git status
- Tests
- Blocker / offene Punkte für W1B/W2

## 12. Stop-Gates

STATUS: BLOCKED ohne Push wenn:

- W0 fehlt/unklar
- Remote Distributed nicht erwarteter Ausgangsstand
- Canonical verändert
- Worktree/Branch unerwartet existiert
- unpreserved Dirty State vorhanden
- W0-Klassifikation widersprüchlich
- Remove-Candidate nicht beweisbar tot
- Tests rot
- git diff --check relevant fehlschlägt
- Push Force erfordern würde

## 13. Rückgabe

STATUS

BASELINE

W0 SCOPE USED

IMPLEMENTED

REMOVED / MIGRATED / KEPT

PROTOCOL BOUNDARY

TESTS

COMMIT
parent
sha
tree

DISTRIBUTED
before
after
fast-forward

CANONICAL
sha unchanged

FILES
W1A evidence folder

NEXT
W1B ready: JA/NEIN
reason
