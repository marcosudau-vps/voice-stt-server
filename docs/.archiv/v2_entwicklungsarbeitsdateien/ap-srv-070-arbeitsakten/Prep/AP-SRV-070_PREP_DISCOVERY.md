# AP-SRV-070 PREP DISCOVERY
# Legacy-Inventar, Runtime-Erreichbarkeit, Dokumentations- und Ordnungs-Audit
# READ-ONLY DISCOVERY – KEINE PRODUKTÄNDERUNGEN

## 0. Auftrag und Status

Du führst eine reine Voruntersuchung für

```text
AP-SRV-070 – Server-Legacyabbau und Protokollgrenze
```

durch.

Dieser Lauf ist ausschließlich:

```text
PREP DISCOVERY / ANALYSE
```

Er ist ausdrücklich NICHT:

```text
kein AP-SRV-070 C1
kein Distributed-Run
kein kanonischer Run
keine Implementierung
keine Root-Abnahme
kein PASS
kein Donor-Code-Commit
```

Ziel ist, vor dem eigentlichen AP-SRV-070 eine belastbare Landkarte zu erzeugen:

1. Welche Legacy-/Compatibility-/Dead-Code-Stellen existieren heute tatsächlich?
2. Welche davon sind noch runtime-erreichbar?
3. Welche wirken noch als zweite oder alte Autorität?
4. Welche können später wahrscheinlich entfernt oder migriert werden?
5. Welche Stellen müssen wegen AP-SRV-060 bewusst unangetastet bleiben?
6. Welche Dokumentations-, Ablage-, Archiv-, Naming- oder sonstigen Aufräumarbeiten fallen im Umfeld auf?
7. Was sollte im späteren Hauptlauf konkret wo bereinigt, verschoben, zusammengeführt, aktualisiert oder gelöscht werden?

Wichtig:

**In diesem Auftrag wird NICHTS davon umgesetzt.**

Du lieferst ausschließlich Analyseartefakte.

---

# 1. Modell / Repository / Basis

Repository:

```text
P:\GithubRepos\marcosudau-vps\voice-stt-server
```

Kanonische Basis für diese Discovery:

```text
Branch:
feat/einheitliche-triggerarchitektur

SHA:
c901cda3f2c19eeb78c468524161728498b6e27e

TREE:
f81144a26f93fb3bc553ab5110d07197a473aa46
```

Das ist der Root-abgenommene AP-SRV-050-Stand.

AP-SRV-060 läuft aktuell separat und ist noch nicht Root-abgenommen.

Deshalb darfst du KEINE laufenden oder vermuteten SRV-060-Änderungen als Ist-Zustand behandeln.

---

# 2. Isolierte, unveränderte Discovery-Arbeitskopie

Die Untersuchung soll exakt gegen die gepinnte Basis erfolgen.

Lege dafür, falls noch nicht vorhanden, einen **detached, read-only verwendeten Worktree** an:

```text
P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\prep-srv-070-discovery
```

Befehl:

```powershell
git -C "P:\GithubRepos\marcosudau-vps\voice-stt-server" worktree add --detach `
  "P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\prep-srv-070-discovery" `
  c901cda3f2c19eeb78c468524161728498b6e27e
```

Wenn der Worktree bereits existiert:

- nicht löschen;
- nicht resetten;
- nicht überschreiben;
- zuerst prüfen, ob HEAD exakt auf der erwarteten SHA steht;
- bei Abweichung `STATUS: BLOCKED`.

Im Discovery-Worktree prüfen:

```powershell
Set-Location "P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\prep-srv-070-discovery"

git rev-parse HEAD
git rev-parse "HEAD^{tree}"
git status --short
```

Erwartung:

```text
HEAD = c901cda3f2c19eeb78c468524161728498b6e27e
TREE = f81144a26f93fb3bc553ab5110d07197a473aa46
working tree = clean
```

Danach bleibt der Produkt-Worktree vollständig unverändert.

