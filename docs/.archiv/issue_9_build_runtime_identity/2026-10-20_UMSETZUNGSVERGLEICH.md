# Issue #9 A+B: Soll-/Ist-Vergleich

## Ergebnis und gepruefte Quellen

**A+B implementiert; Gesamtqualifikation und unabhaengige Abnahme offen.**
Kein Release, Deployment, Git-Tagging oder automatischer Merge.
Dieser Bericht beschreibt eingereichte Quell-/Kandidatenstaende, keinen
produktiv bereitgestellten Server. Die verbindliche Referenz bleibt
[Issue #9](https://github.com/marcosudau-vps/voice-stt-server/issues/9),
Reviewfassung vom 20.10.2026; keine Issuekommentare.

| Rolle | Exakter Commit |
| --- | --- |
| Zielbranch/Baseline | `e761b97334f263a6c51e84314bf3688599b84169` |
| Separater A-Checkpoint | `7e2bb707461b6c04b8a4990e7d3f5f7384de56a1` |
| Kumulative erste B-Implementierung | `fb509532a8b08fad2e4e5cba140b40d062e67a0b` |
| Beobachtete RC-Startblocker korrigiert | `fe6f0e34017af9dfcbba1040997426acbff798cf` |
| Editable-/Startreihenfolge-/Artefaktrechte korrigiert | `e3aa399033aa13fd249048e50355958179706c80` |
| Letzter Build-/Produktcodecheckpoint, WHEEL-Header korrigiert | `89b4d69b0f3a46aac21057f2ff1c2a7081a41e62` |
| Unveraenderter Client `feat/client-v2` | `b80ed8b81ad92bd02ac32553883443d2b7673bcd` |

Letzter Codecheckpoint: Tree
`8baed16b2d4f81c1fe5e462f4a904a682091ad25`,
Quellzeit `2026-10-20T00:40:26Z`, Dirty `false`.
Nachfolgende reine Dokumentationscommits werden nicht rueckwirkend zu
diesen Artefakt-/Paaridentitaeten erklaert. Jeder spaetere Build ist ein
neuer Qualifikationsstand.

Arbeitsbranch `marcosudau-feat/issue-9-build-runtime-identity`,
ein kumulativer PR gegen `feat/einheitliche-triggerarchitektur-distributed`.
Bereitgestellten isolierten Worktree verwendet; keine Arbeit im
Hauptcheckout, kein Zuruecksetzen des Zielbranches.
[Vorplanung](2026-10-20_PLAN.md),
[historischer A-Bericht](2026-10-20_CHECKPOINT_A.md) und
[separate Abweichungen](2026-10-20_ABWEICHUNGEN.md) bleiben unterscheidbar.

## A: Runtime-/API-Ergebnis

| Soll | Ist / Nachweis |
| --- | --- |
| Dockercommit an Runtime binden | Runtime-`ARG`/`ENV` und OCI-Revision verbunden; echte Linux-Free-/Pro-Images zuletzt auf 89b4d69 gebaut und installierte Identitaet gegen Quelle/Labels/Runtime verglichen |
| Eine Appidentitaet fuer alle Flaechen | Frozen `RuntimeIdentity` vor Service-/DB-Erzeugung; OpenAPI, Info, Settings und bestehende V2-Connectionparameter verwenden dieselben Werte |
| Wirevertrag unveraendert | Keine neue Nachricht/Pflichtfelder; Annahme, Snapshot und Refusals behalten ihre bisherigen Formen |
| Billiger oeffentlicher Infoendpunkt | `/api/v2/info`, `no-store`, bestehende Hubkennung; auch ohne Modellbereitschaft; keine Git-/Docker-/Netzwerk-/Modellabfrage im Handler |
| Paket, Runtime und Image nicht vermischen | Generische Images melden `voicestt`; public Free/Pro melden ihre tatsaechliche besitzende Distribution; Kroko nur aus bestehender leichter Provenienz, nicht Key/Modell/Imagebezeichnung |
| Fehlend vs. ungueltig trennen | Optional fehlend bleibt unknown/null/incomplete; korrupte, widerspruechliche oder explizit ungueltige verwendete Identitaet scheitert redigiert vor HTTP-/Sessionannahme |
| Instanz nicht neu erfinden | `StructuredEventHub.server_instance_id`; stabil je Hub und verschieden fuer neue Hubs auch innerhalb eines Prozesses |

Der eigenstaendige A-Checkpoint ist regressionsbelegt, keine
vollstaendige Eigenabnahme. Die spaetere B-Implementierung aendert die
A-Feldnamen nicht; sie fuellt zusaetzliche Herkunftsfelder aus.
Tatsaechliche Image-HTTP-/WebSocket-Endpunktpruefung, Proxy/TLS und
modellgestuetzter Imagebetrieb bleiben **NOT_RUN/NOT_PROVEN**.
Metadatenprojektion im Container ist kein Ersatz fuer diese Realfaelle.

## B: Ressourcen, Packaging und Fehlerstrategie

`VoiceSTT/_build_identity.json`, Schema 1, enthaelt Original-SemVer,
normalisierte Paketversion, Commit/Tree/Dirty/Quellzeit, Distribution,
gebundene Paketvariante und Herkunft. Strikte Felder/Typen/Schemaversion,
eindeutiges JSON und deterministische Bytes; keine Buildlaufzeit,
Runnerpfade, Run-ID, Credentials oder selbstreferenziellen Gesamthashes.

| Pfad | Ergebnis / Grenze |
| --- | --- |
| Source/editable | VERSION/Buildoverride bleibt Authority; stale generierte Ressource ignoriert; echte editable Installation inklusive PEP-660-/Source-Metadatenalias geprueft |
| Manueller Build ohne Git | Echte Installation mit ehrlicher unvollstaendiger Herkunft; kein fremdes Parent-Git und kein offizieller Kandidaten-PASS |
| Aeltere resourcefreie stabile Pakete | Echte Legacy-/Free-/Pro-Installationen; besitzende Distribution statt beliebiger globaler Metadaten |
| Aeltere normalisierte RCs ohne Original | Klarer Versionsfehler gemaess dokumentierter Policy; kein Rueckraten einer verlorenen SemVer-Schreibweise |
| Neue Legacy-/Free-/Pro-Pakete | Fuenf stabile/alpha/beta/RC/RC-plus-Buildmetadatenformen pro Produkt wirklich gebaut/installiert; volle native Qualifikation separat |
| Wheel und sdist zu Wheel | Ohne Git, unter fremdem Git und mit echtem isoliertem PEP-517-Backend; originale Herkunft bleibt erhalten |
| Overrides | Unset/leer/identisch erlaubt; abweichend, explizit unknown gegen bekannten Commit und ungueltig scheitern |
| Beschaedigt/widerspruechlich | Echte Ressourcen-/METADATA-Mismatches, verschiedene und gleichnamige doppelte installierte Produkte regressionsgesichert |
| Offizieller Kandidat | Vollstaendige saubere Quelle und Ressource zwingend; Wheel/native Variante/Image/Labels/RC-Berichte vergleichen, nicht Werte umschreiben |
| Reproduzierbarkeit | Wiederholte generische Wheelbytes und Ressourcen identisch; ganze sdist-Bytes bereits auf Baseline unterschiedlich; keine neue Tarballgarantie |

Beispiel der expliziten Regel:
`2.0.0-rc.1+Build.5` bleibt Produkt-SemVer,
`2.0.0rc1+build.5` ist die getrennte Python-Metadatendarstellung.
Unterstuetzt sind stabile Versionen, `alpha.N`, `beta.N`, `rc.N` und
PEP-440-repraesentierbare Buildmetadaten. Nicht unterstuetzte Formen
scheitern; das bestehende Docker-Tagformat wird nicht fuer `+` umgebaut.

### F01 bis F04 und zusaetzlich beobachtete Defekte

| Befund | Ursache, Repro und Korrektur |
| --- | --- |
| F01 | Docker-Revisionslabel vorhanden, Runtimevariable fehlte; direkte Guard-/Wiretests und echte Image-Metadatenbindung nach Korrektur |
| F02 | Alter Fallback suchte nur `voicestt`; echte installierte Baselinerepros fuer public Free/Pro, neuer Owner-/Ressourcenpfad und resourcefreier stabiler Fallback |
| F03 | Original-SemVer und normalisiertes RC-METADATA verwechselt; echter installierter Baselinerepro, Ressource bewahrt Original, alte verlorene RC-Schreibweise wird nicht erfunden |
| F04 | Settings schluckte Identitaetsfehler pauschal als unknown; gemeinsame validierte Appidentitaet, Startfehler vor Serviceinitialisierung |
| Editable-Alias | Wirklich installierte CI zeigte Source-egg-info plus editable-dist-info; gleicher verifizierter Alias ist kein zweites Produkt, echte doppelte Installationen bleiben Fehler |
| Native Builderrechte | Root-erzeugtes Wheel fuer Host nicht lesbar; nur nicht geheimes gespeichertes Wheel auf 0644, unveraenderter Hash/Store-/Lockvertrag |
| WHEEL-Header | Echte setuptools-Leerzeile verschob neue Plattformheader in den Body; `pip check` schlug fehl. Parserbasierter ROT/GRUEN-Test und echte installierte Tags, kein Plattform-Skip |

Der Baselinerepro ersetzt in einer isolierten echten Packagingkopie nur
den Resolver durch den exakten Gitblob von e761b973. Er ist kein Beleg,
dass eine historische produktive Instanz geaendert oder neu getestet wurde.

## Ausgefuehrte Regressionen und ihre exakten Grenzen

CPython 3.12; lokal Windows, zusaetzlich vorhandene Hosted-Linux-/Windows-CI.
Die angegebenen Skips sind nicht bestanden; optionale Modell-/externe
Planoriginalpruefungen und der POSIX-Rechtetest auf Windows bleiben getrennt.

| Stand / Pruefung | Tatsaechliches Ergebnis |
| --- | --- |
| Exakte Baseline, `python -m pytest -q tests/unit --tb=short` | 1982 passed, 14 skipped, 1296 Subtests; 827.91 s |
| Exakter A-Checkout, gleiche volle Suite | 2000 passed, 14 skipped, 1296 Subtests; 843.58 s |
| Exakter B-Checkout fb50953, gleiche volle Suite | 2105 passed, 14 skipped, 1302 Subtests; 826.86 s |
| B echte Packagingmatrix unter Windows | 42 passed; 1186.05 s |
| Echte Packagingmatrix auf 89b4d69 im Linux-RC | 43 passed; 305.50 s, einschliesslich echter editable Installation |
| Nachkorrektur echte editable-/Duplikatinstallationen | 3 passed; 82.32 s |
| Nachkorrektur installierte native-Fixture-Tags | 2 passed; 60.50 s; synthetisch, kein nativer Importbeleg |
| Betroffene A-HTTP-/Wire- und B-Gateregressionen nach Startreihenfolgekorrektur | 292 passed, 189 Subtests; 141.45 s |
| Direkte Build-/RC-/Headerkorrekturtests | 147 passed, 171 Subtests; 5.74 s |
| CI auf 89b4d69, Ubuntu 24.04 | 2110 passed, 14 skipped, 1302 Subtests; 374.91 s |
| CI auf 89b4d69, Windows | 2109 passed, 15 skipped, 1302 Subtests; 671.81 s |
| Bestehende unveraenderte Clientregressionen | 296 Tests bestanden; 40.858 s |
| Neuer echter Loopback-Paartest auf 89b4d69 | 1 passed, 10 Dependency-Deprecationwarnings; 4.50 s |

[Erfolgreiche letzte gewoehnliche CI](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39349035037)
belegt ausserdem auf beiden Plattformen wirklichen isolierten
Wheel-/sdist-Build, `twine check`, frische vollstaendige generische
Wheelinstallation, zweimal `pip check`, Import/Version, Console-Scripts
und Paketassets. Das ist kein Beleg fuer eingebettete native public
Free-/Pro-Distributionen.

Packagingbefehl:
`python -m pytest -q tests/packaging/test_identity_installation.py`.
Die Matrix erzeugt eigene saubere Git-Testquellen aus den Produktdateien;
deren Ressourcen enthalten ihren eigenen Fixturecommit. Sie werden nicht
als Ressource des tatsaechlichen Servercheckpoints ausgegeben.
Consumerinstallationen hier sind `--no-deps` plus packaging.
Der gesonderte echte Kandidatenartefaktbeleg unten bindet dagegen 89b4d69.

Die anfangs rote lokale Packagingmatrix hatte eine unvollstaendige
Fixture-`.gitignore`: Pythonbytecode machte die Quelle korrekt dirty.
Nur die Fixture wurde korrigiert, der Dirty-Guard nicht abgeschwaecht.
Rote fruehere CI-/RC-Runs sind in der Abweichungsdatei erhalten.

## Echte Artefaktidentitaeten

Sauberer detached Checkout von 89b4d69, zweimal
`python -m build --wheel --sdist --no-isolation --outdir <extern>`,
jeweils gleicher quellabgeleiteter `SOURCE_DATE_EPOCH`.
Beide Wheels sind bytegleich; beide sdists tragen dieselbe exakte
Identitaetsressource. Der Quellbaum blieb sauber.
Verwendete lokale Toolchain: Python 3.12.10, build 1.6.0,
setuptools 83.0.0, wheel 0.48.0, packaging 26.2, pip 25.0.1.

| Artefakt | Bytes | SHA-256 |
| --- | --- | --- |
| `voicestt-2.0.0-py3-none-any.whl`, beide Builds | 30096912 | `c801b6a8ed3559a507fc71bdd92dede5364b04697ddf7e7c2320942373009a6c` |
| `voicestt-2.0.0.tar.gz`, erster Build | 29881065 | `9057b5be625267ef46c48f5c4438899ac0bcbb9b3920a233fa2f7f22ef994451` |
| sdist Wiederholung | 29881032 | `e1de812276965aee8ca1a04185b43b152fb561710b395fbafd316c7a598957d0` |

Frischer Consumer, wirkliche Wheelinstallation ausserhalb des Checkouts:
Distribution `voicestt`, Paket/Produkt `2.0.0`, Commit/Tree/Datum wie oben,
Dirty false, Herkunft git. Ohne installierte native Runtime korrekt
`runtime.krokoVariant=null`, `identityStatus=incomplete`; kein
Image-/Native-PASS aus dieser Metadateninstallation.

## Gezielter RC-Pfad und verbleibende Pflichtfaelle

Die vorhandenen Linux-/Windows-Jobs wurden erweitert, keine schwere neue
Matrix fuer jeden PR. Fresh-install/native/HTTP-Pruefungen und die
hashgebundenen Plattformberichte werden vor bestehender RC-Abnahme gegen
vier konkrete Wheelbytes und deren Krokoherkunft geprueft.
`release_tooling/rc_manifest.py`, `release_tooling/pipeline.py`,
`release-publish.yml`, Publikations-/Promotion-/Resumevertraege bleiben
unveraendert.

Der
[RC auf e3aa399](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39346559296)
belegt 43 echte Linux-Packagingfaelle (251.62 s), beide echten
Linux-Kroko-Wheels, beide generischen Images einschliesslich
Quelle/Paket/Label/Runtimevergleich und beide public Linux-Produktwheels.
Sein nachfolgender vollstaendiger Installationsgate scheiterte am
beschriebenen WHEEL-Headerdefekt, also **kein erfolgreicher nativer
Installations-/HTTPgate** dieses Runs.

Der erneute
[RC auf 89b4d69](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39349037554)
ist der gesonderte Nachweis nach dieser Korrektur:
**Linux-Job erfolgreich, Windows-Job fehlgeschlagen, Gesamtworkflow FAIL.**
Linux baute beide Varianten, bestand beide frischen vollstaendigen
public Wheelinstallationen, `pip check`, native Imports, HTTP-Info/
Settings/OpenAPI, Cache-/Hub-/Readiness- und WebSocket-Refusalchecks.
Beide melden complete und genau die oben genannte Quelle, ihren
tatsaechlichen public Paketnamen und die richtige native Runtime.

Erreichbarer Linux-Beleg: Workflowartefakt `candidate-linux`,
ID `12233217981`, 76759279 Bytes,
Archivdigest
`sha256:a2e32370347740421fb69c1346eca88486261aefa022c45041668dd38cb4b23a`.
Enthaelt beide public Wheels, Distributions-/Build-/Stagingmanifeste,
Packagingevidenz und `identity-qualification-linux.json`.
Bestehende kurze Retention: Ablauf `2026-10-21T01:05:16Z`;
die verlinkten Runlogs belegen die ausgefuehrten Schritte zusaetzlich.
Artefakt wurde separat heruntergeladen und seine Wheel-/Quellbindungen
statisch nachgeprueft, nicht auf Windows als Linuxruntime importiert.

| Artefakt auf 89b4d69 | SHA-256 / Digest |
| --- | --- |
| `voice_stt_server-2.0.0-cp312-cp312-linux_x86_64.whl` | `bb516fde21d4461a86ca74d95492e1dfaff0437c58f78f1efc76b0b3e4534b0e` |
| `voice_stt_server_pro-2.0.0-cp312-cp312-linux_x86_64.whl` | `17424a120e610deb14f6ea07be72f82e36e9954c2dac04b4fb98f5cae11ca98f` |
| Eingebettetes Free-Kroko, Fingerprint `1b2d237c4ab12480` | `266fed2ebd1d54106a956e91203a4ad52bcf8252726085108f111581b2ee8645` |
| Eingebettetes Pro-Kroko, Fingerprint `9e5f8ebbd9821e03` | `7d0e8d4353fe841b708d5442cb86ddf1c5e6b493b9c2f073387a7e4dd9c6da53` |
| Privates generisches Free-Stagingimage | `sha256:9b431fffbe2e169e9605ee8d49638c392600950495e7b7d747f3dbcd2f1c60a0` |
| Privates generisches Pro-Stagingimage | `sha256:558e95ec5c16ea35ec10bfcc742459125b954ab13cabeef26aa2bbf97d58152f` |

Staging blieb beim bestehenden privaten Kandidatenmechanismus, ohne
oeffentliche Promotion oder Bereitstellung. Beide generischen Images
installieren weiterhin `voicestt`, nicht die public Distributionen.
Ihre echte Container-Metadatenpruefung ist vom erfolgreichen HTTP-/
WebSocket-Refusalcheck der installierten public Linuxwheels zu unterscheiden.

Windows scheiterte erneut am benoetigten Linux-Container-Build
(`unknown flag: --platform`, vorhandene Engine Windows/AMD64).
Windows-native Installationsgates sind **NOT_RUN**, ihre Qualifikation
**NOT_PROVEN**. Die nachgelagerte gemeinsame Assembly und Vier-Wheel-
Report-/RC-Abnahme wurde korrekt nicht ausgefuehrt. Keine pauschale
gruene RC-Zusammenfassung aus dem erfolgreichen Linuxjob.

Unabhaengig davon fehlen weiterhin: geeigneter Windows-Linux-Containerhost
fuer den bestehenden Crossbuilder; echte Windows-native Free-/Pro-
Installation und integrierte Vier-Wheel-Berichts-/RC-Abnahme;
echte Image-HTTP-/WebSocket- und Proxy-/Modellqualifikation.
Keine synthetische Pruefung ersetzt diese Faelle. Gesamt-RC-/Image-
und native Byte-Reproduzierbarkeitsqualifikation ist damit **NOT_PROVEN**.

## Unveraenderter Client V2 und Gesamtintegration

K-01 bis K-04 sowie tatsaechlicher Transport, Settings, Media, Logs und
Controls wurden gegen den Serververtrag geprueft. Gitblobs der gemeinsamen
Vektoren sind bytegleich; unterschiedliche Checkout-Zeilenenden wurden
nicht als Protokollaenderung behandelt.

Der neue opt-in Test
`tests/compatibility/test_client_v2_identity.py` verwendet den unveraenderten
Clientproduktstand in einer isolierten Umgebung:

```powershell
$env:VOICESTT_CLIENT_V2_ROOT = "<isolierter unveraenderter Clientcheckout>"
$env:VOICESTT_CLIENT_V2_COMMIT = "b80ed8b81ad92bd02ac32553883443d2b7673bcd"
python -m pytest -q tests\compatibility\test_client_v2_identity.py
```

Echter temporaerer Loopback-HTTP-/WebSocket-Server, echter Clienttransport,
Settingsbootstrap, Audio-Codec/Frames, Controls/Trigger, zuverlaessige
Logs, Reconnect und Refusaldecoding. Annahme, Snapshot, Refusals,
Settings und Info stimmen in Version/Commit ueberein. Nur physischer
Capture sowie serverseitiger Recorder/ASR/Scheduler sind Fixtures.
Clientdateien, historische Pins und bestehender Client-Testserver wurden
nicht veraendert. Kein GUI-/Geraete-/Realmodell-/Proxy-/VPSbeleg.

## Dauerhafte Dokumentation und Abnahmeentscheidung

Buildauthority: [build/BUILD.md](../../../build/BUILD.md).
Aktuelle Vertrage/Bedienung:
[HTTP/Info](../../client-development/06-http-api-und-authentifizierung.md),
[Konfiguration](../../configuration.md),
[FastAPI](../../fastapi-server.md),
[Tests](../../testing.md),
[Releasegrenzen](../../release-process.md).
Kein zweiter VPS-/Compose-/Buildpfad als neue Wahrheitsquelle.

Generierte Logs, Ressourcenberichte, sdists, Wheels, Modelle und
Laufzeitdaten liegen ausserhalb getrackter Dateien. Relevante lokale
Belege: `baseline-exact-tests.log`, `checkpoint-a-full-tests.log`,
`checkpoint-b-full-tests.log`, `checkpoint-b-packaging-tests.log`,
`ordinary-ci-qualified.log`, `packaging-final-client-pair.log`,
`packaging-final-artifacts/artifact-identity.json`.
Erreichbare Remote-Runs sind oben direkt verlinkt.

**Registerstatus: Pruefung offen.** Keine Behauptung eines vollstaendigen
Issueabschlusses bei offenen A-/B-Pflichtnachweisen. Ein unabhaengiger
PR-Review und die fehlenden Realqualifikationen muessen einer gesonderten
Merge-/Bereitstellungsentscheidung vorausgehen.
