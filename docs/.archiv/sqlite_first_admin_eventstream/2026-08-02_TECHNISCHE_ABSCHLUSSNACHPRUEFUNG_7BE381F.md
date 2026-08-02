# Technische Abschlussnachprüfung zu Commit 7be381f

> **Status:** Prüfung offen
> **Datum:** 2. August 2026
> **Branch:** `feature/sqlite-first-admin-eventstream`
> **Geprüfter Commit:** `7be381f4f4b01fb3eae6da3e5db71b599d331a4d`
> **Push, Merge, Deployment:** nicht erfolgt

## Zweck

Diese Datei dokumentiert die lokale technische Gegenprüfung der in
`2026-08-02_NACHPRUEFUNG_B99B71B_UND_ABWEICHUNGEN.md` festgehaltenen
Nachbesserungen. Sie ersetzt oder verändert weder die ursprüngliche Planung
noch den ursprünglichen Soll-/Ist-Bericht.

Der Status bleibt bis zu einer unabhängigen erneuten Abschlussprüfung auf
`Prüfung offen`. AP07-S2 Abschnitt 5.6 „Deployment und Liveabnahme“ ist
weiterhin ausdrücklich nicht ausgeführt.

## 1. Performance-Quellschalter und Spiegel

Die Verantwortlichkeiten sind jetzt getrennt:

- `performance_logging_enabled` ist der Quellschalter. Bei `false` beendet
  `PerformanceLogManager.event()` die Verarbeitung, bevor ein Event den
  `StructuredEventHub` erreicht.
- `performance_log_mirror_enabled` steuert ausschließlich den optionalen
  Performance-Kalender-/stdout-Spiegel.
- Ein bereits erzeugtes Event wird im `StructuredEventHub` weiterhin zuerst
  kanonisch in SQLite committed. Ein deaktivierter Spiegel entfernt es weder
  aus SQLite noch aus Replay oder Liveausgabe.
- Beide Einstellungen sind laufzeitänderbar, über die Admin-Logging-API
  getrennt sichtbar und werden in `runtime.json` getrennt persistiert.

Geprüft wurden der direkte Managerpfad, der echte Servicepfad, die
Laufzeitaktivierung, die YAML-/CLI-Konfiguration und die Admin-HTTP-API.

## 2. Korrelation von Recorder-Ergebnissen

Der Transkriptionsstart legt jetzt unter dem Session-Lock ein FIFO-Ticket mit
Generation, Segment-ID und Ablehnungsstatus an. Der Textworker darf ein
Recorder-Ergebnis nur mit einem vorhandenen Ticket verarbeiten.

Damit gilt:

- das erste leere Ergebnis terminalisiert das tatsächlich gestartete Segment
  genau einmal mit `transcription.discarded(reason=empty_final)`;
- ein dupliziertes Ergebnis ohne weiteren Transkriptionsstart besitzt kein
  Ticket, beansprucht kein synthetisches Folgesegment und wird verworfen;
- abgelehnte, veraltete oder nach Disconnect eintreffende Resultate erzeugen
  kein zusätzliches Terminalereignis;
- normale nichtleere Finaltexte durchlaufen weiterhin denselben Workerpfad.

Der gezielte Integrationstest speist zwei leere Resultate durch den laufenden
`_text_worker` nach genau einem echten `_on_transcription_start()` und weist
genau ein Terminalereignis für Segment 1 nach.

## 3. Archiv- und Dokumentationskorrektur

- Die archivierten Originaldateien
  `2026-08-02_SQLITE_FIRST_ADMIN_EVENTSTREAM_PLAN.md` und
  `2026-08-02_SQLITE_FIRST_ADMIN_EVENTSTREAM_UMSETZUNGSVERGLEICH.md` sind im
  geprüften Stand wieder inhaltsgleich mit Commit `28035dd`.
- Die spätere externe Prüfung und ihre Abweichungen stehen ausschließlich in
  einer neuen datierten Datei.
- Aktive Serverdokumentation, Konfigurationsreferenz und Release Notes erklären
  Quellschalter, Spiegel und Worker-Korrelation entsprechend der
  Implementierung.
- Alle elf für die Cliententwicklung synchronisierten Serverdokumente unter
  `P:\DockerProjekte\voice-stt-client\server-docs-for-client-development`
  sind SHA-256-identisch mit ihren Serverquellen.

## 4. Technische Nachweise

### Automatisierte Tests

- fokussierte AP07-Suite: **67 bestanden**, zusätzlich **6 Subtests**;
- erweiterte betroffene Suite: **118 bestanden**, zusätzlich **17 Subtests**;
- vollständige Pytest-Suite: **377 bestanden**, **13 übersprungen**,
  zusätzlich **78 Subtests**;
- vollständige unittest-Discovery: **342 bestanden**, **13 übersprungen**;
- bekannte Warnung: FastAPI/Starlette weist auf eine spätere
  `httpx2`-Migration des Testclients hin.

### Statische und dokumentarische Prüfungen

- `compileall` für `VoiceSTT`, `VoiceSTT_server`, `api_fastapi_server` und
  `tests`: erfolgreich;
- eingebettetes Browser-JavaScript über Node geparst: erfolgreich;
- aktive lokale Markdownlinks in 41 Dateien geprüft: erfolgreich;
- `git diff --check`: erfolgreich;
- archivierte Originale gegen Commit `28035dd`: keine Inhaltsabweichung.

### Docker

- Image: `voicestt-server:ap07-final-recheck`;
- Image-ID:
  `sha256:c8cec24dc449a68daa04bff7d8e00ba5cb0e30e941e1c69e3eff233c1a10f39d`;
- `compileall` im neu gebauten Image: erfolgreich;
- SQLite-first-Smoke für deaktivierte Performancequelle, spätere
  Laufzeitaktivierung und deaktivierten Spiegel: erfolgreich;
- echter Duplicate-Empty-Worker-Integrationstest im Image: erfolgreich.

## 5. Bewertung

- AP07-S1 ist im lokalen Feature-Branch technisch vollständig nachgebessert.
- AP07-S2 Abschnitte 5.1 bis 5.5 sind im lokalen Feature-Branch technisch
  vollständig nachgebessert.
- AP07-S2 Abschnitt 5.6 bleibt offen und wurde nicht vorweggenommen.
- Eine Livefreigabe wird aus dieser lokalen Prüfung nicht abgeleitet.

Der Branch ist damit für die angekündigte unabhängige Abschlussprüfung
vorbereitet. Das Archivregister bleibt bis zu deren Entscheidung auf
`Prüfung offen`.
