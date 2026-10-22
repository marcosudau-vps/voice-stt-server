# AP-KR-010 – Architekturentscheidung und Lizenzstatusvertrag

22.10.2026. **Bedingte Empfehlung**, zur unabhängigen Prüfung. Entwurf,
keine produktive Implementierung. Evidenz im [Ergebnisbericht](2026-10-22_ERGEBNISBERICHT.md).

## Entscheidung: disjunkte Payloads, eine Prozessgeneration

Basisdistribution `voice-stt-server` enthält Community. Optionale Distribution
`voice-stt-kroko-pro` enthält ausschließlich Pro-Payload und dessen Metadaten/
Lizenzen. Vorgeschlagene private Paketwurzeln:

```text
site-packages/
  VoiceSTT/...                      # Servercode, nur ein Dateibesitzer
  voice_stt_server/...              # öffentliche Imports/CLI unverändert
  voicestt_kroko_free/payload/      # komplette Free-Installationsansicht
  voicestt_kroko_pro/payload/       # komplette Pro-Installationsansicht
```

Die vorgeschlagenen privaten Namen sind keine produktiven neuen Imports.
Im Experiment heißen sie `ap010_free_runtime`/`ap010_pro_runtime`.
Keine `.pth`-Datei, keine automatische globale Pfaderweiterung bei Installation.
`kroko_onnx`, `_sherpa_onnx`, ONNX-/OpenSSL-DLLs und relative Unterordner
bleiben innerhalb des gewählten Payloadroots bytegleich und namensgleich.
Wheel-`.data/platlib` muss zuerst korrekt in diesen Root gespreadet werden.

Ein kontrollierter Bootstrap stellt vor dem **allerersten** nativen Import
exakt einen Root an den Importpfadanfang und prüft die Provenienz sowie alle
relevanten Modulursprünge. Er akzeptiert keine beliebigen Client-/Configpfade
als ausführbare Runtime. Fremde global installierte `kroko-onnx`-/`sherpa-onnx`
oder schon geladene gleichnamige Extensions müssen als Konflikt behandelt
werden. Der kompatible Source-/Entwicklerpfad ist explizit zu definieren.

Der bestehende ASGI-/Schedulerprozess ist der native Besitzer. Er wird bei
Varianten-, Key- und berechtigungsrelevantem Modellwechsel vollständig beendet
und neu gestartet. Ein kleiner nativerzeugungsfreier Launcher/Supervisor bzw.
vorhandene Dienstaufsicht überwacht Startfrist, Prozessende und Freigabe.
Das ist zusätzliche Lifecyclelogik, **kein zweiter permanenter ASR-Worker**.
Windows-Konsole, installierte CLI und Docker benötigen denselben Vertrag;
`python -m VoiceSTT_server.server` darf ihn nicht versehentlich umgehen.

Nur eine ASGI-Kindgeneration darf native Modelle besitzen. Vor Start der neuen
Generation wird die alte beendet und ihr Exit bestätigt. Währenddessen besteht
eine kurze Dienstunterbrechung; bestehende Sessions reconnecten. Unterstützter
Erstzuschnitt: ein verwalteter ASGI-Prozess, kein beliebiges Uvicorn-Multiworker-
Setup. Ein dauerhaft nativer Free-Prozess neben einem Pro-Prozess wäre nicht
vertragskonform. Standalone-Recorderpfade müssen dieselbe Grenze einhalten.

## Bewertete Alternativen

