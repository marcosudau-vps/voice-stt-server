# Soll-/Ist-Vergleich: sitzungslokale Wake-Word-Konfiguration

## Grundlage

Dieser nachträgliche Vergleich ordnet die Aktion vom 25.07.2026 anhand der
[ursprünglichen Spezifikation](2026-07-25_SERVER_SESSION_PROFILE_SPECIFICATION.md),
des damaligen
[Prüf- und Implementierungsberichts](2026-07-25_SERVER_SESSION_PROFILE_IMPLEMENTATION_REPORT.md)
und des inzwischen in `main` veröffentlichten Stands ein.

Die dauerhaft gültige Funktions- und Betriebsdokumentation steht unter
[Sitzungslokale Wake-Word-Konfiguration](../../session-wakeword-erweiterung.md).

## Ergebnis

Das fachliche Kernziel ist umgesetzt: Jede WebSocket-Verbindung kann ihren
Wake-Word-Modus beim Verbindungsaufbau sicher und isoliert festlegen, ohne die
Serverbaseline oder andere Sessions zu verändern. Die Umsetzung verwendet
einen kleineren, expliziten Session-Wake-Word-Contract statt des ursprünglich
vorgeschlagenen allgemeinen Profilkatalogs.

| Planbereich | Umsetzungsstand | Tatsächliche Umsetzung |
| --- | --- | --- |
| Sessionlokale Auswahl | vollständig | `wakeWordEnabled` unterstützt Erben, Aktivieren und Deaktivieren pro Verbindung. |
| Isolation | vollständig | Jede Session erhält eine private Konfigurationskopie; globale und fremde Sessions bleiben unverändert. |
| Verbindungszeitpunkt | vollständig | Sessionparameter werden einmalig beim WebSocket-Aufbau ausgewertet. |
| Bestätigung des wirksamen Zustands | vollständig | `hello` und `ready` liefern `sessionConfig` und `sessionCapabilities`. |
| Fehler und Fallbacks | vollständig | Mehrdeutige oder nicht erfüllbare Wünsche werden abgelehnt; weiche Fallbacks und ignorierte Felder werden sichtbar bestätigt. |
| Sichere Modellwahl | vollständig | OpenWakeWord-Modelle werden über logische IDs aus `models.json` aufgelöst und gegen lokale Dateien validiert. |
| Sessionlokales Tuning | vollständig im Wake-Word-Umfang | Empfindlichkeit, Aktivierungsverzögerung, Timeout, Puffer und Follow-up-Fenster sind begrenzt überschreibbar. |
| Allgemeiner Profilkatalog | nicht umgesetzt | Es gibt keine Profile wie `direct_hotkey` oder `wake_word`; der Vertrag ist parameterbasiert. |
| Breite Audio-, VAD-, Realtime- und Promptprofile | nicht umgesetzt | Der Sessionvertrag wurde bewusst auf Wake-Word-Verhalten begrenzt. |
| Backends | teilweise gegenüber dem ursprünglichen Allgemeinansatz | Der öffentliche Serververtrag bietet OpenWakeWord; Porcupine ist nicht Teil des Session- oder Adminvertrags. |
| Tests | vollständig für den umgesetzten Vertrag | Parser-, Fallback-, Katalog-, Protokoll- und Isolationsfälle sind automatisiert abgedeckt. |
| Dokumentation und Betriebsnachweis | vollständig | Aktuelle Referenz, HTTP-Nachweis und WebSocket-Liveprüfung sind dokumentiert. |

## Abnahme

Die Aktion ist für den tatsächlich festgelegten Session-Wake-Word-Umfang
abgeschlossen. Die Abweichungen vom breiteren ursprünglichen Profilentwurf
sind keine verdeckten Restarbeiten, sondern dokumentierte Architektur- und
Sicherheitsentscheidungen. Sie stehen separat in
[2026-08-01_SESSION_WAKEWORD_ABWEICHUNGEN.md](2026-08-01_SESSION_WAKEWORD_ABWEICHUNGEN.md).
