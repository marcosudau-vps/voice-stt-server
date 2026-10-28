# PR #15 – Abschlussnachtrag zur Korrekturakte (26.10.2026)

Datierte Ergänzung zur Akte `01`–`08` (25.10.2026). Die älteren Dateien bleiben
als historischer Stand unverändert; insbesondere ist die Aussage in
`08_ABSCHLUSSBERICHT.md`, alle H-Befunde seien geschlossen, durch die
[revidierte Abnahmegrundlage](https://github.com/marcosudau-vps/voice-stt-server/pull/15#issuecomment-6408087404)
und diesen Nachtrag **überholt**. Ebenso gilt die Vorgabe zweier gleichzeitiger
Pro-Lanes (P1-04 alt) nicht mehr: maßgeblich ist die Betriebsgrenze „eine native
Kroko-Modellidentität pro Prozess“.

Planung, Soll/Ist und Abweichungen:
[Plan](2026-10-26_PLAN_ABSCHLUSSKORREKTUR.md) ·
[Umsetzungsvergleich](2026-10-26_UMSETZUNGSVERGLEICH.md) ·
[Abweichungen](2026-10-26_ABWEICHUNGEN.md).

## Ergebnis

Alle sechs Befunde der revidierten Bewertung (P0-01, P0-02, P1-03 bis P1-06) und
der zusätzliche Schutzfall „Key-Rotation bei initialisiertem Pro-Singleton“ sind
im bestehenden Architekturrahmen umgesetzt, deterministisch getestet und – wo die
Testumgebung es erlaubt – mit der echten Kroko-ONNX-1.12.9-Pro-Runtime belegt.
Der PR bleibt Draft; die Agentenmeldung `REVIEW_READY` ist an grüne CI auf dem
finalen Commit gebunden (SHA und CI-Läufe: PR-Beschreibung und
Abschlusskommentar).

## Welche Wechsel funktionieren, welche nur nach Neustart, was gesperrt bleibt

| Vorgang | Ergebnis | Nachweis |
| --- | --- | --- |
| Community ohne Key, Pro-Runtime | funktioniert | N1 real |
| Community → Pro (Key gültig) | funktioniert live **im Leerlauf**; bei aktiver Arbeit zurückgestellt | N4 real; Zurückstellung deterministisch |
| Pro → Community (Force Community, Key-Entzug, negative Prüfung) | neue Pro-Aufträge sofort gesperrt; Wechsel im Leerlauf live, sonst zurückgestellt; nativer Pro-Kontext bleibt bis Neustart | N4 real; Sperre/Zurückstellung deterministisch |
| Dasselbe Pro-Modell erneut (Unload/Reload, Force aus → an) | funktioniert (Windows) | N4 real |
| Pro A → Pro B | **nur nach Neustart**, vor dem Laden abgewiesen | deterministisch (Guard, Probe, Switch); **nicht** nativ nachgestellt |
| Neuer/rotierter Key bei initialisiertem Pro-Kontext | **nur nach Neustart**, keine Freigabe | deterministisch |
| Pro ohne Key | gesperrt | deterministisch |
| Zwei Kroko-Modelle / zweite Instanz gleichzeitig | gesperrt (Konfiguration und Laden) | deterministisch |
| Free ↔ Pro *Distribution* | nur Paketaustausch + Neustart | Dokumentation |

## Testevidenz (redigiert, 26.10.2026, Windows, CPython 3.12)

Deterministisch:

| Lauf | Ergebnis |
| --- | --- |
| `tests/unit/test_kroko_pr15_final_correction.py` (neu) | 32 passed |
| `tests/unit/test_kroko_license_lifecycle.py` | unverändert grün (24) |
| `python -m pytest -q tests/unit` (JUnit) | 3670 Testfälle inkl. Subtests, 0 Failures, 0 Errors, 24 skipped (20 bisherige + 4 neue Opt-in-Native-Tests), 753 s |
| `compileall`, `git diff --check` | sauber |

Real (Opt-in `VOICESTT_KROKO_NATIVE_TESTS=1`, je Szenario ein frischer
Kindprozess, deutsche Testaudio per lokaler Sprachsynthese, Key nur aus lokaler
Datei zur Laufzeit; die Tests prüfen, dass der Key in keiner Ausgabe vorkommt):

| Szenario | Ergebnis |
| --- | --- |
| N1 Community DE ohne Key (Pro-Runtime, expliziter leerer Key) | geladen; Transkript enthält „Guten Tag … ein kurzer“ (Teile fehlen am Modell, nicht am Server); `nativeProContextActive: false` |
| N2 Pro DE 16 L mit Key | geladen; vollständiger Satz „Guten Tag! Das ist ein kurzer Test der deutschen Spracherkennung. …“ |
| N3 gemeinsame Pro-Instanz, echter `InferenceScheduler`, Lanes Final **und** Realtime | `sharedInstance: true`, beide Lanes mit vollständigem Satz, genau eine native Instanz, keine Fehler |
| N4 Service-Pfad: Community → Pro (`switch_models`) → Force-Patch (Pro → Community) → Force frei (→ dasselbe Pro) | jede Stufe mit realer Transkription; sofortige Abweisung neuer Pro-Aufträge nach dem Patch; `restartRequired: false`; `nativeProContextActive: true` ab der ersten Pro-Stufe; letzte Stufe über `licenseSource: native_context`; stets `liveNativeInstances == 1` |
| `pytest tests/unit/test_kroko_native_integration.py` (alle vier) | 4 passed (100 s) |

Providerexperiment (isoliert, drei kurze Verbindungen, nur Status
ausgegeben): zwei frische Prüfungen ohne nativen Pro `VALID`; Prüfung während und
nach dem Schließen eines nativen Pro-Recognizers im selben Prozess `INVALID
license_rejected`. Folge: Abweichung A1.

Nicht ausgeführt / `NOT_RUN`: Linux-Realtests; Last- und Mehrsitzungsverhalten
der Umschaltung; Anbieter-Connection-Limits als eigener Prüfgegenstand;
Pro-A→B auf nativer Ebene (laut Auftrag ausgeschlossen).

## Verbleibende, ehrlich ausgewiesene Grenzen

* Der native Pro-Reporter wird durch keinen Modellwechsel beendet; Reset des
  Lizenzkontexts, neue Keys und andere Pro-Modelle brauchen eine neue
  Prozessgeneration.
* Die Python-Freigabe ist ein Admission-Nachweis (≤ 60 s) beziehungsweise – für
  dasselbe Modell/denselben Key – die bestätigte native Ladung. Eine spätere
  Lizenzentziehung des Anbieters erkennt nur die native Runtime.
* Ein Modellwechsel unter aktiven Sessions wird zurückgestellt
  (`modelRefreshPending`), nicht erzwungen; die Wiederaufnahme erfolgt über
  `POST /api/models/refresh` nach Sessionende oder beim nächsten Lizenzereignis.
* Linux-Verhalten (Shutdown-Timeout beim erneuten Laden desselben Pro-Modells)
  wurde aus dem externen Bericht übernommen und hier nicht nachgestellt.
