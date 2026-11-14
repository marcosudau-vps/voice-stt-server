# Konfiguration des Voice-STT-Servers

Der Server verarbeitet Konfiguration aus mehreren Quellen. Die wirksame Bedeutung eines Wertes hängt nicht nur von seinem Namen ab, sondern ebenso von seinem Geltungsbereich und dem Zeitpunkt, zu dem er angewandt wird. Deshalb ist zwischen serverweiten Einstellungen, Einstellungen pro Verbindung beziehungsweise Sitzung und temporären Laufzeitänderungen zu unterscheiden.

## Wake-Word-Parameter im V2-Vertrag

Die serverseitige Wake-Auswertung verfügt unter anderem über `wakeWord.minConsecutivePredictionFrames`, `wakeWord.detectorGain`, `wakeWord.noiseSuppressionEnabled`, `wakeWord.vadThreshold` und `wakeWord.inferenceBackend`. Diese Parameter werden nicht als voneinander unabhängige lokale Schalter ausgelegt: Verfügbarkeit und wirksame Werte müssen vom Server bestätigt werden. Ein Client sollte angeforderte, wirksame und voreingestellte Werte nicht gleichsetzen.

Für den genauen Vorrang der Quellen, zulässige Typen und Validierung siehe [Konfigurationsarchitektur](v2-handbuch/03-konfiguration/03.01-konfigurationsarchitektur.md), [Quellen und Prioritäten](v2-handbuch/03-konfiguration/03.05-quellen-und-prioritaeten.md), [Session-Einstellungen](v2-handbuch/03-konfiguration/03.07-session-einstellungen.md) und den vollständigen [Settings-Katalog](v2-handbuch/08-referenzen/08.03-settings-katalog.md). Beispiele stehen im [Konfigurationskapitel](v2-handbuch/03-konfiguration/03.13-konfigurationsbeispiele.md).
