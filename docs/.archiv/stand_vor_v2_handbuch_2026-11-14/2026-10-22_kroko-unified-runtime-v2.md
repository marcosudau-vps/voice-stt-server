# Unified Kroko Runtime V2 — Untersuchungsstand vom 22.10.2026 (historisch)

> **Einordnung (25.10.2026, PR-#15-Korrekturlauf):** Diese Seite hält den
> Untersuchungsstand vom 22.10.2026 fest und wird nicht rückwirkend
> umgeschrieben. Überholt sind insbesondere: das optionale Pro-Addon- und
> Supervisor-Modell (der geltende Buildvertrag in [build/BUILD.md](../build/BUILD.md)
> liefert zwei vollständige alternative Distributionen `voice-stt-server` /
> `voice-stt-server-pro`); der damals offene Lizenz-Lifecycle ist seit dem
> Korrekturlauf als automatische modellgebundene Policy mit Manager-Integration
> implementiert ([Server-Authentifizierung](server-authentication.md#4-kroko-on-premise-modelllizenz--produkt-entitlement-kein-api-login),
> [Kroko-ONNX](kroko-onnx.md)). Maßgeblich für Build/Packaging ist allein
> `build/BUILD.md`; maßgeblich für die Laufzeit die genannten Fachseiten.

Stand 22.10.2026: AP-KR-010 ist eine Machbarkeitsuntersuchung, zur unabhängigen
Prüfung vorgelegt. Die produktive Installation bleibt unter
[build/BUILD.md](../build/BUILD.md) beschrieben. Das geplante Extra `kroko_pro`
und eine separate Pro-Komponente sind noch kein verfügbares Produkt.

Die echten qualifizierten Nativepayloads lassen sich auf Windows AMD64 und
Linux AMD64 (lokal WSL), jeweils CPython 3.12, in getrennten privaten
Verzeichnissen bereitstellen und in frischen Prozessen auswählen. Community
läuft auch unter der Pro-Runtime ohne Key. Das belegt keine gültige Prolizenz.
Native Fehler können den Besitzerprozess beenden; empfohlen ist deshalb
vollständiger Prozesswechsel mit kontrolliertem Communityfallback.

Das Urteil ist **CONDITIONAL GO**. Vor AP-KR-020 fehlen unabhängige Abnahme,
autorisierte echte Lizenztests, belastbarer Status-/Modellberechtigungs- und
Widerrufsvertrag sowie bestätigte Neustart-/Sessionsemantik. Bei Packaging
und Release bleiben vollständige Native-/Paket-/Imageprovenienz und identische
qualifizierte Artefaktbytes verbindlich. Separate Redistributionsrechte und
Lizenzressourcen sind vor Veröffentlichung vollständig zu prüfen.

- [Gesamtplanung](.archiv/kroko_unified_runtime_v2/2026-10-22_GESAMTPLAN.md)
- [Methodik](.archiv/kroko_unified_runtime_v2/AP-KR-010/2026-10-22_UNTERSUCHUNGSMATRIX.md)
- [Ergebnisse und Plattformbelege](.archiv/kroko_unified_runtime_v2/AP-KR-010/2026-10-22_ERGEBNISBERICHT.md)
- [Architektur und Lizenzstatusvertrag](.archiv/kroko_unified_runtime_v2/AP-KR-010/2026-10-22_ARCHITEKTURENTSCHEIDUNG.md)
- [Risiken und Startvoraussetzungen](.archiv/kroko_unified_runtime_v2/AP-KR-010/2026-10-22_RISIKEN.md)
- [Übergabe AP-KR-020/030](.archiv/kroko_unified_runtime_v2/AP-KR-010/2026-10-22_UEBERGABE.md)
- [Soll-/Ist-Prüfung und Tests](.archiv/kroko_unified_runtime_v2/AP-KR-010/2026-10-22_SOLL_IST.md)
- [Abweichungen](.archiv/kroko_unified_runtime_v2/AP-KR-010/2026-10-22_ABWEICHUNGEN.md)
- [Experiment: Artefaktaudit und native Prozesse](.archiv/kroko_unified_runtime_v2/AP-KR-010/experiments/2026-10-22_native_probe.py)
- [Experiment: Extra, Versionsbindung und Deinstallation](.archiv/kroko_unified_runtime_v2/AP-KR-010/experiments/2026-10-22_extra_probe.py)

VERIFIZIERT, CODEANALYSE, SIMULIERT und OFFEN sind in der Akte ausdrücklich
getrennt. Es wurden keine produktiven Runtime-/Packagingänderungen vorgenommen.
