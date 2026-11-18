# 03_LEGACY_CUT_CANDIDATES

**Discovery-Basis:** `c901cda3f2c19eeb78c468524161728498b6e27e`
**Datum:** 2026-08-28

---

## A. REMOVE_CANDIDATE

### A1: `RealtimeSession` (L001)

**Was:** Inline-Session-Klasse mit eigenem VAD und Recording-Loop
**Wo:** `api_fastapi_server/server.py:2249-2680`
**Warum:** Keine Instanziierung im Produktivcode. Nur `RecorderBackedRealtimeSession` wird verwendet (server.py:6292).
**Zielsymbol:** Klasse vollständig löschen
**Betroffene Dateien:** server.py
**Benötigte Tests:** Keine (dead code)
**Abhängigkeiten:** Keine
**Risiko:** LOW – keine Runtime-Abhängigkeit

---

### A2: `VoiceActivityDetector` (L002)

**Was:** Einfaches VAD-Wrapper mit webrtcvad + Energie-Fallback
**Wo:** `api_fastapi_server/server.py:2213-2247`
**Warum:** Nur von `RealtimeSession.__init__` (L001) genutzt. Mit L001 entfernbar.
**Zielsymbol:** Klasse vollständig löschen
**Betroffene Dateien:** server.py
**Benötigte Tests:** Keine (dead code)
**Abhängigkeiten:** webrtcvad (kann entfernt werden, wenn nicht anderswo genutzt)
**Risiko:** LOW

---

### A3: `ACTION_ALIASES = {"extend": REFRESH}` (L003)

**Was:** v1-Alias-Mapping für `extend` → `refresh`
**Wo:** `api_fastapi_server/activation_commands.py:48-52`
**Warum:** Additive `extend`-Semantik ist tot. Parser normalisiert nur noch.
**Zielsymbol:** Konstante entfernen, `_normalized_action` vereinfachen
**Betroffene Dateien:** activation_commands.py, server.py (L005)
**Benötigte Tests:** `test_server_activation_commands.py` aktualisieren (Alias-Tests entfernen)
**Abhängigkeiten:** v1-Trigger-Clients, die `extend` senden
**Risiko:** MEDIUM – v1-Clients müssen auf `refresh` umstellen

---

### A4: `SESSION_ACTIVATION_RETIRED_QUERY_FIELDS` (L004)

**Was:** Liste ignoriert alter URL-Parameter (`extensionSeconds`)
**Wo:** `api_fastapi_server/server.py:948-953`
**Warum:** Harmloser Migrationscode. URL mit `extensionSeconds` wird toleriert, aber ignoriert.
**Zielsymbol:** Konstante und Filter-Logik entfernen
**Betroffene Dateien:** server.py
**Benötigte Tests:** Keine (kein Verhalten)
**Abhängigkeiten:** Alte Clients, die `extensionSeconds` in URL senden
**Risiko:** LOW

---

### A5: `ACTIVATION_ACTION_ALIASES_PUBLIC` (L005)

**Was:** Öffentliche Liste v1-Alias-Aktionen
**Wo:** `api_fastapi_server/server.py:957-958`
**Warum:** Redundant mit L003. Entfernbar wenn L003 entfernt wird.
**Zielsymbol:** Konstante entfernen
**Betroffene Dateien:** server.py
**Benötigte Tests:** Keine
**Abhängigkeiten:** L003
**Risiko:** LOW

---

### A6: `finalized()` Methode (F1)

**Was:** Transition `finalizing` → `inactive`
**Wo:** `api_fastapi_server/activation.py:312-320`
**Warum:** Kein Aufrufer im Server-Paket. Phase `finalizing` wird nur über `activate()` oder `reset()` verlassen.
**Zielsymbol:** Methode löschen
**Betroffene Dateien:** activation.py
**Benötigte Tests:** `test_server_activation_controller.py` aktualisieren (falls vorhanden)
**Abhängigkeiten:** Keine
**Risiko:** LOW

---

## B. MIGRATION_CANDIDATE

### B1: Dokumentation `GET /api/v2/wake-words` (L006)

**Was:** Erwähnt Endpunkt als AP-SRV-060, existiert aber noch nicht
**Wo:** `docs/einheitliche-triggerarchitektur.md` Section 13.4
**Warum:** Klar als "Future Work" markieren oder AP-SRV-060-Status aktualisieren
**Zielsymbol:** Doku-Update
**Betroffene Dateien:** einheitliche-triggerarchitektur.md
**Benötigte Tests:** N/A
**Abhängigkeiten:** AP-SRV-060
**Risiko:** LOW – Dokumentations-Update

