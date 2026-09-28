# AP-SRV-080: Soll-/Ist-Vergleich

**Datum:** 28.09.2026
**Status:** Prüfung offen – lokale Abnahme vollständig grün, öffentliche CI ausstehend
**Integrationsbasis:** `05a525b8c0667f1c14de328f2b3c7b986b048359`

## Plan gegen Implementierung

| Planpunkt | Status | Tatsächlicher Stand und Nachweis |
| --- | --- | --- |
| Kanonisches V2-Interim | vollständig | `schema.EVENT_TRANSCRIPTION_INTERIM`, Projektion von `realtime_transcript` in `events.py` |
| Reiche Stabilisierungsdaten erhalten | vollständig | optionale Felder von `recordingId` bis `timing` im Interim-Builder; Übergabe aus `_on_realtime_stabilization_event` |
| Kein `stateVersion`-Anstieg für Interim | vollständig | Aufnahme in `NON_STATE_EVENTS`; Projektions- und Sockettests prüfen unveränderte Version |
| Session-Logzugriff in V2-Bootstrap | vollständig | `connection.py` ruft die vorhandene `create_log_access(sessionId)`-Autorität auf und setzt `hello.accepted.logAccess` |
| Sicherheitsgrenze des Sessiontokens | vollständig | E2E-Test belegt HTTP-Historie und `/ws/logs` mit `authorizationScope: session`; bestehende Autorität begrenzt Session und Kanäle |
| Verhalten bei nicht verfügbarem Logging | vollständig | `logAccess.available: false`, maschinenlesbarer Fehlercode, kein `accessToken`; E2E-Test vorhanden |
| Vertragsvektor | vollständig | `transcription_interim_event` in `tests/contracts/protocol-v2-vectors.json` und Contracttest |
| Aktive Dokumentation | vollständig | V2-Handshake, 18 Events, Lebenszyklus, Reducer, Authentifizierung, Logging, Betrieb und Architektur aktualisiert |
| Historische Auditspur | vollständig | Ursprüngliche Audits bleiben auf `f7d2b3c…` bezogen; datierter Follow-up-Bericht beschreibt die spätere Änderung |
| Lokale Gesamtverifikation | vollständig | siehe Testevidenz unten |
| Öffentliche Windows-/Linux-CI | offen | wird nach Push ergänzt; bis dahin bleibt der Registerstatus `Prüfung offen` |

## Lokale Testevidenz

Die bekannte Windows-WMI-Abfrage bei Imports von PyTorch/ONNX wurde nur für
den lokalen Testprozess entsprechend der vorhandenen Projektanweisung durch
feste Rückgaben `platform.machine() = "AMD64"` und
`platform.system() = "Windows"` umgangen. Produktcode und Tests wurden dafür
nicht verändert.

1. Vor Integration von PR #2, gezielter Wiederherstellungslauf:
   `153 passed, 1 skipped, 71 subtests passed`.
2. Vor Integration von PR #2, vollständige Suite:
   `1941 passed, 14 skipped, 1244 subtests passed`.
3. Nach Merge von PR #2 und Dokumentationsangleichung, Fokuslauf aus
   V2-Contract, V2-E2E, V1/V2-Grenze und Dokumentationsoberfläche:
   `266 passed, 1 skipped, 113 subtests passed`.
4. Tatsächlich zu veröffentlichender Gesamtstand, vollständiges `tests/unit`:
   `1941 passed, 14 skipped, 1244 subtests passed` in 627,05 Sekunden.

Zusätzlich erfolgreich: `compileall`, JSON-Parsing des Vertragsvektors,
`git diff --check`, relative Markdown-Links und Hygieneprüfung.

## Abweichungen

Die einzige materielle Prozessabweichung ist separat in
[`2026-09-28_AP-SRV-080_ABWEICHUNGEN.md`](2026-09-28_AP-SRV-080_ABWEICHUNGEN.md)
dokumentiert. Der lokale Wiederherstellungs-WIP entstand während der
Verlustanalyse vor der formalen AP-Registrierung. Vor Commit und Push wurde er
gesichert, auf die gemergte PR-#2-Basis gesetzt und vollständig neu geprüft.

## Abschlussbedingung

Nach Push werden Commit-SHA und öffentliche CI-Läufe für Ubuntu 24.04 und
Windows ergänzt. Erst wenn beide erfolgreich sind, werden dieser Bericht und
der zentrale Registereintrag auf `Abgeschlossen` gesetzt.
