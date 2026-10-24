# Ist-Inventar und Branches

24.10.2026; vor Implementierung, AP-STTM-000.

Arbeitscheckout: `P:/GithubRepos/marcosudau-vps/voice-stt-server/workspaces/kroko-umbau/voice-stt-server-sttm-integration`.
Eigener Git-Worktree von aktuellem `origin/feat/v2-unified-kroko` (`acdffc7`).
Der App-Worktreehelfer meldete am übergeordneten Nicht-Git-Arbeitsordner
`Not a git repository`; deshalb wurde der Worktree mit `git worktree add -b`
angelegt. Vorhandene drei Checkouts waren unverändert und werden nicht umgebaut.

| Zustand | Bestehende Autorität | Änderung / Risiko / Testbezug |
|---|---|---|
| Produkt-/Inventar-/Recovery | VoiceSTT_server/stt_model_management.py | refresh enthält Provisioning und Loadprobes; explizit trennen, LKG-Tests |
| lokale Engineauflösung | VoiceSTT/transcription_engines/model_resolver.py | downloadfrei erhalten, Resolvertests |
| konfigurierte Absicht | ServerSettings / RuntimeConfigStore | ODER-Autoflags durch globale Freigabe UND ID-Liste ersetzen; Settings-Tests |
| Revision/Transaktion | api_fastapi_server/settings_control.py | STT-Adapter derselben Werte; persist-before-commit testen |
| Laden/Session/Inferenz | api_fastapi_server/server.py | nur nötige Integration, gemeinsame Locks und frühe WS-Rückmeldung |
| Lizenz/Nativeprozess | VoiceSTT/kroko/ | Restintegration ist weiter als offizieller PR-Text; unabhängige Evidenzgrenze erhalten |
| Katalog | PR #13, 124 Metadaten | UUID/Manifest/native ID getrennt, keine Downloadrechte ableiten |
| Eventpersistenz | VoiceSTT_server/event_logging.py | Downloadzustandsereignisse über bestehenden Hub |
| Wake Words | bestehender eigenständiger Katalog | nur Statusprojektion, keine STT-Übernahme |

PR #12 ist offen/draft; PR #13 offen/non-draft. Frisch geprüfte HEADs entsprechen
dem Auftrag. Restintegration enthält den #12-HEAD und sieben weitere Commits.
CI und Baselines werden im Run-Evidenzindex nachgetragen. Die Beilage mit
Suffix SPÄTERE_ARBEITSREIHE fehlt unter diesem Namen; gelesen wird die vorhandene
`VoiceSTT_V2_Zielarchitektur_Serverpakete_2026-10-24.md` aus dem aktualisierten
Agentenpaket. Deren umfassende Movevorgaben sind durch den Fokusauftrag aufgehoben.
