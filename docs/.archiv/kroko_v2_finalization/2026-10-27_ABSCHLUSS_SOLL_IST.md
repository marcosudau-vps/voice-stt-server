# Abschluss-Soll/Ist: Unified Kroko V2

2026-10-27. **Status: BLOCKED – technische Windows-Pflichtnachweise und
öffentliche Redistributionsfreigabe offen.** Implementierung und lokal verfügbare
Qualifikation sind abgeschlossen; diese Akte behauptet keinen vollständigen RC.

## Quellen und Arbeitsgrenzen

Basis unverändert: `30fac0d6a83139d67daac9c71da4e9a3260b0b15` auf
`feat/v2-unified-kroko` (erneut remote geprüft). Arbeitsbranch ausschließlich
`work/kroko-v2-finalization-20261027`; Draft-PR
[#16](https://github.com/marcosudau-vps/voice-stt-server/pull/16) zielt auf diese Basis.
Keine Übernahme in `feat/einheitliche-triggerarchitektur` oder `main`, kein Merge,
Deployment, öffentlicher Tag, Registry-Push oder öffentliche Veröffentlichung.
Modelle und Test-Key wurden nur in isolierten Tests gelesen. Binärartefakte,
Modelle, Secrets und erzeugte Logs sind nicht in Git abgelegt.

Der [Originalauftrag](2026-10-27_ORIGINALAUFTRAG.txt) ist byteidentisch zur Anlage,
auch im Git-Blob (SHA-256
`dd75998fb3d71ede04399245c99b558b6585e567a98969bd0e9b222002a81d1b`).
[Plan](2026-10-27_PLAN.md), [Native-Nachtrag vor Umsetzung](2026-10-27_NATIVE_SHUTDOWN_PLAN.md),
[Zwischenstand](2026-10-27_SOLL_IST.md) und
[frühere Abweichungen](2026-10-27_ABWEICHUNGEN.md) bleiben als zeitlich eingeordnete
Akten erhalten; dieser Abschluss schreibt sie nicht rückwirkend um.

Implementierungscommits:

- `63fe561bfa7e71cbbfc1499a3d9b2960ba9d794c`: Einzeldistribution, Produktimage,
  Schema 3, Nativeidentität, Release-/Redistributiongates und Regressionen.
- `46b1d24090176ba1a0241ea018f89d18002ffbae`: technisch notwendiger Native-Shutdown-Fix.
- `c40d1c2e399632e473891b41c67e5b8ae3c34aac`: deterministischer Patch auf wiederverwendeten
  Windows-Checkouts mit LF-/CRLF-Quellen.
- `4ad069de0323168cdcd96a0b61d178bad5ee6dec`: vollständige bekannte Dependency-Hinweise
  aus den tatsächlichen Buildquellen, strengere Plattform-/Manifestgates.
- `ed58ac0e6c70dedbffc29f84b30c0f6ae5f05779`: CI-Prerequisites für echte Packagingtests.

Die folgenden realen Linux-Produktartefakte sind exakt an `ed58ac0` und dessen Tree
`cd61106354485fe3bab054cb52f55557822d7d91` gebunden. Die abschließende
Dokumentationsrevision und ihre CI werden zusätzlich in der PR-Beschreibung mit
exaktem HEAD/Run verknüpft; frühere Artefakte werden nicht als neue HEAD-Artefakte
umdeklariert. Die operative Buildautorität bleibt [build/BUILD.md](../../../build/BUILD.md).

## Soll/Ist gegen den Auftrag

| Bereich | Umsetzung und Beleg | Ergebnis |
| --- | --- | --- |
| Ein öffentliches Produkt | `setup.py`, Buildidentität und Distributions-/Imageauthority verwenden ausschließlich `voice-stt-server` mit Nativeinput `pro`. `voicestt` bleibt Entwicklung; Free-Nativebuilds sind interne Entwicklerpfade. | PASS |
| Komplette Paketierung | Ein Produktwheel je Plattform im Vertrag; kein öffentlicher sdist. Nativepayload wird eingebettet, eigene Kroko-Metadaten nicht installiert, `.data/platlib` korrekt umgelegt, Kollisionen abgewiesen. Echtes Linuxwheel und synthetische Windows-Paketierung geprüft. | Linux PASS; echtes neues Windowswheel extern blockiert |
| Runtime-/Modellverwaltung | Capability stammt aus installierter Produkt-/Nativeidentität. Konfiguration und Key erzeugen keine Fähigkeit. Community ohne Key; modellbezogene Pro-Auswahl getrennt von Aktivierung; Force-/Key-/Generation-/Native-Guards und gemeinsame Instanz bleiben erhalten. | Unit-/Contract-, Live- und reale Linux-Produkttests PASS |
| Native-Reproduzierbarkeit | Upstream, Toolchain- und Builderpins bleiben erhalten. Ausschließlich der belegte Shutdownfehler erfordert Patch-Set 5 und neue Fingerprints; kein Umbenennen alter Bytes. Revalidierter Cachehit beim Produktimage belegt. | Linux PASS; Windows-Neubuild extern blockiert |
| PR 12/14 | Dateilisten geprüft; Race-Testdatei aus PR 12 ist in der Basis bereits identisch. Kein supervisor/native_status/owner_process/IPC übernommen. Neuer eigener Stop-vor-join-Fix bleibt im bestehenden Singleton. | PASS |
| Candidate | Schema 3 verlangt genau einen `pro`-Produkt-/Imageeintrag, beide CP312-Plattformwheels, komplette per-Wheel-Nativeherkunft und digestgebundenes Staging. Zusätzliche Produkte, Duplikate, alte Schemata und fehlende Plattformidentitäten scheitern. | Regressionen PASS; vollständiger realer RC NOT_RUN |
| Veröffentlichung | Ein PyPI Publisher, ein Produkt pro Registry; Tag → PyPI → Docker Hub → identische GHCR-Promotion → externe Prüfung → Aliase → GitHub Release. Resume, ABSENT/MATCH/CONFLICT/UNKNOWN, Hashprüfung und unveränderliche Remoteidentitäten bleiben geschützt. | Simulationen PASS; reale Publikation/Promotion NOT_RUN |
| Redistribution | Source-/Dependencytexte werden gehasht und gebündelt; eigenständiger source-kontrollierter Status `BLOCKED` wird in Kandidaten übernommen und vor realen Writes geprüft. Technische Qualifikation erteilt keine Rechte. | Öffentliche Freigabe BLOCKED |
| Bestehende HTTP-/WS-Verträge | Keine neuen Endpunkte/Protokollnachrichten; eingefrorene Vektoren unverändert. Echter unveränderter Client-Paartest und installierte Produktendpunkte geprüft. | PASS |
| Dokumentation | README, Installation, Kroko-/Modell-, Build-, Lizenz-, Release- und Testreferenzen konsolidiert. Keine konkurrierende Buildreferenz. Historische Akten erhalten. | PASS |

## Technisch notwendiger Native-Restbedarf

Der erste reale Linuxlauf mit historischem Nativeinput `36b440630c0a9475`
aktivierte das Pro-Modell und transkribierte korrekt, blieb danach aber beim
Prozessende hängen. Nach 653,70 s wurde der Child gezielt beendet und der Lauf
unterbrochen: 1 PASS, 1 FAILED durch erzwungene Beendigung, Rest NOT_RUN.
Dieser Lauf ist kein erfolgreicher Shutdownnachweis.

Im gepinnten `license.h` joint `BanafoLicense` einen Reporter, dessen `call()`
bisher endlos lief. Der eng begrenzte Fix setzt ein atomares Stopflag und stoppt
den vorhandenen Asio-Loop vor dem join. Es gibt keine neue native Status-API,
keinen Supervisor, Ownerprozess, IPC oder Prozessgenerationen. Die bestehenden
Python-Autorisierungs-/Key-/Modellguards werden dadurch nicht zurückgesetzt.
Patch-Set 4 → 5 ist eine bewusst deklarierte Änderung der Nativebytes. Der
Quellhashguard wurde angepasst; der Patch ist für LF/CRLF und idempotente
Wiederanwendung getestet. Der Header im tatsächlichen Linuxbuild entspricht
bytegleich dem finalen Patchoutput:
`e0627637c5e284491c0b1b1f4d0c0a52960fbadd16c04af28af97ec848146465`.

Die neuen Linuxbytes bestanden reguläre Prozessenden und den realen Reloadpfad.
Es gibt im erfolgreichen Lauf weder einen erzwungenen Exit noch einen
Timeout als vermeintlichen Erfolg. Windows mit den neuen Bytes bleibt offen.

## Reale Artefakte und Herkunft

| Artefakt | Verifizierte Identität |
| --- | --- |
| Kroko-Upstream | `8657e655192623b98d7708e742a72987f953d3a2` |
| Native Linux Pro, CP312 | Fingerprint `c705d80c3f34546b`; Patch-Set 5, Linux-Builderrevision 2 |
| Native-Wheel SHA-256 | `349ca3888307b5700df34e093ad139d96f49387c5150cfb7ba87bc2c75646bdc` |
| Produktwheel | `voice_stt_server-2.0.0-cp312-cp312-linux_x86_64.whl`, 39.127.419 Bytes |
| Produktwheel SHA-256 | `7187ceb055b077e087f57d995b9f3642ee848688e0ea4d0dc2504eefda864e77` |
| Produktidentität | Name `voice-stt-server`, Version `2.0.0`, Native `pro`, Commit `ed58ac0`, Tree wie oben, `sourceDirty=false` |
| Paketbesitzer | Genau `voice_stt_server-2.0.0.dist-info`; vollständige RECORD-Hashes und ZIP-CRC geprüft |
| Native-/Lizenznachweise | Nativepayload aus qualifiziertem Input; 26 indizierte Hinweise samt Quellen/SHA-256 geprüft; ONNX-Runtime-LICENSE/ThirdPartyNotices entsprechen den tatsächlichen Dependencybytes |
| Linux-Image, lokal | `sha256:db8bbdc681b390d2c06c9b5ed3f33247bd81ecebe5caa0e682e873c02722c356`; aus demselben Produktwheel, Nativecache `reused=true` |
| Windows Pro, neuer Sollinput | Fingerprint `54b5f488d34ff173`; tatsächliches neues Artefakt fehlt wegen externem Buildblocker |

Die lokale Image-ID ist keine behauptete öffentliche OCI-Manifestidentität.
Es gibt keine Staging-/Registryreferenz, keinen veröffentlichten Kandidaten und
keine erfundenen Windows-Hashes. Paket-/Native-Provenienz und Modellberechtigung
bleiben getrennt. Modelle und Credentials sind nicht im Wheel/Image enthalten.

## Ausgeführte Tests und Grenzen

| Prüfung | Ergebnis | Einordnung |
| --- | --- | --- |
| Vollständige lokale Unit-/Contract-/Guard-/Release-/Kompatibilitätssuite | 2326 PASS, 25 SKIP, 1323 Subtests PASS, 949,40 s | Opt-in-/ressourcenabhängige SKIPs sind NOT_RUN; relevante reale Nachweise separat unten |
| Echte Python-Packaging-/Installationssuite | 33 PASS, 1315,66 s | Isolierte Consumer; Nativefixtures ausdrücklich synthetisch, keine Nativequalifikation |
| Reale Linux-Patch-5-Runtime | 4 PASS, 151,87 s | Community ohne Key; Pro mit gültigem Key; eine Final-/Realtimeinstanz; Community→Pro→Force Community→Pro mit regulärem Shutdown |
| Reales installiertes Linux-Produktwheel | 4 PASS, 116,27 s, `pip check` PASS | Unveränderte Testskripte ohne Sourcecheckout; Imports aus site-packages, eindeutiger Produktowner und Commit `ed58ac0` geprüft |
| Frisches Linux-Produktimage | PASS | Vollständige Dependencies, `pip check`, Nativeimport und echte isolierte HTTP-/WebSocket-/Info-/Settings-/OpenAPI-/Refusal-Prüfungen; saubere Quellen und Labels gebunden |
| Live-Lizenzprovider | 3 PASS, 1,52 s | Positiver Modellgrant; ungültiger Key ohne Grant; Force-/Keyentzug widerrufen echten Grant; weitere zwei Smoke-Fälle durch stärkere reale Nativefälle abgedeckt, nicht separat ausgeführt |
| Unveränderter Client-Paartest | 1 PASS, 6,24 s | Client `ca56b5ab58c47bd97bae36335e9d9314b2d35294`, gleiche Vertragsvektoren, echte Loopback-HTTP/WS, keine getrackten Clientänderungen |
| Vorhandene historische Windows-Pro-Runtime | 4 PASS, 109,90 s | Referenz für Python-/Runtimeverhalten, kein Patch-5-Windowsnachweis |
| Neuer Windows-Native-/Produktbuild | extern BLOCKED | Zwei unveränderte Buildversuche: HTTP 503 am gepinnten Ubuntu-Snapshot vor Kompilation; neuer Windows-Wheel-/NOTICE-/Installations-/Nativenachweis NOT_RUN |
| Remote-Promotion/Public Publish | NOT_RUN | Keine Registry-Push-Autorisierung genutzt; Simulationen beweisen Reihenfolge, keine zweiten Builds und Resume-/Konfliktsicherheit |

Die CI wurde erweitert um echte Packagingtests auf Ubuntu und Windows. Der
erste Ubuntu-Packaginglauf deckte fehlendes `wheel` im Host und eine zu flache
Git-Historie für historische Regressionen auf. `ed58ac0` ergänzt diese
Voraussetzungen. Ubuntu-CI auf diesem Code ist PASS; Windows war bei Erstellung
dieser Akte im Packaging-Schritt. Nach der Abschlussdokumentation wird die CI am
exakten finalen PR-HEAD erneut kontrolliert und im PR mit Run-URL nachgewiesen.
Das ersetzt keine fehlende Native-/Windows-/Redistributionsqualifikation.

## Offene Entscheidungen und Release-Gates

1. **Windows-Buildressource:** den unveränderten gepinnten Snapshot wieder verfügbar
   machen; Native `54b5f488d34ff173` tatsächlich erzeugen, neues Produktwheel installieren,
   Notice-/Dependencyinventar und echte Native-/Modell-/Shutdownpfade prüfen.
2. **Redistributionsrechte:** vollständigen Pro-Binary-/Produktvertrag sowie relevante
   Drittanbieter-/Microsoftpflichten anhand finaler Artefakte prüfen. Source-Lizenzen
   und erfolgreiche technische Tests sind keine vollständige Produktfreigabe.
3. **Vollständiger RC und unabhängige Abnahme:** beide Plattformartefakte am gleichen
   freigegebenen Commit/Tree, echte OCI-Stagingmanifestidentität und vollständige
   Qualifikationsberichte zusammenführen. Reale Staging-/Publikationsschritte nur
   nach gesonderter Autorisierung; kanonische Übernahme und Endabnahme bleiben extern.

Der Code wird deshalb als Draft mit klar abgegrenzten Gates übergeben. Der
Registerstatus bleibt `Prüfung offen`; keine automatische Releasefreigabe.
