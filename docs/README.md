# VoiceSTT-Dokumentation

Dieser Ordner enthält die dauerhaft gültige Projekt- und
Serverdokumentation. Historische Planungen und Abschlussvergleiche liegen
getrennt unter [`.archiv`](.archiv/README.md) und ersetzen die aktuelle
Referenz nicht.

## Aktueller Funktionsstand

Die zwei zuletzt abgeschlossenen größeren Erweiterungen sind vollständig in
die aktuelle Dokumentation eingeordnet:

- [Sitzungslokale Wake-Word-Konfiguration](session-wakeword-erweiterung.md):
  sicherer Sessionvertrag, OpenWakeWord-Modellkatalog, Fallbacks, Isolation und
  Betriebsnachweis.
- [Strukturiertes Logging](structured-logging.md): vier Channels, gemeinsamer
  Event-Envelope, kalenderbasierte JSONL-Dateien, SQLite-Historie,
  sessionbezogener HTTP-Zugriff und `/ws/logs`.

## Einstiegspunkte

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
Authentifizierung, Fehlergrenzen, das Clientzustandsmodell und die
sessionlokale Wake-Word-Auswahl.

## Archiv größerer Änderungen

Vor jeder größeren Änderung ist die verbindliche Regel unter
[`.archiv/README.md`](.archiv/README.md) zu beachten. Dort werden pro Aktion
die datierte Gesamtplanung, der spätere Soll-/Ist-Vergleich und gegebenenfalls
eine getrennte Abweichungsbegründung aufbewahrt. Die Aktion wird außerdem im
zentralen Statusregister geführt.
