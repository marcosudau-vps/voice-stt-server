# Nachtrag vor Umsetzung: minimaler Native-Shutdown-Fix

2026-10-27. Reeller Linux-Lauf mit verifiziertem historischen Nativeinput
36b440630c0a9475: Community ohne Key PASS; Pro-Key aktiviert das reale Modell
und transkribiert korrekt, danach bleibt der Prozess haengen. Nach 653.70 s
wurde der haengende Pro-Child gezielt beendet und die Suite unterbrochen:
1 PASS, 1 FAILED (erzwungene Beendigung), weitere Szenarien NOT_RUN.
Die RESULT-Zeile belegt erfolgreiche native Aktivierung und Transkription,
aber keinen erfolgreichen Shutdown. Windows: alle vier Szenarien PASS.

Im gepinnten license.h startet BanafoLicense einen LicenseClient.call()-Thread.
call() besitzt eine Endlosschleife; der Destruktor joint ohne Stopanforderung.
Das erklaert das reproduzierte Linux-Pro-Prozessendeproblem.

Technisch notwendige, eng begrenzte Abweichung vom Ziel unveraenderter
Nativepatches: Stopflag plus Stop des vorhandenen Asio-Loops vor join,
keine Native-Statusschnittstelle, kein Supervisor, IPC, Ownerprozess oder
Prozessgeneration. Derselbe bestehende Singleton und alle Python-Key-/Modell-
Guards bleiben erhalten. Upstream/Toolchainpins bleiben gleich. PATCH_SET_REVISION
muss 4 -> 5 steigen, Quellhashguard und Fingerprinterwartungen folgen. Alte
Nativeartefakte duerfen nicht als Patch-5-Artefakte umetikettiert werden.
Erforderlich: idempotenter Patchtest, vollstaendige Suite, echte Neubuilds und
Linux-/Windows-Nativetests mit den neu erzeugten Bytes. Ohne diese Pflichtbelege
bleibt das technische Ergebnis BLOCKED.
