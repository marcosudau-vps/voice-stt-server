# FastAPI- und WebSocket-Schnittstellen

Der HTTP- und WebSocket-Eingang des Voice-STT-Servers wird über die FastAPI-Anwendung bereitgestellt. Dahinter liegen spezialisierte Verwaltungs-, Sicherheits- und Transkriptionskomponenten. Die Existenz einer Route ist nicht gleichbedeutend mit anonymem Zugriff: Manche Endpunkte verlangen getrennte Berechtigungen für Administrationsbefehle, Logs oder die OpenAI-kompatible API.

## Öffentliche Schnittstellen

Die V2-Schnittstelle `/ws/v2` ist der primäre, zustandsbehaftete Clientkanal. Andere HTTP-Routen geben Status, Schema-, Konfigurations- oder Verwaltungsinformationen zurück und müssen entsprechend ihren Authentifizierungsregeln aufgerufen werden. Der Server stellt außerdem die gesonderte OpenAI-kompatible `/v1/*`-Oberfläche sowie einen Legacy-V1-WebSocket bereit.

Die vollständigen und codegeprüften Methoden, Routen und Felder stehen im [API-Endpunkt-Katalog](v2-handbuch/08-referenzen/08.04-api-endpunkt-katalog.md). Siehe außerdem [Schnittstellenübersicht](v2-handbuch/04-schnittstellen/04.01-schnittstellenuebersicht.md), [HTTP-Grundlagen](v2-handbuch/04-schnittstellen/04.02-http-grundlagen.md), [V2-WebSocket](v2-handbuch/04-schnittstellen/04.03-websocket-v2.md), [Authentifizierung](v2-handbuch/05-administration/05.01-sicherheitsarchitektur.md) und [Fehlerantworten](v2-handbuch/05-administration/05.10-fehler-zugriffsantworten.md).
