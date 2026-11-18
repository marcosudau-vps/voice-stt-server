# AP-SRV-070 / W5-R01 - Abweichungen

## AW-01: Archiv-Plan wurde nicht strikt vor Implementierungsbeginn angelegt

- **Soll:** `docs/.archiv/README.md` (verbindlich via `AGENTS.md`) verlangt:
  "Vor der Implementierung eine datierte Gesamtplanung erstellen." Der
  W5-R01-Plan (`docs/.archiv/einheitliche_triggerarchitektur/AP-SRV-070/2026-09-06_W5_R01_PLAN.md`)
  haette also vor dem ersten Implementierungsschritt (Anlegen von
  `release_tooling/`) existieren muessen.
- **Ist:** Der Plan wurde faktisch erst geschrieben, nachdem
  `release_tooling/` und `release.py` bereits implementiert und lokal
  getestet waren (nach dem Lesen der bindenden Autoritaeten, aber vor
  Fertigstellung von CI/Doku/Tests/Archiv-Vergleich). Reihenfolge dieses
  Runs faktisch: Autoritaeten lesen -> Implementierung `release_tooling/` ->
  Plan-Dokument -> CI/Doku/Release-Notes -> volle Testsuite -> Soll-/Ist-
  Vergleich.
- **Ursache:** Arbeitsreihenfolge-Fehler bei der Umsetzung dieses Runs -
  keine bewusste Entscheidung, den Archivprozess zu umgehen.
- **Auswirkung:** Der Plan beschreibt inhaltlich exakt das, was tatsaechlich
  gebaut wurde (er wurde aus der bereits getroffenen Architektur heraus
  formuliert, nicht umgekehrt), es gibt also keine inhaltliche Luecke
  zwischen Plan und Umsetzung und keinen Sicherheits- oder
  Korrektheitsimpakt. Der Verstoss ist rein prozessual: die vorgeschriebene
  Reihenfolge (erst Plan, dann Code) wurde nicht eingehalten.
- **Entscheidung:** Wird als materielle Abweichung dokumentiert und nicht
  verschwiegen. `03_GATE_INDEX.md` bewertet **W5P-G03** deshalb als **FAIL**
  (das Gate verlangt explizit "vor der Implementierung"), auch wenn der
  Plan inhaltlich vollstaendig und zutreffend ist. Root Review entscheidet,
  ob dies fuer die Freigabe dieses Runs blockierend ist; fuer W5-R02/W6 gilt
  ab sofort wieder die volle Prozessreihenfolge.
- **Weiterer Status:** Kein Nacharbeitsbedarf am Plan-Inhalt selbst. Fuer
  kuenftige Runs: Plan-Datei als allerersten Schritt nach dem Lesen der
  bindenden Autoritaeten anlegen, vor jeder Code-Aenderung.

## Sonstige Beobachtungen (keine Abweichung vom Prompt)

- Ein voller `python -m pytest -q tests/unit`-Lauf in dieser Sandbox kann
  mit `PermissionError: [WinError 5] Zugriff verweigert:
  '...\AppData\Local\Temp\pytest-of-marco'` fehlschlagen, wenn dieses von
  pytest verwaltete Standard-Temp-Basisverzeichnis in der Sandbox gesperrt
  ist. Das ist eine Umgebungseigenschaft dieser Sitzung (reproduzierbar auch
  ohne jede Code-Aenderung), keine Regression durch W5-R01: ein gezielter
  Retry mit ueberschriebenem `TEMP`/`TMP` (Projektunterordner statt
  OS-Standard) bestaetigt dies. Die fuer `03_GATE_INDEX.md`/`05_FINAL_REPORT.md`
  gewertete volle Testsuite laeuft mit dieser Ueberschreibung; siehe
  `Evidence/07_Tests/`.
- GHCR-/Docker-Hub-Repository-Namen sind bewusst nicht konfiguriert (siehe
  Plan, Entscheidung C) - kein Blocker fuer W5-R01, aber ein offener Punkt,
  der vor einem echten W6-Lauf durch eine explizite Betreiberentscheidung
  gesetzt werden muss.
