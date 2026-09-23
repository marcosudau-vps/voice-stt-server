# V1 Preservation Packaging Correction 1 – Abweichungen

## Nachgetragene Archivregistrierung

- Grund: Die Korrektur wurde zunächst in einer externen GitHub-fähigen
  Chat-Session begonnen. Bei der lokalen Fortsetzung existierten der
  Korrekturbranch und mehrere gepushte Commits bereits.
- Auswirkung: Diese repository-interne Archivplanung wurde nicht vor dem
  allerersten Korrekturcommit angelegt.
- Entscheidung: Der unveränderte externe Scope Lock bleibt die ursprüngliche
  Planung; dieses Archiv dokumentiert die Fortsetzung, Prüfung und tatsächliche
  Abnahme transparent nach.
- Status: Akzeptierte Prozessabweichung; der Soll-/Ist-Vergleich wird erst nach
  den realen Builds, CI und Operator-Smokes abgeschlossen.

## Historischer Candidate-Workflow-Datensatz

- Grund: GitHub registrierte für eine zwischenzeitlich ungültige
  `release-candidate.yml` automatisch den parse-only Push-Run `34703916749`.
- Auswirkung: Ein Run-Datensatz existiert, obwohl der Candidate nie manuell
  gestartet wurde; der Run hatte keine Jobs und keine Publikationswirkung.
- Entscheidung: Nicht löschen oder umdeuten, sondern im No-Publication-Guard
  und Risk Register ausdrücklich offenlegen.
- Status: Historische Evidenz; manuelle Candidate- und Publish-Dispatches
  bleiben bis zur späteren Autorisierung gesperrt.

## Quellcheckout überschattete den Pro-Wheel-Marker

- Grund: Der erste Linux-Clean-Install-Smoke wurde aus dem Repository-Root
  ausgeführt. Python importierte dadurch den absichtlich auf Free gesetzten
  Entwicklungsmarker statt des frisch installierten Pro-Wheels.
- Auswirkung: Beide Linux-Smokes des Runs `34714943188` schlugen fehl, obwohl
  Wheel-Inventar und Windows-Clean-Installs erfolgreich waren.
- Entscheidung: Sämtliche Linux- und Windows-Clean-Install-Importe laufen aus
  einem temporären Verzeichnis außerhalb des Checkouts und protokollieren den
  tatsächlichen Paketpfad. Der lokale Acceptance-Runner verwendet dieselbe
  Trennung.
- Status: Behoben und lokal sowie auf dem VPS gegen Free/Pro reproduziert; die
  abschließende CI-Gegenprüfung bleibt Bestandteil des Release-Gates.

## Neuere Runner-GLIBC war nicht Bookworm-kompatibel

- Grund: Der erste Linux-Kroko-Build lief nativ auf Ubuntu 24.04. Sein
  `linux_x86_64`-Wheel verlangte GLIBC 2.38, während das gepinnte
  Debian-Bookworm-Laufzeitimage GLIBC 2.36 bereitstellt.
- Auswirkung: Der isolierte VPS-Docker-Preflight konnte `kroko_onnx` nicht
  importieren und stoppte vor Containerstart; Produktion war nicht betroffen.
- Entscheidung: Der Linux-Release-Build läuft in einem source-controlled
  Bookworm-Builder mit exakt demselben gepinnten Basisimage-Digest wie das
  Runtime-Dockerfile. Textbasierte Fingerprint-Eingaben werden unabhängig von
  CRLF/LF kanonisch gehasht.
- Status: Implementiert; realer Bookworm-Import, finale CI-Docker-Smokes und
  Operator-Abnahmen werden vor Abschluss dokumentiert.

## Bewegliche Slproweb-Dateinamen brachen den manuellen Windows-Build

- Grund: Der allgemeine `stt-install-kroko`-Pfad ersetzte die historische
  OpenSSL-Quelle durch eine Liste vermeintlich aktueller Slproweb-EXE-Namen.
  Am 20. September 2026 lieferte keiner dieser Namen noch eine Datei.
