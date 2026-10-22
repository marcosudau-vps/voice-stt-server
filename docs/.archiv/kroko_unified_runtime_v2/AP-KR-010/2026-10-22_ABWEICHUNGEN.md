# AP-KR-010 – Abweichungen und Nachweisgrenzen

22.10.2026. Historische Belege wurden nicht verändert.

| Sachverhalt | Grund | Auswirkung / Entscheidung / Status |
| --- | --- | --- |
| Initialer Branch war `main` statt V2 | Neuer Checkout auf Defaultbranch | Vor Arbeit korrigiert: Integration exakt auf V2-Merge `67f3ce4`, AP-010 davon. Dokumentiert in Gesamtplanung; erledigt. |
| Ältere PR-/Archivtexte zeigen noch RC NOT_RUN | Historische Snapshots vor neuem RC | Aktuelle Actions-Metadaten belegen SUCCESS 39405176300 auf gleichem Tree wie Merge. Eigener Nachweis statt Umschreiben; erledigt. |
| Originale Intermediate-Wheels nicht separat im RC | RC liefert qualifizierte Produktwheels | Deren echte native Payloads und ursprüngliche Nativeprovenienz geprüft. Kein behaupteter neuer Hashcheck der Intermediatearchive; Grenze bleibt explizit. |
| Erste Windowsextraktion konnte nicht importieren | Fehlende Wheel-`.data/platlib`-Spreadingsemantik im Experiment | Probe korrigiert; gehashte DLL in privaten Installationsroot übernommen, unveränderte Bytes. Danach alle nativen Fälle grün. Folgepflicht AP-030. |
| Linux zusätzlich lokal ausführbar | WSL Ubuntu mit CPython 3.12 vorhanden | Reale Linuxnative-Fälle ausgeführt, WSL-/glibc-Grenze benannt. Docker Desktop blieb pausiert, kein neuer Containerbeleg. |
| Keine echten positiven/negativen Lizenzserverfälle | Keine dedizierte autorisierte Lizenztestumgebung verwendet; Zugangsdaten nicht gesucht | Vorhandene Communitydatei wird real geprüft, Prolizenzfälle OFFEN. Invalid-Headerfixture ist nur fataler Nativefehler, kein ungültiger Key. Voraussetzung R01/R02 vor AP-020. |
| Native Umschaltung braucht vollständigen Besitzerprozesswechsel | Gleiche Imports, Singleton/Reporter, fataler Exit | Kleinste robuste Empfehlung mit kurzer Dienstunterbrechung; kein Produktumbau. Bestätigung des Betriebsvertrags vor AP-020; offen. |
| Windows-Kroko-Lizenztext fehlt im geprüften Produktwheel | Vollständige Lizenz-/Notice-Dateinamenssuche gegen reale Artefakte | Aktuelle Doku präzisiert; Releaseblocker für Folgequalifikation, keine rückwirkende Neubewertung alter Abnahme. AP-030 offen. |

Eine spätere produktive Soll-/Ist-Prüfung der Gesamtaktion kann erst nach
AP-KR-020/AP-KR-030 und deren unabhängig geprüfter Veröffentlichung entstehen.
Die heutige Soll-/Ist-Datei bewertet ausschließlich den Untersuchungsauftrag.
