# Korrekturlauf PR #15 – Dokumentationsabgleich (25.10.2026)

Auftragsliste §9: alle 13 Dokumente geprüft. BUILD.md unverändert (bleibt
alleinige Build-/Paketreferenz; keine Build-/Fingerprint-Änderung im PR).
Root-README unverändert (Community-auf-beiden-Distributionen bereits korrekt).

| Dokument | Vorher | Änderung | Links |
| --- | --- | --- | --- |
| `server-authentication.md` | §4 beschreibt nur expliziten Adapter + Nicht-Ziele | §4 neu: Eingänge/Key-Auflösung/Prüfzeitpunkte/Zustandswechsel/Manager-Integration/Fehler/Abgrenzung/Live-Grenzen | ok (9) |
| `openai-http-api.md` | Auth-Fehler teils ohne X-Request-ID | Satz korrigiert (jetzt überall) | ok |
| `kroko-onnx.md` | „keine Pro-Freischaltung", „nicht angeschlossen" | Lifecycle-Abschnitt neu (Auto-Punkte, Force-Option, Runtime-Grenzen, Live-Opt-in) | ok |
| `stt-model-management.md` | Key ≠ Eligibility | Abschnitt Lizenz-vs-Runtime-Guards neu (Policy, Community-unter-Pro, LKG-Filter, `krokoLicense`-Feld) | ok |
| `configuration.md` | Kroko-Absatz veraltet | Absatz aktualisiert + neuer Betreiberabschnitt (Key/Wechsel/Force/Zustände/Abgrenzung) | ok |
| `testing.md` | Nur explizite synthetische Checks | Lifecycle-Suite + Live-Opt-in-Befehle dokumentiert | ok |
| `fastapi-server.md` | Keine Lizenz-Endpunkte | `license/refresh`-Route + `krokoLicense`-Feld ergänzt | ok |
| `module-map.md` | Alte Gate-/Kroko-Zeilen | Security-/Server-/Kroko-Zeilen auf Lifecycle aktualisiert | ok |
| `docs/README.md` | „aktuelle" 2026-Seite | Historisch-Markierung + BUILD-Verweis | ok |
| `server-modularization-roadmap.md` | Adapter-ja/später; „keine Echtlizenztests" | Kroko-Zeile, Phase A, Separat-Zeile, Quali-Absatz aktualisiert | ok |
| `2026-10-22_kroko-unified-runtime-v2.md` | „aktueller Untersuchungsstand" + Addon | Einordnungs-Box (historisch, überholt, Verweise); Inhalt sonst unverändert | ok |
| `README.md` (root) | — | keine Änderung nötig | — |
| `build/BUILD.md` | — | keine Änderung nötig | — |

Alle relativen Markdown-Links der geänderten Dateien geprüft (0 defekt).
Historische Plan-/Vergleichsdateien unverändert; Supersession nur additiv
in dieser Akte + PR-Beschreibung/Kommentar.
