# PR #8: Gesamtplanung der unabhaengigen P1-Clear-Korrektur

Stand: 2026-10-19, vor Produktimplementierung.

## Ausgang und enger Auftrag

Repository `marcosudau-vps/voice-stt-server`, vorhandener PR #8,
Arbeitsbranch `marcosudau-wake-rearm-reset`, Ausgangscommit
`3475f1d43dab945443e8c38d8c877a25d32528d8`.
Ziel bleibt `feat/einheitliche-triggerarchitektur-distributed`.
Der Worktree ist sauber; die urspruenglichen Ubuntu-/Windows-PR-Checks
sind erfolgreich. Das ist kein Nachweis fuer die neue Korrektur.

Der unabhaengige Reviewbefund ist bestaetigt: `clear()` setzt unter
`self.lock` den Session-/Activationzustand zurueck und invalidiert den
Detektor erst nach Lockfreigabe. Dazwischen kann `admit()` unter dem
Coordinatorlock die noch alte Generation pruefen und auf der nun freien
Activationautoritaet committen. Die Lifecycleepoche sperrt diesen Pfad nicht.

## G1: Deterministischer ROT-Nachweis

Ein echter Evaluator mit zustandsbehaftetem Fakemodell berechnet einen Hit.
Ein Clear-Thread wird unmittelbar vor `_reset_wake_detector()` angehalten,
nachdem die Session zurueckgesetzt und ihr Lock freigegeben wurde.
Ein Admission-Thread bietet den alten Hit an. Events und ein transparenter
Probe-Wrapper um das bestehende RLock erfassen den Lockversuch ohne Sleeps.
Ohne Fix darf der Thread bis zum falschen Commit laufen, bevor der Test
Clear weiterlaufen laesst; mit Fix muss er bis zur Invalidierung warten.
Erwartung: keine neue Activation und kein logisches Wakeevent.
Der unveraenderte Vorherstand und das tatsaechliche FAIL werden getrennt
festgehalten, bevor Produktcode geaendert wird.

## G2: Minimale Synchronisationskorrektur

Die vorhandene Coordinator-RLock soll den Sessionreset und den anschliessenden
Detektorreset als eine Admissiongrenze umschliessen. Ein kleiner expliziter
Contextmanager im Coordinator darf dazu das bestehende Lock exponieren,
ohne neue Zustandsvariable oder neue Sperre. `clear()` tritt vor seinem
Sessionlock in diese Grenze ein und invalidiert erst nach Sessionlockfreigabe.
Legacy ohne Coordinator verwendet einen leeren Contextmanager.

Lockreihenfolge: Coordinator -> Session; nach Freigabe der Session
Coordinator -> Evaluator -> Engine. Keine Sessioncallbacks unter
Evaluator-/Enginelock, kein Warten auf Coordinator unter Sessionlock.
Bereits zuvor abgeschlossene Admissions werden regulaer durch Clear
geschlossen; wartende alte Hits werden nach Reset als stale abgewiesen.
Frische Hits nach Clear bleiben normal admissible.

Keine Aenderung an Scoring, Frames, Cursor, Pre-Roll, Cooldown, Events,
Schemas oder ActivationController. Die bisherigen Issue-7-Korrekturen bleiben.

## G3/G4: Verifikation und Abgabe

- Derselbe ROT-Test muss GRUEN werden: konkurrierender und nach Clear
  erneut angebotener alter Hit wirkungslos; frische Phrase erfolgreich.
- Echter In-flight-Inferenzpfad gegen Clear mit Events: Sessionlock bleibt
  verfuegbar, beide Threads terminieren, alter Hit wirkungslos, neuer erlaubt.
- V2-Identitaeten, exakt ein logisches Event, unveraenderter Score und
  wiederholte Admission desselben Hits pruefen.
- Bestehende Finish-/Cancel-/Timeout-, Samplepositions-/Pre-Roll- und
  v2 Regressionen ueber die elf Pflichtmodule erneut ausfuehren.
- Vollstaendige verfuegbare Fast-Suite auf eingefrorenem finalem Code;
  keine neuen Skips und keine abgeschwaechten Assertions.
- Diff und Lockreihenfolge dateiweise pruefen. Aktuelle Wake-Dokumentation,
  getrennten datierten Soll-/Ist-Nachtrag und Register aktualisieren;
  historische Originalberichte nicht umschreiben.
- Produkt-/Testcommit und dokumentierte Messungen auf denselben Branch
  pushen, denselben PR #8 aktualisieren und neue CI-Ergebnisse beobachten.

Keine neuen Features oder Eventfelder, kein neuer PR, keine selbsterteilte
Review-/Mergefreigabe, kein Merge, Release oder Deployment.
Physische Modell-/Hardware- und Clientqualifikation bleiben getrennt offen.
