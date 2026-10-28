# Jules-Quellenpaket V0.1 importieren

Der Branch `research/v2-documentation-sources` basiert auf `feat/v2-unified-kroko`.
Für eine öffentliche Veröffentlichung der Quelltexte müssen die ZIP-Inhalte
zuvor auf nichtöffentliche Informationen geprüft werden. **Ein temporärer
Branch ist im öffentlichen Repository ebenfalls öffentlich.**

Das Quellenpaket `jules_quellenpaket_v01_zur_pruefung.zip` ist noch nicht
im Repository vorhanden. Das Importskript prüft seinen SHA-256-Hash und
verifiziert die pro Datei aufgeführten Prüfsummen, bevor es 38 Dateien
nach `research/doc-sources/` extrahiert.

Beispiel Windows PowerShell (ZIP vorher aus ChatGPT herunterladen):

```powershell
git clone --branch research/v2-documentation-sources https://github.com/marcosudau-vps/voice-stt-server.git
cd voice-stt-server
python research/doc-sources/import_sources.py "C:\\Users\\<BENUTZER>\\Downloads\\jules_quellenpaket_v01_zur_pruefung.zip"
git status --short
# Jetzt Inhalte auf Veröffentlichbarkeit prüfen.
git add research/doc-sources/
git commit -m "docs(research): add historical source bundle v0.1"
git push origin research/v2-documentation-sources
```

Das Skript committet und pusht aus Sicherheitsgründen **nicht automatisch**.

Nach dem Push die Dateien `research/doc-sources/SOURCE_INDEX.csv`
und `research/doc-sources/sources/observability_client_v1/00_INDEX.md`
im GitHub-Browser kontrollieren. Erst danach die Jules-Dokumentationsaufträge
starten. Keine eigenmächtige Übernahme in den kanonischen V2-Branch.
