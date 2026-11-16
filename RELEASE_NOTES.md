# Voice-STT-Server – Versionshistorie

Diese Versionsübersicht beschreibt die veröffentlichten und geplanten VoiceSTT-Produktstände. Die maßgebliche technische V2-Beschreibung ist das [Handbuch](docs/v2-handbuch/README.md).

## Noch nicht veröffentlicht

### Kroko-Laufzeitgrenzen

Die interne native Kroko-Verwaltung wurde darauf begrenzt, in einer laufenden Serverinstanz nicht mehrere konkurrierende Kroko-Modelle gleichzeitig vorzuhalten. Werden für Final- und Realtime-Erkennung verschiedene native Kroko-Modelle verlangt, wird die Kombination abgelehnt, statt unbemerkt mehrere native Kontexte zu erzeugen. Ein Pro-Modellwechsel kann einen Neustart erfordern; das beobachtbare Laufzeitverhalten wird im Modellstatus ausgewiesen.

Diese Arbeiten liegen auf dem Entwicklungszweig und sind noch kein veröffentlichtes Paket.

## 2.0.0 – Release in Vorbereitung

### Produktumfang

VoiceSTT bündelt in V2 eine Python-Bibliothek mit einem eigenständig betreibbaren FastAPI-Server. Die vorgesehene Distribution heißt `voice-stt-server`; sie stellt das Importpaket `voice_stt_server` sowie den Programmstart `voice-stt-server` bereit. Die unterstützten Zielsysteme der nativen Distributionspakete sind **CPython 3.12 auf Windows x86-64 und Linux x86-64**. Die historische Produktstruktur mit mehreren öffentlich getrennten Kroko-Varianten wird auf **ein** Paket zusammengeführt.

Im öffentlichen Produktionsumfang sind **Faster-Whisper** und **Kroko-ONNX** vorgesehen. Frühere Engine-Prototypen sind keine durch V2 zugesagten Backends. Eine gültige Kroko-Pro-Berechtigung erlaubt die Nutzung der entsprechend berechtigten Modelle; Community-Modelle kommen ohne Pro-Key aus. Modellgewichte sind nicht im Serverpaket enthalten. Die native Runtimefähigkeit und die Modellnutzungsberechtigung bleiben getrennte Entscheidungen.

### Schnittstellen und Transkriptionsabläufe

- Zustandsbehaftetes WebSocket-Protokoll `/ws/v2` für neue Clients, mit eigenständigen Verbindungs-, Session-, Aktivierungs- und Segmentidentitäten.
- Serverbestätigte Steuerbefehle und Acknowledgements; ein Client soll seine Anzeige nicht allein aus dem Tastendruck oder einem lokalen Countdown ableiten.
- Sitzungsbezogene Audioverarbeitung, Wake-Word- und Manual-Aktivierung mit definiertem Vorrang, Zeitgrenzen und Wiederverbindungsverhalten.
- Getrennte Zuständigkeiten für endgültige und laufende Transkription sowie nachvollziehbare Modellverwaltung.
- Eigene HTTP-Flächen für Status, Administration und Konfiguration; weiterhin vorhandene OpenAI-kompatible HTTP-Route.
- Legacy-V1-Kompatibilitätsoberfläche bleibt separat dokumentiert. V2 ist kein stillschweigendes Alias des V1-Protokolls.

### Konfiguration, Rechte und Beobachtbarkeit

Die V2-Settingsarchitektur unterscheidet Werte nach Scope, Quelle, Validierung und Wirksamkeitszeitpunkt. Der Server trennt die Berechtigungen für administrative Eingriffe, Logs, die OpenAI-kompatible API und die Kroko-Modellberechtigung. Eine strukturierte Ereigniserfassung und persistente Logging-Infrastruktur ermöglichen die Analyse von Sitzungen und Fehlern, ohne darauf angewiesen zu sein, dass der Client beliebige interne Zustände errät.

### Installation und Betrieb

Die endgültigen Produktwheels sollen die native Kroko-Laufzeit enthalten. Ein Endnutzer soll dafür keine Buildtoolchain für Kroko installieren müssen. Die Build- und Installationsqualifikation achtet auf CPU-only-Torch in den vorgesehenen Installationspfaden; unter Linux kann ein unvorbereiteter allgemeiner `pip install`-Aufruf andere Torch-Abhängigkeiten auflösen, weshalb die gesondert dokumentierte CPU-Installation maßgeblich ist. Für Container wird ein Linux/AMD64-Image mit überprüfbaren Paket- und OCI-Identitäten vorbereitet.

### Releaseautomation und Qualitätssicherung

Der Server verfügt über getrennte GitHub-Workflows für gewöhnliche CI, die nicht veröffentlichende Herstellung eines qualifizierten Release Candidate und den späteren kontrollierten Publish. Kandidaten binden Source-Commit, Tree, Plattformwheels und Image-Digest. Die Veröffentlichung überprüft externe Artefaktidentitäten und erzeugt den öffentlichen GitHub-Releaseeintrag erst nach erfolgreichen vorgelagerten Schritten. Rechte-, Modell- und Release-Gates dürfen weder durch einen grünen Unit-Test noch durch ein erfolgreiches Wheel-Packaging automatisch übersprungen werden.

### Neue Dokumentation

Das bisherige Entwicklungs- und Referenzmaterial wird durch ein umfassendes, aus Code und Tests abgeleitetes [V2-Handbuch](docs/v2-handbuch/README.md) ergänzt. Es enthält 104 Kapitel, technische Kataloge, Betriebsanleitungen und Diagramme. Seine unabhängige Dokumentationsabnahme gilt für den geprüften Codecommit `a8993c5c68042d996eab680d84a5b138a214bb5d`; spätere technische Änderungen erfordern einen Abgleich.

### Wichtige Einschränkungen vor Veröffentlichung

- Version 2.0.0 ist derzeit **noch nicht veröffentlicht**. Im Entwicklungsbranch vorhandene Features sind kein öffentliches Releaseversprechen.
- Die finale Modell-/Native-Qualifikation mit den exakten Paketen und das gebündelte Redistribution-Gate müssen vor dem Publish abgeschlossen werden.
- Die neue Dokumentation ersetzt nicht den separaten End-to-End-Test von Server und V2-Windows-Client.
- V2 unterstützt nicht beliebige Python- oder CPU-Architekturen.

## 1.0.0 – Vorheriger veröffentlichter Projektstand

Version 1.0.0 ist der vorangehende öffentliche VoiceSTT-Veröffentlichungsstand. Die unveränderten Tags und GitHub-Releaseartefakte dokumentieren dessen genauen Inhalt. Der V1-Protokollvertrag bleibt für Bestandsclients separat beschrieben und wird durch das V2-WebSocket-Protokoll nicht rückwirkend ersetzt.

Historische Veröffentlichungen sind über die unveränderten Git-Tags nachvollziehbar. Verbindliche Copyright- und Lizenztexte stehen in der Original-Lizenzdatei.

## Technische Referenzen

- [V2-Handbuch](docs/v2-handbuch/README.md)
- [Release- und Publish-Verfahren](docs/v2-handbuch/ressourcen/release-process.md)
- [Paketierung und Native-Build](build/BUILD.md)
- [Lizenzstatus und Mitlieferpflichten](docs/v2-handbuch/ressourcen/licenses.md)
- [V1/V2-Abgrenzung](docs/v2-handbuch/09-anhaenge/09.03-v1-v2-unterschiede.md)
