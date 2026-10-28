# PR #15 – Abschlusskorrektur nach revidierter Abnahmegrundlage (Plan, 26.10.2026)

Dies ist eine **neue, datierte Ergänzung** zur Korrekturakte `01`–`08`
(25.10.2026). Die älteren Dateien bleiben unverändert; ihre Aussagen zu „alle
H-Befunde geschlossen“ und zu den Pro-Lanes sind durch diesen Nachtrag und die
[revidierte Abnahmegrundlage](https://github.com/marcosudau-vps/voice-stt-server/pull/15#issuecomment-6408087404)
überholt.

> **Prozesshinweis.** Die Planung wurde zu Beginn des Laufs im Arbeitsablauf
> festgelegt, aber erst mit dem Umsetzungscommit als Datei erfasst. Sie ist
> deshalb inhaltlich der Stand vor der Implementierung, zeitlich jedoch nicht
> vor deren Beginn archiviert (siehe Abweichungsdatei).

## Ausgangslage

Basis `4f000fd2`. Die revidierte Abnahmegrundlage ersetzt die technischen
Forderungen P0-01 bis P1-06 der Wiederabnahme vom 25.10.2026 und stützt sich auf
isolierte Messungen der Kroko-ONNX-1.12.9-Pro-Runtime:

* Community ohne Key in der Pro-Runtime funktioniert.
* Community → Pro und Pro → Community funktionieren in einem Prozess.
* Dasselbe Pro-Modell kann erneut geladen werden.
* Pro A → Pro B im selben Prozess hängt oder stürzt ab.
* Ein erneutes Laden beweist keinen Reset des nativen Lizenz-Singletons.

## Ziele

| ID | Ziel |
| --- | --- |
| P0-01 | Ein verspäteter Lizenz-Worker darf nie einen älteren Key-/Force-Intent erneut binden. |
| P0-02 | Force Community / Key-Entzug sperren neue Pro-Aufträge synchron; Unterschied Python-Freigabe ↔ nativer Lizenzkontext ehrlich ausweisen; Neustartbedarf anzeigen. |
| P1-03 | Automatische Berechtigungsprüfung auch aus Community-Konfiguration (Key + lokales Pro-Modell); Auswahlberechtigung ≠ Aktivierung. |
| P1-04 (neu) | Schutzguard: höchstens eine native Kroko-Modellidentität; Final/Realtime teilen eine Instanz; Verstöße vor jedem nativen Laden abweisen. |
| P1-05 | Prüfung und Admission lösen den Modellpfad über dieselbe Autorität auf (Engine-`model_dir`/Custom-Pfade). |
| P1-06 | Nach Hintergrundprüfung Berechtigung, Snapshot und Status generationssicher aktualisieren; Community↔Pro nur dort live, wo der vorhandene Scheduler-Lifecycle es sicher trägt, sonst Neustart/Zurückstellung ausweisen. |

## Nicht-Ziele (Arbeitsgrenzen)

Keine neue Native-Runtime-, Supervisor-, IPC- oder Prozessarchitektur; keine
Native-Patches oder Build-Fingerprint-Änderungen; keine Änderung des V2-Wire-
Vertrags; kein neuer Persistenzmechanismus für Credentials; keine allgemeine
Lizenzvertragsrecherche; kein Pro-A→Pro-B-Experiment; kein Merge, Rebase oder
Force-Push; kein Wechsel auf „Ready for Review“.

## Entscheidungen

1. **Gate (`security/kroko.py`).** `prepare` (Bind + Entscheidung + `begin`, ohne
   Netz, unter Sperre) und `run` (Netzwerk + generationsgebundenes `apply`)
   werden getrennt. Der Worker bindet nichts; nach Abschluss wird nur der
   *aktuelle* Zustand gelesen (`current_decision`).
2. **Service.** Intent lesen und binden geschieht atomar unter
   `_kroko_policy_lock`; das Netz läuft außerhalb der Sperre. Die Entitlement-
   Hook liest zusätzlich den Live-Force-Intent und den Native-Guard. Ein
   synchroner Auftrags-Gate in `_submit_scheduler_job` sperrt neue Aufträge
   auf eine aktive Pro-Instanz nach Force/Key-Entzug.
3. **Pfadautorität.** `STTModelManager.locate_local_path` /
   `resolve_license_uuid` / `local_license_candidates` sind die einzige
   Auflösung für Vorprüfung, Eligibility und Kandidatenwahl; die Eligibility
   erhält den im Snapshot gefundenen Kandidatenpfad.
4. **Native-Guard (`VoiceSTT/kroko/native_guard.py`).** Prozessweit; Regeln:
   eine native Instanz zur Zeit, nach Pro-Initialisierung nur dieselbe
   Pro-Identität und derselbe Key-Kontext, Pro nur mit Key. Durchgesetzt im
   Engine-Konstruktor (letzte Linie), in Load-Probe, Scheduler-Erstellung und
   Modellwechsel (vorab) sowie in der Konfigurationsprüfung
   (`enforce_kroko_single_identity`).
5. **Abgleich (`reconcile_kroko_models`).** Nutzt den vorhandenen
   transaktionalen Refresh. Ein Kroko-Kandidat wird nie neben einer anderen
   lebenden Kroko-Instanz geprüft; blockiert nur die laufende Instanz und ist
   der Server im Leerlauf, wird sie über `unload_models` freigegeben und der
   Refresh einmal wiederholt. Bei aktiver Arbeit: zurückgestellt, nie erzwungen.
6. **Status.** `krokoRuntime` in `GET /api/models/management` trennt installierte
   Variante, Berechtigung, gewünschtes und aktives Modell, nativen Kontext und
   Neustartbedarf. Kein Wire-Vertrag (V2) ändert sich.

## Risiken

* Der Modellabgleich entlädt im Leerlauf die einzige Instanz; mit aktiver Arbeit
  wird er zurückgestellt (kein stilles Verwerfen).
* Die Gate-Entscheidung gegen den nativen Kontext ist best-effort für den
  Python-Teil: Der native Reporter bleibt bis zum Neustart (ausgewiesen).
* Die Evidenz zu Linux-Verhalten stammt aus dem externen Testbericht und wurde
  hier nicht wiederholt.

## Abnahmekriterien

Deterministische Regressionstests je Befund, isolierte echte Native-Tests
(Community ohne Key, Pro mit Key, gemeinsame Pro-Instanz Final/Realtime,
produktiver Community↔Pro-Wechsel über den Serverpfad), vollständige Suite,
grüne GitHub-CI auf Ubuntu und Windows, konsistente Dokumentation,
aktualisierte PR-Beschreibung und Abschlusskommentar.
