# Kroko-Modellkatalog

`VoiceSTT.kroko.catalog` liest bereinigte Kroko-Metadaten vollständig offline.
Es erweitert weder die serverseitige Produktautorität noch Modellrechte.
Die [STT-Modellverwaltung](stt-model-management.md) bleibt für Discovery,
Validierung und Provisioning zuständig. Das bestehende Manifest
`VoiceSTT/assets/kroko/models.json` enthält weiterhin zwölf Modelle.

## Datenvertrag

`load_catalog(path)` akzeptiert UTF-8/UTF-8-BOM-JSON bis 4 MiB im Format
`{"schema": "kroko-catalog-probe-v1", "models": [...]}`. Optional ist ausschließlich
die Notiz `Catalog only; NOT a license/entitlement proof` zulässig.
`KrokoCatalog.from_payload(payload)` bietet dieselbe semantische Validierung.

Pflichtfelder eines Modells: `model_id` (exakte kanonische Portal-UUID),
`name`, `language`, `edition`, `chunk` (Integer), `size`, `mode`, `revision`
(String einschließlich führender Nullen). Alle Werte müssen zum vollständigen
Dateinamen passen:

```text
Kroko-LANGUAGE-Community|Pro-CHUNK-S|M|L-Streaming-NNN.data
```

Sprachcodes bestehen aus 2–5 ASCII-Großbuchstaben; keine Aliasumwandlung,
insbesondere IW bleibt IW. Chunk ist eine positive Zahl mit 1–6 Stellen;
Revision hat drei Ziffern. Neue Größen oder Modi benötigen eine bewusste
Parsererweiterung und erzeugen bis dahin `unknown_name`. Die bisher gelieferten
124 Modelle haben Größen S/M/L, Revisionen 001/002 und ausschließlich Streaming.

Optionale Felder sind `download_url` (öffentliche erlaubte URL oder null),
`source` (ausschließlich `offline-file` oder null) und `parse_ok` (true oder null).
Freigegebene Originalwerte bleiben unverändert, fehlende optionale Felder
werden als null dargestellt. `CatalogEntry.streaming` ist abgeleitet.
Objekte sind unveränderlich. Unbekannte Felder, Schema-/Namensvarianten,
JSON-Doppelfelder, ID-Duplikate und widersprüchliche IDs/Namen/URLs werden
abgelehnt. Es wird kein teilweise gültiger Katalog zurückgegeben.

`CatalogValidationError.diagnostics` enthält Index (null für die Wurzel),
stabilen Fehlercode und Erklärung ohne Rohwerte, Pfade oder URLs. Mehrere
fehlerhafte Zeilen werden gemeinsam gemeldet. Lizenz-/Portalrohantworten
werden nicht angenommen und nicht in Datenobjekten behalten. Beliebige
zusätzliche Metadaten müssen vor einer künftigen Freigabe geprüft werden.

## Auswahl

```python
from VoiceSTT.kroko.catalog import load_catalog, create_download_plan

catalog = load_catalog("model-katalog.json")
entries = catalog.filter(language="DE", edition="Pro", chunk=16,
                         size="M", streaming=True)
plan = create_download_plan(entries[0])
```

Alle Filter sind optional und kombinierbar. Originalschreibweisen werden
exakt verglichen. `catalog.get(model_id)` sucht ausschließlich die exakte
Portal-UUID. `catalog.languages` und `catalog.summary()` liefern Übersichten.
Die Sortierung ist Sprache, Edition (Community vor Pro), numerischer Chunk,
Größe S/M/L, numerische Revision, Originalrevision, Name, Portal-ID. Sie gilt
auch für Filterergebnisse und ist unabhängig von der Eingabereihenfolge.
Keine Auswahl impliziert Lizenzberechtigung.

## Offline-CLI

Aus dem Repository mit Python 3.12; keine Zusatzabhängigkeiten für diese CLI:

```powershell
python tools/kroko_catalog_cli.py --catalog <DATEI> summary
python tools/kroko_catalog_cli.py --catalog <DATEI> languages
python tools/kroko_catalog_cli.py --catalog <DATEI> list --language DE --edition Pro --chunk 16 --size M --streaming yes
python tools/kroko_catalog_cli.py --catalog <DATEI> inspect --model-id <PORTAL_UUID>
python tools/kroko_catalog_cli.py --catalog <DATEI> plan --model-id <PORTAL_UUID>
python tools/kroko_catalog_cli.py --catalog <DATEI> validate
```

Alle Resultate sind JSON. Exitcodes: 0 Erfolg, 1 Modell-ID unbekannt,
2 Validierungs-/Eingabe-/Manifestfehler. `validate` prüft dieselben Invarianten
wie alle übrigen Befehle. Bei Fehlern stehen sichere Diagnosen auf stderr,
kein partielles Resultat auf stdout. Die bereinigte Entwicklerdatei muss
explizit übergeben werden; das Testfixture ist keine produktive Standardquelle.

