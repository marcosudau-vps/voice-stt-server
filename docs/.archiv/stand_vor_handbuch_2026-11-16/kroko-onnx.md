# Kroko-ONNX in der V2-Distribution

`kroko_onnx` ist die zweite unterstützte Produktions-Engine. Das V2-Produkt sieht eine Pro-fähige native Kroko-Laufzeit im gemeinsamen Serverpaket vor. Das bedeutet nicht, dass ein Pro-Modell ohne Lizenz genutzt werden dürfte. Die Enginefähigkeit ergibt sich aus dem installierten Binärpaket; die Berechtigung für ein konkretes Modell wird gesondert geprüft.

## Community, Pro und Modelle

Community-Modelle kommen ohne Pro-Key aus. Für lizenzpflichtige Modelle ist ein gültiger, passender Kroko-Key nötig. Ein Key allein stellt weder das Modell bereit noch macht er aus einer inkompatiblen Runtime eine geeignete Installation. Modelle selbst sind nicht Bestandteil der geplanten öffentlichen Serverdistribution. Ihr Speicherort und ihre Bereitstellung werden separat konfiguriert.

Der Lizenz-Check einer laufenden Installation ist außerdem **keine automatische Freigabe zur Weiterverbreitung** der eingebetteten Binärdateien. Für den öffentlichen Releaseprozess gelten deshalb die Hinweise und Nachweise unter [Lizenzierung](licenses.md#unified-v2-release-gate).

Weiterführend: [Engine-Abläufe](v2-handbuch/02-funktionsweise/02.06-engines.md), [Kroko-Lizenzierung](v2-handbuch/05-administration/05.07-kroko-lizenzierung.md), [Native Guard](v2-handbuch/05-administration/05.08-native-guard.md), [Modelle](v2-handbuch/02-funktionsweise/02.07-modelle-und-modellverwaltung.md) und [Engine-Referenz](v2-handbuch/08-referenzen/08.08-engine-referenz.md). Native Build- und Distributionsnachweise stehen unter [build/BUILD.md](../build/BUILD.md).
