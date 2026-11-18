# 06_DISCOVERY_REPORT

**Discovery-Basis:** `c901cda3f2c19eeb78c468524161728498b6e27e`
**Discovery-Tree:** `f81144a26f93fb3bc553ab5110d07197a473aa46`
**Datum:** 2026-08-28

---

## Executive Summary

### STATUS: DISCOVERY_COMPLETE

**Basis-SHA:** c901cda3f2c19eeb78c468524161728498b6e27e
**Basis-Tree:** f81144a26f93fb3bc553ab5110d07197a473aa46
**Discovery-Worktree:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\prep-srv-070-discovery`
**Produkt-Workingtree unverändert:** JA

---

## Fund-Statistik

### Legacy-Kategorien

| Kategorie | Anzahl |
|---|---|
| REMOVE_CANDIDATE | 6 |
| MIGRATION_CANDIDATE | 1 |
| KEEP_COMPATIBILITY | 9 |
| STILL_ACTIVE_REQUIRED | 6 |
| PUBLIC_LIBRARY_API_OUT_OF_SCOPE | 1 |
| UNKNOWN_NEEDS_REVIEW | 0 |
| EXCLUDED_WAKEWORD_ZONE | 4 |

### Dokumentations- und Repository-Funde

| Kategorie | Anzahl |
|---|---|
| Dokumentationslücken/Widersprüche | 8 |
| Repository-/Ablage-/Ordnungsfunde | 8 |

### Test- und Protocol-Funde

| Kategorie | Anzahl |
|---|---|
| Legacy-Tests (Legacy-Erwartungen) | 0 |
| Stale Fixtures / Testdoubles | 0 |
| Fehlende Cut-Guards | 9 |
| Protocol Gaps | 10 |

---

## Top-10 wahrscheinlich relevante SRV-070-Cuts

1. **`RealtimeSession` entfernen** (L001) – Dead-Code-Klasse ohne Instanziierung, `server.py:2249-2680`
2. **`VoiceActivityDetector` entfernen** (L002) – Nur von `RealtimeSession` genutzt, `server.py:2213-2247`
3. **`ACTION_ALIASES = {"extend": REFRESH}` entfernen** (L003) – v1-Alias-Mapping, `activation_commands.py:48-52`
4. **`SESSION_ACTIVATION_RETIRED_QUERY_FIELDS` entfernen** (L004) – Ignoriert alte `extensionSeconds`, `server.py:948-953`
5. **`ACTIVATION_ACTION_ALIASES_PUBLIC` entfernen** (L005) – Redundant mit L003, `server.py:957-958`
6. **`finalized()` Methode entfernen** (F1) – Kein Aufrufer im Server-Paket, `activation.py:312-320`
7. **v1→v2 Upgrade-Hinweis zu v1-Hello hinzufügen** (LCA-1) – Schließt GAP-1 und GAP-4
8. **Explizite v2-Ablehnung für v1-Nachrichtentypen** (LCA-2) – Schließt GAP-3
9. **Test für v1-Ablehnung von v2-Command-Typen** (LCA-3) – Schließt MCG-1 und GAP-2
10. **Test für v2-Ablehnung von v1-Command-Typen** (LCA-4) – Schließt MCG-2 und GAP-3

---

## Top-Dokumentationsfunde

1. **`README.md`** – Keine Protocol-v2-Erwähnung
2. **`fastapi-server.md`** – Kein `/ws/v2` dokumentiert
3. **`docs/.archiv/README.md`** – Status "In Umsetzung" veraltet
4. **`einheitliche-triggerarchitektur.md`** – `activation_command.py` Tippfehler (sollte `activation_commands.py` sein)
5. **`module-map.md`** – Verweis auf nicht existierende `docs/ARCHITECTURE.md`
6. **`api-compatibility.md`** – Hardcoded lokaler Pfad `D:/Projekte/STT/VoiceSTT/VoiceSTT`
7. **`configuration.md`** – Gemischte Sprache (Deutsch/Englisch)
8. **`09-betriebsmodi-und-serverkonfiguration.md`** – Alter Dateiname erwähnt ohne Datum

---

## Top-Ordnungsfunde

1. **`Planning/logging-fixes-implementierungsplan.md`** – Sollte archiviert werden (bereits implementiert)
2. **`api_fastapi_server/MULTI_USER_IMPLEMENTATION_GUIDE.md`** – Historisches Design-Dokument, sollte archiviert werden
3. **Binärdateien in `tests/`** – `suh_mahn_thuh.onnx`, `suh_man_tuh.onnx`, `samanta.tflite` – sollten nicht committed werden
4. **`docs/session-wakeword-erweiterung.md`** – Überlappende Dokumentation, historischer Teil sollte archiviert werden
5. **`docs/stt-server-specification.md`** – Übergabe-Spezifikation für externes Projekt, sollte archiviert werden
6. **Redundante Batch-Skripte** – `app_browserclient/start_server.bat`, `app_talk_with_llm/start.bat`, `app_talk_with_llm/install_cpu.bat`
7. **`tests/contracts/protocol-v2-vectors.json`** – Externe Kopie, bereits dokumentiert
8. **Alte Beispiel-Apps** – `app_browserclient/`, `app_webserver/`, `app_talk_with_llm/` – als "legacy examples" markieren

---

## Top-Test-/Protocol-Gaps

### Fehlende Cut-Guards

1. **MCG-1** – v1-Transport akzeptiert nie v2-Envelope-Nachrichten (nicht getestet)
2. **MCG-2** – v2-Transport akzeptiert nie v1-Nachrichtentypen (nicht getestet)
3. **MCG-3** – `SUPPORTED_PROTOCOL_VERSIONS` ist geschlossen bei `{2}` (nicht getestet)
4. **MCG-4** – Serverversion ist über alle veröffentlichten Oberflächen konsistent (nicht getestet)
5. **MCG-5** – v1/v2 Session-ID-Isolation (nicht getestet)
6. **MCG-6** – `DEFAULT_HANDSHAKE_TIMEOUT_SECONDS` ist auffindbar und konsistent (nicht getestet)
7. **MCG-7** – v1 emittiert nie kanonische v2-Event-Namen (nicht getestet)
8. **MCG-8** – `PROTOCOL_VERSION = 2` ist der einzige Wert, den `negotiate()` zurückgeben kann (nicht getestet)
9. **MCG-9** – v1 `activationConfig.mode` ist `"legacy"` ohne Trigger-Parameter (nicht vollständig getestet)

### Protocol Gaps

1. **GAP-1** – v1-Endpunkt hat kein Protocol-Version-Gate
2. **GAP-2** – v1-Endpunkt lehnt v2-Command-Typen nicht ab
3. **GAP-3** – v2-Endpunkt lehnt v1-Command-Typen nicht explizit ab
4. **GAP-4** – Keine Version-Anzeige auf v1
5. **GAP-5** – `SERVER_VERSION = "2.0.0"` ist unabhängig von Protocol-Version hartcodiert
6. **GAP-6** – v1 Session-IDs lecken kompaktes Hex in UUID-Namespace-Welt
7. **GAP-7** – `serverCommit` fällt still auf `"unknown"` zurück
8. **GAP-8** – Kein gemeinsames Versionsmanifest
9. **GAP-9** – v1 `activationConfig.mode` ist serverseitige Entscheidung
10. **GAP-10** – v1-Endpunkt akzeptiert Verbindungen ohne Client-Identität

---

## Wake-Word-Zone

**Vollständig ausgeschlossen:** JA

Folgende Bereiche wurden als `EXCLUDED_WAKEWORD_ZONE` markiert und nicht fachlich bewertet:

- `docs/wake-words.md` (L022)
- `VoiceSTT/core/wakeword.py` (L023)
- `VoiceSTT/core/openwakeword_catalog.py` (L024)
- `_start_wakeword_followup_window` (G1 in Runtime-Map)

**Begründung:** AP-SRV-060 läuft parallel. Alle Wake-Word-bezogenen Pfade sind von der fachlichen Bewertung ausgeschlossen.

---

## Unabhängig von SRV-060 umsetzbar

### Sofort umsetzbar (REMOVE_CANDIDATE)

1. `RealtimeSession` entfernen
2. `VoiceActivityDetector` entfernen
3. `ACTION_ALIASES = {"extend": REFRESH}` entfernen
4. `SESSION_ACTIVATION_RETIRED_QUERY_FIELDS` entfernen
5. `ACTIVATION_ACTION_ALIASES_PUBLIC` entfernen
6. `finalized()` Methode entfernen

### Dokumentations-Updates (DOCUMENT_ONLY)

1. `README.md` – Protocol-v2-Erwähnung hinzufügen
2. `fastapi-server.md` – `/ws/v2` dokumentieren
3. `docs/.archiv/README.md` – Status aktualisieren
4. `einheitliche-triggerarchitektur.md` – Tippfehler korrigieren
5. `module-map.md` – toten Link entfernen
6. `api-compatibility.md` – hardcoded Pfad durch Platzhalter ersetzen
7. `configuration.md` – Sprache vereinheitlichen
8. `09-betriebsmodi-und-serverkonfiguration.md` – Datum hinzufügen oder Hinweis entfernen

### Repository-Aufräumung (ARCHIVE/DELETE_CANDIDATE)

1. `Planning/logging-fixes-implementierungsplan.md` → archivieren
2. `api_fastapi_server/MULTI_USER_IMPLEMENTATION_GUIDE.md` → archivieren
3. Binärdateien in `tests/` → entfernen
4. `docs/session-wakeword-erweiterung.md` → Teile archivieren
5. `docs/stt-server-specification.md` → archivieren
6. Redundante Batch-Skripte → entfernen

### Protocol-Boundary-Tests (LATER_CUT_ACTIONS)

1. v1→v2 Upgrade-Hinweis zu v1-Hello (LCA-1)
2. Explizite v2-Ablehnung für v1-Nachrichtentypen (LCA-2)
3. Test für v1-Ablehnung von v2-Command-Typen (LCA-3)
4. Test für v2-Ablehnung von v1-Command-Typen (LCA-4)
5. Versionsmanifest vereinheitlichen (LCA-5)
6. Cross-Surface-Server-Identitäts-Konsistenztest (LCA-6)

---

## Nach SRV-060 erneut zu prüfen

### KEEP_COMPATIBILITY (bis v1-Transport entfernt wird)

1. `activation_config.mode == "legacy"` (L007)
2. `_compat_final_context` (L008)
3. `_on_recording_start` (legacy branch) (L009)
4. `_on_recording_stop` (legacy branch) (L010)
5. `_legacy_activation_sequence` (L011)
6. `_trigger_ack` (L012)
7. `_normalized_action` (L013)
8. v2-zu-v1-Bridge (L014)
9. `finalizing` Phase (F2)

### EXCLUDED_WAKEWORD_ZONE (nach SRV-060-Abnahme)

1. `docs/wake-words.md` (L022)
2. `VoiceSTT/core/wakeword.py` (L023)
3. `VoiceSTT/core/openwakeword_catalog.py` (L024)
4. `_start_wakeword_followup_window` (G1 in Runtime-Map)

---

## Historische Legacy-Map-Funde

### Noch gültig

1. **`RealtimeSession` und `VoiceActivityDetector`** – Dead-Code, keine Instanziierung gefunden
2. **`finalized()` Methode** – Kein Aufrufer im Server-Paket
3. **Additive `extend`-Semantik** – Durch Test bewiesen tot
4. **`finalizing` Phase** – Nur über `activate()` oder `reset()` verlassen, `finalized()` nie aufgerufen
5. **v1/v2 Transport-Isolation** – Zwei unabhängige Protokoll-Transporte, korrekt isoliert

### Veraltet

Keine veralteten Funde aus der historischen Legacy-Map identifiziert. Alle historischen Funde sind auf dem aktuellen Stand.

---

## Empfehlung für die nächste Prep-Runde

### Konkreter, enger Implementierungsumfang

**Phase 1: Dead-Code-Entfernung (LOW RISK)**

1. `RealtimeSession` Klasse entfernen (`server.py:2249-2680`)
2. `VoiceActivityDetector` Klasse entfernen (`server.py:2213-2247`)
3. `finalized()` Methode entfernen (`activation.py:312-320`)
4. `ACTION_ALIASES` entfernen (`activation_commands.py:48-52`)
5. `SESSION_ACTIVATION_RETIRED_QUERY_FIELDS` entfernen (`server.py:948-953`)
6. `ACTIVATION_ACTION_ALIASES_PUBLIC` entfernen (`server.py:957-958`)

**Testnachweis:** Bestehende Tests sollten grün bleiben. Keine neuen Tests erforderlich für Dead-Code-Entfernung.

**Phase 2: Dokumentations-Updates (LOW RISK)**

1. `README.md` – Protocol-v2-Erwähnung hinzufügen
2. `fastapi-server.md` – `/ws/v2` dokumentieren
3. `docs/.archiv/README.md` – Status aktualisieren
4. `einheitliche-triggerarchitektur.md` – Tippfehler korrigieren
5. `module-map.md` – toten Link entfernen
6. `api-compatibility.md` – hardcoded Pfad durch Platzhalter ersetzen
7. `configuration.md` – Sprache vereinheitlichen
8. `09-betriebsmodi-und-serverkonfiguration.md` – Datum hinzufügen oder Hinweis entfernen

**Phase 3: Repository-Aufräumung (LOW-MEDIUM RISK)**

1. `Planning/logging-fixes-implementierungsplan.md` → `docs/.archiv/logging-fixes/`
2. `api_fastapi_server/MULTI_USER_IMPLEMENTATION_GUIDE.md` → `docs/.archiv/multi-user-design/`
3. Binärdateien in `tests/` → entfernen
4. `docs/session-wakeword-erweiterung.md` → Teile archivieren
5. `docs/stt-server-specification.md` → `docs/.archiv/desktop-client-spec/`
6. Redundante Batch-Skripte → entfernen

**Phase 4: Protocol-Boundary-Tests (MEDIUM RISK)**

1. v1→v2 Upgrade-Hinweis zu v1-Hello (LCA-1)
2. Explizite v2-Ablehnung für v1-Nachrichtentypen (LCA-2)
3. Test für v1-Ablehnung von v2-Command-Typen (LCA-3)
4. Test für v2-Ablehnung von v1-Command-Typen (LCA-4)
5. Versionsmanifest vereinheitlichen (LCA-5)
6. Cross-Surface-Server-Identitäts-Konsistenztest (LCA-6)

**Phase 5: KEEP_COMPATIBILITY (nach v1-Transport-Deprecation)**

Erst nach vollständiger v2-Migration und v1-Deprecation:

1. `activation_config.mode == "legacy"` entfernen
2. `_compat_final_context` entfernen
3. `_on_recording_start` (legacy branch) entfernen
4. `_on_recording_stop` (legacy branch) entfernen
5. `_legacy_activation_sequence` entfernen
6. `_trigger_ack` entfernen
7. `_normalized_action` vereinfachen
8. v2-zu-v1-Bridge vereinfachen
9. `finalizing` Phase entfernen

---

## Abschlussprüfung

**Discovery-Worktree clean:** JA
**Produktänderungen:** KEINE
**Commit:** KEINER
**Push:** NEIN

**Verifikation:**

```
HEAD = c901cda3f2c19eeb78c468524161728498b6e27e
TREE = f81144a26f93fb3bc553ab5110d07197a473aa46
working tree = clean
```

---

## Artefakte

Erstellt unter: `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prep\Discovery\2026-08-28\`

1. `01_LEGACY_INVENTORY.md` – Vollständiges Codeinventar
2. `02_RUNTIME_REACHABILITY_MAP.md` – Runtime-Erreichbarkeitsanalyse
3. `03_LEGACY_CUT_CANDIDATES.md` – Cut-Kandidaten gruppiert
4. `04_DOCUMENTATION_AND_REPOSITORY_CLEANUP_AUDIT.md` – Dokumentations- und Repository-Audit
5. `05_TEST_AND_PROTOCOL_GAP_AUDIT.md` – Test- und Protocol-Gap-Audit
6. `06_DISCOVERY_REPORT.md` – Dieser Bericht

---

**Discovery abgeschlossen.**
