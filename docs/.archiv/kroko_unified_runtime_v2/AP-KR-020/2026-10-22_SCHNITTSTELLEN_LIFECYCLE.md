# AP-KR-020 – Lizenzschnittstelle und Lifecycle-Grenze

22.10.2026. **BLOCKED: kein qualifizierter Lizenzvalidierungsvertrag.**
Diese Datei dokumentiert Arbeitsschritt A und Anforderungen an die Fortsetzung;
sie beschreibt keine implementierte öffentliche API.
Die AP-010-Abnahme ist bestätigt und kein offenes Gate mehr.

## Gezielte Quellenprüfung

Unveränderter lokaler Kroko-Checkout auf
`8657e655192623b98d7708e742a72987f953d3a2`, `git status --porcelain` und
`git diff --exit-code` sauber. Dies entspricht der Authority in
`VoiceSTT/kroko/buildinputs.py`; kein Upstreamwechsel.
AP-010-Nativeexperimente werden nicht wiederholt oder als neue Tests gezählt.

| Originalquelle auf diesem Commit | SHA-256 des kanonischen Gitblobs (LF) |
| --- | --- |
| `sherpa-onnx/csrc/license.h` | `68f23b22e449e14fdc6c82cecdf640a9ab18b88bca422c192e0fca5e5172458c` |
| `sherpa-onnx/csrc/online-transducer-model.cc` | `a697cc9048dcc361da5c85de342a63c903eea7b3d464044c6cbd74c6f3731040` |
| `sherpa-onnx/csrc/ModelData.h` | `4aa2d94a710c6748e88092ec37d01c42af4c9aeee16c7debd159eaeb0a19b292` |
| `sherpa-onnx/python/csrc/sherpa-onnx.cc` | `071b4ae2a917f3479f57966726744a2425cdc56408b2a467d90aadb82bc39f80` |

Reproduzierbar mit Checkout dieses Commits, `git status --porcelain` und
SHA-256 der byteweisen Ausgabe von `git show HEAD:<pfad>` je Datei.
Der gelesene Windowscheckout hat CRLF; die obigen Digests binden ausdrücklich
die unveränderten Gitblobs und sind deshalb plattformunabhängig.
Die Dateiidentitäten sind Quellnachweise, keine
Nativebuild-Fingerprints und keine Lizenznachweise. VoiceSTTs vorhandener
Quiet-Patch wurde separat gelesen; er umhüllt Ausgaben, ergänzt keine
Status-/Validierungsfunktion.

Primärquellen:

