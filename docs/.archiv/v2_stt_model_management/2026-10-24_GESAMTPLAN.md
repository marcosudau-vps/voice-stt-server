# Gesamtplan – RUN-20261024-STTM-001

Status: Geplant, vor produktiven Änderungen. Datum: 24.10.2026.

## Auftrag und Grenzen

Die weitergehende Kroko-Restintegration und den unveränderten 124er-Katalog
auf `work/v2-stt-model-management-integration` integrieren, danach eine gemeinsame
Modellverwaltung um Jobs, sichere Installationen, Settings, HTTP, Status und
frühe Lazy-Reload-Kommunikation ergänzen. Ziel ist ein Review-PR gegen
`feat/v2-unified-kroko`. Kein Merge, Release, Deployment oder Client-Repo-Eingriff.
Die breit angelegte Servermigration ist ausdrücklich Folgearbeit.

## Ausgangslage und Entscheidungen

Basis `acdffc7042357cb8ae5e47961e42b78a25bd902c`; unveränderte bestehende
Checkouts, eigener Worktree. PR #12: `454e497fff4c0b1f466de03f536a13cf7bce522a`;
Restintegration: `03b813f27b4f707758ca14bdd1cf5d7d59edeb88` (sieben zusätzliche
Commits); PR #13: `58a85b7df0e414bff59b66789748077c0f7ff559`.
Der vorhandene STTModelManager bleibt Inventar-/Recoveryautorität. Neue, leichte
Download-/Storagebausteine unter `voice_stt_server/models/` arbeiten über
explizite Abhängigkeiten. Scheduler, Settings-Control-Plane, RuntimeConfigStore,
Eventhub, Kroko-Owner und Wake-Word-Katalog behalten ihre Zuständigkeit.

## Phasen und Abnahme

| AP | Umsetzung | Prüfung |
|---|---|---|
| 000 | Register, Originalprompt, Inventar, Baseline, zwei nachvollziehbare Integrationsmerges | SHA/Ancestor/PR/CI, Unitbaseline vor/nach Integration |
| 010 | Authority-/Aufrufmatrix, kleine fachliche Modulgrenzen | Lazy-/Kompatibilitätsimports, Recovery |
| 020 | Produkt-/Installationsprojektion, externe Read-only-Pfade, eine begrenzte Queue, atomare verifizierte Datei-/Verzeichnisinstallation, geschützte Löschung | Zustände/Races/Dedupe/Cancel/Restart/Hash/Quelle/Pfadgrenzen |
| 030 | eine Settingsrevision und Persistenz, ausgewählte IDs, V2-STT-API, Serverstatus | Auth/Revision/Persistenzatomarität/Public-Redaction |
| 040 | integrierte Kroko-Gates prüfen/ergänzen, gemeinsame Ownergeneration, Clientzugriff | Fake-Native-Regression; echte Providerbelege getrennt BLOCKED |
| 050 | V1/V2-Ladereihenfolge, frühes Signal, begrenztes responsives Warten | verzögerter Erfolg/Fehler, Parallelclients, Frozen-Wire unverändert |
| 060 | Fachreferenzen, Soll/Ist, Abweichungen, Abschlussakten, neuer Review-PR | gesamte Unit-/Contractsuite, pip check, Build/Imports/compileall/diff, CI |

## Risiken und Sicherungen

Fehlende Kroko-Lizenz-/Modellrechte-/Downloadverträge bleiben fail closed;
Metadaten und synthetische Tests ersetzen keine realen Berechtigungen.
Refresh wird downloadfrei von expliziter Runtime-Recovery getrennt; Installation
aktiviert keine Modelle. Auto-Downloads nur global UND explizit ausgewählt UND
qualifiziert. Externe Pfade sind niemals Schreib-/Löschziele. Queue startet
höchstens einen Transfer, nur queued ist stornierbar, keine persistente Queue.
LKG, MINIMUM_READY, recovery_priority und 3600-s-Idlepolicy bleiben erhalten.
Settingspersistenz vor RAM-/Revisionscommit, keine zweite Schreibautorität.
Native-Buildinputs werden nur bei zwingendem Bedarf verändert; keine alten
Fingerprints für neue Bytes. Plattform-/RC-/echte Protests separat NOT_RUN.

Jede Phase erhält Journal, Testevidenz und Commit. Abschließende Anforderungen
erhalten PASS/PARTIAL/BLOCKED/FAIL/NOT_RUN und eine Evidenzklasse. Nicht belegte
externe oder Plattformqualifikation begründet keinen Abbruch unabhängiger Arbeit.
