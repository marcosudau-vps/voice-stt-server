# VoiceSTT 1.0.0 – finaler Release- und Publikationsplan

Stand: 26.09.2026. Dieses Dokument ist der Freigabeplan für das gemeinsame
V1-Erstrelease von Server und Client. Es ersetzt widersprechende ältere
Planannahmen. Die allgemeinen Buildbefehle stehen in [build/BUILD.md](../build/BUILD.md),
der konkrete Server-Produktvertrag in
[v1-preservation-release.md](v1-preservation-release.md). Der konkrete
Git-Historienübergang zur späteren V2-Veröffentlichung steht in
[v1-v2-history-transition.md](v1-v2-history-transition.md). Die fünf am Ende
genannten historischen Dokumente waren **Ideenquellen, keine Anweisungen**.

## Geltende Entscheidungen und Grenzen

- Eine gemeinsame Kompatibilitätsbasis **1.0.0**, aber zwei getrennte
  Repository- und Publikationsvorgänge: zuerst Server vollständig, danach
  Client. Ob spätere Versionen gekoppelt bleiben, ist nicht entschieden.
- Die gesamte öffentliche Artefaktproduktion und Publikation läuft über
  **GitHub Actions**. Lokale Windows- und isolierte Linux/VPS-Tests sind
  zusätzliche Produktabnahme, nicht die Quelle der veröffentlichten Bytes.
- Kein öffentlicher 0.9.0-Probelauf. Kein lokaler PyPI-/Registry-Push.
- Bis zu einer **separaten Release-Freigabe** sind nur Source-Commit/-Push,
  normale CI und die dabei entstehenden privaten Prüfartefakte erlaubt.
  Candidate- und Publish-Workflow werden nicht allein durch einen Push
  gestartet. Kein Tag, PyPI, finaler Registry-Tag oder GitHub Release.
- Der produktive VPS-Server bleibt unverändert. VPS-Tests laufen nur im
  isolierten Workspace mit anderen Namen und Ports. `build/vps/**` ist
  keine öffentliche Buildauthority.
- Exakt qualifizierte Artefakte werden veröffentlicht, nicht nach der
  Qualifikation neu gebaut: **build once – qualify exactly – publish exactly**.

## 1. Source-Freeze und normale CI (noch kein Release)

1. Beide Worktrees separat auf beabsichtigte Dateien, Secrets und
   generierte Artefakte prüfen. Historische Branches nicht löschen,
   überschreiben, rebasen oder force-pushen.
2. Der bereits geprüfte `release/v1.0.0-prep` ist ein Arbeitsbranch mit
   18 Commits nach der historischen V1-Main-Basis `13c1629` und darf
   **nicht** direkt nach `main` gelangen. Den abschließend geprüften
   V1-Dateibaum auf einem neuen Branch direkt von dieser Basis als
   **einen** fokussierten Clean-Commit herstellen. Vor dem Commit den
   Tree gegen den beabsichtigten Vorbereitungsstand und alle zusätzlichen
   Governance-Änderungen prüfen. Nur diesen neuen Branch pushen.
   Die Push-Trigger beider normalen CI-Workflows müssen ihn einschließen;
   diese Runs sind **keine** Candidate- oder Publish-Runs.
3. Beide Server-CI-Runs auf exakt dem neuen Clean-Commit/Tree abwarten;
   der grüne Lauf des Arbeitsbranches ersetzt sie nicht. Die
   Build-Validation muss vier native Produktwheels, zwei echte
   Windows- und zwei Linux-Clean-Installs, Free/Pro-Docker-Smokes und das
   überprüfbare Evidenzpaket liefern. Keine grüne Aussage allein aus
   YAML-/String-Vertragstests ableiten.
4. Den letzten Client-Source-Stand getrennt fixieren und testen. Die
   Client-CI und der endgültige EXE-/Wheel-/sdist-Build müssen auf exakt
   dessen Commit laufen. Server- und Client-Commit-SHAs samt
   Kompatibilitätsmatrix festhalten.
