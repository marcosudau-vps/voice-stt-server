# AP-SRV-070 / W4C-R01-C1 - Correction Report

## Scope

Enger Korrekturlauf zur Requalifizierung zweier Root-Review-Findings aus
W4C-R01. Keine Sourceaenderung, kein neuer Commit, kein Push. Beide Findings
wurden mit zusaetzlicher, direkter Evidence im bereits gebauten Image
`voice-stt-server:fa3c9dc887b0` (identisch zum in W4C-R01 dokumentierten
Free-Image, `docker inspect .Id =
sha256:22c707ec3c5bc200951709988f35a8283f3ad1b74cc923f402af348759333a9f`)
und dem unveraenderten, bereits committeten `docker-compose.yml`
requalifiziert.

## Finding A - Managed Model Store Persistence (G22)

**Ergebnis: PASS.**

Der urspruengliche W4C-R01-Nachweis pruefte nur einen generischen Marker
direkt unter `/var/lib/voicestt`, nicht die kanonischen Managed-Store-Pfade
selbst. Dieser Korrekturlauf hat direkt in
`/var/lib/voicestt/models/stt/fasterwhisper` und
`/var/lib/voicestt/models/stt/kroko_asr` je eine Testdatei als effektiver
Runtime-Benutzer (uid 10001, `voicestt`) angelegt, einen vollstaendigen
Container-Recreate durchgefuehrt und danach Existenz, Inhalt (SHA-256-
identisch), Schreibbarkeit und Container-Health erneut geprueft - alles mit
Erfolg.

Dabei wurde eine relevante, dokumentierte Randbeobachtung gemacht: Ein
frischer Bind-Mount auf `/var/lib/voicestt` ueberdeckt vollstaendig die im
Image bereits angelegten Managed-Store-Verzeichnisse (Standard-Bind-Mount-
Semantik); ohne vorherige Provisionierung existieren sie daher nicht
automatisch, sondern erst beim ersten echten Provisionierungsschreibzugriff
(so wie es `AtomicModelProvisioner` im Produktcode ohnehin bereits tut). Das
ist kein Fehler und keine Abweichung vom dokumentierten Verhalten, aber eine
Praezisierung gegenueber der ungenauen Formulierung "der Model Store bleibt
erhalten" im urspruenglichen W4C-R01-Bericht.

Vollstaendige Evidence: `Evidence/01_Managed_Model_Store_Persistence/`.

## Finding B - Graceful Shutdown (G24/G25/G26)

**Ergebnis: PASS.**

Der urspruengliche Nachweis zeigte nur Exit-Code 143 und eine kurze
Stopdauer - beides notwendig, aber fuer sich allein kein Beweis, dass der
Application-Shutdownpfad tatsaechlich durchlief. Dieser Korrekturlauf hat
zusaetzlich zwei voneinander unabhaengige, bereits vorhandene (nicht fuer den
Test hinzugefuegte) technische Signale gesichert:

1. Uvicorns eigene ASGI-Lifespan-Lifecycle-Meldungen im Containerlog
   ("Shutting down" / "Waiting for application shutdown." / "Application
   shutdown complete."), die exakt den Lauf des projekteigenen
   `lifespan()`-Codes (`api_fastapi_server/server.py`) umschliessen.
2. Einen persistenten, zeitlich praezise passenden Eintrag im SQLite-
   Event-Store (`server.stopping` / "Server wird beendet"), der ausschliesslich
   von `VoiceSTTService.stop()` erzeugt wird - 44 Millisekunden vor dem vom
   Docker-Daemon erfassten `FinishedAt`-Zeitstempel.

Kombiniert mit der bereits bekannten schnellen, unerzwungenen Beendigung
(Exit 143, kein SIGKILL/OOM, weit unter dem 15s-Stop-Timeout) belegt das den
vollstaendig durchlaufenen Application-Shutdownpfad eindeutig.

Vollstaendige Evidence: `Evidence/02_Graceful_Shutdown/`.

## Keine Sourceaenderungen

In diesem Lauf wurde keine Datei im Source-Repository geaendert. Der lokale
HEAD bleibt `e5f76bf1e4fd28e68624f30140fcf8ec6876db96`, identisch zum
W4C-R01-Endstand. Kein Push wurde ausgefuehrt oder versucht.

## Status

`W4C-R01-C1 EVIDENCE COMPLETE — READY FOR EXTERNAL ROOT REVIEW`
