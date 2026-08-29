# AP-SRV-060 – Tracking-Handoff für Root/Koordination

**Status:** vorbereitet, **nicht** ausgeführt.

**Fortschreibung nach Root FAIL / C2.** C1 wurde von Root mit den Findings
F1–F10 abgelehnt. Die unten korrigierten Stellen betreffen Annahmen, die nach
den Root-Findings falsch waren:

- der v2-Wire nimmt **ausschließlich kanonische IDs**; die tolerante Auflösung
  ist Konfigurationsfeature (F1);
- `next_activation` für die Wake-Settings gilt erst jetzt als umgesetzt, weil
  die reale Runtimebindung erst in C2 existiert und nachgewiesen ist (F2);
- `WW-18`/`WW-19` sind nicht `EVIDENCE_PENDING`, sondern **`EVIDENCE_BLOCKED`**
  – reale positive Aufnahmen existieren im lokalen Umfeld nachweislich nicht.

**Fortschreibung nach Root FAIL / C3.** C2 wurde von Root mit den Findings
F11–F15 abgelehnt. Zusätzlich wurde die Detection-Semantik verbindlich
präzisiert. Für das zentrale Tracking sind daraus vier Punkte neu:

- „1 Wake Word = 1 `wakeword.detected`" ist **Exactly-once Eventing** für eine
  zusammengehörige Wake-Äußerung, nicht „ein Scoreframe ist ein Wake Word".
  Die früheren Formulierungen „keine Mehrfach-Chunk-Regel", „keine 5/10
  Treffer" und „zusätzliche Multi-Chunk-Regel nur nach Evidence" sind
  **zurückgezogen** und dürfen im Tracking nicht als Norm fortgeschrieben
  werden;
- die Wake-Erkennung arbeitet auf zusammenhängenden Trefferbereichen echter
  OpenWakeWord-Prediction-Frames mit `wakeWord.sensitivity` und
  `wakeWord.minConsecutivePredictionFrames`; Arbitration ist
  First-come-first-served (erster finalisierender qualifizierter Hit gewinnt);
- die Wake-Audiogrenze ist **keine Schätzung mehr**: der operationale
  Nullpunkt ist als Trailing Edge des gewonnenen qualifizierten Wake-Hits
  definiert (`boundaryBasis = operational_zero_point`). `WW-19` bleibt offen,
  aber nur noch für die **empirische Kalibrierung**, nicht für den Nullpunkt
  selbst;
- neu im Produktvertrag: Dual Inference Backend mit genau einem gemeinsamen
  Backend je Live-Engine (`wakeWord.inferenceBackend`, betriebssystemabhängige
  Präferenz, gemeinsamer Fallback, kein stiller Wechsel bei expliziter Wahl)
  sowie die Wake-Settings `minConsecutivePredictionFrames`, `detectorGain`,
  `noiseSuppressionEnabled` und `vadThreshold`.

Der Server-AP hat weder Clientproduktcode noch zentrale normative
Koordinationsdateien verändert. Dieses Dokument beschreibt vollständig, was
nach einem Root-PASS in den zentralen Trackingdateien nachgezogen werden muss,
damit der Sachstand nicht verloren geht.

**Wichtig:**

- Die unten genannten Dateien wurden von diesem Lauf **nicht** angefasst.
- AP-SRV-060 ist **nicht** auf PASS gesetzt.
- Es wurde **keine** kanonische Dependency-SHA erfunden. Überall, wo eine SHA
  einzusetzen ist, steht ausdrücklich, dass Root sie einsetzt.

Basispfad aller Dateien:

```text
P:\GithubRepos\marcosudau-vps\voice-stt-client\workspaces\einheitliche-triggerarchitektur\
ARBEITSDATEIEN\
```

---

## 1. `00_STEUERUNG\CURRENT_STATE.md`

**Änderung nach Root-PASS erforderlich:** JA

**Betroffene Abschnitte:** aktueller Arbeitsstand / nächstes Arbeitspaket /
kanonischer Serverstand.

**Konkreter neuer Sachstand:**

- AP-SRV-060 („Wake-Word-Katalog, Detection und Audiogrenze“) ist auf dem
  Server abgeschlossen und kanonisiert;
- der Server besitzt damit einen versionierten, im Build enthaltenen
  Wake-Word-Katalog, eine öffentliche Catalog-API, atomare Sessionadmission,
  selected-only Modellinitialisierung, genau ein `wakeword.detected` je
  akzeptierter Äußerung und eine detection-verankerte Audiogrenze;
- nächstes Serverarbeitspaket ist AP-SRV-070 (Legacyabbau und
  Protokollgrenze);
- clientseitig hängt AP-CLI-020 (Hotkeys/Suppression/Audioverfügbarkeit) und
  AP-CLI-030 (Settings-UI, Wake-Word-Auswahl) an diesem Stand.

