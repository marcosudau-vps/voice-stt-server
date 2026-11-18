# 02_RUNTIME_REACHABILITY_MAP

**Discovery-Basis:** `c901cda3f2c19eeb78c468524161728498b6e27e`
**Datum:** 2026-08-28

---

## A. Alte Session-Pfade

### A1: `RealtimeSession` (DEAD)

```
api_fastapi_server/server.py:2249  class RealtimeSession
    └── __init__:2256  → VoiceActivityDetector (L002, ebenfalls dead)
    └── handle_trigger_command  → ActivationController-ähnliche Logik
    └── feed_audio  → eigene VAD-Entscheidung

Instanziierung: KEINE im Produktivcode.
Einziger Verweis außerhalb der Definition: Typannotation server.py:4359.
Fazit: Vollständig dead, kann entfernt werden.
```

### A2: `VoiceActivityDetector` (DEAD)

```
api_fastapi_server/server.py:2213  class VoiceActivityDetector
    └── verwendet webrtcvad + Energie-Fallback
    └── einziger Nutzer: RealtimeSession.__init__ (L001)

Fazit: Nur von L001 genutzt, mit L001 entfernbar.
```

---

## B. v1 Trigger-Pfade

### B1: v1 trigger/trigger_ack (COMPATIBILITY)

```
/ws/transcribe  (server.py:9206)
    └── Client sendet: {"type":"trigger","action":"activate","source":"manual","commandId":…}
    └── Server parst: server.py:3043-3070 (handle_trigger_command)
    └── → ActivationController.activate(source)
    └── → _trigger_ack(server.py:3472-3483)
    └── → sendet {"type":"trigger_ack", ...}

Status: AKTIVE Runtime-Kompatibilität. Desktop-Client sendet v1-Trigger.
Nach AP-SRV-070: Kandidat für Entfernung, wenn Desktop-Client vollständig auf v2 umgestellt.
```

### B2: v1 `extend`-Alias → `refresh` (REMOVABLE)

```
/ws/transcribe
    └── Client sendet: {"type":"trigger","action":"extend",...}
    └── activation_commands.py:179  _normalized_action
        └── ACTION_ALIASES.get("extend") → REFRESH
    └── → ActivationController.refresh()

Status: Parser-Kompatibilität. extend ist semantisch tot,
wird nur noch als refresh normalisiert.
```

### B3: `extensionSeconds` Query-Field (REMOVABLE)

```
server.py:948-953  SESSION_ACTIVATION_RETIRED_QUERY_FIELDS = ("extensionSeconds",)
    └── Wird in resolve_session_activation_config verwendet
    └── Filtert alte URL-Parameter heraus, ohne sie zu rejected

Status: Harmloser Migrationscode. URL mit extensionSeconds wird toleriert.
Entfernbar in AP-SRV-070.
```

---

## C. Source-Merge / Mehrfachautorität

### C1: `ActivationController.activate()` – Merge-Zweig

```
activation.py:164  activate(source)
    └── Wenn Phase ∈ OPEN_WINDOW_PHASES:
        └── Quelle wird an sources angehängt → "merged"
        └── oder → "already_active"

Status: AKTIV, aber nur im v1-Transport relevant.
Im v2-Transport ist der Desktop-Client so gebaut, dass er
während offener Activation keine zweiten activate sendet.
Wake-Word-Callback (server.py:4083-4090) nutzt denselben
Merge-Zweig → EXCLUDED_WAKEWORD_ZONE.

Fazit: Merge-Zweig ist funktional korrekt für den v1-Pfad.
Kein Remove-Candidate ohne vollständige v1/v2-Abgrenzung.
```

---

## D. Modeautorität

### D1: `activation_config.mode` (legacy/controlled)

```
server.py:1124  resolve_session_activation_config
    └── Ohne trigger flags → mode="legacy"
    └── Mit trigger flags → mode="controlled"

server.py:2791  RecorderBackedRealtimeSession.__init__
    └── mode == "controlled" → ActivationController
    └── mode == "legacy" → Recorder-getriebener Lifecycle

Status: AKTIVE Runtime-Autorität. Dies ist die kanonische
Weiche zwischen dem neuen und dem alten Pfad.
Nach AP-SRV-070: Wenn alle Clients trigger flags senden,
kann der legacy-Zweig entfallen.
```

---

## E. Additive Extension

### E1: Controller-Level