5. Vor Veröffentlichung den normalen Nutzerpfad nochmals prüfen:
   Windows-EXE ohne Sonderflags, alle Einstellungen, belegte
   Hotkeys/Rollback/Neustart, Ton/LED, Wakeword und Hotkey,
   Echtzeit-/Finaltext. Isolierte Windows-/Linux-Server mit echtem Modell
   und echter Pro-Lizenz sowie unveränderter VPS-Produktion dokumentieren.
   Ein gefundenes Produktproblem führt zu Fix, neuen Tests/Builds und
   neuem Freeze.
6. **GitHub-Workflow-Aktivierung:** `workflow_dispatch` setzt voraus,
   dass die Workflowdatei auch auf dem Default-Branch liegt. Derzeit
   fehlt `release-publish.yml` auf `main`. Erst nach erfolgreicher
   **Clean-Commit-CI und gesonderter Main-Freigabe** exakt diesen einen
   V1-Commit nach `main` übernehmen; die 18 Arbeitscommits bleiben
   außerhalb der dauerhaften Main-Historie. Remote-SHA/Tree erneut
   prüfen. Erst danach Candidate/Publish manuell dispatchen. Keine
   stille Umdeutung des Candidates auf einen anderen Commit.

## V1/V2-Git-Historie nach dem V1-Release

Der V1-Tag bleibt auf dem qualifizierten V1-Main-Commit. Die V2-Linien
`feat/einheitliche-triggerarchitektur-distributed` und
`feat/einheitliche-triggerarchitektur` werden durch V1 nicht verändert
oder rebasiert. Nach AP-SRV-070 W6 und Root PASS wird der endgültig
qualifizierte V2-Canonical-Commit separat in `main` integriert. Weil
beide Linien dann divergiert sind, ist dies ein **bewusster Merge**,
kein Fast-Forward. Sein unverhandelbares Gate lautet:

`TREE(Main nach V2-Merge) == TREE(final qualifizierter V2 Canonical)`.

Der Merge-Commit hat V1-Main und V2-Canonical als Eltern, bewahrt also
beide Historien, übernimmt im Ergebnis aber genau den freigegebenen
V2-Dateibaum. Überlappende Packaging-, Modell- und Workflow-Dateien
nicht automatisch vermischen. Tree-Hash und vollständige CI des
tatsächlichen Merge-Commits vor dem V2-Release prüfen. Der V2-Tree
muss dabei seine eigenen Release-Workflows enthalten; der derzeitige
Canonical-Zwischenstand hat sie noch nicht, Distributed schon. Auch diese
V1/V2-Übergangsdokumentation muss vor dem finalen V2-Freeze bewusst in
V2 Canonical aufgenommen und dort mitqualifiziert werden, wenn sie
nach dem Merge erhalten bleiben soll. Sie darf nicht erst bei der
Konfliktauflösung in den bereits qualifizierten V2-Tree hineinrutschen.

## 2. Server-Candidate – erst nach eigener Freigabe

1. Aus **dem exakt grünen Server-Commit** den manuellen
   `release-candidate.yml`-Workflow starten. Zuvor private
   `*-v1-staging`-GHCR-Ziele und den Workflow-Guard prüfen. Run-ID und
   Commit/Tree im Release-Record festhalten.
2. Vier öffentliche Klassen aus demselben Source-Commit erzeugen:
   `voice-stt-server` Free und `voice-stt-server-pro` Pro, jeweils
   CPython 3.12 / Linux x86_64 und Windows AMD64. Kroko Native Runtime
   ist direkt im Produktwheel; kein zweites Nutzer-Wheel, kein
   `py3-none-any`, kein öffentlicher Server-sdist.
3. Free/Pro sowie Plattform nicht aus dem API-Key erraten. Modelle,
   insbesondere Pro-Modelle, und Schlüssel nicht in Wheels/Images
   einbetten. Die 14 dokumentierten Wakeword-Klassifikatoren und ihre
   Pipeline-Dateien dagegen als bewusste Paketressourcen prüfen.
