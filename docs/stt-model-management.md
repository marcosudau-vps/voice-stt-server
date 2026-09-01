# STT-Modellverwaltung

VoiceSTT verwaltet grosse STT-Modelle fuer Faster-Whisper und Kroko ueber eine
gemeinsame serverautoritative Schicht. Wake-Word-Assets gehoeren nicht zu
diesem System.

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

Kroko-Pro-Modelle bleiben bei fehlender Pro-Runtime oder Lizenzvoraussetzung
diagnostisch sichtbar, koennen aber nicht aktiv werden. Der Lizenzschluessel
wird weder in Modellmetadaten noch Status, Logs oder Speicher geschrieben.
Native Kroko-Runtimes und ASR-Modelle sind getrennte Artefakte; diese Schicht
baut keine native Runtime.

Engine-Konstruktoren erhalten ausschliesslich lokale Pfade. Auch alte
`auto_download_model`-Optionen oder Umgebungsflags koennen keinen versteckten
Faster-Whisper-/Kroko-Download mehr ausloesen.

## Administration

- `GET /api/models/management`: Registry, Readiness, aktive Rollen und
  handlungsrelevante Diagnosen.
- `POST /api/models/refresh`: transaktionaler Discovery-/Recovery-Refresh.
- `GET /health`: `sttReady` und `sttModels` getrennt von Prozess-Liveness.

Ohne nutzbares Modell bleibt der Prozess erreichbar. Konfiguration,
Diagnostik und Recovery koennen daher bedient werden, statt einen
Docker-Restartloop zu erzeugen.
