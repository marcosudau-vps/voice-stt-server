# AP-KR-010 – Untersuchungsmatrix und Methodik

Vor den nativen Experimenten erstellt. Stand 22.10.2026.

VERIFIZIERT = hier real ausgeführt oder explizit benannter externer CI-Beleg;
CODEANALYSE = Schluss aus gepinntem Quellcode; SIMULIERT = künstlicher Vertrag /
Fixture, auch wenn echte Werkzeuge laufen; OFFEN = kein belastbarer Nachweis.

| ID | Fragestellung | Methode / Erfolgskriterium |
| --- | --- | --- |
| B0 | Baseline | Fetch, sauberer Initialbaum, Merge-/CI-/RC-Metadaten, Treevergleich PR-HEAD/Merge |
| A1 | Tatsächliche Free-/Pro-Dateien | RC 39405176300, gesamtes SHA-Inventar verifizieren, vier Produktwheels untersuchen; eingebettete Original-Runtimeidentität auslesen |
| A2 | Kollisionen | ZIP-Pfade/Bytes vergleichen, CPython-Extension und DLL/ELF-Abhängigkeiten prüfen; keine gleichzeitige Installation der alten Vollprodukte |
| A3 | Beide bereitgestellt, nur eine importiert | Native Payloads bytegleich in getrennte private Verzeichnisse extrahieren; frische isolierte Prozesse je Plattform/Variante; geladene Modulpfade prüfen |
| A4 | Importreihenfolge | Pfadwechsel Free→Pro und Pro→Free im selben Prozess; Cacheidentität feststellen; kein riskantes dlclose/FreeLibrary |
| A5 | Reale Initialisierung | Vorhandenes Community-Modell gegen Manifestgröße/SHA prüfen; je Runtime Recognizer und Stream bauen, Stille decodieren; keinerlei Lizenzkey oder Lizenznetz erforderlich |
| A6 | Fataler Nativefehler/Fallback/erneuter Wechsel | Eigene ungültige Headerfixture (kein echtes Modell verändern) im Pro-Kindprozess; Exitstatus und Timeout abfangen, danach frischer Free-, dann Pro-Prozess mit Community-Modell |
| A7 | Plattform | Windows AMD64 CPython 3.12; Linux AMD64 CPython 3.12 unter lokalem WSL; fehlende Dependencies/Plattformpfade explizit offen lassen |
| B1 | Wann Lizenzprüfung? | Gepinnte Quellen `online-transducer-model.cc`, `license.h`, Pythonbindings; Import vs. Modellaufbau, Singleton, Reporter, Fehler und Timeout unterscheiden |
| B2 | Positive/negative echte Lizenz | Nur vorhandene ausdrücklich autorisierte Lizenztestumgebung; keine Keys suchen/erfinden/ändern. Sonst OFFEN; kein Communitytest als Positivlizenztest |
| B3 | Statusvertrag | Generationgebundene Invalidierung, Ablauf/Lizenzverlust, Berechtigungen, sichere serverweite Projektion als Entwurf |
| C1 | Server/Modelle/Client | Variantenchecks, Resolver, Provisionierung, Settings, Secrets, Thread-/Prozessgrenze, Modellwechsel, HTTP-/Wireidentität systematisch kartieren |
| D1 | Extra/Komponente | Separates lokales Experiment: synthetische Basis-METADATA mit Extra plus reale bytegleiche Payloads in disjunkten Verzeichnissen, offline pip-Auflösung/Deinstallation; keine Produktqualifikation |
| D2 | Release | setup, Buildhelpers, Artifact-/Fingerprintauthority, RC-Schema, CI, Publish/Resume/Rollback, OCI und Lizenzressourcen lesen; konkrete Folgeänderungen dokumentieren |
| T1 | Regression | Ganze vorhandene `tests/unit`-Suite; optionale Integrationen als skips; vorhandene Packaging-/Contracttests nach Umgebung, kein ungeprüftes Gesamt-PASS |
| T2 | Evidenzqualität | Skript reproduzierbar, keine Credentials in Child-Env/Argumenten/Output, keine Binärdateien/Modelle/Logs committet, Links/Whitespace/Produktdiff prüfen |

Artefakte, erzeugte Ergebnisse und Fixtures liegen im lokalen externen
Tempverzeichnis `ap-kr-010-20261022`. Modellquellen bleiben read-only.
Die Experimentierskripte gehören ausschließlich zu dieser Untersuchung.
