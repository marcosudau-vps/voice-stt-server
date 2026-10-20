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
| V2-Segment-Activation-Korrelation (Nachtrag zu PR #3) | 29.09.2026 | Prüfung offen | [v2_segment_activation_correlation](v2_segment_activation_correlation/) |
| V2-Realtime-Identitäten und verspätete Interims | 30.09.2026 | In Umsetzung | [v2_realtime_identity](v2_realtime_identity/) |
| Issue #7: sichere Wake-Wiederfreigabe | 19.10.2026 | Prüfung offen | [issue_7_wake_rearm](issue_7_wake_rearm/) |
| Issue #9: Build-/Runtimeidentitaet A+B | 20.10.2026 | Prüfung offen | [issue_9_build_runtime_identity](issue_9_build_runtime_identity/) |

Die zugehörigen [Vor-Merge-Soll-/Ist-Prüfung](issue_9_build_runtime_identity/2026-10-20_PREMERGE_HAERTUNG_UMSETZUNGSVERGLEICH.md)
und [Abweichungsakte](issue_9_build_runtime_identity/2026-10-20_PREMERGE_HAERTUNG_ABWEICHUNGEN.md)
halten den zum Erstellungszeitpunkt offenen CI-/RC-Status korrekt fest;
nach dem finalen neuen Kandidatenlauf sind dessen realen Nachweise separat
an PR #10 zu binden.

Vor-Merge-Nachtrag zu Issue #9: [Plan der lokalen Manifestkopie und
Builddeklaration](issue_9_build_runtime_identity/2026-10-20_PREMERGE_HAERTUNG_PLAN.md);
Implementierung und neuer RC sind gesondert zu qualifizieren.

Nachtrag zu Issue #9 / PR #10: Der benutzerbeauftragte Windows-RC-Fix ist
vor Umsetzung in
[2026-10-20_WINDOWS_RC_PLAN.md](issue_9_build_runtime_identity/2026-10-20_WINDOWS_RC_PLAN.md)
registriert. Die V1-Referenz wird als CI-Muster geprueft; V2-Fingerprints,
Toolchainpins und Publikationsvertraege bleiben erhalten.
Der getrennte
[Soll-/Ist-Nachtrag](issue_9_build_runtime_identity/2026-10-20_WINDOWS_RC_UMSETZUNGSVERGLEICH.md)
und die
[neuen Abweichungen](issue_9_build_runtime_identity/2026-10-20_WINDOWS_RC_ABWEICHUNGEN.md)
belegen die Hostkorrektur und den danach sichtbar gewordenen
Microsoft-Channel-Manifestkonflikt. Diese Zwischenstaende hatten keine
gruene Windows-/Gesamt-RC-Abnahme.
Die anschliessende autonome Fortsetzung registriert vor Umsetzung die
[bytegleiche Manifest-Wiederbeschaffung](issue_9_build_runtime_identity/2026-10-20_MANIFEST_LOCATOR_PLAN.md).
Die neue explizite Bezugsquelle muss korrekt neue Windows-Fingerprints
ableiten; alte Identitaeten werden nicht fuer geaenderte Inputs verwendet.
Der bisher offene echte Image-Endpunktnachweis wird vor Umsetzung unter
[2026-10-20_IMAGE_ENDPOINT_PLAN.md](issue_9_build_runtime_identity/2026-10-20_IMAGE_ENDPOINT_PLAN.md)
registriert; keine zusaetzliche Publikationsautoritaet.
Der abschliessende
[Fortsetzungsvergleich](issue_9_build_runtime_identity/2026-10-20_FORTSETZUNG_UMSETZUNGSVERGLEICH.md)
und die
[materiellen Abweichungen](issue_9_build_runtime_identity/2026-10-20_FORTSETZUNG_ABWEICHUNGEN.md)
belegen nun den echten erfolgreichen Vier-Wheel-/Image-Endpunkt-RC
[39359464011](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39359464011)
auf d99633a, die separate Artefaktnachpruefung und den unveraenderten
Client-Paartest. A+B sind implementiert und technisch qualifiziert;
unabhaengiger PR-Review und jede spaetere Uebernahme bleiben offen.
Keine automatische Gesamtfreigabe, kein Release oder Deployment.

Nachtrag zu Issue #7 / PR #8: Die unabhaengige P1-Reviewkorrektur zur
Clear-/Wake-Admission-Race ist vor Umsetzung in
[2026-10-19_P1_CLEAR_PLAN.md](issue_7_wake_rearm/2026-10-19_P1_CLEAR_PLAN.md)
registriert. Der getrennte
[Soll-/Ist-Nachtrag](issue_7_wake_rearm/2026-10-19_P1_CLEAR_UMSETZUNGSVERGLEICH.md)
dokumentiert ROT/GRUEN und den geprueften Korrekturcommit
(Status: Prüfung offen). Die urspruengliche Aktion bleibt Pruefung offen.

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
| AP-SRV-060 Wake-Word-Katalog, Detection und Audiogrenze | **Pending Root Review** (Run 01 ROOT FAIL, Run 02 ROOT FAIL, Run 03 Korrektur eingereicht) | [AP-SRV-060](einheitliche_triggerarchitektur/AP-SRV-060/) |
| AP-SRV-070 Serverbereinigung und Produktionshaertung | In Umsetzung (W5-R04 Release-Infrastruktur und Dokumentations-Rebaseline eingereicht, Root Review ausstehend) | [AP-SRV-070](einheitliche_triggerarchitektur/AP-SRV-070/) |
| AP-SRV-080 V2-Realtime- und Session-Logzugriff | Abgeschlossen | [AP-SRV-080](einheitliche_triggerarchitektur/AP-SRV-080/) |

Die Gesamtaktion bleibt `In Umsetzung`, bis auch die verbleibenden
Arbeitspakete abgenommen und Umsetzung, Gegenprüfung,
Abweichungsdokumentation und Fachdokumentation konsistent sind. Ein einzelnes
Arbeitspaket wird erst nach Root-Abnahme als abgenommen geführt.
