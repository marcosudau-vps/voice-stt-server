# Entscheidungen

- 2026-11-06: Vollständige Gliederung V0.2 mit 104 einzelnen Statusobjekten.
- Recherche ausschließlich aus aktuellem Code, unabhängig geprüft.
- Diagrammwünsche sind redaktionelle Ideen, keine Code-Fakten.
- Kein bestehender Produktcode / keine alte Dokumentation geändert.
- 2026-11-08 (Charge 1): Faktenakten MÜSSEN pretty-printed JSON (indent=2) sein. Minifizierte einzeilige JSONs sind für Subagenten-Reader unlesbar (Zeilencap ~2000 Zeichen); Writer/Reviewer arbeiten sonst blind. Betroffen waren 01.01/01.02 (Subagent-Workarounds dokumentiert); behoben per json.dumps(indent=2). Registry-Pfad research/<ID>.json bleibt.
- 2026-11-08 (Charge 1): Tool-Hinweis workflow_cli.py: Konsolenausgabe enthält '→' (U+2192); unter cp1252-Codepage stürzt der Print nach erfolgreich abgeschlossenem Statuswechsel+Refresh ab (UnicodeEncodeError). Status ist trotzdem gesetzt. Workaround: $env:PYTHONUTF8='1' setzen. Kein Tool-Fix ohne Freigabe.
- 2026-11-08 (Charge 2): 01.04-Researcher meldete „kein .git im Checkout" (Subagent-Sichtbeschränkung). Orchestrator-Verifikation: .git vorhanden, HEAD=a8993c5c, Arbeitsbaum sauber. N-04 als widerlegt annotiert. Lehre: Commit-Identität immer per eigenem git rev-parse prüfen, nicht per Subagent-Behauptung.
