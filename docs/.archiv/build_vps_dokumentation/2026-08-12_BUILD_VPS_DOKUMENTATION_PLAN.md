# Gesamtplanung: zentrale Build- und VPS-Deploymentdokumentation

## Ausgangslage

Build-, Installations- und Deploymentinformationen sind auf Root-Dokumente,
Engine-Dokumentation, Dockerfiles, Compose-Dateien, Hilfsskripte und einen
serverlokalen Release-Ordner verteilt. Der produktive VPS verwendet Kroko Pro,
waehrend mehrere reproduzierbare Buildpfade und die serverseitige
Release-Automation noch standardmaessig die Community-Variante bauen. Teile der
versionierten VPS-Metadaten verweisen zudem auf den frueheren Checkout-Namen
`stt-voice` statt `voice-stt-server`.

Der produktiv verifizierte Kroko-Pro-Betrieb benoetigt einen mit
`KROKO_LICENSE=ON` gebauten Kroko-ONNX-Runtime, einen ausschliesslich zur
Laufzeit eingebundenen API-Key und ein lokales Pro-Modell. Auf dem aktuellen
VPS muss fuer finale und Realtime-Erkennung dieselbe Pro-16-Instanz geteilt
werden, weil zwei gleichzeitig initialisierte lizenzierte Recognizer im selben
Prozess reproduzierbar einen nativen Prozessabbruch ausloesen.

## Ziele

1. `build/BUILD.md` wird die zentrale, allgemeingueltige Referenz fuer Build,
   Installation, Paketierung, Docker, Tests und Deployment des Projekts.
2. `build/vps/` dokumentiert und versioniert ausschliesslich die
   servergebundene Auspraegung, einschliesslich Compose-/Konfigurationskopien
   ohne Secrets und der kanonischen Release-Automation.
3. Der VPS-Release baut standardmaessig Kroko Pro, prueft die notwendigen
   Voraussetzungen und verifiziert nach dem Start nicht nur den Healthstatus,
   sondern auch die tatsaechlich aktiven Pro-Modelle.
4. Bestehende serverlokale Einstiegspunkte bleiben als Wrapper oder Verweis
   kompatibel, damit der etablierte automatische Release-Aufruf weiter
   funktioniert.
5. Relevante Projektdateien verweisen auf die zentrale Dokumentation und
   enthalten keine widerspruechlichen Kurzrezepte.
6. Alle Aenderungen bleiben ueber Git, Image-Tags und dokumentierte
   Rollbackschritte reversibel.

## Nicht-Ziele

- Keine Migration von `setup.py` auf `pyproject.toml` in dieser Aktion.
- Keine Entfernung oder funktionale Umgestaltung von Transkriptions-Engines.
- Keine Aufnahme von API-Keys, GitHub-Tokens, Pro-Modellen, Wheels oder
  erzeugten Laufzeitdaten in Git.
- Keine allgemeine Uebersetzung der bestehenden englischen Dokumentation.
- Keine Aenderung des oeffentlichen HTTP-/WebSocket-Protokolls.

## Entscheidungen

- Der portable Standard bleibt `free`; nur das versionierte VPS-Profil und die
  serverseitige Release-Automation verwenden explizit `pro`.
- `stt-install-kroko --build --variant pro` beziehungsweise Docker
  `--build-arg KROKO_VARIANT=pro` sind die kanonischen Pro-Buildwege.
- Der API-Key ist ein Runtime-Secret. Er wird nicht fuer den Image-Build
  benoetigt und nicht in das Image kopiert.
- Der serverlokale Release-Wrapper bleibt am bisherigen Pfad und delegiert an
  das versionierte Skript unter `build/vps/`.
- Servergenerierte Resultate und fortlaufende Release-Logs bleiben ausserhalb
  des Projekt-Repositories, damit Releases den Checkout nicht verschmutzen.

## Risiken und Gegenmassnahmen