**Welche SHA/Testwerte erst Root einsetzen darf:**

- die kanonische AP-SRV-060-SHA und ihr Tree auf
  `feat/einheitliche-triggerarchitektur` (existiert erst mit dem Root-Close);
- die im Root-Review bestätigten Vollsuite-Zahlen.

---

## 2. `10_AKTUELL\EINHEITLICHE_TRIGGERARCHITEKTUR\STATUS.md`

**Änderung nach Root-PASS erforderlich:** JA

**Betroffene Abschnitte:** Arbeitspaketstatus, offene Kalibrierpunkte.

**Konkreter neuer Sachstand:**

- AP-SRV-060 von „offen/in Umsetzung“ auf abgenommen;
- ausdrücklich als weiterhin offen führen: die von realer positiver
  Wake-Word-Sprache abhängige Kalibrierung (`WW-18`, `WW-19` und die Frage
  einer zusätzlichen Mehrfach-Chunk-Regel). Diese Punkte sind **nicht** durch
  AP-SRV-060 erledigt, sondern ausdrücklich als `EVIDENCE_PENDING`
  eingereicht;
- gemessene und damit belastbare Teilaussagen, die übernommen werden können:
  Empfangsfenster der gebündelten Klassifikatoren 1960–3400 ms; über 63.99 s
  reales Negativmaterial kein einziger Rohkandidat oberhalb Schwelle 0.5;
- ausdrücklich **nicht** übernehmen: diese Empfangsfenster sind kein
  kalibrierter Cooldown-/Pre-Roll-Betriebsbereich (Root F5).

**Welche SHA/Testwerte erst Root einsetzen darf:** kanonische AP-SRV-060-SHA;
Root-bestätigte Testzahlen.

---

## 3. `10_AKTUELL\EINHEITLICHE_TRIGGERARCHITEKTUR\VERLAUF.md`

**Änderung nach Root-PASS erforderlich:** JA

**Betroffene Abschnitte:** chronologischer Verlauf.

**Konkreter neuer Sachstand:** ein datierter Eintrag mit

- Einreichung des C1-Runs von AP-SRV-060 auf der kanonischen
  AP-SRV-050-Basis `c901cda3f2c19eeb78c468524161728498b6e27e`;
- Root-Review-Ergebnis (PASS oder C2-Auftrag);
- bei PASS: Kanonisierung als ein Gesamt-Commit;
- Vermerk, dass `openwakeword 0.6.0` in der Serverentwicklungsumgebung
  nachinstalliert werden musste, weil es zwar in `requirements.txt` steht,
  aber nicht installiert war.

**Welche SHA/Testwerte erst Root einsetzen darf:** C1-SHA (aus dem
Handoff-Report), Review-Ergebnis, kanonische Close-SHA.

---

## 4. `10_AKTUELL\EINHEITLICHE_TRIGGERARCHITEKTUR\NACHVERFOLGUNG\AUSFUEHRUNGSSTATUS.md`

**Änderung nach Root-PASS erforderlich:** JA

**Betroffene Abschnitte:** Zeile AP-SRV-060; Freigabezeile AP-SRV-070.

**Konkreter neuer Sachstand:**

- AP-SRV-060: Status abgenommen, Runs = 1 (Implementierung), Review-Branch
  bzw. Distributed-Eintrag laut Root;
- AP-SRV-070 wird durch den Close freigegeben (Dependency SRV-060 erfüllt);
- Hinweis, dass AP-CLI-020/030 den v2-Katalogvertrag
  (`GET /api/v2/wake-words`, kanonische IDs im `hello`) verwenden können.

**Welche SHA/Testwerte erst Root einsetzen darf:** kanonische AP-SRV-060-SHA
und Tree; die Distributed-Referenz des C1-Runs.

---

## 5. `10_AKTUELL\EINHEITLICHE_TRIGGERARCHITEKTUR\NACHVERFOLGUNG\TRACEABILITY.md`

**Änderung nach Root-PASS erforderlich:** JA

**Betroffene IDs und neuer Sachstand:**

