# Korrekturlauf PR #15 – Abschlussbericht (25.10.2026)

Finaler Commit: Branch-Spitze bei Push (SHA + CI-Links in PR-Beschreibung
und Abschlusskommentar; §14.1: nach finaler CI keine weiteren Commits).

## Soll/Ist-Abgleich

| Vorgabe (§12) | Ist |
| --- | --- |
| Auto-Lizenzprüfung integriert | Ja: Gate-Lifecycle + Service-Hooks (Init/Refresh/Switch/PATCH/Admin-Recheck), R1 live VALID |
| Keywechsel/Force korrekt | Ja: sofortige Invalidierung, Force-an→Community ohne Netz, Force-aus→Neuprüfung; R4 live |
| Pro-Freigaben an Lizenzzustand gebunden | Ja: `_eligible`/`candidate_eligible`/LKG-Filter über lesende Policy; R3 lädt Pro nur mit Grant |
| Manager + Security konsistent | Ja: eine Authority je Seite, keine zweite Registrierung/kein zweiter State |
| Deterministische Tests erfolgreich | Ja: 24 Lifecycle-Tests + dotychczasige Suiten (finale Zahlen in 05) |
| Reale Integrationstests erfolgreich | Ja: R1/R2/R3/R3b/R4 (redigiert, minimale Verbindungen) |
| Keine offenen hohen/kritischen Befunde | Ja: alle H/D/M geschlossen oder begründet (07); Anbieter-Limits/Widerruf NOT_RUN als Folgeauftrag |
| Doku == Code | Ja: 13 Dokumente abgeglichen, Links geprüft, Historie unverändert |
| CI Windows+Ubuntu finaler Commit | Nach Push: Läufe abwarten, Links in PR-Beschreibung/Kommentar |

## Finale Änderungsübersicht

Code: `security/kroko.py` (decide/refresh/timeout), `license_state.py`
(Scope), `kroko/models.py` (Header-UUID), `settings_control.py`
(`kroko.forceCommunity`), `stt_model_management.py` (Policy/Community/LKG),
`server.py` (Init-Reihenfolge, Policy-Helfer, Hooks, Admin-Route,
`krokoLicense`-Feld, M-03-Fixes), `openai_routes.py` (Request-ID),
`security/logs.py` (Host-Dedup, Pruning). Tests: neu Lifecycle (24) + Live
(R1–R4/R3b); eine gepinnte Schema-Menge um den beauftragten Key erweitert.
Doku: 11 Dateien aktualisiert, 2 unverändert korrekt. Keine nativen
Buildinputs/Fingerprints, kein Wire-, kein Persistenzschema-Wechsel
(Overlay nutzt bestehendes Format, keine Secrets).

## Verbleibende Risiken

Anbieter-Limits/Reports/Widerruf NOT_RUN; native Langzeit-Reporter-Semantik
unverändert; Pro-Runtime nur lokal gebaut (CI bleibt Upstream-Free).

## Status

**REVIEW_READY** — sofern finale Vollsuite lokal und finale CI (Ubuntu +
Windows) auf dem finalen Commit grün sind (Nachweise in 05 + PR-Kommentar).
Bedeutet nur: erneute unabhängige Abnahme kann stattfinden. PR bleibt Draft,
offen, ungemergt; kein Merge, kein Ready-for-Review.
