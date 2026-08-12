# Soll-/Ist-Vergleich: zentrale Build- und VPS-Deploymentdokumentation

## Veroeffentlichter Stand

- Projekt-Repository: `marcosudau-vps/voice-stt-server`
- Implementierungscommit: `a617295dca7a66f816491c8ff3c3ca96f1f1ab37`
- Projektbranch: `main`, erfolgreich auf `origin/main` gepusht
- Server-/Selfhost-Repository: `marcosudau-vps/selfhost`
- Server-Kompatibilitaetscommit: `eb5afd3`
- Produktives Image: `selfhost/stt-voice:local`
- Produktiver Container: `stt-voice`, Docker-Health `healthy`
- Gepruefter Laufzeitstand: Kroko Pro-16 fuer final und realtime,
  `sharedWithFinal=true`, keine Startupfehler

Der vorliegende Abschlussvergleich und der Registerabschluss werden in einem
nachfolgenden Projektcommit veroeffentlicht.

## Planpunkte

| Planpunkt | Status | Tatsaechlicher Stand und Nachweis |
| --- | --- | --- |
| Zentrale allgemeingueltige Buildreferenz | Vollstaendig | `build/BUILD.md` beginnt mit einem Schnellstart und dokumentiert Python, Paketierung, Windows, Docker, Compose, statische Browserassets, Tests, Versionierung, Deployment und Rollback. |
| Geschlossener Kroko-Abschnitt | Vollstaendig | Community/Pro, Lizenzmodelle, Key-/Modell-/Wheel-Trennung, alle CLI-Optionen, Docker-Varianten, Pro-Wheel-Upgrade, Modell-Sharing und Fehlerdiagnose sind zentral beschrieben. |
| Getrennter VPS-Bereich | Vollstaendig | `build/vps` enthaelt README, Anleitung, Automation, Compose, Server-YAML, Service-Metadaten und Build-Area-Helfer ohne Secretwerte. |
| Kanonische Serverautomation im Projekt | Vollstaendig | `build/vps/release-voice-stt.sh` ist ausfuehrbar, standardmaessig `pro`, variantenbewusst und schreibt erzeugte Logs/Resultate ausserhalb des Projektcheckouts. |
| Kompatibilitaet am alten Serverpfad | Vollstaendig | Der alte Shellpfad delegiert als Wrapper; die alte Anleitung verweist als gleichnamige Markdown-Datei auf den neuen Ort. Beides ist im Selfhost-Commit `eb5afd3` veroeffentlicht. |
| Pro-Voraussetzungen vor Release pruefen | Vollstaendig | Preflight prueft Pro-Compose, Pro-16 fuer final/realtime, Sharing, Modell, Key-Variablennamen, Docker, Programme, sauberen Checkout und Speicherplatz ohne Secret-Ausgabe. |
| Aussagekraeftige Releaseabnahme | Vollstaendig | `/health` muss Engine, beide Modellnamen und `sharedWithFinal=true` melden; Mounts und Logs werden zusaetzlich geprueft. |
| Reversibilitaet | Vollstaendig | Vorheriges Image und persistierte `runtime.json` werden gemeinsam gesichert und bei Healthfehler gemeinsam wiederhergestellt. Community-Modelle und vorhandenes Langzeit-Rollbackimage bleiben erhalten. |
| Portabler Compose-Build | Vollstaendig | `deployment.kroko_variant` wird validiert und als `VOICESTT_KROKO_VARIANT` an Compose weitergereicht; Projektstandard bleibt bewusst `free`. |
| Alte VPS-Metadaten bereinigen | Vollstaendig | Inhalte aus `docker/vps/voice` wurden in `build/vps` konsolidiert; ein README-Verweis erhaelt historische Links. Veraltete `stt-voice`-Checkoutpfade wurden korrigiert. |
| Projektweite Verweise | Vollstaendig | README, AGENTS, Release Notes, Setup-Metadaten, Dokuindex, Installation, Kroko, FastAPI, Lizenzen, Tests, Troubleshooting, Windows und Produktionsspezifikation verweisen auf die zentrale Referenz. |
| Produktiven Pro-Betrieb erhalten | Vollstaendig | HTTP-Dateitranskription lieferte nichtleeren deutschen Text. Der WebSocket lieferte mehrere Realtime-Texte und einen Final-Text. Wake Word wurde danach auf den vorherigen Runtimewert zurueckgesetzt. |
| GitHub-Veroeffentlichung | Vollstaendig | Projektimplementierung und serverseitige Wrapper/Stackaenderungen wurden in ihren jeweiligen Repositories auf `main` gepusht. |

