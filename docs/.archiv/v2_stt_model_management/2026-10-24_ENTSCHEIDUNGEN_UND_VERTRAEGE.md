# Entscheidungen und Verträge

24.10.2026, AP-STTM-010; vor Featureimplementierung.

## Authority und Kompatibilität

Der bisherige STTModelManager bleibt die eine Produkt-/Inventar-/Recoveryautorität.
Bestehende Imports und Mockpatchpunkte bleiben erhalten. Neue leichte Module
unter `voice_stt_server/models/` besitzen nur Jobs bzw. verwaltete Dateitransaktionen;
keine Appimporte, Nativeinitialisierung oder zweite Registry. `refresh_inventory`
prüft ausschließlich den Bestand und erhält effektive Rollen/LKG; `refresh`
bleibt explizite Recovery für bestehende interne Aufrufer, wird jedoch downloadfrei.
Die HTTP-Refreshrouten verwenden ausschließlich Inventory. Expliziter Load und
Modellwechsel behalten Runtime-/Recoveryverantwortung.

## Identitäten

`modelId` bleibt für bestehende manifestierte Produkte die bisherige stabile ID.
Portal-UUID wird als `catalogId` getrennt abgebildet; native Lizenz-ID bleibt
allein beim bestehenden nativen Modellrechteadapter. Katalogprodukte ohne
Manifest erhalten die exakte Portal-UUID als ID, jedoch keinerlei Downloadrecht.
`installationId` bindet Engine, Produkt und normalisierten absoluten lokalen Ort
über SHA-256; Pfade bleiben aus öffentlichen Payloads entfernt. Mehrere Kopien
bleiben getrennt. `jobId` ist eine flüchtige UUID.

## Settings-Transaktion

Zwei skalare neue Registryeinträge `stt.autoDownload.enabled` und
`stt.autoDownload.selectedModelIds` sind server/admin/live. Ihre einzige
Persistenz liegt im bestehenden Control-Overlay und dessen Revision. Die
ServerSettings-Felder sind Laufzeit-/CLI-/YAMLprojektionen. Beim Altformatstart
seedet ein fehlender Overlaywert genau einmal aus den bisherigen Settings;
existierender Overlaywert hat Vorrang. Historische Engine-/Modell-Autoflags
bleiben wirkungslos; keine automatische Übersetzung in eine ID-Auswahl.

Beide HTTP-Schreibpfade benutzen den Settingslock und dieselbe Control-Plane.
Vor RAM-/Revisionscommit schreibt der vorhandene RuntimeConfigStore ein einziges
Dokument atomar mit Legacysettings und Overlay; redundante STT-Skalarwerte werden
aus der Legacysektion entfernt. Legacy-Mischpatches bereiten alle Werte vor;
Persistenzfehler übernehmen keine Werte. Auto-Auswahländerungen planen erst nach
erfolgreichem Commit künftige Jobs. Unveränderte Auswahl wiederholt keine Fehler.

## Jobs, Dateien und Berechtigungen

Eine flüchtige begrenzte Queue mit einem Worker; keine persistente Queue und
kein Resume. Dedupe vereinigt manual/automatic. Nur queued kann storniert werden;
nach Start laufen auch abgewählte Jobs weiter. Herkunft ist eine Menge.
Ein Fehler erzeugt keinen automatischen Retry. Refresh und Downloadabschluss
aktivieren keine Runtime. Events gehen über den bestehenden Hub, Fortschritt
bleibt im Snapshot. Fehler verwenden feste Codes ohne Providertext oder URL.

Alle Schreibziele liegen ausschließlich unter den beiden data_root-Modellroots.
Symlinks, Junctions/Reparsepunkte, Hardlinks und Traversal sind für mutierende
Operationen gesperrt. Löschung erfolgt über bekannte konkrete Installations-ID,
mit Referenzprüfung und denselben Runtime-/Inventarlocks. Konfigurierte,
effektive, ladende, benutzte und durch Jobs referenzierte Produkte sind geschützt.
Ein administrativ exklusiver data_root ist Voraussetzung für Dateimutationen;
keine Garantie gegen einen privilegierten lokalen Prozess, der Locks und
Dateisystemberechtigungen umgehen kann.

Faster-Whisper: versionierte MIT-Snapshots von Systran, SHA-256 und Bytecount je
Datei. LFS-Hash aus revisionsgebundenen Metadaten, kleine Dateien zusätzlich
selbst gehasht; keine Modelldownloads zur Manifestgewinnung. Runtime führt keine
Metadatenabfrage aus. HTTP nur HTTPS, Redirectprüfung vor Kontakt, ausschließlich
deklarierte Hugging-Face/CDN-Hosts, keine fremden Credentials. Vollständiges
Verzeichnis wird erst nach jeder Dateiprüfung atomar sichtbar.
Kroko: bestehende Rechte-/Integritätsgates bleiben unverändert gesperrt.

## Status und WebSocket

Neue Routen entsprechen dem Auftrag. Öffentliche Status-/Inventarprojektionen
verwenden explizite Feldlisten; keine Pfade, freie Diagnosen, Quell-URLs oder
Secrets. Status ist eine Projektion der bestehenden Autoritäten.

V1: WebSockettransport früh annehmen, vorhandene `status`-Nachricht mit
angenommen/Ladezustand vor jeder teuren Sessionarbeit senden, Admission und
Reload in Workerthread, begrenzte Wartezeit und Statuskeepalive. Erst nach
wirklichem Load `ready`; Fehler erhalten feste Codes. V2-Schema bleibt bytegleich.
V2-Admission wird aus dem Event Loop genommen; `hello.accepted` bestätigt die
Session und niemals Modellreadiness. Ein bestehender Snapshotrequest bleibt
auch bei entladenem Modell möglich, Inferenz lädt im vorhandenen Worker nach.
Neue allgemeine HTTP-Statusprojektion ergänzt, ersetzt aber keine frühe
WebSocketannahme. Verpflichtende externe Clientänderungen werden separat beauftragt.
