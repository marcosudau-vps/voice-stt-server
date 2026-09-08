# AP-SRV-070 W5-R04 — Soll-/Ist-Vergleich

Datum: 08.09.2026
Arbeitspaket: AP-SRV-070, Phase W5 (Release-Infrastruktur)
Run: W5-R04
Ausgangscommit: `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`
Geprüfter Stand: der lokale W5-R04-Implementierungscommit (noch nicht gepusht)

Dieser Vergleich prüft die Umsetzung gegen
[`2026-09-08_W5_R04_PLAN.md`](2026-09-08_W5_R04_PLAN.md). Materielle
Abweichungen sind am Ende getrennt aufgeführt.

## 0. Nachträglich geänderte Produkt-/Packaging-Autorität

Während der Umsetzung ist eine neue verbindliche Produkt- und
Packaging-Autorität hinzugekommen, die dem ursprünglichen Auftrag vorgeht:

VoiceSTT wird künftig als **zwei vollständige, alternative PyPI-Distributionen**
ausgeliefert — `voice-stt-server` (Kroko Free) und `voice-stt-server-pro`
(Kroko Pro). Beide enthalten die jeweilige native Kroko-Laufzeit bereits,
stellen dasselbe Importpaket `voice_stt_server` und dieselbe CLI
`voice-stt-server` bereit und schließen einander aus. Ein separates
öffentliches Kroko-Paket entfällt; ein Endanwender baut Kroko nie selbst.

Die bis dahin umgesetzten Punkte (Kroko-Builder-Pinning, Dockerfile-Digest,
quellabgeleiteter Build-Zeitstempel, neue Zustandsreihenfolge) waren mit dieser
Autorität vereinbar und wurden vollständig weiterverwendet; nichts musste
zurückgenommen werden. Die Planung wurde entsprechend erweitert.

## 1. Ziel-für-Ziel

| Planziel | Stand | Nachweis |
| --- | --- | --- |
| 1. Kandidat vollständig auf frischem GitHub-Runner aus exaktem Commit | **vollständig** | `.github/workflows/release-candidate.yml`, `tools/release_candidate.py`; lokaler Nachweis mit leerem Artefaktspeicher |
| 2. Genau die qualifizierten Bytes/Manifeste werden veröffentlicht | **vollständig** | Manifest-Promotion per Digest in `release_tooling/adapters.py`; kein zweiter Produktionsbuild im Graphen |
| 3. Git-Tag vor der ersten öffentlichen Veröffentlichung | **vollständig** | `STATE_ORDER`, `assert_tag_allowed`, `assert_public_publication_allowed` |
| 4. Docker Hub vor GHCR, GHCR per Digest-Promotion | **vollständig** | `DockerHubAdapter`/`GHCRAdapter`; Test `test_ghcr_promotes_from_docker_hub_by_digest` |
| 5. Aliase erst nach verifizierten exakten Artefakten, danach selbst verifiziert | **vollständig** | `release_tooling/aliases.py`, `AliasAdapter`, `assert_aliases_allowed` |
| 6. GitHub Release als letzter öffentlicher Marker | **vollständig** | `assert_github_release_allowed` verlangt `ALIASES_PUBLISHED` |
| 7. Eine kanonische Zustandsmaschine für Trockenlauf, Publikation, Resume | **vollständig** | `release_tooling/engine.py`; `--until` verkürzt nur, ordnet nie um |
| 8. Wahrheitsgemäßer öffentlicher Dokumentationsstand | **vollständig** | README-Neufassung, `docs/engines/` entfernt, `docs/transcription-engines.md` reduziert |

## 2. Entscheidungen aus der Planung

