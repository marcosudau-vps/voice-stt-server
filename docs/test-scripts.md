# Testbefehle und Qualifikationsstufen

Ein grüner Unit-Test belegt nur die geprüften Bedingungen. Für Voice-STT-Server V2 werden Vertragsprüfungen, Packaging-Kontrollen und reale Laufzeitszenarien getrennt bewertet. Insbesondere künstliche Modellfixtures können die Struktur eines Wheels beweisen, aber keine native Modellinferenz.

## Prüfpfade

Für einen sauberen, eingerichteten Entwickler-Checkout stehen die Testpakete unter `tests/unit`, `tests/compatibility` und `tests/packaging`. Der gewöhnliche Aufruf über `python -m pytest` benötigt die in der Entwicklungsumgebung definierten Abhängigkeiten. Release-Candidate-Prüfungen werden dagegen auf gebauten Wheels und OCI-Artefakten ausgeführt und dürfen nicht ungeprüft durch Tests aus dem Quellcheckout ersetzt werden.

Die systematische Einordnung findet sich in der [Testarchitektur](v2-handbuch/07-entwicklung/07.05-testarchitektur.md), im [Testverfahren](v2-handbuch/07-entwicklung/07.06-testverfahren.md), der [CI](v2-handbuch/07-entwicklung/07.09-ci.md) und der [RC-Qualifikation](v2-handbuch/07-entwicklung/07.10-release-candidate.md). Konkrete Release-Befehle und Gates beschreibt [release-process.md](release-process.md).
