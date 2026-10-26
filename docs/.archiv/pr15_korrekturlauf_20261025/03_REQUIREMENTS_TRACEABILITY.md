# Korrekturlauf PR #15 – Requirements-Traceability (25.10.2026, Stand vor Implementierung)

Legende: SOLL = Review-/Auftragsforderung; IST(15d7a89) = Befund am Ausgangs-HEAD;
PLAN = Korrekturvorhaben; Status nach Umsetzung in 07/08.

| Befund | SOLL | IST (15d7a89) | PLAN (Komponente) |
| --- | --- | --- | --- |
| H-01 Scope-Baseline | Produktweite Soll/Ist-Matrix; Auto-Lizenz als offene verbindliche Anforderung | Teilplan-Nicht-Ziel ohne Nachverfolgung; 20/20-PASS verkürzt | Diese Akte (03–08) + Supersession-Vermerk; alte Akten unverändert |
| H-02 Auto-Prüfung | Idempotenter Lifecycle-Check (Init/Key/Force/Recheck), fail-closed, kein Netz ohne Key/Force, kein Loop-Block | Nur `check_model()` explizit; kein produktiver Aufruf | `KrokoLicenseGate.evaluate()` + `VoiceSTTService.refresh_kroko_license_policy()` (sync-Entscheid + Daemon-Thread-Check), Hooks in `__init__`/Refresh/Switch/PATCH + Admin-Route |
| H-03 Key-/Force-Pfad | Ein Generationen-/Invalidierungs-/Recheck-Flow; reale Änderungswege + Neustart-Doku; nur Intent persistiert | Kein Setting, kein Hook; Env extern unsichtbar | Registry-Key `kroko.forceCommunity` (server/admin/live, Overlay-persistiert); Re-Eval bei Refresh/Switch/PATCH/explizit; Doku der Neustart-Wege |
| H-04 Modell-Integration | Pro-Auswahl nur mit aktuellem VALID vor Admission/Load-Probe; LKG/Recovery/Lanes identisch geschützt | `_eligible`/`candidate_eligible` nur Variante+Enabled; Refresh/Probe zuerst | Optionale `license_policy`-Injektion im Manager (Default: Legacy-Verhalten); Service injiziert immer; Gate vor erstem Refresh in `__init__` |
| H-05 UUID-Zuordnung | Echte Zuordnung Pro-Modell → technische UUID, keine Erfindung, in Kroko-Authority | Keine UUIDs im Manifest/Katalog | `models.py`: `read_model_uuid()` (Header-JSON) + `license_uuid_for()` (Manifest→Datei→Header); Header ist Ground Truth (nativ identische Quelle) |
| H-06 Runtime-Variante | Pro-Freigabe nur in passender Runtime; Community-unter-Pro korrekt abbilden + echte Tests; kein Hot-Swap/Supervisor | Strikte Gleichheit beidseitig; Community-unter-Pro entgegen nativem Befund verweigert | Community-Eligibility unter Pro-Runtime öffnen (nativ belegt); Pro nur mit Entitlement; Ebenen getrennt beweisen (frei-lokal echt, pro-seitig deterministisch + ggf. Pro-Build) |
| H-07 Lifecycle produktiv | Sperren neuer Jobs/Modelle + alte Sessions nach Rotation/Force/Ablauf/Negativ; Recheck/Timeout getestet | Isolierte State-Tests nur; keine Admission-/Refresh-/Switch-Durchsetzung | Admission-Gate im Manager + Ablauf via `pro_enabled_for` an jedem Check; Übergänge deterministisch getestet |
| H-08 Tests | E2E Key→Prüfung→State→Rechte/Rotation/Force/Start/Recheck/Timeout/Race + echte Lizenztests | `does_not_auto_check`-Test zementiert alte Grenze; nur Fakes | Neue Lifecycle-Suite (Wahrheitstabelle, echter Komponentenweg) + Opt-in-Live-Tests R1–R4 (`VOICESTT_KROKO_LIVE_TESTS=1`); alter Test wird an neue Architektur angepasst (Auto per Default an, explizit abschaltbar für alte Assertions) |
| D-01 IST/SOLL/BLOCKED | Unerfülltes SOLL als BLOCKED kennzeichnen | Ist-Zustand ohne SOLL-Markierung | Alle 13 Doku-Ziele mit Statusmarkierung aktualisieren |
| D-02 2026-10-22-Seite | Überholte Entwürfe (Addon/Supervisor) als historisch kennzeichnen; BUILD.md Authority | „Aktueller Untersuchungsstand" mit Addon-Referenz | Hinweis-Box + Verweis auf BUILD.md, Inhalt unverändert |
| D-03 Alte Traceability | Additive Supersession, neue IDs, aktuelles BLOCKED, Belegkette | PR15-ARCH-02 PASS irreführend neben BLOCKED | Diese Akte supersediert ausdrücklich; alte Akten unverändert (08 bleibt lesbar mit neuem Vermerk? — 08 ist Review-Akte, unverändert; Vermerk nur hier) |
| D-04 Security-Referenz | Entitlement-Grenze, Trigger, Credentials, Modell-Authority tabellarisch/diagrammatisch | Nur alte Nicht-Ziele | `server-authentication.md` §4 neu schreiben |
| D-05 Key-/Force-Semantik | Eingabe/Änderung/Force/Fehler/Neustart vs. `runtime_variant` dokumentieren (erst nach Code) | Fehlt | configuration/kroko-onnx/testing nach Implementierung |
| M-01 Snapshot-Scope | Kein globaler Freigabeschein aus Modell-VALID | `proEnabled` ohne Scope | `public_snapshot()` + `"scope": "model"`; Enforcement nur via `pro_enabled_for` |
| M-02 Async/Dedup | Kein Loop-Block; keine Doppelchecks; native Single-Init | Synchrone Probe, keine Policy | Daemon-Thread-Check + Skip-wenn-frisch; Recognizer unberührt |
| M-03 Kleinstbefunde | Je realem Vertrag minimal fixen oder begründet behalten | 5 offen | Einzeln verifizieren (Request-ID, Alias-Status, Host-Konstante, Pruning, Stop-Maskierung) |

## Wahrheitstabelle (Zielverhalten, vgl. Auftrag §7/D1)

Kein Key → Community/kein Netz. Force → Community/kein Netz. Key+gültig → VALID/Pro.
Key+negativ/Timeout → Community. Keywechsel/-entfernung/Force-an → sofortige Invalidierung.
Force-aus+Key → Neuprüfung. Alte Generation überlappt → nur aktuelles Ergebnis. TTL abgelaufen →
keine Verwendung. Pro lokal fehlend/falsche Runtime → kein Start. Gültig+verfügbar → Freigabe.
Negativ bei Switch → kein Pro-Job. Neustart → kein persistierter Positivstatus.
