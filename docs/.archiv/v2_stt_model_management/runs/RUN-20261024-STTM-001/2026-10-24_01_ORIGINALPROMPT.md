# Agentenauftrag – VoiceSTT V2: Laufende Kroko-Arbeiten abschließen und einheitliche Modellverwaltung umsetzen (Architektur vorbereiten, Großrefactoring später)

**Auftragsdatum:** 2026-10-24  
**Repository:** `https://github.com/marcosudau-vps/voice-stt-server`  
**Verbindlicher Zielbranch für die spätere Integration:** `feat/v2-unified-kroko`  
**Neuer ausführender Arbeitsbranch:** `work/v2-stt-model-management-integration`  
**Arbeitsaktenwurzel:** `docs/.archiv/v2_stt_model_management/`  
**Run-ID:** `RUN-20261024-STTM-001`  
**Auftragstyp:** eigenständige, implementierende Mehrphasenarbeit mit vollständiger Evidenz und abschließendem Review-PR; **inhaltlicher Abschluss der begonnenen Kroko-/Modellverwaltungsarbeiten hat Vorrang vor Strukturkosmetik**. **Kein automatischer Merge, Release oder Deployment.**
**Beilage (Zielbild, nicht aktueller Pflichtumfang):** `VoiceSTT_V2_Zielarchitektur_Serverpakete_SPÄTERE_ARBEITSREIHE_2026-10-24.md`. Diese Datei ist ausschließlich die **langfristige Orientierung** für später separat zu beauftragende Server-Umstrukturierung. Ist→Soll-Zeilen, neue HTTP-/Session-/Scheduler-Unterpakete und die Zerlegung von `api_fastapi_server/server.py` sind **keine Abnahmekriterien dieses Agentenlaufs**.

## 0. Arbeitsweise: Lies dies vollständig und führe es aus

Du bist der **ausführende Implementierungsagent**, nicht nur ein Planungs- oder Analyseagent. Führe den **fachlichen Gesamtauftrag** im gegebenen Repository so weit wie belegbar durch: Ausgangsstände prüfen, Integrationsbranch herstellen, **Kroko-PRs und bestehende Restintegration abschließen**, gemeinsame STT-Modellverwaltung, Downloads, API/Settings, allgemeinen Status und Lazy-Reload-Kommunikation umsetzen, testen, dokumentieren, eine prüfbare Arbeitsakte führen und einen PR zur unabhängigen Abnahme bereitstellen. **Die großflächige Server-/Paket-Neuordnung ist ausdrücklich ausgeklammert.**

**Wichtige Grenzen:**
- Implementiere alle unabhängig realisierbaren Anforderungen vollständig. Unbekannte oder nicht nachgewiesene Kroko-Lizenz-, Entitlement-, Download- oder Redistributierungsverträge **niemals erfinden oder simuliert freischalten**.
- Ein technisch sauber implementiertes, aber wegen nicht verfügbarer externer Lizenznachweise gesperrtes Feature ist **CONDITIONAL/BLOCKED**, nicht COMPLETE.
- Bestehendes funktionierendes Verhalten und eingefrorene V2-Wire-Verträge respektieren. Keine zweite Serverautorität, Download-Queue, Settings-Persistenz oder Logginginfrastruktur schaffen.
- Bei fehlenden externen Berechtigungen **weiter an sämtlichen unabhängigen Arbeitspaketen arbeiten**, nicht den gesamten Auftrag vorschnell abbrechen. Die tatsächlich unüberwindbaren Teile mit genauer Evidenz benennen.
- Interne Detailentscheidungen darfst du innerhalb der hier definierten Invarianten selbst treffen. Keine Rückfrage zu bereits entschiedenen Sachverhalten. Bei Widersprüchen: **ausdrücklich beschlossene Produktregeln > bisherige Architekturentwürfe > Beispielpayloads**; bestehende unveränderte Verträge sind mitzuberücksichtigen.
- Keine unbelegte Erfolgsmeldung; kein Deployment/Release, kein unerlaubtes Netzwerkexperiment an Drittsystemen, keine echten Pro-Lizenztests ohne ausdrücklich autorisierten Prüfzugang.
- **Scope-Vorrang:** funktionale Fertigstellung und Betriebsstabilität > kleine unmittelbar erforderliche Modulgrenzen > zukünftige Paketästhetik. Keinen eigenständigen Struktur-Gate, keine pauschale Migration des Hauptservers und keine Verlagerung der AP-SRV-/Protokollv2-Module.
- **Erlaubte Strukturverbesserung:** ausschließlich ohnehin berührte, fachlich klar trennbare Modellverwaltungsbausteine, ohne zusätzliche allgemeine Migrationswelle. Neue serverseitige Modellkomponenten bevorzugt unter `voice_stt_server/models/` anlegen (das spätere Zielpaket), sofern dies ohne Abhängigkeitszyklen oder unverhältnismäßiges Packaging-/Importrefactoring gelingt. Andernfalls den vorhandenen Modulort beibehalten und eine konkrete spätere Extraktion dokumentieren. Nicht nur zur Erfüllung des Architekturbaums neue Dateien anlegen.
- **Keine vollständige Ist→Soll-Pflicht:** das separate Architekturpapier ist ein Architektur-Backlog für eine **künftige eigene Arbeitsreihe**. Nicht laufende Modellarbeiten unterbrechen, um `api_fastapi_server/server.py`, HTTP-Router, Sessions, Scheduler, V2-Protokoll, Logging, Settings-Control-Plane, Browseroberfläche oder Legacy-Entrypoints nach `voice_stt_server/` zu migrieren.
- **Keine künstlichen Abschlussblocker** durch nicht beauftragte strukturelle Arbeiten. Stattdessen für die spätere Umstrukturierungsreihe konkrete Beobachtungen, Abhängigkeiten, Stellen und Empfehlungen als gesonderte Übergabe erfassen.

**Begleitdokumente:**
- `VoiceSTT_V2_Modellverwaltung_Beschlussstand_2026-10-24.md`: **verbindlicher fachlicher Beschlussstand**, vollständig lesen.
- `VoiceSTT_V2_Zielarchitektur_Serverpakete_SPÄTERE_ARBEITSREIHE_2026-10-24.md`: **langfristige Strukturorientierung**, vollständig lesen; die dort dargestellten umfassenden Move-/Migrationstabellen gelten **nicht als aktuelle Implementierungsanforderung**.

Der Agentenauftrag bleibt bezüglich der fachlichen Anforderungen selbstständig verwendbar. Bei widersprüchlichen Formulierungen hat die ausdrückliche **Scope-Reduktion dieses Auftrags** Vorrang vor älteren Struktur-/Phasenempfehlungen; die fachlichen Kroko-, Modell-, Sicherheits-, Wire- und Settings-Invarianten bleiben unverändert.

## 1. Ist-Stände und Pull Requests: zuerst verbindlich prüfen

**Bisher nachgewiesener Stand vom 24.10.2026 (erneut frisch mit `git fetch` / GitHub validieren):**

