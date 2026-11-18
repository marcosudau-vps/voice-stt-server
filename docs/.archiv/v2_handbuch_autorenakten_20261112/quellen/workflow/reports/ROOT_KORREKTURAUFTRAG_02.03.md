# Korrekturauftrag nach externer ROOT-Prüfung – ausschließlich Kapitel 02.03

Der eigenständige ROOT-Review hat vier konkrete Korrekturfindings festgestellt. **Das bisherige interne PASS ist noch keine externe Abnahme.**

Lies zunächst vollständig `workflow/reviews/02.03-ROOT-REVIEW-2026-11-06.md` und `SPEZIFIKATION_v0.2.md`. Verwende `a8993c5c68042d996eab680d84a5b138a214bb5d` als Quellstand, verifiziere den tatsächlichen HEAD selbst.

Bearbeite nur `02.03 Activation`:
- **ROOT-01:** V1-Controlled kann die sechs Activation-Timings über Queryparameter erhalten; die Darstellung „nur Defaults“ ist falsch. V1-Legacy abgrenzen.
- **ROOT-02:** Replay-Cache nur pro Session; keine garantierte `commandId`-Idempotenz über eine neue Session nach Disconnect.
- **ROOT-03:** V2-`activate` verlangt `source: "manual"`. Das Weglassen dieses Felds ist falsch; es darf nur aus `refresh/finish/cancel` entfallen. Wake-Word-Admission ist serverseitig.
- **ROOT-04:** ActivationController existiert nur bei Controlled Activation; klassische V1-Legacy-Sitzungen besitzen ihn nicht.
- Redaktionell §3.3 stream/session Rejections vom Geräteverlust sauber trennen.

Rufe die **tatsächlich konfigurierten** `doc-researcher` (DeepSeek), `doc-writer` (DeepSeek) und `doc-reviewer` (Muse) separat auf. Researcher ausschließlich Code/Schemas/Tests; Writer praxisorientiert; Reviewer prüft die korrigierten Sätze eigenständig gegen den Originalcode und erneut alle betroffen dargestellten Diagrammübergänge.

Lege einen neuen Review-Nachtrag an, protokolliere jedes ROOT-Finding als CLOSED oder OPEN mit Beleg, überprüfe `python tools/workflow_cli.py validate` und relevante Unit-Tests. Erhalte die vorherige Reviewer-Historie und schaffe keine stillschweigende Überschreibung.

Ändere den Produktcode, die alte Dokumentation oder die anderen 103 Kapitel **nicht**. Kein Merge, Push, Release oder Folgekapitel.

Melde anschließend `ROOT_REVIEW_READY` mit den konkreten Änderungen, den Belegen, den tatsächlich eingesetzten Subagenten (nach Möglichkeit mit Session-IDs) und dem unabhängigen Endurteil.
