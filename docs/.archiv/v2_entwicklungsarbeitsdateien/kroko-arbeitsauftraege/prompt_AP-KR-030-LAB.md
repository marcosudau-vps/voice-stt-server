# AP-KR-030-LAB – Lokale Vorimplementierung von Packaging und Release

## Auftrag

Bereite die Umsetzung von AP-KR-030 (Unified Kroko Packaging, Build- und Releaseintegration) so weit wie technisch möglich vollständig vor.

Dies ist ein ausdrücklich genehmigter, **inoffizieller lokaler Entwicklungs- und Testlauf**.

Der offizielle AP-KR-030-Prozess wird dadurch nicht begonnen oder abgeschlossen. Es soll kein Pull Request entstehen und kein bestehender Entwicklungsbranch verändert werden.

Ziel ist, möglichst viel später notwendige Implementierungsarbeit bereits jetzt zu erledigen, obwohl AP-KR-020 noch nicht vollständig abgeschlossen ist.

Es handelt sich ausdrücklich **nicht nur um eine Planungs- oder Untersuchungstätigkeit**. Implementiere tatsächlichen Code, Konfigurationen, Packagingwerkzeuge und Tests, soweit dies unabhängig von der fehlenden Lizenzschnittstelle möglich ist.

## Repository

Hauptrepository:

`P:\GithubRepos\marcosudau-vps\voice-stt-server`

Integrationsbranch:

`feat/v2-unified-kroko`

Offener AP-020-Branch:

`feat/v2-unified-kroko-ap020`

Offener Draft-PR:

<https://github.com/marcosudau-vps/voice-stt-server/pull/12>

Der AP-020-Branch darf nicht verändert werden.

Die separat laufende Katalogentwicklung darf ebenfalls nicht verändert werden.

## Isolierter lokaler Arbeitsbereich

Erstelle folgenden lokalen Arbeitsbereich:

`P:\GithubRepos\marcosudau-vps\voice-stt-server-ap030-lab`

Nutze dafür einen separaten Git-Worktree auf Basis des aktuellen Integrationsbranches:

`feat/v2-unified-kroko`

Verwende einen Detached HEAD.

Es dürfen im LAB keine Commits, Pushes, neuen Remote-Branches, PRs oder Merges ausgeführt werden.

Git darf ausschließlich zum Lesen der Herkunft, zur Herstellung der isolierten Ausgangsbasis und zum Exportieren der lokalen Änderungen verwendet werden.

Der Hauptcheckout und alle vorhandenen Arbeitsbranches müssen unverändert bleiben.

Erstelle für Ergebnisse und Berichte ein separates lokales Verzeichnis:

`P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\kroko-umbau\AP-KR-030-LAB`

Vorhandene Dateien oder Worktrees niemals ohne Prüfung überschreiben oder löschen.

## Vorbereitende Pflichtlektüre

Lies vor der Implementierung:

- `AGENTS.md`
- `build/BUILD.md`
- `docs/release-process.md`
- `docs/testing.md`
- `docs/.archiv/kroko_unified_runtime_v2/2026-10-22_GESAMTPLAN.md`
- `docs/.archiv/kroko_unified_runtime_v2/AP-KR-010/2026-10-22_ARCHITEKTURENTSCHEIDUNG.md`
- `docs/.archiv/kroko_unified_runtime_v2/AP-KR-010/2026-10-22_ERGEBNISBERICHT.md`
- `docs/.archiv/kroko_unified_runtime_v2/AP-KR-010/2026-10-22_UEBERGABE.md`
- `docs/.archiv/kroko_unified_runtime_v2/AP-KR-020/2026-10-22_UEBERGABE_AP030.md` aus dem AP-020-Branch

Untersuche außerdem die bestehenden Packaging-, RC-, Provenienz-, Docker- und CI-Werkzeuge im Repository.

Das vorhandene Buildsystem darf nicht durch eine parallele Neuentwicklung ersetzt werden.

## Verbindliche Architektur

Übernimm die aus AP-KR-010 abgenommene Paketstrategie:

