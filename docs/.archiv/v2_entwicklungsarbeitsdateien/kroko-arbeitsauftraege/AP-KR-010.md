# AP-KR-010 – Technische Machbarkeit: Unified Kroko Runtime V2

## Auftrag

Untersuche und verifiziere die technische Machbarkeit einer gemeinsamen Voice-STT-Server-V2-Distribution, die Kroko Community standardmäßig enthält und Kroko Pro optional nachinstallierbar macht.

Erarbeite die belastbare technische Entscheidungsgrundlage für zwei nachfolgende Arbeitspakete:

- AP-KR-020: Runtime- und Lizenzintegration
- AP-KR-030: Packaging, Release und Gesamtqualifikation

Dieses Arbeitspaket ist eine Untersuchung, keine produktive Implementierung.

## Repository und Arbeitsbasis

Repository:

`https://github.com/marcosudau-vps/voice-stt-server`

Geschützter V2-Zielbranch:
feat/einheitliche-triggerarchitektur-distributed

Integrationsbranch:
feat/v2-unified-kroko

Arbeitsbranch für AP-KR-010:
feat/v2-unified-kroko-ap010

PR-Ziel für AP-KR-010:
feat/v2-unified-kroko

Vorgehen:

1. Den exakten zuletzt abgenommenen V2-Commit feststellen.
2. Sicherstellen, dass der Integrationsbranch von diesem
   Commit abzweigt.
3. Den AP-010-Arbeitsbranch vom Integrationsbranch erstellen.
4. AP-010 ausschließlich auf dem Arbeitsbranch durchführen.
5. Einen PR gegen den Integrationsbranch erstellen.
6. Nicht eigenständig mergen.

Für AP-020 und AP-030 wird jeweils vom dann aktuellen,
zuvor abgenommenen Integrationsstand abgezweigt.

Der geschützte V2-Zielbranch darf während der drei
Arbeitspakete nicht verändert werden.

Nach der unabhängigen Gesamtqualifikation wird der
Integrationsbranch über einen abschließenden PR per
Squash-Merge in den V2-Zielbranch übernommen.

Kein direkter Push auf den V2-Zielbranch.
Kein Merge ohne ausdrückliche Benutzerfreigabe.

Prüfe vor Beginn, ob der Ausgangsbranch den aktuellen qualifizierten V2-Stand enthält. Dokumentiere Ausgangscommit, Arbeitsbaumzustand und eventuell erkannte Abweichungen. Arbeite auf einem eigenen Branch.

Lies zuerst:

- AGENTS.md
- docs/.archiv/README.md
- build/BUILD.md
- docs/release-process.md
- docs/testing.md
- README.md

Untersuche anschließend mindestens:

- setup.py
- tools/build_distribution.py
- tools/build_production.py
- tools/release_candidate.py
- release_tooling/
- .github/workflows/
- VoiceSTT/install_kroko.py
- VoiceSTT/kroko/
- VoiceSTT/transcription_engines/kroko_onnx_engine.py
- VoiceSTT/transcription_engines/model_resolver.py
- VoiceSTT/assets/kroko/models.json
- tests/

Untersuche weitere betroffene Komponenten nach Bedarf, insbesondere Initialisierung, Modellmanager, Settings-Control-Plane, Serverstart und Client-seitige Modellverfügbarkeit.

## Verbindliche Zielarchitektur

Die bestehenden Kroko-Builds bleiben grundsätzlich erhalten:

Community:
KROKO_LICENSE=OFF

- Community-Modelle nutzbar
- Kein API-Key notwendig

Pro:
KROKO_LICENSE=ON

- Community- und Pro-Modelle nutzbar
- API-Key erforderlich

Zur Laufzeit darf nur eine Kroko-Runtime aktiv sein.

Die Engine-Auswahl ist abgeleitet:

pro_enabled =
    api_key_present
    AND NOT force_community
    AND license_validation_successful

Wenn pro_enabled wahr ist:

- Pro-Runtime verwenden
- Community- und berechtigte Pro-Modelle anbieten

Andernfalls:

- Community-Runtime verwenden
- Nur Community-Modelle anbieten

Die aktive Engine und pro_enabled dürfen keine redundanten persistenten Zustandsvariablen werden.

Bei fehlendem API-Key oder erzwungener Community wird keine Pro-Runtime initialisiert und keine Lizenzprüfung ausgeführt.

Bei vorhandenem Key und nicht erzwungener Community wird die Pro-Initialisierung einschließlich Lizenzprüfung versucht. Schlägt sie fehl, wird kontrolliert auf Community zurückgefallen.

