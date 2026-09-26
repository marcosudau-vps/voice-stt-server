# V1 Registry-UNKNOWN-Publish-Guard – Soll-/Ist-Vergleich

Stand: 26.09.2026, Review-Branch vor zweitem Main-Fast-Forward.

| Planpunkt | Ist | Bewertung |
| --- | --- | --- |
| Registry-Reads klassifizieren statt Fehler als fehlende Tags zu deuten | `tools/v1_registry_probe.py` trennt ABSENT, MATCH, CONFLICT und UNKNOWN. Explizit fehlender Tag ist der einzige ABSENT-Pfad; Auth-, Transport-, Parser- und Serverfehler stoppen. | Umgesetzt, Unit- und Live-Read-Probes lokal geprüft. |
| Vor PyPI Registry- und Token-Zustand prüfen | `registry-preflight` authentifiziert beide Registries, prüft Candidate-Digests sowie Free/Pro-Exact- und Alias-Zielrefs. Docker Hub `pull,push`-Claims für beide Repositories werden ohne Upload geprüft. | Implementiert; echter GitHub-Secret-Check erst nach qualifiziertem Main-Push über separaten manuellen Read-only-Workflow möglich. |
| Keine blinden Registry-Writes und unmittelbare Post-Write-Prüfung | Docker-Hub-, GHCR- und Alias-Jobs verwenden denselben Helper vor und nach jedem Tag-Write; CONFLICT/UNKNOWN stoppen. | Implementiert und statisch getestet; kein öffentlicher Tag-Write zur Probe. |
| PyPI- und GitHub-Release-Grenzfälle härten | Unerwartete Datei bei 1.0.0 ergibt immer CONFLICT. GitHub-Release-Lesefehler ist UNKNOWN; `gh release create --verify-tag` verhindert implizite Tag-Erstellung. | Implementiert und lokal getestet. |
| Version, Candidate-Bindung, Reihenfolge und V2-Historie bewahren | Version 1.0.0, Candidate-SHA/Tree, Free → Pro → Docker Hub → GHCR → Aliase → Prüfung → Tag → GitHub Release bleiben. Der zweite V1-Sicherheitscommit wird V2-seitig als erster Merge-Parent dokumentiert. | Statisch geprüft; echte Candidate-/Publikationsläufe weiter gesperrt bis gesondertem Go. |
| Gegenprüfung und vollständige Regression | Neue Unit-/Workflowtests, YAML-/Shell-Prüfung, vollständige lokale Suite und Native GitHub CI auf exakter Review-SHA. | Lokal: 442 bestanden, 13 übersprungen, 78 Subtests bestanden; 43 Workflow-Bash-Skripte syntaxgeprüft. CI-Ergebnis wird im gesonderten Evidenzpaket nachgereicht, nicht vorweggenommen. |

## Bekannte Restgrenzen

- Registry-Probe und Tag-Write sind keine atomare Transaktion; nach dem Write wird deshalb der exakte Digest nochmals geprüft.
- Für GHCR kann ein nicht eindeutig lesbarer privater/fehlender Tag UNKNOWN bleiben und den Publish-Lauf vor PyPI anhalten. Das ist ein absichtlicher Sicherheitsstopp, kein Beweis für einen fehlenden Tag.
- Die tatsächliche Berechtigung des GitHub-Environment-Secrets lässt sich lokal nicht auslesen. Der manuelle Read-only-Workflow prüft genau dieses Secret nach dem Main-Push.
- Keine öffentliche Publikation ist Teil dieses Vergleichs. Exakte CI-/Secret-Prüfergebnisse werden im Release-Evidenzpaket festgehalten.