| Ansatz | Bewertung |
| --- | --- |
| Zwei heutige Vollprodukte / zwei originale Kroko-Wheels im selben site-packages | Verworfen: gleiche Dateien, Metadatenname des Intermediates identisch; pip ersetzt/überschreibt, Deinstallation beschädigt die andere Variante. |
| Nur ein Python-Extra | Unzureichend: steuert Abhängigkeiten, löst weder Dateikollisionen noch Prozessglobalzustand. |
| Private Roots + nur `sys.path` umschalten | Für kalte Auswahl verifiziert; als Wechsel verworfen, zweiter Import bleibt erste Extension. |
| `sys.modules` löschen, reload, Extension umbenennen, dlclose/FreeLibrary | Verworfen: kein belegbarer Reset von C++-Singletons, Reporterthread, abhängigen Bibliotheken und Referenzen. Keine Upstreamänderung nur für Aliasnamen. |
| Separate venvs | Technisch möglich mit Prozesswechsel, aber zusätzliche Python-/Dependencyinstallationen und Launcherpfade; liefert keinen Schutz ohne Prozessgrenze. Reserve für nachgewiesene Loaderkonflikte. |
| Private Roots + vollständiger Besitzerprozesswechsel | **Empfohlen:** beide Plattformen mit unveränderten Binärbytes geprüft; kleiner Eingriff in Nativepackaging, zuverlässiger nativer Reset. |
| Neuer permanenter ASR-Worker hinter stabiler ASGI-Schicht | Hält Verbindungen eher stabil, verlangt IPC/Audio-/Schedulerumbau. Erst nötig, wenn unterbrechungsfreier Wechsel bindend wird; derzeit unnötiger Umfang. |
| Upstreamstatus-/Fehlerpatch | Für Isolation nicht notwendig. Für strukturierte Lizenzdiagnostik/Entitlements eventuell erforderlich, sofern Anbieter keine unterstützte Schnittstelle bereitstellt. Dann neue deklarierte Nativeauthority, kein versteckter Patch. |

## Start, Fallback, Wiederholung

1. Serverabsicht/Secretrevision/Komponentenprovenienz ohne native Imports lesen.
2. Kein Key oder force-Community: Status NOT_CHECKED, sofort Free starten.
   Pro wird weder geladen/initialisiert noch validiert. Installiertes Addon
   allein ist keine Aktivierungsabsicht.
3. Key vorhanden, Community nicht erzwungen: Freigabe der alten Generation
   invalidieren, Prokandidat in frischem Besitzerprozess mit Startfrist laden.
   Fehlt Addon, autorisiertes Pro-Prüfmodell oder unterstützter Lizenznachweis:
   CHECK_FAILED, Community. Kein Community-Recognizer als Lizenzprobe.
4. Erst nach echtem erfolgreichen Laden eines integritätsgeprüften berechtigten
   Pro-Modells und generationgebundener Readinessmeldung darf VALID entstehen.
   Dieser Kandidat wird dann der bedienende Proprozess. Keine doppelte
   Aktivierung durch erst eine Lizenzprobe und danach dasselbe Modell erneut
   in einem anderen Prozess, solange Aktivierungs-/Singletonvertrag offen ist.
5. Fataler Exit, Timeout, beschädigter Nativeinput oder expliziter Lizenzfehler:
   Kandidat vollständig beenden, Freigabe verwerfen, Free in neuer Generation
   starten und Community-Modellsnapshot aufbauen. Fehlt auch Communitymodell,
   ehrlich nicht bereit bleiben; keine implizite Modelldownloadrettung.
6. Kein sofortiger endloser Pro-Recoveryloop bei unverändertem Key. Ein
   flüchtiger Versuchszähler/Backoff je Konfigurationsgeneration verhindert
   Crashloops. Neue Keyrevision, Moduswechsel zurück zu Auto oder expliziter
   Retry darf eine neue Prüfung starten. Dieser Ablaufzustand ist kein
   persistiertes `active_engine` oder `pro_enabled`.
7. Lizenzverlust im Betrieb: Freigabe sofort verwerfen, Sessions/Jobs der
   alten Generation sperren, vollständigen Prozesswechsel auf Free durchführen.
   Harte native Exits erkennt die Aufsicht, bei unklarer Ursache CHECK_FAILED.
   Späte alte Events/Readinessmeldungen dürfen nie eine neue Freigabe erteilen.