4. Echte Installations-, Import-, CLI-, CPU-only-, `pip check`-,
   Modellpolitik-, Lizenz/NOTICE- und Secret-Prüfungen gegen die
   tatsächlichen Candidate-Bytes ausführen. Die beiden daraus
   gebauten Images zusätzlich im isolierten PC-/VPS-Teststack mit
   Health, echter Transkription und den 14 Wakewords qualifizieren.
   Freigabe nur, wenn Windows **und** Linux Free/Pro grün sind. Für Pro
   zusätzlich Missing-Model-Fail-Closed und reale Lizenz-/Modellnutzung
   nachweisen; die produktive VPS-Instanz bleibt dabei an.
5. `rc-manifest.json` und SHA-256-Inventar an Commit, Tree,
   Workflow-Run und alle vier Wheels/OCI-Digests binden. Die
   qualifizierten Bytes als unveränderlichen Candidate aufbewahren.
   Das Evidenzpaket enthält auch diesen Plan und seine Prüfsumme.

## 3. Server-Publish-Preflight – vor dem ersten öffentlichen Write

- Separates ausdrückliches Startsignal des Nutzers einholen. Workflow
  `release-publish.yml` muss zuvor auf `main` verfügbar sein. Ihn
  manuell auf **dem Candidate-Commit** mit dessen Run-ID starten;
  nicht auf einem späteren Checkout oder anderen Candidate.
- Versionsnummer 1.0.0, Git-Commit/Tree, Candidate-Manifest, alle
  lokalen SHA-256 und alle Remote-Zielnamen prüfen. Bereits vorhandenen
  `v1.0.0`-Tag nur bei exakt erwartetem Commit als MATCH behandeln.
- PyPI Trusted Publisher für Free: Repository
  `marcosudau-vps/voice-stt-server`, Workflow
  `release-publish.yml`, Environment `release`.
  Pro nutzt später dieselbe Identity. Das GitHub-Environment,
  OIDC-Rechte, Docker-Hub-Token/-Namespace und GHCR-Rechte müssen vor
  dem betreffenden Write funktionieren. Secret-Werte nicht protokollieren.
- Alle externen Dateien/Images pro Artefakt klassifizieren:
  **ABSENT** = nur dann schreiben, **MATCH** = überspringen,
  **CONFLICT** oder **UNKNOWN** = vor dem nächsten Write stoppen.
  Nicht erreichbarer Remote ist UNKNOWN, nicht ABSENT.

## 4. Server-Publikation – feste Reihenfolge

1. **PyPI Free:** Linux- und Windows-Wheel nur bei ABSENT hochladen;
   beide Remote-Dateien mit Candidate-Hashes als MATCH verifizieren.
2. **PyPI Pro Bootstrap:** Beim ersten Free-Upload zeigt der Workflow
   anschließend ein **240-Sekunden-Fenster**. Der Nutzer kann in dieser
   Zeit `voice-stt-server-pro` als Pending Publisher mit derselben
   Identity einrichten. Danach wird Pro im **selben Lauf** versucht.
   Gelingt das Setup nicht rechtzeitig, endet der Lauf bei Pro. Das ist
   kein Grund für Version 1.0.1 oder einen neuen Candidate: Publisher
   korrigieren und `release-publish.yml` erneut mit **derselben
   Version, Candidate-Run-ID, Source-SHA und denselben Bytes** starten.
   Bereits MATCH Free-Dateien dürfen nie erneut hochgeladen werden.
   Auch bei nur einem vorhandenen Pro-Wheel wird nur das ABSENT-Wheel
   gestaged. Vor Containern müssen alle vier PyPI-Wheels MATCH sein.
3. **Docker Hub exact:** Free/Pro mit unveränderlichen `:1.0.0`-Tags
   aus den qualifizierten Candidate-OCI-Identitäten veröffentlichen
   und remote digest-verifizieren. Kein zweiter Image-Build.
