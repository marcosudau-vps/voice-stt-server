# Issue #9 A+B: Abweichungen und offene Qualifikation

Diese Datei ergaenzt die vor Umsetzung erstellte
[Gesamtplanung](2026-10-20_PLAN.md) und den historischen
[Checkpoint A](2026-10-20_CHECKPOINT_A.md). Sie erteilt keine Gesamtfreigabe.

## D1: Bereitgestellte Branchbasis und Name

Der anfangs saubere Agentenworktree stand auf `main`
`714b1cf9199bc83b69ca7a531143d174bb60354b`, nicht auf dem beauftragten
Zielbranch. Vor Produktarbeit wurde ausschliesslich dieser isolierte
Arbeitsbranch auf den tatsaechlichen Zielstand
`e761b97334f263a6c51e84314bf3688599b84169` ausgerichtet. Fremde
Main-Aenderungen wurden nicht uebernommen, der Zielbranch nicht zurueckgesetzt.
Der appkonforme Name ist
`marcosudau-feat/issue-9-build-runtime-identity`.
Status: behoben, keine Aenderung des beauftragten PR-Ziels.

## D2: A-Checkpoint ist keine vollstaendige Dockerabnahme

Die A-Implementierung und ihre isoliert commitgebundenen Regressionen sind
belegt. Der gemeinsam genutzte lokale Docker-Desktop-Daemon ist jedoch
manuell pausiert. Er wurde weder entpausiert noch umkonfiguriert.
Echte generische Free-/Pro-Imagebuilds und deren HTTP-/WebSocket-Betrieb
waren dort **NOT_RUN**, ihre Varianten-/Imagequalifikation **NOT_PROVEN**.

B wurde gemaess dem zusammenhaengenden Auftrag trotzdem im selben Lauf
implementiert. Das ist keine nachtraegliche Gruenwertung des offenen
A-Pflichtnachweises. Zusaetzlich wurde der vorhandene RC-Workflow am
expliziten isolierten Feature-Ref tatsaechlich ausgefuehrt.
Offene echte Image-/Nativefaelle bleiben Abnahmevoraussetzung.

## D3: Konkrete bestehende RC-Startblocker

Der erste echte RC-Versuch auf
`fb509532a8b08fad2e4e5cba140b40d062e67a0b`,
[Run 39344417196](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39344417196),
scheiterte vor der nativen Qualifikation:

| Plattform | Beobachtung | Eng begrenzte Korrektur |
| --- | --- | --- |
| Linux | GitHub wies den alten Cacheaktions-Pin als veraltet ab | Aktuellen `actions/cache`-v4-Commit direkt aus der GitHub-Tagreferenz aufgeloest und wieder per vollem SHA gepinnt |
| Windows | Direkter Aufruf von `VoiceSTT/install_kroko.py` fand das Paket `VoiceSTT` nicht | Bestehenden CLI-Einstieg als `python -m VoiceSTT.install_kroko` aus dem Repositoryroot ausfuehren |

Korrekturcommit: `fe6f0e34017af9dfcbba1040997426acbff798cf`.
Der neue Regressionstest startet diesen Moduleinstieg wirklich ohne
`PYTHONPATH`; die betroffenen RC-/Workflow-/Identitaetsgatetests bestehen.
Keine neue Builder-, Release-, Manifest- oder Publikationsarchitektur.

Der
[Wiederholungsrun 39344648751](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39344648751)
erreichte auf Windows anschliessend den echten gepinnten Kroko-Builder.
Der verfuegbare Hosted-Runner hatte eine Windows/AMD64-Dockerengine;
der benoetigte Linux-Container-Build scheiterte mit
`unknown flag: --platform`. Das ist **FAIL beim Build**, kein erfolgreicher
nativer Import. Nachfolgende Windows-Installations-/Nativepruefungen sind
**NOT_RUN**, Windows- und Gesamt-RC-Qualifikation **NOT_PROVEN**.
Die vorhandene Plattformmatrix wurde nicht still reduziert oder durch
synthetische Wheels gruen gemacht. Ein geeigneter isolierter Windows-
Qualifikationshost beziehungsweise eine gesondert entschiedene
Infrastrukturkorrektur bleibt erforderlich.