---

# 3. Harte Read-only-Regeln

VERBOTEN:

```text
Produktcode ändern
Tests ändern
Dokumentation im Repository ändern
Dateien löschen/verschieben/umbenennen
Formatierungsläufe mit Schreibwirkung
Auto-Fixes
git add
git commit
git checkout auf andere Branches
git reset
git clean
git rebase
git merge
git cherry-pick
git push
canonical verändern
distributed verändern
neue venv anlegen
```

Auch offensichtliche Kleinigkeiten NICHT direkt korrigieren.

Stattdessen immer:

```text
Fund
→ Nachweis
→ empfohlene spätere Maßnahme
→ Zielpfad/Zielsymbol
```

---

# 4. Wake-Word-Zone vollständig aus der fachlichen Analyse herausnehmen

AP-SRV-060 läuft aktuell.

Darum wird alles, was fachlich oder technisch nahe an Wake Word liegt, in dieser Discovery NICHT bewertet, NICHT umgebaut und NICHT als Remove-/Migration-Candidate klassifiziert.

Konservativ ausnehmen:

```text
wakeword
wake_word
OpenWakeWord
openwakeword
Porcupine
WakeWordCatalog
WakeWordRegistry
WakeWordPort
Wake Admission
wake detection
wakeword.detected
wakeword.availability_changed
Wake-Word-Auswahl / Selection
Wake-Word-Aliase
Wake-Word-Modelle / Assets / Manifest
Sensitivity
Cooldown
Pre-Roll
Wake-Audiogrenze
Wake-spezifische Recorder-/Gate-Grenzen
Wake-spezifische Callback-/Latch-/Detection-Pfade
Wake-spezifische Sessionadmission
Wake-spezifische Settings
Wake-Follow-up-Logik, sofern nicht eindeutig unabhängig von SRV-060
```

Wenn du bei einer Stelle unsicher bist, ob sie in die Wake-Word-Zone fällt:

```text
EXCLUDED_WAKEWORD_ZONE
```

und nicht weiter fachlich beurteilen.

Du darfst solche Stellen im Inventar lediglich nennen, damit später bekannt ist, dass sie bewusst ausgespart wurden.

Keine Aussage:

```text
safe remove
dead
replace
migrate
```

für diese Zone.

Der spätere Root-PASS von SRV-060 entscheidet, wie diese Bereiche im echten AP-SRV-070 behandelt werden.

---

# 5. Normative Quellen

Client-Koordinationsworkspace nur lesen:

```text
P:\GithubRepos\marcosudau-vps\voice-stt-client\workspaces\einheitliche-triggerarchitektur\
ARBEITSDATEIEN\10_AKTUELL\EINHEITLICHE_TRIGGERARCHITEKTUR\
```

Mindestens:

```text
PLANUNG\ZIELBILD.md
PLANUNG\TECHNISCHER_CONTRACT_FREEZE.md
PLANUNG\PROTOKOLL_V2_WIRE_SCHEMA.md
PLANUNG\ENTSCHEIDUNGEN_UND_OFFENE_PUNKTE.md
PLANUNG\IMPLEMENTIERUNGSPLAN.md

PLANUNG\ANALYSEN\LEGACY_AND_DEAD_CODE_MAP.md
PLANUNG\ANALYSEN\CODE_ARCHITECTURE_BASELINE.md
PLANUNG\ANALYSEN\STATE_EVENT_COMMAND_ATLAS.md

NACHVERFOLGUNG\TRACEABILITY.md
NACHVERFOLGUNG\FUNDE.md
NACHVERFOLGUNG\WIEDEREINSTIEG.md
NACHVERFOLGUNG\AUSFUEHRUNGSSTATUS.md
```

Server:

```text
AGENTS.md
docs/.archiv/README.md
docs/einheitliche-triggerarchitektur.md
docs/module-map.md
docs/configuration.md
docs/api-compatibility.md
docs/fastapi-server.md
docs/wake-words.md
```

