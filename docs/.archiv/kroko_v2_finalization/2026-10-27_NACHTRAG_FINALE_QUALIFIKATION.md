# Nachtrag: finale Linux-/Windows-Produktqualifikation

2026-10-27, nach der ersten Abschlussakte. **Produktqualifikation beider
Plattformen: PASS. Gesamtfreigabe: BLOCKED**, weil ein vollständiger realer RC
mit verifizierter OCI-Stagingidentität und die öffentliche Redistributionsfreigabe
weiterhin fehlen. Kein behaupteter veröffentlichungsfähiger RC.

Dieser neue Nachtrag aktualisiert die zeitlich früheren Aussagen zu Windows
im [Abschlussvergleich](2026-10-27_ABSCHLUSS_SOLL_IST.md) und in den
[Abweichungen](2026-10-27_ABSCHLUSS_ABWEICHUNGEN.md). Die ursprünglichen
Fehlerbefunde und ihre Einordnung bleiben erhalten. Es gab keine weitere
Änderung an Produktcode, Nativepatches, Builderpins oder Vertragsvektoren.

## Windowsblocker tatsächlich überwunden

Eine abschließende Ressourcenprüfung lieferte wieder HTTP 200 für den unveränderten
Ubuntu-Snapshot. Der erneute unveränderte Build lief danach vollständig durch:
gepinntes Builderimage, SDK/CRT, Python-Target, OpenSSL, native Kompilation,
Python-Erweiterung und Wheel-Reparatur. Es wurde weder ein anderer Mirror noch
eine ältere Runtime verwendet. Native-Patch-Set 5, Windows-Builderrevision 5
und Pro-Fähigkeit sind in der tatsächlichen Artefaktherkunft erfasst.

## Quellengebundene reale Artefakte

Alle Produktartefakte dieser Tabelle gehören exakt zu Commit
`219081272f3af46b1bb009f4394c80a4d39eb5eb`, Tree
`d26845ede41ed96dc537fd8b2130a808982b3a3c`, `sourceDirty=false`,
`sourceDate=2026-10-27T04:04:07Z`. Upstream bleibt
`8657e655192623b98d7708e742a72987f953d3a2`.

| Artefakt | Verifizierte Identität |
| --- | --- |
| Linux-Native CP312 Pro | Fingerprint `c705d80c3f34546b`; SHA-256 `349ca3888307b5700df34e093ad139d96f49387c5150cfb7ba87bc2c75646bdc` |
| Windows-Native CP312 Pro | Fingerprint `54b5f488d34ff173`; SHA-256 `0db928d3579c0fe9a47fd71fd48896af3b7ba09ea9189cb15ed6d87313616dd3`; 15.916.538 Bytes |
| Linuxprodukt | `voice_stt_server-2.0.0-cp312-cp312-linux_x86_64.whl`; SHA-256 `fd32e5e6567ec9957e09e64cf7183742c221e436b7adb097c474c4495c8e09dd`; 39.127.419 Bytes |
| Windowsprodukt | `voice_stt_server-2.0.0-cp312-cp312-win_amd64.whl`; SHA-256 `b1dce0876842f73089147e124f7472a61849168b63f8537863eee98f174386de`; 46.287.474 Bytes |
| Linuxproduktimage, lokal | `sha256:6f20e7a8718a8ebab612f9389a16de479682907975114bf76f859109d4c0cae0`; aus demselben Linuxproduktwheel, Nativecache erneut verifiziert, `reused=true` |

Das Linuxwheel unterscheidet sich vom zuvor real getesteten `ed58ac0`-Wheel
ausschließlich in `VoiceSTT/_build_identity.json` und RECORD; alle Native- und
Runtimecodebytes sind identisch. Zusätzlich wurde das neue installierte
Linuxproduktimage nochmals tatsächlich mit Modellen getestet.

