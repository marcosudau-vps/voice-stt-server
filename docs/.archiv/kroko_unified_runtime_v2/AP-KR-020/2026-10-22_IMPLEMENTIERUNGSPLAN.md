# AP-KR-020 – Implementierungsplanung

22.10.2026, vor Codeänderungen. Status: Geplant.

## Ausgangslage und Freigabe

Basis: `acdffc7042357cb8ae5e47961e42b78a25bd902c`,
`origin/feat/v2-unified-kroko`, aktuell per Fetch geprüft.
Arbeitsbranch: `feat/v2-unified-kroko-ap020`, exakt von dieser Basis erstellt.
Die [formale Abnahme von AP-010](https://github.com/marcosudau-vps/voice-stt-server/pull/11#issuecomment-6346283640)
und der ausdrückliche Folgeauftrag heben den früheren Startblocker auf.
Die historische AP-010-Akte bleibt unverändert.

## Ziele und Reihenfolge

1. Arbeitsschritt A zuerst abschließen: am gepinnten Kroko-Stand gezielt eine
   unterstützte Lizenzschnittstelle, danach eine minimale native Ergänzung,
   danach eine kurzlebige Prüfgeneration bewerten. Keine allgemeine Wiederholung
   von AP-010. Keine Lizenzserverkontakte und keine Suche nach Secrets.
2. Erst bei belastbarem Validierungsvertrag B–G integrieren: zentrale flüchtige
   Autorität mit Generation/Credentialrevision/Komponentenidentität und konkreten
   Rechten; kalter privater Bootstrap; vollständiger Besitzerprozesswechsel mit
   Startupfrist, bestätigtem Exit, begrenztem Retry und Community-Fallback;
   serverseitige Modellrechte; Force-Community in der Settings-Control-Plane;
   redigierte Statusprojektion und getrennte Build-/Komponentenidentität.
3. Wenn A technisch nicht belastbar lösbar ist, den konkreten Vertrag und
   fehlenden Nachweis dokumentieren. Keine scheinbar fertige Pro-Freischaltung,
   kein unbenutztes Ersatzgerüst als abgeschlossene Integration ausgeben.
4. Unabhängig davon den ausdrücklich beauftragten Realtime-Testfehler minimal
   reproduzieren und beheben. R1 muss nachweislich bis zum R2-Start blockieren,
   nach Freigabe tatsächlich zurückkehren und als veraltetes Resultat verworfen
   werden. Synchronisationsfehler müssen im Testthread sichtbar bleiben.
5. Gesamte relevante Unit-/Guard-/Contractsuite und vorhandene Packaging- und
   Kompatibilitätstests ausführen. Reale Lizenztests nur bei ausdrücklich
   autorisierter Umgebung; ansonsten NOT_RUN, niemals durch Mocks ersetzen.
6. Getrennte Verträge, Evidenz, Soll/Ist, materielle Abweichungen und Übergabe
   erstellen; aktuelle Fachdokumentation und lokale Links prüfen. Commit und
   PR gegen den Integrationsbranch, kein Merge.

## Entscheidungen und Risiken

Der Lizenzvertrag muss positive Berechtigung, autoritative Ablehnung,
Technikfehler, Ablauf/Widerruf, konkrete Modellrechte und Aktualität eindeutig
abbilden. Import oder Community-Modellaufbau unter Pro reicht nicht.
Ein Community-Standardmodell darf für die Prüfung nicht ersetzt werden.
Eine native Ergänzung wäre ein versionierter neuer Buildinput mit neuen
Fingerprints; die bestehende Authority darf nicht still umdefiniert werden.
Native Exits sind keine Pythonexceptions. Keine eigenen Lizenzprotokolle,
keine Freigabe aus Konsolentext oder aus unklassifizierten Exitcodes.

## Abnahme und Grenzen

Die zwölf Abnahmekriterien aus dem Auftrag werden einzeln gegen den realen
Stand geprüft. Fehlt A, lautet der Gesamtstatus BLOCKED, auch bei erfolgreicher
unabhängiger Testkorrektur. Fehlende echte Lizenzqualifikation allein erlaubt
höchstens CONDITIONAL. Bestehende V2-Vektoren, Integritäts-/Downloadgrenzen,
Secretpfade und Modellrechte bleiben verbindlich.

Kein öffentlicher Release, Registry-Push, Deployment, eigenständiger Merge,
geschützter V2-Branchwechsel, Upstreamwechsel oder Beginn von AP-KR-030.