| ID | Neuer Status | Begründung |
|---|---|---|
| `WW-01` | umgesetzt (SRV-060) | Build-Katalog, atomare Auswahl, selected-only |
| `WW-02` | umgesetzt (SRV-060) | kanonische IDs, explizite Aliase, ein Resolver. **Präzisierung nach Root F1:** die tolerante Auflösung gilt nur für menschliche Konfiguration; der v2-Wire trägt ausschließlich kanonische IDs |
| `WW-03` | umgesetzt (SRV-050 + SRV-060) | gemeinsame Sensitivity wirkt in der Detection |
| `WW-04` | **teilweise** umgesetzt | Latch und Exactly-once sind umgesetzt; der Bedarf einer zusätzlichen Mehrfach-Chunk-Regel bleibt messdatenabhängig offen |
| `WW-05` | umgesetzt (SRV-060) | Wake Word während Activation ohne Wirkung |
| `WW-08` | umgesetzt (SRV-060) | Wake Word nicht im Nutztranskript, erstes Nutzerwort erhalten |
| `WW-09` | umgesetzt (SRV-060) | `GET /api/v2/wake-words` |
| `WW-10` | umgesetzt (SRV-060) | Normalisierung und Kollisionsregel; ein Alias auf dem Wire wird mit `reason=not_canonical` abgelehnt (Root F1) |
| `WW-11` | umgesetzt (SRV-060) | atomare Admission ohne Teilfallback |
| `WW-12` | umgesetzt (SRV-060) | nur gewählte Modelle initialisiert |
| `WW-13` | umgesetzt (SRV-060) | `wakeword.detected` mit ID, Score, `activationId` |
| `WW-14` | **teilweise** umgesetzt | gemeinsame Sensitivity ja; Zusatzregel weiterhin messdatenabhängig |
| `WW-15` | umgesetzt (SRV-060) | Cooldown/Pre-Roll serverautoritativ und real `next_activation`-wirksam (Root F2); `0 ms` zulässig. Bereich/Default bleiben als `calibration: pending` publiziert |
| `WW-16` | umgesetzt (SRV-060) | Latch bis Eingabeschluss, kein Mehrfachereignis |
| `WW-17` | umgesetzt (SRV-040 + SRV-060) | leere Auswahl nur bei `wakeWord=false` |
| `WW-18` | **EVIDENCE_BLOCKED** | vorläufige Eingabegrenze 0–3400 ms, Default `0`, im Schema als `calibration: pending` ausgewiesen; positiver Wake-Word-Audiobestand existiert nicht |
| `WW-19` | **EVIDENCE_BLOCKED** | vorläufige Eingabegrenze 0–1960 ms, Default `0`; zusätzlich ist die Wake-Endgrenze selbst eine Schätzung (`boundaryMeasured = false`). Grenztest mit realer Sprache fehlt |
| `WIRE-02` | serverseitig umgesetzt | atomare Validierung vor Audio-/Triggerfreigabe |
| `WIRE-04` | serverseitig umgesetzt | `session.rejected` nennt jede problematische ID |
| `SET-13b` | umgesetzt (SRV-060) | öffentlicher versionierter Katalog |

Zusätzlich zu ergänzen: der Erkennungsvertrag kennt jetzt ein zweites
serverseitiges Wake-Event `wakeword.availability_changed` (Katalogebene,
`catalogRevision` + `availableWakeWordIds`). Das ist eine additive
v2-Erweiterung im Rahmen des Frozen Contract (§6.3 führt das Event bereits).

**Welche SHA/Testwerte erst Root einsetzen darf:** die kanonische
AP-SRV-060-SHA als Umsetzungsnachweis je ID.

---

## 6. `10_AKTUELL\EINHEITLICHE_TRIGGERARCHITEKTUR\NACHVERFOLGUNG\FUNDE.md`

**Änderung nach Root-PASS erforderlich:** JA

**Betroffene IDs:** `FIND-011`.

**Konkreter neuer Sachstand:**

- Status von `CONFIRMED / FALSE-POSITIVE POLICY TO MEASURE` auf behoben im
  kanonischen v2-Pfad ändern (Codeanteil; die Policyfrage selbst bleibt offen);
- Ursachenbestätigung: der fehlende Guard in
  `VoiceSTT/core/recording.py` ist geschlossen – die Detection läuft nicht
  weiter, solange ein Treffer gelatcht ist (Nachweis: 40 Chunks mit
  anhaltendem Score ergeben genau einen `predict`-Aufruf und genau eine
  Admission);
- Ergänzung: die zweite Ursache (keine Entprellung über die Dauer einer
  Äußerung) ist durch das aus dem **gemessenen** Empfangsfenster abgeleitete
  Entprellfenster geschlossen. Nach Root F6 ist dieses Fenster ausdrücklich
  vom konfigurierten Cooldown getrennt und endet am sicheren Eingabeschluss,
  damit keine versteckte zweite Vordergrundsperre entsteht;
- offener Restanteil ausdrücklich benennen: die „False-Positive Policy“ ist
  weiterhin messdatenabhängig. Die Negativmessung (63.99 s reale Sprache,
  0 Rohkandidaten ≥ 0.5, Maximalscore 0.000992) ersetzt keine Positivmessung.
  **Nicht** fortschreiben, dass daraus „kein Bedarf für eine Mehrfach-Chunk-
  Regel“ folge: seit C3 ist die Mindestanzahl aufeinanderfolgender
  Prediction-Frames fester Produktbestandteil
  (`wakeWord.minConsecutivePredictionFrames`); offen ist nur ihr kalibrierter
  Wert;
