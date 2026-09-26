# V1 Clean-History Release-Prep – Soll/Ist-Prüfung

Stand vor dem ersten Push des neuen Clean-Branches am 26.09.2026.

| Planpunkt | Tatsächlicher Stand | Bewertung |
| --- | --- | --- |
| Historischen V1-Main-Anker bewahren | Neuer isolierter Worktree von `main@13c162950b944dc715fdd81983a7465f8eb0fd79`; bestehende Worktrees und V2-Branches nicht verändert. | Lokal erfüllt; Remote vor/nach Push erneut prüfen. |
| Geprüften V1-Tree reproduzieren | Vor den gezielten Clean-Governance-Anpassungen entsprach der neue Worktree exakt dem Tree `4c31adf4f3c2e149f6a224e4842c991af242e2f3` des grünen Arbeitsbranches. | Erfüllt; Anpassungen sind bewusst neue CI-/Dokumentations-Deltas. |
| Ein fokussierter Clean-Commit | Commit wird nach dieser Prüfung mit historischem `main` als einzigem Parent erzeugt; keine Arbeitscommits werden gemerged oder gesquasht. | Vor Commit noch offen. |
| GitHub-CI des neuen Branches | Beide Push-Trigger berücksichtigen `review/v1-release-prep-final-clean*`; der No-Publication-Guard prüft den tatsächlichen Branch. | Statisch/lokal geprüft; Remote-Runs noch offen. |
| Evidence-Diff vom richtigen Ursprung | `tools/v1_evidence_pack.py` verwendet den historischen Main-SHA als BASE; alle bekannten 67 V1-Änderungspfade sind einer Scope-Begründung zugeordnet. | Lokal erfüllt; Evidence-Job noch offen. |
| V2-Tree-Invariante | Der finale Release-Plan schreibt den späteren Zwei-Eltern-Merge und `TREE(Main nach V2-Merge) == TREE(final qualifizierter V2 Canonical)` ausdrücklich vor. | Dokumentiert; V2-Integration ist nicht Teil dieser Aktion. |
| Regression | Release-Vertragstests: 26 passed. Vollständige Windows-Suite mit nur prozesslokalem WMI-Fallback: 429 passed, 13 skipped, 78 subtests passed. Vier Release-YAML-Dateien parsebar, `git diff --check` ohne Fehler. | Lokale Prüfung bestanden; neue GitHub-CI zwingend. |
| Sicherheit und Veröffentlichungsgrenze | Kein Main-/V2-Push, kein Candidate, kein Tag, kein PyPI-/Registry-/GitHub-Release-Write. | Bisher erfüllt; vor Push erneut prüfen. |

Der Status bleibt **Prüfung offen**, bis der Ein-Commit-Branch auf seinem
exakten Remote-SHA beide CI-Runs einschließlich Evidenzpaket bestanden hat.
Ein Fehler wird nicht per Amend/Force-Push versteckt; falls nötig wird
ein neuer Clean-Branch vom historischen Main-Anker qualifiziert.
