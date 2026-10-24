# AP-KR-020 – Test- und Evidenzbericht

22.10.2026. Gesamtstatus **BLOCKED** am Lizenzvalidierungsvertrag; kein echter
Pro-Lizenznachweis. Dieser Bericht beschreibt neue AP-020-Ausführungen.
Historische AP-010-Ergebnisse werden nicht als neue Qualifikation gezählt.

## Umgebung und Abgrenzung

Windows 11 AMD64, CPython 3.12.10, pytest 9.1.1. Unit-/gezielte Tests mit
`C:/Users/marco/AppData/Local/Programs/Python/Python312/python.exe` aus dem
aktuellen Sourcecheckout. Packaging-/Kompatibilitätssuite mit der vorhandenen
externen Testvenv
`C:/Users/marco/AppData/Local/Temp/ap-kr-010-20261022/test-venv/Scripts/python.exe`.
`pip check` besteht in beiden Umgebungen. Keine neue Abhängigkeitsinstallation.

Tests nutzen weiterhin ihre bestehenden opt-in-/Plattformgrenzen. Keine
pauschalen Skips oder abgeschwächten Assertions hinzugefügt. Kein
Realmodell-/Audiohardware-/VPS-/Docker-/Lizenzserverexperiment vorgenommen.

Der vollständige finale Testcode ist in Implementierungscommit `c842ccd`
gebunden. Spätere Dokumentationscommits ändern diesen Code nicht.

## Realtime-Regression: Ursache und ROT/GRÜN

Betroffen:
`tests/unit/test_realtime_streaming_transcription.py::RealtimeWorkerOverlapRaceTests::test_blocked_r1_inference_released_after_r2_start`.

1. **Originalfassung lokal falsch grün:** gezielter Lauf `1 passed in 6.79s`.
   Das Modell-Double besitzt kein `assertTrue`. Der echte Worker fängt dessen
   `AttributeError` in `VoiceSTT/core/realtime.py` ab und kann danach R2
   veröffentlichen. Das Ausbleiben von R1 war damit kein Nachweis seiner
   erfolgreichen Inferenz und anschließenden Stale-Verwerfung.
2. **ROT:** Zuerst nur einen `r1_returned`-Nachweis nach Konstruktion des
   R1-Ergebnisses ergänzt und im Testthread nach Workerende geprüft.
   Ohne Behebung des falschen Methodenzugriffs scheitert derselbe Lauf
   deterministisch: `1 failed in 6.42s`,
   `R1 must return after release so stale-result rejection is exercised`.
   Das aufgezeichnete Worker-Warning benennt den `AttributeError`.
3. **Erster Fix:** `test_case = self` hält die wirkliche unittest-Instanz;
   `test_case.assertTrue(release.wait(timeout=15.0), ...)` erhält die ursprüngliche
   Timeoutassertion. Der neue R1-Nachweis verhindert weiterhin falsches Grün,
   falls der Worker eine Assertion oder einen Modellfehler abfangen sollte.
4. **Zusätzliche Race reproduziert:** Die Datei besteht zunächst mit 3 Tests,
   aber 25 Wiederholungen im selben Prozess zeigen 4 Fehler `2 != 1`.
   Zwischen der ersten R2-Vorschau und dem Stoppen im pollenden Testthread
   kann ein zweiter Timerdurchlauf die Sequenz erhöhen. Die bestehende
   Assertion `sequence == 1` wird nicht gelockert.
5. **Endgültige Synchronisation:** Der synchrone Testcallback stoppt
   `is_running` direkt auf dem Workerthread nach der ersten R2-Vorschau und
   signalisiert `r2_published`. Der Test wartet auf dieses Event statt zu
   pollen. R1-Start → R2-Kontext/Reset/Frames → R1-Freigabe → echte R1-Rückkehr
   → R2-Publikation → bestätigtes Threadende sind damit geordnet.
6. **GRÜN:** Finale Testdatei: `3 passed in 8.03s`. Zusätzlich 100 frisch
   instanziierte Wiederholungen desselben unittest-Falls im selben Prozess:
   `Ran 100 tests in 2.218s`, `OK`, ohne Skips.
7. **Produktvertrags-Mutation erkannt:** In einem separaten Pythonprozess
   ausschließlich im Speicher die Identitätsprüfung nach Modellinferenz aus
   `run_realtime_worker` entfernt. Der unveränderte finale Test erkennt diese
   Regression durch exakt einen Fehler `2 != 1`; keine sonstigen Testfehler.
   Keine Produktdatei auf Disk verändert. Der absichtlich negative Mutantenlauf
   ist keine Produktregression und kein echter Native-/Lizenztest.

Alle bestehenden R1-Stale-/R2-Recording-/Stabilizer-/Sequenzassertions bleiben
erhalten. Der echte Worker und Stabilizer laufen gegen ein blockierendes
synthetisches Modell, nicht gegen eine native Kroko-Runtime.

Reproduktion des Wiederholungslaufs:

