# PR #16: Korrekturen, Konsistenzpruefung und technische Einreichung

2026-10-27. Korrekturlauf auf dem bestehenden Draft-PR
[#16](https://github.com/marcosudau-vps/voice-stt-server/pull/16).
Keine unabhaengige Root-Abnahme oder Integrations-/Releasefreigabe.
Die bisherigen Original-, Abschluss- und Qualifikationsakten bleiben unveraendert.
Operative Buildautoritaet bleibt ausschliesslich [build/BUILD.md](../../../build/BUILD.md).

## Ausgangsstand und Identitaeten

- Arbeitsbranch ausschliesslich `work/kroko-v2-finalization-20261027`.
- Lokaler und Remote-Ausgangs-HEAD: `bb63fb922594b870905fea5965ca9a23dd563cdb`;
  Tree `8b9dbad702578af30ca7c2e6c8421bbae2770739`; sauberer Checkout.
- PR-Basis remote unveraendert: `30fac0d6a83139d67daac9c71da4e9a3260b0b15`
  auf `feat/v2-unified-kroko`.
- Korrektur-/Produktquellcommit: `a0950fc9d3c62d33b89d3db36a5b1406462880a2`;
  Tree `066c2be008555541bd8e92abb814e7f3865fff1b`; Produkte `sourceDirty=false`.
- Der anschliessende Aktencommit ergaenzt diese Datei und ihren Registerlink
  sowie eine sprachliche Praezisierung des README-Containerabsatzes.
  Seine exakten finalen Commit-/Tree-IDs und die erst danach feststehenden
  CI-Run-URLs werden in der PR-Beschreibung erfasst. Lokal eindeutig aufloesbar
  mit `git log -1 --format='%H %T' -- docs/.archiv/kroko_v2_finalization/2026-10-27_PR16_REVIEW_KORREKTUREN.md`.
  Ein Commit kann seinen eigenen Hash nicht im eigenen Dateiinhalt enthalten.
  Die Produkte unten werden keinem spaeteren Aktencommit zugeschrieben.

## Bisheriges BLOCKED und Trennung der Gates

Die erste Abschlussakte entstand bei fehlendem Patch-5-Windowsartefakt:
HTTP 503 am unveraenderten Ubuntu-Snapshot verhinderte die Kompilation.
Der spaetere [Qualifikationsnachtrag](2026-10-27_NACHTRAG_FINALE_QUALIFIKATION.md)
belegt den erfolgreichen unveraenderten Build und die reale Produktqualifikation
auf beiden Plattformen. Dieser technische Blocker ist geschlossen.

Die verbleibenden Punkte sind verschieden:

1. **Technische Implementierung:** gezielte Gegenpruefung der Produkt-, Runtime-,
   Packaging-, Candidate- und Releasevertraege; Befunde unten.
2. **Fehlender Release-Nachweis:** kein vollstaendiger realer Zweiplattform-RC
   mit registryverifizierter OCI-Stagingmanifestidentitaet. Das ist ein offenes
   technisches Releasekriterium F6/F7, kein nachgewiesener Implementierungsfehler
   und kein Ersatz fuer den erreichten Featureabschluss F2.
3. **Externes Rechtsgate:** Pro-Binary-Redistributionsrechte und abschliessende
   Drittanbieter-/Microsoftpflichten sind nicht unabhaengig freigegeben.
   `build/kroko-redistribution.json` bleibt unveraendert `BLOCKED`.
4. **Abnahme/Organisation:** unabhaengiger Root-Review und ausdrueckliche
   Integrationserlaubnis fehlen. Dieser ausfuehrende Lauf kann sie nicht erteilen.

## Korrekturen und vollstaendige Dateiliste

Keine Aenderung an Runtimecode, Nativepatches, Fingerprints, Toolchainpins,
Packagingalgorithmus, HTTP-/WS-Vertraegen oder funktionaler Release-/Gatelogik.
Die Python-Aenderungen betreffen ausschliesslich Beschreibungen/Docstrings und
die Formulierung einer bestehenden OrderError-Meldung; keine Guardbedingung.
Ein AST-Vergleich gegen bb63fb9 bestaetigte nach Entfernen der Docstrings nur
drei geaenderte Beschreibungstexte (Engine, OrderError und CLI-Hilfe), sonst
identische Syntaxbaeume. Geparstes Workflow-YAML und Dockerinstruktionen
ohne Kommentare sind ebenfalls identisch zum Ausgangsstand.

| Datei | Konkrete Korrektur / Grund |
| --- | --- |
| `README.md` | Ein Produktimage in zwei Registries, eine PyPI-Distribution; reale Plattformqualifikation von RC/Rechten/Abnahme getrennt |
| `RELEASE_NOTES.md` | Noch unveroeffentlichte 2.0.0-Produktbeschreibung und Registryfolge an Einzeldistribution angepasst; historischer Abschnitt weiterhin zeitlich gekennzeichnet |
| `build/BUILD.md` | Windows-Einzelinstallation, zwei Plattformwheels, Schema 3 ohne Produkt-sdist, OCI-Stagingdigest; eingebettetes Wheel statt separater Kroko-Installation; korrekte Tagfolge, Ubuntu-Basis und Packagingauswahl |
| `.github/workflows/release-candidate.yml` | Veraltete Free-/Pro-/Vier-Wheel-Kommentare berichtigt; ausfuehrbares YAML und Berechtigungen unveraendert |
| `.github/workflows/release-publish.yml` | PyPI-Kommentar nennt beide Plattformwheels eines Produkts |
| `Dockerfile` | Kommentar beschreibt das eine bereits vollstaendige Produktwheel; Instruktionen unveraendert |
| `docs/README.md` | Aktuelle Produktuebersicht von zwei Editionen auf ein Produkt korrigiert |
| `docs/transcription-engines.md` | Installationsflaeche und Unterschied zwischen Nativefaehigkeit und modellbezogener Berechtigung berichtigt |
| `docs/client-development/06-http-api-und-authentifizierung.md` | Tatsachlicher Paketowner von Wheel und Image ist `voice-stt-server`; `voicestt` bleibt Entwicklung |
| `docs/stt-model-management.md` | Veraltete Runtime-Konfigurationspraezedenz entfernt: Manager verwendet installierte Identitaet, sonst `unknown` |
| `docs/kroko-onnx.md` | Frueheren Linux-Shutdowntimeout als mit Patch 5 korrigiert eingeordnet; Entwicklerbuildwechsel von Produktedition getrennt |
| `docs/testing.md` | Aktuelle Produktpackagingmatrix und spaetere echte Pro-/Lifecycle-Nachweise verlinkt |
| `release_tooling/engine.py` | Docker-Hub-Schrittbeschreibung nennt ein qualifiziertes Produktimage |
| `release_tooling/rc_manifest.py` | Docstring nennt eine Distribution |
| `release_tooling/adapters.py` | PyPI-/Registry-Docstrings an Einzelprodukt und Resume angepasst |
| `release_tooling/aliases.py` | Kommentar zum bestehenden Aliasgate berichtigt |
| `release_tooling/state.py` | State-Dokumentation und Fehlermeldung nennen Produktartefakte statt Free/Pro-Editionen |
| `tools/release_candidate.py` | CLI-Hilfe nennt ein Produkt, zwei Wheels und ein Image |
| `docs/.archiv/README.md` | Diesen Nachtrag verlinkt; Status bleibt `Pruefung offen` bis unabhaengiger Abnahme |
| Diese Nachtragsdatei | Bewertungsmatrix, echte Ergebnisse, Provenienz und offene Entscheidungen |

Entwickler-Free-/Pro-Nativebuilds, Migrationshinweise auf den alten Paketnamen
und ausdruecklich historische Beschreibungen bleiben kontextgerecht erhalten.
Keine globale Textersetzung. Keine alten Archivakten umgeschrieben.

## Technische Soll-/Ist-Gegenpruefung

| Vertragsbereich | Geprueftes Verhalten / Evidenz | Ergebnis |
| --- | --- | --- |
| Produktidentitaet | `setup.py`, `build_distribution`, `build_production`, installierter Resolver: nur `voice-stt-server`, offizieller Nativeinput `pro`; ein CP312-Wheel je Linux/Windows-Ziel | PASS |
| Paketowner/Payload | Beide realen Wheels neu inspiziert: genau ein Produkt-dist-info, keine installierte Kroko-Distribution, vollstaendiger RECORD, CRC, Original-/26 indizierte Notices. `.data/platlib`-/`purelib`-Relocation und Kollisionsabweisung im Merge gegengeprueft | PASS |
| Nativeinputs/Cache | Upstream `8657e655192623b98d7708e742a72987f953d3a2`, Patch 5, Builderrevisionen unveraendert; historische Nativehashes verifiziert; keine Umbenennung alter Nativebytes | PASS |
| Native-Shutdown | `KrokoRequestLicenseStop()` setzt atomares Stopflag und stoppt bestehenden Asio-Loop vor Join; Reporter prueft Stop nach `run()` und in Schleife. LF/CRLF-/Idempotenz-/Fingerprintguards vorhanden; reale Prozessnachweise separat unten | PASS |
| Modellberechtigung | Installierte Faehigkeit statt Konfiguration/Key; Community ohne Key, Pro-Modellgrant getrennt von Auswahl und Aktivierung; Force/Key/Generation/Singleton/Scheduler-/Nativeguards erhalten | PASS |
| Candidate/Provenienz | Schema 3: genau ein Produkt, beide CP312-Ziele, per-Wheel-Nativeherkunft, eindeutiger Image-/Stagingdigest; alte Schemata, Duplikate, falsche Herkunft und Hashkonflikte werden abgewiesen | PASS (Regressionen; echter RC separat offen) |
| Publikation/Resume | Exakte qualifizierte Bytes ohne zweiten Build; ABSENT/MATCH/CONFLICT/UNKNOWN, fehlende Wheel-Uploads, Registry-Teilfortschritt und Nachverifikation im bestehenden Vertrag | PASS (Simulationen; keine reale Publikation) |
| Redistribution | Sourcegate bleibt BLOCKED; entsprechendes Kandidatengate verhindert REAL-Engine vor Adapter-/Tag-/Publishaufruf. Technische Qualifikation ist keine Rechtefreigabe | PASS fuer Sperrverhalten; externe Rechte BLOCKED |
| HTTP/WS und verworfene Architektur | Runtime-/Wirecode und Vertragsvektoren unveraendert; installierte Endpunkte separat qualifiziert. Kein Supervisor, Ownerprozess oder IPC hinzugefuegt; kein neuer funktionaler Restbedarf aus PR 12/14 festgestellt | PASS |

## Neue Produkte und Fortgeltung historischer Nachweise

Die beiden erhaltenen 2190812-Produktwheels wurden anhand der im historischen
Nachtrag genannten SHA-256-Werte erneut geprueft. Die neuen Produkte haben
dieselbe Dateimenge; ausschliesslich `VoiceSTT/_build_identity.json`,
Produkt-METADATA (README-Paketbeschreibung) und RECORD unterscheiden sich.
Alle Runtime-, Native-, Guard-, Modell-/Schedulercodebytes und Notices sind
bytegleich. Damit bleibt die historische reale Plattformqualifikation fuer
diese unveraenderten Bytes belastbar. Zusaetzliche neue Laeufe unten werden
gesondert den neuen Produktidentitaeten zugeordnet.

| Artefakt auf Quellcommit a0950fc | SHA-256 / Identitaet |
| --- | --- |
| Linuxprodukt `voice_stt_server-2.0.0-cp312-cp312-linux_x86_64.whl` | `08c6f6d15b3a7e3a9633d04c43dd6d8d6b54b1ac00d2f172abeca7e638df6860`, 39.127.575 Bytes |
| Windowsprodukt `voice_stt_server-2.0.0-cp312-cp312-win_amd64.whl` | `7cb216e5878bea58b11bd337c3631b933ab8632a220ce9b3d128b0523ff55e78`, 46.287.631 Bytes |
| Linux-Native | `c705d80c3f34546b`, SHA-256 `349ca3888307b5700df34e093ad139d96f49387c5150cfb7ba87bc2c75646bdc` |
| Windows-Native | `54b5f488d34ff173`, SHA-256 `0db928d3579c0fe9a47fd71fd48896af3b7ba09ea9189cb15ed6d87313616dd3` |
| Noticeindex, beide Produkte | `2150f2f05f163d88530e7c75a75318c18ad875e23ea71d77fcfbef96554ad643` |
| Neues lokales Linuximage | `sha256:62507d2dcccf8ea69bd9de65e96ceb2b23789de83ea5ce548c9370e9fb7c1caf`; keine behauptete Registrymanifestidentitaet |
| Linuxwheel im Imagebuild | `719e3d23e5bd85a3384649c2472206d295d3612e048c13bec73780b9cbd9ac8f`, 39.127.575 Bytes; exakt dieses Wheel wird im Image installiert |

Die neuen lokalen Produktdateien/Pruefskripte liegen ausserhalb des Gitcheckouts
unter `../pr16-review-products/`, `../pr16_review_products.py` und
`../pr16_review_windows.py`. Erzeugte Logs, Binaires, Modelle und Keys sind
nicht Bestandteil dieses Commits.

Der kanonische Imagebuild setzt die ZIP-Zeitstempel auf den Quellcommitzeitpunkt;
der separate Merge-Lauf oben nutzte den festen Defaultzeitpunkt 1980. Daher
haben die zwei Linux-Wheelcontainer verschiedene Gesamthashes. Ein gesonderter
Vergleich bestaetigt identische Dateimengen und ausnahmslos identische
entpackte Dateibytes, inklusive Buildidentitaet und RECORD. Keine Substitution
eines qualifizierten RC-Artefakts wird behauptet: diese lokalen Builds sind
kein RC. Der echte Linuxbuilder bestaetigte `reused=true`; beide Native-
Fingerprintdokumente wurden erneut zum dokumentierten Fingerprint gehasht
und gegen aktuelle Patch-/Upstreampins geprueft.

## Testmatrix des Korrekturlaufs

| Pruefung | Tatsachliches Ergebnis | Umgebung / Grenze |
| --- | --- | --- |
| Gesamtsuite `pytest -q tests/unit tests/compatibility` | 2326 PASS, 25 SKIP, 1323 Subtests PASS, 1094,65 s | Windows AMD64, CPython 3.12.10, bestehende `finalization-test-env`; Start im Korrekturworktree, gezielte Nachpruefungen nach den letzten Textkorrekturen; opt-in SKIPs sind NOT_RUN |
| Packaging `pytest -q tests/packaging` | 33 PASS, 1143,14 s | Echte isolierte Consumerinstallationen; synthetische Nativefixtures qualifizieren keine Nativeinferenz |
| Gezielte Docs-/Release-/State-/Workflow-/Produktregressionen | 178 PASS, 262 Subtests PASS, 2,80 s | Finale Korrekturinhalte; keine Zeitgrenze/Testlogik geaendert |
| Zusaetzliche Nativepatch-/Fingerprint-/Cache-/RC-/Installationsregressionen | 272 PASS, 136 Subtests PASS, 24,28 s | 10 bestehende WebSocket-Deprecationwarnungen; keine Fehler |
| Mirror-Ueberlasttest | 10/10 neue unabhaengige Windows-Testprozesse PASS, 122,01 s gesamt | Unveraenderter Test einschliesslich `elapsed < 0.25`; parallel zu weiteren lokalen Pruefungen |
| Reale neue Produktwheelinspektion | Beide PASS | Vollstaendiger RECORD/CRC, einzelner Owner, 26 Notices, Nativecache/Provenienz, Bytevergleich zu 2190812 |
| `.data/platlib` und `.data/purelib` | 6 gezielte Proben PASS | Je Scheme: korrekte Relocation, Kollision gegen Basispayload und gegen Nativepayload wird abgewiesen |
| Frisches Windowsprodukt mit vollen Abhaengigkeiten | PASS: Installation, `pip check`, Nativeimport, HTTP/WS/Info/Settings/OpenAPI/Refusal | Neue venv ohne System-Site-Packages, ausserhalb Sourcecheckout; a0950fc, Tree wie oben |
| Installierte Windows-Nativefaelle | 4 PASS, 130,70 s | Community ohne Key, Pro, geteilte Instanz, Community/Pro/Force/Pro; alle Kindprozesse endeten regulaer |
| Neues Linuxproduktimage | PASS: Build, Nativecache-Revalidierung, `pip check`, Nativeimport und installierte HTTP-/WS-Identitaet | Lokales Linux/AMD64-Dockerimage; a0950fc, sauberer Quellstand; kein Registry-Push |
| Installierte Linux-Nativefaelle | 4 PASS, 139,74 s, `pip check` PASS | Dieselben unveraenderten vier Tests ohne Sourcecheckout, regulaere Prozessenden; nur Testwerkzeuge in wegwerfbarem Container ergaenzt |
| Gesamte Live-Lizenzsuite | 5 PASS, 40,03 s | Positiver modellbezogener Grant, ungueltiger Key, echte Pro-Inferenz, Grantentzug/Force, Community ohne Key; Windows mit neuer Produktruntime, unveraenderte Tests |
| Unveraenderter Client-Paartest | 1 PASS, 4,46 s | Client `ca56b5ab58c47bd97bae36335e9d9314b2d35294`, sauber getrackt, echte Loopback-HTTP/WS und identische Vertragsvektoren; ASR/Hardware ausdrueckliche Fixtures |
| Finale Ubuntu-/Windows-GitHub-CI | Nach Aktencommit zu kontrollieren; exakte Runs im PR | Verbindliches letztes Kriterium fuer REVIEW_READY; nicht aus historischer CI abgeleitet |

Die vorhandene lokale Testvenv erbt System-Site-Packages. Ihr zusaetzlicher
`pip check` meldete bereits geerbte Konflikte von NumPy 2.5.4 mit `numba` und
`qtpy-led`. Das ist keine saubere Produktinstallation. Keine globalen Pakete
wurden veraendert; Produkt-pip-checks in isolierten Umgebungen und CI sind
separate Nachweise.

## Einordnung des urspruenglichen Windows-CI-Ausreissers

Im [urspruenglichen PR-Lauf](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/40450910645/attempts/1)
scheiterte ausschliesslich die Assertion `elapsed < 0.25` mit
`0.32799999999997453`; kein nachgewiesener Eventverlust. Der Test misst auch
99 synchrone SQLite-Appends. Der Mirror wird ueber `put_nowait` bedient;
der kanonische Append und die Commitnotification erfolgen davor.
Die feste Wallclockgrenze ist daher von Hostlast/Dateisystemtiming abhaengig.
Die nachfolgenden Daten-/Gapassertions liefen im fehlgeschlagenen Versuch
wegen der vorangestellten Assertion nicht; fuer deren PASS werden nur die
erfolgreichen Laeufe herangezogen.

Historisch bestanden zehn getrennte lokale Windowsprozesse und die komplette
CI-Wiederholung. Jetzt bestanden nochmals zehn getrennte Prozesse mit
unveraendertem Test. Befund: **nicht reproduzierter Timing-Ausreisser**,
kein belegter funktionaler Regressionsdefekt. Das schliesst kuenftige
Hosttimingausreisser nicht mathematisch aus. Keine Lockerung, kein Skip,
keine unbegruendete Aenderung am Event-Hub.

## Statusmatrix und Einreichungsentscheidung

| Ebene | Status / Bedingung | Evidenz / offenes Gate |
| --- | --- | --- |
| Implementierung F2 | PASS, finale CI bleibt Pflicht fuer Einreichung | Produkt-/Runtimevertraege oben; keine bekannten kritischen Codefehler |
| Technische Tests / reproduzierbare Qualifikation | PASS | Gesamt-/Packagingsuite und zusaetzliche Regressionen oben; finale saubere CI zusaetzlich |
| Reale native Linuxqualifikation | PASS, historisch und neu | 2190812-Nachtrag; bytegleiche Runtime/Nativepayload; neue vier Realfaelle im a0950fc-Produktimage |
| Reale native Windowsqualifikation | PASS, historisch und neu | 2190812-Nachtrag; neue vier Realfaelle im isolierten a0950fc-Produkt |
| Packaging / Installation | PASS | Exakte a0950fc-Produkte, frische volle Windowsinstallation und neues Linuximage; keine Umdeklaration alter Artefakte |
| CI auf finalem HEAD | Ausstehend vor Push | Nur tatsaechliche finalen Checks erlauben REVIEW_READY |
| Vollstaendiger realer RC mit Stagingidentitaet | NOT_RUN / Release BLOCKED | Kein Registry-Push autorisiert, kein erfundener Digest |
| Redistributierungsfreigabe | BLOCKED | Unabhaengige Rechte-/Drittanbieter-/Microsoftpruefung erforderlich |
| Unabhaengiger Root-Review | NOT_RUN | Ausfuehrender Agent erteilt keinen Root-PASS |
| Kanonische Integration | NOT_RUN | Erst nach ausdruecklicher Freigabe; keine Uebernahme in andere Branches |
| Oeffentliche Veroeffentlichung | BLOCKED / NOT_RUN | RC, Rechte, Abnahme und gesonderte Publikationsfreigabe fehlen |

Nach PASS aller technischen Featurekriterien einschliesslich der finalen
Ubuntu-/Windows-CI kann dieser PR **REVIEW_READY zur unabhaengigen Root-Abnahme**
eingereicht werden. Die tatsaechliche Schlussentscheidung mit finalen
Commit-/Tree-/Run-IDs wird im PR protokolliert. Der Draftstatus bleibt erhalten.
F2 wird dadurch nicht mit Source-Freeze, F6/F7 oder oeffentlicher Freigabe
gleichgesetzt. Keine Integration, Tags, Registry-/Staging-Pushes, Publikation,
Deployments, Secretwechsel oder Aenderungen an uebergeordneten Branches.
