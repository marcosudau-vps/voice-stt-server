# Issue #9: autonome Fortsetzung, materielle Abweichungen

Diese neue Akte ergaenzt die historischen A-/B-/Windows-RC-Berichte und die
vor Umsetzung registrierten
[Locatorplanung](2026-10-20_MANIFEST_LOCATOR_PLAN.md) sowie
[Image-Endpunktplanung](2026-10-20_IMAGE_ENDPOINT_PLAN.md).
Fruehere rote/laeufige/nicht ausgefuehrte Nachweise werden nicht umgedeutet.

## F1: konkrete Windows-Fingerprints aendern sich durch den Locator

Die urspruengliche Hostkorrektur auf c0e552e liess die konkreten
Windowsfingerprints vollstaendig unveraendert. Ihr echter RC scheiterte
anschliessend am rollierenden Microsoft-Channel-Locator. Die erwarteten
historischen Bytes waren nicht verloren: Die commitgebundene oeffentliche
Archivkopie wurde unabhaengig frisch heruntergeladen und bytegenau
gegen den **bereits bestehenden** Pin geprueft.

Die autonome Fortsetzung aendert auf
`50e980f7af8051b4b1b2ad482e45f162ccb7f385` ausschliesslich
WINDOWS_XWIN_MANIFEST_URL:

| Eingang | Vorher | Nachher |
| --- | --- | --- |
| Channel-Locator | rollierendes aka.ms/vs/17/release/channel | raw.githubusercontent.com/roblabla/msvc-manifest-history/77f6f8ee89705a855ff14c6305ca8ebc9a2a861f/raw_channel.json |
| Laenge | 91833 | unveraendert 91833 |
| SHA-256 | `4c81e902fb7fe2acea779b828e6dc548fe0bbb693df50eda0224263c16686bdd` | unveraendert |
| Visual Studio | 17.14.39, August 2026 | unveraendert |
| Windows-Free-Fingerprint | `28594e6d201fc4a7` | `b28bc64f9ce3e8e0` |
| Windows-Pro-Fingerprint | `08cb569da5feda2e` | `26d5afecf0f5cc17` |
| Windows-Toolchainauthority | `63224eaaaa84424e` | `103518aa86b90a20` |

Das ist eine ausdrueckliche Abweichung von unveraenderten konkreten
Windowswerten, nicht ein angeblich identischer Fingerprint. Die URL ist
selbst Teil der bestehenden Authority. Eine andere deklarierte Quelle
unter den alten Werten zu verbergen waere falsche Provenienz. Der
vorhandene Algorithmus leitet deshalb neue IDs ab, ohne alte Records zu
aendern oder einer neuen Buildkonfiguration zuzuordnen.

Konflikt und Mirrorabhaengigkeit wurden vor der Scopeerweiterung gemeldet.
Bei nicht verfuegbarem Benutzer lautete die Fortsetzung, autonom
weiterzuarbeiten. Bewusste Entscheidung: gleiche Inhaltsbytes und
transparente neue Authority statt stiller Dockerfile-/Proxyumleitung,
gefaelschter alter IDs oder eines VS-/SDK-/CRT-Updates.

Die Regression setzt allein die URL zurueck und rekonstruiert fuer Free
und Pro exakt beide alten IDs samt vollstaendigem Inputdokument. Die
Linuxidentitaet bleibt unveraendert. Builder- und Patchfunktionen, deren
Revisionen und alle bisherigen Source-Digestguards sind unveraendert;
es wurde kein Guardwert angepasst oder entfernt. Auch Paketmanifest,
SDK/CRT, Compiler, OpenSSL, Python und Packagingtools sind unveraendert.

Die Communitykopie ist eine neue **Verfuegbarkeitsabhaengigkeit**, keine
neue Inhaltsautoritaet. Weder Gitcommit noch HTTPS ersetzen den
vorbestehenden Inhaltspin: Vor xwin muessen weiterhin Groesse und SHA-256
passen. Ausfall oder andere Bytes erzeugen einen Fehler, keinen Fallback.
Es wird keine Microsoft-Signatur oder neue Authentizitaetsgarantie behauptet.

## F2: echter Transport statt ausschliesslicher ASGI-In-Process-Pruefung

Auf `104b73f9bd845d584a22d17db71af453e1f7c97e` wird der vorhandene
native Installationsprobe auf echten begrenzten HTTP-/WebSocket-Transport
umgestellt und nach dem bisherigen Metadatencheck auch im generischen
Image ausgefuehrt. Das schliesst einen schon urspruenglich offenen
A+B-Nachweis; kein neuer Endpunkt, Produktcode oder Protokollwechsel.

