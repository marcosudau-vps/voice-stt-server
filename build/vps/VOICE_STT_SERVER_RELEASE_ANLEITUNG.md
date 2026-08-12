# VoiceSTT-Serverrelease auf Marcos VPS

Die kanonische Automation ist
[`release-voice-stt.sh`](release-voice-stt.sh). Der bisherige Aufruf unter
`/home/marco/selfhost/apps/services/voice/release-voice-stt.sh` bleibt als
duenner Wrapper erhalten. Allgemeine Builddetails, insbesondere alle Optionen
von `stt-install-kroko --build`, stehen in [`../BUILD.md`](../BUILD.md).

## Standardrelease

```bash
cd /home/marco/selfhost/apps/services/voice
./release-voice-stt.sh --dry-run
./release-voice-stt.sh
```

Der VPS-Standard ist Kroko Pro. `--variant pro` kann explizit angegeben werden,
ist aber nicht erforderlich. Das Skript baut immer mit
`--build-arg KROKO_VARIANT=pro`; der API-Key wird erst von Compose beim Start
aus `/home/marco/selfhost/secrets/kroko.env` eingebunden.

## Optionen

| Option | Wirkung |
| --- | --- |
| `--variant pro` | produktiver Standard, Pro-Wheel und strikte Pro-16-Pruefung |
| `--variant free` | bewusster Community-Build; vorher Stack-/Runtime-Konfiguration auf ein Community-Modell umstellen |
| `--dry-run` | alle Voraussetzungen pruefen, ohne Git, Build oder Container zu aendern |
| `--skip-build` | vorhandenes `selfhost/stt-voice:local` neu starten; nur fuer kontrollierte Wiederanlaeufe |
| `--with-venv` | zusaetzlich eine externe Build-venv samt Kroko-Runtime reproduzieren |
| `--prune` | nach erfolgreichem Release alte Dockerobjekte konservativ bereinigen |
| `-h`, `--help` | Kurzusage anzeigen |

`KROKO_VARIANT` und `EXPECTED_KROKO_MODEL` koennen auch als Environmentwerte
gesetzt werden. Ein abweichendes erwartetes Modell ist nur nach einer bewusst
versionierten Konfigurationsaenderung sinnvoll.

## Preflight

Vor jeder Aenderung kontrolliert das Skript:

- sauberen Projektcheckout,
- Stack-Compose und Server-YAML,
- laufenden Docker-Daemon, benoetigte Programme und mindestens 20 GB freien
  Speicher,
- vorhandenes erwartetes Kroko-Modell,
- bei Pro: Secret-Datei und den Variablennamen `KROKO_API_KEY`, ohne den Wert
  auszugeben,
- bei Pro: `KROKO_VARIANT: pro`, Pro-16 in der aktiven YAML und geteilte
  Modellinstanz.

Ein Fehler beendet den Lauf vor Git-/Docker-Aenderungen.

## Releasephasen

1. `origin/main` wird ohne interaktiven Prompt gefetcht und per Fast-forward
   in den sauberen Checkout uebernommen.
2. Der Checkout wird ohne `.git` in die externe Build-Area gespiegelt.
3. Optional wird die Build-venv reproduziert.
4. Ein nach Community/Pro getrennter Kroko-Builder-Cache wird aktualisiert.
5. Das vollstaendige CPU-Image wird mit der expliziten Kroko-Variante gebaut.
6. Vorheriges Image und persistierte `runtime.json` werden fuer Rollback
   gesichert; danach wird der Container ersetzt.
7. `/health` wird auf `ok`, `ready`, `kroko_onnx`, beide erwarteten
   Modellnamen und `sharedWithFinal=true` geprueft. Mounts und Logs werden
   ebenfalls kontrolliert.
8. Die Build-Area wird als `tar.gz` gesichert und entfernt.
9. Optional wird Docker konservativ bereinigt; Kroko-Cache-Images sind durch
   ein Keep-Label geschuetzt.
10. Ergebnis und Release-Log werden ausserhalb des Projekt-Repositories
    geschrieben.

## Abnahme nach einem erfolgreichen Lauf

Die automatische Healthpruefung ist die Mindestgrenze. Nach Aenderungen an
Kroko, Dockerfile, Modell oder Serverpipeline zusaetzlich:

1. `/health` formatiert ansehen und aktive Modelle kontrollieren.
2. Eine deutsche WAV-Datei an `/v1/audio/transcriptions` senden.
3. Eine Realtime-WebSocket-Session bis zu mindestens einem Partial- und einem
   korrekten Final-Text pruefen.
4. Container einmal ueber Compose neu starten und erneut Health/Logs pruefen.
5. Image-ID, Commit und Ergebnis in `release-result.json` kontrollieren.

Die Keys fuer diese Tests aus den serverlokalen Secret-Dateien laden und nie in
Kommandos, Screenshots oder Dokumentation ausgeben.

## Automatischer Rollback

Schlaegt der strikte lokale Healthcheck fehl, taggt das Skript das vorherige
Image zurueck, stellt die zuvor gesicherte persistierte Runtime-Konfiguration
wieder her und startet den Container erneut. Danach wird ein allgemeiner
`ok+ready`-Healthcheck ausgefuehrt.

Das gemeinsame Zurueckspielen ist wichtig: Ein Community-Image kann mit einer
persistierten Pro-Modellkonfiguration nicht starten. Die Stack-YAML selbst wird
vom Skript nicht veraendert; Konfigurationsaenderungen muessen vor dem Release
separat versioniert und bei einem manuellen Rollback ebenfalls rueckgaengig
gemacht werden.

## Manueller Rollback

```bash
docker tag selfhost/stt-voice:previous selfhost/stt-voice:local
docker compose -f /home/marco/selfhost/stacks/services/voice/docker-compose.yml \
  up -d --no-build --force-recreate stt-voice
curl -fsS http://127.0.0.1:2000/health | python3 -m json.tool
```

Vorher pruefen, ob die persistierte `runtime.json` zum vorherigen Image passt.
Fuer den Stand vor der Pro-Umstellung existiert zusaetzlich das Image
`selfhost/stt-voice:rollback-before-kroko-pro-20260811`.

## Fehlerbilder

- **Pro-Modell fehlt im Health:** Meist wurde ein Free-Wheel gebaut oder
  `runtime.json` ueberschreibt die YAML.
- **Exit 139 beim Laden:** Keine zwei Pro-Recognizer parallel initialisieren;
  Pro-16 teilen.
- **License does not exist/expired/entitlement:** Key und Modellberechtigung im
  Kroko-Portal pruefen; den Key nicht ausgeben.
- **Machine count exceeded:** Keine Neuaktivierungen erzwingen; Kroko-Support
  fuer eine Maschinenmigration kontaktieren.
- **Oeffentlicher Health fehlschlaegt, lokal ist gesund:** Caddy/DNS/Route
  separat pruefen; das Skript protokolliert dies als Warnung.

## Pflege

Bei jeder serverseitigen Aenderung muessen die aktiven Dateien unter
`/home/marco/selfhost/stacks/services/voice` und ihre Vorlagen unter
`build/vps` gemeinsam aktualisiert werden. Secrets und fortlaufende Logs bleiben
ausschliesslich im Selfhost-Bereich.