---

## C. KEEP_COMPATIBILITY

### C1: `activation_config.mode == "legacy"` (L007)

**Was:** Legacy-Mode für Clients ohne Trigger-Parameter
**Wo:** `api_fastapi_server/server.py:1047-1056, 2555-2562, 2603`
**Warum:** Desktop-Client sendet beide Flags immer. Aber v1-Transport nutzt Legacy-Mode als Fallback.
**Zielsymbol:** Bis v1-Transport entfernt wird behalten
**Betroffene Dateien:** server.py
**Benötigte Tests:** `test_server_controlled_e2e.py`, `test_server_trigger_contract.py`
**Abhängigkeiten:** v1-Transport, Browserclient
**Risiko:** MEDIUM – Entfernung erfordert vollständige v2-Migration

---

### C2: `_compat_final_context` (L008)

**Was:** Synthetische Legacy-Activation-IDs
**Wo:** `api_fastapi_server/server.py:4792-4809`
**Warum:** Erzeugt `legacy-{session_id}-{seq}` IDs für Segmente ohne Controlled-Activation.
**Zielsymbol:** Bis v1-Transport entfernt wird behalten
**Betroffene Dateien:** server.py
**Benötigte Tests:** `test_server_controlled_e2e.py`
**Abhängigkeiten:** L007
**Risiko:** MEDIUM

---

### C3: `_on_recording_start` (legacy branch) (L009)

**Was:** Legacy-Aufnahmestart ohne ActivationController
**Wo:** `api_fastapi_server/server.py:5326-5336`
**Warum:** Nur wenn `_activation is None` (Legacy-Mode).
**Zielsymbol:** Bis L007 entfernt wird behalten
**Betroffene Dateien:** server.py
**Benötigte Tests:** `test_fastapi_server_multi_user.py`
**Abhängigkeiten:** L007
**Risiko:** MEDIUM

---

### C4: `_on_recording_stop` (legacy branch) (L010)

**Was:** Legacy-Aufnahmestopp ohne ActivationController
**Wo:** `api_fastapi_server/server.py:5430, 5448-5450`
**Warum:** Nur wenn `_activation is None` (Legacy-Mode).
**Zielsymbol:** Bis L007 entfernt wird behalten
**Betroffene Dateien:** server.py
**Benötigte Tests:** `test_fastapi_server_multi_user.py`
**Abhängigkeiten:** L007
**Risiko:** MEDIUM

---

### C5: `_legacy_activation_sequence` (L011)

**Was:** Legacy-Sequence-Counter
**Wo:** `api_fastapi_server/server.py:2758`
**Warum:** Nur wenn `_activation is None`. Paralleler Counter für Legacy-Mode.
**Zielsymbol:** Bis L007 entfernt wird behalten
**Betroffene Dateien:** server.py
**Benötigte Tests:** `test_fastapi_server_multi_user.py`
**Abhängigkeiten:** L007, L008
**Risiko:** LOW

---

### C6: `_trigger_ack` (L012)

**Was:** v1-Ack-Format
**Wo:** `api_fastapi_server/server.py:3472-3483`
**Warum:** v1-Transport nutzt `trigger_ack`, v2 nutzt `command.ack`.
**Zielsymbol:** Bis v1-Transport entfernt wird behalten
**Betroffene Dateien:** server.py
**Benötigte Tests:** `test_server_trigger_contract.py`
**Abhängigkeiten:** v1-Transport
**Risiko:** MEDIUM

---

### C7: `_normalized_action` (L013)

**Was:** Alias-Normalisierung
**Wo:** `api_fastapi_server/activation_commands.py:179`
**Warum:** Normalisiert `ACTION_ALIASES`. Wird No-Op wenn L003 entfernt wird.
**Zielsymbol:** Bis L003 entfernt wird behalten
**Betroffene Dateien:** activation_commands.py
**Benötigte Tests:** `test_server_activation_commands.py`
**Abhängigkeiten:** L003
**Risiko:** LOW

---

### C8: v2-zu-v1-Bridge (L014)

