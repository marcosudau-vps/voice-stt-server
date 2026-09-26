# VoiceSTT-Dokumentation

Dieser Ordner enthält die dauerhaft gültige Projekt- und
Serverdokumentation. Historische Planungen und Abschlussvergleiche liegen
getrennt unter [`.archiv`](.archiv/README.md) und ersetzen die aktuelle
Referenz nicht.

## V1-Release und spätere V2-Integration – zuerst lesen

- [Finaler V1-Release- und Publikationsplan](v1-release-final-plan.md):
  Freigabegates, Candidate, PyPI Free/Pro, Docker Hub, GHCR, Git-Tag,
  GitHub Release und anschließender separater Client-Release.
- [V1/V2-Historienübergang](v1-v2-history-transition.md): warum V1 als
  einzelner Commit auf `main` liegt und wie der spätere V2-Merge beide
  Historien bewahrt, ohne den qualifizierten V2-Dateibaum zu vermischen.
- [V1-Produktvertrag](v1-preservation-release.md): Free/Pro-Wheels,
  Modelle, Wakewords, Docker und Qualifikation.

Diese Dokumente sind auch für die V2-Releaseplanung maßgeblich. Der
V2-Canonical-Zweig muss sie vor seinem endgültigen Source-Freeze bewusst
übernehmen, wenn sie nach dem V2-Merge im Ergebnisbaum erhalten bleiben
sollen; der V2-Merge selbst darf den qualifizierten V2-Tree nicht nachträglich
verändern.

## Aktueller Funktionsstand

Die zuletzt abgeschlossenen größeren Erweiterungen sind vollständig in
die aktuelle Dokumentation eingeordnet:

- [Sitzungslokale Wake-Word-Konfiguration](session-wakeword-erweiterung.md):
  sicherer Sessionvertrag, OpenWakeWord-Modellkatalog, Fallbacks, Isolation und
  Betriebsnachweis.
- [Strukturiertes Logging](structured-logging.md): vier Channels, gemeinsamer
  Event-Envelope, kanonischer SQLite-first Commit, optionale kalenderbasierte
  JSONL-Spiegel, sessionbezogener Zugriff und global authentifizierter
  Admin-History-/Livezugriff über `/ws/logs`.

## Einstiegspunkte

- [Zentraler Build und Deployment](../build/BUILD.md)
- [Marcos VPS-Deployment](../build/vps/README.md)
- [Quick Start](quick-start.md)
- [Installation](installation.md)
- [Konfiguration](configuration.md)
- [FastAPI-Server](fastapi-server.md)
- [Windows-/CPU-Deployment](windows-cpu-deployment.md)
- [Transkriptions-Engines](transcription-engines.md)
- [Wake Words](wake-words.md)
- [Testing](testing.md)
- [Troubleshooting](troubleshooting.md)
- [Modulübersicht](module-map.md)

## Cliententwicklung

Der vollständige Vertrag für Browser-, Desktop- und andere API-Clients beginnt
unter [Cliententwicklung](client-development/README.md). Er beschreibt
Session- und Server-Scope, WebSocket-Frames, Serverereignisse,
Authentifizierung, Fehlergrenzen, das getrennte Audio-/Eventstream-
Zustandsmodell, globale Adminlogs und die sessionlokale Wake-Word-Auswahl.

## Archiv größerer Änderungen

Vor jeder größeren Änderung ist die verbindliche Regel unter
[`.archiv/README.md`](.archiv/README.md) zu beachten. Dort werden pro Aktion
die datierte Gesamtplanung, der spätere Soll-/Ist-Vergleich und gegebenenfalls
eine getrennte Abweichungsbegründung aufbewahrt. Die Aktion wird außerdem im
zentralen Statusregister geführt.
