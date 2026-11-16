# Faster-Whisper im Voice-STT-Server V2

`faster_whisper` gehört zu den zwei ausdrücklich unterstützten Produktions-Engines. Es verwendet die Whisper-Modellfamilie über CTranslate2. Die Wahl eines Modells und die tatsächlich bereitstehenden Ressourcen beeinflussen Startverhalten, Speichernutzung und Verarbeitungsgeschwindigkeit. In isolierten oder produktiven Umgebungen sollten Modelldateien vorab provisioniert werden, statt einen automatischen Download vorauszusetzen.

## Einsatz und Betriebsgrenzen

Faster-Whisper kann für endgültige Transkription verwendet werden. Ob zusätzlich ein Realtime-Ergebnis erzeugt wird, hängt von der konkreten Engine-Konfiguration und den zugehörigen Ablaufgrenzen ab. Es sollte nicht angenommen werden, dass ein Zwischenstand die Qualität oder Identität eines abgeschlossenen Segments besitzt.

Das V2-Paket unterstützt aktuell CPython 3.12 auf den qualifizierten x86-64-Zielplattformen. Die veröffentlichten Produktwheels und ihre CPU-only-Abhängigkeiten müssen als Einheit betrachtet werden; insbesondere unter Linux ist die dokumentierte CPU-Torch-Installation wichtig.

Ausführliche Hinweise: [Engines und Rollen](v2-handbuch/02-funktionsweise/02.06-engines.md), [Transcription](v2-handbuch/02-funktionsweise/02.05-transcription.md), [Engine-Referenz](v2-handbuch/08-referenzen/08.08-engine-referenz.md), [Modellverwaltung](v2-handbuch/02-funktionsweise/02.07-modelle-und-modellverwaltung.md) und [Systemvoraussetzungen](v2-handbuch/06-betrieb/06.01-systemvoraussetzungen.md).
