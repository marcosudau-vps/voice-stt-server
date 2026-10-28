# Soll-/Ist-Prüfung – OpenAI-Router, Security und Modularisierungsfahrplan

**Datum:** 25.10.2026 · **Basis:** `feat/v2-unified-kroko` ·
**Ziel:** [Draft PR #15](https://github.com/marcosudau-vps/voice-stt-server/pull/15)

Diese Akte beschreibt den **auf GitHub committeden** Implementierungsstand;
sie ist kein Ersatz für einen abgeschlossenen CI-Lauf oder Root-Review.

| Soll (Plan) | Ist (Commit-Inhalt) | Qualifikation |
| --- | --- | --- |
| OpenAI-HTTP-Routen auslagern | `api_fastapi_server/openai_routes.py` enthält `/v1/models`, `/v1/audio/transcriptions`, SSE, Upload, Fehler, Telemetrie. `server.py` registriert einen Router mit explizit injizierten Fähigkeiten, kein Rückimport des App-Moduls | Code überprüft, Linux/Windows CI separat |
| OpenAI-Service/Scheduler-Verträge stabil | `transcribe_openai`, `complete_pending_api_transcription`, `resolve_openai_model` und gemeinsame `model_catalog` bleiben im Service | Absichtlich keine invasive Scheduler-Änderung |
| Vier Auth-Verfahren an einer Stelle | `api_fastapi_server/security/` mit `SecurityService`, `AdminGate`, `OpenAIGate`, `LogGate`, `KrokoLicenseGate` | Code überprüft, Integrationstest/CI separat |
| Vorhandene Admin-Regeln erhalten | Primärheader, Bearer, Alias, 401; ohne Key lokale Adminzugriffe und remote 403 | gezielte synthetische Regressionstests enthalten |
| Bestehende OpenAI-Auth erhalten | Optionaler Key, direkter Bearer, Audit-Event und 401 mit `WWW-Authenticate` | gezielte synthetische Regressionstests enthalten |
| Log-Tokens und Scopes erhalten | 24h-Tokens im eigenen flüchtigen Store, Sessionbindung; HTTP-Loopback-Ausnahme; kein solcher Bypass bei WebSocket | gezielte synthetische Regressionstests enthalten |
| Kroko im gemeinsamen Interface | Nur Adapter zur vorhandenen expliziten modellbezogenen Lizenzprüfung und flüchtigem Lizenzstatus, keinerlei automatische Aktivierung | Keine reale Pro-Lizenzqualifikation behauptet |
| Schriftlicher Komponentenschlachtplan | `docs/architecture/server-modularization-roadmap.md` mit Status, Modulgrenze, Timing und Risiken als rechte Empfehlungsspalte | Dokument erstellt |
| Projektregeln / Dokumentation | Plan vorher registriert; `docs/configuration.md`, `docs/testing.md` aktualisiert; weitere Schritte getrennt | unabhängiger Review offen |

## Nachweisgrenzen und bewusst zurückgestellte Arbeiten

- Der OpenAI-HTTP-Teil wurde herausgelöst; die tiefer im Scheduler verankerte
  OpenAI-Inferenzkoordination **nicht**. Dies ist die vorher vereinbarte
  risikominimierende Schichtengrenze, keine stillschweigende Vollauslagerung.
- Log-Routen, weitere Admin-Routen, Session-Runtime, Scheduler und V2-WebSockets
  wurden **nicht** gleichzeitig bewegt; siehe Roadmap.
- Kroko: Keine Änderung an nativem Laufzeitpaket, Build-Fingerprint,
  Pro-Entitlement, C++-Patch, V2-Wire oder automatischer Lizenzprüfung.
- Explizite API-Tests sind mit Fakes aufgebaut. Echte Pro-Modellrechte,
  Anbieter-Connection-Limits, Nutzungsreports und Widerruf sind **nicht
  qualifiziert**.
- Der maßgebliche Linux-/Windows-Teststatus ist im GitHub-Actions-Check des
  **aktuellen PR-HEADs** abzulesen. Ein früherer Commitlauf ist kein Ersatz.

**Status:** Prüfung offen, kein Merge.