Diese Nachtragsdatei entsteht nach den genannten Artefakten. Ihre abschließende
Dokumentationsrevision und gegebenenfalls erneut gebaute Produktidentitäten
werden mit exaktem HEAD, Tree und CI-Run in
[PR 16](https://github.com/marcosudau-vps/voice-stt-server/pull/16) erfasst.
Die oben genannten Bytes werden niemals als Artefakte eines anderen Commits
umetikettiert. Eine lokale Image-ID ist kein verifizierter Registrydigest.

## Tatsächlich ausgeführte Qualifikation

| Prüfung | Ergebnis und Grenze |
| --- | --- |
| Finale PR-CI für `2190812`, Ubuntu | 2327 PASS, 24 SKIP, 1323 Subtests PASS; Packaging 33 PASS |
| Finale PR-CI für `2190812`, Windows | 2326 PASS, 25 SKIP, 1323 Subtests PASS; Packaging 33 PASS |
| Direkte Push-CI exakt auf `2190812` | Ubuntu und Windows vollständig PASS |
| Neues installiertes Linuxproduktimage | 4 reale Nativefälle PASS in 95,08 s; kein Sourcecheckout, `pip check` PASS |
| Neues Windowsprodukt, frische venv ohne System-Site-Packages | Installation mit vollständigen Produktabhängigkeiten, `pip check`, Nativeimport und installierte HTTP-/WS-/Info-/Settings-/OpenAPI-/Refusal-Identität PASS |
| Neue installierte Windowsruntime | 4 reale Nativefälle PASS in 100,69 s |
| Beide tatsächlichen Produktwheels | Ein Paketbesitzer `voice_stt_server-2.0.0.dist-info`, vollständiger RECORD, ZIP-CRC und 26 gehashte indizierte Notices PASS |

Die vier echten Nativefälle sind Community ohne Key, Pro mit gültigem Key,
eine gemeinsame Final-/Realtimeinstanz sowie Community→Pro→Force Community→Pro.
Alle erfolgreichen Kindprozesse endeten regulär; weder Kill noch Timeout wird
als Erfolg gezählt. Das Linuxdiagnoseimage erhielt lediglich Testwerkzeuge in
einem wegwerfbaren Container. Die frische Windows-Produktinstallation greift
auf keine historische Kroko-Installation und keinen Sourcecheckout zurück.
Modelle, Test-Key und Testaudio blieben außerhalb von Git und Produktartefakten.

CI-Belege: [PR-Lauf 40447674310](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/40447674310),
[direkter HEAD-Lauf 40447669502](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/40447669502).
Die weiteren lokalen Gesamt-, Packaging-, Liveprovider- und unveränderten
Client-Paartests bleiben im vorherigen Abschlussvergleich dokumentiert.

## Tatsächliche Windows-Lizenz-/Dependencyprüfung

Der neue Nativeinput enthält die ursprüngliche Apache-2.0-Lizenz mit SHA-256
`cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`.
Das Produkt bewahrt sie unter `.dist-info/licenses/KROKO-ORIGINAL/LICENSE`
und ergänzt alle 26 indizierten Dependency-/NOTICE-Texte. Der Quellenindex hat
SHA-256 `2150f2f05f163d88530e7c75a75318c18ad875e23ea71d77fcfbef96554ad643`.
Der historische Befund fehlender Windows-Kroko-Lizenztexte trifft auf dieses
konkret erzeugte Produktwheel nicht mehr zu.

Die tatsächlichen PE-Importtabellen wurden gelesen: Python-Erweiterung,
ONNX Runtime, OpenSSL sowie Sherpa-C-/C++-Bibliotheken sind inventarisiert;
Microsoft VC-/UCRT-/Windows- und Python-DLL-Abhängigkeiten sind sichtbar.
Der unveränderte Nativeinput verwendet für ONNX Runtime einen ursprünglichen
und einen von der Wheel-Reparatur gehashten DLL-Namen mit identischen Bytes.
Diese Upstream-Loadernamen wurden erhalten; es gibt keine zweite installierte
Kroko-Pythondistribution oder einen zweiten Paketbesitzer. Eine allgemeine
Native-Payloadbereinigung oder PE-Umschreibung wurde nicht vorgenommen.

Die [Kroko-On-Premise-Dokumentation](https://docs.kroko.ai/on-premise/) trennt
Communitymodelle, kommerzielle/OEM-Modelle sowie modellbezogene Keys; die
[Anbieterseite](https://kroko.ai/) nennt gesonderte Redistribution-/SDK-Lizenzierung.
Daraus folgt keine nachgewiesene Freigabe dieses konkreten Pro-Binaryprodukts.
Vertragsrechte, abschließende Drittanbieterpflichten und Microsoftbedingungen
bleiben separat zu prüfen. Das source-kontrollierte Redistributionsgate bleibt
deshalb unverändert **BLOCKED**.

## Verbleibende Gates

1. Vollständige Pro-Produkt-/Binary-Redistributionsrechte und relevante
   Drittanbieter-/Microsoftpflichten unabhängig freigeben.
2. Danach einen vollständigen exakten Zweiplattform-RC mit real verifizierter
   OCI-Stagingmanifestidentität und vollständigen Qualifikationsberichten
   zusammenführen. Reale Registry-Pushes und Promotion bleiben NOT_RUN;
   es liegt dafür keine gesonderte Autorisierung vor.
3. Unabhängige Endabnahme und spätere kanonische Übernahme. Kein eigenmächtiger
   Merge, Tag, Publish, Registry-Push, Deployment oder Secretwechsel.

Der frühere Windows-Build-/Nativeblocker ist geschlossen. Eine öffentliche
Releasefreigabe oder ein vollständiger realer RC wird weiterhin nicht behauptet.
Die operative Buildreferenz bleibt ausschließlich [build/BUILD.md](../../../build/BUILD.md).
