# Issue #9 / PR #10 – Planung der ergänzenden Vor-Merge-Härtung

**Stand:** 20.10.2026. Diese Planung wurde vor der nachfolgend beschriebenen Implementierung angelegt. Ausgangspunkt ist der vollständig qualifizierte PR-HEAD `281129716147c1590942cd7602666435722ab131` und der ursprüngliche Produkt-RC auf `d99633a95166d168c2adb8c0fd015f435ff5ec23`.

## Auftrag, Ziel und Grenzen

Drei P2-Punkte des unabhängigen Reviews sollen vor Merge korrigiert beziehungsweise explizit präzisiert werden.

1. **Windows-Channelmanifest lokal:** Das bisher aus einem fremden GitHub-Archiv heruntergeladene rohe Visual-Studio-17.14.39-Channelmanifest wird unter `VoiceSTT/assets/kroko/` bytegleich im Repository und im Python-Wheel/sdist vorgehalten. Originalbytezahl **91833** und SHA-256 **`4c81e902fb7fe2acea779b828e6dc548fe0bbb693df50eda0224263c16686bdd`** sind vor Aufnahme unabhängig zu verifizieren. Der Windows-Cross-Build kopiert ausschließlich diese gebündelte Datei in den Docker-Buildkontext und führt dieselben Byte-/SHA-Prüfungen aus; kein Download und kein Fallback für dieses **Channelmanifest**. Andere gepinnte Microsoft-Komponenten (insbesondere das 17-MB-Paketmanifest) bleiben vorerst externe, SHA-geprüfte Eingänge; **keine Behauptung eines insgesamt netzwerkfreien Kroko-Builds**.
2. **Deklarierte Build-Abhängigkeit:** `packaging>=24.0` zusätzlich direkt in `pyproject.toml` unter `[build-system].requires` benennen, weil `setup.py` die Identitätslogik im isolierten Build importiert. Keine Änderung von Produkt- oder Runtime-Abhängigkeiten.
3. **Manuelle Builds verständlich abgrenzen:** Bestehende streng vollständige Herkunftsprüfung für `tools/build_production.py` und offizielle RCs nicht lockern. Die aktuelle Buildreferenz erklärt explizit den manuellen/development Buildweg und warum ein unqualifiziertes/dirty Produktions-Dockerimage nicht unter dem offiziellen Produktschema erzeugt werden darf. Keine neue heimliche Bypassoption.

## Umsetzung

- Manifestdatei als unveränderte Microsoft-Manifestbytes speichern, Git-Zeilenendentransformation verhindern; im Source-/sdist-/Wheelpaket als Datendatei einschließen.
- Den vorhandenen Windows-Toolchain-Authorityeintrag von externer Channel-URL auf gebündelten Dateipfad umstellen; unveränderte Größe und SHA bleiben bindend.
- Beim Windows-Kroko-Build Originalbytes vor dem Dockeraufruf prüfen und nur bei korrektem Digest in den externen Upstream-Buildkontext kopieren. Die gepinnte Dockerfile-Patchlogik verwendet die kopierte Datei und überprüft nochmals Größe/Hash vor xwin. Keine Netzwerkquelle für dieses Manifest.
- Windows-Build- und Patchrevisionskonstanten gemäß bestehenden Fingerprintguards aktualisieren; erwartete neue Fingerprints nur algorithmisch bestimmen, niemals alte IDs umdeuten. Linux-Authority darf nicht mitwandern.
- Regressionen: fehlende/veränderte Datei fail-closed; Manifest im Wheel/sdist; Dockerfile verwendet lokale Quelle; Fingerprint und Guard-Digests; kein Netzwerkfallback; normale CI.

## Freigabekriterien

**Dieser Patch erzeugt eine neue Source-/Windows-Buildauthority.** Der bisherige vollständig grüne RC auf `d99633a...` belegt nur den alten Stand. Vor Merge müssen die volle CI auf dem neuen PR-HEAD und der vollständige RC für den neuen Produktcommit (vier echte Wheels, beide Images, vollständige Assembly) erfolgreich sein. Auf die bis dahin bereits qualifizierten alten Artefakte darf nicht rückwirkend umetikettiert werden.

Die eigentliche Merge-/Release-/Deploymententscheidung bleibt gesondert: kein Release, kein VPS-Zugriff, kein automatisches Publizieren; materielle Abweichungen und tatsächliche neue Prüfnachweise werden nach Umsetzung in einer neuen datierten Soll-/Ist- und Abweichungsakte dokumentiert.
