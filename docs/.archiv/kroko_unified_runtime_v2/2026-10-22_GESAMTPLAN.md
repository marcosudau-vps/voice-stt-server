# Unified Kroko Runtime V2 – Gesamtplanung

Erstellt am 22.10.2026, vor Experimenten und produktiver Umsetzung.

## Arbeitsbasis und Freigabegrenze

Auftrag: AP-KR-010 aus `Prompts/AP-KR-010.md` im übergeordneten Workspace.
Initialer Checkout: `main`, `714b1cf`, sauber (`git status --short` leer).
Dieser Branch enthält den aktuellen V2-Zielbranch nicht (Ancestor-Prüfung Exit 1).
Nach `git fetch origin --prune` ist der zuletzt übernommene V2-Stand
`67f3ce45f6ea1ff659382e40c194c70bd33d58ff` (Merge PR #10).
PR-HEAD `a694cd822d12c31e1d02d77e1518cae05c6a98b1` besitzt erfolgreiche
Linux-/Windows-CI 39378549972 und erfolgreichen RC 39405176300.
Historische Berichte/PR-Beschreibung nennen noch offene Zwischenstände;
die aktuelle Actions-Abfrage ist gesonderte Evidenz, keine Änderung dieser Belege.
Die Übernahme per Merge ist nachweisbar; eine separate menschliche Abnahmeakte
über den Merge hinaus ist damit nicht behauptet.

Integrationsbranch `feat/v2-unified-kroko` wurde exakt auf `67f3ce4` angelegt,
danach Arbeitsbranch `feat/v2-unified-kroko-ap010` auf demselben Commit.
Geschützter Branch `feat/einheitliche-triggerarchitektur-distributed` bleibt
unverändert. PR-Ziel ist ausschließlich der Integrationsbranch. Kein Merge.

## Ziel und Nicht-Ziele

Eine gemeinsame Serverdistribution enthält Community; Pro ist optional als
vorgebautes natives Paket installierbar. Nur eine Runtime ist aktiv.
`pro_enabled = api_key_present AND NOT force_community AND license_validation_successful`
wird abgeleitet, nicht redundant persistiert. Lizenzstatus und serverweite
Freigabe sind unabhängig vom sitzungslokalen Admin-Unlock.
`KROKO_API_KEY` bleibt erhalten. Kein Key/erzwungene Community bedeutet keine
Pro-Initialisierung und keine Lizenzprüfung. Fehlversuche führen sicher zu Community.

AP-KR-010 untersucht ausschließlich. Keine produktiven Code-/Packagingänderungen,
V2-Wireänderungen, Deployment-, VPS-, Registry- oder Releaseaktionen. Keine
Secrets, Modelle, nativen Dateien oder erzeugten Logs im Commit.

## Schritte und Abnahme

1. AP-KR-010: Pflichtdokumentation, native Artefakte/Quellen, Lizenzmechanismus,
   Server-/Modellpfade und gesamte Releasekette untersuchen. Reale Isolation
   getrennt von Simulation prüfen. Reproduzierbare Experimentierskripte unter
   `AP-KR-010/experiments/`, externe lokale Artefakte außerhalb des Gitstands.
2. Untersuchungsmatrix, Ergebnisbericht, Architekturentscheidung, Risiken,
   Übergabe und Soll-/Ist-Vergleich mit VERIFIZIERT / CODEANALYSE / SIMULIERT /
   OFFEN erstellen; vorhandene Unit-/Contract-Suite ausführen.
3. AP-KR-010 als PR zur unabhängigen Prüfung vorlegen; offene Voraussetzungen
   ausdrücklich benennen. AP-KR-020 beginnt erst nach Abnahme und gesondertem Auftrag.
4. AP-KR-020 (geplant): Runtimeauswahl, Lizenzstatus/Invalidation, Modellfreigaben,
   sichere Übergänge und Settingsintegration auf eigenem Branch vom dann
   abgenommenen Integrationsstand. Positiv-/Negativtests mit autorisierter Umgebung.
5. AP-KR-030 (geplant): native Komponenten/Extras, Build-/Releaseidentität,
   RC-/Resume-/Rollback-Verträge und echte Linux-/Windows-CPython-3.12-Matrix.
6. Unabhängige Gesamtqualifikation; abschließender Squash-PR in den geschützten
   V2-Zielbranch ausschließlich nach ausdrücklicher Benutzerfreigabe.

## Risiken und Nachweisgrenzen vor Untersuchung

Gleiche Import-/Bibliotheksnamen können pip-Dateien und native Zustände kollidieren
lassen. Importerfolg belegt keine Lizenz. Native Fehler können den Prozess
abbrechen. Key-/Moduswechsel müssen Sessions und Freigaben atomar invalidieren.
Packaging darf unveränderte Artefaktbytes, SHA-256, Authority/Fingerprints und
fail-closed Veröffentlichung nicht aufweichen. Redistributionsrecht für eine
separate Pro-Komponente ist Voraussetzung, kein technischer Automatismus.
Docker Desktop ist lokal pausiert; Windows CPython 3.12 und WSL Ubuntu sind
vorhanden. Plattform- und Lizenztests werden nur als bestanden bezeichnet,
wenn tatsächlich ausgeführt. Fehlende Keys/Modelle werden nicht beschafft.
