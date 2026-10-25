# AP-KR-020 Abschluss – Startakte zur isolierten Nachfolgeintegration

Datum: 2026-10-25. Eigener Branch `work/ap-kr-020-abschluss`, eigener
Worktree `voice-stt-server-ap020-abschluss`, Basis exakt
`origin/feat/v2-unified-kroko` nach Merge von PR #13.

## Verifizierter Ausgangsstand (vor fachlicher Integration)

- `origin/feat/v2-unified-kroko` = `d8d6efc3843235a9e11bdf7d75ffde8d61ecc02f`
  (Merge PR #13: vorbereiteter dynamischer Modellkatalog).
- `origin/feat/v2-unified-kroko-ap020` (alter PR #12, BLOCKED-Draft) =
  `454e497fff4c0b1f466de03f536a13cf7bce522a`.
- `origin/work/ap-kr-020-restintegration` =
  `03b813f27b4f707758ca14bdd1cf5d7d59edeb88` (7 Commits über PR #12:
  `6a7c076`, `6522786`, `aedf4c8`, `c855e9e`, `743a8ca`, `d4e2013`,
  `03b813f`).
- `origin/work/v2-stt-model-management-integration` =
  `220a7191bbbbfb2002f7221894976f27b03a40f2` (unverändert, wird nicht
  angefasst).
- Ancestry: `git merge-base --is-ancestor
  origin/feat/v2-unified-kroko-ap020
  origin/work/ap-kr-020-restintegration` = Exit 0 (PR #12 ist Vorfahr).
- `git worktree list` geprüft: kein bestehender Worktree/Branch/PR
  überschrieben, resetet oder umbenannt. Angeforderter P-Pfad war frei;
  lokaler Branch wurde auf korrekter Basis angelegt und liegt im neuen
  separaten Worktree. STTM-Integrationsworktree nur als
  Git-Verwaltungsstartpunkt gelesen, nicht geändert.

## Gelesene Pflichtakten

- `AGENTS.md`, `docs/.archiv/README.md`,
  `docs/2026-10-22_kroko-unified-runtime-v2.md` (Fachdoku),
  `build/BUILD.md` (kanonische Buildreferenz).
- AP-KR-020-Akten aus dem Restintegrationsbranch (im Zielbranch noch nicht
  vorhanden): `2026-10-22_SCHNITTSTELLEN_LIFECYCLE.md`,
  `2026-10-23_FORTSETZUNG_LIZENZENTSCHEIDUNG.md`,
  `2026-10-24_RESTINTEGRATION_PLAN.md` sowie Gesamtplan
  `2026-10-22_GESAMTPLAN.md`.

## Geplante enge Integration (nächster Schritt, noch nicht ausgeführt)

1. `origin/work/ap-kr-020-restintegration` mit erhaltener Historie per
   normalem Merge in `work/ap-kr-020-abschluss` übernehmen (kein
   Rebase/Cherry-Pick; PR-#12-Head nicht separat mergen).
2. Danach Ancestry beider Seiten, `git diff --check` und
   `git diff --name-status origin/feat/v2-unified-kroko...HEAD` prüfen.
   Harter Scope: keine STTM-Neuentwicklungen (`voice_stt_server/models/`,
   `tests/unit/test_stt_download_jobs.py`,
   `tests/unit/test_stt_management_v2.py`, keine neuen STT-HTTP-Routen),
   keine `/ws/v2`-Wire-Änderung, keine Produkterechte-/Manifest-/Lizenz-
   Neuimplementierung.
3. Fokussierte Tests laut Auftrag ausführen, CI für den neuen Branch
   abwarten, externe Lizenz-/Portal-/Produktivkontakte unterlassen.
4. Getrennte datierte Ergänzungsakte mit Originalprompt 1:1, Ablauf,
   Nachweisen, Teilfunktionen, Blockern und Soll/Ist-Abweichungen anlegen;
   `docs/.archiv/README.md`-Register erst dort ergänzen.
5. Nur bei konfliktfreier Integration + Nachweisen: Push (nur dieser
   Branch, kein Force) und Draft-Nachfolge-PR gegen
  `feat/v2-unified-kroko`. PR #12 bleibt unberührt.

## Offener externer Blocker (unverändert)

Unabhängige Kroko-Lizenz-/Modellrechte-/Widerrufs-/Aktualitätsqualifikation
fehlt. Unit-Test, Native-Mock, Portalkatalogliste oder Server-Key sind kein
Pro-Entitlement. Übernahme nur fail-closed, ohne unqualifizierte
Pro-Aktivierung.
