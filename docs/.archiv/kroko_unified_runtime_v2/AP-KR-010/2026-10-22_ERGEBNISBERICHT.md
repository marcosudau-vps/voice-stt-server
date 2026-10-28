# AP-KR-010 – Technischer Ergebnisbericht

Untersuchung vom 22.10.2026. Urteil: **CONDITIONAL GO** für die gemeinsame
Distribution mit getrennten nativen Payloads und vollständigem Prozesswechsel.
Keine Freigabe einer produktiven Implementierung oder Veröffentlichung.
Die Voraussetzungen vor AP-KR-020 stehen in der [Risikoliste](2026-10-22_RISIKEN.md).

## Ausgangsstand und Artefakte (B0/A1 – VERIFIZIERT)

Anfang: sauberer `main` auf `714b1cf`; enthält den aktuellen V2-Stand nicht.
Nach Fetch: zuletzt übernommener V2-Merge
`67f3ce45f6ea1ff659382e40c194c70bd33d58ff`, PR #10, gemergt am 20.10.2026.
Integrationsbranch `feat/v2-unified-kroko` und davon Arbeitsbranch
`feat/v2-unified-kroko-ap010` wurden exakt dort angelegt.
Die tatsächliche Aktion wurde mit Plancommit `5ae877e` vor Experimenten registriert.

PR-HEAD `a694cd822d12c31e1d02d77e1518cae05c6a98b1` und Merge haben denselben
Git-Tree `74f37cad84c5be9e74d880a4b10c3d9623de7da3` (`git diff` leer).
[CI 39378549972](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39378549972)
und [vollständiger RC 39405176300](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39405176300)
stehen auf SUCCESS. RC `gh-39405176300-1` benennt genau diesen HEAD/Tree,
`releaseReadiness=QUALIFIED`. Mergeübernahme ist belegt; keine zusätzliche
menschliche Abnahmeakte über den Merge hinaus gefunden/behauptet.
Historische Texte mit RC NOT_RUN bleiben unverändert.

RC-Artefakt 12258386468 (165047167 Bytes; API-Digest
`sha256:61e3f624c20fa25ec1d0698f436dec1fadf3fd1a07bdd4fc57ce2d4bfc3dfeb0`)
mit `gh run download` außerhalb des Repositorys entpackt. Der API-Archivdigest
ist Referenzmetadatum, hier nicht durch einen separaten ZIP-Download nachgerechnet.
Dagegen wurden **alle 62 inventarisierten Dateien lokal gegen Größe und SHA-256
geprüft**. Die vier echten Produktwheels enthalten die hier geprüften nativen
Payloads. Originale Kroko-Intermediate-Wheels liegen im RC nicht separat vor;
deren Identität stammt aus der eingebetteten Provenienz, nicht aus einem
hier erneut gehashten Intermediate-Archiv.

| Plattform / Runtime | Produktwheel-SHA-256 | Native Fingerprint | Original-Kroko-Wheel-SHA aus Provenienz |
| --- | --- | --- | --- |
| Linux Free | `128f2181c69dcd5e0103bccbb3e2da7ae06a03c55fb5839047bc677c4277d423` | `2ee9379d7d2f5d34` | `9122719e8a084642fd62748aab9a631a6df716bdebde94ec2a7808e6e746269f` |
| Linux Pro | `1622be6052d6d1f955e8418c5dc2e4f37d4d76102ac544181f7ea47f678097ed` | `fe782f84f5e7d93f` | `d4200a3870f872501abcdbd1427c2ba51d658a4d9c42992e5ddb2f0cff896809` |
| Windows Free | `c785c9d960175f160d4d870c33399c259c89fc1bf51e6000b164a0be702f5975` | `60eadb3428690d3d` | `93a8b3dba9875ccf7cb720228e0333c295a1e1d50eebb77bdf8052fdc0e7a329` |
| Windows Pro | `191b6676bbbe503cbe6d96d56069c820a3977c3ad6ab32c2c6a2672b4ccb571e` | `e4f939933cd9985d` | `349e7a3db4ebf25cffb0edae314e116095fd1f0de0d3fab5599dbf2f87f73383` |

