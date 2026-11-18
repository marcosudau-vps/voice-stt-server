# AP-SRV-070 — W1A SCOPE TRACE

**Datum:** 2026-08-29
**Teilblock:** W1A — Protocol / Session / Activation / Lifecycle Hard Cut
**Scope Authority:** `Prep/W0/2026-08-29_W0_DELTA_REVALIDATION.md`,
`Prep/W0/2026-08-29_W0_SCOPE_MATRIX.md`,
`Prep/W0/2026-08-29_W0_EXECUTION_BACKLOG.md` (Status: `VALIDATED / SCOPE_FROZEN`)
**Arbeitsbranch:** `work/AP-SRV-070`
**Worktree:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070`

---

## 1. W1A-Zuschnitt gegenüber W0-Block W1

W0 definiert Block W1 mit fünf Positionen. W1A ist laut Auftrag ausschließlich
für Protocol-, Session-, Activation-, Command-/Timer-Lifecycle und die
zugehörigen negativen Boundary-Tests zuständig. Die Wake-Word-spezifische
Legacy-Bereinigung gehört nicht in diesen Lauf.

| W0-ID | Titel | W1A | Begründung |
|---|---|---|---|
| W1-01 | Dead Code Removal (`RealtimeSession`, `VoiceActivityDetector`) | **umgesetzt** | Session-Lifecycle-Kern in `server.py` |
| W1-02 | Action Alias Cleanup (`ACTION_ALIASES`, `ACTIVATION_ACTION_ALIASES_PUBLIC`) | **umgesetzt** | Activation-/Command-Vokabular an der v1-Grenze |
| W1-03 | Retired Query Fields (`SESSION_ACTIVATION_RETIRED_QUERY_FIELDS`) | **umgesetzt** | Activation-Admission-Metadaten der v1-Session |
| W1-04 | Wake Catalog Migration (`openwakeword_catalog.py`, `WakeWordRegistry`) | **nicht in W1A** | Wake-Word-spezifische Legacy-Bereinigung; laut Auftrag späterer Teilblock (W1B) |
| W1-05 | Protocol Boundary Negative Tests | **umgesetzt** | Kernauftrag von W1A |

### Abhängigkeitsklärung W1-05 → W1-04

Das W0-Backlog führt für W1-05 die Abhängigkeit `W1-01..W1-04`. Diese
Abhängigkeit ist für W1-04 rein organisatorisch, nicht technisch: die fünf
Akzeptanzkriterien von W1-05 (v1 weist v2-Envelopes ab, v2 ignoriert
v1-Nachrichten, Session-ID-Isolation, `SUPPORTED_PROTOCOL_VERSIONS == (2,)`,
Identitätskonsistenz) berühren den Wake-Word-Katalog an keiner Stelle. Die
Boundary-Tests laufen im vorliegenden Lauf ohne W1-04 grün und wurden gegen
Baseline und Zielstand geprüft (siehe Testreport). W1-04 bleibt für W1B offen.

---

## 2. Scope-Matrix-Positionen im W1A-Zielbereich

| S-ID | Klassifikation | Gegenstand | Behandlung in W1A |
|---|---|---|---|
| S01 | `CONFIRMED_REMOVE` | `server.py::RealtimeSession` | **entfernt** (Reachability bewiesen) |
| S02 | `CONFIRMED_REMOVE` | `server.py::VoiceActivityDetector` | **entfernt** (Reachability bewiesen) |
| S03 | `CONFIRMED_REMOVE` | `activation_commands.py::ACTION_ALIASES` | **entfernt**, `_normalized_action` ist Passthrough |
| S04 | `CONFIRMED_REMOVE` | `server.py::SESSION_ACTIVATION_RETIRED_QUERY_FIELDS` | **entfernt** inkl. Capability-Feld |
| S05 | `CONFIRMED_REMOVE` | `server.py::ACTIVATION_ACTION_ALIASES_PUBLIC` | **entfernt** inkl. Capability-Feld |
| S06 | `SUPERSEDED_ALREADY` | `ActivationController.finalized()` / Phase `finalizing` | **verifiziert, keine Änderung** |
| S09 | `KEEP_REQUIRED` | `activation_config.mode == "legacy"` | **unverändert** |
| S10 | `KEEP_REQUIRED` | `_compat_final_context` | **unverändert** |
| S11 | `KEEP_REQUIRED` | `_start_wakeword_followup_window` | **unverändert** |
| S12 | `KEEP_REQUIRED` | `_trigger_ack` (v1-Ack-Format) | **unverändert** |
| S13 | `KEEP_REQUIRED` | v2→v1-Bridge in `protocol_v2/connection.py` | **unverändert** (Namenskorrektur siehe unten) |
| S14 | `OUT_OF_SCOPE` | `AudioToTextRecorderClient` | **nicht angefasst** |
| S15 | `NEEDS_RUNTIME_PROOF` | Negative Boundary Tests | **Proof erbracht** (neue Testdatei) |
| S16 | `NEEDS_RUNTIME_PROOF` | Server-Identitätskonsistenz | **Proof erbracht** |
| S07/S08 | `MIGRATE_BEFORE_REMOVE` | Wake-Word-Katalog | **nicht in W1A** (W1B) |
| S17–S32 | diverse | Doku, Packaging, Docker, Release | **nicht in W1A** (W2–W6) |

---

## 3. Reachability-Beweise vor jeder Entfernung

Für jeden `CONFIRMED_REMOVE`-Kandidaten wurden die sieben vom Prompt
geforderten Prüfschritte durchlaufen. Suchraum war der gesamte Arbeitsbaum ohne
`.git`; historische Akten unter `docs/.archiv/` wurden gelesen, aber nicht
verändert.

### S01 `RealtimeSession`

| Prüfschritt | Ergebnis |
|---|---|
| Symbol-/Pfadsuche | 3 Fundstellen: Definition `server.py:2292`, Typannotation `server.py:6391`, historische Planungsdatei `api_fastapi_server/MULTI_USER_IMPLEMENTATION_GUIDE.md:370` |
| Direkte Caller | **0 Instanziierungen.** Die reale Sessionerzeugung (`server.py:6752`) baut `RecorderBackedRealtimeSession` |
| Indirekte Registrierung | keine Registry, kein Dispatch-Table-Eintrag |
| Reflection / dynamische Nutzung | `globals()`, `getattr(sys.modules...)`, `eval`, `exec`, `importlib` kommen in `server.py` nicht vor; kein `__all__` |
| Imports / Side Effects | keine Importe der Klasse; die Klassendefinition selbst hat keine Modul-Seiteneffekte |
| Tests | keine Testreferenz |
| Doku / Config | einzige Nennung ist das historische, für W2 zur Archivierung vorgesehene Guide-Dokument. Kein Runtimevertrag betroffen, daher in W1A nicht angefasst |

**Entfernt:** `server.py` Zeilen 2256–2724 (gemeinsamer Block mit S02);
Typannotation `server.py:6391` auf `RecorderBackedRealtimeSession` korrigiert.

### S02 `VoiceActivityDetector`

| Prüfschritt | Ergebnis |
|---|---|
| Symbol-/Pfadsuche | 2 Fundstellen: Definition `server.py:2256`, Nutzung `server.py:2299` |
| Direkte Caller | ausschließlich `RealtimeSession.__init__` (S01) |
| Indirekte Registrierung | keine |
| Reflection | keine (siehe S01) |
| Imports / Side Effects | `webrtcvad` wird nur innerhalb der Klasse lokal importiert |
| Tests | keine Testreferenz |
| Doku / Config | keine |

**Entfernt** zusammen mit S01. Mit dem Wegfall von S01 ist S02 nachweisbar tot.

### S03 `ACTION_ALIASES`

| Prüfschritt | Ergebnis |
|---|---|
| Symbol-/Pfadsuche | Definition `activation_commands.py:52`, Nutzung `activation_commands.py:179`, historischer Report unter `docs/.archiv/...AP-SRV-030...` |
| Direkte Caller | nur `_normalized_action` |
| Indirekte Registrierung | keine; der strikte v2-Parser (`protocol_v2/commands.py`) hat den Alias nie gekannt |
| Reflection | keine |
| Imports | `server.py` importiert den Namen nicht |
| Tests | `test_server_activation_commands.py::test_the_deprecated_extend_alias_normalises_to_refresh` beschrieb genau die entfallende Semantik und wurde auf das neue Sollverhalten umgeschrieben. Die v2-Tests (`test_protocol_v2_contract.py`, `test_protocol_v2_e2e.py`) forderten schon vorher Ablehnung und blieben unverändert |
| Doku / Config | zwei aktive Vertragsdokumente nannten den Alias als zulässig; angepasst (siehe §5) |

### S04 `SESSION_ACTIVATION_RETIRED_QUERY_FIELDS` / S05 `ACTIVATION_ACTION_ALIASES_PUBLIC`

| Prüfschritt | Ergebnis |
|---|---|
| Symbol-/Pfadsuche | je Definition und je eine Verwendung in `session_capabilities()` |
| Direkte Caller | ausschließlich der Capability-Dictionary-Aufbau |
| Filterlogik | Für `extensionSeconds` existiert **keine** eigene Filterlogik im Parameter-Extraktor. Der Parameter wird schon dadurch ignoriert, dass er nicht gelesen wird; die Konstante war reine Ankündigung. Das W0-Backlog nennt „die Konstante und die Filterlogik“ — die Akzeptanz ist erfüllt, weil beides nach der Entfernung nachweislich nicht mehr existiert |
| Reflection | keine |
| Tests | keine Testreferenz auf `deprecatedActionAliases` oder `retiredQueryParameters` |
| Clients | `app_browserclient`, `api_fastapi_server/static/index.html` und `app_webserver` lesen keines der beiden Felder und senden `extend` nicht |
| Doku | zwei aktive Vertragsdokumente zeigten beide Felder im Capability-Beispiel; angepasst (siehe §5) |

---

## 4. Pflichtprüfung `ActivationController.finalized()` (Prompt §5)

W0 klassifiziert diesen Punkt als `SUPERSEDED_ALREADY` — also nicht als offen.
Die Klassifikation wurde am Arbeitsstand nachgeprüft und bestätigt:

- `api_fastapi_server/activation.py` enthält weder `finalized` noch
  `finalizing`/`FINALIZING` (0 Treffer).
- Die kanonischen Phasen sind unverändert `IDLE`, `WAITING_FIRST_SPEECH`,
  `SEGMENT_ACTIVE`, `FOLLOWUP_WAIT`, `CLOSING_INPUT`
  (`activation.py:65–69`).

Daraus folgt: keine Caller-Analyse nötig, kein RED-Test, keine Änderung.
`test_server_activation_controller.py` hält die Abwesenheit bereits fest
(`assertFalse(hasattr(self.controller, "extend"))`).

---

## 5. Dokumentationsanpassungen (Prompt §9)

Nur die Stellen, an denen der Runtimevertrag nach dem Cut sonst falsch wäre.
Keine Reorganisation, keine Archivänderung.

| Datei | Änderung |
|---|---|
| `docs/client-development/02-websocket-protokoll.md` | Capability-Beispiel: `deprecatedActionAliases` und `retiredQueryParameters` entfernt; Aussage „`extend` bleibt zulässig“ durch das neue Sollverhalten (`invalid_action`) ersetzt |
| `docs/einheitliche-triggerarchitektur.md` | dieselben zwei Capability-Felder entfernt; Verweis „Die Capability nennt ihn unter `retiredQueryParameters`“ und die Aussage „`extend` bleibt zulässig“ korrigiert |

`docs/einheitliche-triggerarchitektur.md:953` („den v1-Alias `extend` gibt es in
v2 nicht“) bleibt unverändert — die Aussage war und ist korrekt.

---

## 6. Abweichungen und Anmerkungen für W1B/W2

1. **S13-Symbolname.** W0 nennt als v2→v1-Bridge
   `protocol_v2/connection.py::_handle_activation_command`. Unter diesem Namen
   existiert die Methode nicht; die Bridge heißt tatsächlich
   `_apply_activation_command` (`connection.py:368`) und ruft
   `session.handle_trigger_command()`. Der geschützte Anker ist damit eindeutig
   identifiziert und wurde nicht angefasst. Es handelt sich um eine
   Benennungsungenauigkeit in W0, nicht um einen widersprüchlichen
   Klassifikationsbefund — daher kein Stop-Gate.
2. **Stale Formulierung in `protocol_v2/schema.py`.** Der Moduldocstring sagt
   „Der v1-Transport behält seine kompakten Ids bis AP-SRV-070“. W0 friert die
   kompakten v1-Ids jedoch ein: Invariante 3 verlangt ausdrücklich, dass eine
   32-stellige v1-Id auf v2 abgelehnt wird. Eine Umstellung der v1-Ids ist in
   keiner W0-Position enthalten. Die Formulierung wurde deshalb **nicht**
   geändert (kein eingefrorener Vertrag wird in einem Umsetzungslauf
   erweitert). Offener Entscheidungsbedarf für W2: Formulierung schärfen oder
   Umstellung als eigene Position aufnehmen.
3. **W1-04** (Wake-Word-Katalogmigration) bleibt vollständig offen und ist die
   erste Position für W1B.
