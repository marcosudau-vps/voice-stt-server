# Abweichungen: sitzungslokale Wake-Word-Konfiguration

Erstellt am 01.08.2026 als separate Ergänzung zur Aktion vom 25.07.2026.

## 1. Explizite Parameter statt allgemeiner Profilnamen

**Ursprünglicher Entwurf:** Ein `profile`-Parameter sollte benannte Profile wie
`direct_hotkey` und `wake_word` auswählen.

**Umsetzung:** Der veröffentlichte Vertrag verwendet den Tri-State-Parameter
`wakeWordEnabled` sowie ausdrücklich benannte Wake-Word-Tuningfelder.

**Begründung:** Der wirksame Zustand ist dadurch direkt im Protokoll sichtbar,
ohne eine zweite, serverseitig veränderliche Profildefinition auflösen zu
müssen. Die Serverbaseline bleibt die eindeutige Quelle für geerbte Werte.

**Auswirkung und Status:** Bewusste, abgeschlossene Vertragsentscheidung.

## 2. Begrenzung auf Wake-Word-Einstellungen

**Ursprünglicher Entwurf:** Sessionprofile sollten perspektivisch auch Audio,
VAD, Segmentierung, Realtime-Verhalten und Prompts bündeln.

**Umsetzung:** Überschreibbar sind ausschließlich die für den
Wake-Word-Lifecycle erforderlichen Felder. Modell- und Enginebetrieb,
Kapazitätsgrenzen und sonstige globale Sicherheitswerte bleiben serverweit.

**Begründung:** Der kleinere Scope minimiert Ressourcenkonflikte und verhindert,
dass ein Client geteilte Modelle oder globale Betriebsgrenzen indirekt
verändert.

**Auswirkung und Status:** Bewusste Sicherheits- und Scopeentscheidung. Ein
allgemeines Sessionprofilsystem wäre eine neue größere Änderungsaktion und
müsste separat geplant werden.

## 3. OpenWakeWord als einziger öffentlicher Server-Backendvertrag

**Ursprünglicher Entwurf:** Die Backendfrage war allgemeiner gehalten.

**Umsetzung:** Sessionkatalog, Browserauswahl und Adminvertrag veröffentlichen
nur OpenWakeWord. Porcupine bleibt eine Bibliotheksfähigkeit, ist aber nicht
Teil des aktuellen Multi-User-Serververtrags.

**Begründung:** Nur lokal auflösbare und serverseitig verifizierbare Modelle
sollen über den Sessionvertrag auswählbar sein.

**Auswirkung und Status:** Bewusste, dokumentierte Produktgrenze.