| Referenz | Stand | Bedeutung |
|---|---|---|
| Zielbasis `feat/v2-unified-kroko` | `acdffc7042357cb8ae5e47961e42b78a25bd902c` | Bestehender Kroko-Integrationszweig |
| PR #12 `feat/v2-unified-kroko-ap020` → `feat/v2-unified-kroko` | `454e497fff4c0b1f466de03f536a13cf7bce522a` | Draft, AP-KR-020 offiziell BLOCKED an unabhängigem Lizenz-/Modellrechtevertrag |
| Weiterführender Arbeitsbranch `work/ap-kr-020-restintegration` | `03b813f27b4f707758ca14bdd1cf5d7d59edeb88` | **7 Commits voraus** gegenüber PR-#12-HEAD; enthält weitergehende Bootstrap-, Native-Status-, Owner-Prozess-, Lizenz- und FastAPI-Arbeit |
| PR #13 `feat/v2-unified-kroko-catalog` → `feat/v2-unified-kroko` | `58a85b7df0e414bff59b66789748077c0f7ff559` | Positiv überprüfter, noch offener Kroko-Katalog mit 124 Metadateneinträgen; damalige CI-/Abnahmelage erneut prüfen |

Verweise:
- `https://github.com/marcosudau-vps/voice-stt-server/pull/12`
- `https://github.com/marcosudau-vps/voice-stt-server/pull/13`
- `docs/.archiv/kroko_unified_runtime_v2/`
- `docs/kroko-model-catalog.md` (auf PR-#13-Branch)

**Integrationsstrategie (konkret):**
1. Git-Status, Fetch, Commit-SHAs, Ancestor-Beziehungen, PR-/CI-/Reviewstatus und vorhandene uncommittete Änderungen prüfen und dokumentieren. Keine fremden Änderungen verwerfen.
2. Den neuen Branch `work/v2-stt-model-management-integration` **vom aktuellen** `feat/v2-unified-kroko` erstellen. Falls dieser Branch inzwischen existiert: seine Basis/Historie sicher prüfen; nie hart resetten.
3. **Die weitergehende Arbeit `work/ap-kr-020-restintegration` integrieren**; sie enthält bereits die PR-#12-Historie. PR #12 daher nicht nochmals separat cherry-picken. Unterschiede zum offiziellen #12-HEAD und deren Test-/Reviewstand explizit dokumentieren.
4. Die unabhängige PR-#13-Katalogarbeit integrieren, ohne die ursprünglichen 124 Datensätze, Portal-UUIDs oder Integritäts-/Rechte-Sperren umzuschreiben. Konflikte fachlich auflösen, Merge-Commits bzw. nachvollziehbare Integrationshistorie bevorzugen.
5. Baseline-Tests **vor und nach** den Integrationen ausführen und Abweichungen dokumentieren.
6. **PR #12 und #13 weder blind mergen noch löschen/schließen oder umbauen.** Die Original-PR-Historie bleibt für die Abnahme nachvollziehbar. Ziel ist ein **neuer prüfbarer Integrations-PR** aus `work/v2-stt-model-management-integration` gegen `feat/v2-unified-kroko`. Ob ursprüngliche PRs danach als ersetzt geschlossen oder gemergt werden, ist eine separate Reviewentscheidung.
7. **Kein** direkter Merge auf `feat/v2-unified-kroko`, `main` oder andere geschützte Branches ohne ausdrückliche Benutzerfreigabe.

Bei geänderten Branch-HEADs nicht stur alte SHAs auschecken, sondern tatsächliche Stände ermitteln und die Abweichung in der Akte dokumentieren.

## 2. Vor jedem Code: Pflichtlektüre und Quellen

Lies die aktuellen Versionen und dokumentiere relevante Architektur-/API-/Settings-Konventionen:

**Projektregeln**
- `AGENTS.md`
- `docs/.archiv/README.md` – einschließlich Registerpflicht, Datumskonvention, Gesamtplanung **vor Code**, Soll/Ist und Abweichungen
- `docs/module-map.md`
- `VoiceSTT_V2_Zielarchitektur_Serverpakete_SPÄTERE_ARBEITSREIHE_2026-10-24.md` (Beilage, **nur** Orientierung für spätere Strukturreihe)
- `VoiceSTT_V2_Modellverwaltung_Beschlussstand_2026-10-24.md` (Beilage, verbindliche fachliche Beschlüsse)
- `build/BUILD.md`
- `docs/release-process.md`
- `docs/testing.md`

**Modell-, Konfigurations- und HTTP-Verträge**
- `docs/configuration.md`
- `docs/stt-model-management.md`
- `docs/transcription-engines.md`
- `docs/client-development/06-http-api-und-authentifizierung.md`
- `docs/client-development/09-betriebsmodi-und-serverkonfiguration.md`
- `docs/structured-logging.md`
- `docs/2026-10-22_kroko-unified-runtime-v2.md`
- `docs/kroko-model-catalog.md` nach Katalogintegration

**Codeautoritäten**
- `VoiceSTT_server/stt_model_management.py`
- `VoiceSTT_server/operations.py`
- `VoiceSTT/transcription_engines/model_resolver.py`
- `VoiceSTT/transcription_engines/_model_utils.py`
- `VoiceSTT/transcription_engines/faster_whisper_engine.py`
- `VoiceSTT/transcription_engines/kroko_onnx_engine.py`
- `VoiceSTT/kroko/models.py`, `VoiceSTT/kroko/catalog.py`
- `VoiceSTT/kroko/license_runtime.py`, `owner_process.py`, `supervisor.py`, `native_status.py`
- `api_fastapi_server/server.py`
- `api_fastapi_server/settings_control.py`
- `api_fastapi_server/protocol_v2/schema.py` und Handshake/Connection/Events/Snapshot
- `VoiceSTT_server/event_logging.py`

**Relevante AP-Akten**
- `docs/.archiv/kroko_unified_runtime_v2/AP-KR-010/`
- `docs/.archiv/kroko_unified_runtime_v2/AP-KR-020/`
- `docs/.archiv/kroko_unified_runtime_v2/CATALOG/`
- insbesondere `2026-10-22_SCHNITTSTELLEN_LIFECYCLE.md` und die jüngeren Restintegrations-/Übergabeberichte.

Achte auf **bestehenden Code und bereits implementierte Funktionalität** vor jedem neuen Modul oder Endpunkt. Suche relevante Aufrufer und Tests. Notiere für jede zu ersetzende/ergänzende Funktion Ist-Zustand, Zielzustand, Abhängigkeiten, Risiken und Testbezug.

## 3. Verbindliche Arbeitsakte – schon vor der ersten Implementierung

**Ablageorte (feste Pfade):**

```text
docs/.archiv/
  README.md                                      # Aktion in bestehendes Register eintragen
  v2_stt_model_management/
    2026-10-24_GESAMTPLAN.md                     # VOR erstem Umsetzungsschritt
    2026-10-24_IST_ARCHITEKTUR_UND_BRANCHES.md
    2026-10-24_ENTSCHEIDUNGEN_UND_VERTRAEGE.md
    2026-10-24_UMSETZUNGSVERGLEICH.md            # nach Implementierung
    2026-10-24_ABWEICHUNGEN.md                    # ausdrücklich auch Nichtrealisierbares
    2026-10-24_ABSCHLUSSBERICHT.md
    2026-10-24_SERVERSTRUKTUR_FOLGEARBEIT.md             # gesondertes Architektur-Backlog, kein Move-Gate
    runs/
      RUN-20261024-STTM-001/
        2026-10-24_01_ORIGINALPROMPT.md          # DIESER AUFTRAG 1:1
        2026-10-24_02_VERLAUF.md                  # fortlaufende chronologische Journal-Einträge
        2026-10-24_03_ERGEBNISSE.md               # tatsächliche Änderungen/Dateien
        2026-10-24_04_EVIDENZ_INDEX.md            # Nachweismatrix
        2026-10-24_05_ABSCHLUSSBERICHT.md
        evidenz/
          2026-10-24_GIT_UND_PR_BASIS.md
          2026-10-24_TESTMATRIX.md
          2026-10-24_API_SETTINGS_CONTRACTS.md
          2026-10-24_SECURITY_UND_LIZENZGATES.md
          2026-10-24_RELEASE_UND_PACKAGING_STATUS.md
```

Wenn die tatsächliche Ausführung an einem anderen Kalendertag startet, für **neu angelegte** datierte Dokumente das tatsächliche Erstellungsdatum verwenden, aber die feste Run-ID und den Run-Ordner beibehalten. Wenn das Repo bereits ein genaueres Run-Akten-Schema verlangt, dessen zusätzliche Pflichtfelder ergänzen; diese mindestens geforderten Artefakte müssen aber eindeutig auffindbar bleiben.

**Unbedingt:**
- Den vollständigen Originalprompt **wortgetreu** in `2026-10-24_01_ORIGINALPROMPT.md` ablegen. Nicht umformulieren, zusammenfassen oder nur verlinken. Falls die Einreichungsumgebung den Originalprompt nicht automatisiert als Datei herausgibt, den vollständigen Nachrichtentext unverändert übernehmen und diesen Umstand kennzeichnen.
- Zuerst Register + Gesamtplan + Ist-Inventar anlegen und committen, **erst danach** produktiven Code ändern.
- Journal laufend nach jedem Teilabschnitt fortschreiben: Zeit/Branch/Commit, Tätigkeiten, Entscheidungen, Dateien, Tests, Ergebnisse, offene Risiken. Kein nachträglich erfundener Ablauf.
- Evidenzen enthalten **exakte** Kommandos, Ausführungsumgebung, Testanzahl, Exitcodes, Commit-SHAs, CI-URLs und relevante Fehlermeldungen (redigiert); Rohlogs nur, wenn klein, sicher und nützlich. Keine riesigen oder geheimen Logs ins Git.
- Laufende Aufwände/Artefakte in der Run-Akte und die **projektweite** abschließende Soll/Ist-/Abweichungsakte müssen übereinstimmen.
- In den Abschlussberichten jede Anforderung mit `PASS`, `PARTIAL`, `BLOCKED`, `FAIL` oder `NOT_RUN` und Evidenzreferenz versehen. Ein einzelnes synthetisches Testergebnis ist kein Nachweis für reale Native-/Lizenz-/Buildqualifikation.
- Wenn nicht sämtliche freigegebenen Anforderungen nachgewiesen wurden, niemals `COMPLETE` behaupten; `REVIEW_READY_WITH_BLOCKERS`, `PARTIAL` oder `BLOCKED` korrekt verwenden.
- Keine Dateien bloß zur Erfüllung einer Dateiliste leer anlegen; echte verständliche Inhalte schreiben. Maschinelle JSON-Nachweise bei Bedarf **lesbar formatiert**, menschenlesbare Namen statt opaker Ordnertitel, klare README-/Navigationsübersicht.

## 4. Fachliche Invarianten (nicht neu verhandeln)

### 4.1 Gemeinsame Modellautorität

- **Eine gemeinsame serverweite STT-Modellverwaltung für Faster-Whisper und Kroko**, keine getrennten unabhängigen Manager.
- Gewünschte/konfigurierte Final- und Realtime-Modelle bleiben serverweit, keine per-Client-Modellwahl.
- Produktkatalog ≠ lokal installiert ≠ strukturell validiert ≠ `LOAD_VERIFIED` ≠ technisch nutzbar ≠ lizenziert ≠ für Downloads berechtigt ≠ effektiv ausgewählt ≠ im RAM geladen.
- Die vorhandenen Zustandsnamen `DISCOVERED`, `VALIDATED`, `LOAD_VERIFIED`, `MINIMUM_READY` berücksichtigen.
- OpenWakeWord hat eine separate Katalogautorität; nur die allgemeine Serverstatusprojektion kombiniert die Ergebnisse.

### 4.2 Recovery und Laufzeit

- **Bestehende Recovery-Semantik unverändert bewahren:** `recovery_priority`, konfigurierte Final-/Realtime-Auswahl, `MINIMUM_READY`, fallback eligibility, Last Known Good und Rollback.
- Normale Inventaraktualisierung **ohne** Downloads und **ohne** eigenmächtigen Scheduler-/Modellwechsel. Die heute teils gekoppelte `refresh()`-Operation sauber in Inventory und ausdrücklich orchestrierte Runtime-/Recovery-Neubewertung entflechten; alte APIs funktional kompatibel führen, soweit die beschlossenen Regeln dies zulassen.
- Bestehendes manuelles `load`/`unload`, Auto-Idle-Unload (Default **3600 Sekunden**), spätere Lazy-Nachladung und Kroko-Besitzerprozess-Wechsel erhalten. Entladen ≠ Löschen.
- Erfolgreiche Modellinstallation selektiert/aktiviert/lädt **nicht von sich aus** ein anderes Final-/Realtime-Modell; bestehende Start-/Recovery-Regeln bleiben weiterhin maßgeblich.

### 4.3 Kroko Pro: Runtime/Key/Clientzugriff

- Eine gemeinsame native Kroko-Besitzerprozess-/Runtimeinstanz; keine nativen Parallel-Pro-Engines oder Keyübernahme durch Clients.
- `kein Server-Kroko-Key ODER kroko_force_community=true` ⇒ Community. Nur bei Server-Key, nicht erzwungener Community **und belegter Lizenzqualifikation** kann Pro aktiviert werden. Kein unqualifizierter Pro-Zustand.
- Native Umschaltungen erfordern ggf. kontrollierten Besitzerprozess-Generationswechsel. Bei ungültigen/veralteten/entzogenen Qualifikationen sicherer Community-Fallback, ohne die gewünschte Betreiberkonfiguration als Fallback zu überschreiben.
- `kroko_pro_access_public=true` ⇒ bei tatsächlich aktivierter Pro-Runtime allgemeiner Pro-Zugriff für Clients.
- Sonst Pro-Zugriff nur durch **separat konfigurierte serverseitige Pro-Zugangskennung oder separat validierten clienteigenen Kroko-Key**; Admins dürfen Pro zugreifen. Client-Key ist ausschließlich Zugriffsberechtigung, **niemals Server-Native-Key oder automatischer Download-Key**.
- Ungültiger ausdrücklich übermittelter Client-Key darf nicht autorisieren. Bei öffentlichem Pro-Zugriff wird ein mitgelieferter Client-Key für die Freigabeentscheidung ignoriert.
- Secrets/Providerantworten nicht in Events, Status, HTTP-Projektionen, Tracebacks, Artefakten oder Arbeitsakten offenlegen.
- Native On-Premise-Lizenz-API, externe Portal-API und Katalog-Metadaten sind **verschiedene** Verträge. Kein ungeprüfter Schluss von einem zum anderen.

### 4.4 Downloads: einheitlich für beide Engines

- **Ein** asynchroner, serververwalteter Jobmanager für Kroko/Faster-Whisper.
- Manuelle Downloads nur durch Admin und ohne automatische Aktivierung.
- Automatische Downloads Default **aus**, nur für ausdrücklich ausgewählte Modell-IDs, zusätzlich enginespezifische **harte Bezugs-, Integritäts- und Berechtigungsgates**.
- Der globale Auto-Download-Schalter ist lediglich eine Freigabe; **nie** „alle Modelle herunterladen“.
- Trigger nur beim Serverstart sowie bei einer Änderung der expliziten Modell-Auswahlliste/Freigabe. Normales Inventar-`refresh` startet **keine** Downloads. Kein endloses automatisches Retry nach Fehlern; erneut nur explizit oder beim nächsten regulären Serverstart.
- Ein Modell nicht parallel doppelt laden/installieren; derselbe fachliche Job kann Ursprünge `manual` und `automatic` erhalten.
- Zustände: `queued`, `downloading`, `verifying`, `installing`, `completed`, `failed`, `cancelled`.
- **Nur `queued` ist stornierbar.** Ab atomarem Start `downloading` laufen Transfer/Prüfung/Installation regulär; nachträgliche Nutzerstornierung `409`. Beim Entfernen aus Auto-Auswahl dürfen nur reine wartende Auto-Jobs entfallen. Laufende und bereits installierte Modelle bleiben.
- Serverneustart **Variante A**: keine persistente Jobqueue, keine Bytefortsetzung/HTTP-Range-Resumes; unvollständige `.part`-Stände sicher bereinigen, abgeschlossene verifizierte Installationen erhalten, manuelle Jobs nicht automatisch erneut erzeugen, Auto-Auswahl beim Neustart neu auswerten.
- Genaue, redigierte Jobstatusdaten (ID, Modell, Engine, Zustand, Herkunft, Zeitstempel, Bytes/Prozent oder `null`, Fehlercode). Begrenzte flüchtige Historie, zunächst max. **ein aktiver Transfer**; keine unbegrenzten RAM-Listen oder Eventflut.
- Atomare, nach Quellbindung, SHA-256, Bytecount und Produktrechten abgesicherte Installation; `.part`/temporäre Staging-Dateien, keine halbfertigen sichtbaren Installationen.
- Kroko: vorhandenen 124er-Katalog **nicht** als Downloadfreigabe interpretieren; der Katalog-PR dokumentiert, dass für viele Einträge Integritäts- und Berechtigungsbelege fehlen und die Downloadpläne derzeit blockiert sind. Kein ungeprüftes Liveportal-Scraping oder Authentifizierungs-Raten.
- Faster-Whisper: der untersuchte `ProductModel`-Katalog ist bislang `LOCAL_ONLY_UNPINNED`, `artifact_kind="directory"`, `provisioning_allowed=False`. Entwickle einen verifizierbaren, versionierten Bezugs-/Datei-/Verzeichnis-Installationspfad mit klaren Sicherungen; **nicht** stillschweigend implizite Downloads durch Enginebibliotheken reaktivieren.

### 4.5 Verwaltete/externe Ablagen und Löschung

- Server-eigene Modelle in verwalteten Ablagen aus `data_root_path`, bestehende Defaults:
  - `<data_root_path>/models/stt/fasterwhisper/`
  - `<data_root_path>/models/stt/kroko_asr/`
- Konfigurierte externe Pfade ausschließlich **lesen**, prüfen und zum Laden verwenden; nie dorthin schreiben, herunterladen, überschreiben oder löschen. Bisheriges `provisioning_roots()` prüft schreibbare Custom-Pfade: **korrigieren**. Explizite Provisioning-Ziele nur als eindeutig serververwaltete und sichere Ablage erlauben.
- Modelldateien unveränderlich behandeln; kein inhaltliches Umarbeiten.
- Adminlöschung nur für konkrete bekannte **verwaltete Installation** (`installationId`), nie per frei übergebenem Dateipfad; externe Modelle niemals über Verwaltungs-API löschen.
- Löschen verweigern bei konfiguriertem Final/Realtime, effektivem Recovery/Fallback, geladen/in Benutzung, laufender Session/Worker-/Modellwechsel, wartendem/laufendem Installationsjob oder anderen Referenzen. Verständlicher `409`, kein versteckter Wechsel, keine Konfigurationsänderung. Pfad-Traversal, Symlinks, Race und TOCTOU absichern, einschließlich Mehrfachinstallation eines Produkts.

### 4.6 Allgemeiner Serverstatus

Neuer allgemeiner **`GET /api/v2/server/status`**, keine Kroko- oder STT-Spezialroute. Ein read-only, serverautoritativer Snapshot aus bestehenden Zustandsautoritäten:
- Version, Commit, Distribution/Runtimeidentität/Instanz, Startzeit/Uptime, allgemeine Health und STT-Readiness.
- Konfigurierte/geforderte **und** effektiv aufgelöste Final-/Realtime-Modelle getrennt; geladen/entladen/Ladefehler/Fallbackgrund; absichtliches Unload ist kein pauschaler Serverausfall.
- Modelle aus Faster-Whisper, Kroko, OpenWakeWord in sinnvollem Umfang; Wake-Word-Autorität unangetastet.
- Download-/Managementübersicht; redigierte Serverkonfiguration.
- Öffentliche, sensible Informationen herausfilternde Clientprojektion und ggf. erweiterte Adminprojektion; niemals Geheimnisse, ungeschützte Dateipfade oder rohe Lizenzantworten.
- `/health`, `/api/v2/info`, `/api/models/management`, `/api/models/active`, `/api/models/lifecycle`, `/api/v2/settings/server` bleiben bestehen.

### 4.7 Frühe Client-Rückmeldung bei entladenen Modellen – PFLICHT

**Reales Problem:** Nach Idle-Unload kann die erste V1-Verbindung während langsamen Model-Lazy-Loads keine verwertbare rechtzeitige Serverantwort erhalten und auf Clientseite durch Handshake-/Connection-Timeout scheitern. V2 separat prüfen.

**Sollverhalten:**
- Client erhält **vor einem potenziell langen blockierenden Modellload** eine sichere, protokollkonforme Rückmeldung, dass Transport/Anfrage angekommen ist; zwischen **angenommen**, **Modell lädt**, **STT bereit**, **Ladefehler** wird eindeutig unterschieden.
- Während längerer Initialisierung kontrolliert fortführbares/zeitlich begrenztes Warten (Keepalive, Status oder bestehender Wartevertrag), ohne falsche Bereitschaft und ohne unendliches Hängen.
- Nach tatsächlichem Erfolg/Fehler eindeutige finale Rückmeldung; Berechtigungsfehler sauber getrennt. Ladefehler darf nicht als grüner Zustand erscheinen.
- Nachweislich wird das frühe Signal **tatsächlich gesendet**, bevor synchrone Modellarbeit den Event Loop blockieren kann.
- **V1 und V2 unabhängig charakterisieren**, eingefrorenes `api_fastapi_server/protocol_v2/schema.py` und seine Wire-Events **nicht beiläufig erweitern**. Bevorzugt bestehende Handshake-/Status-/Ping-/Keepalive-Mittel oder klar abgegrenzte zusätzliche HTTP-Readinesskommunikation, soweit dies den Client wirklich vor Timeout schützt.
- Ein HTTP-Statusendpunkt oder Admin-`/ws/logs` **allein** ist keine ausreichende Lösung für den verbindenden Client, wenn dieser den Zustand nicht rechtzeitig erkennen kann.
- Serverintegrations- und simulierte Clienttests für lange, erfolgreiche und fehlschlagende Reloads liefern. Für Änderungen am **separaten** Repository `marcosudau-vps/voice-stt-client` einen konkreten, datei-/vertragsscharfen Folgeauftrag bzw. PR vorschlagen; dieses andere Repository ohne gesonderte Berechtigung nicht eigenmächtig verändern. Kein „end-to-end fertig“ behaupten, solange zwingende Clientanpassungen offen sind.

## 5. Einheitliche API- und Settings-Verträge

### API – bestehende Konventionen beibehalten

Geplanter neuer Namensraum `/api/v2/stt/`, Payloads in `camelCase`, bestehender zentraler `admin_auth_error`-Guard, sichere Fehlercodes:

| HTTP | Zielroute | Verhalten |
|---|---|---|
| `GET` | `/api/v2/stt/models` | Katalog/Inventar, sichere öffentliche Projektion, bei Admin zusätzliche Details |
| `POST` | `/api/v2/stt/models/refresh` | Nur Inventar neu prüfen, ohne versteckten Download oder Wechsel |
| `POST` | `/api/v2/stt/models/{modelId}/download` | Admin-Job, `202` bei Annahme |
| `GET` | `/api/v2/stt/downloads` | Adminliste |
| `GET` | `/api/v2/stt/downloads/{jobId}` | Adminjobstatus |
| `POST` | `/api/v2/stt/downloads/{jobId}/cancel` | Admin, nur `queued`; sonst `409` |
| `DELETE` | `/api/v2/stt/installations/{installationId}` | Admin, sichere verwaltete Installation löschen |
| `GET` | `/api/v2/server/status` | allgemeiner Server-Snapshot, nicht STT-spezifisch |

Beispiele: `202` neu gequeued, `200` dedupliziert/bereits installiert, `409` Konflikt, `404` unbekannt, `422` valide Struktur aber fachlich unzulässig, `401/403` aus bestehendem Autorisierungssystem; differenzierte maschinenlesbare Fehlerobjekte.

Bestehende Admin-Modellrouten (`/api/models`, `/api/models/management`, `/api/models/refresh`, `/api/models/load`, `/api/models/unload`, `/api/models/active`, `/api/models/lifecycle`) müssen erhalten bleiben und **dieselbe** Authority nutzen. Legacy-Refresh darf keine unerwarteten Downloads mehr auslösen, muss aber die bisherige Recovery-/LKG-Vertragssemantik berücksichtigen.

Kanonische IDs: `modelId` (Katalogprodukt), `installationId` (bestimmte lokal vorhandene Kopie), `jobId` (flüchtiger Auftrag). Insbesondere **Kroko-Portal-UUID, bisherige Manifest-ID, Dateiname und native Lizenzmodell-ID nicht gleichsetzen**, sondern explizit, beweisbar und testbar abbilden.

### Settings – eine Persistenz, keine Parallelwelten

Beachte die vorhandene AP-SRV-050-Control-Plane:
- `GET /api/v2/settings/schema`
- `GET /api/v2/settings/server`
- `PATCH /api/v2/settings/server` mit `baseSettingsRevision`, atomarer Prüfung, `settingsRevision`, `requestedValue`/`effectiveValue`, `applyPolicy`, `settings_revision_conflict`, `settings_rejected`, persist-before-commit.
- Vorhandene Settings-Metadaten `scope`, `auth`, `type`, `constraints`, `defaultValue`, `applyPolicy`; `live` nur für künftige Einplanungen, nicht rückwirkend für laufende Downloads.

Persistierte Werte:
- bestehend `stt_auto_download_enabled: bool = false`
- neu `stt_auto_download_model_ids: list[str] = []`

V2-Projektion derselben Werte:
- `stt.autoDownload.enabled` (`bool`, `scope=server`, `auth=admin`, `applyPolicy=live`)
- `stt.autoDownload.selectedModelIds` (`string_list`, `scope=server`, `auth=admin`, `applyPolicy=live`)

Semantik:
`automatic_allowed = global_enabled AND modelId explicitly selected AND all product/engine/source/integrity/license/download gates satisfied`.

**Alte ODER-Regel `global OR engine OR model` muss weg.** Bestehende `stt_engine_settings` (`enabled`, `custom_paths` usw.) und `stt_model_settings` (`enabled`, `recovery_priority`) bleiben im Übrigen erhalten. Historische Auto-Download-Felder ohne stillschweigende Aktivierung behandeln; bei nötiger Migration deren Semantik sichtbar dokumentieren. Entwicklungsstände sind noch nicht produktiv etabliert: unnötige komplexe Altformatmigrationen vermeiden, aber gespeicherte Werte sicher und deterministisch handhaben.

Insbesondere `ServerSettings`, `config.yaml`, `RuntimeConfigStore`, `api_fastapi_server/settings_control.py`, `PATCH /api/config`, CLI/ENV und V2-Settings dürfen **keine unabhängigen konkurrierenden Schreib-/Revisionsautoritäten** für dieselben Einstellungen sein. Das Adapter-/Transaktionsmodell vor Implementierung begründen und anschließend testen.

Komplexe Engine-/Modell-Objekte nicht unvalidiert in die bestehende AP-SRV-050-Schemakontrolle einschleusen; dort gibt es bislang nur `int`, `float`, `bool`, `string`, `string_list`.

### Ereignisse und Status

**Kein zweites Eventsystem.** `VoiceSTT_server/event_logging.py`, der kanonische SQLite-first-Eventstore, `/api/logs/events` und `/ws/logs` existieren bereits. Wiederverwenden:
- Bestehende `models.loaded`, `models.unloaded`, `models.switched`, `models.load_failed`, `worker.failed`, `server.ready`, Kroko-Audit/License-Fallback-Events.
- Zusätzliche sparsame `stt.download.queued/started/completed/failed/cancelled` und ggf. notwendige Installations-/Löschereignisse; Daten ohne Secrets/URLs/unsichere Pfade.
- Feingranularer Fortschritt im Job-Snapshot, nicht tausend persistierte Byte-Events.
- Frozen `/ws/v2` nicht mit frei erfundenen Events erweitern; normale Clients besitzen keinen allgemeinen Admin-Logzugriff.

## 6. Begrenzt strukturieren, Zielarchitektur für später vorbereiten

**Dieses Kapitel begrenzt den Umfang ausdrücklich.** Die allgemeine Paketneuordnung in `VoiceSTT_V2_Zielarchitektur_Serverpakete_SPÄTERE_ARBEITSREIHE_2026-10-24.md` ist **eine gesonderte spätere Arbeitsreihe**, nicht Voraussetzung und nicht Gegenstand der aktuellen V2-Funktionsabnahme. Die bestehende produktive Modern-Server-Implementierung unter `api_fastapi_server/`, ihr Einstiegspunkt `VoiceSTT_server/server.py`, die `voice_stt_server`-Lazy-Export-Oberfläche und die Kernbibliothek `VoiceSTT/` müssen weiter funktionsfähig bleiben.

### 6.1 Erlaubter, sinnvoller Schnitt: direkt betroffene Modellverwaltung

Bei der Implementierung der **ohnehin notwendigen** einheitlichen Modellverwaltung darf eine überschaubare serverseitige Paketgruppe angelegt werden, bevorzugt an ihrem langfristigen Bestimmungsort:

```text
voice_stt_server/models/                  # nur fachlich benötigte Dateien erzeugen
    __init__.py
    contracts.py                         # gemeinsame Produkt-/Installations-/Job-/Snapshot-Typen, falls sinnvoll
    inventory.py                         # Katalog/Discovery/externe read-only Modellpfade/Validierung
    storage.py                           # ausschließlich verwaltete Installationen/Löschschutz
    downloads.py                         # gemeinsame Queue/Progress/Dedupe/Restart-A-Regeln
    manager.py                           # eine zentrale Manager-/Fassadenschicht
    runtime.py                           # NUR wenn bereits sicher entkoppelbar; sonst bestehende Servicefunktionen nutzen
```

**Kein Zwang, diese Dateien vollständig auszuschöpfen oder alle Altklassen zu verschieben.** Eine kompakte Aufteilung nach echter Verantwortung ist besser als ein breiter Move der gesamten bisherigen Modell-/Runtimeimplementierung. Insbesondere sind `STTModelManager`, `AtomicModelProvisioner`, `OperatorIntent`, `ModelSnapshot`, `ModelCandidate`, `ManagedModelRegistryView` und der `LocalModelRegistry`-Legacyadapter zunächst hinsichtlich ihrer tatsächlichen Aufrufer zu untersuchen. Eine einzige Autorität behalten und keine parallelen Registries erzeugen. Öffentliche/bisher intern verbreitete Pfade durch schlanke kompatible Importe oder Wrapper erhalten, falls Modellbestandteile umziehen.

**Abhängigkeitsgrenze:** Neue `voice_stt_server.models`-Komponenten dürfen nicht implizit die FastAPI-App initialisieren, keine Heavy-Runtime beim reinen `import voice_stt_server` laden, kein Session-/Nativeprozess-Owner werden und `VoiceSTT` nicht vom Server-Paket abhängig machen. Bei problematischen Imports oder mock.patch-Verträgen die in-situ Erweiterung bevorzugen und den späteren Umzug dokumentieren. `setup.py`/Package-Data und Entwicklungspakete bei tatsächlich neuen Unterpaketen testen.

### 6.2 Was ausdrücklich NICHT Teil dieses Laufs ist

- **Keine** allgemeine Migration/Leerung von `api_fastapi_server/`, `VoiceSTT_server/` oder `voice_stt_server/`.
- **Keine** Zerlegung der ca. 10.600 Zeilen von `api_fastapi_server/server.py` als eigenständiges Ziel; nur punktuelle, funktional notwendige Änderungen für Lizenz-/Modell-/Status-/Timeout-Integration.
- **Keine** neue Routerlandschaft, keine Massenauslagerung von `activation.py`, `segment_ledger.py`, `settings_control.py`, `protocol_v2/`, InferenceScheduler, SessionStore, allgemeinen Events oder Web-Assets.
- **Keine** Neuordnung von `VoiceSTT/core/`, kein Entfernen von Engines, kein pauschales Verlagern von Kroko-Build-/Native-Quellen, keine Beispiel-App-Migration.
- Keine neue öffentliche Importstrategie, kein CLI-/Docker-/Distribution-Entrypoint-Redesign. Besonders `/ws/v2` bleibt eingefroren.
- Nicht für die neue Modellverwaltung notwendige Legacycleanup-/Unbenutztheits-Projekte werden **nicht** mit erledigt; identifizierte Kandidaten für später aufnehmen.

### 6.3 Konkrete spätere Übergabe

Pflege innerhalb der Arbeitsakte **zusätzlich** eine kurze `2026-10-24_SERVERSTRUKTUR_FOLGEARBEIT.md`: dokumentiere die bei der Umsetzung tatsächlich gefundenen verbleibenden Kopplungen, doppelten Verantwortlichkeiten, unübersichtlichen Importpfade, notwendigen Kompatibilitätshüllen, relevanten Tests, Risiken und eine empfohlene **separate, phasenweise Umstrukturierungsreihe**. Verweise auf die beigefügte langfristige Ist→Soll-Karte. Diese Übergabe ist eine **Planung**, keine Pflicht, in diesem Lauf bereits alle beschriebenen Strukturänderungen umzusetzen.

## 7. Arbeitsphasen und Zwischenabnahme

Führe diese Phasen in Reihenfolge aus. **Jede Phase**: Arbeitsakten-Journal, dateibezogene Änderungen, fokussierte Tests, genaue Soll/Ist-Evidenz, Commit. Wenn Blocker nur Teilbereiche betrifft, weiter an unabhängigen Phasen.

**AP-STTM-000 – Baseline, Branchintegration, sichere Planregistrierung**
- Pflichtquellen lesen, Git-/PR-/CI-Status dokumentieren, Arbeitsakte samt Originalprompt anlegen, registrieren, datierten Gesamtplan vor Implementierung erstellen.
- Testbaseline auf Basis und nach Integration von #12+Restintegration+#13.
- Lizenz-/Native-/Katalog-Blocker als Gate-Matrix erhalten.

**AP-STTM-010 – Modellverantwortlichkeiten, punktuelle Strukturvorbereitung**
- Nur die wirklich modellbezogenen Module und Aufrufer charakterisieren; State-/Authority-Matrix und wichtige API-/Importgrenzen dokumentieren.
- Gemeinsame Modellverwaltung in funktional erforderliche Teile überführen oder erweitern, bevorzugt bereits unter `voice_stt_server/models/` **falls gefahrlos**. Bestehende Modellimporte und Paketverträge erhalten. Keine Pflicht zur vollständigen Verschiebung von `stt_model_management.py` oder `api_fastapi_server/server.py`.
- Doppelte Datenautoritäten vermeiden; bereits existierende Klassen, Recovery und Engine-Resolver verwenden statt neu implementieren.
- **Keine allgemeine Migration** der Server-, Session-, Scheduler-, Settings-, V2-Protokoll-, Logging- oder Web-Module. Spätere Strukturreihe getrennt dokumentieren.

**AP-STTM-020 – Inventar, Installationen und Downloadjobs**
- Einheitlicher Produkt- und Installationskatalog samt Herkunft (`managed`/`external`), stabile IDs, Snapshot/Validierung.
- Sichere verwaltete Storage-Grenzen, Löschprüfungen, Pfad-/Symlink-/Race-Tests.
- Asynchrone Queue, Zustandsautomat, Progress, Dedupe, Queued-only-Cancel, Neustartregel A, Fehlerbehandlung, Events.
- Faster-Whisper-Verzeichnisprovisionierung mit echter Quellen-/Integritätsbindung; Kroko-Gates strikt erhalten.
- Keine automatischen Aktivierungen allein durch Downloadabschluss.

**AP-STTM-030 – Settings und HTTP**
- Gemeinsame Settingsautorität, atomare Serverpatches, Recovery-kompatible Trennung von Refresh und Provisionierung.
- Neue `/api/v2/stt/...`-Routen, bestehende Admin-APIs kompatibel halten.
- `GET /api/v2/server/status` mit öffentlicher und ggf. Adminklusion; konsistente Autoritätsprojektion.
- Auth-/Schema-/Revision-/Persistenz-/No-Secret-/API-Tests.

**AP-STTM-040 – Kroko-Lizenz-/Clientzugriff und Runtimeintegration**
- Restintegrationscode gegen #12-BLOCKED-Akte unabhängig bewerten, Pro-/Community-Gates und native Prozessgenerationen qualifizieren.
- Betreiber-Server-Key, `force_community`, Modellrechte, Pro-public/client-owned-key/Passwort-Gate unter **einem** Native-Owner; keine dritte Lizenzautorität.
- Externe verifizierte Lizenz-/Downloadverträge nur implementieren, wenn tatsächlich dokumentiert/autorisiert. Sonst sichere Sperre + präzise Blockerevidenz statt Erfolgsbehauptung.
- Recovery/Last-Known-Good/Idle-Unload/Lazy-Recovery unter Parallelität regressionsfest.

**AP-STTM-050 – Verbindung beim Lazy-Reload**
- V1/V2 tatsächliche Handshake-Reihenfolge und blockierende Modellladungen charakterisieren.
- Frühzeitige Verbindung-/Lade-/Bereit-/Fehlerkommunikation nach Abschnitt 4.7 implementieren, ohne Frozen-Wire-Bruch.
- Langsame Ladefälle, Timeouts, Event-Loop-Antwortfähigkeit, Kroko-Ownergeneration, gleichzeitige Clientzugriffe testen.
- Wenn ein getrenntes Client-Repository technisch geändert werden **muss**, hierfür einen vollständigen konkreten Folgeauftrag mit Vertrag, Dateien, Tests und Abhängigkeit liefern, nicht fälschlich „komplett erledigt“ melden.

**AP-STTM-060 – Fachliche Bereinigung, Regression, Dokumentation, Übergabe**
- Alte doppelte Auto-Download-Auswertung/Registry-Pfade nur dort nach Referenznachweis bereinigen, wo die neue Funktionalität davon abhängt; **keine generelle Server- oder Enginebereinigung**.
- Fachreferenzen, Clientreferenzen, `docs/module-map.md`, `docs/configuration.md`, `docs/stt-model-management.md`, Kroko-Catalog/Runtime-Dokumentation, Test-/Release-Dokumentation aktualisieren.
- Falls Native-Buildinputs wirklich geändert: vollständige Patch-/Fingerprint-/Buildidentitäts- und Releasequalifikation beachten; keine alten Fingerprints für geänderte Bytes wiederverwenden.
- Gesamt-Test-/Sicherheitsmatrix, Soll/Ist, Abweichungen, beiden Abschlussberichten, CI-Status und Review-PR liefern. Zusätzlich die knappe `2026-10-24_SERVERSTRUKTUR_FOLGEARBEIT.md` mit klarer Trennung zu einer später gesondert beauftragten Architektur-Arbeitsreihe erstellen.

## 8. Nicht verhandelbare Test- und Security-Gates

**Automatisiert mindestens prüfen:**
1. Bereits bestehende Unit-/Contract-Suite (z. B. `python -m pytest -q tests/unit`) und fokussierte Dateien:
   - `tests/unit/test_stt_model_management.py`
   - `tests/unit/test_local_model_resolver.py`
   - `tests/unit/test_kroko_model_authority.py`
   - `tests/unit/test_kroko_catalog.py`
   - `tests/unit/test_kroko_unified_runtime.py`
   - `tests/unit/test_kroko_restintegration.py`
   - `tests/unit/test_settings_control_plane.py`
   - `tests/unit/test_settings_runtime_persistence.py`
   - `tests/unit/test_wakeword_catalog_api.py`
   - relevante FastAPI-/V1-/V2-Handshake-, WebSocket-, Multiuser-, Logging- und Lifecycletests.
2. Zusätzlich neue zielgerichtete Tests für alle oben genannten invarianten Szenarien und HTTP-Responsecodes, einschließlich jeder Jobtransitions- und Race-Grenze.
3. **Automatische Downloads:** beide Engines, leere Auswahl, globaler Schalter ohne Auswahl, Auswahländerung bei queued/started/completed, fehlende Berechtigung, nicht verfügbare Integrität, Neustart/`.part`, kein Retry-Loop, kein Download aus Refresh, kein Engine-Hintertürdownload.
4. **Dateisicherheit:** externe Ordner read-only; Sym-/Hardlink-/Traversal-/TOCTOU-Fälle, Mehrfachinstallation, laufender Ladevorgang, Rollback bei Fehl-Commit, beschädigte Bytes, fehlerhafte Redirectquelle, Größe/Hashabweichung, Löschung nur der konkreten verwalteten Installation.
5. **Settings:** `baseSettingsRevision`, konkurrierende Patches, persist-before-commit, no-change, Fehleratomarität, Legacy-API und V2-Adapter, altes Auto-Flag, Restart/Reapply.
6. **Kroko:** fehlender/ungültiger/entzogener/abgelaufener Lizenznachweis, erzwungene Community, keine Pro-Engine trotz Key allein, eine einzige Native-Owner-Instanz, Prozesswechsel, keine Secret-Leaks, keine unautorisierten Pro-Downloads, Client-Zugriffsfälle.
7. **Status:** `ready` vs. `sttReady` vs. `loaded`, gewünschtes vs. effektives Modell, Wake-Word-Teilansicht, öffentliche Redigierung, parallele Updates/Snapshot-Konsistenz.
8. **Client-Lazy-Reload:** in V1 und V2 künstlich verzögerter Load, erstes verwertbares Signal vor Clienttimeout, Laufzeitfortführung, echter Erfolg/Fehler, blockierungsfreier Event Loop, mehrere wartende Clients.
9. **Bestehende Regressionen:** normaler Modellwechsel, manuelles Unload/Load, Idle-Unload nach 3600-Sekunden-Policy (mit fake clock), Recovery-MINIMUM_READY, `recovery_priority`, Last Known Good und Kroko-Generationswechsel.
10. **Packagingsmokes:** `python -m pip check`, `python -m build` soweit verfügbar, `python -m compileall`, `git diff --check`, Import-/Wheelsmoke für **tatsächlich** hinzugefügte oder umgezogene Modellmodule; **keine Migrationsnachweise für nicht beauftragte Serverkomponenten**. Schwergewichtige native Linux/Windows-/RC-Tests, wenn nicht ausführbar, als `NOT_RUN`, nicht `PASS`.

**Tests dürfen synthetische Quellen/Modelldaten verwenden**, aber niemals synthetische Lizenzantworten als produktiven Pro-Nachweis darstellen. Sicherheitschecks zur Autorisierung sind vor Seitenwirkungen auszuführen. Redigierung in Logs und HTTP-Antworten explizit testen.

**Evidenzklassen:** `REAL_VERIFIED`, `INTEGRATION_VERIFIED`, `UNIT_VERIFIED`, `STATIC_REVIEW`, `SIMULATED`, `BLOCKED`, `NOT_RUN`. Jede reale Free-/Pro-, Lizenz-, Deploy- oder Plattformbehauptung mit passender Klasse versehen. Fehlende Providervereinbarungen nicht aus plausibler API-Struktur ableiten.

## 9. Änderungs- und PR-Hygiene

- Alle Änderungen auf `work/v2-stt-model-management-integration`; die beiden vorhandenen PR-Branches und Zielbranche nicht ungefragt verändern.
- Kleine verständlich bezeichnete Commits je Phase; vor jedem riskanten Runtime-/Nativeeingriff relevanten Teststand sichern.
- Keine echten Zugangsdaten, Sessiontokens, Portalrohantworten, privaten URLs, Modelldateien, Wheels, Secrets oder generierten Großlogs committen.
- Nicht die Dokumentation historischer AP-Läufe rückwirkend „korrigieren“; neue datierte Ergänzungen und Links.
- Wenn API-Verträge von den diskutierten Beispielnamen abweichen müssen, die konkrete technische Begründung **vor Implementierung** unter `2026-10-24_ENTSCHEIDUNGEN_UND_VERTRAEGE.md` dokumentieren, inklusive Kompatibilitätsfolgen.
- Dokumentation **für Nutzer und Entwickler auffindbar** strukturieren, insbesondere Ordnernavigation, Dateibenennung, klare Querverweise und gepflegte Beispiele.
- Betroffene README/Docstrings/tests auf die tatsächlich gewählten Namen aktualisieren; veraltete Beispielantworten nicht als aktuelle Produktverträge stehen lassen.
- Keine eigenmächtigen Änderungen an `main`, produktiven Secrets, Releases, Images, VPS-Deployments oder dem separaten Client-Repository.
- PR-Erstellung erfolgt **nach** Ergebnisprüfung und Aktenpflege. PR-Text enthält Zielbranch, Branchbasis, Ausgangs-PRs, exakten HEAD, Phasen-/Testmatrix, Blocker, Lizenz-/Sicherheitsgrenzen, verlinkte Arbeitsakte und Abnahmebedarf. **Kein Merge durch den Agenten.**

## 10. Verbindliches Abschlussformat

Erstelle die Abschlussakte vollständig und gib dem Auftraggeber zum Schluss **einen in sich verständlichen Bericht** mit genau diesen Sachverhalten:

1. **Ergebnisstatus:** `REVIEW_READY`, `REVIEW_READY_WITH_BLOCKERS`, `PARTIAL` oder `BLOCKED`; niemals unverdientes `COMPLETE`.
2. **Branch und PR:** exakter Commit SHA, URL des **neuen** Integrations-PR, Basisbranch; Zustand der ursprünglichen PR #12 und #13.
3. **Umsetzungsmatrix:** Jede Hauptanforderung und jedes AP-STTM-000…060 mit `PASS/PARTIAL/BLOCKED/FAIL/NOT_RUN`, konkret erledigter Funktion und Evidenzlink.
4. **Lizenz-/Providerblocker:** Genau benannter fehlender externer Eingang und sichere derzeitige Produktwirkung; keine vage pauschale Ausrede.
5. **Testergebnisse:** Kommandos, Zahlen, Umgebungen, CI-Status und eindeutige Trennung synthetisch/echt.
6. **Sicherheitsbefunde:** Secret-Redaction, externe Read-only-Pfade, Downloadgates, Delete-Races, Owner-Prozessgrenzen.
7. **Dokumentation und Arbeitsakte:** absolute Repo-relative Pfade zu Originalprompt, Journal, Evidenzindex, Soll/Ist, Abweichungen und Abschlussbericht.
8. **Verbleibende Aufgaben:** Nur konkret offene Punkte, inklusive vollständiger direkt ausführbarer Folge-Agentenprompts mit **fest eingetragenen Repo-Pfaden**, falls echte getrennte Folgearbeit nötig ist. Keine bloße Ankündigung, dass man einen Prompt später schreiben könnte.
9. **Abnahmegrenzen:** Welche Tests/Belege noch ausstehen und warum; kein unbelegter RC/Release-/Mergevorschlag.

**Erwartetes Hauptergebnis:** technisch integrierte, einheitliche serverseitige STT-Modellverwaltung **ohne umfassendes Server-Refactoring** einschließlich neuer Download-, API-, Settings-, Serverstatus- und Lazy-Reload-Funktionen; vorhandene Kroko-PR-Arbeit korrekt integriert; vollständige prüfbare Arbeitsakte und Review-PR. **Dort, wo Kroko-Provider-/Lizenz-/Downloadrechte aktuell nicht nachweisbar sind, bleibt die produktive Freigabe strikt gesperrt und die fehlende Evidenz präzise dokumentiert.**

**Starte mit AP-STTM-000. Bringe zuerst die begonnene Kroko-/Modell-, API-, Settings-, Status- und Lazy-Reload-Arbeit bis zur prüfbaren Implementierung. Strukturiere nur dort, wo du für diese Arbeit ohnehin direkt Code in der Hand hast und es ohne Zusatzrisiko klaren Nutzen bringt. Die umfassende Serverarchitektur ist ein **späterer eigenständiger Auftrag**, kein Blocker dieses PRs.**
