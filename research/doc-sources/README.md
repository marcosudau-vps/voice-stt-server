# Temporärer Jules-Recherchebereich (Voice-STT V2)

**Zweck:** Dokumentationsrecherche und Quellenabgleich auf dem Stand `feat/v2-unified-kroko`.
Dieser Branch dient ausschließlich der Vorbereitung und ist **keine** kanonische Release- oder Cleanup-Linie.

## Erwartetes Quellenpaket

Datei: `jules_quellenpaket_v01_zur_pruefung.zip` (SHA-256 `962d8ce569986d55bbc9fe0ff4fd9d6d287bba528b3ee42aee0e87817e8e8278`).

Die 38 ZIP-Einträge (35 historische Markdown-Quellen, Indexe und Prüfanleitung) sollen **entpackt** unter `research/doc-sources/` liegen:

- `README_VOR_COMMIT_PRUEFEN.md`
- `SOURCE_INDEX.csv` (Quellpfade und SHA-256-Prüfsummen)
- `AP_HISTORY_INDEX.csv` (nur Verweise, nicht die AP-Inhalte)
- `sources/observability_client_v1/` (Client-Historie, keine Server-Ist-Referenz)
- `sources/server_client_contract_v2/` (historische V2-Vertragsdokumentation)

**Stand dieses Branch-Commits:** Nur die Arbeitsanleitung wurde angelegt; die 38 Quelldateien wurden noch **nicht** hochgeladen. Vor Agentenstarts prüfen, dass beide `sources/`-Verzeichnisse und die CSV-Indizes tatsächlich vorhanden sind.

## Verbindliche Regeln für Jules

1. `AGENTS.md` und die aktuellen Projekt-/Archivregeln beachten.
2. Historische Unterlagen sind **Recherchequellen**, keine maßgebliche aktuelle Produktdokumentation. Aktuelle Aussagen gegen Code und Tests dieses Branch-Commits prüfen.
3. Insbesondere die Client-Observability-Historie nicht als serverseitige Implementierung ausgeben.
4. Keine Änderung an Produktcode, Tests, API-/Protokollverträgen, Packaging oder Release-Gates.
5. Für jeden wesentlichen Befund Quellpfad, Code-/Testbeleg, Status (verifiziert/historisch/widersprüchlich/offen) dokumentieren.
6. Dokumentationsarbeit nur in gesonderten Agenten-Branches/PRs; keine eigenmächtigen Merges in V2-Release-Linien.
7. Das Repository ist öffentlich: Vor dem Quellen-Commit alle Dateien auf Secrets, personenbezogene Daten, interne Hostnamen und nicht öffentliche Informationen prüfen.

Der Recherchebranch kann nach kontrollierter Übernahme beziehungsweise Archivierung seiner Ergebnisse wieder gelöscht werden.
