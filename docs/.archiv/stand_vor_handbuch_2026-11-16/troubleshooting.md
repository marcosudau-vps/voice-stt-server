# Fehlerdiagnose im Voice-STT-Server V2

Fehler sollten zuerst der Ebene zugeordnet werden, in der sie entstehen: Paket und Betriebssystem, Start und Konfiguration, Authentifizierung, Verbindung/Session, Aktivierungsphase, Modell oder eigentliche Transkription. Ein Client, der einen WebSocket öffnen kann, beweist damit beispielsweise noch nicht, dass ein Modell geladen oder die Audioverarbeitung bereit ist.

## Diagnose in sinnvoller Reihenfolge

Zunächst sind installierte Version und Plattform sowie die sichtbare Serveridentität zu prüfen. Danach folgen Readiness und Modellstatus, dann die verwendete Route, die Berechtigungen und schließlich der serverbestätigte Aktivierungszustand. Zeitüberschreitungen, zurückgewiesene Commands oder verlorene Verbindungen verlangen andere Maßnahmen als eine nicht auffindbare Modelldatei. Secrets und Transkriptinhalte dürfen nicht in ungeschützten Supportlogs gesammelt werden.

Die [Fehlerdiagnose](v2-handbuch/06-betrieb/06.12-fehlerdiagnose.md) führt die typischen Ursachen zusammen. Ergänzend beschreiben [Fehlerkatalog](v2-handbuch/08-referenzen/08.09-fehlerkatalog.md), [Logging](v2-handbuch/06-betrieb/06.09-logging.md), [Reconnect](v2-handbuch/04-schnittstellen/04.08-reconnect.md) und [Monitoring](v2-handbuch/06-betrieb/06.10-monitoring-und-metriken.md) den Umgang mit reproduzierbaren Fehlerbildern.
