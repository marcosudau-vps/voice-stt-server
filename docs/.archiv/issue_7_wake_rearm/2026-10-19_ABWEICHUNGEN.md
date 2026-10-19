# Issue #7: begruendete Abweichungen und Qualifikationsgrenzen

Stand: 2026-10-19. Keine unabhaengige Review- oder Mergefreigabe.

## Arbeitsbranch und Basisausrichtung

Gewuenscht war `fix/issue-7-wake-rearm-reset`. Die vorgeschriebene
App-Branchumbenennung aus dem Sitzungsnamen erzeugt mit ihrem konfigurierten
Praefix `marcosudau-wake-rearm-reset`. Dieser eine Branch wird gepusht;
es gibt keinen zusaetzlichen Aliasbranch und keinen Force-Push.
Das PR-Ziel ist unveraendert
`feat/einheitliche-triggerarchitektur-distributed`, nie `main`.

Der Appworktree begann auf dem aktuellen Main-Stand. Ein erster Rebaseversuch
erkannte Main-exklusive Releasecommits und wurde ohne Konfliktaufloesung
abgebrochen. Danach wurde der noch eigene-Commit-freie Branch exakt auf den
Zielcommit `ada13b011e1d3829f78e7f389e3b927795a2b3be` gesetzt.
Keine Main-Commits und keine fremden Aenderungen sind Teil des PR-Diffs.

## Kein blosses Einzeilenreset

Das Reset ist erst dann ein sicheres Rearm, wenn auch Tracker, Generation,
In-flight-Ergebnisse und absolute Audiopositionen konsistent sind. Deshalb
sind die fuenf in der Planung genannten Produktmodule erforderlich.
Die bestehende Detektorgeneration wird auch bei erfolgreicher Latchfreigabe
weitergezaehlt: ein vor diesem Close berechneter, spaeter angebotener Hit
darf den wieder freien ActivationController nicht erneut oeffnen.

Der v2 Worker liest die autoritative Evaluator-Latch statt eines verspaeteten
Recorderflag-Schreibens. Alte Audiogrenzen werden mit den bereits vorhandenen
Detection-/Generationsdaten verworfen. Das ist Racekorrektheit desselben
Fehlerpfads, keine neue Activation-State-Machine.

Neu ist genau ein Engine-Fehlerflag `resetFailed`: Ohne dieses koennte ein
fehlgeschlagener Reset bei einem Generationenwechsel ohne alte Latch oder bei
direkter Engineauswertung erneut inferieren. Es gibt kein neues Lock, keinen
neuen Timer und keine neue Audio-Zeitbasis. Diagnosezustand ist kein neues
Wirefeld oder strukturiertes Logschema.

## Reproduzierbare Realmodellpruefung ohne urspruenglichen Container

Die vorhandenen lokalen Pythonpakete und unveraenderten gebuendelten
ONNX-Modelle erlaubten einen Replay in einer eigenen Session-venv mit
`--system-site-packages`. Gemeinsame Pakete wurden nicht installiert oder
veraendert. Die historischen Docker-/VPS-Pfade wurden nicht benutzt.

Der datierte portable [Replayhelfer](2026-10-19_ONNX_REPLAY.py) ist zusaetzliche
dauerhafte Evidenz: Er verwendet vorhandene Engine-/WAV-Helfer, prueft die
autorisierten Inputhashes und vergleicht bewusst erhaltene Modellhistorie mit
produktiver Freigabe sowie sofortigem WAV-Neustart. Sechs Messreihen stimmen
mit dem zuvor separat ausgefuehrten lokalen Helfer exakt ueberein.
Er enthaelt keine WAVs, Modelle, erzeugten Logs oder produktiven Pfade.

## Externe offene Qualifikation

- Physische positive/negative Mikrofonprobe, kontrolliertes Schweigen nach
  Timeout und Soundrueckkopplungspruefung: NOT RUN, keine neue Hardwareaufnahme.
- Echte TFLite-Replays aller Katalogmodelle: NOT RUN. Die deterministische
  Rearmregression prueft alle 25 manifestierten kanonischen IDs; reale positive
  Replays wurden fuer die ausgewaehlten ONNX-Modelle Alexa und Hey Jarvis
  ausgefuehrt. Daraus folgt keine akustische Abnahme anderer Modelle.
- Externe Clientintegration/AP-IV2-020 und neue Client-/Serverpaarqualifikation:
  BLOCKED bis zur gesonderten unabhaengigen Freigabe. Kein Client geaendert.
- Ubuntu-/Windows-CI: beim PR-Anlegen extern zu beobachten, keine lokale
  Ubuntuqualifikation behauptet. Hardwareluecken sind keine lokalen PASS.
- Merge, Release, Deployment und Promotion: nicht beauftragt und nicht erfolgt.

## Zwischenlauf der Gesamtsuite

Ein waehrend der letzten Quelltextkorrektur gestarteter Zwischenlauf meldete
1 FAIL, 1978 PASS, 14 SKIP. Ein struktureller `inspect.getsource`-Test traf
auf die inzwischen verschobenen Quellzeilen der bereits geladenen Funktion.
Der unveraenderte Test bestand im frischen Prozess sofort (1 PASS).
Die komplette Suite wurde deshalb auf eingefrorenem finalem Produktquelltext
erneut ausgefuehrt: 1980 PASS, 14 bestehende SKIP und 1296 bestandene
Subtests in 623.05 s, Exitcode 0. Der Zwischenlauf wird weder als bestandene
Suite noch als unabhaengiger Baselinefehler dargestellt. Die Skipgruende
sind im [Soll-/Ist-Vergleich](2026-10-19_UMSETZUNGSVERGLEICH.md) aufgefuehrt;
keiner dieser optionalen Faelle wird als PASS gewertet.