Das Experiment belegt die native Exit-/Neustartfolge. Produktweiter Supervisor,
Abbruch-/Reconnectsemantik und Statuskommunikation sind noch umzusetzen und
zu testen; kein entsprechendes PASS wird aus subprocess.run abgeleitet.

## Lizenzstatusvertrag (Entwurf, B3 – CODEANALYSE)

Eine zentrale, serverweite Autorität hält nur flüchtigen Prüfzustand:
`status`, `generation`, opake `credentialRevision`, geprüfte `runtimeIdentity`,
konkrete `validatedModelIds`/Berechtigungsmenge, Prüfzeit und Gültigkeitsgrenze,
sanitisierten `reasonCode`. Niemals Keywerte, Keyhashes, Entschlüsselungsdaten
oder native Rohantworten in diesem öffentlichen/datentragenden Snapshot.

Persistiert werden ausschließlich Serverabsicht (`force_community` und
gewünschte Modelle) und die referenzierte Secretkonfiguration. Weder aktive
Runtime noch pro_enabled noch VALID werden persistiert. Beim Neustart neu prüfen.

```text
pro_enabled = api_key_present AND NOT force_community
              AND license_validation_successful

license_validation_successful = status == VALID
  AND proof.generation == current_generation
  AND proof.credentialRevision == current_credential_revision
  AND proof.runtimeIdentity == selected_pro_payload_identity
  AND proof is current and owner_process_is_alive

aktive Runtime = pro wenn pro_enabled, sonst free
```

Während CHECKING ist der Proprozess nur Kandidat, kein freigegebener aktiver
Dienst. Es wird keine zweite Community-Runtime daneben initialisiert.
Für ein Pro-Modell ist zusätzlich die konkrete Modellberechtigung notwendig;
`pro_enabled` allein berechtigt nicht den ganzen Katalog. Community benötigt
keinen Key; unter gültigem Pro nutzt sie dieselbe bereits aktive Pro-Runtime.

| Ausgang / Ereignis | Neuer Status / Wirkung |
| --- | --- |
| Kaltstart, kein Key oder force-Community | NOT_CHECKED; Free, keine Proprüfung |
| Prüfabsicht mit Key/Auto | CHECKING; alte Freigabe und Modellberechtigungen löschen |
| Belastbarer positiver Nachweis für aktuelle Generation | VALID; Berechtigungen nur aus bestätigtem Nachweis, Pro anbieten |
| Explizite autoritative Ablehnung / bestätigter Ablauf / Widerruf | INVALID; Pro sperren, alte Berechtigungen löschen, Free starten |
| Netzwerk, Timeout, Prozessabbruch, fehlendes Addon/Prüfmodell, unklare Antwort | CHECK_FAILED; kein erfundenes INVALID, Pro sperren, Free starten |
| Keyänderung/-entfernung, force-Community geändert, Native-/Prüfmodellidentität geändert | Generation erhöhen, vorherigen Nachweis atomar verwerfen; NOT_CHECKED, dann ggf. CHECKING |
| Verspätetes Ergebnis alter Generation | verwerfen; Status/Freigabe unverändert |
| Native Exit nach VALID, Ursache unbekannt | CHECK_FAILED; niemals automatisch alte VALID-Freigabe übernehmen |

**Wichtige Integrationsgrenze:** Der aktuelle Pythonbindingvertrag liefert
keine strukturierte Ablehnung oder laufende Status-/Entitlementliste. Exit 1
allein unterscheidet keine Lizenzablehnung von einem Modellfehler. INVALID ist
deshalb als eigener Zustand vorgesehen, aber nicht aus Exitcodes/Rohlogs zu
erraten. AP-020 braucht einen belastbaren Anbieterstatusvertrag bzw. eine
explizit beschlossene minimale Schnittstellenergänzung. Keine neue eigene
Lizenzserverimplementierung und kein Reverse Engineering als Produktvertrag.

