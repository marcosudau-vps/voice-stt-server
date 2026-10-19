# PR #8 / P1: deterministischer ROT-Nachweis vor der Korrektur

Stand: 2026-10-19. Produktcode unveraendert auf
`3475f1d43dab945443e8c38d8c877a25d32528d8`.

```powershell
python -m pytest -q tests\unit\test_wakeword_session_e2e.py::WakeEventTests::test_clear_serializes_pending_hit_admission_until_detector_invalidation
```

Tatsaechliches Ergebnis: **1 FAIL in 8.70 s**, Exitcode 1.
Fehler: `AcceptedWakeDetection(...) is not None` an der Assertion, die den
alten Hit nach der Cleargrenze als wirkungslos verlangt.

Der echte Evaluator hatte vor Clear einen Hey-Jarvis-Hit mit Score `0.91`
und Detektorgeneration 0 berechnet. Der Clear-Thread wurde direkt vor
`_reset_wake_detector()` angehalten: Sessiongeneration war bereits erhoeht,
Activationphase IDLE und Sessionlock freigegeben, Detektorgeneration noch 0.
Der Admission-Thread konnte das reale Coordinator-RLock nichtblockierend
erwerben und eine neue Activation committen. Sein Ergebnis war eine
`AcceptedWakeDetection` mit alter Generation 0 und neu vergebener
Activation-ID. Erst danach durfte Clear den Modellreset fortsetzen.

Der Lockprobe-Wrapper delegiert ausschliesslich an das vorhandene RLock,
einschliesslich Reentranz; er ersetzt weder Admission noch Activation.
Events erzwingen das Interleaving ohne Sleeps oder zufaellige Zeitfenster.
Alle Threads wurden freigegeben und beendet; keine Hintergrundexception
wurde als fachliche Ablehnung gewertet.

Das ist ein echter falscher Commit auf dem geprueften Ausgangsstand, nicht
nur ein fehlender Resetaufruf oder eine hypothetische Synchronisationsluecke.
Rohoutput liegt ausschliesslich im externen Sessionartefakt
`p1-clear-red.txt`. GRUEN und Gesamtpruefung folgen in einer getrennten
datierten Gegenpruefung; dieser historische Nachweis bleibt unveraendert.
