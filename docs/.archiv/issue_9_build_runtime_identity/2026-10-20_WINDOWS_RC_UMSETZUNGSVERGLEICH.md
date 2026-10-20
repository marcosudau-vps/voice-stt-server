# Issue #9: Windows-RC-Nachtrag, Soll-/Ist-Vergleich

## Ergebnis und exakter Stand

**V1-CI-Muster gezielt auf V2 uebertragen; reale Windowsqualifikation
weiterhin NOT_PROVEN.** Der falsche Buildhost ist korrigiert. Der echte
Linux-Cross-Build deckt jetzt einen unabhaengigen, bestehenden
Microsoft-Manifestpin-Konflikt auf. Keine Pins, Fingerprints oder
Integritaetspruefungen dafuer abgeschwaecht.

Veroeffentlichter Implementierungscommit:
`c0e552e9837651f8fce9ea5518401349e19371f2`,
Tree `844d213db56043610e9677170dd34b6afab62092`,
Quellzeit `2026-10-20T01:23:39Z`, Dirty false.
Ausgangscommit `354567a08993226f996a533026c4f8a6173e91ad`.
Nachfolgende Dokumentationscommits sind keine rueckwirkenden
Artefakt-/Paaridentitaeten.

Die [Nachtragsplanung](2026-10-20_WINDOWS_RC_PLAN.md) wurde vor Umsetzung
im bestehenden Aktionsordner registriert. Die frueheren A-/B-Berichte
bleiben historisch unveraendert; dieser Nachtrag korrigiert insbesondere
die dortige Einordnung eines benoetigten Windows-Docker-Buildhosts.
Materielle Grenzen stehen getrennt in den
[Windows-RC-Abweichungen](2026-10-20_WINDOWS_RC_ABWEICHUNGEN.md).

## V1-Referenz und technische Uebertragbarkeit