Die Lizenzprüfung benötigt einen eigenen Status mit mindestens NOT_CHECKED, CHECKING, VALID, INVALID und CHECK_FAILED.

Ein erfolgreiches Importieren der Pro-Bibliothek ist kein ausreichender Beleg für eine gültige Pro-Lizenz.

Key-Änderungen, Lizenzverlust und Änderungen des Community-Modus müssen die aktuelle Freigabe korrekt invalidieren.

Der Status ist serverweit relevant und darf nicht mit dem sitzungslokalen Admin-Unlock verwechselt werden.

Der bestehende Runtime-Key-Vertrag, insbesondere KROKO_API_KEY, soll erhalten bleiben.

## Untersuchungsblock A – Native Runtime-Isolation

Untersuche die tatsächlichen Free- und Pro-Wheels einschließlich:

- Python-Modulnamen
- nativer Erweiterungen
- dynamischer Bibliotheken
- Importreihenfolge
- Initialisierungsverhalten
- Entlade- und Wechselmöglichkeiten
- Installations- und Dateikollisionen

Teste soweit technisch möglich:

1. Community allein starten.
2. Pro allein starten.
3. Beide Builds getrennt auf derselben Maschine bereitstellen.
4. Beim Prozessstart genau eine Variante auswählen.
5. Fehlgeschlagene Pro-Initialisierung sicher abfangen.
6. Anschließend Community verfügbar machen.
7. Erneut von Community zu Pro wechseln.

Unterscheide ausdrücklich zwischen:

- beiden Varianten installiert,
- beiden Varianten in einem Prozess importiert,
- beiden Varianten tatsächlich initialisiert.

Bewerte:

- getrennte Runtime-Verzeichnisse,
- kontrollierte Importpfade,
- separate Python-Umgebungen,
- Neustart des betroffenen Prozesses,
- weitere technisch begründete Alternativen.

Bevorzuge die kleinste robuste Lösung. Vermeide neue permanente Worker-Prozesse und Änderungen an Kroko-Upstream, sofern nicht erforderlich.

Untersuche Linux AMD64 und Windows AMD64 sowie CPython 3.12. Nicht lokal ausführbare Plattformtests klar kennzeichnen.

## Untersuchungsblock B – Lizenzvalidierung

Ermittle anhand des tatsächlich verwendeten Kroko-Builds, wann und wie der Lizenzschlüssel geprüft wird.

Klärungsfragen:

- Wird bereits beim Pro-Import validiert?
- Erfolgt die Prüfung erst beim Recognizer-Aufbau?
- Erfordert eine zuverlässige Prüfung ein Pro-Modell?
- Kann ein Community-Modell unter Pro trotz ungültigen Keys starten?
- Existiert eine getrennte Validierungsschnittstelle?
- Welche Fehler liefern ungültige, abgelaufene oder nicht erreichbare Lizenzen?
- Wie kann späterer Lizenzverlust festgestellt werden?
- Wie werden unterschiedliche Pro-Modellberechtigungen erkannt?

Verwende echte positive und negative Tests nur bei vorhandener autorisierter Testumgebung. Keine Zugangsdaten beschaffen, erfinden, verändern, ausgeben oder committen.

Unterscheide echte Integrationstests von Mocks und Quellcodeanalysen. Kann ohne gültigen Key oder Pro-Modell keine positive Prüfung stattfinden, dokumentiere dies als offene Voraussetzung.

Entwerfe einen eindeutigen Lizenzstatusvertrag mit sicheren Zustandsübergängen und Invalidation bei Key-Änderung.

## Untersuchungsblock C – Modell- und Serverintegration

Ermittle alle Stellen, an denen bisher die installierte Free-/Pro-Distribution zur Laufzeit vorausgesetzt wird.

Prüfe insbesondere:

- Modellkompatibilität und Modellmanifest
- Modellauflösung und Modellinstallation
- auswählbare und aktuell aktive Modelle
- serverseitige Modellvalidierung
- Settings-Control-Plane
- Key-Konfiguration und Secret-Verwaltung
- laufende Transkriptionssessions
- Initialisierung und Neustart
- Client-V2-Protokollkompatibilität

Die Pro-Runtime muss Community-Modelle unterstützen, ohne die bestehenden Modellintegritäts- und Sicherheitsprüfungen abzuschwächen.

Beschreibe die erforderlichen Änderungen, implementiere sie aber noch nicht.

## Untersuchungsblock D – Packaging und Release

Untersuche, wie aus zwei vollständigen Server-Distributionen eine gemeinsame Distribution werden kann.

Gewünschte Bedienung:

pip install voice-stt-server

Optional:

pip install "voice-stt-server[kroko_pro]"