sowie der tatsächliche Code und die Tests auf der gepinnten Basis.

Historisches Prep-Material ist nur Vergleichsquelle:

```text
voice-stt-client\
ARBEITSDATEIEN\90_HISTORIE\
2026-08-25_TRIGGERARCHITEKTUR_SERVER_PREP\
2026-08-25\AP-SRV-070\
```

und ggf.:

```text
AP-SRV-070_CLAUDE_PACKAGE
```

Historische Fundstellen müssen gegen den heutigen Code neu verifiziert werden.

---

# 6. Zielbereich außerhalb Wake Word

Untersuche systematisch den gesamten verbleibenden AP-SRV-070-relevanten Serverbereich.

Mindestens:

## 6.1 Alte Lifecycle-/Runtime-Autoritäten

Suche nach Resten von:

```text
session.mode
mode-basierter Triggerautorität
legacy activation mode
alten Dictation-/Window-Autoritäten
zweiten Lifecyclepfaden
alten Foregroundphasen
finalizing als Runtime-/Foregroundautorität
alten finalized/finalizing Übergängen
```

Frage bei jeder Stelle:

- Wird sie heute im Produktpfad erreicht?
- Liest oder schreibt sie Runtimezustand?
- Ist sie nur Compatibility?
- Ist sie vollständig dead?
- Gibt es bereits einen kanonischen Ersatz aus SRV-010 bis SRV-050?

## 6.2 Source-Merge / Mehrfachautorität

Prüfen:

```text
merged
already_active
source merge
source override
zweite Triggerquelle während offener Activation
alte Admissionsemantik
```

Zielbild:

```text
First Trigger wins
keine zweite Source-Autorität
```

## 6.3 v1 / Legacy-Protokollpfade

Prüfen:

```text
v1
legacy trigger
trigger_ack
alte trigger payloads
extend
extensionSeconds
additive extension
alte Desktopadapter
Fallback ohne gültigen v2-Handshake
```

Besonders unterscheiden:

```text
aktive Runtime-Kompatibilität
vs.
harmloser Parser-/Migrationscode
vs.
historische Doku/Testfixture
```

## 6.4 Alte Session-/Admissionpfade

Prüfen:

- alte Sessionobjekte;
- alte Realtime-/Inline-Lifecycles;
- parallele Sessionerzeugung;
- Compatibilitypfade vor/anstatt v2-Admission;
- Fälle, in denen inkompatible Clients bereits Teilzustand erzeugen.

## 6.5 Settings-/Config-Legacy außerhalb Wake Word

Prüfen:

- alte Mode-/Dictation-/Timing-Keys;
- doppelte Timingquellen;
- alte Runtimeautorität außerhalb der SRV-050 Settings-Control-Plane;
- persistierte Legacykeys;
- Migrationseams;
- Default-/Fallbackwerte mit alter Semantik.

Keine Wake-Word-Keys bewerten.

## 6.6 Dead Code / Compatibility / öffentliche API

Historische Kandidaten neu prüfen, z. B.:

```text
RealtimeSession
VoiceActivityDetector
ActivationController.finalized()
AudioToTextRecorderClient
weitere nicht mehr erreichbare FastAPI-Serverpfade
```

Aber:

Nur weil FastAPI etwas nicht nutzt, ist es nicht automatisch entfernbar.

Unterscheide:

```text
SERVER_RUNTIME_DEAD
KEEP_COMPATIBILITY
PUBLIC_LIBRARY_API_OUT_OF_SCOPE
UNKNOWN_EXTERNAL_USE
```

---

# 7. Klassifikationsschema

Jeder relevante Fund außerhalb der Wake-Word-Zone erhält genau eine Hauptkategorie:

