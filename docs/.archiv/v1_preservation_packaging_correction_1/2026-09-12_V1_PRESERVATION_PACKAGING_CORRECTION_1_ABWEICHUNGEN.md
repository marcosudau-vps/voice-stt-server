# V1 Preservation Packaging Correction 1 – Abweichungen

## Nachgetragene Archivregistrierung

- Grund: Die Korrektur wurde zunächst in einer externen GitHub-fähigen
  Chat-Session begonnen. Bei der lokalen Fortsetzung existierten der
  Korrekturbranch und mehrere gepushte Commits bereits.
- Auswirkung: Diese repository-interne Archivplanung wurde nicht vor dem
  allerersten Korrekturcommit angelegt.
- Entscheidung: Der unveränderte externe Scope Lock bleibt die ursprüngliche
  Planung; dieses Archiv dokumentiert die Fortsetzung, Prüfung und tatsächliche
  Abnahme transparent nach.
- Status: Akzeptierte Prozessabweichung; der Soll-/Ist-Vergleich wird erst nach
  den realen Builds, CI und Operator-Smokes abgeschlossen.

## Historischer Candidate-Workflow-Datensatz

- Grund: GitHub registrierte für eine zwischenzeitlich ungültige
  `release-candidate.yml` automatisch den parse-only Push-Run `34703916749`.
- Auswirkung: Ein Run-Datensatz existiert, obwohl der Candidate nie manuell
  gestartet wurde; der Run hatte keine Jobs und keine Publikationswirkung.
- Entscheidung: Nicht löschen oder umdeuten, sondern im No-Publication-Guard
  und Risk Register ausdrücklich offenlegen.
- Status: Historische Evidenz; manuelle Candidate- und Publish-Dispatches
  bleiben bis zur späteren Autorisierung gesperrt.