Verifiziere, ob die optionale Pro-Erweiterung als getrennte Distribution realisierbar ist und wie die nativen Dateikollisionen vermieden werden können.

Bewerte bei Bedarf Alternativen. Ein Python-Extra allein gilt nicht als Nachweis funktionierender nativer Runtime-Isolation.

Die Endanwender sollen keine native Kroko-Kompilierung durchführen müssen.

Untersuche die Auswirkungen auf:

- Wheels und Paketmetadaten
- Abhängigkeiten und Extras
- CPython-/Plattform-Tags
- Docker-Images
- Build-Fingerprints und SHA-256
- Provenienz und Runtime-Identität
- Release-Candidate-Manifeste
- GitHub Actions
- Publish-/Resume-/Rollback-Mechanismen
- Dokumentation und Versionierung

Die bestehende Reproduzierbarkeit und Veröffentlichung exakt qualifizierter Artefakte darf nicht geschwächt werden.

Prüfe auch notwendige Lizenz- und Redistributionsbedingungen für eine separate Pro-Komponente.

## Dokumentation und Ablage

Registriere vor den Experimenten die neue Änderungsaktion gemäß AGENTS.md und docs/.archiv/README.md.

Verwende als festen Aktionsordner:

docs/.archiv/kroko_unified_runtime_v2/

Verwende für AP 1:

docs/.archiv/kroko_unified_runtime_v2/AP-KR-010/

Alle Dokumentdateien bekommen den vorgeschriebenen Datumspräfix ihres tatsächlichen Erstellungstages.

Erstelle mindestens:

- Gesamtplanung der Änderungsaktion
- Untersuchungsmatrix mit Testmethodik
- Technischen Ergebnisbericht mit Evidenz
- Bewertete und begründete Architekturentscheidung
- Risikoliste und offene Voraussetzungen
- Konkrete Übergabe an AP-KR-020 und AP-KR-030

Die Gesamtplanung muss bereits vor der eigentlichen produktiven Umsetzung vorliegen. Erkenntnisse aus AP 1 dürfen durch datierte Planergänzungen aufgenommen werden.

Lege experimentelle Skripte und Fixtures getrennt von Produktionscode ab. Keine Secrets, Modelle, nativen Binärdateien, produktiven Logs oder Buildartefakte committen.

## Abnahmekriterien

AP-KR-010 ist erfolgreich, wenn:

1. Die reale native Free-/Pro-Koexistenz und Auswahl nachvollziehbar untersucht wurde.
2. Der Lizenzprüfungsmechanismus und seine Nachweisgrenzen beschrieben sind.
3. Ein zuverlässiger Fallback- und Wechselansatz bestimmt ist.
4. Die Server- und Modellintegration vollständig eingegrenzt wurde.
5. Ein realisierbarer Packaging-Ansatz mit konkreten Abhängigkeiten vorliegt.
6. Die Auswirkungen auf Release/CI nachvollziehbar erfasst sind.
7. AP-KR-020 und AP-KR-030 ohne erneute Grundlagenuntersuchung planbar sind.

Trenne eindeutig:
VERIFIZIERT / CODEANALYSE / SIMULIERT / OFFEN.

Führe geeignete vorhandene Unit- und Contract-Tests aus und dokumentiere deren Ergebnisse.

## Grenzen

- Keine produktive Runtime-Implementierung.
- Kein produktiver Packaging-Umbau.
- Keine Änderungen am öffentlichen Client-V2-Protokoll.
- Keine Änderung am V2-Transkriptionsverhalten.
- Keine unautorisierte Änderung am VPS oder am laufenden Dienst.
- Keine öffentlichen Releases, Deployments oder Registry-Pushes.
- Keine Änderung historischer Abnahmebelege.
- Kein Merge ohne ausdrückliche Freigabe.

Erstelle zum Abschluss einen Pull Request gegen den angegebenen Zielbranch.

## Abschlussbericht

Gib im Chat abschließend strukturiert aus:

1. Status: GO / CONDITIONAL GO / NO-GO
2. Ausgangscommit und Arbeitsbranch
3. Zentrale verifizierte Ergebnisse
4. Empfohlene native Runtime-Strategie
5. Empfohlene Lizenzvalidierung
6. Empfohlene optionale Pro-Paketierung
7. Offene Blocker und Testeinschränkungen
8. Dateiliste der erstellten Nachweise
9. Tatsächlich durchgeführte Tests
10. PR-Link und Commit-ID

Nenne ausdrücklich, welche Voraussetzungen vor AP-KR-020 noch fehlen.

Beende die Arbeit nach Übergabe zur unabhängigen Prüfung. Beginne AP-KR-020 nicht eigenständig.
