# Issue #9: bytegleiche Windows-Manifest-Wiederbeschaffung

Datum: 2026-10-20. Planung vor Implementierung auf
`d4d4e2f2b1eb87d1a97ae4bb41b7888e5e62d44b`.

## Auftrag, Ausgangslage und bewusste Grenze

Die autonome Fortsetzung soll den echten Windows-/Vier-Wheel-Nachweis
nicht beim ersten andersartigen Fehler aufgeben. Der passende Ubuntu-
Crossbuild stoppt am Groessenguard fuer die rollierende Microsoft-
Channel-URL. Die bereits unabhaengig verifizierte historische Kopie auf
einem vollstaendigen Gitcommit hat genau dieselben 91833 Bytes und
denselben vorher deklarierten SHA-256. Kein Toolchainversionswechsel.

**Materielle Abweichung vom vorherigen Hostfix:** Die URL ist selbst ein
Fingerprintinput. Unveraenderte Fingerprintwerte UND eine andere
deklarierte Bezugsquelle sind daher nicht gleichzeitig ehrlich moeglich.
Dieser Konflikt und die neue Mirrorabhaengigkeit wurden vor Erweiterung
gemeldet; bei nicht erreichbarem Benutzer lautet die Fortsetzung, autonom
weiterzuarbeiten. Gewaehlt wird die strengere Provenienz: neue korrekt
berechnete Windowsidentitaeten statt eine ausserhalb der Authority
versteckte Dockerfile-/Netzwerkumleitung. Die alten Fingerprints/Artefakte
bleiben unveraendert ihren alten Inputs zugeordnet.

## Umsetzung und Nicht-Ziele

1. Nur WINDOWS_XWIN_MANIFEST_URL auf die commitgebundene
   raw_channel.json-Kopie umstellen. Der bisherige SHA-256 und die
   Groesse bleiben unveraendert, ebenso Paketmanifest, SDK, CRT, Compiler,
   OpenSSL, Python, Packagingtools, Nativequellen und Buildflags.
2. Der vorhandene Patchhelfer erzeugt den Download und dieselben
   Groessen-/SHA-Gates. Kein Fallback, kein neuer Downloadhelfer, kein
   Umgehen oder Abschwaechen eines Guards. Builder- und Patchrevision
   bleiben unveraendert, weil keine Builder-/Patchfunktion geaendert wird;
   die explizite URL aendert bereits die Windows-Toolchainauthority.
3. Bestehende Goldenwerte/URL-Erwartungen anpassen. Zusaetzlich beweisen,
   dass Ruecksetzen genau dieser URL die alten Windowsfingerprints
   vollstaendig wiederherstellt und die Linuxauthority unveraendert ist.
   Bytegleichheit unabhaengig anhand des vorbestehenden Digests pruefen.
4. Betroffene Regressionen ausfuehren; danach committen/pushen und genau
   diesen sauberen Ref im bestehenden RC qualifizieren. Keine neuen
   Release-/Promotions-/Resumeschemas, kein neuer PR oder Buildhost.
5. Tatsaechliche Linux-/Windows-/Assemblyresultate, Inputs/Hashes,
   fehlende Nachweise und Abweichung in getrennten datierten Nachtraegen
   dokumentieren; historische Berichte nicht umschreiben.

Kein Merge, Release, Git-Tagging oder Deployment. Keine Aenderung an
Produktiv-/Client-Testservern oder historischem Clientproduktcode.

## Abnahme und Risiken

- Bestehende Patch-/Builder-Digestguards unveraendert gruen.
- Neues Windows-Fingerprintdokument unterscheidet sich ausschliesslich
  in deklarierter URL und daraus abgeleiteter Toolchainauthority.
- Alte SHA-/Groessen-Gates bleiben zwingend vor xwin; falsche Bytes
  werden auch von der neuen Quelle nicht akzeptiert.
- Echte Free-/Pro-Windowswheels auf Linux bauen, auf Windows nativ
  installieren und qualifizieren, mit gemeinsamen vier Wheels abgleichen.
  Erst reale Resultate zaehlen; weitere Fehler bleiben ausdruecklich rot.
- Communityarchiv ist eine neue Verfuegbarkeitsabhaengigkeit, keine neue
  Inhaltsautoritaet: akzeptiert werden nur die schon zuvor gepinnten
  Microsoftbytes. Gitcommit und Hash verhindern stillen Inhaltswechsel.
  Ausfall bricht weiterhin laut ab.

Dauerhafte Buildauthority bleibt [build/BUILD.md](../../../build/BUILD.md).