| Planentscheidung | Stand | Anmerkung |
| --- | --- | --- |
| 4.1 Neue Zustandsreihenfolge | umgesetzt | zusätzlich `ALIASES_PUBLISHED` als eigener Zustand |
| 4.2 Kandidatenpersistenz über private GHCR-Staging-Pakete | umgesetzt | digestgebunden; ein Kandidat ohne Staging-Digest wird abgelehnt |
| 4.3 Freigabegrenze über geschützte Umgebung `release` | umgesetzt | alle vier Publish-Jobs sind an die Umgebung gebunden |
| 4.4 PyPI Trusted Publishing statt Token | umgesetzt | jetzt für **zwei** PyPI-Projekte; Zustandsübergang erst nach verifizierter Fernprüfung |
| 4.5 Kroko-Linux-Fingerprint / Containerdeklaration | umgesetzt | `LINUX_BUILDER_REVISION` 1 → 2; Windows-Autorität unberührt (bleibt 4) |
| 4.6 Quellabgeleiteter Build-Zeitstempel | umgesetzt | aus dem Commit-Zeitstempel; identisch für beide Varianten |

## 3. Abnahmekriterien

| Kriterium | Ergebnis |
| --- | --- |
| Eine kanonische Graph-Autorität | erfüllt |
| Tag vor erster Veröffentlichung, GitHub Release zuletzt | erfüllt |
| Docker Hub vor GHCR, GHCR per Digest-Promotion | erfüllt |
| Aliase erst nach Verifikation, danach selbst verifiziert | erfüllt |
| Frischer Runner ohne Operator-lokale Abhängigkeiten | erfüllt; lokaler Nachweis mit echtem leerem Artefaktspeicher |
| Normale CI kann nichts veröffentlichen | erfüllt (`contents: read` durchgehend) |
| README neu, `docs/engines/` entfernt, beide Guides unter `docs/` | erfüllt |
| Vollständige Unit-/Regressionssuiten grün | erfüllt (Zahlen im Runbericht) |

## 4. Nachweis leerer Artefaktspeicher

Ein neu angelegter, leerer Kroko-Artefaktspeicher wurde verwendet. Beide
Varianten wurden dort real aus der Quelle gebaut:

```text
free  Fingerprint 578d6c898adac1b1  (Build aus der Quelle)
pro   Fingerprint b7f9278878f521f0  (Build aus der Quelle)
```

Die Fingerprints unterscheiden sich, Free und Pro liegen in getrennten
Namensräumen. Ein zweiter Lauf hat das Free-Artefakt validiert wiederverwendet
und das Pro-Artefakt neu gebaut, womit beide Pfade — REUSE mit Revalidierung
und BUILD ONCE — nachgewiesen sind. Beide Produktionsimages wurden aus diesen
Artefakten gebaut; der OCI-Zeitstempel ist bei beiden der quellabgeleitete Wert
`2026-09-07T19:06:57Z`.

## 5. Materielle Abweichungen

Die Abweichungen sind in einer eigenen datierten Datei begründet:
[`2026-09-08_W5_R04_ABWEICHUNGEN.md`](2026-09-08_W5_R04_ABWEICHUNGEN.md).

Kurzfassung:

1. **Kein sdist** für die beiden öffentlichen Distributionen (technisch
   begründet: ein sdist kann die native Laufzeit nicht transportieren).
2. **Zwei Distributionen statt einer** (neue verbindliche Autorität).
3. **`toolchain_identity("linux")` wurde nicht umgebaut**, weil der
   Linux-Fingerprint die reale Toolchain bereits probiert; stattdessen wurde
   der Container deklariert und die Builder-Revision erhöht.
4. **`huggingface_hub` aus dem Kroko-Builder-Image entfernt**, weil es von
   keiner im Image enthaltenen Datei importiert wird.
5. **`--dist-dir` außerhalb des Buildkontexts wird jetzt abgelehnt** statt
   spät und unverständlich zu scheitern.
6. **Registry-Identität ist jetzt der Manifest-Digest** statt der lokalen
   Docker-Image-Id (Korrektur eines bestehenden Fehlers).

## 6. Nicht veröffentlicht

In diesem Run wurde nichts veröffentlicht: kein Push, kein Tag, kein
GitHub Release, kein PyPI-Upload, kein Docker-Hub-Push, kein öffentlicher
GHCR-Schreibzugriff und auch kein Staging-Push. Die GitHub-Ausführung der neuen
Workflows erfolgt erst nach externem Root PASS und exaktem Push.