**Was:** `_handle_activation_command` in v2-Connection
**Wo:** `api_fastapi_server/protocol_v2/connection.py:365-381`
**Warum:** v2-Protokoll delegiert an v1-Session-Methoden und projiziert Ergebnis.
**Zielsymbol:** Bis v1-Session-Methoden refactored sind behalten
**Betroffene Dateien:** protocol_v2/connection.py
**Benötigte Tests:** `test_protocol_v2_contract.py`, `test_protocol_v2_e2e.py`
**Abhängigkeiten:** v1-Session-Methoden
**Risiko:** MEDIUM

---

### C9: `finalizing` Phase (F2)

**Was:** Abschluss-Phase im v1-Transport
**Wo:** `activation.py:34, 353-356`
**Warum:** v1-Protokoll nutzt `finalizing` als Übergangsphase. v2 nutzt `closing_input`.
**Zielsymbol:** Bis v1-Transport entfernt wird behalten
**Betroffene Dateien:** activation.py
**Benötigte Tests:** `test_server_activation_controller.py`
**Abhängigkeiten:** v1-Transport
**Risiko:** MEDIUM

---

## D. STILL_ACTIVE_REQUIRED

### D1: Mode-Weiche controlled/legacy (L015)

**Was:** `RecorderBackedRealtimeSession.__init__` branch
**Wo:** `api_fastapi_server/server.py:2791`
**Warum:** Kanonische Weiche zwischen neuem und altem Pfad.
**Zielsymbol:** Behalten bis vollständige v2-Migration
**Betroffene Dateien:** server.py
**Benötigte Tests:** Alle Activation-Tests
**Abhängigkeiten:** N/A
**Risiko:** N/A

---

### D2-D6: Weitere aktive Komponenten (L016-L020)

- `resolve_session_activation_config` (L016)
- `forced_finalizations` (L017)
- `_force_finalize_in_progress` (L018)
- `_force_finalize_after_limit` (L019)
- `_on_recording_start` (controlled branch) (L020)

**Warum:** Alle sind kanonische, aktive Komponenten ohne Legacy-Bezug.
**Zielsymbol:** Dauerhaft behalten
**Risiko:** N/A

---

## E. PUBLIC_LIBRARY_API_OUT_OF_SCOPE

### E1: `AudioToTextRecorderClient` (L021)

**Was:** Client-Library für Server-Verbindung
**Wo:** `VoiceSTT/audio_recorder_client.py:87`
**Warum:** Öffentliche Bibliotheks-API. Nur von Legacy-CLI-Client genutzt.
**Zielsymbol:** Server-seitig nicht bewerten
**Betroffene Dateien:** audio_recorder_client.py
**Benötigte Tests:** N/A
**Abhängigkeiten:** Externe Nutzer
**Risiko:** N/A – außerhalb Server-Scope

---

## F. UNKNOWN_NEEDS_REVIEW

### F1: Keine UNCERTAIN-Funde

Alle Legacy-Funde sind klar klassifiziert.

---

## G. EXCLUDED_WAKEWORD_ZONE

### G1: Wake-Word-bezogene Legacy-Pfade (L022-L024)

- `docs/wake-words.md` (L022)
- `VoiceSTT/core/wakeword.py` (L023)
- `VoiceSTT/core/openwakeword_catalog.py` (L024)
- `_start_wakeword_followup_window` (G1 in Runtime-Map)

**Warum:** AP-SRV-060 läuft parallel. Alle Wake-Word-bezogenen Pfade sind von der fachlichen Bewertung ausgeschlossen.
**Zielsymbol:** Nach SRV-060-Abnahme erneut prüfen
**Betroffene Dateien:** Wake-Word-Module
**Benötigte Tests:** Nach SRV-060
**Abhängigkeiten:** AP-SRV-060
**Risiko:** N/A – bewusst ausgespart

---

## Zusammenfassung

| Kategorie | Anzahl | Kommentar |
|---|---|---|
| A. REMOVE_CANDIDATE | 6 | Sofort entfernbar nach AP-SRV-070 |
| B. MIGRATION_CANDIDATE | 1 | Doku-Update |
| C. KEEP_COMPATIBILITY | 9 | Bis v1-Transport entfernt wird |
| D. STILL_ACTIVE_REQUIRED | 6 | Kanonisch, dauerhaft behalten |
| E. PUBLIC_LIBRARY_API_OUT_OF_SCOPE | 1 | Außerhalb Server-Scope |
| F. UNKNOWN_NEEDS_REVIEW | 0 | Keine unsicheren Funde |
| G. EXCLUDED_WAKEWORD_ZONE | 4 | Nach SRV-060 prüfen |