[V1.0.0](https://github.com/marcosudau-vps/voice-stt-server/releases/tag/v1.0.0)
ist ein annotierter Tag auf `3df318635aef00a05417f74bce3f5d21b746eb59`.
Der gesondert referenzierte
[erfolgreiche V1-Validierungsrun 36253196730](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/36253196730)
lief auf `1ca4d32a5736e1e0a599ad5fe1417ec96fdf189b`; diese beiden
Gitidentitaeten werden nicht gleichgesetzt.

Aus Runstatus, Schritten und tatsaechlichen Runnerlabels:

| V1-Teil | Host | Ergebnis |
| --- | --- | --- |
| Kroko Free/Pro fuer win_amd64 | ubuntu-24.04 | beide erfolgreich |
| Produktwheels Free/Pro fuer win_amd64 | ubuntu-24.04 | beide erfolgreich |
| Windows clean install Free/Pro | windows-latest | beide erfolgreich |
| Entsprechende Linux-Build-/Installationsjobs | ubuntu-24.04 | erfolgreich |

Gezielt gelesen:
[V1-Workflow](https://github.com/marcosudau-vps/voice-stt-server/blob/v1.0.0/.github/workflows/release-candidate.yml),
[V1-Crossbuild](https://github.com/marcosudau-vps/voice-stt-server/blob/v1.0.0/tools/v1_kroko_release.py)
und
[V1-Wheelpaketierung](https://github.com/marcosudau-vps/voice-stt-server/blob/v1.0.0/tools/v1_product_wheel.py).
Uebernommen wird nur das Build-/Installationsmuster, kein V1-Skript,
kein historischer V1-Pin und kein V1-Publikationsmechanismus.

## Ursache und gewaehlte V2-Umsetzung

Der vorherige V2-Job rief `--platform windows` direkt auf windows-latest
auf; der Installer waehlte daraufhin den Windows-Hostpfad mit Docker-
Linux-Containeranforderung. Die dort verfuegbare Windows/AMD64-Engine
war dafuer ungeeignet. Windows als **Ziel** wurde mit Windows als
**Buildhost** verwechselt; der erfolgreiche V1-Pfad vermeidet genau das.

| Bereich | Implementierung / unveraenderte Invariante |
| --- | --- |
| build-windows | Ubuntu 24.04 erzeugt beide fertigen Windows-Zielwheels; eigene variantengetrennte Caches nach bestehendem Ziel-Fingerprint |
| resolve_windows_kroko | Linux AMD64/CPython 3.12 voraussetzen, aktuelle prepare_checkout/prepare_windows_checkout wiederverwenden; gepatchtes V2-Dockerfile.windows und in_windows_container.sh ausfuehren |
| Native Inputs | Bestehender Compilercontainer, Quellen, Patches, explizite BUILD_VARIANT und gepinnte Retaggingtools unveraendert; kein neuer Hostcompiler |
| Ausgabe | Privates temporaeres /out, Quellmount read-only; UID/GID nach Containerlauf zuruecksetzen; genau ein Wheel verlangen, in gepinntem Container retaggen und echten ArtifactStore verwenden |
| Produkt | Bestehendes build_distribution und validate_distribution; keine neue Windows-Paketierungsautoritaet |
| Transfer | Neues runinternes candidate-windows-build mit fertigen Produktwheels/Distributionsmanifesten; SHA-/Quell-/Variantenpruefung vor Upload und erneut nach Download |
| candidate-windows | Benoetigt build-windows; nur CPython 3.12 x64, Download, frische native Free-/Pro-Installationen, pip check und vorhandene HTTP-/Identitaetsgates; kein Docker/erneuter Build |
| Assembly | Weiterhin candidate-linux und candidate-windows erforderlich; bestehende Vier-Wheel-/Report-/RC-Pruefungen unveraendert |

Windows-Free-Fingerprint bleibt `28594e6d201fc4a7`,
Windows-Pro `08cb569da5feda2e`; Compilerautoritaet
`63224eaaaa84424e`. Hostunabhaengige Berechnung ueber den vorhandenen
Fingerprintrechner ist gegen den bisherigen Windows-Installer geprueft.
`VoiceSTT/install_kroko.py`, `VoiceSTT/kroko/buildinputs.py`,
`VoiceSTT/kroko/fingerprint.py`, Runtime-/API-Produktcode,
`release_tooling/` und `release-publish.yml` sind in diesem Nachtrag
unveraendert. Bestehende Patch-/Builder-/Toolchain-Digestguards bestehen.

Die unnoetige Upstream-NSIS-/Shell-Temp-Cleanup-Orchestrierung wird nicht
importiert. Kompilation und Retagging verwenden weiterhin dieselben
gepinnten V2-Containerinputs; die Fingerprints werden nicht fuer eine
andere Toolchain wiederverwendet.

## Tatsaechlich ausgefuehrte Pruefungen

Lokaler betroffener Regressionslauf:

```text
python -m pytest -q tests/unit/test_release_candidate.py tests/unit/test_release_workflows.py tests/unit/test_kroko_fingerprint.py tests/unit/test_install_kroko_cpu.py tests/unit/test_kroko_artifact_store.py tests/unit/test_build_distribution.py tests/unit/test_qualify_build_identity.py --tb=short
```

**307 passed, 1 skipped, 280 Subtests; 24.57 s.** Der Windows-POSIX-Skip
ist kein PASS. Neue Tests pruefen beide alten Fingerprintdokumente,
echten Store-/SHA-Reuse, korrupte Cachebytes, falsche native Plattform/
Variante, fehlende Ausgabe, sichtbaren Compilefehler trotz Cleanup und
die Job-/Artefakt-/Rechte-/No-Docker-on-Windows-Vertraege.
Native Unitwheels sind Fixtures, keine echten Windows-Imports.

[Gewoehnliche CI auf c0e552e](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39353187831):
**Beide Plattformjobs erfolgreich**, einschliesslich echter generischer
Paketbuilds/-installationen und pip check.
Ubuntu: **2120 passed, 14 skipped, 1 Warning, 1322 Subtests; 382.96 s**.
Windows: **2119 passed, 15 skipped, 1 Warning, 1322 Subtests; 637.28 s**.
Das ist kein Beleg fuer native Windows-Free-/Pro-Produktinstallationen
oder eine gemeinsame gruene RC-Abnahme.

Ein neuer technischer Client-Paartest des exakten c0e552e-Checkouts gegen
den unveraenderten Client
`b80ed8b81ad92bd02ac32553883443d2b7673bcd` bestand:
**1 passed, 10 Dependencywarnings; 5.84 s**. Physischer Capture,
ASR/Recorder/Scheduler bleiben explizite Fixtures wie zuvor.
Clientproduktcode, historische Pins/Belege und Testserver unveraendert.
Der erste zusaetzliche lokale Aufruf endete mit MemoryError; der
saubere immutable Checkout bestand ohne Codeaenderung. Keine gesicherte
Ursachenzuschreibung und keine historische Gruenwertung dieses Fehlers.

## Echter neuer Candidate und neuer Blocker

[RC 39353183125](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39353183125):
**Gesamtworkflow FAIL.**

| Job / Gate | Tatsaechliches Ergebnis |
| --- | --- |
| Build Linux candidate | PASS; 43 echte Packagingfaelle in 203.53 s; beide Images/public Wheels und beide vollstaendigen nativen Installationen/HTTP-/Refusalchecks erfolgreich |
| Cross-build Windows candidate on Linux | FAIL im gepinnten Containeraufbau, vor nativer Kompilation; CMake-/xwin-Downloads geprueft, danach Channel-Manifestkonflikt |
| Windows-Wheel-Transfer/native Installation | NOT_RUN; kein Windows-Wheel/Hash oder erfolgreicher nativer Import erzeugt |
| Gemeinsame Assembly/Vier-Wheel-/RC-Abnahme | NOT_RUN; korrekte Abhaengigkeitssperre |

Windows wird nicht nochmals zum ungeeigneten Docker-Buildhost gemacht.
Die neue konkrete Ursache und eine rein lesend gefundene bytegenaue
historische Manifestkopie sind in der Abweichungsdatei dokumentiert.
Kein Pinupdate, keine neue Bezugsquelle im Builder und kein Fallback.
Weitere native/ABI-Pruefungen koennen erst nach diesem Guard stattfinden.

Erfolgreicher Linuxbeleg: `candidate-linux`, ID `12234368396`,
76759280 Bytes,
Digest `sha256:11ad2c0f224d6c43d484c75cad36412cbdecd4ffa7200315fc7bb56311d8242c`,
bestehende Retention bis `2026-10-21T01:35:12Z`.
Download separat gegen den sauberen c0e552e-Checkout statisch verifiziert;
die echten nativen Imports stammen vom Linuxjob, nicht von Windows.

| Linuxartefakt | SHA-256 / Digest |
| --- | --- |
| voice_stt_server-2.0.0-cp312-cp312-linux_x86_64.whl | `fd5b47f7be84f773d12f45c233e5f84f78d1cd2974a9e5915d682ebc6b282764` |
| voice_stt_server_pro-2.0.0-cp312-cp312-linux_x86_64.whl | `1250c47a8d6d8656960a269e8eb12ed4b3a2f077756ffb4ab2977e089ddec26c` |
| Native Free, Fingerprint 1b2d237c4ab12480 | `266fed2ebd1d54106a956e91203a4ad52bcf8252726085108f111581b2ee8645` |
| Native Pro, Fingerprint 9e5f8ebbd9821e03 | `7d0e8d4353fe841b708d5442cb86ddf1c5e6b493b9c2f073387a7e4dd9c6da53` |
| Privates Free-Stagingimage | `sha256:e6618fa9af15c6271b90eeadf5886f5cc2b6dddbc2a2de28fce6136863719ad9` |
| Privates Pro-Stagingimage | `sha256:455cb89061652ca8349ab66062be6a861fa962ac670d79053694950ec575aaec` |

Beide installierten Linuxprodukte melden complete, Commit/Tree/Datum wie
oben, richtige public Distribution und richtige native Variante.
Native Linuxbytes wurden unveraendert aus verifizierten Caches
wiederverwendet; neue Produktwheels haben die neue Serverquellidentitaet.

## Planabgleich und Entscheidung

TASK-001 bis TASK-006 sind umgesetzt und mit den angegebenen Grenzen
geprueft; dieser Bericht und die Abweichungsdatei liefern TASK-007.
Die echte native Windows-/Vier-Wheel-Erfolgsvoraussetzung von TEST-004
ist **nicht** erfuellt. Ein geeigneter Host allein beweist keine
Verfuegbarkeit aller gepinnten Inputs. Keine Qualifikation synthetischer
Wheels anstelle des fehlenden Windowsprodukts.

Dauerhafte Buildauthority: [build/BUILD.md](../../../build/BUILD.md).
Keine Release-Manifest-, Publikations-, Promotions- oder Resumeaenderung.
Private RC-Stagingimages wurden wie im bisherigen Workflow geschrieben;
kein oeffentlicher Release, kein Deployment, kein Git-Tagging oder Merge.
Produktive Container, gemeinsamer Dockerdaemon und bestehender
Client-Testserver blieben unberuehrt.

Register und bestehender kumulativer PR #10 bleiben **Pruefung offen**.
Die uebrigen im historischen A+B-Bericht genannten Realmodell-/Image-
Endpunkt-/Proxy-/Reproduzierbarkeitsgrenzen sind durch diesen Fix nicht
aufgehoben. Keine eigenstaendige Gesamtfreigabe.
