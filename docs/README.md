# Dokumentation zu Voice-STT-Server V2

Das **[vollständige V2-Handbuch](v2-handbuch/README.md)** ist die maßgebliche, unabhängige geprüfte Dokumentation des aktuellen Serverprojekts. Seine 104 Kapitel decken Systemverständnis, Funktionsweise, Einstellungen, Schnittstellen, Sicherheit, Betrieb, Entwicklung und technische Referenzkataloge ab.

## Für Anwender und Administratoren

- [Systemüberblick](v2-handbuch/01-grundlagen/01.01-produktueberblick.md)
- [Installation, Betrieb und Readiness](v2-handbuch/06-betrieb/06.02-installationskonzept.md)
- [Konfigurationsquellen und Settings](v2-handbuch/03-konfiguration/03.01-konfigurationsarchitektur.md)
- [Berechtigungen, Admin-Zugriff und Kroko](v2-handbuch/05-administration/05.01-sicherheitsarchitektur.md)
- [Fehlerdiagnose](v2-handbuch/06-betrieb/06.12-fehlerdiagnose.md)

## Für Client- und Serverentwickler

- [WebSocket-Protokoll V2](v2-handbuch/04-schnittstellen/04.03-websocket-v2.md)
- [HTTP-/API-Endpunktkatalog](v2-handbuch/08-referenzen/08.04-api-endpunkt-katalog.md)
- [Commands, Events und Fehler](v2-handbuch/04-schnittstellen/04.04-commands-acknowledgements.md)
- [Entwicklungs- und Testverfahren](v2-handbuch/07-entwicklung/07.01-entwicklungsumgebung.md)
- [Quellcodebasierte ergänzende V2-Referenz](v2-code-reference/README.md)

## Release- und Lizenzunterlagen

Die [Release-Anleitung](release-process.md), das [Build-Runbook](../build/BUILD.md) und die [Lizenz- und Attributionserläuterung](licenses.md) bleiben eigenständige, releasekritische Dokumente. Ein erfolgreich geprüfter Code- oder Dokumentationsstand ist nicht automatisch ein veröffentlichter Build. Die Native- und Redistributonsgates werden separat kontrolliert.

## Historische und ergänzende Unterlagen

Die [frühere Eigen-Dokumentation](.archiv/stand_vor_v2_handbuch_2026-11-14/README.md) wurde beim Wechsel zum Handbuch in das Entwicklungsarchiv verlagert. Alte dokumentarische Übernahmen aus RealtimeSTT wurden **nicht** als neue aktive oder duplizierte Archivtexte übernommen; ihre Git-Vorgeschichte bleibt erhalten. Wo bisherige Links benötigt werden, führen sie jetzt zu aktuellen Themenkapiteln.

Die [Legacy-V1-/Client-Verträge](client-development/README.md), die [bisherigen Codebelege](v2-code-reference/README.md), [PR-/Entwicklungsakten](.archiv/README.md) und [Audits](audits/) bleiben aus Gründen der technischen Rückverfolgbarkeit zugänglich. Die historisch nachgewiesene Projektherkunft und alle Original-Lizenzhinweise bleiben erhalten.
