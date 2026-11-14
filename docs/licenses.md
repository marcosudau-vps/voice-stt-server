# Lizenzen, Herkunft und Freigabegrenzen

Die Lizenzübersicht unterscheidet **Quellcode**, **ausgelieferte Binärdateien** und **Modelldateien beziehungsweise Pro-Berechtigungen**. Diese drei Dinge dürfen nicht zu einer einzigen Aussage über „die Kroko-Lizenz“ zusammengezogen werden. Die rechtlich verbindlichen Bedingungen stehen in den jeweiligen Original-Lizenztexten und den Verträgen für die konkret verbreiteten Komponenten.

## Herkunft des Projekts

VoiceSTT entstand unter Weiterverwendung von RealtimeSTT-Bestandteilen. Der ursprüngliche Urhebervermerk von **Kolja Beigel (2023)** und der MIT-Lizenztext bleiben in der Repository-Datei [LICENSE](../LICENSE) **unverändert** erhalten. Eine Änderung der Paketautor-Angabe in `setup.py` ersetzt und entfernt diesen Copyright- und Weiterverwendungshinweis nicht.

Der Repository-Lizenztext gilt nicht automatisch für jedes Modell, jede übertragene Audiodatei oder jede native Abhängigkeit. Bei Builds sind zusätzlich die mitgelieferten Drittanbieter-Lizenzdateien maßgeblich. Ein vollständiger Prüfdurchlauf muss die tatsächlich gebauten Artefakte untersuchen und die Notices im jeweiligen Paket erhalten.

## Unified V2 release gate

Das V2-Produkt `voice-stt-server` soll auf Windows und Linux jeweils als eine vollständige Distribution bereitstehen. Es enthält die native, Pro-fähige Kroko-Laufzeit, **nicht aber die Kroko-Modellgewichte oder den privaten API-Key**. Nutzer können Community-Modelle ohne Pro-Key verwenden; für Pro-Modelle wird ihre modellbezogene Berechtigung technisch validiert. Der Server darf deshalb nicht allein aus einem vorhandenen Key ableiten, dass ein Binärartefakt neu verteilt werden darf.

Der verbindliche, maschinenlesbare Status befindet sich in [build/kroko-redistribution.json](../build/kroko-redistribution.json). Der dortige Status **`BLOCKED`** betrifft die **öffentliche Weiterverbreitung der gesamten gebündelten Pro-fähigen Distribution**. Er ist **nicht** das Ergebnis der bereits implementierten Pro-Key-Prüfung. Der [Releaseprozess](release-process.md) darf diesen Status ausschließlich aufgrund einer dokumentierten Rechtebewertung und der vollständigen Paketnachweise auf `VERIFIED` umstellen, nicht aufgrund erfolgreicher Funktionstests.

### Worauf die Rechteprüfung sich bezieht

| Gegenstand | Technischer Stand | Für die Veröffentlichung prüfen |
| --- | --- | --- |
| VoiceSTT-Quellcode mit RealtimeSTT-Herkunft | MIT-Lizenz im Root, ursprünglicher Copyright-Hinweis unverändert | MIT-Pflichten bei Weitergabe sämtlicher relevanter Bestandteile |
| Kroko-Enginequellen | Das gepinnte `kroko-onnx`-Quellprojekt verwendet Apache 2.0 | Einhaltung der Apache-Bedingungen, Notices, ggf. Verträge für das **konkret gebaute** Pro-fähige Binärpaket |
| Native Bibliotheken, Windows/Linux-Abhängigkeiten | Gehören zu den geprüften Kroko-Buildinputs | Alle tatsächlich enthaltenen Drittkomponenten, NOTICE-/Lizenzdateien und etwaige zusätzliche Binär-/Redistributionsbedingungen |
| Kroko-Community-Modelle | Werden separat provisioniert | Modellbezogene Bedingungen einschließlich Attribution/Share-Alike nach dem jeweiligen Angebot |
| Kroko-Pro-Modelle | Erfordern eine gültige, passende Berechtigung | Separate kommerzielle oder OEM-Modellnutzungsrechte; keine Weiterverteilung von Modellgewichten ohne entsprechende Erlaubnis |
| Faster-Whisper und übrige Laufzeitpakete | Unterstützte Engine bzw. transitive Python-/Native-Abhängigkeiten | MIT-/sonstige Notices der tatsächlich installierten Versionen |
| Wake-Word-/VAD-Modelle | Eigene technische Artefakte | Die jeweils zum konkreten Modell gehörenden Nutzungs- und Verbreitungsregeln |

### Belegquellen im Repository

Der reproduzierbare Kroko-Build bindet Drittquellen, Lizenztexte und SHA-256-Einträge über [VoiceSTT/assets/kroko/licenses/sources.json](../VoiceSTT/assets/kroko/licenses/sources.json) ein. Die zugehörigen Notice-Dateien liegen unter `VoiceSTT/assets/kroko/licenses/`. Der [Buildprozess](../build/BUILD.md) und der [Releaseprozess](release-process.md) beschreiben die Prüfung der Paketmetadaten und der Auslieferungsartefakte. Historische Resultate der Linux-/Windows-Qualifikation bleiben im [Kroko-Abschlussarchiv](.archiv/kroko_v2_finalization/2026-10-27_NACHTRAG_FINALE_QUALIFIKATION.md) abrufbar; sie ersetzen keine Bewertung neuer finaler Buildartefakte.

### Upstream-Lizenzdokumente

- [RealtimeSTT (Ursprung und MIT-Bedingungen)](https://github.com/KoljaB/RealtimeSTT)
- [Kroko-ONNX – gepinnte Quellenlizenz](https://github.com/kroko-ai/kroko-onnx/blob/8657e655192623b98d7708e742a72987f953d3a2/LICENSE)
- [Kroko – On-Premise-/Modellberechtigungen](https://docs.kroko.ai/on-premise)
- [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper)
- [ONNX Runtime](https://github.com/microsoft/onnxruntime)

**Geltungsgrenze:** Diese redaktionell neu verfasste Projektseite ist eine Orientierung und kein Ersatz für die Originalbedingungen. Weder die technische Keyvalidierung noch das Vorliegen eines Apache-/MIT-Texts beweisen ohne Abhängigkeitsinventar eine vollständige Freigabe der tatsächlich ausgelieferten Binärdateien. Das Release-Gate bleibt bis zu einem dokumentierten Nachweis unverändert.
