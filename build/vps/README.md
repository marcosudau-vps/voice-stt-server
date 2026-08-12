# VoiceSTT auf Marcos VPS

Dieser Ordner ist die kanonische, versionierte Referenz fuer den konkreten
VoiceSTT-Build und das Deployment auf Marcos Server. Die allgemeingueltigen
Buildregeln stehen in [`../BUILD.md`](../BUILD.md). Alles hier darf absolute
VPS-Pfade und servergebundene Betriebsentscheidungen enthalten, aber keine
Secrets, Modelle, Wheels, erzeugten Logs oder Laufzeitdaten.

## Aktueller produktiver Stand

| Bereich | Wert |
| --- | --- |
| Checkout | `/home/marco/selfhost/apps/services/voice/voice-stt-server` |
| GitHub | `marcosudau-vps/voice-stt-server`, Branch `main` |
| Stack | `/home/marco/selfhost/stacks/services/voice` |
| Build-Area | `/home/marco/selfhost_outsourced/build_area/services/voice/voice-stt-server` |
| Image | `selfhost/stt-voice:local` |
| Container/Compose-Service | `stt-voice` |
| API lokal | `127.0.0.1:2000 -> 8010` |
| API oeffentlich | `https://stt.voice.marcosudau.com` |
| Kroko-Buildvariante | `pro` |
| Final/Realtime | `Kroko-DE-Pro-16-L-Streaming-001.data`, gemeinsame Instanz |
| Modelle | `/home/marco/selfhost_outsourced/models/stt/kroko_asr` |
| Runtime-Daten | `/home/marco/selfhost/data/services/voice/stt-voice` |

Der Pro-Key liegt serverlokal in
`/home/marco/selfhost/secrets/kroko.env`. Diese Datei und ihr Inhalt duerfen
nicht in dieses Repository kopiert, geloggt oder in ein Image eingebaut werden.
Compose bindet sie mit `env_file` nur beim Containerstart ein.

## Dateien in diesem Ordner

| Datei | Rolle | Aktive Serverkopie |
| --- | --- | --- |
| `release-voice-stt.sh` | kanonische Release-Automation | alter Pfad enthaelt nur einen Wrapper |
| `VOICE_STT_SERVER_RELEASE_ANLEITUNG.md` | Bedienung, Phasen, Fehlerbehandlung | alter Pfad enthaelt nur einen Verweis |
| `docker-compose.yml` | gepruefte Stackvorlage, Kroko Pro | `/home/marco/selfhost/stacks/services/voice/docker-compose.yml` |
| `stt-config.yaml` | gepruefte Serverkonfiguration | `/home/marco/selfhost/stacks/services/voice/stt-config.yaml` |
| `profile.yaml`, `service.yaml` | Selfhost-Service-Metadaten | `/home/marco/selfhost/stacks/services/voice/` |
| `build-area/` | optionaler reproduzierbarer venv-Restore | `/home/marco/selfhost_outsourced/build_area/services/voice/` |

Die Dateien unter `build/vps` sind die nachvollziehbare Vorlage. Der Stack
bleibt absichtlich im Selfhost-Repository aktiv, weil Docker Compose, Backups
und das gesamte Server-Lifecycle-Management dort orchestriert werden. Bei
Aenderungen muessen Vorlage und aktive Serverkopie im selben Arbeitsgang
abgeglichen werden.

## Schnellablauf

Am etablierten serverlokalen Einstiegspunkt:

```bash
cd /home/marco/selfhost/apps/services/voice
./release-voice-stt.sh --dry-run
./release-voice-stt.sh
```

Der Wrapper delegiert an die im Projekt versionierte Datei. Ohne explizite
Option baut die VPS-Automation `pro`. Fuer einen bewussten Community-Rollback
ist `--variant free` erforderlich.

Nach dem Release:

```bash
curl -fsS http://127.0.0.1:2000/health | python3 -m json.tool
docker inspect --format '{{.Image}} {{.State.Health.Status}}' stt-voice
docker logs --tail 200 stt-voice
```

Der Release ist nur erfolgreich, wenn `/health` die erwartete
`kroko_onnx`-Engine, das Pro-16-Modell fuer final und realtime sowie die
gemeinsame Modellinstanz meldet. Die Automation prueft diese Felder.

## Warum Pro-16 geteilt wird

Mit dem auf diesem VPS gebauten Kroko-Pro-Wheel wurde reproduzierbar ein
nativer Exit 139 beobachtet, sobald zwei lizenzierte Recognizer im selben
Serverprozess gleichzeitig initialisiert wurden. Ein einzelner Pro-Recognizer
arbeitet stabil. Deshalb verwendet die produktive Konfiguration Pro-16 sowohl
fuer final als auch realtime und setzt
`use_main_model_for_realtime: true`.

Diese Entscheidung ist server- und runtimeversionsbezogen. Eine spaetere
Kroko-Version darf erst nach einem isolierten Test mit zwei Pro-Recognizern und
anschliessendem HTTP-/WebSocket-Lasttest auf getrennte Modelle umgestellt
werden.

## Synchronisationsregel

Vor einem Projektcommit mit VPS-Aenderungen:

```bash
diff -u build/vps/docker-compose.yml /home/marco/selfhost/stacks/services/voice/docker-compose.yml
diff -u build/vps/stt-config.yaml /home/marco/selfhost/stacks/services/voice/stt-config.yaml
diff -u build/vps/profile.yaml /home/marco/selfhost/stacks/services/voice/profile.yaml
diff -u build/vps/service.yaml /home/marco/selfhost/stacks/services/voice/service.yaml
```

Erwartete Unterschiede duerfen nur absichtlich dokumentierte lokale
Zwischenstaende sein. Secret-Dateien werden nie mit `diff` ausgegeben; nur ihr
Vorhandensein und die benoetigten Variablennamen werden geprueft.

## Reversibilitaet

- Das laufende Image wird vor jedem Build als
  `selfhost/stt-voice:previous` markiert.
- Die bestehende produktive Sicherung
  `selfhost/stt-voice:rollback-before-kroko-pro-20260811` bleibt erhalten, bis
  mindestens ein weiterer unabhaengig verifizierter Pro-Release vorliegt.
- Vor Recreate sichert das Skript die persistierte
  `/data/config/runtime.json`; ein automatischer Rollback stellt sie zusammen
  mit dem vorherigen Image wieder her.
- Community-Modelle bleiben im Modellordner und werden nicht geloescht.
- Das Release-Skript entfernt keine Checkout- oder Modelldaten und verwendet
  Pfad-Guards fuer temporaere Buildbereiche.

## Erzeugte serverlokale Daten

Diese Dateien bleiben ausserhalb des Projekts:

- `/home/marco/selfhost/apps/services/voice/VOICE_STT_SERVER_RELEASE_LOG.md`
- `/home/marco/selfhost/apps/services/voice/release-result.json`
- `/tmp/release-voice-stt-*.log`
- Backups unter `/home/marco/selfhost/backups`

Dadurch bleibt der App-Checkout nach einem Release sauber und kann beim
naechsten Lauf per Fast-forward aktualisiert werden.

## Weiterfuehrung

- [`VOICE_STT_SERVER_RELEASE_ANLEITUNG.md`](VOICE_STT_SERVER_RELEASE_ANLEITUNG.md)
- [`../BUILD.md`](../BUILD.md)
- [`../../docs/engines/kroko-onnx.md`](../../docs/engines/kroko-onnx.md)
- [`../../docs/licenses.md`](../../docs/licenses.md)
