# V1 Registry-UNKNOWN-Publish-Guard – Gesamtplanung

## Ausgangslage

Der auf `main@0582bb1` veröffentlichte (noch nicht gestartete)
`release-publish.yml` benutzt in Docker-Hub-, GHCR- und Alias-Jobs
`docker buildx imagetools inspect` mit unterdrücktem stderr und
`|| true`. Damit werden Registry-Timeout, 401/403, Rate-Limit oder
andere Lesefehler genau wie ein fehlender Tag als leerer Digest
behandelt. Der dokumentierte Vertrag verlangt dagegen
ABSENT/MATCH/CONFLICT/UNKNOWN und bei UNKNOWN einen Stopp vor Write.
Außerdem wird die Docker-Hub-Authentifizierung erst nach beiden
PyPI-Projekten geprüft; ein ungültiger Token könnte einen unnötig
partiellen öffentlichen Release erzeugen.
Die begleitende Durchsicht ergab zwei verwandte Grenzfälle: Ein
zusätzliches fremdes PyPI-Artefakt unter Version 1.0.0 konnte trotz
zweier MATCH-Wheels unbeanstandet bleiben; ein fehlgeschlagener
GitHub-Release-Read wurde wie eine nicht vorhandene Release-Seite
behandelt.

## Ziel und Nicht-Ziele

- Registry-Probes unterscheiden explizit erfolgreiche Reads,
  eindeutig fehlende Tags und alle unklaren Fehler; UNKNOWN stoppt.
- Docker-Hub- und GHCR-Anmeldung werden vor dem ersten PyPI-Upload
  ohne öffentlichen Write geprüft. Die tatsächlich im GitHub-
  Environment hinterlegte Docker-Hub-Identität weist für beide
  Zielrepositories zusätzlich `pull,push`-Scope per read-only
  Registry-Token-Abfrage nach.
- Unerwartete PyPI-Dateien ergeben stets CONFLICT; GitHub-Release-
  Lesefehler ergeben UNKNOWN. Die GitHub-Release-Erstellung setzt
  einen bereits existierenden Git-Tag voraus.
- Candidate- und Publish-Artefaktidentität, Version 1.0.0,
  Publikationsreihenfolge und spätes Git-Tag bleiben unverändert.
- Kein Candidate, PyPI-/Registry-Write, Tag oder GitHub Release als
  Teil der Implementierung. Keine Änderung an V2-Branches.

## Umsetzung

1. Kleinen quellkontrollierten Probe-Helper für `imagetools inspect`
   einführen. Erfolg ohne parsebaren Digest ist UNKNOWN; nur
   eindeutige Tag-Abwesenheit ist ABSENT; 401/403, Timeout, 429,
   Transport-/Parserfehler sind UNKNOWN. Gefundene Digests werden
   exakt mit dem Candidate verglichen.
2. Alle schreibenden Docker-Hub-/GHCR-/Alias-Jobs verwenden diesen
   Helper statt `inspect ... || true`. Vor den PyPI-Jobs prüft ein
   reiner Read-only-Infrastruktur-Job beide Logins und alle Zielrefs.
3. Tests für ABSENT, MATCH, CONFLICT und UNKNOWN einschließlich
   fehlerhafter stderr-/Digest-Fälle ergänzen; Workflow-Gates statisch
   prüfen und vollständige Windows-/Linux-/CI-Regression ausführen.
   Die PyPI- und GitHub-Release-Resume-Grenzen mitprüfen.
   Den Docker-Hub-Scope-Check zusätzlich als rein manuellen,
   vorab ausführbaren GitHub-Actions-Workflow bereitstellen.
4. Gegenprüfung und Abweichungen gesondert dokumentieren. Der Fix
   bleibt auf einem eigenen Branch, bis der Nutzer einen **zweiten**
   eng begrenzten Main-Commit trotz ursprünglicher Ein-Commit-Absicht
   ausdrücklich akzeptiert.

## Abnahme und Restgrenzen

Ein Read-only-Probe kann ohne transaktionales Compare-and-Swap der
Registries keine Race-Condition zwischen Probe und Push ausschließen;
exakte Digest-Verifikation und Stop bei Konflikt bleiben deshalb
zusätzlich Pflicht. Private, für das CI-Token unlesbare Tags sind
UNKNOWN, nicht vermeintlich ABSENT. Keine echte Publikation wird zum
Testen dieses Guards vorgenommen.