Späterer Verlust darf nicht nur beim ersten Import geprüft werden. Der native
Reporter/Prozesswächter erfasst harte Exits, aber keine garantierte zeitnahe
Freigabeänderung bei jedem Netzwerkzustand. Vor AP-020 müssen Ablauf-/Offline-
Regel und maximal zulässiges Alter eines Nachweises feststehen. Ohne
unterstützte Runtime-Signale konservativ begrenzte Freigabe mit vollständiger
Reaktivierung nach Frist; keine frei erfundene Grace Period. Deren Zeit- und
Aktivierungseffekte müssen real geprüft werden.

Key-/Moduswechsel blockiert neue Pro-Jobs sofort. Laufende Jobs werden nach
festgelegtem Abschluss-/Abbruchvertrag beendet, alte Resultate durch
Generationbindung verworfen. Lizenzwiderruf erlaubt keinen weiteren Proauftrag.
Protokollseitige Segment-/Terminalregeln dürfen nicht umgeschrieben werden.
Session-Admin-Unlock autorisiert ggf. eine Serverabsichtsänderung, ersetzt
aber niemals die Lizenzprüfung. Secrets bleiben außerhalb des Settingspatches.

Der aktuelle Build erlaubt keine belegte versteckte Lizenzprobe neben einem
Community-Recognizer. Ohne unabhängige Validierungsschnittstelle muss das
geprüfte Pro-Modell zugleich zur ausdrücklich gewünschten und zugelassenen
Prozessmodellkonfiguration gehören. Ein Community-only-Default plus Key darf
deshalb nicht still auf ein anderes Pro-Modell umgestellt werden, um VALID zu
erzeugen; ohne passenden separaten Nachweis bleibt Community aktiv. Dieser
Bootstrapfall ist Teil des vor AP-020 zu klärenden Schnittstellenvertrags.
Im ersten qualifizierbaren Prozuschnitt sollen final/realtime dasselbe
physische Kroko-Modell teilen (`use_main_model_for_realtime=true`), soweit beide
Kroko nutzen. Mehrere unterschiedliche Kroko-Recognizer im Prozess benötigen
einen eigenen realen Nachweis; der vorhandene Singleton und der in BUILD.md
dokumentierte Pro-Mehrfachladeabsturz sind dagegen konkrete Risiken.

## Paketmetadaten und Versionsbindung (Entwurf)

Für dieselbe normalisierte Paketversion `V`:

```text
voice-stt-server V:
  Provides-Extra: kroko-pro
  Requires-Dist: voice-stt-kroko-pro==V; extra == "kroko-pro"

voice-stt-kroko-pro V:
  Requires-Dist: voice-stt-server==V
```

Die Rückabhängigkeit schützt direkte Addoninstallation vor Serverversionsdrift;
die optionale Kante ist ein auflösbarer Metadatenzyklus. Das lokale
Extraexperiment prüft diesen Ansatz mit 0.0.0. Die Produktnamen sind Vorschläge,
ihre Registry-Verfügbarkeit wurde nicht reserviert oder veröffentlicht.
Beide Produkte: CPython 3.12, konkrete vorhandene AMD64-Plattformtags, keine
sdists als öffentlicher Ersatz. Basisdependencies aus setup bleiben vollständig;
Addon enthält keinen zweiten Servercode/CLI und zieht kein globales Kroko-Wheel.
Nativeversion/Fingerprint und Serverreleaseversion bleiben getrennt.

Provenienz wird komponentenbewusst: je installierter Payload eigene
unveränderliche Herkunft; aktive Auswahl und Lizenzstatus gesondert in RAM.
Das bestehende einmal eingefrorene App-Identitätsobjekt muss bei Prozessstart
konsistent die gewählte Runtime projizieren. Keine geänderten V2-Envelopes,
keine Lizenzzustände in `serverCommit`/`serverVersion`. Konkrete Aufnahme
zusätzlicher HTTP-Statusdaten ist AP-020-Spezifikation, keine stille Wireänderung.