```text
REMOVE_CANDIDATE
MIGRATION_CANDIDATE
KEEP_COMPATIBILITY
STILL_ACTIVE_REQUIRED
PUBLIC_LIBRARY_API_OUT_OF_SCOPE
UNKNOWN_NEEDS_REVIEW
EXCLUDED_WAKEWORD_ZONE
```

Zusätzlich Risikostufe:

```text
LOW
MEDIUM
HIGH
```

und Nachweisqualität:

```text
PROVEN
STRONG_INDICATION
UNCERTAIN
```

`REMOVE_CANDIDATE` darf nur verwendet werden, wenn:

- Callgraph/Callsites geprüft wurden;
- keine aktuelle Produktabhängigkeit gefunden wurde;
- ein Ersatz existiert oder die Funktion wirklich dead ist;
- die Stelle nicht in der Wake-Word-Zone liegt.

---

# 8. Dokumentations-Vollständigkeitsaudit

Zusätzlich zum Codeinventar die aktuelle Serverdokumentation prüfen.

Keine Dokumente ändern.

Prüfen:

```text
docs/einheitliche-triggerarchitektur.md
docs/module-map.md
docs/configuration.md
docs/api-compatibility.md
docs/fastapi-server.md
docs/wake-words.md
docs/client-development/
docs/.archiv/README.md
README.md
AGENTS.md
```

Fragen:

1. Beschreibt die Doku noch Legacy-Verhalten als aktuell?
2. Fehlen bereits umgesetzte SRV-010–050-Verhaltensweisen?
3. Widersprechen sich zwei aktuelle Dokumente?
4. Gibt es veraltete Pfade/Dateinamen/Symbole?
5. Gibt es doppelte Dokumentation mit unklarer Autorität?
6. Ist klar getrennt zwischen aktuellem Runtimeverhalten, Migration/Compatibility, Historie und geplantem Verhalten?
7. Sind Browserclient und Desktop-v2 sauber voneinander abgegrenzt?
8. Sind Protokollgrenzen und unterstützte Versionen konsistent beschrieben?
9. Gibt es Doku, die fachlich eher ins Archiv gehört?
10. Fehlen zentrale Querverweise?

Wake-Word-Inhalte nicht fachlich korrigieren oder bewerten.

Wenn dort Auffälligkeiten sichtbar sind:

```text
EXCLUDED_WAKEWORD_ZONE – nach SRV-060 erneut prüfen
```

---

# 9. Repository-Ordnungs- und Aufräumaudit

Ebenfalls nur analysieren, nichts verschieben.

Suche nach:

```text
offensichtlich falsch abgelegten Dateien
temporären Arbeitsdateien
veralteten Prep-/Reviewresten
doppelten Dokumenten
historischen Dateien außerhalb dafür vorgesehener Archivbereiche
untracked-/generierte Artefaktmuster
alte Scripts ohne erkennbare Nutzung
obsolete Fixtures
alte Configbeispiele
TODO/FIXME/DEPRECATED Marker
Dateien mit irreführendem Namen
verwaiste Verzeichnisse
alte Compatibility-Hilfen ohne dokumentierten Zweck
```

Für jeden Ordnungsfund angeben:

```text
aktuelle Position
Problem
empfohlene spätere Aktion:
- KEEP
- MOVE
- ARCHIVE
- MERGE
- RENAME
- DELETE_CANDIDATE
- DOCUMENT_ONLY

konkreter Zielpfad, falls MOVE/ARCHIVE/RENAME empfohlen
Begründung
Risiko
```

Keine pauschalen Schönheitsvorschläge.

Nur Dinge aufnehmen, deren Bereinigung die Wartbarkeit, Nachvollziehbarkeit oder Architekturgrenze tatsächlich verbessert.

---

# 10. Test- und Fixture-Audit

Prüfe, welche Tests noch bewusst oder unbewusst Legacy-Soll schützen.

Unterscheide:

```text
VALID_CURRENT_TEST
LEGACY_EXPECTATION
COMPATIBILITY_TEST
STALE_FIXTURE
MISLEADING_DOUBLE
MISSING_CUT_GUARD
```

