# AP-SRV-070 W5-R04 — Abweichungen

Datum: 08.09.2026
Run: W5-R04

Materielle Abweichungen von der Planung
[`2026-09-08_W5_R04_PLAN.md`](2026-09-08_W5_R04_PLAN.md) beziehungsweise vom
ursprünglichen Auftrag. Je Abweichung: Grund, Auswirkung, bewusste Entscheidung
und Status.

---

## A1 — Kein sdist für die beiden öffentlichen Distributionen

**Abweichung.** Der ursprüngliche Auftrag verlangte Wheel **und** sdist als
Kandidatenartefakte. Es wird kein sdist für `voice-stt-server` und
`voice-stt-server-pro` erzeugt oder veröffentlicht.

**Grund.** Das definierende Merkmal dieser Distributionen ist, dass sie eine
qualifizierte native Kroko-Laufzeit *enthalten*. Ein sdist ist Quellcode und
kann diese Laufzeit nicht transportieren. Überall, wo pip ein sdist bevorzugen
würde, hätte die Installation entweder einen lokalen nativen Kroko-Build
(~30 Minuten) ausgelöst oder still eine Installation ganz ohne Kroko-Laufzeit
erzeugt. Beides bricht genau die Garantie, für die es diese Distributionen
gibt.

**Auswirkung.** Für jede dokumentierte Plattform wird ein Wheel veröffentlicht,
sodass pip auf einer unterstützten Plattform nie ein sdist benötigt. Auf einer
nicht unterstützten Plattform schlägt die Installation laut fehl, statt still
etwas Unvollständiges zu erzeugen. Das RC-Manifest (Schema v2) bindet keine
sdist-Identität mehr; Release-Engine und Tests wurden entsprechend angepasst.

**Entscheidung.** Bewusst, gedeckt durch Abschnitt 9 der neueren verbindlichen
Autorität, die die alte Vorgabe ausdrücklich zur Neubewertung stellt.

**Status.** Umgesetzt und in [`docs/release-process.md`](../../../release-process.md)
technisch begründet.

---

## A2 — Zwei Distributionen statt einer

**Abweichung.** Der ursprüngliche Auftrag ging von einem PyPI-Projekt aus. Es
sind zwei geworden.

**Grund.** Neue verbindliche Produkt-/Packaging-Autorität: Free- und
Pro-Kroko sind technisch unterschiedliche, nicht gegeneinander austauschbare
native Laufzeiten.

**Auswirkung.** RC-Manifest, Release-State, PyPI-Adapter, Preflight, Workflows
und die gesamte Dokumentation behandeln durchgängig beide Distributionen.
`PYPI_PUBLISHED` bedeutet ausdrücklich „beide verifiziert veröffentlicht“.
Trusted Publishing benötigt zwei Publisher.

**Entscheidung.** Bewusst, weil die neuere Autorität dem ursprünglichen Prompt
vorgeht.

**Status.** Umgesetzt.

---

## A3 — `toolchain_identity("linux")` wurde nicht umgebaut

**Abweichung.** Die Planung sah vor, `fingerprint.toolchain_identity("linux")`
analog zur Windows-Seite auf eine deklarierte Toolchain-Autorität umzustellen.
Das ist nicht geschehen.

**Grund.** Die Bestandsaufnahme dieses Runs hat gezeigt, dass die Annahme hinter
dem Planpunkt unvollständig war: `toolchain_identity("linux")` liefert zwar
`{"kind": "host-native"}`, aber `install_kroko.fingerprint_for` übergibt auf
Linux eine **real probierte** Toolchain-Identität (echte `cmake`/`cc`/`c++`-
und OpenSSL-Identität aus dem Buildcontainer). Der Linux-Fingerprint war also
nie blind. Eine zusätzliche deklarierte Toolchain hätte die probierte Identität
ohnehin nicht überschrieben und wäre wirkungslos geblieben.

**Auswirkung.** Das reale Problem war nicht Korrektheit, sondern Stabilität: ein
bewegliches Basis-Image ließ den Fingerprint aus nicht deklarierten Gründen
driften und machte Artefakt-Wiederverwendung auf einem frischen Runner
wertlos. Umgesetzt wurde deshalb die Deklaration des Containers selbst
(`linux_builder_declaration()`), das Pinnen von Basis-Image-Digest und
Packaging-Werkzeugen, ein Guard-Test über Deklaration **und** Dockerfile sowie
die Erhöhung von `LINUX_BUILDER_REVISION` 1 → 2. Die
Windows-Autorität bleibt unberührt (`WINDOWS_BUILDER_REVISION` = 4), das bereits
qualifizierte Windows-Artefakt wird nicht entwertet.

