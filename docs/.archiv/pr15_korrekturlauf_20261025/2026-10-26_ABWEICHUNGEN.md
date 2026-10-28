# PR #15 – Abweichungen der Abschlusskorrektur vom Plan (26.10.2026)

Je Abweichung: Grund, Auswirkung, Entscheidung beziehungsweise Handlungsbedarf,
Status. Bezug: [Plan](2026-10-26_PLAN_ABSCHLUSSKORREKTUR.md),
[Soll-/Ist-Vergleich](2026-10-26_UMSETZUNGSVERGLEICH.md).

## A1 – Bestätigter nativer Kontext als Berechtigungsnachweis (nicht geplant)

* **Grund.** Der isolierte Realtest des produktiven Wechsels (Community → Pro →
  Force → Community → Force frei → Pro) zeigte, dass der Lizenzdienst eine
  zusätzliche externe Prüfung desselben Keys/Modells mit `license_rejected`
  ablehnt, sobald ein nativer Pro-Reporter im Prozess existiert (bestätigt in
  einem eigenen kleinen Experiment: zwei frische Prüfungen ohne nativen Pro
  `VALID`; Prüfung während **und** nach dem Schließen des nativen Pro
  `INVALID`). Der 60-s-Nachweis ist dann nicht erneuerbar; ohne Gegenmaßnahme
  würde jeder Admin-Refresh nach Ablauf das laufende Pro-Modell auf Community
  herabstufen und „Pro erneut“ wäre unmöglich.
* **Entscheidung.** Für dasselbe Pro-Modell und denselben Key gilt die
  **bestätigte native Ladung** als Nachweis (`confirm_loaded` im Guard,
  `licenseSource: "native_context"`, keine weitere Provider-Verbindung). Andere
  Modelle, andere Keys und Force Community werden nie davon abgedeckt.
* **Auswirkung.** Mehr Verhalten als die sechs Befunde verlangen; dokumentiert in
  `kroko-onnx.md` und `server-authentication.md` §4.5. Die Gültigkeit der Lizenz
  während des Betriebs bleibt Sache der nativen Runtime.
* **Status.** Umgesetzt und mit realem Provider belegt (Windows, ein Key). Ob
  die Ablehnung durch ein Connection-Limit oder eine andere Provider-Regel
  entsteht, wurde nicht ermittelt (keine Anbieterrecherche im Auftrag).

## A2 – Pfad-Auflösung prüft keine Größe/Hash

* **Grund.** `locate_local_path` adressiert eine Datei anhand ihres Namens in den
  Discovery-Roots; ein Größenabgleich würde die vorhandenen Fixtures mit
  synthetischen Headerdateien unterbinden und ändert nichts an der Sicherheit
  der Aktivierung.
* **Auswirkung.** Eine unvollständige Pro-Datei kann eine Lizenzabfrage
  auslösen. Aktiviert wird sie nie: der Snapshot verlangt weiterhin
  `VALIDATED` (Größe) und `LOAD_VERIFIED`.
* **Status.** Bewusst; keine weitere Handlung.

## A3 – Schärfere Konfigurationsregel (Verhaltensänderung)

* **Grund.** Betriebsgrenze „höchstens eine native Kroko-Modellidentität“.
* **Auswirkung.** `enforce_cpu_model_policy` lehnt Final ≠ Realtime bei Kroko mit
  `ValueError` ab (zuvor zwei Recognizer). Bestehender Test
  `test_service_recheck_path_with_fake_transport` musste auf ein gemeinsames
  Modell umgestellt werden (Testdaten, kein Produktivcode). Release-Hinweis in
  `RELEASE_NOTES.md` (Unreleased).
* **Status.** Beabsichtigt.

## A4 – Planarchivierung nach Beginn der Umsetzung

* **Grund.** Die Planung entstand im Arbeitsablauf zu Beginn des Laufs, wurde aber
  erst mit dem Umsetzungscommit als Datei ins Archiv aufgenommen.
* **Auswirkung.** Prozessabweichung gegen `AGENTS.md` (Plan vor Umsetzung als
  Datei). Der Registereintrag wurde ebenfalls erst im Laufe der Umsetzung
  angelegt.
* **Status.** Offengelegt; kein inhaltlicher Einfluss.

## A5 – Umfang der Realtests

* Nur Windows und ein Key; Linux, Mehrsitzungs- und Lastverhalten der
  Umschaltung sowie lang laufende Reporter-Szenarien sind **NOT_RUN**.
* Der Pro-Wechsel „Force aus → dasselbe Pro“ nutzt einen Neuladevorgang
  desselben Modells. Der externe Testbericht beobachtete dafür unter Linux einen
  späteren Shutdown-Timeout; das wurde hier nicht nachgestellt.
