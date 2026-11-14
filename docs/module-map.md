# Modulübersicht der V2-Implementierung

Die öffentliche Oberfläche des Voice-STT-Servers entsteht aus mehreren getrennten Verantwortlichkeiten. Die Benutzer-API liegt nicht unmittelbar in jedem internen Erkennungsmodul; zwischen Eingangsroute, Sitzungsverwaltung, Aktivierung, Scheduler, Engine und Eventausgabe werden Zustände und Rechte kontrolliert.

## Orientierung im Quellbaum

| Pfad | Schwerpunkt |
| --- | --- |
| `api_fastapi_server/` | HTTP-/WebSocket-Eingang, V2-Protokoll, Authentifizierung und Settings-Kontrolle |
| `VoiceSTT/` | Recorder, Audioverarbeitung, Wake Word, Transkriptions-Engine und Modellinfrastruktur |
| `VoiceSTT_server/` | Startpunkte, Dienstintegration und Kommandozeilenoberfläche |
| `engineering/` | Build-, Release-, Qualifikations- und isolierte Entwicklungswerkzeuge |
| `tests/` | Vertrags-, Unit-, Packaging- und Integrationsprüfungen |

Für eine konkrete Änderung sollten Entwickler zuerst die öffentliche Vertragsebene und dann den tatsächlich zuständigen Codepfad bestimmen. Ein schneller Importtest ersetzt weder ein End-to-End-Vertragsreview noch eine Releaseprüfung.

Siehe [Komponenten und Schichten](v2-handbuch/01-grundlagen/01.03-komponenten-und-schichten.md), [Repository-Architektur](v2-handbuch/07-entwicklung/07.02-repository-architektur.md), [Erweiterungspunkte](v2-handbuch/07-entwicklung/07.04-erweiterungspunkte.md) und die weiterhin separat vorhandene [codebasierte V2-Referenz](v2-code-reference/README.md).
