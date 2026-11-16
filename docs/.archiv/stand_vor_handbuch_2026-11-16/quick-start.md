# Schnelle Orientierung

Für einen ersten V2-Start sind drei Dinge zu unterscheiden: ein zur Plattform passendes Serverpaket, die erforderlichen Modelldateien und eine gültige Konfiguration für den gewählten Betriebsmodus. Die native Kroko-Fähigkeit ist im geplanten öffentlichen Paket enthalten; Pro-Modelle benötigen zusätzlich einen für das Modell gültigen Key.

## Serverstart als Beispiel

Der Server stellt den Einstieg über `voice-stt-server` bereit. Ein typischer lokaler Aufruf setzt Host und Port ausdrücklich:

```powershell
voice-stt-server --host 127.0.0.1 --port 8765
```

Dies ist ein Aufrufmuster, **keine Zusage**, dass auf einem frisch installierten System bereits alle Modelle geladen oder eine Transkriptionssitzung bereit ist. Die Readiness muss getrennt geprüft werden. Für eine noch nicht öffentlich veröffentlichte V2 sind ausschließlich geprüfte lokale Artefakte oder ein qualifizierter Quellstand geeignet.

Ausführliche, nach Zielsystem und Modellverfügbarkeit getrennte Schritte enthalten [Ersteinrichtung](v2-handbuch/06-betrieb/06.06-ersteinrichtung.md), [Serverstart und Stopp](v2-handbuch/06-betrieb/06.07-serverstart-stopp.md), [Installation](v2-handbuch/06-betrieb/06.02-installationskonzept.md) und [Fehlerdiagnose](v2-handbuch/06-betrieb/06.12-fehlerdiagnose.md). Für Clienttests beginne mit [V2-WebSocket](v2-handbuch/04-schnittstellen/04.03-websocket-v2.md).
