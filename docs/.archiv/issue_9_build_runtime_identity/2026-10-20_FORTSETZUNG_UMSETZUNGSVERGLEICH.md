# Issue #9: fortgesetzte A+B-Qualifikation

## Exakte Implementierungsstaende

| Stand | Commit / Tree / Quellzeit |
| --- | --- |
| Bytegleiche Channel-Wiederbeschaffung | `50e980f7af8051b4b1b2ad482e45f162ccb7f385` / `ecbcfa4220e1f40f48ecf8004011a6657a857233` / `2026-10-20T01:51:37Z` |
| Gemeinsamer echter HTTP-/WS-Probe fuer native Wheels und Images | `104b73f9bd845d584a22d17db71af453e1f7c97e` / `d76622c3d80b8759d8d3a3f2e4af7dafe958c1b0` / `2026-10-20T02:02:17Z` |
| Final qualifizierter Code: kalte Identitaet und Modellbereitschaft getrennt | `d99633a95166d168c2adb8c0fd015f435ff5ec23` / `1b5760921d12383b8eba00b7371a42435a86c8c1` / `2026-10-20T02:32:19Z` |

Alle drei Codepunkte sind veroeffentlicht. Ein nachfolgender reiner
Dokumentationscommit ist keine neue Identitaet dieser Artefakte.
Ausgangs- und Zielbranch ist
feat/einheitliche-triggerarchitektur-distributed; dessen zuletzt erneut
gelesener HEAD ist unveraendert e761b97334f263a6c51e84314bf3688599b84169.
Arbeitsbranch: marcosudau-feat/issue-9-build-runtime-identity.
Einziger kumulativer [PR #10](https://github.com/marcosudau-vps/voice-stt-server/pull/10);
der [vollstaendige Diff](https://github.com/marcosudau-vps/voice-stt-server/pull/10/files)
ist die Dateiliste aller A+B-Aenderungen. Der
[urspruengliche Soll-/Ist-Bericht](2026-10-20_UMSETZUNGSVERGLEICH.md)
bleibt ein historischer Snapshot; dieser Nachtrag schliesst dessen
offene technische Windows-/Vier-Wheel-/Image-Endpunktnachweise.
Die vor Umsetzung registrierten
[Locatorplanung](2026-10-20_MANIFEST_LOCATOR_PLAN.md) und
[Imageplanung](2026-10-20_IMAGE_ENDPOINT_PLAN.md) werden hier getrennt
gegen tatsaechliche Resultate geprueft. Die
[materiellen Abweichungen](2026-10-20_FORTSETZUNG_ABWEICHUNGEN.md)
benennen insbesondere die neuen konkreten Windows-Fingerprints.

## A: Runtimeidentitaet und realer Transport

Produktcode und bestehende V2-Nachrichten bleiben gegenueber dem
implementierten A+B-Stand unveraendert. Der vorhandene selbstenthaltene
Installationsprobe startet jetzt einen echten Uvicorn-Server auf einem
gebundenen Ephemeralport, sendet echte HTTP-Anfragen und fuehrt einen
echten WebSocket-Handshake aus. HTTP-Proxys sind ausgeschaltet und der
WS-Client erhaelt einen ausdruecklichen Loopbacksocket.

Geprueft werden unveraenderte Paketressource, echter Nativeimport,
Info/no-store/complete, Sourcecommit/-tree/-datum, Distribution/
Paketversion/native Variante, wiederholte Infoantwort und Hubinstanz,
beide Settingsprojektionen, OpenAPIversion und V2-Protokollrefusal
mit derselben Identitaet. Ein erster echter Loopbackserver ohne
Lifespanstart prueft HTTP-200-Info bei ready=false. Danach prueft
normaler Startup desselben Appzustands identische Info sowie
sttReady=false und ok=false ohne Modelle. Das bestehende ready
bezeichnet Initialisierungsabschluss, nicht gesunde Modelle;
die Produktsemantik wurde nicht geaendert.
Bounded Startup/Shutdown und Fehlercleanup ersetzen keine Fehler durch
einen Erfolgsmarker.

Generische Images behalten voicestt als Besitzer und null als native
Variante in der **Paketressource**. Separater nativer Free-/Pro-Import,
Runtimeantwort und OCI-Label muessen zusammenpassen. Ein frischer
unprivilegierter --rm/--network-none-Container prueft den unveraenderten
installierten Server ohne ASGI-/Native-Fixtures, Hostports, Hostmounts,
Modelle oder Downloads. Der vorherige Label-/Metadatencheck bleibt
zusaetzlich erhalten; der Endpunktcheck liegt vor dem Stagingpush.

## B: bytegleiche Wiederbeschaffung und Provenienz

Frischer Download der neuen commitgebundenen Channelquelle:
**91833 Bytes**, SHA-256
`4c81e902fb7fe2acea779b828e6dc548fe0bbb693df50eda0224263c16686bdd`,
Visual Studio 17.14.39. Die Referenz auf das unveraendert gepinnte
Microsoft-Paketmanifest ist enthalten. Der vorherige Bytecount und
SHA-256 bleiben die Inhaltsautoritaet, nicht die Communityquelle.
Alle bisherigen Groessen-/Hash-/xwin-/SDK-/CRT-Gates bleiben aktiv.

Der vorhandene Fingerprintrechner bindet die neue explizite URL korrekt
als Input. Neue Werte: Free `b28bc64f9ce3e8e0`, Pro `26d5afecf0f5cc17`,
Toolchainauthority `103518aa86b90a20`. Keine manuell festgelegten IDs.
Die neuen Golden-/Ruecksetzungstests rekonstruieren beide vorherigen
IDs und vollstaendigen Dokumente allein mit der alten URL; Linux bleibt
unveraendert. Nativequellen, Versionen, Compilerflags, Builder-/
Patchfunktionen, Revisionen und deren Guarddigests sind unveraendert.

## Lokale und gewoehnliche CI-Regressionen

| Lauf | Tatsaechliches Ergebnis |
| --- | --- |
| Vor Locatorumstellung: neue Golden-/Ruecksetzungstests | erwartetes RED: vier Subtestfehler, zwei Testkoerper; keine gruene Umdeutung |
| Locatorumstellung: betroffene sieben Unitdateien | 308 passed, 1 skipped, 284 Subtests; 26.12 s |
| Erster Image-/Wheelprobe auf 104b73f, neun Unitdateien einschliesslich Dockervertrag | 384 passed, 1 skipped, 10 Dependencywarnings, 284 Subtests; 33.05 s |
| Deterministische Lifecycle-Regression vor Probekorrektur | vier erwartete REDs auf echtem Transport; kein PASS |
| Finaler Probe auf d99633a, derselbe Selektor | 384 passed, 1 skipped, 10 Dependencywarnings, 284 Subtests; 40.45 s |
| [PR-CI zum Locatorhead 50e980f](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39355757089) | beide Plattformjobs erfolgreich |
| [PR-CI zum Zwischenstand 104b73f](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39356730498), Ubuntu | 2147 passed, 14 skipped, 1 Warning, 1326 Subtests; 307.19 s |
| Dieselbe CI, Windows | 2146 passed, 15 skipped, 1 Warning, 1326 Subtests; 625.20 s |
| [Finale PR-CI auf d99633a](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39359470290), Ubuntu 24.04 | 2147 passed, 14 skipped, 1 Warning, 1326 Subtests; 389.06 s |
| Dieselbe finale CI, Windows | 2146 passed, 15 skipped, 1 Warning, 1326 Subtests; 394.28 s |
| Finaler echter RC, Linux-Packagingmatrix | 43 passed; 280.19 s |

Beide finalen CI-Jobs enthalten echte generische Wheel-/sdist-Builds,
twine check, saubere Installationen, pip check, Imports/Scripts/Assets.
Diese gewoehnliche PR-CI ist kein Ersatz fuer den exakten dispatch-only
RC mit echten nativen Free-/Pro-Produkten.

Der finale lokale Selektor:

```text
python -m pytest -q tests\unit\test_build_production.py tests\unit\test_production_docker_contract.py tests\unit\test_qualify_build_identity.py tests\unit\test_release_candidate.py tests\unit\test_release_workflows.py tests\unit\test_kroko_fingerprint.py tests\unit\test_install_kroko_cpu.py tests\unit\test_kroko_artifact_store.py tests\unit\test_build_distribution.py --tb=short
```

Lokale neue Probetests verwenden deklarierte ASGI-/Native-Fixtures:
echter HTTP-/WS-Transport, vier generische/public-Free-/Pro-Zuordnungen,
HTTPfehler, widerspruechliche WS-Identitaet, nachgewiesener Servercleanup.
Dockeraufrufe und fehlende/ungueltige/mehrdeutige/native oder
quellwiderspruechliche Belege sind gesondert negativ geprueft.
Kein synthetisches Wheel oder Fixture wird als echte native Abnahme
ausgewiesen; Skips sind kein PASS.

## Unveraenderter Client, neuer Qualifikationsstand

Client `feat/client-v2`:
`b80ed8b81ad92bd02ac32553883443d2b7673bcd`, keine getrackten Aenderungen.
Historische Clienttests/-pins/-belege unveraendert.
Der opt-in Paartest wurde in einem separaten sauberen detached
Servercheckout erneut ausgefuehrt:

| Exakter Server | Ergebnis |
| --- | --- |
| 50e980f | 1 passed, 10 Dependencywarnings; 11.54 s |
| 104b73f | 1 passed, 10 Dependencywarnings; 3.81 s |
| d99633a | 1 passed, 10 Dependencywarnings; 4.53 s |

Echter HTTP-/WebSocket-Transport und unveraenderte Clientproduktmodule
pruefen neue Identitaet, Settings, Verbindungen/Reconnect, Audioframes,
Trigger/Controls, Logstream und Refusals. Recorder/ASR/Scheduler und
physischer Capture sind Fixtures. Kein GUI-, Geraete-, Realmodell-,
Proxy-/TLS-/VPS- oder bestehender Testserverbeleg. Die neuen
Servercommits werden als neue Paare behandelt, nicht rueckwirkend in
historische Clientqualifikation eingetragen.

## Echte Kandidaten und Gesamtintegration

Der [Locator-RC 39355754541](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39355754541)
verwendet exakt 50e980f und besteht erstmals alle vier Jobs,
einschliesslich echter nativer Windows-Free-/Pro-Installationen und
gemeinsamer RC-Abnahme. Der nachfolgende
[Endpoint-RC 39358314020](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39358314020)
auf 104b73f ist dagegen FAIL: Windows-Crossbuild erfolgreich,
Windowsinstallation und erstes generisches Image scheitern an der
zeitabhaengigen ready-Annahme. Assembly korrekt uebersprungen.
Dieser rote Lauf wird nicht in einen Erfolg umgedeutet; Ursache und
bewusste Korrektur stehen separat in der Abweichungsdatei.

Der [finale RC 39359464011](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39359464011)
verwendet exakt d99633a und ist **SUCCESS**:

| Job | Ergebnis / UTC |
| --- | --- |
| Linux, ID 118421948764 | SUCCESS; 02:32:26 bis 02:47:39 |
| Windows-Crossbuild unter Ubuntu, ID 118421948905 | SUCCESS; 02:32:26 bis 02:33:09 |
| Echte Windowsqualification, ID 118422176373 | SUCCESS; 02:33:12 bis 02:37:28 |
| Gemeinsame Assembly, ID 118426371689 | SUCCESS; 02:47:42 bis 02:48:12 |

Beide generischen Images bestehen den tatsaechlichen containerinternen
HTTP-/WS-Probe. Beide public Varianten werden auf Linux und Windows
frisch vollstaendig installiert, pip check/native Imports und derselbe
HTTP-/WS-Probe bestehen. Gemeinsame Assembly gleicht vier Wheelbytes,
beide Installationsberichte, Nativeherkunft, saubere Sourceidentitaet,
RC-Manifest und finales Inventar ab. Nativecache-Reuse bleibt
hash-/inputgeprueft und ist kein erneuter nativer Byte-Reproduzierbarkeitsbeleg.

### Finales erreichbares Artefakt und separate Nachpruefung

Artefakt **release-candidate-d99633a95166d168c2adb8c0fd015f435ff5ec23**,
[ID 12236898094](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39359464011/artifacts/12236898094),
**164943602 Bytes**, Archivdigest
`sha256:fc7e74eaf1bd67409efd2a4ff8c23999a9b306e31458857f746737ccadd71197`,
Ablauf **2027-01-18T02:32:23Z**. Die regulaere 90-Tage-Retention
bleibt unveraendert; die kurzlebigen Plattformzwischenartefakte ersetzen
nicht dieses finale Bundle.

Das finale ZIP wurde separat heruntergeladen und tatsaechlich gegen
GitHubs Groesse und Archivdigest gehasht. Im sauberen detached
d99633a-Checkout bestehen erneut:

```text
python tools\qualify_build_identity.py --candidate-dir <extrahiertes-Bundle> --check-reports
python release.py manifest validate <extrahiertes-Bundle>\rc-manifest.json
```

Ausserdem alle **62** inventarisierten Dateien selbst gehasht, Groessen,
eindeutige relative Pfade und vollstaendige Inventarabdeckung geprueft.
RC-Status QUALIFIED, Quelle/Tree/Datum, vier native Wheel-Tags,
Paketressourcen, Nativehash-/Fingerprintzuordnungen, beide wirklichen
Installationsberichte sowie Buildlabels/Stagingdigests stimmen ueberein.
Die Linux-Runlogs enthalten vier erfolgreiche Endpointprozesse: zwei
generische Images und zwei public Produkte. Der bestehende Runner
und sein Aufrufer projizieren den jeweiligen Image-stdout doppelt in
den Gesamtlog; die Kopien sind bytegleich. Das ist kein doppelter
Marker innerhalb eines Prozessstdout und aendert den strikten Parser nicht.

| Public Wheel auf d99633a | SHA-256 |
| --- | --- |
| voice_stt_server-2.0.0-cp312-cp312-linux_x86_64.whl | `35b45ae063c2e67c675286f494929e8b95b235744f0d767df86a3d3eeb565863` |
| voice_stt_server_pro-2.0.0-cp312-cp312-linux_x86_64.whl | `d456f136bd6f1c687c5756ebd8511109663e93b91a18d92281f0eb8036eadeff` |
| voice_stt_server-2.0.0-cp312-cp312-win_amd64.whl | `9c93d57f5e3c53a619b53f40228d6b2e4ce323a179de0ab85e9280cace35a2a0` |
| voice_stt_server_pro-2.0.0-cp312-cp312-win_amd64.whl | `d2a4c2b86687c7311bcbc625b14b9a4acaa895d6e3ff029d2040ac52e75a1dbd` |

| Eingebettete Nativeherkunft | Fingerprint / nativer Wheel-SHA-256 |
| --- | --- |
| Linux Free | `1b2d237c4ab12480` / `266fed2ebd1d54106a956e91203a4ad52bcf8252726085108f111581b2ee8645` |
| Linux Pro | `9e5f8ebbd9821e03` / `7d0e8d4353fe841b708d5442cb86ddf1c5e6b493b9c2f073387a7e4dd9c6da53` |
| Windows Free | `b28bc64f9ce3e8e0` / `691e0fe6fe342d290139495aedd91f387282d3ccb5c740126de7fea3094ddeba` |
| Windows Pro | `26d5afecf0f5cc17` / `3b28212d49f03cffc04ad479e9ba06a0ee3eedf1aa7e78cd40860e22016faea7` |

Generische private Stagingdigests:
Free `sha256:a7c6a5c31b3d0828a949f2a64f9b00d64b059e8ff26997c13cfea1c10764916a`,
Pro `sha256:dce285ebc10a8595454d5c8a5ebe56c4a9ba5432c75cc7afcb6d7e6c19b3f376`.
Beide installieren voicestt und die separat gebundene Nativevariante;
kein Zugriff auf laufende produktive Images oder bestehenden Testserver.

### Reproduzierbarkeit auf dem exakten finalen Code

Sauberer detached d99633a-Checkout, Python 3.12.10, zweimal
`python -m build --wheel --sdist --no-isolation --outdir <extern>`,
SOURCE_DATE_EPOCH aus dessen Git-Commitzeit:
beide generischen Wheels **bytegleich**, 30097032 Bytes,
SHA-256 `273f6ca2bb3f3359f0b012974bab4a250f0e568d34a93ca7a1bdf70e2100fab4`.
Alle vier Wheel-/sdist-Identitaetsressourcen bytegleich und exakt auf
Commit/Tree/Datum gebunden; Quellbaum unveraendert sauber.
Die gesamten sdists sind **nicht** bytegleich:
erster 29881223 Bytes,
SHA-256 `39542a9caf18c53801da6ce82bf330fe81fe65a37bdd0f8c4cd9e94d796036b0`;
zweiter 29881202 Bytes,
SHA-256 `ab7da034f316e4fe9df3c6c832fa530ba2c30257ac44017ac1cb41e7a2b0af01`.
Die schon separat dokumentierte sdist-Archivgrenze wird nicht als neue
Identitaetsreproduzierbarkeit oder als PASS des Gesamtarchivs umbenannt.
Kein plattform-/toolchainuebergreifender Gleichheitsanspruch.

### Planabgleich und Abschlussgrenze

| Pflichtbereich | Tatsaechlicher Stand |
| --- | --- |
| A: Runtime-/Settings-/Info-/Wire-/Hub-/Cachevertrag | implementiert; direkte Regressionen und nun echte generische Free-/Pro-Images/Endpunkte bestanden |
| B: Legacy/Free/Pro, Original-SemVer, alpha/beta/rc/Buildmetadaten, sdist ohne/fremdes Git, Source/editable und Mismatches | echte Python-Packagingmatrix bestanden; Native-Fixtures dort ausdruecklich kein Nativequalifikationsbeleg |
| B: echte native Produkte und Source-/Paket-/Imagekette | vier echte vollstaendige Installationen plus zwei echte generische Images und gemeinsamer RC auf d99633a bestanden |
| V1-Muster minimal auf V2 uebertragen | Ubuntu-Crossbuild und native Windowsinstallation getrennt bestanden; keine V1-Skripte/Pins uebernommen |
| Provenienz und Reproduzierbarkeit | saubere Source-/Ressourcen-/Hashbindungen und bytegleiche generische Wheels bestanden; ganze sdists und native/Image-Byte-Reproduzierbarkeit nicht behauptet |
| Bestehender Client und Releasevertraege | unveraendertes Clientprodukt neu gepaart bestanden; Manifestformat/Publikation/Promotion/Resume unveraendert |
| Unabhaengige Gesamtabnahme, Merge/Bereitstellung | Pruefung offen; ausdruecklich nicht durch den ausfuehrenden Agenten freigegeben |

Keine beauftragte technische Windows-/Vier-Wheel-/Image-Endpunktpruefung
bleibt nach dem finalen RC als NOT_RUN offen. Realmodelle, Geraete/GUI,
TLS/Proxy/VPS und ganze native/Image-Byte-Reproduzierbarkeit bleiben
die ausdruecklichen NOT_RUN/NOT_PROVEN-Grenzen; der erfolgreiche
Identitaets-RC ist kein allgemeiner Betriebs- oder Releasefreigabebeleg.

Generierte Artefakte und volle lokale Logs bleiben ausserhalb von Git
im Sitzungsbereich. Relevante neue Dateien: image-readiness-regressions.log,
image-readiness-client.log, image-readiness-ci-{linux,windows}.log,
image-readiness-rc-linux.log, image-readiness-repro-evidence.json,
final-rc-independent-validation.log und final-rc-independent-evidence.json.
Die verlinkten Actionsruns und das hashgebundene finale Bundle sind die
erreichbaren externen Nachweise.

Keine Manifest-/Publikations-/Promotions-/Resumeaenderung. Dauerhafte
Buildauthority: [build/BUILD.md](../../../build/BUILD.md).
Kein oeffentlicher Release, Deployment, Git-Tagging, Merge, produktiver
Docker-/VPS-Zugriff oder Aenderung bestehender Client-Testserver.
Unabhaengiger Review und gesonderte Uebernahmeentscheidung bleiben
ausserhalb der technischen Kandidatengates.
**Registerstatus: Pruefung offen.** Der unabhaengige PR-Review bleibt
Voraussetzung einer getrennten Uebernahmeentscheidung.
