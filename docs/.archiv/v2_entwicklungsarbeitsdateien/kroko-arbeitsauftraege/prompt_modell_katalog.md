# Voice-STT-Server V2 – Kroko-Modellkatalog vorbereiten

## Ziel

Implementiere die technische Grundlage für einen dynamischen Kroko-Modellkatalog mit strukturierter Modellerkennung, Filterung, Validierung und Vorbereitung einer späteren automatischen Modellinstallation.

Dieser Auftrag ist eine unabhängige Vorarbeit zum laufenden Unified-Kroko-Umbau. Er darf sofort umgesetzt werden, auch wenn AP-KR-020 wegen des noch unvollständigen Lizenz- und Entitlementvertrags blockiert ist.

Die Arbeit soll produktiv nutzbare, getestete Komponenten liefern – nicht nur einen Untersuchungsbericht.

## Repository und Branch

Repository:
`P:\GithubRepos\marcosudau-vps\voice-stt-server`

GitHub:
<https://github.com/marcosudau-vps/voice-stt-server>

Ausgangsbranch:
`feat/v2-unified-kroko`

Eigener Arbeitsbranch:
`feat/v2-unified-kroko-catalog`

Zielbranch des späteren Pull Requests:
`feat/v2-unified-kroko`

Der bestehende AP-020-Branch `feat/v2-unified-kroko-ap020` und Draft-PR #12 dürfen nicht verändert werden.

Erstelle bei Bedarf einen separaten Git-Worktree. Keine vorhandenen lokalen Änderungen überschreiben oder löschen.

## Vorhandene Quelldaten

Im lokalen Verzeichnis

`P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\kroko-umbau`

liegen:

- `kroko-models.json` – ursprüngliche Webportal-Antwort
- `model-katalog.json` – bereinigter Modellkatalog
- `model-katalog.csv` – bereinigte CSV-Fassung
- `kroko_catalog_probe.py` – bisheriges Experimentalskript

Die Ausgangs-JSON wurde aus folgendem beobachteten Kroko-Endpunkt gewonnen:

`GET https://app.kroko.ai/api/v1/limiter/on-premise/licenses`

Die bereinigten Daten enthalten 124 Modelle:

- 105 Pro-Modelle
- 19 Community-Modelle
- 12 unterschiedliche Sprachcodes

Alle 124 Dateinamen konnten bereits anhand eines einheitlichen Namensschemas zerlegt werden.

WICHTIG: Die ursprüngliche JSON kann Lizenzschlüssel, Modellpasswörter und weitere sensible Daten enthalten. Diese Datei niemals committen, in Artefakte kopieren oder vollständig loggen.

Bevorzuge die bereinigte JSON als Entwicklungsgrundlage.

## Arbeit 1 – Bestehende Modellarchitektur untersuchen

Lies zuerst:

- `AGENTS.md`
- `VoiceSTT/kroko/models.py`
- `VoiceSTT/assets/kroko/models.json`
- `docs/stt-model-management.md`
- `docs/kroko-onnx.md`
- die relevanten Kroko-Architekturunterlagen unter `docs/.archiv/kroko_unified_runtime_v2/`

Untersuche die bestehenden Manifest-, Modellintegritäts-, Download- und Provisionierungsverträge.

Ziel ist eine kompatible Erweiterung, keine parallele konkurrierende Modellverwaltung.

Die bisherigen zwölf manifestierten Kroko-Modelle und ihre Integritätsangaben dürfen nicht stillschweigend ersetzt oder aufgeweicht werden.

## Arbeit 2 – Modellkatalog-Modul

Implementiere ein eigenständiges Modul:

`VoiceSTT/kroko/catalog.py`

Es soll die bereinigten Kroko-Modellmetadaten laden, typisiert validieren und normalisieren.

Erforderliche Eigenschaften:

- Exakte Kroko-Modell-ID
- Modellname
- Sprachcode
- Edition: Community / Pro
- Chunk-Wert
- Modellgröße: M / L / weitere tatsächlich vorkommende Größen
- Streaming-Kennzeichnung
- Modellrevision
- Download-URL
- Optional vorhandene weitere ungefährliche Metadaten