**Entscheidung.** Bewusst; die kleinere, wirksame Korrektur wurde der geplanten,
wirkungslosen vorgezogen.

**Status.** Umgesetzt. Verbleibende Grenze (nicht gepinnte Debian-Paket-
Punktversionen) ist in `buildinputs.py` und `docs/release-process.md`
ausdrücklich dokumentiert.

---

## A4 — `huggingface_hub` aus dem Kroko-Builder-Image entfernt

**Abweichung.** Nicht geplant.

**Grund.** Das Image installierte `huggingface_hub` ungepinnt. Eine Prüfung
aller in das Image kopierten Dateien (`VERSION`, `VoiceSTT/__init__.py`,
`VoiceSTT/_version.py`, `VoiceSTT/install_kroko.py`, `VoiceSTT/kroko/`) hat
ergeben, dass keine davon es importiert. Es war ein ungepinnter Netzwerk-Eingang
ohne Funktion.

**Auswirkung.** Der Builder ist kleiner und hat einen unkontrollierten Eingang
weniger. Die Modell-Downloadhilfe bleibt unverändert als Extra
`kroko-builder` der Entwicklungsdistribution verfügbar.

**Entscheidung.** Bewusst; Teil der von Abschnitt 12 verlangten Prüfung des
Linux-Builders auf veränderliche/nicht deklarierte Build-Eingänge.

**Status.** Umgesetzt und über die Container-Deklaration guard-getestet.

---

## A5 — `--dist-dir` außerhalb des Buildkontexts wird abgelehnt

**Abweichung.** Nicht geplant; beim Nachweis mit leerem Artefaktspeicher
entdeckt.

**Grund.** Das Produktions-Dockerfile kopiert die bereitgestellten Wheels mit
literalen `COPY dist/...`-Anweisungen relativ zum Buildkontext
(Repository-Wurzel). Ein `--dist-dir` außerhalb davon kann grundsätzlich nicht
funktionieren. Vorher lief zuerst ein vollständiger nativer Kroko-Build
(~25 Minuten) und scheiterte erst danach mit
`lstat /dist/voicestt: no such file or directory`.

**Auswirkung.** Die Option scheitert jetzt sofort und mit einer erklärenden
Meldung. Der teure Build wird nicht mehr sinnlos ausgeführt.

**Entscheidung.** Bewusst; kleinste korrekte Korrektur, ohne den
W4C-Build-Vertrag zu ändern.

**Status.** Umgesetzt und guard-getestet.

---

## A6 — Registry-Identität ist der Manifest-Digest

**Abweichung.** Korrektur eines bestehenden Fehlers, nicht geplant.

**Grund.** `remote_checks.check_registry_image` verglich den entfernten
Manifest-Digest mit der **lokalen** Docker-Image-`Id`. Das sind
unterschiedliche Werte (lokaler Config-Blob-Digest gegenüber entferntem
Manifest-Digest) und können nie übereinstimmen; jede echte Registry-Prüfung
hätte einen unechten `CONFLICT` gemeldet. Das RC-Manifest enthielt überdies gar
kein Digest-Feld.

**Auswirkung.** Das Manifest (Schema v2) bindet jetzt
`images.<variante>.digest`. Die Prüfung vergleicht Manifest-Digest gegen
Manifest-Digest — genau die Identität, die
`docker buildx imagetools create` zwischen Registries überträgt. Alias-Tags
werden bewusst anders behandelt: ein Alias, der woanders hinzeigt, ist kein
Konflikt, sondern schlicht noch nicht gesetzt.

**Entscheidung.** Bewusst; ohne diese Korrektur wäre die geforderte
Digest-Promotion nicht verifizierbar gewesen.

**Status.** Umgesetzt und guard-getestet.

---

## A7 — Redaktion in `remote_checks`

**Abweichung.** Nicht geplant; durch einen eigenen neuen Test entdeckt.

**Grund.** `remote_manifest_digest` löste `VerificationUnavailableError` mit
**unredigiertem** stderr aus. Registry-stderr kann ein Zugangsdatum zurückgeben
(ein abgelehnter `docker login` tut genau das), und diese Meldung landet in
Workflow-Logs und Evidenzdateien.

**Auswirkung.** Die Meldung wird jetzt an der Grenze redigiert, statt sich
darauf zu verlassen, dass jeder Aufrufer daran denkt.

**Entscheidung.** Bewusst; Gate W5R4-G49 verlangt, dass Secrets nicht in Logs
oder Artefakte gelangen.

**Status.** Umgesetzt und guard-getestet.
