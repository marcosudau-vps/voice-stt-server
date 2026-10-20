# Issue #9 – Vor-Merge-Härtung: Abweichungen und Grenzen

## A1 – Neues lokales Buildinput statt vorheriger URL

Die Windows-Toolchain deklarierte vorher eine commitgebundene Community-URL für das historische Microsoft-Channelmanifest. Die neue Quelle ist eine bytegleiche, im Repository und installierten Python-Paket geführte Ressource. Das vermeidet diesen externen Locator, ändert aber bewusst Fingerprint-Inputstruktur, Windows-Patch- und Builderrevision und damit sämtliche Windows-Kroko-Cache-IDs.

**Entscheidung:** Alte IDs werden nicht wiederverwendet. Alte native Windows-Cacheinhalte sind für die neue Authority ungeeignet; echte native Windowsqualifikation muss neu erfolgen. Bytezahl und SHA-256 bleiben identisch und werden sowohl beim lokalen Staging als auch im Container geprüft. Kein Ersatzeingang bei fehlender oder beschädigter Datei.

**Grenze:** Das historische Channelmanifest ist eine Microsoft-Manifestdatei, keine freie Neuschöpfung des VoiceSTT-Projekts. Diese Aufnahme bedeutet keine Neulizenzierung unter VoiceSTT-MIT. Andere Microsoft-/Toolchainartefakte (z.B. das 17-MB-Paketmanifest) bleiben fremd gehostete, geprüfte Inputs. Die neue Ressource verhindert *nur* eine Verfügbarkeitsabhängigkeit für die Channeldatei.

## A2 – Keine Aufweichung der Produktions-Build-Schranke

Das P2-Thema „manuelle Dockerbuilds“ wurde als ausdrücklich dokumentierte Produkt-/Betriebsgrenze gelöst, nicht durch einen neuen Modus mit unvollständiger offizieller Identität: `tools/build_production.py` ist ein Produktionsimagegenerator und bleibt fail-closed auf dirty/unvollständiger Herkunft. Manuelle Python-Builds bleiben möglich; deren Unvollständigkeit ist normal und keine Kandidatenfreigabe. Ein zusätzliches `--ignore-provenance` wäre eine neue Sicherheitsfläche und nicht Teil dieser Härtung.

## A3 – Qualifikation des exakten neuen Commits

Die erste frühere RC-Qualifikation gehört zum unveränderten d99633a. Der neue Implementierungscommit und jede weitere reine Dokumentationsrevision sind andere Gitquellen. Vor der Übernahme eines neuen Kandidaten braucht es vollständige CI und einen eigenen, auf dem endgültigen Commit/Tree basierenden RC. Ein lediglich grüner Packagingtest ist kein echter Windows-Docker-Crossbuildbeleg.

**Stand beim Schreiben:** Neue CI läuft; neuer RC noch nicht ausgeführt. Merge, Release und Deployment bleiben gesperrt, bis die notwendigen tatsächlich erfolgreichen Nachweise vorliegen.

## A4 – Nachträgliche CI-Regressionen und Ressourcentrennung

Die erste CI der Manifest-Vendoring-Änderung (`ff5924f…`, Run #39373447927) war auf beiden Plattformen rot (je 5 Tests): alte Downloadparameter-Annahme, alte Windows-Builderrevision, zwei ältere Golden-Fingerprints im RC-Test sowie die zuvor exklusive Kroko-Modellmetadaten-Assetliste. Das waren Versäumnisse bei der ersten Implementierung des kleinen Nachtrags; kein neuer Nachweis eines Produkt- oder Nativebuild-Fehlers. Die Channeldatei wurde daher aus `assets/kroko/` nach `assets/build_inputs/windows/` verschoben, um die bestehende Modell-Lizenzgrenze unangetastet zu lassen. Alle an die neue Windows-Authority gebundenen Golden-Werte wurden folgerichtig neu abgeleitet; der historische Baseline-Test bleibt erhalten. Der korrigierte Stand benötigt erneut erfolgreiche CI und einen echten vollständigen RC, bevor ein Merge zulässig ist.
