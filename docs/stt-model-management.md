# STT-Modellverwaltung

VoiceSTT verwaltet grosse STT-Modelle fuer Faster-Whisper und Kroko ueber eine
gemeinsame serverautoritative Schicht. Wake-Word-Assets gehoeren nicht zu
diesem System.

## Installierte Kroko-Faehigkeit

Die einheitliche V2-Distribution `voice-stt-server` bringt eine Pro-faehige
Runtime mit. Der Manager liest die tatsaechliche Produkt-/Nativeidentitaet;
Betreibereinstellungen, `VOICESTT_KROKO_VARIANT` und Keys setzen keine Faehigkeit.
Ohne bekannte Nativeidentitaet bleibt sie `unknown`. Entwickler koennen weiter
verifizierte separate Free-/Pro-Nativewheels verwenden.

Community ist ohne Key verfuegbar. Ein lokales Pro-Modell wird erst bei gueltiger
modellbezogener Berechtigung auswaehlbar; Berechtigung ist keine Aktivierung.
Force Community sperrt neue Pro-Jobs sofort. Keyentzug/-rotation bleiben
an Generation und nativen Kontext gebunden; Pythonstatus autorisiert keinen
bestehenden Pro-Kontext neu. Final/Realtime teilen bei gleicher Krokoidentitaet
dieselbe Instanz; verschiedene Proidentitaeten scheitern vor dem Native-Load.
Oeffentliche Statusfelder behalten ihren Vertrag und zeigen echte Faehigkeit,
Lizenzberechtigung, aktives Modell und gegebenenfalls Neustartbedarf getrennt.

## Kroko-Katalogmetadaten

Der [Offline-Modellkatalog](kroko-model-catalog.md) ergänzt die Discovery um
strukturierte Anbieter-Metadaten, Filter und einen reinen Downloadplan.
Katalogeinträge werden nicht automatisch zu Produktmodellen im Manager.
Portal-UUID und bestehende Manifest-ID bleiben getrennt. Das zwölf Modelle
umfassende Manifest, Produktrechte und die folgenden Provisioningregeln
bleiben unverändert.

## Speicher und Suchreihenfolge

Der vorhandene `data_root_path` ist die einzige persistente Laufzeitwurzel.
Die Standardspeicher sind:

```text
<data_root_path>/models/stt/fasterwhisper
<data_root_path>/models/stt/kroko_asr
```

`stt_engine_settings.<engine>.custom_paths` werden in der angegebenen
Reihenfolge vor dem Standardspeicher durchsucht. Alle Pfade werden betrachtet.
Eine schreibgeschuetzte Quelle bleibt eine gueltige Discovery-Quelle; sie wird
nur nicht als Provisioning-Ziel benutzt. Ein explizites
`provisioning_target` wird bevorzugt, sofern es beschreibbar ist, danach folgen
die Custom-Pfade und zuletzt immer der beschreibbare Standardspeicher. Es gibt
keinen zweiten dauerhaften Downloadcache.

## Zustaende und Autoritaetsgrenze

- `DISCOVERED`: Ein lokaler Kandidat wurde einer Engine/Identitaet zugeordnet.
- `VALIDATED`: billige deterministische Struktur-, Metadaten-, Groessen- und
  Kompatibilitaetspruefungen sind erfolgreich.
- `LOAD_VERIFIED`: die echte Engine konnte den ernsthaften Kandidaten laden.

Unveraenderliche Produktfakten stehen in der Produktautoritaet: stabile ID,
Engine, Sprache, Rollen, Community/Pro-/Lizenzklasse, Runtimevariante,
Revision, Dateiname, Inhaltsidentitaet, Provisioningrecht und optionale
`recovery_priority`. Betreiberkonfiguration darf diese Fakten nicht
ueberschreiben. Sie steuert nur Aktivierung, Custom-Pfade, Defaults,
Auto-Download und optionale Prioritaetsoverrides.

Fehlen Revision, SHA-256, Bytezahl, eindeutige Quelle oder erforderliche
Rechte, bleibt automatische Provisionierung hart gesperrt. Ein vorhandenes,
sicher lokal nutzbares Modell darf trotzdem entdeckt und explizit ausgewaehlt
werden.

## Auto-Download

`stt_auto_download_enabled`, das Enginefeld `auto_download_enabled` und das
gleichnamige Modellfeld bilden exakt eine hierarchische ODER-Freigabe:

```text
effective = global OR engine OR model
```

Ein untergeordnetes `false` hebt ein uebergeordnetes `true` nicht auf. Die
Freigabe ist nur Betreiberabsicht; harte Produkt-, Rechte-, Integritaets- und
Runtimevoraussetzungen gelten weiterhin. Der Standard ist ueberall `false`,
damit ein Serverstart keine ueberraschenden grossen Downloads ausloest.

