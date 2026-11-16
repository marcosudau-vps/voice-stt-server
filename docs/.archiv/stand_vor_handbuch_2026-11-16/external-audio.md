# Audio von externen Clients

Ein Voice-STT-Server muss Audiodaten nicht zwingend selbst an einem lokalen Mikrofon abgreifen. Bei einer externen Anbindung stammt der Datenstrom vom Client, während der Server den Sitzungszustand, die Aktivierung und die Verarbeitung koordiniert.

Bei einem V2-Client ist die Übertragung Teil des WebSocket-Sitzungsvertrags. Eine bestehende Verbindung bedeutet noch nicht automatisch, dass Audiodaten in einem aktiven Eingabesegment akzeptiert werden. Vor dem Senden sind daher Handshake, Audioverfügbarkeit und der serverbestätigte Aktivierungszustand zu berücksichtigen. Auch Reconnect und eine neue Sitzung dürfen nicht als Fortsetzung beliebiger alter Segmente behandelt werden.

Konkrete Formate, Nachrichten, Sessiongrenzen und negative Fälle sind im [Audiotransport](v2-handbuch/04-schnittstellen/04.05-audiotransport.md), bei der [Audioverarbeitung](v2-handbuch/02-funktionsweise/02.02-audioverarbeitung.md), dem [Sessionmanagement](v2-handbuch/02-funktionsweise/02.01-session-management.md) sowie den [Integrationsbeispielen](v2-handbuch/04-schnittstellen/04.13-integrationsbeispiele.md) dokumentiert. Für den Legacy-V1-Eingang gilt dagegen sein eigener Vertrag.
