# AP-SRV-030 – Root-Abnahme

**Status:** PASS  
**Datum:** 2026-08-27  
**Arbeitsblock:** Einheitliche Triggerarchitektur  
**Repository:** `marcosudau-vps/voice-stt-server`

## Abgenommene Basis

- Start / AP-SRV-020 PASS: `8535ee79bb2d898d9897e91b57d6a735c479edf0`
- getesteter C3-Candidate: `1d9a4b26ce04de54c25b7e3afad7f7a96809ec91`
- getesteter C3-Code-/Dokumentations-Tree vor Einfügung dieser Root-Abnahme: `a61584db3397f388e3039f69082d5befce025b68`
- CI-Validierung: GitHub Actions Run `33028252444`, Windows Server 2025, Python 3.12.10
- Evidence-Artifact: `AP-SRV-030-C3-validation-evidence`, Artifact-ID `9629327610`
- Artifact-ZIP SHA-256 laut GitHub Actions: `15e9257a4009899409099e3211af632595ec00c11d6033ce66790188fb1bb784`

Der finale kanonische AP-SRV-030-Commit wird als genau ein Commit direkt auf AP-SRV-020 erzeugt. Sein Produkt-/Test-/Dokumentationsinhalt entspricht exakt dem oben genannten vollständig getesteten C3-Tree; diese Datei ist die anschließend in denselben finalen AP-Commit aufgenommene Root-Abnahme.

## Verifizierte Korrekturen

### PHASE-04 – Safe Close vor Idle/Unlock

Der Close-Pfad registriert das logische `activation.input_closed`/Legacy-`activation_closed`-Ereignis vor dem Übergang des Foreground-Slots nach `idle`:

1. generation-bound Gate schließen,
2. Recorder stoppen/flushen,
3. Ledger-Input-Close registrieren,
4. logisches Input-Close-Ereignis registrieren,
5. identity-bound `input_closed()` / Idle,
6. Transport-Publikation des bereits registrierten Ereignisses.

Damit kann keine neue Activation zwischen sicherem Input-Close und logischer Close-Ereignisregistrierung zugelassen werden.

### PHASE-05 – unrecoverable Closing Recovery

Kann der alte Eingabepfad selbst durch Hard-Abort nicht sicher geschlossen werden, wird die Session technisch terminal beendet. Es wird kein wiederverwendbares `idle` behauptet und kein dauerhaft lebender `closing_input`-Zustand hinterlassen.

`closed` ist in `publish_status()` terminal/sticky. Ein verspäteter Timer-/Recorder-/Wake-Callback kann eine bereits geschlossene Session nicht wieder auf `listening`, `wakeword_wait` oder einen anderen nichtterminalen Status setzen.

### Weitere C2/C3-Invarianten

- Controls sind activation-bound und source-neutral.
- Command-Replay und `commandId`-Konflikte sind sessionweit deterministisch.
- Cancel besitzt eine totale Ordnung gegenüber noch unveröffentlichten Final-Resultaten.
- Recovery behält intern die ursprüngliche Close-Command-Identität; die tatsächliche Recovery-Completion projiziert `causedByCommandId=null`.
- Ledger-/Session-Lock-Ordnung ist deadlock-frei festgelegt.
- verspätete Wake-/Lifecycle-Callbacks werden durch Lifecycle-Epochs inert.
- Session-/Streamverlust kann keine alte Activation in einer neuen Session fortsetzen.

## Testevidence

Finaler GitHub-Windows-Lauf `33028252444`:

- C3-Zielregressionen: **2 passed**
- AP-SRV-030-Fokussuite: **197 passed, 82 subtests passed**
- AP-SRV-020-Regression: **53 passed, 3 subtests passed**
- vollständige Unit-Suite: **615 passed, 13 skipped, 167 subtests passed**
- Race-/Recovery-Wiederholung: **20/20 PASS**, je Lauf **21 passed, 4 subtests passed**
- `git diff --check`: PASS
- C3-Dateimenge vor Commit war hart auf genau vier C3-Dateien begrenzt.
- Candidate-Worktree nach Commit: clean.

Die einzige Warnung der Vollsuite war eine externe Starlette/httpx-Deprecation-Warnung und kein AP-SRV-030-Fehler.

## Root-Entscheidung

**AP-SRV-030 = PASS.**

Die beiden verbliebenen Root-Befunde B1/PHASE-04 und B2/PHASE-05 sind geschlossen. Der vollständige Candidate hat die fokussierten, regressiven, vollständigen und wiederholten Race-/Recovery-Gates bestanden. Es bestehen keine bekannten offenen AP-SRV-030-Blocker.

AP-SRV-040 darf ausschließlich auf dem final gepushten AP-SRV-030-SHA/Tree starten, die im zentralen Ausführungsregister eingetragen werden.
