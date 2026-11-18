# Korrekturauftrag nach externer ROOT-Gesamtabnahme (2026-11-11)

Du bist `doc-orchestrator` im bereits eingerichteten Dokumentationsprojekt `P:\GithubRepos\marcosudau-vps\voice-stt-server\2026_11_06_Server_Dokunentation`.

**Lies zuerst vollständig den unabhängigen Bericht `workflow/reviews/ROOT-EXTERNAL-2026-11-11.md`.** Das externe Urteil ist `ROOT_CHANGES_REQUESTED`, nicht `ROOT_PASS`. Alle 104 Unterkapitel sind bereits erstellt; starte **keine** Neuschreibung des Handbuchs, keinen Produktcodeumbau und keine zusätzlichen Kapitel.

Arbeite ROOT-001 bis ROOT-005 nacheinander gezielt ab:

1. **ROOT-001:** 79 Entwurfskennzeichnungen und 13 `DRAFTED`-Statusmarker in final intern reviewten Kapiteln, `docs/v2-handbuch/README.md` sowie Root-`README.md` auf den tatsächlich bestehenden Integrationsstand korrigieren. Externe ROOT-Freigabe **nicht** im Voraus behaupten. Navigation und Markdown-Links erhalten.
2. **ROOT-002:** Für 42 Kapitel ohne konkrete Reviewer-Session-ID die tatsächlichen historischen `doc-reviewer`-Sessions über OpenCode recherchieren, korrekt in den Reviewakten belegen. **Keine IDs halluzinieren.** Wo echte unabhängige Prüfläufe nicht rekonstruierbar sind, durch `doc-reviewer` (Muse Spark 1.3 Contributor) erneut am angegebenen Originalquellcode prüfen und mit neuen Session-IDs nachweisen. Historische Reviews bleiben erhalten.
3. **ROOT-003:** 43 Diagramm-Briefs mit tatsächlichen Mermaid-Blöcken abgleichen. 42 IDEA-Kapitel mit 77 Blöcken, 13 NOT_REQUESTED-Kapitel mit 27 weiteren Blöcken, Pilot 02.03 mit 2 = insgesamt 106. Status-/Vorschlagsentscheidungen belegbar machen und im Abschlussbericht korrekt darstellen. Zusätzliche freiwillige Diagramme nicht grundlos löschen.
4. **ROOT-004:** `09.08 Dokumentationsstand`: den historischen Zwischenstand `103 INTEGRATED + 1 IN_REVIEW` korrekt als Zeitpunkt kennzeichnen, den aktuellen Zustand `104 INTEGRATED` und aktuelle Rundenstatistik ergänzen; Faktenakte und unabhängigen Reviewer für inhaltliche Änderungen verwenden.
5. **ROOT-005:** Das tatsächliche Mermaid-Rendering mit zugelassenen, kostenlosen Werkzeugen prüfen, sofern möglich. Die npm-Sicherheitsregel `EALLOWSCRIPTS` **nicht** aufheben oder umgehen. Bei fehlender Möglichkeit transparent Nicht-Prüfbarkeit nachweisen, keinen Erfolg behaupten.

**Agenten:** Orchestrator und unabhängiger Reviewer Muse Spark 1.3 Contributor; Researcher und Writer DeepSeek V4.1 Flash. Rollen wirklich getrennt aufrufen, wo fachliche Änderungen/Reviews notwendig werden. Für bloße Status-/README-Redaktion genügt ein nachvollziehbarer Deltatest. Den bereits extern abgenommenen Activation-Pilot nicht fachlich umschreiben.

**Quellstand:** `a8993c5c68042d996eab680d84a5b138a214bb5d`, exakt mit `git rev-parse HEAD` prüfen. Keine Branch- oder Quellstandsdrift.

**Abschlussgates:** `python tools/workflow_cli.py refresh`, `validate` und `status`; alle 104 Registry-Einträge `INTEGRATED` und `PASS`; Review-/Subagentenbelege; Links; vollständige Katalogregistrierungen (18 Events, 5 Commands, 15 Results, 19 Settings, 37 Routen); Diagramm-Nachweise; geänderte Kapitel auf Verständlichkeit/Quelltreue prüfen. Keine Produktcodeänderungen, kein Git-Push/Merge/Release, keine unfreigegebenen kostenpflichtigen Modelle.

**Ergebnis:** Erstelle einen detaillierten Korrekturbericht mit Finding-ID, Lösung, Beweis/Session-ID, geänderten Dateien und Prüfergebnis unter `workflow/reports/`; melde danach `ROOT_REVIEW_READY`. Die externe Abnahme übernimmt ausschließlich der Auftraggeber/ROOT-Reviewer – keine Selbstfreigabe als `ROOT_PASS`.
