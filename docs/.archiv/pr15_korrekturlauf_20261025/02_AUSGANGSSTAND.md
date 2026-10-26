# Korrekturlauf PR #15 – Ausgangsstand (25.10.2026)

## HEAD / PR-Status (verifiziert)

- Bei Auftragserstellung bekannter HEAD: `15d7a89f49bf157cb3b2eb70c2255e001e3cf983`
- Tatsächlicher HEAD bei Arbeitsbeginn (nach `git fetch` + `git pull --ff-only`):
  `15d7a89f49bf157cb3b2eb70c2255e001e3cf983` — stimmt überein, keine Abweichung.
- Dazwischen (gegenüber erstem Auftrag `66d12de`): 5 rein dokumentarische Review-Commits
  (08_ABNAHME-Akte, openai-http-api.md, server-authentication.md, module-map/fastapi-server/README-Verweise,
  Traceability-Richtigstellung). Kein Produktionscode darin.
- Branch `work/kroko-v2-selective-improvements-20261025`, Ziel `feat/v2-unified-kroko`,
  Working Tree clean, kein Merge/Rebase/Force-Push.
- Maßgebliches Review: PR-Kommentar 6401918956 (BLOCKED), ersetzt frühere positive Abnahme;
  Korrekturkommentar 6401796384 und Abnahme 6401307417 bleiben historisch erhalten.

## Ursprüngliche Anforderung (Gesamtplan 22.10.2026)

`pro_enabled = api_key_present AND NOT force_community AND license_validation_successful`,
abgeleitet und flüchtig; automatische Prüfung an Init/Keywechsel/Recheck; Pro-Freigabe an
Modellmanager gebunden; zwei Voll-Distributionen respektiert; echte Lizenztests erforderlich.

## Festgestellte Abweichungen (Review, Kurzfassung)

- H-01: Teilplan erklärte Auto-Freigabe zum Nicht-Ziel ohne offene Nachverfolgung; 20/20-PASS gegen verkürzten Scope.
- H-02: kein produktiver Auto-Check (kein Aufruf in `VoiceSTTService`).
- H-03: kein `force_community`-Setting, kein Key-Änderungs-Hook.
- H-04: `_eligible`/`candidate_eligible` ohne Lizenzbindung; Refresh/Probe vor Lizenzentscheidung.
- H-05: keine Modell-UUID-Zuordnung (Manifest hat keine UUIDs).
- H-06: strikter Variantenguard vs. nativ belegtem Community-unter-Pro; keine Live-Umschaltung erfinden.
- H-07: kein produktiver Generationen-/Ablauf-Lifecycle (Jobs/Sessions/Recheck).
- H-08: Tests belegen alte Scope-Grenze (`does_not_auto_check`-Test); echte Lizenztests fehlen.
- D-01..D-05: Doku markiert SOLL nicht als unerfüllt; 2026-10-22-Seite veraltet; alte Traceability irreführend (wird per Supersession aufgelöst, nicht umgeschrieben); Security-Referenz ohne Entitlement-Grenze/Trigger; Key-/Force-/Neustartsemantik undokumentiert.
- M-01: `public_snapshot().proEnabled` ohne Modellscope. M-02: synchrone Probe, Doppelcheck-Gefahr.
  M-03: fünf kleine Altbefunde (Request-ID, Alias-500, Host-Duplikat, Pruning, Stop-Maskierung).

## Eigene Vorabfeststellungen (neu, für H-05/B3 entscheidend)

- Echte Modell-UUIDs sind in keiner Repo-/VPS-Doku, aber **in jedem lokalen `.data`-Header**
  als JSON `{"id": "<uuid>", ...}` enthalten (alle 6 geprüften Dateien, Pro + Community,
  z. B. DE-Pro-16-L → `b358fad7-…`). Das ist die nachweisbare Zuordnung aus vorhandenen
  technischen Modellinformationen (dieselbe Quelle, die nativ `BanafoLicense` nutzt).
  Keine UUID erfunden; Portal-Katalog (`P:\GithubRepos\marcosudau-vps\kroko-models.json`,
  124 Modelle) führt nur numerische Portal-IDs und keine UUIDs.
- VPS-Secrets: `KROKO_ASR_API_KEY[_SECOND]` (env_file, native liest sie selbst); Server-Resolver
  kennt nur 4 andere Vars + Options-Key (bleibt unverändert). Live-Tests nutzen Options-Key zur Laufzeit.
- Installierte lokale Runtime: upstream `kroko_onnx` 1.12.9 (free). Echte Pro-Modelle lokal
  vorhanden (VPS-Spiegel). Docker-Desktop-Linux-Engine läuft → Pro-Wheel-Build möglich.

## Bestehende Architektur (Kurzfassung)

`SecurityService` (Admin/OpenAI/Logs/Kroko-Adapter getrennt) → `VoiceSTTService` →
`STTModelManager` (alleinige Modell-Authority, LKG, Refresh/Switch) + `settings_control`
(Registry, Overlay-Persistenz `runtime.json`, Admin-PATCH). `KrokoLicenseState` flüchtig,
generationsgebunden, TTL ≤ 60 s. Lifecycle-Punkte: `__init__`/Refresh/Switch/PATCH-Hook
(Pattern `WAKE_WORD_GLOBAL_DISABLED`), Admin-Routen, Lifespan-`finally`.