## Recovery und Readiness

Zuerst werden die konfigurierten Final- und Realtime-Defaults betrachtet.
Danach folgen nur Modelle mit `recovery_priority`, aufsteigend und bei Gleichstand
nach stabiler Modell-ID. Ein Modell ohne Prioritaet ist kein generischer
Fallback. Bereits lokale Kandidaten benoetigen keine Auto-Download-Freigabe;
fehlende Kandidaten schon.

Ein load-verifiziertes Modell darf beide Rollen abdecken. Sobald Final und
Realtime abgedeckt sind, ist `MINIMUM_READY` erreicht und die Recovery-
Eskalation endet. Davon unabhaengig explizit angeforderte optionale Modelle
duerfen weiter provisioniert werden. Status unterscheidet deshalb
`ready_complete`, `ready_optional_provisioning`, `ready_optional_errors` und
`not_ready`. Ein optionaler Fehler nimmt einen funktionierenden Mindeststand
nicht zurueck.

```text
START / REFRESH
|
+-- alle Custom-/Standardorte entdecken
+-- Kandidaten billig validieren
+-- lokaler Kandidat fuer benoetigte Rolle(n)?
|     +-- ja: ernsthaften Kandidaten mit echter Engine pruefen
|     |        +-- Rollen abgedeckt: MINIMUM_READY
|     |        +-- Fehler: Recovery fortsetzen
|     +-- nein: Recovery fortsetzen
+-- Recovery
      +-- konfigurierte Defaults zuerst
      +-- danach recovery_priority + stabile ID
      +-- lokal: validieren und load-proben
      +-- fehlend: effective auto-download UND harte Eligibility?
      |            +-- ja: verifiziert atomar bereitstellen, dann load-proben
      |            +-- nein: Diagnose und naechster Kandidat
      +-- MINIMUM_READY: Eskalation stoppen; nur optionale Requests fortsetzen
```

## Atomaritaet, Refresh und Sicherheit

Dateimodelle werden unter einem eindeutigen `.part`-Namen gestreamt, gegen
Quelle, Bytezahl und SHA-256 geprueft und erst danach mit `os.replace` aktiviert.
Part-/Staging-Inhalte sind nie Discovery-Kandidaten. Ein Fehler laesst eine
vorherige Zieldatei unangetastet; temporaere Daten werden entfernt.
Zielbezogene Sperren serialisieren konkurrierende Provisionierungen.

Refresh baut einen vollstaendigen Kandidatensnapshot ausserhalb des aktiven
Registry-Snapshots auf und publiziert ihn atomar. Schlaegt ein Refresh fehl,
bleiben Registry, Rollenzuordnung und `MINIMUM_READY` des letzten guten Stands
erhalten.

Kroko-Pro-Modelle muessen zur explizit aufgeloesten Runtimevariante `pro`
passen. Ein Lizenzschluessel ist ausschliesslich Runtime-Credential: seine
blosse Anwesenheit waehlt weder Pro noch macht sie ein Modell eligible. Die
Eligibility kommerzieller Kroko-Modelle entscheidet der Lizenz-Guard (naechster
Abschnitt) anhand einer frischen, modellgebundenen Pruefung; ob die konkrete
Pro-Runtime mit dem Credential laden kann, entscheidet erst der echte
Load-Probe. Der Lizenzschluessel wird weder in Modellmetadaten noch Status,
API-Antworten, Audit-/Performance-Events, Diagnosen oder Runtime-Persistenz
geschrieben; bekannte Aliase und verschachtelte Kroko-Optionsfelder werden an
allen diesen Grenzen zentral entfernt bzw. redigiert.
Native Kroko-Runtimes und ASR-Modelle sind getrennte Artefakte; diese Schicht
baut keine native Runtime.

## Lizenz-Eligibility und Runtime-Kompatibilitaet

Lizenzberechtigung und technische Lauffaehigkeit sind zwei getrennte Guards,
die beide bestehen muessen:

1. **Lizenz-Guard** (nur kommerzielle Kroko-Produkte): Der Server injiziert
   dem Manager eine lesende `license_policy`. Ein Pro-Modell ist in
   `_eligible`/`candidate_eligible` genau dann zulaessig, wenn fuer die UUID
   der tatsaechlich vorliegenden `.data`-Datei (gelesen aus dem Dateiheader)
   ein frischer modellgebundener Nachweis (`VALID`, TTL-begrenzt) besteht und
   kein nur per Neustart loesbarer nativer Konflikt vorliegt. Den Pfad dieser
   Datei loest der Manager selbst auf (`locate_local_path`, dieselben Roots wie
   die Snapshot-Discovery, einschliesslich Engine-`model_dir`/-`model_path`
   und Custom-Paths); Vorpruefung und Admission koennen dadurch nie
   verschiedene Dateien adressieren. Ohne injizierte Policy gilt das
   Legacy-Verhalten (Variante + Enabled). Die LKG-Wiederherstellung filtert
   entfallene Pro-Rollen heraus, sodass kein abgelaufener Nachweis ein
   Pro-Modell wiederbelebt.
