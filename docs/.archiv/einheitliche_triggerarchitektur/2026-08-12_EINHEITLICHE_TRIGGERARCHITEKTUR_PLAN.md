# Gesamtplanung: einheitliche serverseitige Triggerarchitektur

> Status: verbindliche Planung vor Umsetzung
> Stand: 2026-08-12
> Ausgangscommit: `13c1629`
> Repositoryübergreifende Planung: `zusammenarbeit/betriebsmodus-auflösen/2026-08-12_implementierungsplan_einheitliche_serverseitige_triggerarchitektur.md`

## Ausgangslage

Der veröffentlichte WebSocket-Vertrag besitzt zwei durch
`wakeWordEnabled` getrennte Nutzungsmuster. Ohne Wake Word öffnet VAD nach
Streamstart direkt ein Segment; mit Wake Word öffnet OpenWakeWord zuerst das
Aufnahmegate. Der Desktop-Client verwendet deshalb verschiedene
Streamlebenszyklen für Hotkey und Wake Word.

Beide Pfade benutzen bereits `RecorderBackedRealtimeSession`, denselben
`AudioToTextRecorder`, dieselben Segment- und Schedulerpfade und dieselben
Realtime-/Finalereignisse. Es fehlt eine ausdrückliche serverseitige
Aktivierungsgrenze, die einen manuellen Clienttrigger und ein Wake Word
gleichberechtigt vereinigt.

## Ziel

Der Server erhält additiv einen kontrollierten Aktivierungsmodus:

- eine Session und eine Streamingphase;
- optionaler manueller Trigger und optionales Wake Word, mindestens eines;
- ein gemeinsamer, generationengebundener Aktivierungsautomat;
- VAD-Aufnahme nur bei offenem Aktivierungsgate;
- korrelierte Triggerbefehle und eindeutige Bestätigungen;
- keine Doppelaufnahme bei überlappenden Triggern;
- Legacyclients und Browserclient bleiben unverändert funktionsfähig.

## Nicht-Ziele

- Keine Entfernung des Legacyvertrags in dieser Aktion.
- Keine Änderung an Transkriptpersistenz oder Modellformaten.
- Keine neue Clientauthentifizierung oder Admin-Key-Verteilung.
- Keine grundlegende Scheduler- oder Inferenzengineänderung.
- Kein Deployment ohne getrennte Freigabe nach lokaler Verifikation.

## Entscheidungen

1. `start` und `stop` bleiben ausschließlich Grenzen der Streamingphase.
2. Der neue Vertrag verwendet `activationMode=controlled` und
   `manualTriggerEnabled`; Wake-Word-Parameter bleiben im bestehenden
   sessionlokalen Vertrag.
3. `hello` und `ready` ergänzen ein versioniertes `activationConfig` sowie die
   Capability `sessionCapabilities.activationTriggers`.
4. Manuelle Aktionen verwenden `trigger` mit `activate`, `extend`, `finish`
   oder `cancel`, einer `commandId` und Quelle `manual`.
5. Der Server antwortet mit korreliertem `trigger_ack`; Statusereignisse sind
   keine Befehlsbestätigung.
6. Der erste Trigger öffnet eine Aktivierung. Weitere Trigger vereinigen sich
   mit ihr und erzeugen kein zweites Segment.
7. Legacy-VAD, Legacy-Wakeword und kontrollierte Aktivierung werden als
   ausdrückliche Recorderpolitik getrennt.
8. Alte Session-/Aktivierungsgenerationen dürfen durch Timer oder Callbacks
   keine aktuelle Aktivierung verändern.

## Betroffene Bereiche

- `VoiceSTT/core/initialization.py`
- `VoiceSTT/core/recording.py`
- `VoiceSTT/core/lifecycle.py`
- `VoiceSTT/audio_recorder.py`
- `api_fastapi_server/server.py`
- gegebenenfalls neue kleine Aktivierungsmodule in beiden Paketen
- Protokoll-, Recorder-, Multiuser- und Integrationsprüfungen unter `tests/unit`
- Cliententwicklungsdokumentation unter `docs/client-development`
- `docs/fastapi-server.md` und `docs/configuration.md`, soweit betroffen

## Umsetzungsschritte

1. Bestehende Testbaseline im separaten Worktree feststellen.
2. Recorder um eine validierte Aktivierungspolitik und thread-sichere manuelle
   Gate-API ergänzen; Legacyverhalten durch fokussierte Tests sichern.
3. Reinen Aktivierungsautomaten und Queryauflösung implementieren.
4. Triggerbefehle, Acks, Idempotenz, Timer, Finish/Cancel und Eventkorrelation
   in `RecorderBackedRealtimeSession` integrieren.
5. Handshake, Metriken und Timeline/strukturierte Events erweitern.
6. Legacy-, Kollisions-, Race-, Reconnect- und Multiuserfälle testen.
7. Dauerhafte Protokolldokumentation aktualisieren.
8. Gesamtsuite, Buildchecks und sicheren lokalen WebSocket-Smoke ausführen.
9. Soll-/Ist-Prüfung erstellen; materielle Abweichungen separat dokumentieren.
10. Register erst nach veröffentlichter und dokumentierter Prüfung abschließen.

## Risiken und Gegenmaßnahmen

| Risiko | Gegenmaßnahme |
| --- | --- |
| Kontrollierter Modus startet ohne Trigger durch VAD | explizite Recorderpolitik und Negativtest mit Sprache bei geschlossenem Gate |
| Doppelaufnahme bei Triggerkollision | genau eine `activationId`, serialisierter Automat und Gleichzeitigkeitstests |
| Timer wirkt auf neue Session | Session- und Aktivierungsgeneration in jedem Timeout prüfen |
| `finish` verliert Final | Recordergrenzen und nachlaufende Finals gezielt testen |
| Legacyclient bricht | additive Query-/Payloadfelder; vollständige Legacytests und Browser-Smoke |
| Eventduplikate | stabile Korrelation über Session, Aktivierung, Segment und `commandId` |
| Servermonolith wächst weiter | reinen Automaten in eigenem Modul halten; Sessionintegration klein halten |

## Abnahmekriterien

- Kontrollierte Session lehnt beide Trigger deaktiviert vor Recorderaufnahme ab.
- Manuell, Wake Word und beide gemeinsam funktionieren in einer Session.
- Überlappende Trigger erzeugen höchstens ein Recording und ein Final.
- Activate/Extend/Finish/Cancel sind korreliert, idempotent und
  generationensicher.
- `start`/`stop` behalten ihre bisherige Bedeutung.
- Legacyclients und Browserclient bleiben kompatibel.
- Bestehende sowie neue Servergesamttests sind grün.
- Öffentliche Dokumentation entspricht dem implementierten Vertrag.
- Soll-/Ist- und gegebenenfalls Abweichungsdokumentation sind vorhanden.

## Rollback

Der neue Vertrag ist additiv und besitzt keine persistierte Datenmigration.
Vor einem Deployment bleibt das vorherige Image unter einem unveränderlichen
Rollback-Tag erhalten. Ein Serverrollback stellt den bisherigen Vertrag wieder
her; während des server-first Rollouts benutzt der produktive Desktop-Client
weiter den Legacyvertrag. Der neue Client wird erst nach bestätigter
Serverfähigkeit veröffentlicht.
