# Installation von Voice-STT-Server V2

Die installierbare Produktdistribution heißt `voice-stt-server`. Ihr V2-Paket enthält die benötigte native Kroko-Laufzeit; ein Benutzer soll dafür keine separate C++-Buildumgebung installieren müssen. Die öffentlich geplanten Wheels sind für CPython 3.12 auf Linux x86-64 und Windows x86-64 ausgelegt. Der produktive Containerbetrieb ist als Linux/AMD64-Variante vorgesehen.

**Stand dieser Dokumentationsrevision:** Das geplante öffentliche 2.0.0-Release ist noch nicht freigegeben. Beispielbefehle dürfen daher nicht als bereits vorhandene PyPI- oder Registry-Artefakte verstanden werden. Der Installationsweg richtet sich nach den tatsächlich verfügbaren und geprüften Paketen.

## Prüfreihenfolge

Vor einer Inbetriebnahme werden Zielplattform, Python-Version, Abhängigkeiten, Modelle und Datenverzeichnis geprüft. Nach der Installation sind Paketidentität und Start-/Readiness-Verhalten zu kontrollieren. Ein fehlendes Modell ist von einem fehlenden oder falsch paketierten nativen Runtimebestandteil zu unterscheiden.

Die konkrete Anleitung ist nach Zielsystem getrennt: [Windows](v2-handbuch/06-betrieb/06.03-windows-installation.md), [Linux](v2-handbuch/06-betrieb/06.04-linux-installation.md), [Docker](v2-handbuch/06-betrieb/06.05-docker-betrieb.md). Die [Ersteinrichtung](v2-handbuch/06-betrieb/06.06-ersteinrichtung.md) und der [Serverstart](v2-handbuch/06-betrieb/06.07-serverstart-stopp.md) ergänzen die Installation; Entwickler finden den Paketaufbau unter [Packaging](v2-handbuch/07-entwicklung/07.07-packaging.md).
