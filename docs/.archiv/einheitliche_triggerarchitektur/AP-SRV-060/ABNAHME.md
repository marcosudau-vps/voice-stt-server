# AP-SRV-060 – Root-Abnahme

**Datum:** offen

**Status:** **PENDING ROOT REVIEW**

Dieses Dokument ist bewusst ein leerer Platzhalter der AP-Akte. Der
Implementierungsagent setzt keine Abnahme. `PASS`, `FAIL` und die
Kanonisierung von AP-SRV-060 gehören ausschließlich Root/Koordination.

## Canonical Base

```text
SHA:
c901cda3f2c19eeb78c468524161728498b6e27e

Tree:
f81144a26f93fb3bc553ab5110d07197a473aa46

Branch:
feat/einheitliche-triggerarchitektur
```

## Execution Provenance

```text
C1:
548057e96a8a722c84d9a43451577a4415bcd7b1
Tree 8751ef47ab17a6c5a1359d75f08fcd18358c5003
Parent c901cda3f2c19eeb78c468524161728498b6e27e
Arbeitsbranch work/AP-SRV-060/C1

C2:
5e429d6227d6a4660b79c432aa934318e293ecfd
Tree ac278c4649e64793bdf938a0a41e484209d882ff
Parent 548057e96a8a722c84d9a43451577a4415bcd7b1
Arbeitsbranch work/AP-SRV-060/C2

C3:
siehe runs/03_ROOT_CORRECTION/2026-08-28_REPORT.md
Parent 5e429d6227d6a4660b79c432aa934318e293ecfd
Arbeitsbranch work/AP-SRV-060/C3
```

## Root-Ergebnis

```text
C1: ROOT FAIL (F1-F10), C2 REQUIRED
C2: ROOT FAIL (F11-F15), C3 REQUIRED
C3: eingereicht, Root Review offen
```

## Offener Abnahmeblocker

```text
WW-18 / WW-19 = EVIDENCE_BLOCKED
Reale positive Wake-Word-Aufnahmen sind im lokalen Umfeld nicht vorhanden.
Die Codefindings F1-F15 sind geschlossen; die algorithmische Detection- und
Boundary-Semantik ist implementiert und getestet. Offen bleibt ausschliesslich
die empirische Kalibrierung (Score-Schwelle, Mindestanzahl Prediction-Frames,
Pre-Roll, Cooldown, Gain, VAD-/Noise-Tuning, False Positives/Negatives); sie
kann ohne dieses Audiomaterial nicht getroffen werden.

Nicht mehr offen ist der operationale Nullpunkt selbst: er ist seit C3 als
Trailing Edge des gewonnenen qualifizierten Wake-Hits definiert.
```

## Offene Deploymentvoraussetzung

```text
Der ausgelieferte Assetbundle enthaelt heute nur .onnx-Artefakte. Die
Dual-Backend-Kette ist implementiert und gegen echte Zweiformat-Bundles
getestet; das Nachliefern der .tflite-Artefakte ist ein Deployment-/
Assetschritt ausserhalb dieses Runs (keine Runtime-Downloads).
```
