# Abschließende Abweichungen

2026-10-27. Ergänzung zu den erhaltenen Zwischenakten.

| Abweichung | Grund und Auswirkung | Entscheidung / Status |
| --- | --- | --- |
| Nativepatches wurden geändert | Realer Linux-Pro-Prozess blieb nach korrekter Inferenz hängen; gepinnter Reporter lief endlos und wurde ohne Stop gejoint. | Enger eigener Stop-vor-join-Fix, Patch-Set 5 und neue Fingerprints. Linux neu gebaut und real sowohl aus Source als auch Produktwheel geprüft. Keine PR-14-Architektur. |
| Neue Windowsartefakte fehlen | Unveränderter Snapshot `snapshot.ubuntu.com/ubuntu/20260825T000000Z` liefert in zwei Buildversuchen HTTP 503 für noble/noble-updates/noble-security. | Keine Ersatzquelle/-toolchain und keine als neu umetikettierten Altbytes. Neuer Native-/Produkt-/NOTICE-/Installationsnachweis extern blockiert. |
| Vollständiger RC fehlt | Windows-Pflichtartefakt fehlt; keine reale Staging-Promotion/Registry-Pushes durchgeführt. | Schema-/Hash-/Resume-/Promotionregressionen PASS; kein erfundenes Manifest und keine simulierten Bytes als reale Qualifikation. |
| Öffentliche Freigabe bleibt gesperrt | Source-Lizenzen belegen nicht sämtliche Pro-Produkt-/Binaryrechte oder alle abschließenden Windows-Redistributionspflichten. | source-kontrollierter Status BLOCKED, vor realen Writes wirksam; unabhängige Vertragsprüfung erforderlich. |
| CI-Prerequisites erweitert | Neu in reguläre CI aufgenommene Packagingtests brauchen wheel und vollständige historische Gitobjekte. | Hostwerkzeug und fetch-depth 0 ergänzt, keine Änderung der Native-Toolchainpins. Finaler CI-Nachweis am PR-HEAD wird extern verknüpft. |

Native-Neubuilds wurden nicht durch eine reine Produktumbenennung erzwungen.
Der erste Linuxlauf auf alten Inputs wurde für den nachgewiesenen technischen
Fix beendet. Ein zwischenzeitlicher Produktbuild wurde bei geänderter
Sourceidentität korrekt abgewiesen; danach wurde der saubere Stand `ed58ac0`
erfolgreich mit bereits verifiziertem Patch-5-Cache gebaut und qualifiziert.

Der [Abschlussvergleich](2026-10-27_ABSCHLUSS_SOLL_IST.md) führt exakte Hashes,
Commits, Tests und offene Gates. Implementierung ist eingereicht, Gesamtstatus
BLOCKED bis die technischen Pflichtnachweise und externen Freigaben vorliegen.
