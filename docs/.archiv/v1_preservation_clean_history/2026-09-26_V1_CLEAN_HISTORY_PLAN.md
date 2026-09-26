# V1 Clean-History Release-Prep – Gesamtplanung

## Ausgangslage

`main` steht auf dem historischen V1-Commit
`13c162950b944dc715fdd81983a7465f8eb0fd79`. Der grüne
Vorbereitungsstand `release/v1.0.0-prep@1ca4d32a5736e1e0a599ad5fe1417ec96fdf189b`
hat 18 Commits nach dieser Basis. Der ältere Ein-Commit-Clean-Branch
`review/v1-release-prep-clean` enthält die späteren Korrekturen nicht.
Die V2-Branches stammen ebenfalls von der historischen Main-Basis ab.

## Ziel und Nicht-Ziele

- Einen neuen V1-Clean-Branch direkt von der unveränderten Main-Basis
  erzeugen und den geprüften V1-Release-Tree bewusst als **einen**
  fokussierten Commit konservieren.
- Branch-CI und Evidence Pack auf genau diesem neuen Commit vollständig
  erneut ausführen; den alten Run nicht als Freigabe des neuen Commits
  ausgeben.
- Den finalen Release-Plan an die V1/V2-Historienstrategie anpassen:
  Main-Integration nur nach eigener Freigabe; beim späteren V2-Merge
  `TREE(Main nach Merge) == TREE(final qualifizierter V2 Canonical)`.
- Keine Änderungen an `main`, V2 Canonical/Distributed, `build/vps/**`,
  produktiver VPS-Instanz, Candidate, Tag oder öffentlicher Distribution.

## Umsetzung

1. Auf frischem, separatem Worktree vom exakten Main-SHA den V1-Tree
   aus dem geprüften Vorbereitungsbranch übernehmen; Tree-Hash vor
   weiteren nötigen Release-Governance-Korrekturen vergleichen.
2. Normalen CI-Push-Trigger für neue Clean-Branches öffnen, den
   No-Publication-Guard auf den tatsächlichen Branch beziehen und die
   Evidence-Diff-Basis auf den historischen Main-Commit stellen.
3. Release-Plan, dauerhaft gültige Dokumentation und Vertragstests
   konsistent aktualisieren. Alle Änderungen selektiv prüfen.
4. Lokale gezielte Tests, komplette Server-Suite, Diff-/YAML-/Shell-
   Checks ausführen; anschließend einen Commit mit Parent `13c1629`
   erzeugen und nur den neuen Clean-Branch pushen.
5. Die beiden GitHub-CI-Runs am neuen Commit abwarten. Bei einem Fehler
   nicht amend/force-pushen: Ursache beheben und nötigenfalls einen
   weiteren neuen Clean-Branch von `main` qualifizieren.

## Risiken und Abnahme

- Workflow-Trigger oder Evidence-Base könnten noch auf den alten
  Korrekturbranch zeigen; beides wird explizit getestet.
- Ein gleicher Dateibaum mit neuer Commit-ID ist **nicht** automatisch
  qualifiziert; CI muss auf dem neuen SHA grün sein.
- Der spätere V2-Merge darf V1-Release-Dateien nicht blind mit V2 mischen.
  Der finale V2-Tree bleibt Authority und wird vor V2-Publikation per
  Tree-Hash und vollständiger CI gegen den tatsächlichen Merge geprüft.
- Abschluss dieses Arbeitsschritts: ein Clean-Commit mit historischem
  Main als einzigem Parent, erfolgreiche Windows-/Linux-Free/Pro-CI,
  geprüfte Evidenz und unveränderte Main-/V2-Refs. Public Release und
  Main-Integration bleiben gesonderte Gates.
