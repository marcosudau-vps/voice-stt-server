# Abweichung von der V1-Ein-Commit-Absicht

## Grund

Nach dem qualifizierten V1-Preservation-Fast-Forward auf
`main@0582bb13535f754c895438ffc4b1c2ce144e13bb` wurde bei der
abschließenden Publikationsprüfung eine sicherheitsrelevante
UNKNOWN/ABSENT-Verwechslung im Registry-Resume entdeckt. Eine
Korrektur vor Candidate/Publish erfordert einen neuen Commit; den
bereits gepushten Main-Commit umzuschreiben oder force-zupushen
wäre riskanter und widerspräche der bewahrten Historie.

## Entscheidung und Auswirkung

Der Nutzer hat nach Hinweis auf die Abweichung genau **einen** zweiten,
eng begrenzten Sicherheitscommit auf `main` freigegeben, unter der
Bedingung einer vollständigen Vorprüfung, damit danach kein weiterer
Main-Fix benötigt wird. Die 18 Arbeitscommits des alten
V1-Vorbereitungsbranches bleiben weiterhin außerhalb von `main`.
V1 besteht historisch aus Preservation-Commit und Sicherheitskorrektur;
der `v1.0.0`-Tag muss auf die qualifizierte **zweite** SHA zeigen.

Für V2 bleibt der geplante Zwei-Eltern-Merge möglich: erster Parent
ist der endgültige V1-Main-Commit, zweiter Parent der endgültige
V2-Canonical-Commit. Die Tree-Hash-Invariante und die notwendige
V2-Merge-CI gelten unverändert. Kein V2-Branch wird umgeschrieben.

## Weiterer Status

Sicherheitsfix auf einem getrennten Review-Branch vollständig testen,
dessen exakte SHA in CI qualifizieren und erst danach ohne Force-Push
nach `main` übernehmen. Candidate und öffentliche Writes bleiben bis
dahin gesperrt. Live-CI-Ergebnisse stehen im getrennten Evidenzpaket,
nicht als vorweggenommene Behauptung in dieser datierten Begründung.
