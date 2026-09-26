# V1 – Gebündelte Standard-Wakewords

> Status: Gesamtplanung vor Umsetzung
> Stand: 2026-09-23

## Ausgangslage

VoiceSTT Server 1.0.0 löst OpenWakeWord-Modelle offline über einen externen
Modellstamm oder explizite Pfade auf. Das V1-Wheel und das Docker-Image
enthalten bislang keine Wakeword-Modelle. Im V2-Entwicklungszweig existieren
bereits ein manifestbasierter Bundleaufbau, reproduzierbare Modellartefakte
und Paketierungs-/Integritätstests.

## Ziel

- fünf ausgewählte, nichtkommerziell verwendete OpenWakeWord-Klassifikatoren
  zusammen mit den benötigten ONNX-Pipeline-Modellen in Wheel und Docker-Image
  ausliefern;
- `hey_jarvis` als funktionsfähigen eingebauten Default bereitstellen;
- externe Modellordner und explizite Modellpfade weiterhin zusätzlich
  unterstützen;
- Herkunft, Prüfsummen und CC-BY-NC-SA-4.0-Hinweise dokumentieren;
- die bestehende V1-API und die logischen Wakeword-IDs unverändert lassen.

## Ausgewählte Modelle

1. `hey_jarvis`
2. `alexa`
3. `hey_mycroft`
4. `hey_rhasspy`
5. `computer`

Für V1 wird nur der bereits verwendete ONNX-Pfad gebündelt. Externe
TFLite-Modelle bleiben weiterhin konfigurierbar.

## Umsetzung

1. Die ausgewählten, bereits im V2-Zweig inventarisierten Artefakte sowie
   `melspectrogram.onnx` und `embedding_model.onnx` übernehmen.
2. Ein kleines V1-kompatibles `models.json` mit Herkunft, Größe und SHA-256
   pflegen.
3. `OpenWakeWordCatalog` so erweitern, dass Bundle und externe Quellen
   zusammengeführt werden; explizite externe Einträge erhalten bei gleicher
   ID Vorrang.
4. Paketdaten ausschließlich manifestbasiert aufnehmen und durch Tests gegen
   fehlende beziehungsweise nicht deklarierte Artefakte absichern.
5. Generic-Config auf die logische ID `hey_jarvis` statt einen externen
   Dateinamen ausrichten. Explizite VPS-Konfigurationen bleiben unangetastet.
6. Anwender-, Wakeword-, Lizenz-, Build- und Release-Dokumentation anpassen.

## Risiken und Grenzen

- Die mitgelieferten vortrainierten OpenWakeWord-Modelle sind laut Upstream
  CC BY-NC-SA 4.0 und daher nur für den hier ausdrücklich nichtkommerziellen
  Release vorgesehen.
- Modellbytes und Manifest müssen exakt übereinstimmen.
- Der vorhandene externe Pfad darf nicht durch den Bundle-Fallback verdrängt
  werden.
- Die aktuelle produktive VPS-Instanz wird nicht verändert.

## Abnahme

- Katalogtests für Bundle, externe Ergänzungen, Vorrang und Pipeline-Fallback;
- Paket-/Wheel-Inhalt und Prüfsummen testen;
- relevante Wakeword-, Server- und V1-Releaseworkflowtests;
- vollständige Servertestsuite;
- Free- und Pro-Wheel-/Docker-Gates auf Windows und Linux;
- realer `hey_jarvis`-Test mit dem gemeinsam freizugebenden Client.