Besonders suchen nach Tests, die noch voraussetzen:

```text
session.mode Runtimeautorität
Source-Merge
additives extend
v1 Triggerpfad
finalizing als Foregroundphase
alte Sessionadmission
```

Wake-Word-Tests auslassen.

Keine Tests ändern.

Für `MISSING_CUT_GUARD` konkret vorschlagen:

```text
welche Invariante
welcher sinnvollste Testtyp
ungefähre bestehende Testdatei oder neue Zieldatei
```

---

# 11. Protokollgrenzen-Audit

Ohne Implementierung prüfen:

- Wo wird Protokollversion heute entschieden?
- Wo kann ein inkompatibler Client noch weiterkommen?
- Wo wird Sessionzustand erzeugt?
- Wo existieren Legacy-Fallbacks?
- Welche Pfade umgehen den v2-Handshake?
- Welche alten Messageformen werden noch akzeptiert?
- Sind Serverversion/Commit/supported versions überall konsistent?

Ergebnis:

```text
CURRENT_PROTOCOL_BOUNDARY
GAPS
LATER_CUT_ACTIONS
```

Keine neue Wire-Semantik erfinden.

---

# 12. Pflicht-Artefakte

Alle Ergebnisse werden AUSSERHALB des Produktrepositories gespeichert.

Zielordner:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prep\Discovery\2026-08-28\
```

Dieser Ordner ist Workflow-/Koordinationsmaterial.

Er gehört:

```text
NICHT in voice-stt-server
NICHT in canonical
NICHT in distributed
```

Erzeuge dort exakt:

```text
01_LEGACY_INVENTORY.md
02_RUNTIME_REACHABILITY_MAP.md
03_LEGACY_CUT_CANDIDATES.md
04_DOCUMENTATION_AND_REPOSITORY_CLEANUP_AUDIT.md
05_TEST_AND_PROTOCOL_GAP_AUDIT.md
06_DISCOVERY_REPORT.md
```

---

# 13. Inhalt der Artefakte

## 13.1 01_LEGACY_INVENTORY.md

Tabelle:

```text
ID
Datei
Symbol/Bereich
Kategorie
Risiko
Nachweisqualität
Runtime-erreichbar JA/NEIN/UNKLAR
aktuelle Funktion
kanonischer Ersatz
Wake-Word-Zone JA/NEIN
empfohlene spätere Aktion
Evidence
```

Wake-Zone nur inventarisieren:

```text
EXCLUDED_WAKEWORD_ZONE
```

ohne weitere Bewertung.

## 13.2 02_RUNTIME_REACHABILITY_MAP.md

Für relevante Nicht-Wake-Legacypfade:

```text
Entry point
→ Adapter
→ Domain/Runtime
→ Seiteneffekt
→ Rückweg/Event
```

Besonders:

- alte Sessionpfade;
- v1 Trigger;
- Source-Merge;
- Modeautorität;
- additive Extension;
- finalizing-Reste.

## 13.3 03_LEGACY_CUT_CANDIDATES.md

Gruppiert:

```text
A. REMOVE_CANDIDATE
B. MIGRATION_CANDIDATE
C. KEEP_COMPATIBILITY
D. STILL_ACTIVE_REQUIRED
E. PUBLIC_LIBRARY_API_OUT_OF_SCOPE
F. UNKNOWN_NEEDS_REVIEW
G. EXCLUDED_WAKEWORD_ZONE
```

Für A/B zusätzlich:

```text
spätere konkrete Änderung
betroffene Dateien
benötigte Tests
Abhängigkeiten
erwartetes Risiko
```

Noch nichts ausführen.

## 13.4 04_DOCUMENTATION_AND_REPOSITORY_CLEANUP_AUDIT.md

Zwei Bereiche:

```text
A. Dokumentationslücken/Widersprüche
B. Repository-/Ablage-/Ordnungsfunde
```

Immer konkrete spätere Aktion + Zielpfad.

## 13.5 05_TEST_AND_PROTOCOL_GAP_AUDIT.md

Enthält:

```text
Legacy-Tests
stale Fixtures/Testdoubles
fehlende Cut-Guards
aktuelle Protocol Boundary
Protocol-Gaps
empfohlene spätere Tests
```

Keine Wake-Word-Testbewertung.

## 13.6 06_DISCOVERY_REPORT.md

Executive Summary:

```text
STATUS: DISCOVERY_COMPLETE | PARTIAL | BLOCKED

