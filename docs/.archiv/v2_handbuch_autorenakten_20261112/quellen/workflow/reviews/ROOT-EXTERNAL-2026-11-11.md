# Externe ROOT-Endabnahme – Gesamtdokumentation Voice-STT-Server V2

**Prüfdatum:** 2026-11-11
**ROOT-Urteil:** `ROOT_CHANGES_REQUESTED` – **keine uneingeschränkte Endfreigabe**.
**Prüfbasis:** Archiv `2026_11_06_Server_Dokunentation.zip`, Produktquellstand `a8993c5c68042d996eab680d84a5b138a214bb5d` (detached HEAD, sauber).

## Bestätigte Prüfungen

- 104/104 Kapitel, 104/104 Forschungs-JSON (insgesamt 2.700 Fact-Records), 104 Reviewakten vorhanden. Registry: 104 `INTEGRATED` / 104 `PASS`.
- `workflow_cli.py validate` erfolgreich (9 Bereiche/43 Briefs).
- 1.245 interne Markdown-Links: keine fehlenden Dateiziele/prüfbaren Fragmente.
- Source AST: 18 Event-Typen, 5 Commands, 15 Result-Codes, 19 SettingsDefinition-Registrierungen, 37 HTTP/WS-Routen, 5 V2-Close-Codes. Alle Namen in den Referenzkapiteln vorhanden.
- Quellspiegel Git-HEAD entspricht Commit, Arbeitsbaum sauber; ZIP-Dokumentation (105 Markdown-Dateien) hat denselben gemeinsamen SHA256-Digest wie die PC-Arbeitskopie: `79712e7b760a5a8f384e6829339fa9501c1fb01c858b1aa643ddbb9c98782daf`.
- Am Quellstand zusätzlich gestartet: `python -m unittest -q tests.unit.test_protocol_v2_contract tests.unit.test_protocol_v2_settings tests.unit.test_settings_control_plane tests.unit.test_stt_model_management tests.unit.test_kroko_license_lifecycle` → Ran 110 tests, OK (skipped=1). Das sind 109 erfolgreich ausgeführte und 1 übersprungener Test.
- 106 Mermaid-Codeblöcke in 56 Kapiteln vorhanden. Ein tatsächliches vollständiges Rendering wurde NICHT erfolgreich ausgeführt.

## Befunde

### ROOT-001 – MAJOR: Sichtbarer Status widerspricht Registry

**79 Kapitel** tragen noch `Entwurf zur unabhängigen Prüfung`, **13 Kapitel 04.01–04.13** sogar `Status: DRAFTED (Writer-Entwurf)`. Die Navigation `docs/v2-handbuch/README.md` sagt `Geplante Dokumentation – 104 Unterkapitel` und `keine fertig recherchierte technische Dokumentation`. Root-`README.md` sagt weiterhin, 103 Kapitel seien erst noch zu erstellen. Dies widerspricht dem behaupteten Status 104 × INTEGRATED.

**Korrektur:** Status- und Entwurfsmarker nach finalem internen Review bereinigen. ROOT-Freigabe nicht als erteilt behaupten. Root- und Handbuch-Navigation aktualisieren; 104 Links erhalten; keine technischen Texte unnötig ändern.

### ROOT-002 – MAJOR: Reviewer-Nachweise für 42 Kapitel unvollständig

In `workflow/reviews/01.01–01.09.md`, `02.01–02.02.md`, `02.04–02.08.md`, `03.01–03.13.md` und `04.01–04.13.md`: Reviewakte nennt `doc-reviewer` und `PASS`, aber **keine echte `ses_...`-Session-ID**. Die verlangte getrennte Subagentensession ist daher anhand dieser 42 ZIP-Reviewakten nicht unabhängig belegbar. Das ist keine Behauptung, dass der Review nicht stattgefunden habe.

**Korrektur:** Historische Subagentensessions aus OpenCode eindeutig zuordnen und mit realer ID in jede Akte nachtragen. Niemals IDs erfinden. Falls historisch nicht nachweisbar, betroffene Kapitel neu durch unabhängig gestarteten `doc-reviewer` fachlich prüfen, Prüflog/Session-ID sichern.