4. **GHCR exact:** Dasselbe qualifizierte OCI-Manifest nach GHCR
   promoten, Free/Pro `:1.0.0` digest-verifizieren. Nicht einfach
   aus demselben Source-Commit neu bauen.
5. **Bewegliche Aliase:** Erst wenn alle vier exakten Image-Ziele
   stimmen, `:1.0`, `:1`, `:latest` für Free/Pro in beiden
   Registries setzen und jeden Alias-Digest gegen `:1.0.0`
   verifizieren. Bestehende fremde Exact-Tags nie überschreiben.
6. **Pre-Tag-Gate:** Nochmals Candidate, alle vier PyPI-Dateien,
   alle exakten Image-Tags und Aliase extern prüfen. Erst danach den
   Git-Tag `v1.0.0` auf den Candidate-Commit erzeugen bzw. exakt
   passenden vorhandenen Tag akzeptieren. Der Tag wird nicht
   umgeschrieben. Diese späte Reihenfolge ist die ausdrückliche
   **V1-Entscheidung**; der ältere V2-Plan empfiehlt das Gegenteil.
   PyPI/Registry-Writes sind dennoch schon öffentlich und nicht
   rückgängig zu machen. Ein Abbruch davor wird mit derselben
   Candidate-Identität fortgesetzt.
7. **GitHub Release zuletzt:** Auf `v1.0.0` die vier Wheel-Bytes,
   Candidate-Manifest und SHA-Inventar veröffentlichen. Existierende
   Assets **vor** Ergänzung fehlender Assets byteweise vergleichen;
   niemals `--clobber`. Danach alle Assets, PyPI und Registry-Digests
   final verifizieren. Erst dann Serverstatus COMPLETE melden.

## 5. Client erst nach vollständig erfolgreichem Server

Der Client wird aus dem eigenen Repository separat als 1.0.0
veröffentlicht: Windows-EXE sowie Python-Wheel und sdist. Sein
Release-Bundle muss aus genau einem getesteten Commit stammen; EXE,
Wheel und sdist erhalten SHA-256 und einen isolierten Installations-/
Start-Smoke. Der bisherige Client-Workflow startet per Tag und erzeugt
den Tag damit **vor PyPI**; außerdem ist ein partieller PyPI-Upload
nicht ausreichend resumefähig. Vor dem Client-Publish ist diese
Abweichung gezielt zu schließen und der tatsächliche Workflow gegen
die hier vereinbarte Reihenfolge zu prüfen: PyPI-Artefakte exakt
prüfen/veröffentlichen, danach Git-Tag, GitHub Release zuletzt.
Das Client-`pypi`-Environment/Trusted Publishing ist zuvor einzurichten.
Keine Client-Veröffentlichung allein wegen erfolgreichem Server-Release.

## 6. Nachweise, Abbruch und Abschluss

- Evidenz umfasst Commit/Tree, CI-Run-IDs, vier Wheel-Namen/Größen/
  SHA-256, Native-Runtime-Provenance, Windows-/Linux-Clean-Install,
  CPU-only/`pip check`, Free/Pro-Varianten, 14 Wakewords, Docker
  Free/Pro, echte Lizenz/Transkription, Secret-/Lizenzinventar,
  PyPI-Resume-Simulation und den No-Publication-Guard. Den
  `v1-correction-1-evidence`-Ordner samt `SHA256SUMS.txt` als
  überprüfbares CI-Artefakt aufbewahren; lokale Testergebnisse
  getrennt und ehrlich als zusätzliche Abnahme ausweisen.
- Bei jeder Abweichung STOP vor dem nächsten externen Write; Status
  mit Remote-Identität und Ursache festhalten. Nur bei ABSENT
  weitermachen; bei MATCH überspringen. CONFLICT/UNKNOWN nicht
  automatisch beheben. Nach Source-Änderung ist der frühere
  Candidate ungültig und muss neu gebaut/qualifiziert werden.
