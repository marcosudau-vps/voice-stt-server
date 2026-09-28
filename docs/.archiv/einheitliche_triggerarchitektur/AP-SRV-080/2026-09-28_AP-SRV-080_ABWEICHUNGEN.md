# AP-SRV-080: Abweichungen

**Datum:** 28.09.2026
**Status:** In Umsetzung

## A-01: Lokaler Wiederherstellungsstand entstand vor der Archivregistrierung

**Planabweichung.** Die ersten Produkt-, Vertrags- und Teständerungen entstanden
während einer historischen Verlustanalyse als uncommitteter lokaler
Wiederherstellungsstand, bevor AP-SRV-080 im Repositoryarchiv registriert war.

**Grund.** Zu Beginn war offen, ob Funktionen entfernt worden waren oder nur
die neue V2-Projektion unvollständig war. Erst die Rekonstruktion zeigte, dass
Realtime-Engine und Logging-Backend erhalten geblieben waren und eine
abgrenzbare öffentliche Protokollergänzung erforderlich ist.

**Auswirkung.** Die chronologische Vorgabe „Plan vor Implementierung“ war für
den bereits vorhandenen WIP nicht erfüllt. Vor Integration, Commit oder Push
wurde der Stand jedoch gesichert, PR #2 als Dokumentationsbasis gemergt, diese
Planung angelegt und der gesamte Umfang erneut gegen Plan und Tests geprüft.

**Entscheidung und weiterer Status.** Der WIP wird nicht als historische
Planung ausgegeben. Diese Abweichung bleibt dauerhaft dokumentiert. Die Aktion
kann erst nach vollständigem Soll-/Ist-Vergleich und öffentlicher CI auf
`Abgeschlossen` gesetzt werden.
