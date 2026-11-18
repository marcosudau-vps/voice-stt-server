# 04_DOCUMENTATION_AND_REPOSITORY_CLEANUP_AUDIT

**Discovery-Basis:** `c901cda3f2c19eeb78c468524161728498b6e27e`
**Datum:** 2026-08-28

---

## A. Dokumentationslücken/Widersprüche

### A1: `README.md` – Keine Protocol-v2-Erwähnung

**Aktuelle Position:** `README.md` (Root)
**Problem:** Erwähnt nicht Protocol v2 (`/ws/v2`) oder AP-SRV-010-050
**Empfohlene spätere Aktion:** DOCUMENT_ONLY
**Zielpfad:** `README.md` Section "Protocol" oder "Architecture"
**Begründung:** Projektübersicht sollte aktuelle Architektur widerspiegeln
**Risiko:** LOW – Dokumentations-Update

---

### A2: `fastapi-server.md` – Kein `/ws/v2` dokumentiert

**Aktuelle Position:** `docs/fastapi-server.md`
**Problem:** Dokumentiert nur `/ws/transcribe` (v1), nicht `/ws/v2`
**Empfohlene spätere Aktion:** DOCUMENT_ONLY
**Zielpfad:** `docs/fastapi-server.md` Section "WebSocket Endpoints"
**Begründung:** Server-Dokumentation sollte beide Protokoll-Endpunkte abdecken
**Risiko:** LOW – Dokumentations-Update

---

### A3: `docs/.archiv/README.md` – Status veraltet

**Aktuelle Position:** `docs/.archiv/README.md:79`
**Problem:** Status "Einheitliche serverseitige Triggerarchitektur" ist "In Umsetzung", aber Doku ist weitgehend vollständig
**Empfohlene spätere Aktion:** DOCUMENT_ONLY
**Zielpfad:** `docs/.archiv/README.md` Status-Spalte
**Begründung:** Archiv-Status sollte aktuellen Stand reflektieren
**Risiko:** LOW – Dokumentations-Update

---

### A4: `einheitliche-triggerarchitektur.md` – `activation_command.py` Tippfehler

**Aktuelle Position:** `docs/einheitliche-triggerarchitektur.md` Section 3a Ownership-Tabelle, Zeile ~388
**Problem:** Erwähnt `activation_command.py` (singular), Datei heißt aber `activation_commands.py` (plural)
**Empfohlene spätere Aktion:** DOCUMENT_ONLY
**Zielpfad:** `docs/einheitliche-triggerarchitektur.md` Zeile ~388
**Begründung:** Dateiname inkorrekt
**Risiko:** LOW – Dokumentations-Update

---

### A5: `module-map.md` – Verweis auf nicht existierende `docs/ARCHITECTURE.md`

**Aktuelle Position:** `docs/module-map.md` Zeile 4, Zeile 37
**Problem:** Verweist auf `docs/ARCHITECTURE.md`, Datei existiert nicht (laut `.gitignore` wird `ARCHITECTURE.md` ignoriert)
**Empfohlene spätere Aktion:** DOCUMENT_ONLY
**Zielpfad:** `docs/module-map.md` Zeile 4, 37 – Verweis entfernen oder auf existierende Datei umleiten
**Begründung:** Toter Link
**Risiko:** LOW – Dokumentations-Update

---

### A6: `api-compatibility.md` – Hardcoded lokaler Pfad

**Aktuelle Position:** `docs/api-compatibility.md:395`
**Problem:** Enthält `git -c safe.directory=D:/Projekte/STT/VoiceSTT/VoiceSTT status` – hardcoded lokaler Pfad
**Empfohlene spätere Aktion:** DOCUMENT_ONLY
**Zielpfad:** `docs/api-compatibility.md` Zeile 395 – Pfad durch Platzhalter ersetzen
**Begründung:** Entwicklerepezifischer Pfad in allgemeiner Doku
**Risiko:** LOW – Dokumentations-Update

---

### A7: `configuration.md` – Gemischte Sprache

**Aktuelle Position:** `docs/configuration.md` Section "Server Runtime Settings (AP-SRV-050)" Zeilen 179-208
**Problem:** Section ist auf Deutsch, Rest auf Englisch
**Empfohlene spätere Aktion:** DOCUMENT_ONLY
**Zielpfad:** `docs/configuration.md` – Sprache vereinheitlichen (Englisch empfohlen)
**Begründung:** Inkonsistente Sprache in technischer Doku
**Risiko:** LOW – Dokumentations-Update

---

### A8: `09-betriebsmodi-und-serverkonfiguration.md` – Alter Dateiname erwähnt

**Aktuelle Position:** `docs/client-development/09-betriebsmodi-und-serverkonfiguration.md` Zeilen 5-11
**Problem:** Erwähnt "Diese Datei hieß früher 'Betriebsmodi und sessionlokale Wake-Word-Konfiguration'", aber kein Datum der Umbenennung
**Empfohlene spätere Aktion:** DOCUMENT_ONLY
**Zielpfad:** `docs/client-development/09-betriebsmodi-und-serverkonfiguration.md` – Datum hinzufügen oder Hinweis entfernen
**Begründung:** Unvollständige Historie
**Risiko:** LOW – Dokumentations-Update

---

## B. Repository-/Ablage-/Ordnungsfunde

### B1: `Planning/logging-fixes-implementierungsplan.md`

**Aktuelle Position:** `Planning/logging-fixes-implementierungsplan.md`
**Problem:** Implementierungsplan liegt außerhalb des Archivs. Status: "Implementiert, nach Abnahmebericht nachgebessert und verifiziert" (Z. 3) – sollte archiviert werden.
**Empfohlene spätere Aktion:** ARCHIVE
**Zielpfad:** `docs/.archiv/logging-fixes/2026-XX-XX_PLAN.md`
**Begründung:** Historischer Plan, bereits implementiert. Archiv-Regel verlangt Ablage in `.archiv/`.
**Risiko:** LOW – Nur Dokumentation