2. **Runtime-Guard** (unveraendert strikt fuer Pro, geoeffnet fuer Community):
   Kommerzielle Modelle verlangen exakt die installierte Variante `pro`.
   Community-Modelle sind auf Free- **und** Pro-Installationen zulaessig –
   die native Lizenzpruefung wird fuer sie nicht konsultiert. Modelle mit
   unbekannter Lizenzklasse behalten den bisherigen strikten Vergleich.

Ein gueltiger Nachweis schaltet die Auswahl frei – auch bei einer
Community-Konfiguration (Key + lokales Pro-Modell); er aktiviert nichts.
Verfügbarkeit, Provisionierung, Load-Probe und die Last-Known-Good-Mechanik
bleiben davon unberührt und können einen Start weiterhin verhindern
(fehlende/beschaedigte Datei, falsche Runtime). Nach einem Hintergrundergebnis
oder einer Force-Aenderung gleicht der Service Snapshot, aktive Zuordnung und
Status ueber den vorhandenen transaktionalen Refresh ab; Kroko-Kandidaten
werden dabei nie neben einer anderen lebenden Kroko-Instanz geprueft (ein
Prozess betreibt hoechstens eine native Kroko-Instanz; ein Wechsel erfolgt im
Leerlauf ueber den regulaeren Entlade-Pfad, bei aktiver Arbeit wird er als
`modelRefreshPending` zurueckgestellt). `GET /api/models/management` enthaelt
den redigierten Lizenzstatus als `krokoLicense` (Scope `model`, keine Secrets)
und `krokoRuntime` (installierte Variante, Berechtigung, gewuenschtes und
tatsaechlich aktives Modell, Neustartbedarf getrennt ausgewiesen; siehe
[Kroko-ONNX](kroko-onnx.md#modell--und-lizenzwechsel-im-laufenden-prozess)).

Die Runtimevariante des Managers wird aus der validierten installierten
Produkt-/Nativeidentitaet aufgeloest (`pro`, Entwicklerbuild `free`, sonst
`unknown`). Die fruehere Konfigurationspraezedenz bis zum Default `free`
gilt dafuer nicht mehr. Ein `runtime_variant`-Wert oder
`VOICESTT_KROKO_VARIANT` ersetzt keine installierte Faehigkeit.
Engine-Optionen werden bei Probe, Worker-
Start, Recovery und Modellwechsel anhand der tatsaechlich aufgeloesten Engine
gewaehlt. Dadurch erhaelt ein Kroko-Fallback nie Faster-Whisper-Optionen und
umgekehrt; bei identischen Engines bleiben die lanespezifischen Optionen
erhalten.

Engine-Konstruktoren erhalten ausschliesslich lokale Pfade. Auch alte
`auto_download_model`-Optionen oder Umgebungsflags koennen keinen versteckten
Faster-Whisper-/Kroko-Download mehr ausloesen.

## Administration

- `GET /api/models/management`: Registry, Readiness, aktive Rollen und
  handlungsrelevante Diagnosen.
- `POST /api/models/refresh`: transaktionaler Discovery-/Recovery-Refresh.
- `GET /health`: `sttReady` und `sttModels` getrennt von Prozess-Liveness.

`PATCH /api/config` mit `stt_auto_download_enabled`, `stt_engine_settings`
oder `stt_model_settings` persistiert nur den neuen Betreiber-Intent und setzt
`modelRefreshRequired`/`refreshRequired`. PATCH laedt oder provisioniert kein
Modell. Erst `POST /api/models/refresh` baut einen Kandidatensnapshot auf. Er
wird nur bei erfolgreichem Load-Probe und Aktivierung uebernommen; bei Fehler,
Busy-Zustand oder Worker-Startfehler bleiben vorheriger Intent im aktiven
Manager, letzter guter Snapshot und Rollenzuordnung erhalten, waehrend der
persistierte neue Intent fuer einen spaeteren Retry ausstehend bleibt.

Ohne nutzbares Modell bleibt der Prozess erreichbar. Konfiguration,
Diagnostik und Recovery koennen daher bedient werden, statt einen
Docker-Restartloop zu erzeugen.