| Risiko | Gegenmassnahme |
| --- | --- |
| Versehentliches Committen eines Secrets | Nur Secret-Dateipfade dokumentieren; vor Commit nach Schluessel-/Tokenmustern suchen. |
| Free-Image startet mit persistierter Pro-Konfiguration nicht | Runtime-Konfiguration im Release sichern und Rollbackverfahren dokumentieren. |
| Healthcheck ist gruen, obwohl Community aktiv ist | Aktive Engine-, Modell- und Sharing-Felder aus `/health` pruefen. |
| Serverautomation bricht durch den Umzug | Kompatiblen Wrapper am alten Pfad und Shell-Syntax-/Dry-Run-Test bereitstellen. |
| Portabilitaet geht durch VPS-Pfade verloren | Allgemeine und VPS-spezifische Dokumentation strikt trennen. |
| Buildanweisungen driften erneut auseinander | Zentrale Referenz verlinken und Detailduplikate in Einstiegspunkten reduzieren. |

## Betroffene Bereiche

- `build/` und `build/vps/`
- Root-Dokumentation und Paketmetadaten
- Kroko-, Installations-, Lizenz-, Test- und Deploymentdokumentation
- Docker-/Compose-Buildparameter
- VPS-Metadaten unter `docker/vps/voice/`
- serverlokaler Release-Einstieg unter
  `/home/marco/selfhost/apps/services/voice/`
- serverseitiger Compose-/Konfigurationsstand unter
  `/home/marco/selfhost/stacks/services/voice/`

## Umsetzungsschritte

1. Alle aktuellen Build-/Deploymentquellen und serverlokalen Pfadabhaengigkeiten
   inventarisieren.
2. `build/BUILD.md` mit Schnellstart, vollstaendiger Buildmatrix,
   Docker-/Paketierungswegen, Tests, Deployment und Rollback erstellen.
3. Kroko Community/Pro, Lizenzgrenzen, alle Optionen von
   `stt-install-kroko --build`, Dockervarianten und Fehlersuche geschlossen
   dokumentieren.
4. Serverdateien ohne Secrets nach `build/vps/` uebernehmen und dort die
   produktive Pro-Konfiguration als kanonisches VPS-Profil festhalten.
5. Release-Skript nach `build/vps/` verschieben, auf Pro absichern und am alten
   Ort einen Wrapper sowie Dokumentationsverweise hinterlassen.
6. Verstreute Dokumentation und Metadaten auf die zentrale Referenz ausrichten.
7. Syntax, Links, Tests, Compose-Konfiguration, Dry-Run und produktiven
   Health-/Transkriptionsstand pruefen.
8. Implementierung committen und auf `origin/main` veroeffentlichen.
9. Getrennten Soll-/Ist-Vergleich anlegen, Register abschliessen und den
   Abschluss ebenfalls veroeffentlichen.

## Abnahmekriterien

- `build/BUILD.md` beginnt mit einer kurzen, ausfuehrbaren Handlungsanleitung
  und deckt danach alle gefundenen Build-/Deploymentpfade ab.
- Kroko Pro kann aus der Dokumentation ohne implizites Wissen reproduziert
  werden; Community und Pro sind technisch und lizenzseitig getrennt.
- `build/vps/` enthaelt die VPS-Anleitung, das Release-Skript, Compose,
  Konfiguration und benoetigte Metadaten, aber keine Secrets.
- Der alte serverseitige Release-Aufruf funktioniert weiterhin ueber einen
  Wrapper und verwendet ohne Zusatzparameter Pro.
- Die produktive Instanz meldet Kroko Pro fuer final und realtime und besteht
  einen realen HTTP- sowie WebSocket-Transkriptionstest.
- Relevante Tests, Shell-Syntax, Compose-Auswertung und interne Markdownlinks
  sind erfolgreich.
- Der Projekt-Checkout ist nach Commit/Push sauber; fremde Aenderungen im
  Selfhost-Repository bleiben unangetastet.