- Auswirkung: Der lokale Pro-Build brach in `Dockerfile.windows` bei
  `test -s openssl.exe` ab, bevor Kroko kompiliert wurde. Der gepinnte
  Release-Builder war nicht betroffen.
- Entscheidung: Auch der allgemeine Installer verwendet jetzt das bereits im
  Release-Build qualifizierte, versionierte `openssl-native 3.5.5`-NuGet-Paket
  und prüft Header, Importbibliotheken und Laufzeit-DLLs explizit.
- Status: Behoben; der vollständige Pro-Build erzeugte auf dem Windows-PC ein
  Wheel und einen NSIS-Installer, CMake erkannte OpenSSL 3.5.5 und das Wheel
  ließ sich in einer frischen CPython-3.12-Umgebung installieren/importieren.

## Silero-Auflösung ersetzte CPU-Torch im finalen Image

- Grund: Der Docker-Build installierte zunächst das jeweils neueste CPU-Torch,
  während `silero-vad 6.2.x` für sein ONNX-Extra `torchaudio < 2.10` verlangt.
  Beim anschließenden Extras-Install ersetzte pip das neuere CPU-Paar deshalb
  durch das CUDA-fähige PyPI-Paar 2.9.1 samt `nvidia-*` und `triton`.
- Auswirkung: Alle nativen Builds, Produkt-Wheels und Clean-Installs des Runs
  `35534641862` bestanden, beide finalen Docker-Jobs stoppten jedoch korrekt am
  CPU-only-Guard (`torch.version.cuda == 12.8`).
- Entscheidung: Das finale V1-Image pinnt das zusammenpassende CPU-Paar
  `torch==2.9.1+cpu` / `torchaudio==2.9.1+cpu` aus dem offiziellen CPU-Index.
- Status: Lokal mit dem exakten Pro-Linux-Produkt-Wheel aus Run
  `35534641862` bestanden: Image-Build, `pip check`, CPU-/CUDA-Guard,
  Pro-Lizenz-Warmup und eine echte HTTP-Transkription waren erfolgreich. Die
  erneute CI-Abnahme bleibt vor Candidate erforderlich.

## Evidence-Pack kannte den nativen Installerpfad nicht

- Grund: `VoiceSTT/install_kroko.py` wurde für den reproduzierbaren
  Windows-OpenSSL-Bezug geändert, war aber noch nicht in der geschlossenen
  Scope-Zuordnung des Evidence-Packers enthalten.
- Auswirkung: Run `35538173163` bestand sämtliche 14 nativen Build-,
  Produkt-Wheel-, Clean-Install- und Docker-Jobs; ausschließlich das finale
  Zusammenstellen des Beweispakets stoppte mit `unmapped scope path`.
- Entscheidung: Der Installerpfad erhält eine explizite fachliche Zuordnung
  und einen Regressionstest. Binärartefakte oder Laufzeitverhalten ändern sich
  dadurch nicht.

## Lokale vollständige Wake-Word-Abnahme

- Grund: Der erste lokale Pro-Stack hatte keine OpenWakeWord-Assets im
  zentralen Modellordner und deaktivierte Wake Word deshalb vollständig.
- Korrektur: Die gepinnten ONNX-Modelle `hey_jarvis` und `alexa` sowie
  Melspektrogramm- und Embedding-Pipeline aus openWakeWord `v0.5.1` wurden mit
  SHA-256-Provenienz extern unter `MODELS/openwakeword` bereitgestellt und
  read-only in den Teststack eingebunden; sie bleiben aus allen Release-
  Artefakten ausgeschlossen.
- Status: Der reale Desktop-Client erhielt für beide Modelle `hello` und
  `ready: true`; Mikrofon, sessiongebundener Eventstream und Kroko-Pro-Modell
  liefen gleichzeitig im isolierten lokalen Stack.
