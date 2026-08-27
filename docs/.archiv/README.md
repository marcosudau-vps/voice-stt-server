# Archiv größerer Änderungsaktionen

## Verbindliche Regel

Jede größere Änderungsaktion am Projekt muss vor Beginn der Umsetzung in
diesem Archiv registriert und in einem eigenen Unterordner dokumentiert werden.
Als größere Änderungsaktion gelten insbesondere Änderungen an Architektur,
öffentlichen Protokollen oder APIs, persistierten Datenformaten,
Sicherheitsgrenzen, Deploymentstrukturen oder mehrere Module übergreifenden
Funktionen.

Für jede solche Aktion sind mindestens zwei getrennte Dokumente verpflichtend:

1. **Gesamtplanung vor der Umsetzung:** Sie beschreibt Ausgangslage, Ziele,
   Nicht-Ziele, Entscheidungen, Risiken, betroffene Bereiche, konkrete
   Umsetzungsschritte und Abnahmekriterien.
2. **Soll-/Ist-Vergleich nach der Umsetzung:** Er prüft die veröffentlichte
   Implementierung gegen jeden wesentlichen Planpunkt, nennt den tatsächlich
   verifizierten Stand und unterscheidet vollständig, teilweise und nicht
   umgesetzt.

Weicht die Umsetzung vom Plan ab, muss zusätzlich eine eigene
**Abweichungsdatei** angelegt werden. Darin sind für jede Abweichung mindestens
Grund, Auswirkung, bewusste Entscheidung beziehungsweise Handlungsbedarf und
der weitere Status festzuhalten. Abweichungen dürfen nicht nur beiläufig im
Abschlussvergleich erwähnt werden.

## Ablage- und Namenskonvention

Jede Aktion erhält genau einen stabil benannten Ordner:

```text
docs/.archiv/<aktionsname>/
```

Alle aktionsbezogenen Dateien beginnen mit ihrem tatsächlichen Erstellungsdatum
im Format `YYYY-MM-DD_`. Das gilt auch für spätere Ergänzungen. Empfohlene
Namen sind beispielsweise:

```text
YYYY-MM-DD_<AKTION>_PLAN.md
YYYY-MM-DD_<AKTION>_UMSETZUNGSVERGLEICH.md
YYYY-MM-DD_<AKTION>_ABWEICHUNGEN.md
```

Die zentrale Datei `docs/.archiv/README.md` ist als dauerhaftes Regelwerk und
Register von der Datumspräfix-Regel ausgenommen. Bereits archivierte
Originaldokumente werden inhaltlich nicht nachträglich umgeschrieben; ihre
historische Einordnung erfolgt über ergänzende, datierte Dateien.

## Verbindlicher Ablauf

1. Aktion im Register am Ende dieser Datei mit Status `Geplant` eintragen.
2. Aktionsordner und datierte Gesamtplanung anlegen.
3. Erst danach mit der Umsetzung beginnen.
4. Nach der Umsetzung den real veröffentlichten Stand gegen die Planung
   prüfen; bei produktiven Änderungen gehören GitHub- und Deploymentstand in
   die Gegenprüfung.
5. Datierte Soll-/Ist-Prüfung anlegen.
6. Bei jeder materiellen Abweichung eine separate datierte Abweichungsdatei
   anlegen oder fortschreiben.
7. Die dauerhaft gültige Fachdokumentation außerhalb von `.archiv`
   aktualisieren. Das Archiv ersetzt keine aktuelle Referenzdokumentation.
8. Links prüfen und den Status im Register erst danach auf `Abgeschlossen`
   setzen.

Zulässige Statuswerte sind `Geplant`, `In Umsetzung`, `Prüfung offen`,
`Abgeschlossen` und `Abgebrochen`. Bei `Abgebrochen` bleiben Planung und
Begründung im Archiv erhalten.

## Abgeschlossene und laufende Änderungsaktionen

| Aktion | Aktionsdatum | Status | Archiv |
| --- | --- | --- | --- |
| Sitzungslokale Wake-Word-Konfiguration | 25.07.2026 | Abgeschlossen | [session-wakeword](session-wakeword/) |
| Neues Logging- und Event-System | 31.07.2026 | Abgeschlossen | [neues_logging_event_system](neues_logging_event_system/) |
| SQLite-first Eventstream und Admin-Logvertrag | 02.08.2026 | Abgeschlossen | [sqlite_first_admin_eventstream](sqlite_first_admin_eventstream/) |
| Zentrale Build- und VPS-Deploymentdokumentation | 12.08.2026 | Abgeschlossen | [build_vps_dokumentation](build_vps_dokumentation/) |
| Einheitliche serverseitige Triggerarchitektur | 12.08.2026 | In Umsetzung | [einheitliche_triggerarchitektur](einheitliche_triggerarchitektur/) |

### Arbeitspaketakten „Einheitliche serverseitige Triggerarchitektur“

Die laufende Aktion ist in Arbeitspaketakten unterhalb von
[`einheitliche_triggerarchitektur/`](einheitliche_triggerarchitektur/)
gegliedert. Jede Akte enthält Planung, Runs mit byteidentischer Promptkopie,
Bericht und Evidence sowie den Umsetzungsvergleich.

| Arbeitspaket | Stand | Akte |
| --- | --- | --- |
| AP-SRV-000 Serverbaseline | Root PASS | [AP-SRV-000](einheitliche_triggerarchitektur/AP-SRV-000/) |
| AP-SRV-010 State Machine | Root PASS | [AP-SRV-010](einheitliche_triggerarchitektur/AP-SRV-010/) |
| AP-SRV-020 Segmentledger | Root PASS | [AP-SRV-020](einheitliche_triggerarchitektur/AP-SRV-020/) |
| AP-SRV-030 Commands und Timer | Root PASS | [AP-SRV-030](einheitliche_triggerarchitektur/AP-SRV-030/) |
| AP-SRV-040 Protokoll v2 | Root PASS | [AP-SRV-040](einheitliche_triggerarchitektur/AP-SRV-040/) |
| AP-SRV-050 Settings-Control-Plane | Root PASS | [AP-SRV-050](einheitliche_triggerarchitektur/AP-SRV-050/) |
| AP-SRV-060 Wake-Word-Katalog, Detection und Audiogrenze | **Pending Root Review** (Run 01) | [AP-SRV-060](einheitliche_triggerarchitektur/AP-SRV-060/) |

Die Gesamtaktion bleibt `In Umsetzung`, bis auch die verbleibenden
Arbeitspakete abgenommen und Umsetzung, Gegenprüfung,
Abweichungsdokumentation und Fachdokumentation konsistent sind. Ein einzelnes
Arbeitspaket wird erst nach Root-Abnahme als abgenommen geführt.