Der Parser muss die Originalwerte vollständig erhalten.

Sprachcodes wie `IW` nicht eigenmächtig umbenennen.

Unbekannte oder neue Modellnamensvarianten dürfen nicht stillschweigend falsch interpretiert werden. Verwende eine klare Validierung mit nachvollziehbaren Diagnosemeldungen.

Doppelte Modell-IDs, widersprüchliche Metadaten und widersprüchliche Download-URLs erkennen.

API und Datenobjekte sauber typisieren.

## Arbeit 3 – Katalogfilterung und Modellwahl

Implementiere wiederverwendbare Filterfunktionen für:

- Sprache
- Community / Pro
- Chunk-Wert
- Modellgröße
- Streaming-Fähigkeit
- Kombinationen dieser Kriterien

Ermögliche eine deterministische Sortierung, etwa Sprache → Edition → Chunk → Größe → Revision.

Die Filterung darf keine Lizenzberechtigung implizieren.

Die tatsächliche Pro-Modellfreigabe bleibt weiterhin Aufgabe der serverseitigen Lizenzautorität aus AP-KR-020.

## Arbeit 4 – Sichere Downloadvorbereitung

Implementiere eine Schnittstelle, die für einen ausgewählten Katalogeintrag einen Downloadplan erstellt.

Ein Downloadplan soll mindestens enthalten:

- Kanonische Modell-ID
- Erwarteten Modellnamen
- Downloadquelle
- Vorgeschlagenen lokalen Dateinamen
- Vorhandenen oder fehlenden Integritätsnachweis
- Aussage, ob das Modell nach den bisherigen Manifestregeln automatisch installiert werden dürfte

Unterscheide strikt zwischen:

1. Modell ist im Katalog sichtbar.
2. Download-URL ist vorhanden.
3. Download ist technisch zugänglich.
4. Downloadintegrität ist verifiziert.
5. Modell darf gemäß Produkt- und Lizenzregeln installiert bzw. aktiviert werden.

Eine bekannte URL darf niemals automatisch einen vertrauenswürdigen Download begründen.

Beachte die vorhandenen Schutzmechanismen gegen Pfadmanipulation, unsichere Redirects, unerlaubte Hosts und ungeprüfte Modellbytes.

Wenn ein Katalogeintrag keinen verifizierten Hash oder keine andere bestehende autoritative Integritätsbindung besitzt, darf der Plan nicht behaupten, dass eine vollständige sichere automatische Provisionierung möglich sei.

Keine Änderung am bestehenden vertrauenswürdigen Modellmanifest ohne explizite fachliche Grundlage.

## Arbeit 5 – Diagnose-CLI

Erstelle ein kleines Kommandozeilenwerkzeug:

`tools/kroko_catalog_cli.py`

Das Werkzeug soll den Katalog offline einlesen und folgende Funktionen anbieten:

- Katalogzusammenfassung
- Liste aller Sprachen
- Filterung nach Edition, Sprache, Chunk und Modellgröße
- Detailansicht eines Modells
- Downloadplan ohne tatsächlichen Download
- Prüfung auf Inkonsistenzen und unbekannte Namensmuster

Beispielhafte Bedienung:

`python tools/kroko_catalog_cli.py --catalog <DATEI> list --language DE --edition Pro`

`python tools/kroko_catalog_cli.py --catalog <DATEI> inspect --model-id <MODELL_ID>`

Die genaue CLI-Syntax darf entsprechend den bestehenden Projektkonventionen umgesetzt werden. Dokumentiere die tatsächlich implementierten Befehle.

Keine Zugangsdaten und keine Lizenzserveranfragen erforderlich.

## Arbeit 6 – Automatisierte Tests

Erstelle:

`tests/unit/test_kroko_catalog.py`

Teste insbesondere:

- Korrekte Auswertung der bereitgestellten 124 Modelleinträge.
- Erkennung sämtlicher vorhandener Sprachcodes.
- Korrekte Extraktion von Edition, Chunk, Größe und Revision.
- Deterministische Filterung und Sortierung.
- Ungültige Dateinamen.
- Fehlende Pflichtfelder.
- Duplikate und ID-Konflikte.
- Ungültige oder unerlaubte Download-URLs.
- Sichere Behandlung von Pfadmanipulationen.
- Fehlende Integritätsinformationen.
- Keine Ausgabe von Lizenzschlüsseln oder Modellpasswörtern.
- Keine Veränderung bestehender Manifest- oder Modellrechte.

Erstelle zusätzlich kleine synthetische Testfixtures ohne Secrets.

Lasse die bestehenden relevanten Unit-, Contract- und Modellmanagementtests laufen.

Reale externe Downloads oder Lizenzserverkontakte sind nicht Bestandteil dieses Auftrags.

## Arbeit 7 – Architektur für spätere Live-Katalogaktualisierung vorbereiten

Untersuche die bekannten Endpunkte:

`https://app.kroko.ai/api/v1/limiter/on-premise/models`

`https://app.kroko.ai/api/v1/limiter/on-premise/licenses`

Berücksichtige folgende Erkenntnisse:

- Die Webportal-API liefert nachgewiesen strukturierte Lizenz- und Modellinformationen.
- Die Webportal-Authentifizierung ist nicht mit dem On-Premise-Lizenzschlüssel gleichzusetzen.
- Ein direkter WebSocket-Lizenztest mit Key und Modell-ID war bereits erfolgreich.
- Eine vom Webportal unabhängige Katalogauthentifizierung ist noch nicht nachgewiesen.

Entwirf eine kleine optionale Datenquellen-Abstraktion, falls sich diese sinnvoll in die konkrete Implementierung einfügt.

Der funktionierende Offline-Katalog darf nicht von einem Live-Endpoint abhängen.

Keine Implementierung eines Browser-Logins, keine Verwendung von Sessioncookies, keine Tokengewinnung durch nachgebildete Webanmeldungen.

Keine spekulative produktive Nutzung undokumentierter Endpunkte.

Dokumentiere, wie später eine tatsächlich verifizierte Onlinequelle ergänzt werden könnte.

## Verbindliche Grenzen

- Kein Eingriff in AP-KR-020.
- Kein eigenständiger Merge.
- Kein Release oder Deployment.
- Keine Änderungen an Lizenzierungs- oder nativen Kroko-Binaries.
- Kein eigenmächtiger Ausbau des bestehenden Pro-Freischaltmechanismus.
- Keine Änderungen am V2-Protokoll.
- Keine ungeprüften Modelldownloads.
- Keine sensitiven Daten in Git, Logs, Testreports oder CI-Artefakten.
- Keine Verwechslung von Katalogverfügbarkeit und Modellberechtigung.

## Dokumentation und Abschluss

Dokumentiere die Umsetzung unter:

`docs/.archiv/kroko_unified_runtime_v2/CATALOG/`

Erstelle dort:

- `2026-10-22_KONZEPT.md`
- `2026-10-22_IMPLEMENTIERUNG.md`
- `2026-10-22_TEST_EVIDENZ.md`
- `2026-10-22_OFFENE_PUNKTE.md`

Pflege die bestehende fachliche Dokumentation, sofern tatsächlich implementierte Funktionen beschrieben werden.

Erstelle nach erfolgreicher Umsetzung einen Pull Request gegen:

`feat/v2-unified-kroko`

Titelvorschlag:

`feat(kroko): vorbereiteter dynamischer Modellkatalog`

Der PR soll ausdrücklich als unabhängige Vorarbeit gekennzeichnet sein.

Abschlussbericht mit:

- Implementierten Komponenten
- Relevanten Designentscheidungen
- Testergebnissen
- Commit-SHA
- PR-Link
- Offenen Voraussetzungen für Online-Katalog und Auto-Download

**Beginne jetzt mit der Umsetzung.** Der offene Lizenzvertrag ist für diesen abgegrenzten Auftrag kein Startblocker. Keine zusätzlichen Freigabefragen für die oben genannten Arbeiten stellen.
