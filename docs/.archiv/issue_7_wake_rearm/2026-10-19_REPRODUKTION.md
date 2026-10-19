# G1: Reproduktion vor der Produktkorrektur

Stand: 2026-10-19, Produktbasis
`ada13b011e1d3829f78e7f389e3b927795a2b3be`. Noch keine Produktdatei geaendert.

## Deterministisch: FAIL wie erwartet

```powershell
python -m unittest -v tests.unit.test_wakeword_recording_path.WakeRearmRegressionTests
```

Ein Test, eine Assertion fehlgeschlagen: `2 != 1` bei der Zahl akzeptierter
Detections. Der produktive Recording-Worker verarbeitet einen PCM-markierten
Wake-Hit mit echter Engine, Evaluator, Coordinator und ActivationController.
Zehn weitere Chunks werden waehrend der Activation nicht inferiert
(`predict_calls == 2`). Finish und identitaetsgebundenes `input_closed`
schliessen die Eingabe. Nach `release` folgen ausschliesslich Nullsamples.
Die verzogerte Featurehistorie des Fakes erzeugt eine zweite reale Activation
und ein zweites logisches Event. Es ist kein Client-/Anzeigeeffekt.

Der Fake behaelt bewusst mehr als den letzten Score. Ein Trackerreset allein
kann den Fehler daher nicht beheben. Kein Test-Skip und keine Abschwaechung
vorhandener Assertions.

## Betroffene bestehende Suite: PASS

Die elf im Auftrag genannten Module, mit den zehn bestehenden Recordingtests
statt des neuen roten Tests: 338 Tests, 251.020 s, OK, keine Skips.
Aufruf wie im Auftrag, Recordingmodul selektiert als
`Find011Tests` und `LegacyPathTests`.

## Echte ONNX-Modelle: urspruenglicher Fehler bestaetigt

Separate Session-venv mit `--system-site-packages`, keine Installation und
keine Aenderung gemeinsamer Pakete. Windows, Python 3.12.10, NumPy 1.26.4,
OpenWakeWord 0.6.0, ONNX Runtime 1.28.0, CPU. Beide selektierten ONNX-Modelle
aus dem unveraenderten Repositorybundle, Policy-Schwelle 0.5, Seed 0,
40-ms-Chunks. Kein Docker, kein laufender Server und keine Hardwaremutation.

Autorisierte Original-WAVs vom im Issue gepinnten Clientcommit ausschliesslich
im Sessionartefaktverzeichnis, SHA256 verifiziert:

| WAV | SHA256 |
| --- | --- |
| alexa_pause.wav | `abae5a687cee97d120487c2a601509aba41d056b4428966959a1ef1e467b09b3` |
| jarvis_direct.wav | `98e3f96e35cb736b5176c96159cf6e2416d50eb739faa2380320e181caf6d9b2` |

Alexa: erster echter Treffer `0.9997421503067017`; nach produktiver
Latchfreigabe auf reiner digitaler Stille zweiter Treffer
`0.8239456415176392` nach 240 ms. Identisch zur Issue-Evidenz.
Hey Jarvis: erster Treffer `0.9871283769607544`, kein zweiter Treffer bei
fuenf Sekunden digitaler Stille in dieser Aufnahme. Kein Gegenbeweis fuer
andere Modellhistorien.

Der lokale Reprohelfer variiert Produktfreigabe, behaltene Modellhistorie
mit frischem Evaluator als Negativkontrolle und sofortigen WAV-Neustart.
Rohresultate/Logs/WAVs verbleiben ausserhalb des Repositories.
Die Inferenzpause wird emuliert; kein 15-s-Wandzeitlauf und keine neue
menschliche Mikrofonprobe. Der Replay beweist nicht die historische Akustik.