Gleiche Identitaetsassertionen und staerkere Status-/Herkunftsabgleiche;
keine Ersetzung des vorherigen OCI-/Metadatenchecks. Ein frischer
unprivilegierter --network-none-Container benoetigt nur eigenes Loopback,
keine Hostports, Hostverzeichnisse oder Modelle. HTTP-Proxys werden
ignoriert; WebSockets verwenden einen expliziten Loopbacksocket.
Fehler und erfolgreicher Abschluss stoppen den Server nachweislich.

Die generische Paketressource bleibt voicestt/krokoVariant=null. Die
separat installierte native Free-/Pro-Variante wird ausdruecklich geprueft,
nicht nachtraeglich in die Paketressource hineingeschrieben.
Mehrdeutige/fehlende/ungueltige Erfolgsmarker und native/HTTP-/WS-
Identitaetskonflikte duerfen keinen erfolgreichen Build-/Stagingbeleg
erzeugen. Markerformat und bestehende RC-/Publikationsschemas bleiben
unveraendert.

## F3: echte Endpunkte decken eine zeitabhaengige Probeannahme auf

Der erste echte Endpoint-RC auf 104b73f,
[39358314020](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39358314020),
ist FAIL. Der Windows-Crossbuild verwendet beide verifizierten neuen
Nativecaches erfolgreich; der echte Windows-Fullinstall und das erste
generische Linuximage bestehen Nativeimport/Info/Settings/OpenAPI,
scheitern aber an der neuen Annahme ready=false nach normalem Startup.
Kein roter Lauf wird als erfolgreicher Endpunktbeleg gewertet.

Konkrete Ursache: Der unveraenderte _ready_worker setzt das vorhandene
ready-Event auch nach abgeschlossener fehlgeschlagener Modellinitialisierung.
Gesunde Modellverfuegbarkeit ist separat sttReady/ok. Der fruehere
In-Process-Aufruf konnte das Event vor Abschluss des Workers beobachten;
eine sofortige False-Annahme war zeitabhaengig. Die neue deterministische
Regression reproduziert das mit echtem Transport auf allen vier
generischen/public-Varianten: Initialisierung abgeschlossen, Modelle
nicht bereit. Vier erwartete REDs vor der Probekorrektur.

Bewusste Entscheidung: kein unbestellter Umbau der Produkt-/Health- oder
Verbindungssemantik und kein Entfernen des Vor-Ready-Nachweises.
Ein erster echter Loopbackserver mit explizit ausgeschaltetem Lifespan
prueft Info bei ready=false vor jeglichem Modellstart; danach startet
derselbe unveraenderte Appzustand mit normalem Lifespan. Identitaet muss
gleich bleiben, Modellstatus sttReady=false und ok=false sein, und
Settings/OpenAPI/WS-Refusal muessen bestehen. Beide Server werden auch
bei Assertionfehler beendet. Der Erfolg beweist damit sowohl kalte
Identitaet als auch den normalen modelllosen Control-Plane-Betrieb.
Diese Korrektur ist auf d99633a95166d168c2adb8c0fd015f435ff5ec23
veroeffentlicht. Der
[abschliessende echte RC](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39359464011)
besteht alle vier Jobs einschliesslich beider realer Image-Endpunktproben
und aller vier nativen Produktinstallationen. Die
[gewoehnliche CI](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39359470290)
ist auf beiden Plattformen gruen. Kein offener technischer
Readiness- oder Windows-RC-Blocker wird daraus weitergefuehrt;
die materielle Locatorabweichung und ihre Nachweisgrenzen bleiben bestehen.

## F4: verbleibende sachliche Nachweisgrenzen

Lokale Probetests verwenden deklarierte ASGI-/Native-Fixtures, echten
Transport und Fehler-/Cleanupfaelle. Sie sind kein echter Docker- oder
Nativeimportbeleg. Die echten Kandidatengates verwenden dagegen den
unveraenderten installierten Server und echte native Imports.

Ohne bereitgestellte Modelle bleibt sttReady=false beabsichtigt; ready
wird getrennt vor dem Lifespanstart geprueft. Daraus
folgen keine Realmodell-, Transkriptions-, Mikrofon-/Audiohardware-, GUI-,
TLS-/Proxy- oder VPS-Nachweise. Ebenso wird aus Cache-Reuse oder einem
Build keine native/Image-Byte-Reproduzierbarkeit abgeleitet. Diese
Grenzen bleiben ausdruecklich NOT_RUN beziehungsweise NOT_PROVEN.

Kein Zugriff auf produktive Container, gemeinsamen lokalen Dockerdaemon
oder bestehenden Client-Testserver. Private Kandidatenstagingwrites
bleiben Teil des vorhandenen RC-Vertrags. Kein oeffentlicher Release,
Git-Tagging, Deployment, Merge oder automatische Gesamtfreigabe.