- Vermerk, dass der v1-Pfad die alte Semantik bis AP-SRV-070 behält.

**Welche SHA/Testwerte erst Root einsetzen darf:** kanonische AP-SRV-060-SHA
als Behebungsnachweis.

---

## 7. `10_AKTUELL\EINHEITLICHE_TRIGGERARCHITEKTUR\NACHVERFOLGUNG\WIEDEREINSTIEG.md`

**Änderung nach Root-PASS erforderlich:** JA

**Betroffene Abschnitte:** Wiedereinstiegspunkt, offene Punkte, benötigte
Artefakte.

**Konkreter neuer Sachstand:**

- Wiedereinstieg nach AP-SRV-060 ist AP-SRV-070 auf der neuen kanonischen
  Serverbasis;
- als konkret benötigtes Artefakt aufnehmen: **reale positive
  Wake-Word-Audioaufnahmen** (16 kHz, mono, 16 Bit PCM, gesprochenes Wake Word
  plus unmittelbar folgende Nutzsprache, bekannte akustische Wake-Endgrenze)
  für `WW-18`/`WW-19`. Ohne sie bleiben die kalibrierten Werte für
  Score-Schwelle, Mindestanzahl Prediction-Frames, Pre-Roll, Cooldown und Gain
  sowie das False-Positive-/False-Negative-Verhalten unbeantwortet. Der Status
  ist `EVIDENCE_BLOCKED`, nicht nur `PENDING`: die Suche im lokalen Umfeld ist
  abgeschlossen und negativ (C2-Evidence §8). Die **algorithmische** Semantik
  ist seit C3 nicht mehr Teil dieser Lücke;
- zusätzlich als Deploymentvoraussetzung aufnehmen: die `.tflite`-Artefakte des
  Wake-Word-Bundles. Die Dual-Backend-Kette ist seit C3 implementiert und
  getestet, der ausgelieferte Bundle enthält aber nur `.onnx`; Downloads zur
  Laufzeit sind ausgeschlossen;
- Werkzeug für die Nachholung ist bereits im Server vorhanden und
  reproduzierbar:
  `python tools/wakeword_calibration.py scores --audio <datei.wav>`
  (sowie `artifacts` und `resources`). Seit C3 fährt `scores` die echten
  C3-Regeln – Prediction-Frames, `--threshold`, `--min-frames`,
  `--detector-gain`, `--vad-threshold`, `--noise-suppression` – und meldet
  finalisierte Trefferbereiche statt Einzelspitzen;
- Umgebungsvoraussetzung notieren: `openwakeword>=0.6.0` muss in der
  verwendeten Python-Umgebung tatsächlich installiert sein;
- Hinweis, dass die Wake-Word-Buildassets jetzt im Repository liegen
  (`VoiceSTT/assets/wakeword_models/`, ca. 15.9 MB) und
  `tools/sync_wakeword_assets.py --check` die Bundleintegrität gegen eine
  Quelle prüft.

**Welche SHA/Testwerte erst Root einsetzen darf:** kanonische AP-SRV-060-SHA
als neuer Wiedereinstiegsstand.

---

## 8. Zusammenfassung für Root

| Datei | Änderung nötig | Kernpunkt |
|---|---|---|
| `00_STEUERUNG\CURRENT_STATE.md` | JA | Serverstand nach AP-SRV-060, nächstes Paket AP-SRV-070 |
| `…\STATUS.md` | JA | AP-SRV-060 abgenommen, Kalibrierrest offen halten |
| `…\VERLAUF.md` | JA | C1-Einreichung, Review, Kanonisierung |
| `…\NACHVERFOLGUNG\AUSFUEHRUNGSSTATUS.md` | JA | AP-SRV-060 abgenommen, AP-SRV-070 freigegeben |
| `…\NACHVERFOLGUNG\TRACEABILITY.md` | JA | WW-01…WW-19, WIRE-02/04, SET-13b (WW-18/WW-19 bleiben EVIDENCE_BLOCKED, nur noch für die empirische Kalibrierung) |
| `…\NACHVERFOLGUNG\FUNDE.md` | JA | FIND-011 behoben, False-Positive-Policy bleibt messdatenabhängig; die zurückgezogenen Multi-Chunk-Aussagen nicht fortschreiben |
| `…\NACHVERFOLGUNG\WIEDEREINSTIEG.md` | JA | AP-SRV-070; benötigte Positivaudios und die `.tflite`-Bundleartefakte benennen |

Keine dieser Dateien wurde von AP-SRV-060 verändert.
