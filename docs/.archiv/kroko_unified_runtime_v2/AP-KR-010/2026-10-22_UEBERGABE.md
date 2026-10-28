# AP-KR-010 – Konkrete Übergabe an AP-KR-020 und AP-KR-030

22.10.2026. Keine Folgeimplementierung in AP-010. Ausgangspunkt der Folge-APs
ist jeweils der dann unabhängig abgenommene Integrationscommit, nicht blind
der heutige HEAD oder der geschützte V2-Zielbranch.

## AP-KR-020 – Runtime- und Lizenzintegration

**Eingänge:** [Entscheidung/Statusvertrag](2026-10-22_ARCHITEKTURENTSCHEIDUNG.md),
[Integrationskarte](2026-10-22_ERGEBNISBERICHT.md), R01–R07/R15 der
[Risikoakte](2026-10-22_RISIKEN.md). Vorbedingungen dort erfüllen.

Umsetzung in dieser Reihenfolge:

1. Unterstützten Nachweis für Lizenzstatus, Modellberechtigung und Widerruf
   festlegen; exakten Key-/Modelltestplan mit Betreiberfreigabe registrieren.
   Kein Key in Quellcode, CLI-Argumenten, Git, Responses oder Testlogs.
2. Zentrale reine serverweite Statusautorität mit Generation/Secretrevision/
   Komponentenidentität und den fünf Zuständen bauen. Nur `force_community`
   als Absicht persistieren; `pro_enabled` und aktive Runtime ableiten.
   Bestehende Keypriorität inklusive `KROKO_API_KEY` ausdrücklich übernehmen.
3. Kalten Bootstrap und Besitzerprozessaufsicht integrieren: keine nativen
   Imports im Supervisor, eine Kindgeneration, Deadline/Exit-/Retrybehandlung,
   Freefallback nach bestätigtem Proprozessende. Moduleinstiege, installierte
   Scripts, Docker und direkten Recorder/Legacypfad berücksichtigen.
4. Vor `ServerService`/Modelmanager-`refresh` bereits Runtimeabsicht festlegen;
   dessen heutige Ladeprobe darf nicht ungeschützt Pro im ASGI-Prozess starten.
   Status VALID erst nach echtem berechtigten Pro-Modellaufbau plus aktueller
   Readiness. Zweifelsfall CHECK_FAILED.
   Community-only-Defaults dürfen nicht heimlich durch ein Pro-Prüfmodell
   ersetzt werden; hierfür vorab den unabhängigen Lizenznachweis definieren.
5. Capabilitymatrix in `models.py`, Intent, beiden Eligibilitypfaden und
   Registry vereinheitlichen. Free→Community; Pro→Community + bestätigte
   Pro-IDs; unbekannte Runtime/fehlender Nachweis→keine Pro-Auswahl.
   Downloads bleiben explizit, Pro manuell provisioniert; bestehende
   Größen-/SHA-/Quelle-/Rechte- und `.part`-/Atomic-Rename-Guards erhalten.
6. Modellwechsel/Recovery und Scheduler konsequent generationbinden; bei
   Key-/Modus-/Berechtigungswechsel alte Sessions/Jobs invalidieren und
   Prozesswechsel ausführen. Kein Schedulerthread-Reset als Nativewechsel.
   final/realtime teilen konsistent dieselbe Runtime und dieselbe Keyauthority.
   Beide Kroko-Lanes zunächst mit einem physischen Pro-Recognizer teilen;
   unterschiedliche gleichzeitige Kroko-Modelle sind ein separates Realtestgate.
7. Settings-Control-Plane: vorhandene requested/effective-/Revision-/Persist-
   before-commit-Semantik nutzen. Secretstore getrennt, Admin-Unlock nur Auth.
   Serverseitiger Force-Modus ist kein Sessionwert. Keine V2-Wireänderung.
8. Build-/Installationsidentität von flüchtiger aktiver Runtime trennen;
   konsistente vorhandene HTTP-/Settings-/Wireidentität je Prozess. Neue
   Lizenzstatusprojektion nur als explizit spezifizierte, redigierte Serverfläche.

**Erforderliche Tests:** Wahrheitstabelle Key/Force/Status, kein Import/kein
Prüfaufruf ohne Key oder bei Force; fehlendes Addon/Modell; stale-generation-
Success nach Keywechsel; keine Secretpersistenz; echte Lizenzpositiv-/Negativ-
und Timeoutfälle; native Exit-/Neustart-/Fallbacksequenz auf beiden Plattformen;
Pro-Community sowie berechtigte/unberechtigte Pro-IDs; Widerruf während Sessions;
keine alten Ergebnisse/LKG-Freigaben; Reconnect und unveränderte V2-Vektoren;
ganze Unit-/Contractsuite. Mocks und echte Lizenzbelege getrennt berichten.

