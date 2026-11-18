# AP-SRV-070 — KOMPAKTE AUSFÜHRUNGSÜBERSICHT

**Status:** Planungsentwurf
**Ziel:** Server-V2 finalisieren, Altlasten entfernen, Package/Docker/Release fertigstellen.

## W0 — Delta-Revalidation / Scope Freeze
- Alte 070-Discovery gegen finalen SRV-060-Stand prüfen.
- Bestätigen, was wirklich noch entfernt/geändert werden muss.
- Besonders: Legacy-Pfade, v1/v2-Grenze, Wake-Word-Altpfade, Packaging/Docker-Lücken.
- Kein Produktcode, kein neuer Worktree.
- Ergebnis: verbindliche Aufgabenliste für W1–W6.

## W1 — Runtime & Legacy Hard Cut
- Nachweislich tote Legacy-/Compatibility-Pfade entfernen.
- Alte Wake-/Trigger-/Loader-/Config-Pfade bereinigen, soweit W0 bestätigt.
- v1/v2 sauber trennen und negative Boundary-Tests ergänzen.
- Fokus nur auf Runtime/Protokoll, noch keine große Doku-/Release-Arbeit.

## W2 — Product Surface / Docs / Repo Hygiene
- README und aktive Produktdoku auf finalen Produktstand bringen.
- Getting Started, Konfiguration, API v2, Settings, Wake Words, Betrieb usw. ordnen.
- WIP-/Debug-/temporäre Reste aus der aktiven Produktoberfläche entfernen.
- Historische Evidence bleibt im Archiv erhalten.

## W3 — Packaging & Installed Distribution
- Wheel + sdist sauber bauen.
- Package-Version, Build-Backend, Entry Points und Resources eindeutig machen.
- Beweisen, dass Wake-Word-Assets im installierten Paket vollständig enthalten sind.
- Smoke-Test gegen installierte Distribution, nicht gegen Source-Checkout.
- Noch kein PyPI-Upload.

## W4 — Production Docker / Deployment
- Production-Image herstellen.
- Installiertes Package statt Source-Checkout als Runtime verwenden.
- Healthcheck, Shutdown, non-root soweit sinnvoll, OCI-Metadaten, keine Secrets/Dev-Reste.
- Lokaler Build-/Start-/API-/Wake-Word-/Shutdown-Smoke.
- Noch kein Registry-Push.

## W5 — Release Candidate Audit
- Vollständige Regression des kumulativen AP-SRV-070-Standes.
- Package-, Asset-, Docker-, Protocol- und Lifecycle-Prüfung.
- Release-Version einfrieren und RC-Artefakte hashen.
- Danach vollständiger adversarial Root Review.
- Nur ROOT PASS erlaubt W6.

## W6 — Canonicalization & Release
- Genau ein AP-SRV-070 Aggregate-Commit auf Canonical.
- Release-Tag.
- PyPI-Veröffentlichung + frischer Install-Smoke.
- Container Registry Push + Fresh-Pull-Smoke.
- GitHub Release + Tracking-/Archivabschluss.
- Keine Veröffentlichung bei Root FAIL.

## Git-Prinzip
- Canonical bleibt bis zum finalen ROOT PASS unverändert.
- Distributed enthält jeden eingereichten Agenten-/Korrekturrun kumulativ.
- Temporäre Worktrees/Branches werden nach Abschluss wieder entfernt.
