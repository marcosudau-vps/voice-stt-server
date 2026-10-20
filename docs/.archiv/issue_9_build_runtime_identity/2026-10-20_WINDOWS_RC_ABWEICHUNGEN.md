# Issue #9: Windows-RC-Nachtrag, Abweichungen

Ergaenzt die [Nachtragsplanung](2026-10-20_WINDOWS_RC_PLAN.md) und den
[neuen Soll-/Ist-Bericht](2026-10-20_WINDOWS_RC_UMSETZUNGSVERGLEICH.md).
Historische A-/B-Berichte werden nicht umgeschrieben.

## W1: Hostfehler korrigiert, neues Inputproblem sichtbar

Der bisher fehlende Linux-Containerhost war kein prinzipiell fehlender
Windows-Qualifikationshost: V1 baute Windows-Ziele bereits auf Ubuntu
und installierte sie erst danach auf Windows. V2 uebernimmt dieses
Muster im Commit `c0e552e9837651f8fce9ea5518401349e19371f2`.
Der erneute passende
[RC 39353183125](https://github.com/marcosudau-vps/voice-stt-server/actions/runs/39353183125)
erreicht im Ubuntu-Cross-Build den echten gepinnten V2-Containeraufbau.
Er scheitert nicht mehr am Windows-Dockerflag.

Der neue Fehler ist unabhaengig: Der deklarierte Channel-Manifestpin
verweist auf `https://aka.ms/vs/17/release/channel`. Die Alias-URL liefert
mittlerweile Visual Studio 17.14.42 statt der eingefrorenen
17.14.39-Ausgabe. Die Groessenpruefung in Dockerfile.windows:128
bricht vor der nachfolgenden SHA-Pruefung ab. CMake und xwin wurden im
Job zuvor erfolgreich anhand ihrer unveraenderten Digests geprueft.
Windows-Kompilation, Artefakttransfer und native Installationsgates wurden
noch nicht erreicht.

Zusaetzliche rein lesende Downloads am 20.10.2026:

| Ressource | Tatsaechliche Bytes / SHA-256 |
| --- | --- |
| Deklarierter Channelpin | 91833 / `4c81e902fb7fe2acea779b828e6dc548fe0bbb693df50eda0224263c16686bdd` |
| Aktuell ueber Alias geliefert | 91688 / `4f0f290bb4d58a061a49a2fa893357a8c9e7e2b49fc91873f533ab8f791e4fa0` |
| Separat gepinntes Microsoft-Paketmanifest | 17955171 / `3891c3018a07338b3880cbb28088bb22ef7762eb9206523655b2e3972b9d527e`; bytegenau passend und weiterhin erreichbar |

Der aktuelle Alias leitet auf eine andere .chman-CDN-Ressource um.
Das unveraenderte Paketmanifest beschreibt weiterhin
`17.14.39+37614.0.-august.2026-`. Ein blosses Aktualisieren des
Channelhashes waere keine Wiederherstellung desselben Inputs.

## W2: Historische Bytes gefunden, keine neue Beschaffungsautoritaet

Die begrenzte rein lesende Suche fand eine bytegenaue historische Kopie:
[roblabla/msvc-manifest-history, raw_channel.json auf 77f6f8ee89705a855ff14c6305ca8ebc9a2a861f](https://github.com/roblabla/msvc-manifest-history/blob/77f6f8ee89705a855ff14c6305ca8ebc9a2a861f/raw_channel.json).
Diese heruntergeladene Datei ist **91833 Bytes** lang und hat exakt den
bereits in V2 deklarierten SHA-256
`4c81e902fb7fe2acea779b828e6dc548fe0bbb693df50eda0224263c16686bdd`.
Sie beschreibt dieselbe 17.14.39-Ausgabe. Benachbarte August-/September-
Snapshots wurden geprueft und stimmen nicht ueberein.

Das ist ein konkreter Wiederbeschaffungshinweis, **kein** bereits
implementierter oder ausgefuehrter Builderpfad. Die Kopie wurde nur
ausserhalb des Repositories heruntergeladen, nicht committed, ausgefuehrt,
in den Compilercontainer injiziert oder als neues Vertrauenssubstitut
verwendet. Kein historisches Nativewheel wurde unter einem neuen
Fingerprint umetikettiert.

Eine dauerhafte Wiederherstellung der exakten Manifestbytes benoetigt
eine explizite Entscheidung ueber deren Bereitstellung/Locator:
vorzugsweise nachvollziehbare unveraenderliche Originalquelle, ansonsten
bewusst festgelegte Vorhaltung derselben hashgeprueften Bytes. Eine neue
Mirrorabhaengigkeit, Dockerfile-Umschreibung ausserhalb der deklarierten
Patchhelfer oder ein Pin-/Fingerprintupdate wurde nicht ungefragt
hinzugefuegt. Die neue materielle Grenze wurde gemeldet; weitere
Implementierung dazu bleibt ausserhalb dieses gezielten Hostfixes.

## W3: Tatsaechlicher Status, keine gruene Ersetzung

Die lokalen betroffenen Regressionen und der neue immutable Client-
Loopbacklauf sind bestanden. Im echten RC ist der Linuxjob erfolgreich,
der neue Windows-Buildjob FAIL und die nachgelagerten Windows-/Vier-Wheel-
Gates NOT_RUN. Die Windowsqualifikation bleibt **NOT_PROVEN**.
Nach Wiederherstellung des Inputs koennen weitere Build-/ABI-Risiken
erstmals geprueft werden; sie sind nicht vorab als bestanden auszuweisen.

Kein weiterer gleichartiger RC auf ungeeigneter Windows-Dockerengine;
kein Retry ohne veraenderten Erkenntnisstand; keine Abschwaechung von
Laengen-, SHA-, Varianten-, Tag-, Fingerprint- oder Quellpruefungen.
Bestehende V2-Toolchain, Fingerprints und Release-/Promotion-/Resumevertraege
bleiben unveraendert. Kein Merge, Release, Git-Tagging oder Deployment.
