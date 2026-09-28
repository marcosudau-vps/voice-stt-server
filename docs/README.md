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
  `ActivationController`, Recorder-Gate, Protokoll-V2-Wire (§12) und der
  Legacy-V1-Vertrag `trigger`/`trigger_ack`,
  Kollisionssemantik von Manual und Wake Word, Command-Phasenmatrix mit
  sessionweitem `commandId`-Replay, nicht kumulatives `refresh`,
  Daueraufnahme-Watchdog, `closing_input`-Recovery, immutable Segmentkontexte,
  terminales Segmentledger und sessionsweit geordneter Background-Drain.
- [Wake Words](wake-words.md) und
  [Triggerquellen, Wake Words & Settings (V2)](client-development/09-betriebsmodi-und-serverkonfiguration.md):
  sicherer Sessionvertrag, kanonischer Wake-Word-Katalog, OpenWakeWord-Modelle,
  Fallbacks, Isolation und Admin-API. Die ursprüngliche Einführungsdokumentation
  ist archiviert unter
  [`.archiv/session-wakeword`](.archiv/session-wakeword/).
- [Strukturiertes Logging](structured-logging.md): vier Channels, gemeinsamer
  Event-Envelope, kanonischer SQLite-first Commit, optionale kalenderbasierte
  JSONL-Spiegel, sessionbezogener Zugriff und global authentifizierter
  Admin-History-/Livezugriff über `/ws/logs`.

## Einstiegspunkte

- [Zentraler Build und Deployment](../build/BUILD.md)
- [Releaseprozess und Operator-Einrichtung](release-process.md)
- [Marcos VPS-Deployment](../build/vps/README.md)
- [Quick Start](quick-start.md)
- [Installation](installation.md)
- [Konfiguration](configuration.md)
- [FastAPI-Server](fastapi-server.md)
- [Windows-/CPU-Deployment](windows-cpu-deployment.md)
- [Transkriptions-Engines](transcription-engines.md)
- [Faster-Whisper](faster-whisper.md)
- [Kroko-ONNX](kroko-onnx.md)
- [STT-Modellverwaltung](stt-model-management.md)
- [Wake Words](wake-words.md)
- [Testing](testing.md)
- [Troubleshooting](troubleshooting.md)
- [Modulübersicht](module-map.md)

## Produktflächen und Engines

VoiceSTT wird als zwei vollständige, alternative Distributionen ausgeliefert:
`voice-stt-server` (Kroko Free) und `voice-stt-server-pro` (Kroko Pro). Beide
enthalten die passende native Laufzeit bereits, stellen dasselbe Importpaket
`voice_stt_server` und dieselbe CLI `voice-stt-server` bereit und schließen
einander aus. Welche Laufzeit installiert ist, entscheidet die Distribution -
niemals ein Runtime-Key.

Als unterstützte Produktions-STT-Engines sind ausschließlich **Faster-Whisper**
und **Kroko-ONNX** dokumentiert und qualifiziert. Weitere Adapter im Quellbaum
sind intern/experimentell und keine zugesagte Produktfläche; die Einordnung
steht in [transcription-engines.md](transcription-engines.md).

## Cliententwicklung

Der kanonische Vertrag für neue Clients (Protokoll V2 auf `/ws/v2`) beginnt
unter [Cliententwicklung](client-development/README.md). Er beschreibt
Handshake, Identitäten, Commands und Acks, Events und Sequenzierung,
Snapshot/Resync, Reconnect, das Audioformat, Wake Words, Settings,
HTTP-APIs, Authentifizierung und Fehlergrenzen.

Das Legacy-V1-Protokoll `/ws/transcribe` (Browserclient, bestehende Clients)
ist getrennt unter
[client-development/legacy-v1](client-development/legacy-v1/README.md)
dokumentiert und nicht für neue Clients bestimmt.

Prüfberichte zum V2-Vertrag:
[Audit](audits/v2-client-contract/AUDIT_SUMMARY.md) und
[unabhängige Prüfung](audits/v2-client-contract-review/INDEPENDENT_REVIEW.md).

## Archiv größerer Änderungen

Vor jeder größeren Änderung ist die verbindliche Regel unter
[`.archiv/README.md`](.archiv/README.md) zu beachten. Dort werden pro Aktion
die datierte Gesamtplanung, der spätere Soll-/Ist-Vergleich und gegebenenfalls
eine getrennte Abweichungsbegründung aufbewahrt. Die Aktion wird außerdem im
zentralen Statusregister geführt.