Linux bestand im Wiederholungsrun die gesamte echte Packagingmatrix
(`42 passed`, 271.40 s) und erzeugte ein echtes Free-Kroko-Wheel.
Der anschliessende Hostzugriff scheiterte an dessen aus dem Root-Builder
uebernommenen Dateirechten. Die gezielte Korrektur setzt ausschliesslich
das neue, nicht geheime gespeicherte Wheel auf lesbare `0644`; Original,
Bytes, Hash, Storeformat, Locking und Promotion bleiben unveraendert.
Ein POSIX-Regressionstest prueft Rechte und unveraenderte Bytes.

Die zusaetzlich tatsaechlich ausgefuehrte
[gewoehnliche CI auf fe6f0e3](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39344966820)
zeigte einen eigenen neuen Defekt: Source-`.egg-info` und die installierte
PEP-660-`.dist-info` desselben editable Produkts wurden irrtuemlich als
zwei Installationen gezaehlt. Beide Plattformen bauten/installierten das
generische Paket inklusive Abhaengigkeiten erfolgreich, scheiterten aber
in der Serversuite. Dies ist kein Umgebungs-Skip und kein gruener CI-Lauf.

Korrektur `e3aa399033aa13fd249048e50355958179706c80` erkennt nur den
eindeutig zugeordneten gleichen Source-/editable-Metadatenalias als eine
Installation. Echte doppelte Installationen und unterschiedliche Versionen
bleiben Fehler; zusaetzliche echte editable-/Duplikatinstallationen und
direkte Unitregressionen belegen dies. Identitaetsfehler treten jetzt vor
Service-/Datenbankinitialisierung auf, damit ein fehlgeschlagener Start
keine offenen SQLite-Ressourcen hinterlaesst.

Dieser Korrekturstand wurde erneut ueber die unveraenderten
[Zweiplattform-CI-Jobs](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39346555876)
und den
[gezielten RC-Pfad](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39346559296)
geprueft. Der Soll-/Ist-Bericht nennt deren tatsaechlichen Endstatus;
die frueheren roten Runs werden nicht nachtraeglich gruen geschrieben.

Auf `e3aa399` war die gewoehnliche CI auf **beiden** Plattformen
erfolgreich. Der Linux-RC-Job bestand 43 echte Packagingfaelle und baute
anschliessend beide nativen Kroko-Wheels, generische Images und
oeffentliche Linux-Produktwheels. Die Quelle-/Paket-/Label-/Runtimebindung
in beiden echten Images bestand. Der bestehende Workflow schrieb dabei
private GHCR-Kandidatenstaging-Images, keine oeffentlichen Releases.

Die neue vollstaendige Paketinstallation deckte danach einen weiteren
bestehenden Mergefehler auf: `_rewrite_wheel_metadata` behielt die
abschliessende Leerzeile der echten setuptools-`WHEEL`-Datei vor den neuen
Headern. `Tag` und `Root-Is-Purelib` standen dadurch im Body. Pip konnte
die Datei installieren, wies das installierte Produkt bei `pip check`
aber als nicht plattformkompatibel zurueck. Das war ein Packagingdefekt,
keine fehlende Plattform und kein erfolgreicher Nativecheck.

Korrektur `89b4d69b0f3a46aac21057f2ff1c2a7081a41e62` entfernt beim
bestehenden Headerrewrite nur Leerzeilen. Ein ROT/GRUEN-Test liest die
Header jetzt mit dem echten RFC822-Parser statt nur per Stringsuche;
zwei echte installierte Free-/Pro-Fixturepakete pruefen ihre geparsten
Tags gegen `packaging.tags.sys_tags()`. Der gezielte Check umfasste
147 schnelle Tests/171 Subtests und zwei echte Installationsfaelle.
Die erneute
[CI](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39349035037)
und der
[RC-Lauf](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39349037554)
bleiben getrennte, exakt commitgebundene Nachweise. Keine Manifestformat-,
Dateinamens-, Publikations-, Promotion- oder Resumeaenderung.

Endergebnis auf 89b4d69: gewoehnliche CI auf beiden Plattformen
erfolgreich. Im RC waren alle Linuxschritte erfolgreich, einschliesslich
beider echten vollstaendigen public Free-/Pro-Installationen, `pip check`,
nativer Imports und HTTP-/WebSocket-Refusalidentitaet. Linuxevidenz wurde
als `candidate-linux` hochgeladen. Windows scheiterte unveraendert an
der Linux-Container-Voraussetzung; Gesamt-RC FAIL und gemeinsame
Assembly/Abnahme NOT_RUN. Die genaue Artefakt-/Quellbindung und Grenzen
stehen im [Soll-/Ist-Bericht](2026-10-20_UMSETZUNGSVERGLEICH.md).