Alle Runtimeidentitäten: Kroko 1.12.9, Upstream
`8657e655192623b98d7708e742a72987f953d3a2`, Buildtag `1free`/`1pro`,
`cp312-cp312-linux_x86_64` bzw. `cp312-cp312-win_amd64`.

## Native Isolation (A2–A7 – VERIFIZIERT, Grenzen ausdrücklich)

Beide Varianten exportieren `kroko_onnx` und `_sherpa_onnx`; außerdem
`sherpa_onnx`-Payloads. Linux hat 14 gemeinsame installierte Payloadpfade,
Windows 19. Linux unterscheiden sich insbesondere Extension und C-API-Bibliothek;
Windows Extension sowie C-/C++-API-DLL. Windows Pro hat zusätzlich zwei
gehashte OpenSSL-DLLs. Unterschiedliche Distributionsnamen lösen die Kollision
derselben Import- und Bibliotheksdateien nicht.

Linux: `_sherpa_onnx.cpython-312-x86_64-linux-gnu.so`,
`sherpa_onnx/lib/libonnxruntime.so`, `libsherpa-onnx-c-api.so`,
`libsherpa-onnx-cxx-api.so`. `readelf -d` zeigt RUNPATH
`$ORIGIN:$ORIGIN/sherpa_onnx/lib`; Pro benötigt u.a. System-OpenSSL 3,
libstdc++, libc und die mitgelieferte ONNX-Runtime. Kein neuer manylinux-Nachweis.

Windows: `_sherpa_onnx.cp312-win_amd64.pyd`, ONNX-DLLs und API-DLLs.
PE-Importtabellen (`pefile`) zeigen Python 3.12, Kernel32, Winsock, gehashte
ONNX-Runtime; Pro zusätzlich gehashte libcrypto/libssl. Delvewheel registriert
den Payloadwurzelordner über `os.add_dll_directory`.
Entscheidend: die gehashte ONNX-DLL liegt im Wheel unter
`kroko_onnx-1.12.9.data/platlib/`; beim Installieren muss sie in denselben
privaten Payloadroot wie die Extension **gespreadet** werden. Einfaches Kopieren
nur von `kroko_onnx/`, `sherpa_onnx/` und Rootdateien scheitert am DLL-Import.
Der erste Experimentlauf hat genau das aufgedeckt; der korrigierte Versuch
bildet die Wheelinstallationssemantik ab, ohne Binärbytes zu verändern.

Reale Plattformen: Windows 11 AMD64 CPython **3.12.10** und Ubuntu unter
WSL2 x86_64 CPython **3.12.3**, glibc 2.39. Native Linuxausführung unter WSL
ist ein Linuxbeleg; anderer Kernel/Deploymentcontainer und Docker wurden hier
nicht erneut qualifiziert. Docker Desktop war pausiert und blieb unverändert.

| Fall (je Plattform) | Ergebnis |
| --- | --- |
| Free allein importieren | Exit 0, Modul/Extension aus gewähltem privaten Root |
| Pro allein importieren | Exit 0 ohne Key, keine exportierte Lizenzvalidierungsfunktion gefunden |
| Free→Pro-Pfadwechsel im Prozess | zweiter Import bleibt dasselbe Free-Modul/Extensionobjekt |
| Pro→Free-Pfadwechsel im Prozess | zweiter Import bleibt dasselbe Pro-Modul/Extensionobjekt |
| Free + Community-Modell initialisieren/Stille decodieren | Exit 0, Recognizer und Stream erfolgreich, leeres Stilletranskript |
| Pro + dasselbe Community-Modell ohne Key | Exit 0, Recognizer/Stream/Decode erfolgreich; **keine Pro-Lizenzvalidierung** |
| Pro + eigene ungültige Headerfixture | Import zuvor erfolgreich; native Meldung `Failed to load model header.`, Exit 1 ohne Pythonexception |
| Frischer Free-Prozess nach dem Fehler | Initialisierung/Decode erfolgreich |
| Erneut frischer Pro-Prozess nach Free | Initialisierung/Decode mit Community erfolgreich |

