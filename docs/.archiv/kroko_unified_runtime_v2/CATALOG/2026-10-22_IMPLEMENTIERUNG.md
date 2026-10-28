# Kroko-Modellkatalog – Implementierung und Soll/Ist

22.10.2026. Unabhängige Vorarbeit; kein Bestandteil von AP-KR-020.
Basis `acdffc7`, eigener Branch `feat/v2-unified-kroko-catalog`.
Die [Planung](2026-10-22_KONZEPT.md) wurde vor der Implementierung registriert.
Maßgeblich sind der PR-Diff dieses Branches und die
[Testevidenz](2026-10-22_TEST_EVIDENZ.md); kein Deploymentstand wird behauptet.

## Komponenten und Planvergleich

| Planpunkt | Implementierter Stand | Bewertung |
| --- | --- | --- |
| Bestehende Authority berücksichtigen | `models.py`, Manifest, Servermanager und AP-010-Verträge gelesen; AP-020-Lizenzgrenze nur lesend berücksichtigt | Vollständig |
| Typisierter Offlinekatalog | `catalog.py`: frozen Datenobjekte, probe-v1, Originalwerte, UUID und alle Namensfelder validiert, sichere strukturierte Diagnosen | Vollständig |
| Filter/Sortierung | Sprache, Edition, Chunk, S/M/L, Streaming; stabile sprach-/editions-/numerische Sortierung mit ID-Tiebreaker | Vollständig |
| Sichere Downloadvorbereitung | Reiner Plan, exakter Manifestabgleich, getrennte Portal-/Produkt-ID, nur Manifesthash/Bytecount, gegebenenfalls gepinnte Communityquelle | Vollständig |
| Getrennte Freigabegrenzen | Sichtbar, URL vorhanden, Zugriff ungeprüft, Sollintegrität, Bytes ungeprüft, Manifestrecht und Aktivierung getrennt | Vollständig |
| Diagnose-CLI | `summary`, `languages`, `list`, `inspect`, `plan`, `validate`; JSON/Exitcodes, keine Netzwerkeffekte | Vollständig |
| Tests | 124er-Snapshot plus synthetische Fixture, Positiv-/Negativ-/CLI-/Authoritytests, gesamte Suite gemäß Evidenz | Siehe Testevidenz |
| Optionale Datenquelle | `CatalogSource`-Protocol, ausschließlich `OfflineCatalogSource` implementiert | Vollständig |
| Aktuelle Dokumentation | `docs/kroko-model-catalog.md`, Verweise aus Modellmanagement und Kroko-Engine-Dokumentation | Vollständig |
| Veröffentlichung zur Prüfung | Eigener Commit/PR gegen `feat/v2-unified-kroko`; keine Übernahme/Deployment | PR-Metadaten sind maßgeblich |

## Designentscheidungen

Der Katalog schreibt weder Registry noch Manifest und erzeugt keine
`ProductModel`-Einträge. Damit existiert keine konkurrierende Produktverwaltung.
Die existierenden zwölf Hash-/Byte-/Rechtebindungen bleiben unverändert.
Alle 124 Portal-IDs bleiben Anbieter-UUIDs; die zwölf bestehenden Produkt-IDs
werden nur im Plan separat genannt. Aus keiner UUID wird ein Entitlement abgeleitet.

124 Modelle: 105 Pro, 19 Community, zwölf Sprachen; Größen S=20/M=28/L=76.
IW und JP bleiben Originalcodes. Revisionen bleiben Strings mit führenden
Nullen. Aktuell ist ausschließlich Streaming nachgewiesen; neue Modi/Größen
werden diagnostiziert und erfordern eine gezielte Vertragserweiterung.

Eine Positivliste für Felder verhindert, dass Portalcredentials in Raw-Dicts,
Reprs, Diagnosen oder CLI-Ausgaben landen. Zusätzliche ungefährliche Felder
sind später bewusst zu typisieren; unbekannte Felder werden abgelehnt.
Quellen sind auf exakte öffentliche HTTPS-Modellpfade beschränkt. Die originale
Katalogquelle wird erhalten, selbst wenn der Plan eine gepinnte Quelle nutzt.

Ein Manifesthash beschreibt erwartete Bytes; er verifiziert keinen Download.
Alle 124 Pläne bleiben `automatic_provisioning_ready=false`; die bestehenden
Manifestrechte sperren zudem `manifest_automatic_install_allowed` für alle.
Pro-Freigabe bleibt bei der künftigen AP-KR-020-Lizenzauthority.

## Endpunktuntersuchung und Nachweisgrenze

Aus dem bereitgestellten sauberen Export und dem bestehenden Probeskript ist
die strukturierte Portalantwort der licenses-Route nachvollziehbar. Das
Probeskript behandelt models ausdrücklich als unverifizierten Kandidaten.
Es wurde kein Probe-Code in das Produkt übernommen oder ausgeführt.
Die ursprüngliche sensitive JSON wurde nicht gelesen oder kopiert.
Keine erneute API-Anfrage, kein WebSockettest, keine Portalanmeldung.

Ein früher erfolgreicher Key-/Modell-WebSockettest ist eine bereitgestellte
Beobachtung und kein neuer Testbeleg dieser Arbeit. Daraus folgt kein
Katalogauthentifizierungs- oder Entitlementvertrag. Die Voraussetzungen für
Onlineadapter und echte Auto-Provisionierung sind in den
[offenen Punkten](2026-10-22_OFFENE_PUNKTE.md) festgehalten.

## Abweichungen

Keine materielle Abweichung vom vorab registrierten Umfang. Liveadapter,
Downloads und Aktivierung waren ausdrücklich ausgeschlossen. Der
App-Worktree-Helfer konnte den übergeordneten Nicht-Git-Workspace nicht
zuordnen; der separate Git-Worktree wurde deshalb mit `git worktree add`
vom geforderten Integrationsbranch angelegt. AP-020 blieb unangetastet.