**Abnahme:** eine aktive Runtime, korrekte serverweite Modellfreigabe,
funktionierender kontrollierter Fallback und erneuter Proversuch ohne
persistierte aktive Variante; klare INVALID/CHECK_FAILED-Klassifikation.
Für Tests vor finalem Packaging kann dieselbe externe private Payloadanordnung
wie im AP-010-Versuch verwendet werden, ohne sie zum öffentlichen Produkt zu erklären.

## AP-KR-030 – Packaging, Release und Gesamtqualifikation

**Eingang:** abgenommener AP-020-Integrationsstand, bestehende kanonische
[Buildreferenz](../../../../build/BUILD.md), [Releasevertrag](../../../release-process.md),
vier native Fingerprints/Inputs aus dem Ergebnisbericht. Keine Änderung
historischer Abnahmeartefakte oder Übernahme heutiger Dummyversion 0.0.0.

1. Komponentenlayout und die zwei gegeneinander gepinnten Paketversionen
   umsetzen (`voice-stt-server[kroko_pro]`→separates `voice-stt-kroko-pro`).
   Addon besitzt nur private Prodateien, keinen Servercode, keine globalen
   gleichnamigen Krokoimports, keine `.pth`. Vollständige Native-`.data`-
   Installationsansicht, Lizenzen/Notices und relativen Loaderpfade erhalten.
2. `setup.py`, `tools/build_distribution.py`, eingebettete Ressourcen und
   Installerqualifikation auf Komponenten umstellen; `cp312-cp312` und beide
   bestehenden AMD64-Plattformen, keine öffentlichen sdists/Endnutzerbuilds.
   Native Free-/Pro-Buildauthority und Secret-Sanitizing bleiben getrennt.
3. Nativeidentität und Repackagingidentität trennen. Ursprüngliche unveränderte
   Payloadhashes/Nativefingerprints erhalten; neuer Wrapperwheel-SHA, RECORD,
   Quellcommit/Tree/Zeit/Schema und Komponentenrolle vollständig binden.
   Neue Nativeänderungen erzwingen deklarierte Revision-/Guardupdates.
4. RC-Komponentenschema ausdrücklich versionieren; `release_tooling/`-
   Kandidatenassembly, Validator, Config, Preflight, State, Adapters,
   Remotechecks, CLI, SHA-Inventar und `qualify_build_identity.py` konsistent
   umstellen. Historische Schema-2-Daten nie als neue Produktrollen interpretieren.
5. Offizielle Imagescope festlegen: Basisimage + optionales von exakt
   qualifizierten Wheels abgeleitetes Addonimage oder dokumentierter eigener
   Imagebuild aus diesen Bytes. Keine Neucompilierung/Neubuilds bei Promotion.
   OCI-Provenienz bindet Paketset, nicht erfolgreiche Lizenz oder Secrets.
6. Gepinnte GitHub Actions behalten: Linuxnative + Windowscrossbuild unter
   Ubuntu, echte frische Windowsinstallation, gemeinsame Artefaktqualifikation.
   Gewöhnliche PR-CI benötigt keine Prosecrets. Lizenztestumgebung gesondert.
7. PyPI Trusted Publisher für neue Komponente, Uploadordner/Resumeprüfungen,
   Imagepromotion/Registryaliases/Releaseassetliste aktualisieren. Eine einzige
   Releaseengine mit Tag zuerst, exakten Bytes, MATCH-resume und
   UNKNOWN/CONFLICT-Abbruch beibehalten. Kein altes Release-State-Fortschreiben
   mit geänderter Produktmenge. Rollback bindet komplettes früheres Paketset.
8. Neue aktuelle Installation, Upgrade von heutigem Free und heutigem Pro,
   Addonnachinstallation/-entfernung und Versionsrollback dokumentieren.
   Bei Altprodukt-Pro zuerst kontrolliert entfernen, keine kollidierenden
   Vollprodukte übereinander installieren. VERSION/RELEASE_NOTES/Metadaten/
   OCI/Manifeste weiterhin eine konsistente Produktversionsauthority.

**Abnahmematrix:** pro OS Basis-only, Basis+Addon, Upgrade/Downgrade,
Addonuninstall ohne Freeverlust, fremde globale Kroko/Sherpa-Installation,
Addon-/Basisversionskonflikt, kaputte/manipulierte Provenienz, fehlende DLL,
vollständige Noticeinventur; `pip check`, Scripts/Assets/native Ursprünge,
echte Modell-/Lizenz-/Fallback-/Reconnecttests, unveränderte V2-Contracts,
gesamte Unit-/Packaging-Suite; exakte RC-Wheel-/Payload-/Imagebindings,
Resume nach Teilerfolg und Abbruch bei geänderter Komponente. Staging nur
nach eigenem Auftrag; öffentliche Publikation/Deployment separat freigeben.

**Abnahme:** unabhängige Linux-/Windows-/Docker-Gesamtqualifikation und
Soll-/Ist-/Abweichungsakte. Danach gesonderter abschließender Squash-PR vom
Integrationsbranch in den geschützten V2-Zielbranch; kein automatischer Merge.
