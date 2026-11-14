# Textübernahmen im V2-Dokumentationsstand – unabhängige Vergleichsmessung

**Datum:** 14. November 2026
**VoiceSTT-Ausgangspunkt:** §feat/v2-release-cleanup§ @ §a8993c5c68042d996eab680d84a5b138a214bb5d§.
**Vergleichsquelle:** §KoljaB/RealtimeSTT§ @ §3574c247c531b8f6ff1f595b319eb400ba499f82§ (öffentlicher Upstream zum Audit-Zeitpunkt).

## Methode und Aussagekraft

Verglichen wurden lange identische Wortfolgen in der jeweils gleichen Dokumentationsdatei, nachdem nur die Projektbezeichnungen (RealtimeSTT/VoiceSTT) vereinheitlicht wurden. Ein Textwort wird gezählt, wenn es in einer gemeinsam vorkommenden Sequenz von mindestens **acht aufeinanderfolgenden Wörtern** liegt. Die Zahlen geben den Anteil solcher gedeckten Wörter an den VoiceSTT-Dokumenten vor und nach der Bereinigung wieder. Sie sind **keine** Plagiats- oder Lizenzrechtsquote, kein Vergleich beliebiger Quellen auf dem Internet und auch kein Beweis ursprünglicher Urheberschaft. Frühere historische Quellversionen können weitere Überschneidungen enthalten.

## Betroffene Dokumentationsdateien

| Datei in §docs/§ | Alter Textüberlapp | Neuer Textüberlapp |
| --- | ---: | ---: |
| §api-compatibility.md§ | 87.1 % | 0.0 % |
| §configuration.md§ | 43.7 % | 0.0 % |
| §external-audio.md§ | 100.0 % | 0.0 % |
| §fastapi-server.md§ | 33.0 % | 0.0 % |
| §faster-whisper.md§ | 89.9 % | 0.0 % |
| §installation.md§ | 76.1 % | 0.0 % |
| §kroko-onnx.md§ | 35.5 % | 0.0 % |
| §licenses.md§ | 66.1 % | 1.5 % |
| §module-map.md§ | 41.3 % | 0.0 % |
| §quick-start.md§ | 85.3 % | 0.0 % |
| §test-scripts.md§ | 95.6 % | 0.0 % |
| §testing.md§ | 53.7 % | 0.0 % |
| §transcription-engines.md§ | 26.3 % | 0.0 % |
| §troubleshooting.md§ | 95.0 % | 0.0 % |

Die hoch überlappenden Seiten wurden nicht als bloße neue Kopien archiviert. Sie sind durch **neu geschriebene, bewusst fokussierte V2-Wegweiser** mit Links auf das umfangreiche, unabhängig geprüfte [V2-Handbuch](../v2-handbuch/README.md) ersetzt worden. Der vollständige technische Inhalt ist im Handbuch selbst enthalten. Vorherige Texte bleiben in der unveränderlichen Git-Historie rückverfolgbar, aber nicht als aktiv gepflegte oder zusätzlich duplizierte Archivseiten.

## Root-Dateien – Einordnung statt formaler Textbereinigung

| Datei | Ausgangsüberlapp | Nachher | Entscheidung |
| --- | ---: | ---: | --- |
| §RELEASE_NOTES.md§ | 25.0 % | 0.0 % | VoiceSTT-eigene Versionshistorie vollständig neu verfasst; keine Übernahme der RealtimeSTT-Releasechronik |
| §README.md§ | 8.0 % | 7.9 % | Schon vor diesem Audit überwiegend eigenständig; auf V2-Handbuch verlinkt |
| §.gitignore§ | 87.3 % | 87.3 % | Technisches Muster-/Exclusion-Regelwerk, nicht allein aufgrund struktureller Ähnlichkeit verändert |
| §setup.py§ | 39.1 % | 38.6 % | Technische Buildlogik aus funktionalen Gründen beibehalten; tatsächlichen Paketautor auf Marco Sudau korrigiert; ursprüngliche Herkunft in Lizenzdatei gesichert |
| §LICENSE§ | 0.0 % | 0.0 % | Original-MIT-Lizenz und Copyright unverändert beibehalten; rechtlich notwendige Hinweise dürfen nicht zur Reduktion einer Vergleichsquote umgeschrieben werden |
| §MANIFEST.in§ | 17.7 % | 17.7 % | Technische Packaging-Globs und Exclusions aus Gründen der Paketstabilität erhalten |
| §requirements.txt§ | 49.4 % | 49.4 % | Technische Abhängigkeitsliste aus dem funktionalen Produktstand beibehalten |

## Archivierung und Herkunft

Eigenständig erstellte ältere VoiceSTT-Projektbeschreibungen wurden nach [`docs/.archiv/stand_vor_v2_handbuch_2026-11-14/`](../.archiv/stand_vor_v2_handbuch_2026-11-14/README.md) verschoben. Releasekritische Betriebs-, Authentifizierungs-, Code- und Lizenzunterlagen bleiben im aktiven Dokumentationsbaum erreichbar. Historische Tests, Kompatibilitätsverträge und Code-Referenzdokumente werden nicht ohne eigene Abnahme entfernt.

Das Wurzel-`LICENSE` führt weiterhin den ursprünglichen MIT-Hinweis und das Copyright von **Kolja Beigel (2023)**. Die [neue projektbezogene Lizenzübersicht](../licenses.md) trennt die Rechte am VoiceSTT-Quellcode, an der kompilierten Kroko-Runtime und an den gesondert berechtigten Modellgewichten. Eine gültige Pro-Keyprüfung ist kein automatischer Nachweis der gesamten binären Weitervertriebsrechte. Ein eventuell weiterhin `BLOCKED` gemeldeter Release-Rechtecheck wurde bei dieser Dokumentationsarbeit ausdrücklich **nicht** manipuliert.

## Prüfregeln für die Integration

- Von 105 übernommenen Handbuch-Markdown-Dateien (104 Kapitel + Index) bleiben **103 byteidentisch** zum ROOT-abgenommenen Arbeitsordner. In `01-grundlagen/01.04-gesamter-datenfluss.md` wurde **ausschließlich ein lokaler absoluter Windows-Prüfpfad** durch `lokaler unveränderter Git-Quellspiegel` ersetzt; Git-SHA und technische Aussagen sind unverändert. In `v2-handbuch/README.md` wurde ausschließlich eine redundante Leerzeile am Dateiende entfernt, damit `git diff --check` besteht. Beide redaktionellen Deltas sind separat ausgewiesen.
- Vor einer Git-Änderung an späteren Produktfunktionen sind API- und Konfigurationsbeispiele erneut gegen den aktuellen Code zu kontrollieren.
- Relative Links und die bestehenden maschinellen `test_docs_surface`- sowie `test_v2_code_reference`-Verträge sind zusätzliche Abnahmekriterien.
- Eine inhaltlich neu formulierte Dokumentation ändert nicht die Rechte am zugrunde liegenden Code oder Modell.