```python
import unittest
name = ('tests.unit.test_realtime_streaming_transcription.'
        'RealtimeWorkerOverlapRaceTests.'
        'test_blocked_r1_inference_released_after_r2_start')
suite = unittest.TestSuite(
    unittest.defaultTestLoader.loadTestsFromName(name) for _ in range(100)
)
result = unittest.TextTestRunner(verbosity=1).run(suite)
raise SystemExit(not result.wasSuccessful())
```

## Breite Regressionen

Die vollständige finale Unit-/Guard-/Contractsuite und die vorhandene
Packaging-/Kompatibilitätssuite sind abgeschlossen.

Der erste breite Unitlauf wurde nach der zusätzlichen Synchronisationskorrektur
kontrolliert unterbrochen: sein Pythonprozess hatte noch die vorherige
Testfassung geladen. Dieser Teillauf zählt nicht als bestandene Suite. Ein
vollständig neuer Unitlauf prüft nun den finalen Code aus `c842ccd`.

| Prüfung | Tatsächliches neues Ergebnis |
| --- | --- |
| `python -m pytest -q tests/unit --disable-warnings --tb=short` | **2147 passed, 15 skipped, 10 warnings, 1326 subtests passed**, 896,92 s. Vollständiger finaler Lauf nach der Synchronisationskorrektur. |
| `<externe-testvenv>/python -m pytest -q tests/packaging tests/compatibility --disable-warnings --tb=short` | **43 passed, 1 skipped**, 1532,11 s. Alle vorhandenen Packagingfälle; der opt-in-Client-Paartest ohne expliziten Checkout/Commit bleibt übersprungen. |
| `python -m pip check`, beide Testumgebungen | **No broken requirements found**, jeweils Exit 0. |

In Summe **2190 passed, 16 skipped, 1326 subtests passed**. Die gezielten
ROT-/GRÜN-/Wiederholungs-/Mutantenläufe sind zusätzlich separat berichtet
und werden nicht als weitere eindeutige Suitefälle addiert. Die 15 Unit-Skips
sind weiterhin nicht ausgeführte optionale Integrations-/Plattformfälle.
Eine neue GitHub-CI oder ein offizieller RC ist mit diesen lokalen Resultaten
nicht behauptet. Der Draft-PR stößt die gewöhnliche CI an; kein RC/Release.

```text
python -m pytest -q tests/unit --disable-warnings --tb=short
<externe-testvenv>/python -m pytest -q tests/packaging tests/compatibility --disable-warnings --tb=short
```

Packagingtests bauen echte Pakete und installieren diese in frischen
Consumerumgebungen mit `--no-deps`. Ihre nativen Dateien sind synthetische
Fixtures. Das ist keine native Kroko-/Full-Dependency-/Lizenzqualifikation.
Ein unveränderter Client-Paartest benötigt seinen expliziten Checkout/Commit;
fehlende opt-in-Eingänge werden ehrlich als Skip ausgewiesen.

## Dokumentations- und Änderungsgrenzen

- 86 lokale Markdown-Linkziele in geänderten/neuen Dokumenten auflösbar.
- Geänderte Testdatei mit `ast.parse` geprüft; `git diff --check` fehlerfrei.
- Diff gegen `acdffc7` enthält ausschließlich Dokumentation und den beauftragten
  Race-Test. Keine Produktquellen, Buildinputs oder Workflows verändert.
- AP-010-Archiv bytegleich zum Integrationsstand (`git diff` leer).

## Lizenz- und Implementierungsevidenz

| Ebene | Ergebnis / Grenze |
| --- | --- |
| Aktuelle AP-010-Abnahme und Integrationsbasis | VERIFIZIERT über PR-Kommentar, GitHub-Metadaten, Fetch und Remote-Ref `acdffc7`. |
| Unterstützte Lizenzschnittstelle / native Ergänzung / Prüfprozess | CODEANALYSE in vorgeschriebener Reihenfolge, Quellencommit und vier SHA-256 im Schnittstellenbericht. Keine implementierte neue API. |
| Positive, negative, abgelaufene, widerrufene oder modellunberechtigte echte Lizenzfälle | NOT_RUN; keine autorisierte Testumgebung. |
| Lizenztimeout/Offline, Besitzerprozesswechsel, Community-Fallback, Key-/Forcewechsel, späte Generationen, reale Sessions/Reconnect der neuen Runtimeintegration | NOT_RUN; A–G-Integration nicht implementiert. Bestehende synthetische Suitefälle beweisen diese neue Integration nicht. |
| Simulierte gültige Pro-Lizenz in neuer AP-020-Implementierung | Keine solche Implementierung oder Simulation hinzugefügt. |
| Modellmanifest, Download-/SHA-/Quellen-/Provisionierungsgrenzen | Unverändert. Keine neue Modellberechtigung aus Dateipräsenz abgeleitet. |
| Neue öffentliche HTTP-/V2-/Settingsfelder | Keine; Force-Community und Lizenzstatusprojektion nicht implementiert. |

Quellenprüfung und technische Entscheidung im
[Schnittstellen-/Lifecyclebericht](2026-10-22_SCHNITTSTELLEN_LIFECYCLE.md).
Fehlende echte Lizenztests allein würden CONDITIONAL bedeuten. Der Gesamtstatus
ist hier BLOCKED, weil zusätzlich kein belastbarer Lizenzvertrag implementiert
werden konnte.
