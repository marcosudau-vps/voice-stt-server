# V1 Preservation Packaging Correction 1 – Gesamtplanung

## Ausgangslage

Der erhaltene erste Clean-Release-Prep-Snapshot veröffentlichte nur ein
plattformunabhängiges VoiceSTT-Wheel, einen sdist und eine separat zu
installierende Kroko-Runtime. Das widerspricht dem extern festgelegten
V1.0.0-Produktvertrag. Der Korrekturbranch basiert unverändert auf
`7b8d940133e8f566fb28742f4fc9fde5cc4eccaa`.

## Ziele und Entscheidungen

- Zwei alternative Distributionen: `voice-stt-server` (Free) und
  `voice-stt-server-pro` (Pro).
- Je ein natives CPython-3.12-Wheel für Linux x86_64 und Windows AMD64.
- Direkte Einbettung der passenden Kroko-Runtime einschließlich nativer
  Bibliotheken und Lizenzhinweisen; keine Modelle, kein nested Wheel und kein
  zweites Kroko-dist-info.
- Gebackene Free-/Pro-Identität ohne Ableitung aus `KROKO_API_KEY`.
- Fail-closed Modellregeln, kein öffentlicher V1-sdist und resumefähiger
  zweiphasiger PyPI-Erst-Release mit vier Artefaktzuständen.
- Docker konsumiert das bereits qualifizierte Linux-Produktwheel.
- Reale Linux-/Windows-Clean-Installs, Docker-Smokes und ein vollständiges
  Evidence Pack.

## Nicht-Ziele

Keine V2-, API-, Protokoll-, Logging-, Wakeword-, allgemeine Trigger-,
`build/vps/**`- oder Produktionsänderung. Keine Candidate-/Publish-Ausführung
und keine öffentliche Veröffentlichung.

## Risiken und Absicherung

- Windows-Cross-Build: gepinnter Upstream und echte Installation auf
  `windows-latest`.
- Free/Pro-Verwechslung: gebackener Marker, Environment-freie Clean-Installs
  und Matrixinventar.
- Secret-/Modell-Leak: Byte- und Docker-COPY-Input-Prüfung.
- PyPI-Erstbootstrap: sieben ungefährliche State-Simulationen, kein Upload.
- VPS-Konflikte: isolierter Workspace, eigene Container-/Portnamen, bestehende
  Produktion bleibt unangetastet.

## Umsetzung und Abnahme

Der externe Release-Auftrag ist der detaillierte Scope Lock. Die Abnahme
erfordert vier reale Produktwheels, Tests der gesamten relevanten Codebasis,
Windows- und Linux-Operator-Smokes mit echtem Modell/Pro-Credential, zwei
isolierte Client-Endpunkte, grüne CI am exakten HEAD und alle Pflichtdateien
des Evidence Packs.