### ROOT-003 – MEDIUM: Diagrammstatus und Bericht falsch abgeglichen

Registry: **42 × IDEA**, **1 × VERIFIED**, **61 × NOT_REQUESTED**. In den 42 IDEA-Kapiteln stehen bereits **77 Mermaid-Blöcke**, in 13 NOT_REQUESTED-Kapiteln **27 zusätzliche Blöcke** (03.03, 03.04, 03.06, 03.07, 03.10, 03.11, 03.12, 04.01, 04.02, 04.05, 04.11, 04.12, 04.13). Gesamtsumme 106. Der interne Abschlussbericht behauptet irrtümlich `NOT_REQUESTED ohne Mermaid (0 Mismatches)`. Zusätzliche Diagramme sind nicht unzulässig, aber die Nachweise sind nicht konsistent.

**Korrektur:** Jede der 43 Diagrammplanungen samt Entscheidungen/Belegen abgleichen. IDEA-Status kontrolliert aktualisieren, falls verifiziert; bei begründet ausgelassenen Vorschlägen Entscheidung dokumentieren. Zusätzliche Diagramme korrekt zählen, **nicht automatisch löschen**. Abschlussbericht berichtigen.

### ROOT-004 – MEDIUM: 09.08 enthält veraltete Statuszahlen

`docs/v2-handbuch/09-anhaenge/09.08-dokumentationsstand.md` zeigt `103 INTEGRATED + 1 IN_REVIEW` und Rundenstatistik `21/67/14/1` als damals untersuchten Stand. Aktuell sind 104 INTEGRATED, Abschlussbericht meldet `20/67/16/1`. Nicht als aktuelle Abschlusswahrheit stehen lassen.

**Korrektur:** Historische Momentaufnahme klar als solche erhalten, abschließende Ist-Zahlen ergänzen, Research- und Reviewakte synchronisieren.

### ROOT-005 – Prüfgrenze: Kein vollständiger Mermaid-Rendertest

Nur Fences/Diagramm-Typen strukturell geprüft. Ein temp. CLI-Installationsversuch scheiterte wegen npm-Sicherheitsregel `EALLOWSCRIPTS`; diese Regel wurde **nicht umgangen**. Kein erfolgreicher Rendernachweis für 106 Mermaid-Blöcke.

**Korrektur:** Bei vorhandenem, zugelassenem Renderer Mermaid-Blöcke rendern; insbesondere Sequenz-/Zustandsdiagramme priorisieren. Blocker/Grenze transparent dokumentieren, keine PASS-Behauptung ohne Test.

## Weiteres Vorgehen

1. ROOT-001..004 nachweisbar schließen; für ROOT-002 unbedingt echte Subagenten-Nachweise oder neue unabhängige Prüfungen.
2. ROOT-005 mit erlaubtem Tool nachholen oder explizit dokumentiert zur gesonderten Entscheidung vorlegen.
3. Nach Korrektur `workflow_cli.py refresh`, `validate`, `status`, Link- und Faktenchecks, Katalogvergleiche und Reviewer-Delta-Checks erneut ausführen.
4. Danach `ROOT_REVIEW_READY` mit Änderungs-/Belegliste melden. **Keine Selbstfreigabe, keine Produktänderungen, kein Git-Merge/Push/Release.**

**Anmerkung zur Prüftiefe:** Verifiziert wurden die komplette Struktur/Linkoberfläche und die zentralen Registry-Sollmengen; fachliche Tiefenprüfung weiterer Kapitel erfolgte stichprobenartig. Es wurden nicht sämtliche circa 2.700 Fact-Records und 106 Mermaid-Kantenbilder unabhängig Zeile für Zeile gegen die Implementierung kontrolliert.

**Gesamturteil: ROOT_CHANGES_REQUESTED.** Der Umfang ist substanziell fertig; ein gezielter Korrekturlauf genügt.
