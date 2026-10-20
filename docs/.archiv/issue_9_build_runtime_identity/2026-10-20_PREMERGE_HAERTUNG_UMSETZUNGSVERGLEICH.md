# Issue #9 – Vor-Merge-Härtung: Soll-/Ist-Stand

**Plan:** [2026-10-20_PREMERGE_HAERTUNG_PLAN.md](2026-10-20_PREMERGE_HAERTUNG_PLAN.md)
**Ausgangspunkt:** `281129716147c1590942cd7602666435722ab131`.
**Implementierungscommit:** `300934686e5be018043ea65c13f74d806c929ebf`.
**Prüfung:** unabhängig vom ursprünglichen A+B-RC; ein neuer gesamter Kandidatenlauf ist erforderlich.

| Planpunkt | Tatsächlicher Stand |
| --- | --- |
| Historisches Windows-Channelmanifest ohne externen Locator | Byteidentische Originalkopie unter `VoiceSTT/assets/kroko/visual-studio-17.14.39-channel.json` mit `.gitattributes -text -diff`; bei Bezug vor Aufnahme 91833 UTF-8-Bytes und SHA-256 `4c81e902fb7fe2acea779b828e6dc548fe0bbb693df50eda0224263c16686bdd` unabhängig berechnet. |
| Source-/Paketressource | `MANIFEST.in` und `setup.py` nehmen die Datei in sdist, Legacy-Wheel sowie beide public Free-/Pro-Wheels auf. Echte Packagingtests kontrollieren Dateibytes und SHA in Wheel und sdist. |
| Windows-Crossbuild | `stage_windows_channel_manifest` prüft Quelldaten zuerst, kopiert sie in Kroko-Dockerkontext; das generierte Dockerfile verwendet `COPY` und lokales `cp` statt einem URL-Download. Innerhalb des Images werden Bytezahl und SHA vor xwin erneut geprüft; der Download und seine Fallbackoption entfallen ausschließlich für das Channelmanifest. |
| Provenienz/Fingerprints | Eigenständige Windows-Patch-/Builder-Revisionen 4/5; Windows-Toolchainauthority `acd0769f21c4694f`, Windows Free `2c5c203bf1a4b367` und Pro `a847152ec7e2d030`. Aus dem aktualisierten Sourcecode unabhängig berechnete Guard-Digests `b0ca8b0627daadbf34be7e1221861fa18696bda2503ec1f6857b7de361beb94f` (Patch) und `76d3de5d57960c7e836f62cf252d31c42c56a1885d55ca4c320b83bc9562a86e` (Windows-Builder). Unveränderte Linux-Revision. |
| Isoliertes Packagingbackend | `packaging>=24.0` direkt in `pyproject.toml [build-system].requires` aufgenommen. Produktdependencies bleiben bestehen. |
| Manueller vs. offizieller Build | `build/BUILD.md` beschreibt die absichtliche Fail-closed-Strategie für offizielle Produktionsimages und die weiter möglichen unqualifizierten Entwicklungs-/manuellen Python-Paketbuilds; kein neuer Bypass und kein paralleler Dockerreleasepfad. |
| Tests | Golden-Fingerprints, alter commitgebundener Locatorbeleg, stage fail-closed bei fehlendem/falschem Manifest, Docker-COPY/Checksum-Prüfung und echte Wheel-/sdist-Byteprüfung ergänzt. Die automatische GitHub-CI wird separat ausgewertet. |

## Verbindliche Nachweisgrenze

Der [bisherige erfolgreiche A+B-RC](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39359464011) auf `d99633a...` ist **nicht** die Qualifikation des nachträglich geänderten Channel-Authority- oder Quellcommits. Die CI auf dem neuen Implementierungsstand wurde automatisch gestartet, ist in diesem Berichts-Snapshot jedoch **nicht abschließend ausgewertet**. Der komplette neue Linux-/Windows-/Vier-Wheel-/Dockerimage-RC ist zum Zeitpunkt dieser Datei **NOT_RUN**. Er darf nur für den endgültigen neuen HEAD angestoßen werden; dessen Ergebnis bleibt gesondert nachzuweisen.

Die vorstehend algorithmisch ermittelten Fingerprints sind keine Behauptung eines nativen Build-/Installationserfolgs. Der Paketmanifestdownload und weitere gepinnte Toolchainkomponenten benötigen weiterhin externe Bezugsquellen. Keine Umdeklaration des ursprünglichen RC und keine Änderung von Publikation, Promotion, Resume, Wake Word oder Clientprodukt. 
