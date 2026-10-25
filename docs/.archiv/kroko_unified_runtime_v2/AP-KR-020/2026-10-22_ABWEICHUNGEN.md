# AP-KR-020 – Materielle Abweichungen

22.10.2026. Gesamtstatus BLOCKED. Der formale AP-010-Startblocker ist aufgehoben.

## D01 – Kein belastbarer Lizenzvalidierungsvertrag in Arbeitsschritt A

**Grund:** Die drei vorgeschriebenen Wege wurden gezielt bewertet:
vorhandene Schnittstelle, minimale native Ergänzung, kurzlebige Prüfgeneration.
Die gelesenen Quellen unterstützen nur modellgebundene Aktivierung. Eine
öffentliche unabhängige Validierung mit aktuellen Modellrechten ist nicht
nachgewiesen. Ein Export bestehender Booleans würde keine atomare aktuelle
Freigabe, typisierte Fehler oder bestätigte Entitlementzuordnung liefern.
Ein beendeter Probeprozess liefert keinen lebenden Besitzer-/Lizenznachweis.
Details und Quellen im [Schnittstellenbericht](2026-10-22_SCHNITTSTELLEN_LIFECYCLE.md).

**Auswirkung:** Arbeitsschritt A nicht bestanden. B–G und die zugehörige
Integrationsqualifikation bleiben nicht implementiert. Es gibt keine neue
Pro-Freischaltung, Lizenzautorität, Force-Community-Einstellung, Supervisor-
oder Komponentenprojektion. Die bestehenden Produktverträge gelten weiter;
dieser Stand verspricht auch keinen neuen automatischen Community-Fallback.

**Bewusste Entscheidung:** Den in Abschnitt 4 des Auftrags vorgesehenen
technischen Blocker melden, statt eine scheinbar vollständige Pro-Integration
mit synthetischen Lizenznachweisen oder erfundenen Anbieterregeln zu bauen.
Kein ungenutztes produktives Autoritäts-/Supervisorgerüst als fertiges Feature.

**Weiterer Schritt:** Unterstützten Anbieter-/Bindingvertrag gemäß Bericht
beschaffen beziehungsweise fachlich bestätigen, dann native Ergänzung explizit
versionieren, fingerprintbinden und A–G integrieren. Das ist eine Fortsetzung
von AP-020, kein neuer AP-010-Lauf und kein Beginn von AP-030.

## D02 – Echte Lizenzfälle nicht ausgeführt

**Grund:** Keine ausdrücklich benannte autorisierte Lizenztestumgebung mit
erlaubten Positiv-/Negativ-/Ablauf-/Widerrufs-/Kontingentfällen eingerichtet.
Vorhandene Secrets oder Modelle werden nicht gesucht. Die ausdrückliche
Implementierungsfreigabe ersetzt diese gesonderte Lizenztestautorisierung nicht.

**Auswirkung:** Kein neuer echter Pro-Nachweis. Auch ein vorhandener positiver
Vertrag würde ohne diese Realtests höchstens CONDITIONAL erlauben.

**Entscheidung:** Keine Lizenzserverexperimente, Keys oder simulierten
Lizenzantworten als echte Qualifikation. Diese Nachweislücke ist von D01 und
von der erledigten AP-010-Abnahme ausdrücklich getrennt.

## D03 – Teil-PR mit Testfix und Blockerakte

**Grund:** Der ausdrücklich übergebene Realtime-Testdefekt ist unabhängig von
D01 korrigierbar und im selben Auftrag zu bearbeiten.

**Auswirkung:** Der PR enthält den reproduzierten Regressionstestfix und die
vollständige Teilstandsakte; keinen abgeschlossenen Runtimeumbau. Der finale
PR wird als Draft mit BLOCKED gekennzeichnet. Keine automatische Mergefreigabe.

**Entscheidung:** Keine pauschalen Skips, keine abgeschwächten Assertions.
Die R1-Rückkehr wird zusätzlich nachgewiesen, da der Worker Modellfehler
abfängt und die alte Testfassung dadurch sogar falsch grün werden konnte.
Die ursprüngliche Prüfung alter R1-Ergebnisse gegen R2 bleibt erhalten.

Ein Wiederholungslauf deckte zusätzlich eine Race zwischen erster R2-Vorschau
und pollendem Testthread auf. Der Test stoppt daher im synchronen R2-Callback
und wartet auf ein Publikations-Event. Die genaue Sequenzassertion bleibt
erhalten; 100 finale Wiederholungen bestehen. Ein rein im Speicher entfernter
Stale-Guard wird durch dieselbe Assertion erkannt.

**Status:** Testfix gezielt grün; vollständige neue Suiteergebnisse separat
im [Evidenzbericht](2026-10-22_TEST_EVIDENZ.md). Gesamt-AP bleibt BLOCKED.