Das sind **18 reale Prozessfälle** (8 normale Erfolge und ein erwarteter
nativer Exit je Plattform). Der Eltern-Testprozess überlebt den nativen Exit.
Dies belegt die Prozessgrenze und Wiederanlaufsequenz, **keinen implementierten
Produkt-Supervisor** und **keinen ungültigen Lizenztest**.

Modell: vorhandene Betreiberdatei `Kroko-DE-Community-64-L-Streaming-001.data`,
155839333 Bytes, SHA-256
`0013d4b3e1216b4e0c15f18f345aa58ca8bb2cdbeff7a7d55a513f6b400862a5`;
vor Versuchen gegen das Manifest verifiziert, ausschließlich gelesen.
Keine Modell- oder Credentialbeschaffung. Alle vier Key-Envnamen werden in
nativen Kindprozessen entfernt; `key=""`. Pro-Modelldateien existieren lokal,
aber keine ausdrücklich eingerichtete Lizenztestumgebung wurde verwendet.

Strikte Unterscheidung: **beide bereitgestellt/installiert: ja**;
**zwei Imports versucht: ja, gecachtes erstes Modul**;
**beide nativen Varianten gleichzeitig im selben Prozess geladen: nicht getestet**;
**beide tatsächlich gleichzeitig initialisiert: nicht getestet und nicht empfohlen**.
Kein Löschen von `sys.modules`, Umbenennen der Extension, dlclose/FreeLibrary
oder behauptetes sicheres Entladen. Die [CPython-Dokumentation](https://docs.python.org/3.12/library/importlib.html#importlib.reload)
beschreibt Grenzen beim Reload nativer Extensions; ein Reload ist kein
Reset der hier vorhandenen C++-Singletons/Threads (CODEANALYSE).

## Lizenzmechanismus (B1 – CODEANALYSE, B2 – OFFEN)

Maßgeblich sind die gepinnten Upstreamdateien
[online-transducer-model.cc](https://github.com/kroko-ai/kroko-onnx/blob/8657e655192623b98d7708e742a72987f953d3a2/sherpa-onnx/csrc/online-transducer-model.cc),
[license.h](https://github.com/kroko-ai/kroko-onnx/blob/8657e655192623b98d7708e742a72987f953d3a2/sherpa-onnx/csrc/license.h)
und Pythonbindings. VoiceSTTs Patch `patch_license_quiet_env` unterdrückt
Lizenzausgaben; er schafft keine neue Validierungs-/Fehlerschnittstelle.

- Import konstruiert keinen Pro-Recognizer und ist keine Validierung. Native
  Exportinventur beider Plattformen zeigt keine separate Lizenz-/Entitlement-API.
  Die vorhandenen `validate`-Configmethoden sind keine Lizenzprüfung.
- `BanafoLoadModel` liest den Header. Nur bei Pro-Build und Header `free=false`
  wird `BanafoLicense::getInstance(key, model-id, referralcode)` aufgerufen.
  Community lädt auch im Pro-Build ohne diesen Lizenzpfad. Dass dies ohne Key
  funktioniert, ist zusätzlich real geprüft; ein ungültiger Key wurde nicht gesendet.
- Der Lizenzclient nutzt WSS zu `license.kroko.ai` mit Key und Modell-ID.
  Er verarbeitet `allowed`, Fehler, Laufzeit-/Kontingentfelder, Ablaufdatum,
  Reportintervall, Offlinetimeout, Verbindungsgrenzen, Featureliste und
  Entschlüsselungspasswort. Diese Daten sind nicht als Pythonstatus exportiert.
- Aktivierung wartet auf `is_finish`; Ablehnung beendet beim Modellladen den
  Prozess mit Exit 1. Ein erstmalig nicht erreichbarer Server kann endlos
  retryen: anfänglicher `offline_timeout=0` und keine verbindliche Startupfrist.
  Python-`try/except` kann weder dieses Warten noch `exit(1)` zuverlässig abfangen.
- Periodischer Reporter läuft als abgetrennter Thread einmal je Prozess.
  `allowed=false` und überschrittener Offlinetimeout können später ebenfalls
  den Prozess beenden. Ein Nutzungsreportfehler ist nicht automatisch eine
  unterscheidbare Lizenzablehnung. Abgelaufen/ungültig/unberechtigt sind ohne
  echte Antwort-/Fehlervertragsprüfung nicht zuverlässig klassifizierbar.
- `BanafoLicense` bindet ersten Key und erste Modell-ID pro Prozess;
  `ModelData` ist ebenfalls Singleton. Key-/Modellwechsel durch neuen
  Recognizer oder Schedulerthread sind kein belastbarer Zustandsreset.
  Keine Zusage, dass ein Key alle Pro-Modelle berechtigt.

**OFFEN:** positive Aktivierung eines berechtigten Pro-Modells; echte ungültige,
abgelaufene, widerrufene, offline und modellunberechtigte Fälle; sichere
spätere Statusprojektion; dokumentierter Feature-/Modellberechtigungsvertrag.
Kein Testkey wurde erfunden, gesucht, ausgegeben oder committet.
Der [Anbieter beschreibt Lizenzkontakt und Nutzungsberichte](https://docs.kroko.ai/on-premise/);
das ersetzt keine Integrationstests des konkret gepinnten Builds.

## Server- und Modellintegration (C1 – CODEANALYSE)

| Quelle / Einstieg | Ist-Vertrag und notwendige Folgeänderung |
| --- | --- |
| `VoiceSTT/kroko/models.py:check_variant_compatibility` | Exakte Gleichheit Free/Pro sperrt Community unter Pro; explizite Fähigkeitsmatrix Free→Community, Pro→Community plus berechtigte Pro, unbekannt→gesperrt. Hash-/Größen-/Herkunftsprüfungen erhalten. |
| `VoiceSTT/assets/kroko/models.json` | 4 Community-/8 Pro-Einträge; `requiresRuntimeVariant=free/pro` bezeichnet Mindestfähigkeit, künftig keine ausschließliche Distribution. Modellhashes, Bytes, Quellen und Rechte nicht umdeklarieren. |
| `VoiceSTT/transcription_engines/model_resolver.py:resolve_kroko_model` | Lokalpfad-/Rootauflösung, keine impliziten Downloads. Direkte Enginepfade bleiben lokale Entwicklerfläche; Servermodellfreigabe muss vor Resolver/Engine greifen. |
| `VoiceSTT/transcription_engines/kroko_onnx_engine.py` | Lazy globaler Import; Schlüssel aus Options/Env, verschachteltes `recognizer` kann kwargs überschreiben. Zentrale Auswahl vor jedem nativen Import; konsistente Secrets für final/realtime, keine per Session wechselnde Runtime. |
| `VoiceSTT_server/stt_model_management.py:STTModelIntent.from_settings` | Runtime derzeit aus persistenten Engineoptionen/Config/Env/default Free; durch abgeleiteten serverweiten Autoritäts-Snapshot ersetzen, Altwerte kontrolliert migrieren. |
| `STTModelManager._eligible`, `candidate_eligible` | Beide vergleichen Variante exakt. Einen gemeinsamen Capability-/Entitlementcheck für Auswahl, Recovery und öffentliche Registry nutzen. |
| `KrokoAdapter`, `AtomicModelProvisioner`, `ManagedModelRegistryView` | Lokale Größe, atomare SHA-/Quellenprüfung beim Provisionieren, `available/eligible/validationState` getrennt. Lokale Pro-Datei ist kein Recht. Bekannte unberechtigte Modelle nicht als auswählbar anbieten; Registry und Servervalidierung konsistent filtern. |
| `api_fastapi_server/server.py:ServerService.__init__`, `_probe_stt_model` | Bereits `refresh()` im Konstruktor kann per scheduler_factory eine native Ladeprobe auslösen, lange vor normalem Serverstart. Auswahl/Deadline/Pro-Berechtigung müssen davor greifen; Probe ist derzeit ein Thread im ASGI-Prozess. |
| `SharedEngineWorker`, `InferenceScheduler` | ASGI nutzt Threads für shared final/realtime; Recorder-Multiprocessing schützt diesen Pfad nicht. Stop/Neubau des Schedulers entlädt keine native Library. Variantenwechsel muss ganzen besitzenden Prozess ersetzen. |
| `refresh_stt_models`, `_switch_models_locked` | Bestehender Pythonexception-Rollback rettet keinen nativen Exit und keine alten Lizenzsingletonwerte; Key-/Modus-/Pro-Modellwechsel über neue Prozessgeneration. Community-Fallback darf keinen alten Pro-LKG-Snapshot restaurieren. |
| `active_models`, `GET /v1/models`, `GET /api/models/active`, `PUT /api/models/active` | Konfigurierte Auswahl, aufgelöste Auswahl, tatsächlich aktive Modelle und Freigabe getrennt halten; keine Pro-Auswahl während CHECKING/INVALID/CHECK_FAILED; serverseitig auch Requests mit manuell gesetzten IDs abweisen. |
| `api_fastapi_server/settings_control.py` | Revision, Persist-before-commit, requested/effective und `server_restart` wiederverwenden. Force-Community als Serverabsicht behandeln; Secret-Patches sind bereits verboten. Kein Umdeuten von Session-Admin-Unlock zur Lizenzfreigabe. |
| `VoiceSTT_server/credential_redaction.py`, ConfigStore/Settings.public_dict | Bestehende vier Runtime-Keyaliases/redigierte Antworten erhalten. Keine Keys, Fingerprints des Keywerts, nativen Rohfehler oder Lizenzantwortpasswörter in Events/Settings/RC speichern. Keyrevision als opaker Zähler. |
| `api_fastapi_server/protocol_v2/identity.py`, `VoiceSTT/_build_identity.py`, `voice_stt_server/_embedded.py` | Installation ist heute gleichzeitig aktive Variante; Konfliktcheck würde Basis-Free+Pro ablehnen. Unveränderliche Buildidentität muss verfügbare Payloads belegen; aktive Runtime gehört zum Prozess-Snapshot. Keine Lizenzdaten in Buildprovenienz. |
| `VoiceSTT/kroko/artifacts.py:verify_installed_runtime` | Import + Variantenmarker belegt Laufzeitidentität, keine Lizenz; Mehrkomponenteninstallation und disjunkte Dateibesitzer berücksichtigen. |
| `VoiceSTT/core/initialization.py`, `VoiceSTT/core/transcription.py` | Direkte Recorder-/Legacypfade haben eigene Worker und ggf. Realtime im Elternprozess; dieselbe Auswahl vor allen Imports erzwingen. Kein zweiter dauerhafter ASR-Worker nur für Pro. |
| `config.yaml`, Dockerfile/Compose, `install_kroko.py`, `tools/compose.py` | Buildvariante von force-Community und aktiver Auswahl trennen; Builder Free/Pro und Sanitizing bleiben bestehen. Key nie Buildinput. Kein Deployment in AP-010. |
| `api_fastapi_server/static/index.html`, `app_browserclient`, V2-Settings/Clients | Listen/aktive Auswahl aus Serverprojektion, keine Erkennung anhand installierter Paketnamen oder Keyfeld. V2-Envelopes, Pflichtfelder, Audio-, Ack-/Activation-/Segmentsemantik bleiben unverändert. Reconnect nach Prozesswechsel erneut qualifizieren. |

Bestehende Sicherheitsgrenzen: Manifestrechte Community `POLICY_REQUIRED`,
Pro `PROHIBITED`; keine Modelle im Paket. Laufzeitauflösung prüft nicht überall
automatisch SHA-256 (lokale Adapter prüfen u.a. Größe). Deshalb vorhandene
Integritätsgarantien genau erhalten und die neue Freigabe daran binden;
keinen hier nicht vorhandenen flächendeckenden Hashnachweis behaupten.

## Packaging und Release (D1/D2)

**VERIFIZIERT mit synthetischer Produktmetadaten-Fixture:** Auf beiden
Plattformen wurden zwei experimentelle cp312-Wheels gebaut: Basis mit realem
Free-Payload unter `ap010_free_runtime/payload`, separates
`voice-stt-kroko-pro` mit realem Pro-Payload unter `ap010_pro_runtime/payload`.
Basisversion 0.0.0, Extra-Metadaten `kroko-pro` mit exaktem Komponentenpin.
In frischer venv: Basis allein enthält kein Pro; offline
`pip install --no-index ... "voice-stt-server[kroko_pro]==0.0.0"` löst Pro
nach; beide Payloads sind bytegleich zum Ausgang; frische Prozesse importieren
je genau eine Runtime; `pip check` besteht. Pro-Deinstallation entfernt keine
Free-Datei; danach Free erneut importierbar. NumPy wurde zuvor separat installiert.
Keine Endnutzerkompilierung. Extra-Unterstrich wird normalisiert, wie die
[PyPA-Spezifikation](https://packaging.python.org/en/latest/specifications/dependency-specifiers/#extras)
vorsieht. **SIMULIERT** bleiben Servermetadata/Anwendung und Releaseversion:
Dies sind keine produktiven Wheels, kein offizieller Build-/Releasepfad.

**CODEANALYSE:** `setup.py`/`tools/build_distribution.py` erzeugen heute zwei
Vollprodukte und betten alle nativen Dateien global ein; `_embedded_kroko.json`
bindet Produktname und eine Variante. `tools/build_production.py` und Docker
haben variantengetrennte Kontexte/Images. Diese Rollen müssen in AP-030 auf
ein Basisprodukt und eine optionale native Komponente umgestellt werden;
die zwei **nativen Builds** bleiben unverändert getrennt.

`release_tooling/rc_manifest.py` Schema 2 verlangt Free/Pro-Distributionen,
je zwei Plattformwheels und zwei unterschiedliche Image-Digests. Es ist kein
generisches Komponentenschema. `candidate.py`, `config.py`, CLI, preflight,
Adapters/PyPI-upload, SHA-Inventar und `tools/qualify_build_identity.py` hängen
daran. `pipeline.py` ist nur Fassade; die einzige Publishreihenfolge steht in
`engine.py`, Resumeidentität in `state.py`, Remote-MATCH/CONFLICT/UNKNOWN in
`remote_checks.py`. Ein Umbenennen des Pro-Wheels reicht nicht.

Empfehlung: neues explizites RC-Schema mit Komponentenrollen
`server`/`kroko-pro`, je Linux-/Windowswheel, abhängigkeitsgebundener Version,
Payloadpfaden/-hashes, originalem Nativefingerprint/-wheelhash und
Repackagingidentität; Images als eigenes Inventar. Historisches Schema 2 bleibt
unverändert lesbar/validierbar oder wird im neuen Publisher explizit abgewiesen,
niemals still neu interpretiert. Eine neue Release-State-Identität bindet
Schema und sämtliche Komponenten; keine Änderung laufender alter Releasezustände.

Release-CI: bestehende gepinnte Actions und Ubuntu-Windows-Crossbuild/
echte Windowsinstallation behalten. Vier Wheels bleiben möglich, jetzt
Basis+Addon pro Plattform; zusätzlich Basis-only, Basis+Addon, kein Key,
force-Community, Fallback/Wechsel, Pro entfernen/Upgrade/Downgrade und
Identity-/Dateibesitzer-Gates. Native/Lizenztests erfordern getrennte
autorisierte Umgebung und dürfen gewöhnliche PR-CI nicht mit Secrets versorgen.
Keine Modell-/Keyabhängigkeit des Builds. `--only-binary`-Matrix ohne sdist.

Docker: ein offizielles Basisimage mit Community; optionales Addon wird aus
exakt qualifiziertem Wheel in ein abgeleitetes Image installiert. Soll zusätzlich
ein fertiges Addonimage veröffentlicht werden, ist es dieselbe Serverdistribution
mit komponentengebundenem Paketset, kein zweites Serverprodukt. Imageumfang
muss vor AP-030 ausdrücklich festgelegt sein. Debian/glibc/System-OpenSSL-
Voraussetzungen bleiben nachzuweisen. Keine Runtime-pip-Installation im Server.

SHA/Fingerprints: bytegleiche native Payloads dürfen ihre ursprüngliche
Nativeauthority behalten. Repackaging ist ein **neues** Artefakt mit eigenem
SHA/RECORD/Buildschema, deterministischen Pfaden/Zeiten und unveränderlicher
Quellidentität. Bei nativer Patch-/Builderänderung Revisionen und Guards erhöhen.
Weder Versionswechsel noch Dokumentation dürfen allein native Neubauten erzwingen.
Keine Behauptung voller nativer Gesamtbyte-Reproduzierbarkeit aus diesem Versuch.

Publikation: neue PyPI-Pro-Komponente benötigt eigenen Trusted Publisher;
Basis-/Komponentenbytes und OCI-Manifeste werden einmal qualifiziert und
danach unverändert veröffentlicht. Tag vor öffentlichem Schreiben, Docker Hub
vor GHCR, Aliases zuletzt, MATCH-resume und fail-closed UNKNOWN/CONFLICT bleiben.
Rollback verwendet ein vollständiges früher qualifiziertes Paketset bzw.
Imagedigest und neu abgeleitete Freigabe, keinen persistierten VALID-Status.

Lizenzressourcen: gepinnte Runtimequelle hat
[Apache-2.0](https://github.com/kroko-ai/kroko-onnx/blob/8657e655192623b98d7708e742a72987f953d3a2/LICENSE).
Das ist keine automatische Freigabe aller gebündelten Drittkomponenten oder
Pro-Modelle. In den geprüften Linuxwheels liegt `KROKO-ONNX-LICENSE`; in beiden
Windowswheels findet die vollständige Namenssuche nur die VoiceSTT-LICENSE,
keinen Kroko-/Drittkomponentenhinweis. **Releaseblocker für AP-030:** exakte
Apache-/ONNX-/OpenSSL-/Toolchain-Notices und separate Redistributionsbedingungen
prüfen und komplett aufnehmen. Keine neuen Modellredistributionsrechte ableiten.

## Reproduktion und Ergebnisdateien

Skripte: [native_probe](experiments/2026-10-22_native_probe.py) und
[extra_probe](experiments/2026-10-22_extra_probe.py). Beide `--help` beschreiben
die Eingänge. Beispiel nach RC-Download:

```text
python 2026-10-22_native_probe.py audit --rc <externer-rc-ordner> --out <payloads>
python 2026-10-22_native_probe.py probes --root <payloads/windows-oder-linux> --model <verifiziertes-community-modell> --manifest <repo>/VoiceSTT/assets/kroko/models.json --out <externe-ergebnisse>
python 2026-10-22_extra_probe.py --root <payloads/windows-oder-linux> --out <neuer-externer-ordner> --probe <absoluter-pfad-zum-native-probe>
```

Lokale Audits/Outputs/Fixtures/Wheels/venvs liegen ausschließlich unter
`C:\Users\marco\AppData\Local\Temp\ap-kr-010-20261022`; Linux-Extraexperiment
unter `/home/marco/.cache/ap-kr-010-extra-20261022`. Nicht als portable
Archivnachweise voraussetzen: dieser Bericht hält Methoden, Inputs und Resultate
fest; generierte Logs/Binärdateien werden gemäß Auftrag nicht committet.
Vorhandene Suite-Ergebnisse stehen in der [Soll-/Ist-Prüfung](2026-10-22_SOLL_IST.md).