Basis-SHA
Basis-Tree
Discovery-Worktree
Produktworkingtree unverändert: JA/NEIN

Anzahl Funde je Kategorie
Top-10 wahrscheinlich relevante SRV-070-Cuts
Top-Dokumentationsfunde
Top-Ordnungsfunde
Top-Test-/Protocol-Gaps

Wake-Word-Zone vollständig ausgeschlossen: JA/NEIN

Was kann voraussichtlich unabhängig von SRV-060 umgesetzt werden?
Was muss zwingend nach SRV-060 erneut geprüft werden?
Welche historischen Legacy-Map-Funde sind heute noch gültig?
Welche sind inzwischen veraltet?

Empfehlung für die nächste Prep-Runde:
konkreter, enger Implementierungsumfang
```

---

# 14. Evidence-Standard

Jeder wesentliche Fund muss reproduzierbar sein.

Nutze je nach Fall:

```text
rg / git grep
Callsite-Suche
Import-/Exportprüfung
Testsammlung
AST-/Symbolsuche
git log / git blame nur wenn Herkunft relevant ist
```

Keine riesigen Rohoutputs in die Artefakte kopieren.

Stattdessen:

```text
Befehl
kurzes Ergebnis
Datei/Symbol
Interpretation
```

Wenn etwas nur vermutet wird, klar `UNCERTAIN` markieren.

---

# 15. Keine Implementationsempfehlung ohne Zielort

Jede spätere Änderungsempfehlung muss konkret sagen:

```text
was
wo
warum
welcher Zielpfad / welches Zielsymbol
welcher Testnachweis
```

Nicht:

```text
"cleanup docs"
"remove legacy"
"refactor config"
```

Sondern konkret, z. B.:

```text
MOVE:
docs/foo.md
→ docs/.archiv/.../foo.md

Grund:
nur historischer Migrationsstand, wird von aktueller Referenzdoku widersprochen.
```

oder:

```text
REMOVE_CANDIDATE:
api_fastapi_server/server.py :: RealtimeSession
Grund:
keine Produktionsinstanziierung auf gepinnter Basis,
RecorderBackedRealtimeSession ist einziger aktiver Pfad.
Vor Umsetzung erneut gegen finalen SRV-060-Stand prüfen.
```

---

# 16. Abschlussprüfung

Vor Rückgabe:

```powershell
git -C "P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\prep-srv-070-discovery" status --short
git -C "P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\prep-srv-070-discovery" rev-parse HEAD
```

Muss ergeben:

```text
HEAD = c901cda3f2c19eeb78c468524161728498b6e27e
working tree = clean
```

Keine Produktdatei verändert.

Kein Commit.

Kein Push.

---

# 17. Chat-Rückgabe

Am Ende nur kompakt melden:

```text
STATUS
Basis-SHA/Tree
Discovery-Worktree clean: JA/NEIN

Artefakte erstellt:
vollständige Pfade zu 01–06

Funde je Kategorie
Wake-Word-Zone ausgeschlossen: JA/NEIN

Top-5 sichere Kandidaten für spätere Umsetzung
Top-5 Punkte, die Root/Koordination prüfen sollte
Top-5 Ordnungs-/Dokufunde

Produktänderungen: KEINE
Commit: KEINER
Push: NEIN
```

Dann stoppen.