## D4: Grenzen der echten Packaginginstallationen

Die opt-in Packagingmatrix baut echte Wheels/sdists und installiert sie
in frische Consumerumgebungen ausserhalb des Checkouts. `--no-deps` und
`packaging` isolieren dabei gezielt Identitaets-/Metadatenfragen. Explizit
synthetische native Testwheels belegen die Varianten-/Mismatchverdrahtung,
nicht den nativen Kroko-Code.

Diese Ergebnisse ersetzen keine vollstaendigen Free-/Pro-Installationen
mit allen Abhaengigkeiten, keinen nativen Import auf beiden Plattformen
und keine Images. Dafuer wurden eigenstaendige verpflichtende Gates im
vorhandenen RC-Pfad hinzugefuegt. Blockierte Gates bleiben blockiert;
kein Bericht uebernimmt einen synthetischen Erfolg als Nativebeleg.

## D5: Reproduzierbarkeit nicht ueberdehnen

Wiederholte saubere Builds desselben getesteten Quellstands erzeugten
byteidentische generische Wheels und identische eingebettete
Identitaetsressourcen in Wheel und sdist. Ganze sdist-Tarballs waren
dagegen nicht byteidentisch. Das wurde auch auf der unveraenderten
Baseline `e761b97334f263a6c51e84314bf3688599b84169` mit gleichem
`SOURCE_DATE_EPOCH` reproduziert:

| Baseline-sdist | SHA-256 |
| --- | --- |
| erster Build | `cc1772fc4e328f33b61b7f0cec5f41a60d38a07a558ad1de32ac345df70627ce` |
| Wiederholung | `5593959eebb7d8d3a676e3939dc23994464f21bab3d40690f2302c2e00d2698c` |

Keine neue Tarball-Byteidentitaetsgarantie und kein allgemeiner Umbau des
funktionierenden sdist-/Releasepfads. Die geforderte Herkunftserhaltung
und bisherigen Wheel-Reproduzierbarkeitseigenschaften werden separat
geprueft; Image-Reproduzierbarkeit bleibt ohne kontrollierte echte
Wiederholungsbuilds **NOT_PROVEN**.

PEP-440-repraesentierbare SemVer-Buildmetadaten werden in Paketen erhalten.
Das bestehende Docker-Tag-/Releaseformat erlaubt kein `+` im Tag.
Der Imagebuild lehnt solche Versionen deshalb vor teuren Builds explizit
ab, statt still umzubenennen oder die Publikations-/Resumevertraege zu
aendern. Keine pauschale Image-/Releasequalifikation dieser Versionen.

## D6: Neues Clientpaar, keine historische Umqualifikation

Der unveraenderte Clientstand
`b80ed8b81ad92bd02ac32553883443d2b7673bcd` wurde als neues Paar gegen
die geaenderten Servercheckpoints geprueft. Bestehende Pins, historische
Tests und Belege wurden nicht retargetet. Der neue separate Loopbacktest
verwendet echten HTTP-/WebSocket-Transport und unveraenderten Client-
Produktcode; physischer Capture, ASR/Recorder und Scheduler sind Fixtures.

Die Grenzen sind absichtlich sichtbar: keine GUI-/Geraete-/Modell-,
Proxy-/TLS-, VPS- oder produktive Paarqualifikation. Keine Aenderung am
bestehenden Client-Testserver. Diese offenen Realumgebungsfaelle werden
nicht aus den gruenen Protokoll-/Clientregressionen abgeleitet.

## Entscheidung und weiterer Status

Umsetzung A+B eingereicht, Nachweisumfang strikt begrenzt; keine
eigenstaendige Gesamtfreigabe und kein Issueabschluss. Das Register bleibt
`Pruefung offen`. Unabhaengiger PR-Review und die fehlenden realen
Plattform-/Imagequalifikationen gehen einer Merge-/Bereitstellungsentscheidung
voraus. Kein Release, Deployment, Tagging oder automatischer Merge.
