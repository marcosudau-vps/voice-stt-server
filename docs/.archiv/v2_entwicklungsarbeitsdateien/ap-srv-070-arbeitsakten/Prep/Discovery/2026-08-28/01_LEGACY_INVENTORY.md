# 01_LEGACY_INVENTORY

**Discovery-Basis:** `c901cda3f2c19eeb78c468524161728498b6e27e`
**Worktree:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\prep-srv-070-discovery`
**Datum:** 2026-08-28

---

## REMOVE_CANDIDATE

| ID | Datei | Symbol/Bereich | Zeile | Funktion | Runtime-erreichbar | Ersatz | Wake-Word-Zone | Aktion |
|---|---|---|---|---|---|---|---|---|
| L001 | `api_fastapi_server/server.py` | `RealtimeSession` | 2249-2680 | Inline-Session-Klasse mit eigenem VAD | NEIN | `RecorderBackedRealtimeSession` | NEIN | Löschen |
| L002 | `api_fastapi_server/server.py` | `VoiceActivityDetector` | 2213-2247 | Einfaches VAD-Wrapper | NEIN (nur von L001) | `AudioToTextRecorder` intern | NEIN | Löschen |
| L003 | `api_fastapi_server/activation_commands.py` | `ACTION_ALIASES` | 48-52 | v1-Alias `extend`→`refresh` | JA | Direkt `REFRESH` | NEIN | Entfernen |
| L004 | `api_fastapi_server/server.py` | `SESSION_ACTIVATION_RETIRED_QUERY_FIELDS` | 948-953 | Ignoriert alte `extensionSeconds` | JA | `ActivationTimingPolicy` | NEIN | Entfernen |
| L005 | `api_fastapi_server/server.py` | `ACTIVATION_ACTION_ALIASES_PUBLIC` | 957-958 | v1-Alias-Liste | JA | Direkt `REFRESH` | NEIN | Entfernen |

---

## MIGRATION_CANDIDATE

| ID | Datei | Symbol/Bereich | Zeile | Funktion | Runtime-erreichbar | Ersatz | Wake-Word-Zone | Aktion |
|---|---|---|---|---|---|---|---|---|
| L006 | `docs/einheitliche-triggerarchitektur.md` | Section 13.4 | ~1100 | Erwähnt `GET /api/v2/wake-words` als AP-SRV-060 | N/A | N/A | NEIN | Doku aktualisieren |

---

## KEEP_COMPATIBILITY

| ID | Datei | Symbol/Bereich | Zeile | Funktion | Runtime-erreichbar | Ersatz | Wake-Word-Zone | Aktion |
|---|---|---|---|---|---|---|---|---|
| L007 | `api_fastapi_server/server.py` | `activation_config.mode == "legacy"` | 1047-1056, 2555-2562, 2603 | Legacy-Mode für Clients ohne Trigger-Parameter | JA | Controlled-Mode | NEIN | Bis AP-SRV-070 behalten |
| L008 | `api_fastapi_server/server.py` | `_compat_final_context` | 4792-4809 | Synthetische Legacy-Activation-IDs | JA | `ActivationController` | NEIN | Bis AP-SRV-070 behalten |
| L009 | `api_fastapi_server/server.py` | `_on_recording_start` (legacy branch) | 5326-5336 | Legacy-Aufnahmestart ohne Controller | JA | Controlled-Path | NEIN | Bis AP-SRV-070 behalten |
| L010 | `api_fastapi_server/server.py` | `_on_recording_stop` (legacy branch) | 5430, 5448-5450 | Legacy-Aufnahmestopp ohne Controller | JA | Controlled-Path | NEIN | Bis AP-SRV-070 behalten |
| L011 | `api_fastapi_server/server.py` | `_legacy_activation_sequence` | 2758 | Legacy-Sequence-Counter | JA | `_activation_sequence` | NEIN | Bis AP-SRV-070 behalten |
| L012 | `api_fastapi_server/server.py` | `_trigger_ack` | 3472-3483 | v1-Ack-Format | JA | v2 `command.ack` | NEIN | Bis AP-SRV-070 behalten |
| L013 | `api_fastapi_server/activation_commands.py` | `_normalized_action` | 179 | Alias-Normalisierung | JA | Direkt-Lookup | NEIN | Bis AP-SRV-070 behalten |
| L014 | `api_fastapi_server/protocol_v2/connection.py` | `_handle_activation_command` | 365-381 | v2-zu-v1-Bridge | JA | Direkt-v2-Handling | NEIN | Bis AP-SRV-070 behalten |

---

## STILL_ACTIVE_REQUIRED

| ID | Datei | Symbol/Bereich | Zeile | Funktion | Runtime-erreichbar | Ersatz | Wake-Word-Zone | Aktion |
|---|---|---|---|---|---|---|---|---|
| L015 | `api_fastapi_server/server.py` | `RecorderBackedRealtimeSession.__init__` | 2791 | Branch auf controlled/legacy | JA | N/A | NEIN | Behalten |
| L016 | `api_fastapi_server/server.py` | `resolve_session_activation_config` | 1124 | Setzt mode="legacy" ohne Flags | JA | N/A | NEIN | Behalten |
| L017 | `api_fastapi_server/server.py` | `forced_finalizations` | 2739 | Force-Finalize-Counter | JA | N/A | NEIN | Behalten |
| L018 | `api_fastapi_server/server.py` | `_force_finalize_in_progress` | 2743 | Force-Finalize-Guard | JA | N/A | NEIN | Behalten |
| L019 | `api_fastapi_server/server.py` | `_force_finalize_after_limit` | 5949-5973 | Max-Duration-Enforcement | JA | N/A | NEIN | Behalten |
| L020 | `api_fastapi_server/server.py` | `_on_recording_start` (controlled branch) | 5287-5336 | Controlled-Path | JA | N/A | NEIN | Behalten |

---

## PUBLIC_LIBRARY_API_OUT_OF_SCOPE

| ID | Datei | Symbol/Bereich | Zeile | Funktion | Runtime-erreichbar | Ersatz | Wake-Word-Zone | Aktion |
|---|---|---|---|---|---|---|---|---|
| L021 | `VoiceSTT/audio_recorder_client.py` | `AudioToTextRecorderClient` | 87 | Client-Library für Server | JA (nur Legacy-CLI) | WebSocket v2 | NEIN | Server-seitig nicht bewerten |

---

## EXCLUDED_WAKEWORD_ZONE

| ID | Datei | Symbol/Bereich | Zeile | Funktion | Wake-Word-Zone | Aktion |
|---|---|---|---|---|---|---|
| L022 | `docs/wake-words.md` | Gesamt | - | Wake-Word-Dokumentation | JA | Nach SRV-060 prüfen |
| L023 | `VoiceSTT/core/wakeword.py` | Gesamt | - | Wake-Word-Detection | JA | Nach SRV-060 prüfen |
| L024 | `VoiceSTT/core/openwakeword_catalog.py` | Gesamt | - | Wake-Word-Katalog | JA | Nach SRV-060 prüfen |

---

## Zusammenfassung

| Kategorie | Anzahl |
|---|---|
| REMOVE_CANDIDATE | 5 |
| MIGRATION_CANDIDATE | 1 |
| KEEP_COMPATIBILITY | 8 |
| STILL_ACTIVE_REQUIRED | 6 |
| PUBLIC_LIBRARY_API_OUT_OF_SCOPE | 1 |
| EXCLUDED_WAKEWORD_ZONE | 3 |
