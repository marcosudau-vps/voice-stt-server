# VoiceSTT-Dokumentation

Dieser Ordner enthält die dauerhaft gültige Projekt- und
Serverdokumentation. Historische Planungen und Abschlussvergleiche liegen
getrennt unter [`.archiv`](.archiv/README.md) und ersetzen die aktuelle
Referenz nicht.

## Aktueller Funktionsstand

Die zuletzt abgeschlossenen größeren Erweiterungen sind vollständig in
die aktuelle Dokumentation eingeordnet:

- [Einheitliche serverseitige Triggerarchitektur](einheitliche-triggerarchitektur.md):
  eine Session mit einem kontinuierlichen Stream, serverautoritativer
  `ActivationController`, Recorder-Gate, `trigger`/`trigger_ack`-Vertrag,
  Kollisionssemantik von Manual und Wake Word, immutable Segmentkontexte,
  terminales Segmentledger und sessionsweit geordneter Background-Drain.
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
