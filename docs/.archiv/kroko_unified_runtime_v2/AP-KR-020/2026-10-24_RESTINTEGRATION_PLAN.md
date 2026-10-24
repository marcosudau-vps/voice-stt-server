# AP-KR-020 Restintegration – Plan und initialer Soll/Ist-Abgleich

24.10.2026, vor Implementierung. Basis: Remote-HEAD
`454e497fff4c0b1f466de03f536a13cf7bce522a`, nach `git fetch origin`.
Eigener isolierter Worktree, Branch `work/ap-kr-020-restintegration`.
Bestehende Checkouts bleiben unverändert. Pflichtakten gelesen.

| Kategorie | Nachprüfbarer Iststand |
| --- | --- |
| Implementiert und synthetisch qualifiziert | Authority, Bootstrap, manifestiertes Community-Fallback; bestehende AP-020-Suite: 43 passed, Windows CPython 3.12.10. |
| Implementiert, unvollständig integriert | `OwnerSupervisor` wird vom Serverstart nicht aufgerufen; Force-Schalter invalidiert nur Status; Modellwechsel vergleicht keine Modellidentität. |
| Produktiv fehlend | Versionierter nativer Statusadapter; kohärenter nativer Snapshot; überwachte ASGI-Prozessgeneration und Restart-Anforderung über bestehende Adminpfade. |
| Fehler in vorhandener Implementierung | `run_check` hat eine Lücke zwischen Generationprüfung und Commit; parallele Checks teilen CHECKING; Verifierausnahmen bleiben unbehandelt; `accept_event` akzeptiert Ereignisse nach Stop/Exit; konkurrierende Starts sind nicht serialisiert. |
| Ausschließlich Realqualifikation | Lizenzablehnung/Offlineverhalten beim Anbieter, neue vollständige Native-Wheels je Plattform, Deployment/Reconnect unter Last. |
| AP-025/AP-030-Abhängigkeiten | Verifizierte Pro-Modellmetadaten/UUID-Abbildung fehlen im Communitymanifest; offizielle disjunkte Payloads und Komponentenprovenienz gehören AP-030. |

## Umsetzung und Abnahme

1. Authority atomar und modell-/ownergebunden machen, Gründe redigieren,
   aktuelle Nachweise begrenzen. Native Snapshot-API versionieren und soweit
   lokal möglich bauen/testen; kein Python-Lizenzprotokoll, kein Livekontakt.
2. Supervisor serialisieren, Exit bestätigen, Readiness an Kindgeneration
   binden; produktiven Serverlauncher und kontrollierte Neustarts integrieren.
   Ein Besitzer, kein zweiter ASR-Worker. Fehler/Timeout führen zu begrenztem
   Community-Fallback. Bestehende V2-Envelopes bleiben unverändert.
3. Bestehende Settings-/Adminpfade weiterverwenden; nur Intent persistieren,
   keine Secrets in Status. Modell-/Force-/Keywechsel dürfen keine alte
   Nativegeneration weiter freigeben.
4. Gezielte Unit- und echte lokale Kindprozesstests mit synthetischem Native,
   dann gesamte praktikable Regression. Exakte Befehle/Ergebnisse festhalten.
5. Getrennte Soll/Ist-, Abweichungs- und Übergabeakte; aktuelle Fachdokumente
   nachziehen, thematische Commits, Draft-PR ausschließlich gegen AP-020.

Keine Downloadverwaltung, kein Katalogmerge, keine LAB-Änderungen, kein
Release/Deployment. Nicht ausgeführte Realtests bleiben NOT_RUN. Fehlende
Anbietersemantik wird nicht aus Logs/Exitcodes abgeleitet. Native Änderungen
benötigen Patchrevision, Quelldigests und neue Fingerprints.
