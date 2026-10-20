# Issue #9: echter Image-Endpunktnachweis

Datum: 2026-10-20. Vor Umsetzung auf
`50e980f7af8051b4b1b2ad482e45f162ccb7f385` registriert.

## Ausgangslage und Ziel

Die bestehende echte Dockerpruefung vergleicht OCI-Labels und installierte
Metadaten; die HTTP-/Refusalchecks laufen nur in den installierten
Produktwheels. Der urspruengliche A+B-Auftrag verlangt zusaetzlich echte
Image-Endpunkte. Das ist weiterhin ein offener Nachweis, kein neuer
Produkt-/Deploymentauftrag.

## Gezielte Umsetzung

1. Den vorhandenen selbstenthaltenen INSTALLED_CHECK in
   tools/qualify_build_identity.py von In-Process-TestClient auf einen
   kurzlebigen echten Uvicorn-Loopbackserver, HTTP und WebSocket umstellen.
   Gleiche positiven/negativen Identitaetsassertionen; gebundener
   Ephemeralport, begrenzte Wartezeiten und Cleanup auch bei Fehler.
2. Fuer generische Images die installierte BuildIdentity weiterhin als
   voicestt mit krokoVariant=null behandeln. Die separate native Variante
   explizit als zweiten Parameter pruefen; keine falsche Gleichsetzung von
   Paket-, Native- und Imageidentitaet.
3. validate_image_identity fuehrt nach dem bisherigen Label-/Metadatencheck
   genau denselben Probe in einem frischen --rm/--network none Container
   als bestehender unprivilegierter Imagebenutzer aus. Keine Ports,
   Hostverzeichnisse oder Modelle bereitstellen; Listener nur im
   containerinternen Loopback, Modelle offline, ready=false erwartet.
4. Der Probe muss einen gebundenen Erfolgsbeleg liefern. Fehlender,
   falscher oder nativer Fehlbeleg darf keinen Build-/Stagingerfolg
   erzeugen. Bestehende Release-/Manifest-/Promotionsregeln unveraendert.
5. Lokale echte HTTP-/WS-Probelogik mit klar deklarierten ASGI-/Native-
   Fixtures und Fehler-/Cleanupsfaellen testen; Dockeraufruf/Belegvalidierung
   separat pruefen. Danach vorhandene gezielte Regressionen und einen
   echten sauberen RC mit beiden Images/public Wheelplattformen ausfuehren.

## Grenzen und Nachweise

Kein Produktcode-/Protokollwechsel, keine Modelle/Geraete oder
Transkriptionsqualifikation aus der Endpointpruefung ableiten. Der reale
Imageprobe verwendet unveraenderten Servercode ohne ASGI-/Native-Fixtures;
fehlende Modelle sind die beabsichtigte NOT_READY-Konfiguration.
Kein produktiver/shared Dockerzugriff, Release, Tagging, Deployment oder
Merge. Historische Berichte bleiben erhalten; neue Soll-/Ist- und
Abweichungsnachtraege dokumentieren ausschliesslich echte Ergebnisse.
