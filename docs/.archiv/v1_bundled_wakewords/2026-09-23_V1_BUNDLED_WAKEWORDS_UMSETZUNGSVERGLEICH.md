# Soll-/Ist-Vergleich: gebündelte Wakewords für V1

Datum: 2026-09-23

## Ergebnis

Die Umsetzung entspricht dem Plan:

- fünf ONNX-Klassifikatoren (`hey_jarvis`, `alexa`, `hey_mycroft`,
  `hey_rhasspy`, `computer`) wurden aus dem geprüften V2-Bestand übernommen;
- Feature-Pipeline, Manifest, SHA-256-Werte und Attribution werden mit Paket
  und Image ausgeliefert;
- externe Verzeichnisse und Manifeste ergänzen den eingebauten Katalog;
- externe Modelle überschreiben bei gleicher logischer ID das eingebaute
  Modell;
- der generische Default benötigt keinen externen Modellpfad mehr;
- die VPS-Produktionskonfiguration wurde nicht verändert.

Es gab keine materielle Abweichung vom Plan; eine Abweichungsdatei ist daher
nicht erforderlich.

## Nachweis

- `tests/unit/test_wakeword.py`: Katalog, externe Overrides, Pipeline und
  Hashprüfung;
- `tests/test_v1_release_workflows.py`: bestehende Release-Sicherungen;
- Paketinhalt wird zusätzlich durch einen lokalen Wheel-Build geprüft.

## Plattformabnahme

- Windows: 380 Servertests, 13 erwartete Skips und 78 Subtests; Wheel-Inhalt
  geprüft; echtes `hey_jarvis` mit OpenWakeWord/ONNX Runtime geladen;
  isolierter Kroko-Pro-Dockerstack gesund; WebSocket `hello` und `ready` mit
  allen fünf Wakeword-IDs.
- Linux/VPS: gezielte 20 Wakeword-/Release-Workflowtests; Linux-Wheel gebaut
  und auf sieben ONNX-Dateien plus Manifest/Attribution geprüft; isolierter
  Kroko-Free-Dockerstack gesund; echtes `hey_jarvis` geladen; WebSocket-Smoke
  über einen lokalen SSH-Tunnel erfolgreich.
- Die laufende VPS-Produktion blieb unverändert und gesund. LiteLLM, Redis und
  Control Plane wurden nach der Aktion mit HTTP 200 geprüft.
