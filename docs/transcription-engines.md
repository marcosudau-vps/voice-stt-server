# Unterstützte Transkriptions-Engines

Die V2-Produktoberfläche unterstützt **genau zwei** auswählbare Transkriptions-Engines:

| Konfigurationsname | Aufgabe | Dokumentation |
| --- | --- | --- |
| `faster_whisper` | Whisper-basierte Transkription, häufig für fertige Textsegmente eingesetzt | [Faster-Whisper](faster-whisper.md) |
| `kroko_onnx` | Kroko-Modellerkennung für konfigurierte Transkriptionsaufgaben | [Kroko-ONNX](kroko-onnx.md) |

Andere in früheren Entwicklungsständen vorhandene oder diskutierte Adapter sind **internal and experimental**, also **not part of the supported production surface**. Ihre bloße Existenz in historischen Plänen oder isolierten Entwurfsdateien begründet keine verfügbare V2-Engine. Veraltete Aliase dürfen nicht als normale unterstützte Namen beschrieben werden.

## Auswahl und Modellrechte

Die gültigen Enginekennungen und tatsächlichen Konfigurationsfelder ergeben sich aus dem aktuellen Paket und seinem Settingsvertrag. Insbesondere bei Kroko sind installierte native Fähigkeit, Modelldatei und gegebenenfalls Pro-Lizenzberechtigung drei getrennte Voraussetzungen. Änderungen im laufenden Betrieb können abgelehnt werden, wenn das vorhandene native Modell nicht sicher ersetzt werden kann.

Die vollständige technische Darstellung steht in [Engines](v2-handbuch/02-funktionsweise/02.06-engines.md), [Modellverwaltung](v2-handbuch/02-funktionsweise/02.07-modelle-und-modellverwaltung.md), [Engine-Referenz](v2-handbuch/08-referenzen/08.08-engine-referenz.md) und im [Modellkatalog](v2-handbuch/08-referenzen/08.07-modell-katalog-referenz.md).