- Eine Basisdistribution `voice-stt-server` mit Community-Runtime.
- Ein optionales Addon `voice-stt-kroko-pro` ausschließlich mit Pro-Payload und zugehörigen Metadaten.
- Getrennte private Installationswurzeln für beide nativen Komponenten.
- Keine globalen Dateikollisionen von `kroko_onnx`, `_sherpa_onnx`, `sherpa_onnx` und zugehörigen DLLs.
- Keine zweite Serverimplementierung im Addon.
- Keine konkurrierenden öffentlichen CLI-Einstiege.
- Gleiche Produktversion für Basis und Addon.
- Kein Lizenzschlüssel als Buildinput.
- Keine Änderung des vorhandenen V2-Wire-Protokolls.

Vorgeschlagenes Versionsmodell:

Basisdistribution V:
`voice-stt-kroko-pro==V` als optionales Extra `kroko-pro`

Pro-Addon V:
`voice-stt-server==V` als exakte Rückabhängigkeit.

Die vorhandenen AP-010-Experimente sind ein technischer Ausgangspunkt, nicht bereits freigegebene Produktpakete.

## Phase 1 – Echte Produkt-Paketierung

Implementiere die getrennte Paketstruktur lokal im LAB.

Erforderlich:

1. Community-Runtime in der Basisdistribution.
2. Optionales separates Pro-Paket.
3. Getrennte private Native-Payloadroots.
4. Vollständige Installation aller erforderlichen nativen Dateien.
5. Behandlung des Windows-Wheel-Layouts einschließlich `.data/platlib`.
6. Korrekte relative Loaderpfade.
7. Vollständige Paketmetadaten.
8. Exakte Versionskopplung.
9. Keine Überschreibung gemeinsam verwendeter Dateien.
10. Deinstallation des Pro-Addons ohne Beschädigung der Community-Installation.

Verwende nach Möglichkeit vorhandene, nachweisbar qualifizierte native Testartefakte und die bereits dokumentierten Builder.

Erfinde keine neuen nativen Binärdateien oder Provenienzangaben.

## Phase 2 – Build- und Komponentenidentität

Bereite die bestehende Herkunfts- und Integritätsprüfung auf zwei separat installierbare Komponenten vor.

Zu unterscheiden sind:

- Serverversion und Servercommit.
- Basisdistribution.
- Pro-Addon-Version.
- Native-Komponentenrevision.
- Native-Fingerprints.
- Installierte Komponenten.
- Tatsächlich ausgewählte Runtime.
- Lizenzstatus.

Die letzten beiden Punkte sind flüchtiger Runtimezustand und dürfen nicht als unveränderliche Artefaktidentität ausgegeben werden.

Ändere die bestehende Provenienz- und Guard-Architektur nur soweit erforderlich und dokumentiere jede Vertragsänderung.

Da die endgültige Lizenzschnittstelle noch nicht feststeht, darf dafür keine fingierte Komponentenidentität oder ein behaupteter Lizenznachweis erzeugt werden.

## Phase 3 – Packaging- und Installationstests

Implementiere automatisierte Tests für:

- Basisdistribution ohne Pro-Addon.
- Installation mit optionalem Pro-Addon.
- Exakte Versionskompatibilität.
- Ablehnung inkompatibler Versionen.
- Native-Dateitrennung.
- Kollisionserkennung.
- Windows-spezifisches Wheel-Spreading.
- Native Importfähigkeit bei korrekter isolierter Auswahl.
- Deinstallation des Pro-Addons.
- Weiterhin funktionsfähige Community-Installation nach Entfernung des Addons.
- Korrekte Paket- und Buildidentität.
- Fehlerfälle bei fehlenden oder beschädigten nativen Payloads.

Teste unter CPython 3.12 auf Windows und Linux/WSL, soweit die Umgebungen verfügbar sind.

Unterscheide echte Native-Tests ausdrücklich von synthetischen Paketfixtures.

Keine echten Pro-Modellaktivierungen oder Lizenzserverexperimente in diesem Auftrag.

## Phase 4 – Docker und CI vorbereiten

Überarbeite lokal die bestehenden Build- und Workflowkonzepte für die neue Komponentenstruktur.

Ziel:

- Ein gemeinsamer Serverstand.
- Community als Basiskomponente.
- Pro als optionale native Ergänzung.
- Reproduzierbare Komponentenauflösung.
- Unveränderte Secretgrenzen.
- Keine native Kompilierung im öffentlichen Runtime-Image.
- Unveränderte Sicherheitsanforderungen für offizielle Releasekandidaten.

