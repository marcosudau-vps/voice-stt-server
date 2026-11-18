# AP-SRV-070 — W4B
# Production Docker / Deployment / Runtime Qualification

## Auftrag
Baue auf W4A ein produktionsfähiges Container-/Deployment-System. W4B konsumiert ausschließlich das von W4A definierte Kroko-Artefakt; normale Server-Builds dürfen Kroko nicht erneut kompilieren.

## Startbedingungen
Nur starten wenn:
- W4A Root-geprüft PASS
- W4A STATE: W4B ready = JA
- Remote Distributed HEAD == finaler W4A SHA
- Worktree clean
- Canonical unverändert

Sonst: STATUS: BLOCKED

## Git / Worktree
Branch: `work/AP-SRV-070`
Worktree:
`P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070`

Kein neuer Worktree. Kein Force-Push.

## Production Image
Ziel:
- Multi-Stage-Build
- VoiceSTT aus gebautem Wheel installieren, kein editable/source checkout
- Runtime ohne unnötige Compiler/Buildtools
- keine Tests, Prompts, Worklogs, Caches, Secrets
- non-root soweit technisch möglich
- sauberes Signalhandling / SIGTERM
- Healthcheck
- minimale Runtime
- OCI-Metadaten: version, revision, source, created, title

Version/Revision müssen mit W3-Versionauthority und aktuellem Commit übereinstimmen.

## Kroko
- gewünschte Variante free/pro explizit
- passendes W4A-Artefakt anhand Fingerprint/Metadaten auswählen
- Integrität prüfen
- bei fehlendem Artefakt nicht still neu kompilieren
- Force-Rebuild bleibt expliziter W4A/Kroko-Buildpfad
- Pro-Key ausschließlich Runtime-Secret
- kein Secret im Image

## Modelle
- Wake Assets aus installierter Python-Distribution gemäß W3
- Kroko-Modelle gemäß W4A-Modellauthority
- Community nur gemäß geklärter Redistribution/Provisioning-Regel
- Pro nicht öffentlich einbetten ohne eindeutige Berechtigung
- Offline-Produktionsmodus ohne spontane Downloads

## Compose / Deployment
- explizite Image-Referenz
- Config read-only
- Secrets nur Runtime Secret/env_file/Secret Store
- persistente Daten getrennt
- Modellpfade eindeutig
- Ressourcenlimits soweit sinnvoll
- Logging begrenzen/rotieren
- Health-gated dependencies
- keine persönlichen absoluten Pfade als allgemeiner Produktvertrag

## Qualification
Mindestens:
1. Production Image bauen.
2. Nachweis: Kroko wurde bei vorhandenem W4A-Artefakt nicht neu kompiliert.
3. Image auf Source-/Test-/Secret-Leaks prüfen.
4. Container starten.
5. Health ready/ok.
6. Server-Version/Commit/Protocol-Metadaten korrekt.
7. `/api/v2/wake-words` erfolgreich.
8. Wake Assets aus installierter Distribution.
9. Kroko-Runtime für gewünschte Variante importierbar.
10. Variant-/Model-Mismatch klarer Fehler.
11. minimale Session/API-Smokes.
12. SIGTERM sauberer Exit.
13. Recreate funktioniert.
14. `docker compose config` sauber.
15. `git diff --check`.

## Registry-Vorbereitung
Noch nicht veröffentlichen. Image muss für W6 für GHCR und Docker Hub geeignet sein.
Immutable Version-Tags zuerst; `latest`/Major-/Minor-Aliase erst nach vollständigem Release-Erfolg.

## Commit
Genau ein Commit:
`build(server): finalize production container deployment`

Distributed nur Fast-Forward. Canonical unverändert.

## Evidence
`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4B\`

Mindestens:
- `2026-08-29_W4B_CONTAINER_REPORT.md`
- `2026-08-29_W4B_DEPLOYMENT_REPORT.md`
- `2026-08-29_W4B_RUNTIME_SMOKE.md`
- `2026-08-29_W4B_STATE.md`

STATE: Parent, SHA/TREE, Image ID, Version/Revision, Kroko Fingerprint, No-Rebuild Proof, Secret Check, Health/Shutdown, Distributed before/after, Canonical unchanged, W5 readiness.

## Rückgabe
Schick mir alle Dateien aus diesem Ordner.
