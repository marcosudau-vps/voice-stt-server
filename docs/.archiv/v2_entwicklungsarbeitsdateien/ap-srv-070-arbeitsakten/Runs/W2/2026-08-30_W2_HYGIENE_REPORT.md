# AP-SRV-070 — W2 HYGIENE REPORT

**Datum:** 2026-08-30
**Teilblock:** W2 — Repository Hygiene (§ W2-05 des Prompts)

---

## 1. Vorgehen

Für jeden der sechs im Prompt genannten Löschkandidaten wurde vor der
Löschung eine repo-weite Referenzsuche (Quellcode, aktive Doku, `.bat`/`.ps1`,
README-Dateien) außerhalb von `docs/.archiv/` durchgeführt. Ein Kandidat
wurde nur gelöscht, wenn die Suche **keine** aktive Referenz ergab. Ein
Kandidat mit gefundener aktiver Referenz wurde **bewusst behalten**, auch wenn
die W0-Scope-Matrix (S21/S22) ihn ursprünglich pauschal als
`CONFIRMED_REMOVE` klassifiziert hatte — das Prompt selbst verlangt genau
diese Prüfung vor Löschung und definiert „ein Löschkandidat wird noch aktiv
referenziert" als Stop-Gate-Bedingung; hier als gezielte Ausnahme für die
eine betroffene Datei behandelt, nicht als Abbruch des gesamten W2-Laufs.

## 2. Ergebnis je Kandidat

| Kandidat | Ergebnis | Referenzbefund |
|---|---|---|
| `tests/suh_mahn_thuh.onnx` | **entfernt** | Nur erwähnt in `tests/openwakeword_test.py` (Demoskript) und `tests/README.md`. `tests/README.md` instruiert jedoch explizit, das Demoskript und beide Modelldateien frisch in einen **neuen, separaten** Ordner (`mkdir samantha_wake_word`) außerhalb dieses Checkouts herunterzuladen — die im Repository committeten Binärdateien werden vom dokumentierten Workflow nicht genutzt. Obsoleszenz damit belegt. |
| `tests/suh_man_tuh.onnx` | **entfernt** | Wie oben. |
| `tests/samanta.tflite` | **entfernt** | Keine einzige Codereferenz per Namen gefunden; nur eine generische Erwähnung „used by demos" in `docs/test-scripts.md`. Wird von keinem Skript geladen. |
| `app_browserclient/start_server.bat` | **entfernt** | Repo-weit unreferenziert; trivialer Wrapper (`python server.py`), redundant mit direktem Aufruf. `docs/windows-cpu-deployment.md` referenziert `app_browserclient/server.py` direkt, nicht den `.bat`-Wrapper. |
| `app_talk_with_llm/start.bat` | **entfernt** | Repo-weit unreferenziert. Nutzt zudem eine veraltete, abweichende venv-Struktur (`test_env` statt der dokumentierten `.venv`) und ist durch den in `app_talk_with_llm/README.MD` dokumentierten Startweg (`.venv\Scripts\python.exe .\app_talk_with_llm\ui_openai_voice_interface.py`) ersetzt. |
| `app_talk_with_llm/install_cpu.bat` | **bewusst behalten** | **Aktiv referenziert** in `app_talk_with_llm/README.MD` Zeile 14: „The compatibility wrapper `app_talk_with_llm\install_cpu.bat` invokes the same installer and does not create a second virtual environment." Explizit als beabsichtigter Kompatibilitäts-Wrapper dokumentiert, keine tote Datei. Löschung hätte einen aktiven Doku-Verweis gebrochen. |

Nach jeder Löschung wurde erneut repo-weit nach dem jeweiligen Dateinamen
gesucht (inklusive Backslash- und Forward-Slash-Schreibweise); keine
verbleibenden Referenzen gefunden.

## 3. Folgeanpassung

`docs/test-scripts.md` enthielt eine Tabellenzeile pro gelöschter
`.onnx`/`.tflite`-Datei sowie eine Erwähnung im `openwakeword_test.py`-Eintrag.
Beide wurden angepasst, damit die Tabelle keine Datei mehr nennt, die im
Repository nicht mehr existiert; der Verweis auf den externen
Download-Workflow in `tests/README.md` bleibt erhalten und wurde inhaltlich
nicht verändert (beschreibt bereits korrekt den externen, nicht
repo-gebundenen Ablauf).

## 4. Keine produktiven Wake-Word-Bundle-Assets betroffen

Keine der Löschungen betrifft `VoiceSTT/assets/wakeword_models/**`. Das
kanonische Wake-Word-Bundle blieb vollständig unangetastet.

## 5. Nicht in W2-05 behandelt

Docker-/Compose-Referenzen auf `VOICESTT_OPENWAKEWORD_MODEL_ROOT` in
`Dockerfile`, `docker-compose.yml` und `build/vps/docker-compose.yml` wurden
geprüft (Treffer vorhanden), aber gemäß Prompt-Abschnitt „Nicht in W2 lösen"
ausdrücklich unangetastet gelassen — das gehört laut Auftrag zum
W4-Deployment-Cut.