---

### B2: `api_fastapi_server/MULTI_USER_IMPLEMENTATION_GUIDE.md`

**Aktuelle Position:** `api_fastapi_server/MULTI_USER_IMPLEMENTATION_GUIDE.md`
**Problem:** Design-Dokument von vor der Multi-User-Implementierung. 406 Zeilen. Beschreibt "The design work needed before turning `api_fastapi_server` into a multi-user realtime transcription server" (Z. 3-4) – längst implementiert.
**Empfohlene spätere Aktion:** ARCHIVE
**Zielpfad:** `docs/.archiv/multi-user-design/`
**Begründung:** Historisches Design-Dokument, keine aktuelle Referenz.
**Risiko:** LOW

---

### B3: Binärdateien in `tests/`

**Aktuelle Position:** `tests/suh_mahn_thuh.onnx`, `tests/suh_man_tuh.onnx`, `tests/samanta.tflite`
**Problem:** Wake-Word-Model-Dateien in `tests/` – gehören nicht in die Test-Suite. `tests/README.md` beschreibt Setup-Schritte für lokale Modelle, aber die Dateien selbst sind Binaries.
**Empfohlene spätere Aktion:** DELETE_CANDIDATE
**Zielpfad:** Entfernen
**Begründung:** Binärdateien in `tests/` sollten nicht committed werden. Modelle werden lokal heruntergeladen.
**Risiko:** MEDIUM – Könnte Tests brechen wenn sie referenziert werden

---

### B4: `docs/session-wakeword-erweiterung.md`

**Aktuelle Position:** `docs/session-wakeword-erweiterung.md`
**Problem:** 488 Zeilen. Beschreibt die Session-Wake-Word-Erweiterung, die bereits in `main` integriert ist (Z. 6-7). Verweist auf Archiv-Dokumente (Z. 29-33). Einige Inhalte überlappen mit `client-development/09-betriebsmodi-und-serverkonfiguration.md`. Die historische Power-Shell-Verifikation (Z. 400+) gehört ins Archiv.
**Empfohlene spätere Aktion:** MERGE
**Zielpfad:** Teile in `docs/wake-words.md` oder `docs/client-development/09-*.md`, historischer Teil nach `docs/.archiv/`
**Begründung:** Überlappende Dokumentation, historischer Teil sollte archiviert werden
**Risiko:** MEDIUM – Könnte Links brechen

---

### B5: `docs/stt-server-specification.md`

**Aktuelle Position:** `docs/stt-server-specification.md`
**Problem:** 1379 Zeilen. Desktop-Client-Spezifikation. Enthält "Übergabespezifikation: VoiceSTT-Server für einen dauerhaften Desktop-Client" (Z. 1).
**Empfohlene spätere Aktion:** ARCHIVE
**Zielpfad:** `docs/.archiv/desktop-client-spec/`
**Begründung:** Ist eine Übergabe-Spezifikation für ein externes Projekt, keine Server-Dokumentation. Sollte separat archiviert werden.
**Risiko:** MEDIUM – Externe Referenzen könnten brechen

---

### B6: Redundante Batch-Skripte

**Aktuelle Position:** `app_browserclient/start_server.bat`, `app_talk_with_llm/start.bat`, `app_talk_with_llm/install_cpu.bat`
**Problem:** Windows-Batch-Skripte in Beispiel-Apps. `app_talk_with_llm/install_cpu.bat` ruft nur `install_windows_cpu.ps1` auf – redundant.
**Empfohlene spätere Aktion:** DELETE_CANDIDATE
**Zielpfad:** Entfernen
**Begründung:** Redundante Wrapper-Skripte. Die PowerShell-Skripte sind die kanonischen Installer.
**Risiko:** LOW

---

### B7: `tests/contracts/protocol-v2-vectors.json` – Externe Kopie

**Aktuelle Position:** `tests/contracts/protocol-v2-vectors.json`
**Problem:** Kopie aus einem anderen Repository (`voice-stt-client/workspaces/...`). `tests/contracts/README.md` erklärt: "Do not edit this file here" (Z. 24).
**Empfohlene spätere Aktion:** KEEP + DOCUMENT_ONLY
**Zielpfad:** Keine Änderung, aber in `AGENTS.md` erwähnen
**Begründung:** Ist bereits dokumentiert als Kopie. Keine Aktion nötig.
**Risiko:** LOW

---

### B8: `app_browserclient/`, `app_webserver/`, `app_talk_with_llm/` – Alte Beispiele

**Aktuelle Position:** `app_browserclient/`, `app_webserver/`, `app_talk_with_llm/`
**Problem:** Alte Beispiel-Apps. `module-map.md` Z. 93 beschreibt sie als "Older/manual examples and demos... avoid treating examples as the primary architecture source".
**Empfohlene spätere Aktion:** KEEP
**Zielpfad:** Keine Änderung
**Begründung:** Sind als Beispiele nützlich, aber sollten klar als "legacy examples" in der Dokumentation markiert werden.
**Risiko:** LOW

---

## Zusammenfassung

| Kategorie | Anzahl |
|---|---|
| A. Dokumentationslücken/Widersprüche | 8 |
| B. Repository-/Ablage-/Ordnungsfunde | 8 |

**Prioritäten:**
- **High:** Keine
- **Medium:** ARCHIVE (B1, B2, B4, B5), DELETE_CANDIDATE (B3, B6)
- **Low:** DOCUMENT_ONLY (A1-A8, B7, B8)
