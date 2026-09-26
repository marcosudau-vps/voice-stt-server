# V1-Erstrelease und späterer V2-Historienübergang

Stand: 26.09.2026. Einstieg für die spätere V2-Releasearbeit. Der
[finale V1-Releaseplan](v1-release-final-plan.md) regelt die
Publikationsreihenfolge; dieses Dokument regelt ausschließlich den
Git-Historienübergang. V1 und V2 sind bewusst unterschiedliche
Produktstände. V2-Code wird nicht in V1 zurückportiert.

## Ausgangslage und unveränderliche Anker

- Historischer gemeinsamer V1-`main`-Anker:
  `13c162950b944dc715fdd81983a7465f8eb0fd79`.
- Die V1-Vorbereitung `release/v1.0.0-prep` enthält 18 Arbeitscommits,
  die **nicht** zur dauerhaften `main`-Historie werden sollen.
- Der V1-Preservation-Commit `0582bb13535f754c895438ffc4b1c2ce144e13bb`
  ist genau ein Nachfahre dieses Ankers. Er wurde nach grüner CI und
  ausdrücklicher Main-Freigabe per Fast-Forward `main`.
- Beim abschließenden Publish-Audit wurde ein Registry-UNKNOWN-Guard-Fehler
  entdeckt. Der Nutzer hat **genau einen** zweiten, eng begrenzten
  Sicherheitscommit auf `main` nach vollständiger erneuter Qualifikation
  freigegeben. Der `v1.0.0`-Tag muss auf diesen finalen V1-Main-Commit
  zeigen; der erste Preservation-Commit bleibt sein Parent und wird
  nicht umgeschrieben. Es gibt keinen Grund, die 18 Arbeitscommits
  nachträglich einzufügen.
- V2 Distributed (`feat/einheitliche-triggerarchitektur-distributed`)
  und V2 Canonical (`feat/einheitliche-triggerarchitektur`) gingen vom
  historischen Main-Anker aus. Ihre damaligen Referenzen waren
  `f7d2b3ccd07757172a45b371829b04bcedffab4b` und
  `c82923fc6ce889b4dfbbde1f9877b8b76481a1e8`. Für den
  tatsächlichen V2-Merge sind **neu qualifizierte finale** Referenzen
  zu ermitteln; diese beiden SHAs sind keine V2-Releasefreigabe.

V1-Main und V2 Canonical sind danach divergiert. V2 kann nicht einfach
per Fast-Forward auf den V1-Main-Zweig gelegt werden. Ein Rebase oder
Force-Push der V2-Branches ist hierfür nicht nötig und würde die
bestehenden Arbeits- und Evidenzreferenzen unnötig verändern.

## Vor dem V2-Merge

1. V2 Canonical samt AP-SRV-070 W6 und Root-PASS fertigstellen.
   Fehlende V2-Release-Workflows sowie diese dauerhaft nützlichen
   V1/V2-Übergangsdokumente **vor** dem V2-Source-Freeze bewusst in
   Canonical übernehmen. Sie gehören dann zum qualifizierten V2-Tree.
   Der bisherige Canonical-Zwischenstand enthält die Release-Workflows
   noch nicht; Distributed ist nicht automatisch die Authority.
2. Den finalen V2-Canonical-Commit und seinen Tree-Hash notieren.
   V2-CI und Produktabnahme auf genau diesem Commit durchführen. Den
   V1-Tag, die V1-Artefakt-Hashes und den V1-Main-Commit getrennt
   festhalten. Keine V1-Release-Workflows oder Packaging-Dateien
   ungeprüft mit V2-Code kombinieren.
3. In einem neuen Integrationsbranch von dann aktuellem `main` einen
   bewussten Zwei-Eltern-Merge mit dem finalen V2-Canonical-Commit
   vorbereiten. Konflikte so lösen, dass der **gesamte Ergebnisbaum**
   exakt dem qualifizierten V2-Canonical-Tree entspricht. Das betrifft
   auch hinzugefügte/entfernte Dateien, Dokumentation und Workflows;
   eine nur oberflächlich erfolgreiche Merge-Konfliktlösung genügt nicht.
4. Vor V2-Publikation prüfen: Merge-Commit hat V1-Main und finalen V2
   Canonical als Eltern, `v1.0.0` zeigt unverändert auf den V1-Commit,
   und `TREE(Main nach V2-Merge) == TREE(final qualifizierter V2 Canonical)`.
   Die vollständige V2-CI läuft auf dem **tatsächlichen Merge-Commit**,
   nicht nur auf dem vorherigen Canonical-Commit. Erst nach grünem
   Ergebnis und eigener V2-Freigabe `main` aktualisieren.

Zur Prüfung der Tree-Gleichheit die beiden Ausgaben von
`git rev-parse <merge-commit>^{tree}` und
`git rev-parse <final-v2-canonical>^{tree}` vergleichen; für die
Eltern `git rev-list --parents -n 1 <merge-commit>` verwenden.
Zusätzlich die V1-Tag-Zuordnung und die tatsächlichen Workflow-Dateien
im Ergebnisbaum prüfen. Wenn die Trees nicht gleich sind, **STOP**:
keinen halb gemischten Merge freigeben. Nötige Änderungen zuerst in
V2 Canonical aufnehmen, dort erneut qualifizieren und erst dann den
Integrationsmerge neu vorbereiten.

## Warum diese Reihenfolge wichtig ist

Der V1-Commit bleibt über den ersten Merge-Elternpfad in `main`
auffindbar; V2 Canonical bleibt über den zweiten Elternpfad erhalten.
Das veröffentlichte V2-Dateisystem ist trotzdem exakt der eigens
qualifizierte V2-Stand. Ein `git diff` ohne Änderungen zwischen beiden
Trees ist der entscheidende Inhaltsbeweis; eine bloße grüne CI des
V2-Feature-Branches oder ein konfliktfreier Merge beweist das nicht.

Der Client wird für V1 erst **nach** vollständig erfolgreichem
Server-Release separat veröffentlicht. Seine 1.0.0-Kompatibilität ist
zu dokumentieren; ob spätere Client-/Serverversionen gekoppelt bleiben,
ist ausdrücklich offen.