## Verifikation

### Statische und Konfigurationspruefungen

- `git diff --check`: erfolgreich
- Shellsyntax fuer kanonisches Release, venv-Restore und beide Wrapper:
  erfolgreich
- Portables `tools/compose.py config --quiet`: erfolgreich
- Projekt- und aktive VPS-Compose-Auswertung: erfolgreich
- Bytevergleich von VPS-Vorlagen mit aktivem Compose, Server-YAML,
  `profile.yaml` und `service.yaml`: ohne Abweichung
- Lokale Markdownlinks in 16 zentralen Dokumenten: vollstaendig aufloesbar
- Scan gegen die tatsaechlichen Kroko-/GitHub-Secretwerte: kein Treffer im
  Projekt
- Dokumentierte `stt-install-kroko`-Optionen: vom Parser akzeptiert
- VPS-Release am alten Einstiegspunkt mit `--dry-run`: erfolgreich; keine
  Aenderung ausgefuehrt

### Tests und Paketierung

- Fokussierte Build-/Compose-/Kroko-Tests: `32 passed`, `1 skipped`,
  `4 subtests passed`
- Gesamte Unit-Suite im produktionsgleichen Image mit deaktiviertem
  Deployment-Offline-Override: `378 passed`, `12 skipped`, `78 subtests
  passed`; ein reihenfolgeabhaengiger WebSocket-Replay-Test schlug im
  Gesamtlauf durch ein vorangestelltes Logevent fehl und bestand unmittelbar
  danach isoliert (`1 passed`). Die fokussiert geaenderten Bereiche waren
  davon nicht betroffen.
- Wheel und sdist mit `python -m build`: erfolgreich
- `twine check` fuer Wheel und sdist: erfolgreich
- Setuptools meldet bestehende, nicht blockierende Warnungen zur impliziten
  Paketbehandlung von `VoiceSTT.assets` und `api_fastapi_server.static`; die
  benoetigten Assets sind nachweislich im Wheel enthalten.

### Produktiver Laufzeitnachweis

- `/health`: `ok=true`, `ready=true`, keine Startupfehler
- Final: `kroko_onnx` / `Kroko-DE-Pro-16-L-Streaming-001.data`
- Realtime: dasselbe Pro-16-Modell, `sharedWithFinal=true`
- Docker: Container `stt-voice`, Healthstatus `healthy`
- HTTP-Smoke-Test mit neu erzeugter deutscher 16-kHz-WAV: nichtleerer Text
- WebSocket-Smoke-Test mit derselben WAV: drei nichtleere Realtime-Texte und
  ein nichtleerer Final-Text in rund elf Sekunden
- Wake-Word-Zustand nach Test: wieder aktiviert, OpenWakeWord / `Hey_Bro`

## Abweichungen

Es gab keine materielle Abweichung von der Gesamtplanung. Deshalb ist keine
separate Abweichungsdatei erforderlich.

Die folgenden Beobachtungen sind keine Abweichungen dieser Aktion und wurden
nicht nebenbei funktional veraendert:

- Der Ordnername `build/` wird von Setuptools als technischer Ausgabeordner
  behandelt und nicht in sdist/Wheel aufgenommen. Die kanonische Dokumentation
  ist Teil des Git-Repositories und wird aus den Paketmetadaten auf GitHub
  verlinkt.
- Ein vorhandener WebSocket-Replay-Test ist im gemeinsamen Gesamtlauf
  reihenfolgeabhaengig, besteht aber isoliert. Das ist ein gesondertes
  Testisolations-/Determinismusthema.
- Die Paket-Assetwarnungen sind Kandidaten fuer eine spaetere
  `pyproject.toml`-/Paketdiscovery-Bereinigung.

## Abschluss

Alle Abnahmekriterien der Planung sind erfuellt. Allgemeingueltiger Build,
Kroko-Sonderfall und servergebundener VPS-Betrieb sind klar getrennt, zentral
verlinkt, reproduzierbar und mit einem gemeinsamen Image-/Runtime-Rollback
abgesichert. Die Aktion kann nach Veroeffentlichung dieses Vergleichs als
abgeschlossen gelten.
