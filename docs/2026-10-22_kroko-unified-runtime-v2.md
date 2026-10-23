# Unified Kroko Runtime V2 – aktueller Untersuchungsstand

Stand 22.10.2026: AP-KR-010 ist für den vereinbarten Untersuchungsumfang
[abgenommen](https://github.com/marcosudau-vps/voice-stt-server/pull/11#issuecomment-6346283640).
AP-KR-020 wurde auf Integrationscommit `acdffc7` begonnen. Die produktive Installation bleibt unter
[build/BUILD.md](../build/BUILD.md) beschrieben. Das geplante Extra `kroko_pro`
und eine separate Pro-Komponente sind noch kein verfügbares Produkt.

Die echten qualifizierten Nativepayloads lassen sich auf Windows AMD64 und
Linux AMD64 (lokal WSL), jeweils CPython 3.12, in getrennten privaten
Verzeichnissen bereitstellen und in frischen Prozessen auswählen. Community
läuft auch unter der Pro-Runtime ohne Key. Das belegt keine gültige Prolizenz.
Native Fehler können den Besitzerprozess beenden; empfohlen ist deshalb
vollständiger Prozesswechsel mit kontrolliertem Communityfallback.

AP-010s **CONDITIONAL GO** ist als konditionale Architekturgrundlage akzeptiert;
auch eine kurze Dienstunterbrechung beim Prozesswechsel ist freigegeben.
AP-KR-020 ist wegen des in Arbeitsschritt A nicht belastbar geschlossenen
[Lizenzvalidierungsvertrags](.archiv/kroko_unified_runtime_v2/AP-KR-020/2026-10-22_SCHNITTSTELLEN_LIFECYCLE.md)
**BLOCKED**. Eine unabhängige Realtime-Testkorrektur ist implementiert;
Runtime-/Settings-/Modellintegration sind noch nicht umgesetzt. Autorisierte
echte Lizenztests fehlen ebenfalls und werden nicht durch Mocks ersetzt.
Bei Packaging
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
- [AP-KR-020: Planung](.archiv/kroko_unified_runtime_v2/AP-KR-020/2026-10-22_IMPLEMENTIERUNGSPLAN.md)
- [AP-KR-020: Soll/Ist und Blocker](.archiv/kroko_unified_runtime_v2/AP-KR-020/2026-10-22_SOLL_IST.md)
- [AP-KR-020: neue Tests und Nachweisgrenzen](.archiv/kroko_unified_runtime_v2/AP-KR-020/2026-10-22_TEST_EVIDENZ.md)
- [AP-KR-020: Abweichungen](.archiv/kroko_unified_runtime_v2/AP-KR-020/2026-10-22_ABWEICHUNGEN.md)
- [AP-KR-020: Übergabegrenze zu AP-030](.archiv/kroko_unified_runtime_v2/AP-KR-020/2026-10-22_UEBERGABE_AP030.md)

## Nachtrag 23.10.2026 (Fortsetzung AP-KR-020, CONDITIONAL)

Lizenzentscheidung für Variante C mit spezifiziertem nativen Folgeauftrag A
und verworfener Python-Protokollimplementierung, dazu implementiert: flüchtige
Lizenz-/Runtimeautorität, kalter Bootstrap, Besitzerprozess-Supervisor,
`kroko_force_community`, modellrechtsscharfes Fail-closed-Gate,
Startup-Community-Fallback und redaktierte Statusprojektion – synthetisch
qualifiziert (43 neue Fälle), produktiv ohne qualifizierten Nachweisweg
fail-closed auf Community.

- [Fortsetzung Lizenzentscheidung](.archiv/kroko_unified_runtime_v2/AP-KR-020/2026-10-23_FORTSETZUNG_LIZENZENTSCHEIDUNG.md)
- [Fortsetzung Implementierung](.archiv/kroko_unified_runtime_v2/AP-KR-020/2026-10-23_FORTSETZUNG_IMPLEMENTIERUNG.md)
- [Fortsetzung Soll/Ist (CONDITIONAL)](.archiv/kroko_unified_runtime_v2/AP-KR-020/2026-10-23_FORTSETZUNG_SOLL_IST.md)
- [Fortsetzung Abweichungen](.archiv/kroko_unified_runtime_v2/AP-KR-020/2026-10-23_FORTSETZUNG_ABWEICHUNGEN.md)
- [Fortsetzung Übergabe AP-025/AP-030](.archiv/kroko_unified_runtime_v2/AP-KR-020/2026-10-23_FORTSETZUNG_UEBERGABE_AP025_AP030.md)
- [Fortsetzung Testevidenz](.archiv/kroko_unified_runtime_v2/AP-KR-020/2026-10-23_FORTSETZUNG_TEST_EVIDENZ.md)

VERIFIZIERT, CODEANALYSE, SIMULIERT und OFFEN sind in der Akte ausdrücklich
getrennt. Es wurden keine produktiven Runtime-/Packagingänderungen vorgenommen.