- Abschlussmeldung nennt Server- und Client-Commit, Candidate- und
  CI-Run-IDs, Evidence-Artefakt, veröffentlichte URLs/Dateihashes/
  Digests, Ergebnis der manuellen End-to-End-Tests und jedes
  verbleibende Risiko. „Alles grün“ ohne diese Identitäten genügt
  nicht.

## Aus älteren Quellen gezielt übernommene Ideen

| Übernommen | Herkunft | Konkreter Mehrwert |
| --- | --- | --- |
| Candidate an Commit **und Tree**, Dateihashes und OCI-Digests binden | V2-Plan §5, C1 §§11/27 | Verhindert einen stillen Austausch gleicher Versionsnamen. |
| Einmal bauen, exakte Bytes qualifizieren und promoten | V2-Plan §§2/5/25, V1-Original §8 | Verhindert verschiedene GitHub-/Docker-/PyPI-Buildstände. |
| Docker Hub vor GHCR; dasselbe Manifest statt Rebuild | V2-Plan §11, V1-Original §11 | Senkt Registry-Drift und macht Digestprüfung eindeutig. |
| Erst Exact-Tags, danach Aliase | V2-Plan §§12/15, Docker-Draft „Registry“ | `latest` zeigt nie vorzeitig auf einen halben Free/Pro-Release. |
| ABSENT/MATCH/CONFLICT/UNKNOWN pro Datei | V2-Plan §§13/14, C1 §§14/15 | Sicherer Resume ohne Überschreiben oder Raten bei Netzfehlern. |
| OIDC-gebundener PyPI-Publisher und getrennte Publish-Rechte | V2-Plan §§18–21, C1 §14 | Kein langlebiger PyPI-Token im Workflow; CI ohne Publish-Rechte. |
| SHA-gepinnte Drittanbieter-Actions | V2-Plan §18 | Verringert Änderungen an der Action-Supply-Chain zwischen Runs. |
| Echter Windows-/Linux-Clean-Install mit Variant-/CPU-Beweis | C1 §§21/27, C2 CPU-only | Testet das tatsächlich gelieferte native Endnutzerprodukt. |
| Wheel-/Lizenz-/Secret-Inventar und Evidence-Prüfsummen | C1 §27, Docker-Draft „Qualification“ | Unabhängiger Review ohne Vertrauen auf Chat-Zusammenfassungen. |
| Container-Health und keine Secrets/Pro-Modelle im Image | Docker-Draft „Production/Qualification“ | Erkennt reale Betriebs- und Datenleckrisiken vor Publikation. |
| GitHub Release als letzter sichtbarer Erfolgspunkt | V2-Plan §§16/17, V1-Original §11 | Die Release-Seite erscheint erst nach bestätigter Distribution. |
| Kein Release von einem beliebigen Tag-Push | V2-Plan §7 | Manuelle Candidate-/Publish-Dispatches halten den Start kontrolliert. |

**Bewusst nicht übernommen:** Die frühe Tag-Erstellung aus dem V2-Plan
widerspricht der späteren ausdrücklichen V1-Entscheidung. Die
V1-Originalannahme `1.0.2`/nur ein PyPI-Projekt/öffentlicher sdist
ist durch den später qualifizierten 1.0.0-Free/Pro-Vertrag ersetzt.
Ein lokaler Publish, ein öffentlicher 0.9.0-Probelauf, V2-Architektur-
Backports, eine zusätzliche SIGTERM-Testinfrastruktur nur für den
Releaseablauf und ein modellgefülltes Docker-Image bringen für diesen
V1-Release keinen gerechtfertigten Vorteil.

## Historische Ideenquellen (nicht normativ)

- `AP-SRV-070 #U2013 Fixierter Release- und Publikationsplan.md`
- `AP-SRV-070_W4C_PRODUCTION_DOCKER_DEPLOYMENT_DRAFT (1).md`
- `V1_RELEASE_PROMPT_2026-09-11.md`
- `V1_RELEASE_PROMPT-C1_2026-09-11.md`
- `V1_RELEASE_PROMPT-C2_2026-09-14.md`
