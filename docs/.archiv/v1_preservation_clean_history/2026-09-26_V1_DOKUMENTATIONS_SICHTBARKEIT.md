# V1/V2-Dokumentationssichtbarkeit vor Main-Integration

Die erste qualifizierte Ein-Commit-Fassung enthielt den finalen
Releaseplan bereits unter `docs/`, aber die zentrale `docs/README.md`
verwies noch nicht darauf. Nach ausdrücklicher Main-Freigabe wurde
vor dem Main-Push ein neuer Clean-Branch direkt vom historischen
Main-Anker hergestellt; der alte qualifizierte Commit blieb erhalten.

Die neue Fassung ergänzt den sichtbaren Dokumentationseinstieg, den
eigenen V1/V2-Historienübergang und prüfbare Index-Verweise. Der
Evidence-Scope wurde um diese Dateien erweitert. Der neue Branch
erfordert eigene Tests und GitHub-CI auf seiner exakten SHA. Der
frühere CI-Lauf darf nicht als Qualifikation des neuen Commits gelten.

Noch offen zum Zeitpunkt dieser Notiz: neuer Commit/Tree, dessen
GitHub-CI und Main-Fast-Forward. Der V2-Branch bleibt unverändert;
die Portierung der Dokumente nach V2 Canonical ist ein Gate der
späteren V2-Qualifikation, keine nachträgliche Merge-Konfliktlösung.
