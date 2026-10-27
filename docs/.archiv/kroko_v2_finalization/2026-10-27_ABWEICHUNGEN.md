# Abweichungen und offene Gates

2026-10-27. Status: Prüfung offen.

## Technisch notwendiger Nativefix

Der reale Linux-Pro-Child aktivierte, transkribierte und schrieb RESULT,
beendete sich aber nicht. Der Lauf wurde nach 653.70 s gezielt beendet:
1 PASS / 1 FAILED; restliche Linuxszenarien NOT_RUN. Der separate Windowslauf
mit vorhandenem Runtimeinput bestand alle vier Szenarien (109.90 s).
Nach [vorheriger Planung](2026-10-27_NATIVE_SHUTDOWN_PLAN.md) wird der bestehende
Asio-Lizenzreporter vor dem Destruktor-join gestoppt. Keine Übernahme von PR 14.
PATCH_SET_REVISION 5 und Hashguard bilden die tatsächliche Nativeänderung ab.
Neuer Windows-Pro-Fingerprint: 54b5f488d34ff173; historisches e4f939933cd9985d
bleibt Patch 4. Ein Rebuild ist ausschließlich wegen des belegten Nativefehlers
nötig. Bis echte Tests der neuen Bytes erfolgreich sind: technisch BLOCKED.

## Externe Ressourcen

Der erste Windows-Neubuild scheiterte vor der Kompilation am unveränderten,
gepinnten Ubuntu-Snapshot: HTTP 503 Service Unavailable für
snapshot.ubuntu.com/ubuntu/20260825T000000Z, noble/noble-updates/noble-security.
Keine Ersatztoolchain, kein unpinnter Mirror oder stilles Altartefakt wird
verwendet. Ein erneuter unveränderter Versuch und die Plattformqualifikation
werden separat dokumentiert.
Der begonnene Linux-Patch-4-Build wurde für den notwendigen Patch-5-Neubuild
beendet, nicht als qualifiziert ausgewiesen.

## Redistribution und Veröffentlichung

Source-Lizenztexte und technische Tests belegen nicht die vollständigen
Pro-Produktrechte. Vertrags-/Binary-Redistribution, finales transitive dependency
inventory und gegebenenfalls Microsoft-Rechte bleiben externe Release-Gates.
Der source-kontrollierte Status bleibt BLOCKED. Keine Veröffentlichung,
öffentlichen Tags oder Registry-Pushes sind erfolgt. Remote-Staging-Promotion
wird durch Simulationen geprüft; eine echte Promotion benötigt gesonderte
explizite Autorisierung und vollständige qualifizierte Artefakte.