Die vorhandene CI-/Releasepipeline soll später die neue Struktur abbilden können.

Für den LAB-Lauf dürfen nur lokale Prüfungen oder gezielte Simulationen verwendet werden.

Keine GitHub-Workflowauslösung, kein Registryzugriff mit Schreibwirkung, kein Push.

## Phase 5 – Releasekandidaten und Rollback

Bereite die bestehenden Verfahren vor für:

- Komponentenabhängige RC-Manifeste.
- Native-Payloadprovenienz.
- Prüfung der installierten Paketkombination.
- Qualifikation unter Windows und Linux.
- Resume nach unterbrochenem Build.
- Wiederverwendung unveränderter qualifizierter Artefakte.
- Atomare Promotion.
- Rollback einer fehlgeschlagenen Releasekandidatenprüfung.

Achte besonders darauf, dass ein Community-Release auch ohne vorhandenes Pro-Addon installierbar und benutzbar bleibt.

Produktive Publishing- und Promotionoperationen müssen weiterhin fail-closed sein.

Keine bestehenden Release-Gates für den LAB-Lauf deaktivieren oder durch künstliche Erfolgswerte überbrücken.

Wenn offizielle Kandidatengates wegen fehlender sauberer Git-Provenienz im Arbeitsbaum nicht ausgeführt werden können, dokumentiere das und nutze ausschließlich die dafür vorgesehenen lokalen Development-/Dry-Run-Wege.

## Phase 6 – Fehlende Lizenzintegration ausdrücklich abgrenzen

Folgende Punkte gelten noch nicht als gelöst:

- Verbindliche Modellberechtigungen.
- Lizenzstatusaktualität.
- Widerrufs- und Ablaufsemantik.
- Endgültige native Lizenzschnittstelle.
- Reale Pro-Lizenzqualifikation.
- Noch ausstehende Änderungen an der AP-020-Runtime.

Bilde dafür nur eindeutig definierte Integrationspunkte.

Keine produktive Fake-Lizenzimplementierung.

Keine bloßen Attrappen als erfolgreich qualifizierte Komponenten ausgeben.

Keine releasefähige Pro-Distribution behaupten, solange Native-Authority, Redistributierungsbedingungen, Notices und Lizenzqualifikation nicht vollständig nachgewiesen sind.

## Phase 7 – Ergebnisse konservieren

Erstelle im lokalen Ergebnisverzeichnis:

`P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\kroko-umbau\AP-KR-030-LAB`

Folgende Dateien:

- `01_AUSGANGSLAGE.md`
- `02_IMPLEMENTIERUNG.md`
- `03_TESTERGEBNISSE.md`
- `04_OFFENE_INTEGRATIONSPUNKTE.md`
- `05_UEBERNAHMEPLAN.md`
- `06_ABSCHLUSSBERICHT.md`

Erzeuge außerdem:

`AP-KR-030-LAB.patch`

als binären Git-Diff aller Änderungen an bereits versionierten Dateien.

Neue, noch unversionierte Quelldateien müssen zusätzlich vollständig und mit Pfadangaben in einem separaten ZIP-Archiv gesichert werden.

Keine Secrets, heruntergeladenen Modelle oder nativen Lizenzdaten in Patch, ZIP oder Berichte aufnehmen.

Der Übernahmeplan muss aufzeigen, wie die LAB-Arbeit später mit der abgeschlossenen AP-020-Integration zusammengeführt und unabhängig qualifiziert werden kann.

## Abschlussanforderungen

Melde getrennt:

- Implementiert und lokal getestet.
- Implementiert, aber nur synthetisch getestet.
- Vorbereitet, aber nicht qualifiziert.
- Wegen AP-020 noch offen.
- Wegen Redistributierung oder fehlender Artefakte offen.

Eine fehlende Lizenzschnittstelle ist kein Grund, die davon unabhängige Packaging-Vorbereitung abzubrechen.

Gleichzeitig darf sie niemals durch erfundene erfolgreiche Lizenznachweise ersetzt werden.

**Es gibt ausdrücklich keine Release- oder Mergefreigabe.**

Beginne sofort mit der lokalen Vorimplementierung. Arbeite die Phasen soweit möglich vollständig ab und liefere ein reproduzierbares, später übernehmbares Ergebnis.
