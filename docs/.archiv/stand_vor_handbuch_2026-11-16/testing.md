# Qualitätssicherung und Teststrategie

Bei der Entwicklung des Voice-STT-Servers sind automatisierte Prüfungen auf mehreren Ebenen vorgesehen. Das V2-Protokoll wird unabhängig von realer Mikrofonhardware gegen definierte Zustände und Fehlermeldungen geprüft. Für die Veröffentlichung reichen diese isolierten Tests allerdings nicht aus: Ein vollständiges Paket muss auch nach frischer Installation, auf den unterstützten Zielsystemen und mit den tatsächlich vorgesehenen Modellen funktionieren.

## Was ein Testergebnis bedeutet

Unit- und Contract-Tests bestätigen jeweils implementierte Regeln innerhalb ihrer Testgrenzen. Packaging-Tests kontrollieren installierte Dateien, Metadaten und Imports. Für native Komponenten sind echte Betriebssystem- und Modelltests erforderlich. Eine übersprungene Pflichtprüfung muss in der Schlussabnahme als `NOT_RUN` sichtbar bleiben; aus einem synthetischen Test darf kein reales Modell-`PASS` entstehen.

Die [Testarchitektur](v2-handbuch/07-entwicklung/07.05-testarchitektur.md) nennt die Ebenen, die [Testverfahren](v2-handbuch/07-entwicklung/07.06-testverfahren.md) ihre praktische Durchführung. [CI](v2-handbuch/07-entwicklung/07.09-ci.md), [Release Candidate](v2-handbuch/07-entwicklung/07.10-release-candidate.md) und [Veröffentlichung](v2-handbuch/07-entwicklung/07.11-veroeffentlichung.md) beschreiben den Weg bis zu einem überprüften Release.