- [Lizenzclient](https://github.com/kroko-ai/kroko-onnx/blob/8657e655192623b98d7708e742a72987f953d3a2/sherpa-onnx/csrc/license.h)
- [Modellaktivierung und Reporter](https://github.com/kroko-ai/kroko-onnx/blob/8657e655192623b98d7708e742a72987f953d3a2/sherpa-onnx/csrc/online-transducer-model.cc)
- [Pythonregistrierung](https://github.com/kroko-ai/kroko-onnx/blob/8657e655192623b98d7708e742a72987f953d3a2/sherpa-onnx/python/csrc/sherpa-onnx.cc)
- [Anbieterdokumentation](https://docs.kroko.ai/on-premise/), am 22.10.2026
  gelesen: beschreibt Modellstart mit Key, Lizenzkontakt und Nutzungsmeldung;
  benennt modellbezogene Fehler. Liefert keinen separaten versionierten
  Pythonvalidierungsvertrag, keine strukturierte Entitlementabbildung und
  keine dokumentierte Aktualitätsgarantie für einen exportierten Snapshot.

## 1. Vorhandene unterstützte Schnittstelle

**CODEANALYSE: für den vollständigen geforderten Vertrag nicht vorhanden.**
Pythonbindings und C-API wurden auf Lizenz-/Entitlementexporte untersucht.
Die vorhandenen `validate()`-Methoden prüfen Konfigurationen. Der dokumentierte
Pythonpfad konstruiert einen Recognizer mit Modellpfad und optionalem Key.
Eine weitere vom Anbieter bereitgestellte Schnittstelle ist in den geprüften
Quellen nicht nachgewiesen; damit wird keine weltweite Nichtexistenz behauptet.
Die zusätzlich gefundene [Hosted-API-Authentifizierung](https://docs.kroko.ai/api/)
bezieht sich auf den gehosteten STT-Dienst. Ein dortiger Handshake belegt keine
Berechtigung für lokale Pro-Modelle und wird nicht als Lizenzprobe verwendet.

`BanafoLoadModel`, Zeilen 95–136, ruft `BanafoLicense::getInstance` ausschließlich
für einen Header mit `free=false` auf und nimmt die Lizenzmodell-ID aus dessen
`id`. Für Community wird sogar `license_status=true` gesetzt, ohne Lizenzkontakt.
Auch dieser interne Status ist deshalb kein Pro-Nachweis.

Der Client baut seine Anfrage mit Key **und Modell-ID** auf (`license.h:148–152`).
Der Key allein liefert hier keine modellunabhängige Aussage. `allowed` ist ein
internes Antwortfeld und kein öffentlicher Nachweis für alle Pro-Modelle.
Das Servermanifest enthält Produkt-IDs und Integritätsdaten, jedoch keine
vom Lizenzanbieter bestätigte Zuordnung seiner Featurefelder zu diesen IDs.

## 2. Minimale native Status-/Validierungsergänzung

**Technisch denkbar, aber als robuste Integration nicht nachgewiesen.**
Es fehlt keine pauschale Erlaubnis zur Untersuchung oder zur minimalen
Ergänzung: der Auftrag erlaubt diese ausdrücklich. Eine reine
pybind11-Exportfunktion wäre technisch möglich. Sie löst aber die folgenden
semantischen und synchronisationsbezogenen Probleme nicht:

1. `BanafoLicense::mActivated` wird nach dem ersten Aktivierungswarten einmalig
   aus `client.allowed` kopiert (`license.h:253–257`). Es ist kein laufender
   Widerrufssnapshot. Ein Export dieses Werts würde alte Freigaben fortschreiben.
2. `LicenseClient.allowed`, `is_finish`, Zeitfelder und Featureliste sind
   gewöhnliche mutable Felder. Netzwerkthread, Konstruktor und Reporter greifen
   ohne einen gemeinsamen Snapshotlock darauf zu. Ein zusätzlicher Pythonleser
   schafft keine atomare, generationgebundene Statussicht.
3. Die erste Antwort setzt `allowed` vor dem weiteren Parsing. Fehlende
   Zeit-/Featurefelder erhalten Defaults; Parsefehler werden ausgegeben, ohne
   einen strukturierten fehlgeschlagenen Abschluss zu liefern. Diese Zustände
   dürfen nicht unverändert als autoritativer VALID-Snapshot exportiert werden.
4. Ein negatives `allowed` hat lediglich ein frei formuliertes `error`.
   Es gibt keinen typisierten Code für ungültigen Key, Ablauf, Widerruf,
   fehlendes Modellrecht oder technisches Problem. Eine Textklassifikation
   würde den geforderten belastbaren Vertrag nicht schaffen. Eine pauschale
   negative Lizenzklassifikation könnte eine nur modellbezogene Ablehnung
   fälschlich auf den gesamten Key übertragen.
5. `features` ist nur eine Liste beliebiger `name`-/`value`-Strings. Weder
   Whitelist noch Zuordnung zu den Servermodell-IDs sind definiert. Eine
   erfolgreiche Modellaktivierung berechtigt deshalb nur dieses Modell,
   nicht den übrigen Katalog.
6. `expirable` und `expires_at` werden gelesen, aber hier nicht als lokale
   Ablaufgrenze ausgewertet. `last_online_time` wird bei Verbindung und Close
   gesetzt und ist nicht der Zeitpunkt einer bestätigten Lizenzantwort.
   `offline_timeout=0` schaltet die lokale Offlineprüfung aus. Daraus lässt
   sich keine unterstützte allgemeine Snapshotgültigkeitsfrist ableiten.
7. Ein direkter Aufruf von `BanafoLicense::getInstance(key, modelId)` vor dem
   Recognizer könnte Aktivierung ohne Modellladen beginnen. Dafür muss aber
   eine explizite Lizenzmodell-ID gewählt werden; der Singleton bindet diese
   erste ID samt Key. Ohne definierten Vertrag zur Probe-ID, zu späteren
   Modellrechten, Nutzungsreporting und Aktualität ist das kein Ersatz für
   die verlangte modellunabhängige Keyprüfung bei Community-Defaults.

Ein vollständiger sicherer Patch müsste die Zustandsübergänge im bestehenden
Client synchronisieren, Fehler/Antwortschemas verbindlich festlegen,
Aktualität nachweisen und den Reporter-/Aktivierungslebenszyklus für den
Community-only-Fall definieren. Ein Getter oder ein zusätzlicher Exitcode
reicht nicht. Die Quellprüfung allein liefert diese Anbietersemantik nicht.
Es wird keine eigene Ersatzimplementierung des Lizenzprotokolls geschrieben.

**Folge:** Kein nativer Patch und kein neues scheinbar qualifiziertes Payload
in diesem Stand. Patch-/Builderrevisionen und Fingerprints bleiben unverändert.
Nach bestätigtem Vertrag ist eine Erweiterung ausdrücklich zu versionieren,
in `PATCHED_UPSTREAM_SOURCES`/Patchrevision und Guards aufzunehmen und mit
neuen plattformspezifischen Fingerprints/Artefakthashes zu qualifizieren.

## 3. Isolierte kurzlebige Prüfgeneration

**Für diesen Vertrag nicht geeignet nachgewiesen.**

| Prüfprozess | Aussage / fehlende Eigenschaft |
| --- | --- |
| Import oder Community-Modell mit Pro-Payload | Kein Lizenzkontakt; kein positiver Lizenznachweis. |
| Berechtigtes Pro-Modell laden, Erfolg strukturiert melden | Könnte nach realer Qualifikation einen Erfolg für genau diese Modellaktivierung belegen. Dafür fehlen hier autorisierte Testumgebung und ein unabhängiger Aktualitäts-/Übertragungsvertrag. |
| Pro-Laden beendet Prozess mit Exit 1 | Modellheader, Entschlüsselung, Lizenzablehnung und Offlinefehler sind anhand des Exits nicht eindeutig unterscheidbar. CHECK_FAILED, keine erfundene INVALID-Klassifikation. |
| Timeout beim Laden | Aufsicht könnte Prozess abbrechen; das belegt Technikfehler, keine ungültige Lizenz. |
| Probe beenden und neuen Community-/Pro-Besitzer starten | Die bestätigte Lizenzverbindung und ihr Reporter sterben mit dem Probeprozess. Eine alte Bestätigung ist kein aktueller Nachweis für den neuen Besitzerprozess. Erneute Aktivierungs-/Kontingentsemantik ist nicht bestätigt. |

Den Pro-Prüfprozess als dauerhaften Besitzer zu übernehmen ist ein anderer
Ansatz als eine kurzlebige Probe. Dafür müsste dessen Pro-Modell ausdrücklich
zur gewünschten Konfiguration gehören. Ein Community-Default darf nicht durch
ein verborgenes Pro-Prüfmodell ersetzt oder mit einem unbelegten zweiten
Recognizer im Singleton kombiniert werden. AP-010s Mehrfachladungsgrenze gilt.

## Ergebnis und konkret fehlender Eingang

**A ist nicht abgeschlossen.** Es gibt keinen implementierten belastbaren
Mechanismus für Key → Validierung → aktuelle Pro-/Modellfreigabe ohne
verdeckten Modellwechsel. Das ist ein technischer Schnittstellenblocker,
keine erneut fehlende AP-010-Abnahme und kein Beweis prinzipieller Unmöglichkeit.

Benötigt wird entweder ein unterstützter modellunabhängiger Validierungsvertrag
oder ein bestätigter Vertrag für explizite modellbezogene Prüfungen ohne
Änderung der gewünschten Community-Konfiguration, mit:

- Identität/Scope der Berechtigung und Zuordnung zu Modell-IDs;
- strukturierten Ablehnungsgründen einschließlich Ablauf/Widerruf;
- bestätigtem Antwortschema sowie Gültigkeits-/Aktualitäts-/Reportingregeln;
- Definition der Prozess-/Aktivierungsbindung und erlaubter Wiederholungen.

Eine unterstützte schmale Bindingergänzung dieses Vertrags bleibt der bevorzugte
nächste technische Schritt. Zusätzlich ist eine ausdrücklich autorisierte
Lizenztestumgebung mit erlaubten Fällen und Aktivierungsgrenzen nötig. Deren
Fehlen allein würde nur die Qualifikation auf CONDITIONAL begrenzen; es ist
nicht der alleinige Grund dieses Schnittstellenblockers. Keine Secretwerte
in Tickets, Dokumentation, Status oder Testausgaben übermitteln.

## Weiter geltender Lifecycle-Sollvertrag (nicht implementiert)

`pro_enabled = api_key_present and not force_community and license_validation_successful`.
Kein Key/Force bedeutet NOT_CHECKED, keine Pro-Initialisierung/-Prüfung.
Unbelegbare Prüfung bedeutet CHECK_FAILED und keine Pro-Freigabe.

Der spätere Snapshot bindet Status an Konfigurationsgeneration, opake
Credentialrevision, Pro-Komponentenidentität, bestätigte Modellrechte,
Aktualität und lebenden Besitzerprozess. Key-/Modus-/Komponenten-/Rechtewechsel
invalidiert atomar; alte Readiness-/Jobergebnisse bleiben ungültig.
Keine persistenten `pro_enabled`-/`active_engine`-Werte.

Supervisor ohne native Imports, genau eine Besitzerprozessgeneration,
Startupfrist, begrenztes Retry/Backoff, kontrolliertes Stoppen und bestätigter
Exit vor Fallback/Neustart; Readiness erst nach Initialisierung. Alle CLI-,
Modul-, Container- und Legacyeinstiege müssen diese Grenze verwenden.
Kurze Dienstunterbrechung ist bereits freigegeben. V2-Reconnect, Terminal- und
Segmentverträge bleiben bestehen. Keine Behauptung einer hier implementierten
oder getesteten Supervisor-/Sessionintegration.