```
activation.py:204  extend(source)
    └── segment_active → pending_extension += extension_seconds
    └── sonst → deadline = max(now, deadline) + extension_seconds

Status: Die additive Semantik IST ENTFERNT.
test_the_additive_extend_semantics_is_gone_from_the_controller
beweist das. Die Methode existiert aber noch mit nicht-additiver
Semantik (refresh-artig). → KEEP_COMPATIBILITY
```

---

## F. Finalizing-Reste

### F1: `finalized()` Methode

```
activation.py:312-320  finalized()
    └── Erlaubt nur aus Phase "finalizing"
    └── Transition → inactive
    └── grep zeigt: KEIN AUFRUFER im Server-Paket

Status: DEAD. Phase "finalizing" wird nur über activate()
oder reset() verlassen. finalized() kann entfernt werden.
```

### F2: `finalizing` Phase

```
activation.py:34  FINALIZING = "finalizing"
    └── Erreicht über _close_window_locked(finalize=True)
    └── Verlassen nur über activate() oder reset()
    └── Kein finalized()-Aufruf

Status: PARTIALLY DISCONNECTED. Phase wird betreten aber
der kanonische Exit (finalized()) wird nie aufgerufen.
Im v2-Protokoll ist "closing_input" der Ersatz.
Im v1-Protokoll ist "finalizing" noch der Abschlusstransition.
→ KEEP_COMPATIBILITY bis v1-Transport entfernt wird.
```

---

## G. Legacy-Follow-up

### G1: `_start_wakeword_followup_window`

```
server.py:3924-3982  _start_wakeword_followup_window
    └── Timer-Thread für Legacy-Follow-up
    └── Aufruf steht hinter: if self._activation is None
    └→ Nur im Legacy-Admissionmodus erreichbar

Status: EXCLUDED_WAKEWORD_ZONE + KEEP_COMPATIBILITY.
Wake-Word-bezogen UND legacy-only.
Nach SRV-060 + AP-SRV-070: Remove-Candidate.
```

---

## H. Settings-/Config-Legacy außerhalb Wake Word

### H1: Keine doppelte Timing-Quelle gefunden

```
Alle Timing-Konfiguration fließt über:
    ActivationTimingPolicy (server.py)
    SessionSettingsState (settings_control.py)

Keine alte Runtime-Autorität außerhalb SRV-050 Settings-Control-Plane gefunden.
```

---

## I. Alte Session-Admission

### I1: v1 Admission via Query-Parameter

```
server.py:9206  /ws/transcribe
    └── Query-Parameter: manualTriggerEnabled, wakeWordTriggerEnabled
    └→ Session-Admission ohne Handshake
    └→ Server sendet hello sofort
    └→ Compact-Hex-Session-ID (uuid.uuid4().hex)

Status: AKTIVE Runtime-Kompatibilität.
Desktop-Client nutzt diesen Pfad noch.
Nach AP-SRV-070: Kandidat für Deprecation.
```

### I2: v2 Admission via Hello-Handshake

```
server.py:9415  /ws/v2
    └→ Client sendet hello mit supportedProtocolVersions
    └→ Server validiert vollständig
    └→ Canonical-UUID-Session-ID
    └→ snapshot wird mit hello.accepted geliefert

Status: KANONISCH. Kein Legacy.
```

---

## Zusammenfassung

| Pfad | Entry Point | Runtime-Status | Kategorie |
|---|---|---|---|
| RealtimeSession | Keiner (dead) | DEAD | REMOVE |
| VoiceActivityDetector | Nur via RealtimeSession | DEAD | REMOVE |
| v1 trigger/trigger_ack | /ws/transcribe | AKTIV | COMPATIBILITY |
| v1 extend alias | /ws/transcribe | AKTIV (normalisiert) | REMOVE |
| extensionSeconds query | URL-Parsing | AKTIV (ignoriert) | REMOVE |
| Mode legacy/controlled | Admission | AKTIV | STILL_ACTIVE |
| finalized() | Kein Aufrufer | DEAD | REMOVE |
| finalizing phase | ActivationController | PARTIALLY CONNECTED | COMPATIBILITY |
| Legacy-Follow-up | Wake-Word-Path | AKTIV (legacy only) | EXCLUDED_WAKEWORD_ZONE |
| v1 Admission | /ws/transcribe | AKTIV | COMPATIBILITY |
| v2 Admission | /ws/v2 | KANONISCH | STILL_ACTIVE |
