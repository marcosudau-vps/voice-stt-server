# Schnittstellen und Protokollkompatibilität

Die aktuelle Clientanbindung des Voice-STT-Servers verwendet das WebSocket-Protokoll V2 unter `/ws/v2`. Die Identität einer Verbindung, ihrer Aktivierungen und ihrer Segmente wird im V2-Ablauf bewusst getrennt geführt. Änderungen an Commands werden vom Server quittiert; Ereignisse dürfen daher nicht ohne Prüfung der Identitäten als erfolgreiche Aktion interpretiert werden.

## Migrationshinweise

Bestandsclients, die `/ws/transcribe` nutzen, sprechen den getrennt gepflegten Legacy-V1-Vertrag. Das ist kein Ersatz für den V2-Handschlag. Ein V2-Client muss die V2-Nachrichtenformen, Acknowledgements und Resynchronisierung einhalten. Bei einer Umstellung sollten bestehende Installationen und ihre Clientversionen gesondert geprüft werden, statt beide Protokolle zu vermischen.

Die maßgeblichen Kapitel behandeln [V2-WebSockets](v2-handbuch/04-schnittstellen/04.03-websocket-v2.md), [Legacy V1](v2-handbuch/04-schnittstellen/04.12-legacy-v1.md), [V1/V2-Unterschiede](v2-handbuch/09-anhaenge/09.03-v1-v2-unterschiede.md) und [Kompatibilitätsverträge](v2-handbuch/09-anhaenge/09.05-kompatibilitaetsvertraege.md). Die vollständige Ereignis- und API-Referenz steht im Handbuch, nicht auf dieser Übersichtsseite.