## Downloadplan und Vertrauensgrenzen

`create_download_plan(entry)` liest bei Bedarf ausschließlich das lokale
Manifest. `model_id` bleibt die exakte kanonische Kroko-Portal-ID;
`manifest_model_id` ist gegebenenfalls die getrennte bisherige Produkt-ID.
Ein Manifestabgleich erfolgt über den exakten, pfadlosen Dateinamen und
prüft Sprache, Edition und Runtimevariante. Kataloghashes werden nicht akzeptiert.

| Feld | Bedeutung |
| --- | --- |
| `catalog_visible` | Validierter Katalogeintrag vorhanden |
| `catalog_source` | Original-Download-URL aus dem Katalog, gegebenenfalls null |
| `download_source` / `download_url_present` | Geplante Quelle und deren Vorhandensein |
| `technical_access` | Immer `not_checked`; keine HEAD-/GET-Anfrage |
| `expected_name` / `local_filename` | Exakter validierter Dateiname ohne Verzeichnisse |
| `integrity_evidence` | `manifest` bei vorhandenem SHA-256/Bytecount, sonst `missing` |
| `expected_sha256` / `expected_bytes` | Nur bestehendes Manifest, sonst null |
| `download_integrity_verified` | Immer false; es wurden keine Modellbytes geprüft |
| `manifest_automatic_install_allowed` | Statische Manifestregeln für Integrität, immutable Quelle und Produktrechte erfüllt |
| `product_license_activation` | Immer `not_checked`; insbesondere keine AP-KR-020-Freigabe |
| `automatic_provisioning_ready` | Immer false; dieser Auftrag provisioniert nicht |
| `blockers` | Stabile Gründe für ausstehende technische, Produkt- und Runtimeprüfungen |

Bei manifestierten Community-Modellen ersetzt eine durch SHA-Revision und
Provenienz gebundene Quelle die veränderliche `main`-Quelle des Katalogs im
Plan. Die Originalquelle bleibt separat erhalten. Ein fehlender Kataloglink
schließt eine vorhandene autoritative Quelle nicht aus. Eine bekannte URL
allein ist niemals Vertrauensbeweis. Aktuell bleibt auch mit Manifesthash
`manifest_automatic_install_allowed=false`, weil Communityrechte
POLICY_REQUIRED und Prorechte PROHIBITED sind. Filterung und Planung ändern
daran nichts. Betreiberabsicht, Runtimefähigkeit und Modellberechtigung
müssen separat durch die vorhandenen bzw. späteren Autoritäten geprüft werden.

Erlaubte URLs: ausschließlich HTTPS, exakte Hosts `download.kroko.ai` mit
`/models/<NAME>` oder `huggingface.co` mit
`/Banafo/Kroko-ASR/resolve/<main|40-stellige SHA>/<NAME>` und optional exakt
`?download=true`. Benutzerinfo, Ports, Fragmente, andere Queries, Prozentkodierung,
Backslashes, Kontrollzeichen und abweichende Dateinamen sind verboten.
Die Planung führt keinerlei Redirect aus. Ein späterer Downloader muss vor
jedem Kontakt Ziel/Redirect prüfen, Hash und Bytecount zwingend validieren
und die bestehenden Sperren, `.part`-Staging-/Atomic-Rename-Regeln verwenden.
Die vorhandene Provisionierung wird durch diesen Plan nicht aufgerufen.

## Spätere Datenquellen

`CatalogSource.load() -> KrokoCatalog` ist eine kleine optionale Protocol-
Schnittstelle; `OfflineCatalogSource` ist die einzige Implementierung.
Ein Onlineadapter muss sichere Metadaten explizit auswählen und anschließend
denselben Validator verwenden. Er benötigt zunächst einen tatsächlich
verifizierten API-, Authentifizierungs- und Aktualisierungsvertrag sowie
Timeout-/Größen-/Redirect-/Credentialgrenzen. Ein letzter guter Offlinekatalog
darf nicht durch einen ungültigen oder teilweise geladenen Snapshot ersetzt werden.

Die beobachteten Portalendpunkte
`https://app.kroko.ai/api/v1/limiter/on-premise/licenses` und
`https://app.kroko.ai/api/v1/limiter/on-premise/models` sind keine hier
implementierten oder zugesicherten Produkt-APIs. Die bereitgestellten
bereinigten Daten belegen strukturierte Informationen aus der licenses-Route.
Ein eigenständiger Katalogauthentifizierungsvertrag und die models-Route
sind nicht verifiziert. Portalauthentifizierung ist nicht der On-Premise-Key;
ein erfolgreicher Key-/Modell-WebSockettest beweist keine Kataloganmeldung.
Es gibt keinen Login-, Cookie-, Sessiontoken- oder Live-Endpunktadapter.

Implementierungs- und Testbelege liegen in der
[Katalogakte](.archiv/kroko_unified_runtime_v2/CATALOG/2026-10-22_IMPLEMENTIERUNG.md).
