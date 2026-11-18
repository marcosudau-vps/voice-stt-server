# AP-SRV-070 — W1A IMPLEMENTATION REPORT

**Datum:** 2026-08-29
**Teilblock:** W1A — Protocol / Session / Activation / Lifecycle Hard Cut
**Arbeitsbranch:** `work/AP-SRV-070`
**Worktree:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070`
**Parent (Distributed):** `1e74fec3096778d78c4f91e3916ef272c762ebd3`

---

## 1. Ausgangslage

Vor Beginn der Arbeit wurden alle Vorbedingungen aus Prompt §2 geprüft:

| Prüfung | Erwartet | Gefunden | Ergebnis |
|---|---|---|---|
| Remote Distributed | `1e74fec3096778d78c4f91e3916ef272c762ebd3` | identisch | PASS |
| Remote Canonical | `c82923fc6ce889b4dfbbde1f9877b8b76481a1e8` | identisch | PASS |
| Lokal Distributed | `1e74fec…` | identisch | PASS |
| Lokal Canonical | `c82923f…` | identisch | PASS |
| TREE beider Linien | `de6fe364545b508a47a87ead67a01c5732477e71` | identisch für beide | PASS |
| Canonical-Workspace | clean | `git status --porcelain` leer | PASS |
| Branch `work/AP-SRV-070` | existiert nicht | existierte nicht | PASS |
| Worktree `workspaces/ap-srv-070` | existiert nicht | existierte nicht | PASS |

Der Arbeitsworktree wurde daraufhin exakt von Distributed `1e74fec…` erzeugt
und startete mit TREE `de6fe36…`. Er bleibt für W1B/W2/… bestehen; es wurde
kein zweiter Worktree angelegt.

W0 ist in `2026-08-29_W0_DELTA_REVALIDATION.md` mit
`Status: VALIDATED / SCOPE_FROZEN` abgeschlossen, die Blöcke W1–W6 sind im
Execution-Backlog operationalisiert. W1 ist damit planbar.

---

## 2. Umgesetzte W0-Positionen

### W1-01 — Dead Code Removal (S01, S02)

`api_fastapi_server/server.py`

- `class VoiceActivityDetector` (36 Zeilen) und `class RealtimeSession`
  (433 Zeilen) vollständig entfernt — zusammenhängender Block Zeilen 2256–2724.
- Die einzige verbliebene Referenz war eine veraltete Typannotation in
  `SessionStore.__init__`. Sie wurde auf die real erzeugte Klasse korrigiert:

  ```python
  self._sessions: Dict[str, RecorderBackedRealtimeSession] = {}
  ```

  Das ist keine kosmetische Korrektur: die Annotation eines Attributziels wird
  bei jedem `__init__`-Durchlauf ausgewertet, sie hätte nach der Entfernung
  einen `NameError` geworfen.
- Nach der Entfernung gibt es im gesamten Produktiv- und Testcode keine
  Referenz auf eines der beiden Symbole mehr.

Die Reachability-Beweise stehen vollständig in
`2026-08-29_W1A_SCOPE_TRACE.md` §3.

### W1-02 — Action Alias Cleanup (S03, S05)

`api_fastapi_server/activation_commands.py`

- `ACTION_ALIASES = {"extend": REFRESH}` samt Docstring entfernt.
- `_normalized_action` ist jetzt ein direkter Passthrough:

  ```python
  def _normalized_action(data):
      raw_action = data.get("action")
      if raw_action is not None and not isinstance(raw_action, str):
          return None
      return str(raw_action or "").strip().lower()
  ```

`api_fastapi_server/server.py`

- `ACTIVATION_ACTION_ALIASES_PUBLIC = ("extend",)` entfernt.
- Das Capability-Feld `deprecatedActionAliases` entfällt aus
  `session_capabilities()`.

**Verhaltensänderung:** Der v1-Parser akzeptiert `action: "extend"` nicht mehr.
Die Aktion durchläuft jetzt dieselbe Prüfung wie jede andere unbekannte Aktion
und wird mit `invalid_action` abgelehnt. Damit haben v1 und v2 dasselbe
Aktionsvokabular; der strikte v2-Parser hat den Alias nie gekannt.

### W1-03 — Retired Query Fields (S04)

`api_fastapi_server/server.py`

- `SESSION_ACTIVATION_RETIRED_QUERY_FIELDS = ("extensionSeconds",)` samt
  Docstring entfernt.
- Das Capability-Feld `retiredQueryParameters` entfällt aus
  `session_capabilities()`.

Eine eigene Filterlogik für `extensionSeconds` existierte nicht: der Parameter
wurde nie gelesen, die Konstante diente allein der Ankündigung. Das Verhalten
gegenüber einem alten Client bleibt unverändert — eine URL mit
`extensionSeconds` wird weiterhin akzeptiert und der Wert weiterhin ignoriert;
angekündigt wird er nur nicht mehr.

### W1-05 — Protocol Boundary Negative Tests (S15, S16)

Neu: `tests/unit/test_protocol_v1_v2_boundary.py` (15 Tests, 5 Klassen).
Details im Testreport.

---

## 3. Geschützte Kompatibilitätsanker (`KEEP_REQUIRED`)

Alle fünf Anker wurden nach dem Cut erneut verifiziert und sind unverändert:

| S-ID | Anker | Status nach W1A |
|---|---|---|
| S09 | `activation_config.mode == "legacy"` | 2 Fundstellen, unverändert |
| S10 | `_compat_final_context` | unverändert |
| S11 | `_start_wakeword_followup_window` | unverändert, weiterhin hinter `if self._activation is None:` |
| S12 | `_trigger_ack` (v1-Ack-Format) | unverändert |
| S13 | v2→v1-Bridge (`_apply_activation_command`) | unverändert |

Die entfernten Symbole liegen sämtlich **außerhalb** dieser Anker: der
Legacy-Mode-Pfad benutzt `RecorderBackedRealtimeSession`, nie die entfernte
`RealtimeSession`.

---

## 4. Nicht angefasst

- **W1-04 / S07 / S08** — Wake-Word-Katalogmigration. Laut Auftrag nicht Teil
  von W1A; keine technische Abhängigkeit der Boundary-Tests darauf
  (Begründung im Scope-Trace §1).
- **S14** — `AudioToTextRecorderClient` (`OUT_OF_SCOPE`).
- **S17–S32** — Doku-Reorganisation, Repo-Hygiene, Packaging, Docker, Release
  (W2–W6).
- **`docs/.archiv/**`** — historische Akten unverändert.
- **`api_fastapi_server/MULTI_USER_IMPLEMENTATION_GUIDE.md`** — nennt
  `RealtimeSession` als historischen Entwurfsschritt. Das Dokument ist in W0
  als W2-Archivkandidat (S18) klassifiziert und wurde deshalb nicht editiert;
  ein Runtimevertrag hängt nicht daran.

---

## 5. Dokumentation

Nur die zwei aktiven Vertragsdokumente, deren Aussagen nach dem Cut falsch
gewesen wären:

- `docs/client-development/02-websocket-protokoll.md`
- `docs/einheitliche-triggerarchitektur.md`

Beide Capability-Beispiele zeigen `deprecatedActionAliases` und
`retiredQueryParameters` nicht mehr, und beide Fließtextstellen beschreiben
`extend` jetzt als entfallen statt als zulässig. Keine Reorganisation, kein
Verschieben, keine Archivberührung.

---

## 6. Geänderte Dateien

| Datei | Art |
|---|---|
| `api_fastapi_server/server.py` | Legacy-Cut (Klassen, 2 Konstanten, 2 Capability-Felder), Typannotation |
| `api_fastapi_server/activation_commands.py` | Alias-Cut, Passthrough-Normalisierung |
| `tests/unit/test_protocol_v1_v2_boundary.py` | **neu** — negative Boundary-Regressionen |
| `tests/unit/test_server_activation_commands.py` | v1-Alias-Test auf neues Sollverhalten umgeschrieben |
| `docs/client-development/02-websocket-protokoll.md` | Vertragskorrektur |
| `docs/einheitliche-triggerarchitektur.md` | Vertragskorrektur |
