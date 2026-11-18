# AP-SRV-070 – Fixierter Release- und Publikationsplan

## 1. Zweck und Status dieses Dokuments

Dieses Dokument fixiert den aktualisierten Release- und Publikationsplan für **AP-SRV-070 / VoiceSTT 2.0.0**.

Der Releaseweg wurde gegenüber der ursprünglichen Planung während W5 gezielt überarbeitet. Anlass war insbesondere der Vergleich mit dem bereits erfolgreich eingesetzten Releaseverfahren des Referenzprojekts `admin_portal_workspaces`.

Dabei wurde nicht das Ziel verfolgt, dessen Verfahren unverändert zu kopieren. Stattdessen wurden die dort bewährten Mechanismen übernommen, soweit sie für VoiceSTT geeignet sind, während bereits stärkere VoiceSTT-spezifische Mechanismen erhalten bleiben.

Dieser Plan ersetzt für den Releaseablauf die früheren Annahmen, insbesondere bezüglich:

- Zeitpunkt der Git-Tag-Erzeugung,
- Reihenfolge der Container-Registries,
- Rolle von GitHub Actions,
- Behandlung der qualifizierten Release-Artefakte,
- Registry-Aliases,
- GitHub Release,
- Wiederaufnahme teilweise abgeschlossener Releases,
- Authentifizierung gegenüber den Publikationszielen.

Nicht Gegenstand dieses Releaseplans sind zusätzliche Produktfunktionen oder neue Distributionsvarianten. Insbesondere wird **kein separates Docker-Image mit vorinstallierten STT-Modellen** mehr in AP-SRV-070 aufgenommen. Die bestehende Model-Management-/Provisioning-Architektur bleibt für 2.0.0 unverändert.

---

# 2. Grundprinzip des Releaseverfahrens

Für VoiceSTT gilt weiterhin:

> Ein Release darf nicht aus einem beliebigen Checkout oder durch einen erneuten unqualifizierten Build entstehen. Veröffentlicht werden dürfen ausschließlich Artefakte, deren konkrete Identität auf einen qualifizierten Release Candidate zurückgeführt werden kann.

Der zentrale Unterschied zu einem einfachen „Tag push → alles neu bauen“-Workflow besteht darin, dass VoiceSTT wesentlich stärkere Artefakt- und Variantenanforderungen besitzt.

Die Releasequalifikation umfasst unter anderem:

- VoiceSTT Wheel,
- Source Distribution,
- Kroko-Free-Runtime,
- Kroko-Pro-Runtime,
- Docker Free,
- Docker Pro,
- exakte Produktversion,
- exakten Git Commit,
- exakten Git Tree,
- definierte SHA-256-Identitäten,
- Free-/Pro-Artefaktauthority,
- installierte Distribution,
- reale STT-E2E-Qualifikation.

Daraus folgt:

> **Build once – qualify exactly – publish exactly.**

Ein späterer unabhängiger Rebuild desselben Source Commits gilt nicht automatisch als identisches Releaseartefakt.

---

# 3. Warum der ursprüngliche Publish-Ansatz geändert wurde

Der frühere VoiceSTT-Plan sah sinngemäß folgenden Ablauf vor:

```text
PREPARED
→ PyPI
→ GHCR
→ Docker Hub
→ externe Verifikation
→ Git Tag
→ GitHub Release
→ finale Verifikation
→ COMPLETE
```

Dieser Ablauf wird nicht mehr verwendet.

Insbesondere die späte Erzeugung des Git Tags erwies sich im Vergleich mit dem Referenzprojekt als ungünstig.

Sobald beispielsweise `VoiceSTT 2.0.0` auf PyPI veröffentlicht wurde, ist die Versionsnummer extern bereits verbraucht. Ein noch fehlender Git Tag bietet zu diesem Zeitpunkt keinen echten Schutz mehr.

Im Gegenteil könnte dadurch folgender unvorteilhafter Zustand entstehen:

```text
PyPI 2.0.0 veröffentlicht
Docker teilweise veröffentlicht
Git Tag v2.0.0 fehlt
```

Damit würde eine bereits öffentliche Releaseidentität existieren, ohne dass gleichzeitig die kanonische immutable Git-Identität vorhanden ist.

Der aktualisierte Plan erzeugt deshalb den Release-Tag **nach allen deterministischen Prüfungen, aber vor dem ersten öffentlichen Publish-Schritt**.

---

# 4. Aktualisierter Gesamtprozess

Der Zielablauf für VoiceSTT 2.0.0 lautet:

```text
Release Candidate vorbereiten
        ↓
exakte Artefakte erzeugen
        ↓
exakte Artefakte qualifizieren
        ↓
externe Root Review
        ↓
Root PASS
        ↓
GitHub CI auf exaktem Release Commit
        ↓
alle Preflight-/Credential-/Remote-State-Gates
        ↓
Git Tag v2.0.0
        ↓
PyPI
        ↓
Docker Hub – exakte Version
        ↓
GHCR – Promotion desselben OCI-Manifests
        ↓
exakte Registry-Artefakte verifizieren
        ↓
Registry-Aliases bewegen
        ↓
Aliases verifizieren
        ↓
GitHub Release
        ↓
finale externe Verifikation
        ↓
COMPLETE
```

Wichtig ist dabei die Trennung zwischen:

1. **Release Candidate / Qualification**
2. **Release Publication**

Die Publikation darf keine neue Produktentwicklung und keine neue unqualifizierte Artefaktgeneration darstellen.

---

# 5. Release Candidate und Artefaktidentität

## 5.1 Kanonischer Release Candidate

Vor der Veröffentlichung wird ein konkreter Release Candidate festgelegt.

Dieser besitzt mindestens:

- Git Commit SHA,
- Git Tree SHA,
- Version,
- Wheel SHA-256,
- Source Distribution SHA-256,
- Kroko-Free-Artefaktidentität,
- Kroko-Pro-Artefaktidentität,
- Free-Containeridentität,
- Pro-Containeridentität,
- Qualification-/Evidence-Referenzen.

Diese Informationen werden in einem RC-/Release-Manifest festgehalten.

Das Manifest ist ein zentraler Bestandteil der Release Authority.

---

## 5.2 Kein stiller Rebuild nach Qualification

Eine wesentliche Erkenntnis aus W5 ist:

Der aktuelle Production Build ist nicht zwangsläufig byte-identisch reproduzierbar.

Beispielsweise fließt beim Container-Build derzeit ein Build-Zeitpunkt in die OCI-Metadaten ein.

Dadurch gilt:

```text
gleicher Git Commit
≠ automatisch
gleiche Containeridentität
```

Deshalb darf ein GitHub-Publish-Workflow nicht einfach nach dem Tag einen komplett neuen Free-/Pro-Build erstellen und diesen ungeprüft veröffentlichen.

Der Zielzustand ist:

```text
einmal bauen
→ genau diese Artefakte qualifizieren
→ genau diese Artefakte publizieren
```

---

# 6. GitHub Actions als Publikationsauthority

Der tatsächliche externe Publish soll grundsätzlich über **GitHub Actions** erfolgen.

Der lokale Releasecode beziehungsweise das lokale Release-Tool bleibt für Vorbereitung, Orchestrierung, Validierung und Statusprüfung relevant.

Die eigentliche Veröffentlichung soll jedoch nicht von einem Entwickler-PC als alleiniger Publish-Endpunkt abhängig sein.

GitHub Actions übernimmt insbesondere die kontrollierte Veröffentlichung gegenüber:

- PyPI,
- Docker Hub,
- GHCR,
- GitHub Releases.

Damit werden:

- Credentials zentralisiert,
- Veröffentlichungen nachvollziehbar,
- Logs dauerhaft verfügbar,
- Wiederholungen kontrollierbar,
- lokale Umgebungsabhängigkeiten reduziert.

---

# 7. Release-Trigger

Die Veröffentlichung darf nicht versehentlich allein durch einen beliebigen Tag-Push gestartet werden.

Der Workflow muss einen kontrollierten Releasekontext besitzen.

Der Releaseprozess soll mindestens auf einer eindeutig definierten RC-/Releaseidentität beruhen.

Für den produktiven Publish ist ein kontrollierter GitHub-Workflow vorgesehen, beispielsweise über:

- bewusstes `workflow_dispatch`,
- oder einen vom Releaseorchestrator kontrolliert erzeugten Release-Tag,
- gegebenenfalls kombiniert mit einem geschützten GitHub Environment `release`.

Entscheidend ist:

> Ein zufällig oder manuell falsch erzeugter `v*`-Tag darf nicht ungeprüft einen vollständigen Produktrelease auslösen.

---

# 8. Git Tag

Der Git Tag wird künftig **vor der ersten öffentlichen Veröffentlichung** erzeugt.

Voraussetzungen sind:

- Release Candidate qualifiziert,
- Root PASS erteilt,
- exakter Source Commit festgelegt,
- CI für diesen Commit erfolgreich,
- Repositoryzustand sauber,
- Zielversion konsistent,
- keine Konflikte mit bereits bestehenden Remote-Artefakten,
- benötigte Publish-Credentials vorhanden,
- Registry-Zielnamen konfiguriert,
- Releasezustand eindeutig.

Danach wird der immutable Release Tag erzeugt:

```text
v2.0.0
```

Ein veröffentlichter Tag wird nicht nachträglich verschoben oder überschrieben.

Insbesondere verboten:

- force push des Release Tags,
- Tag löschen und neu erzeugen,
- Tag auf anderen Commit verschieben,
- Releaseversion unter anderer Source Identity weiterführen.

---

# 9. PyPI

PyPI bleibt ein eigenständiger öffentlicher Releasekanal.

Veröffentlicht werden ausschließlich die bereits qualifizierten Python-Artefakte.

Kein neuer Package-Build darf erst während des öffentlichen Publish-Schritts unkontrolliert entstehen.

Der bevorzugte zukünftige Authentifizierungsweg ist **PyPI Trusted Publishing via GitHub OIDC**, sofern dies ohne Aufspaltung oder Schwächung des zentralen Releaseprozesses integriert werden kann.

Vorteile:

- kein langlebiger PyPI API Token,
- kurzlebige OIDC-basierte Credentials,
- Bindung an das konkrete GitHub Repository bzw. Environment.

Falls die OIDC-Integration für 2.0.0 unverhältnismäßig in den bestehenden Release Engine eingreifen würde, kann für diesen Release auch ein projektgebundener PyPI Token verwendet werden.

Die Architektur darf jedoch nicht allein wegen OIDC unnötig umgebaut werden.

---

# 10. Container-Publikation

Für VoiceSTT existieren zwei Produktvarianten:

```text
Free
Pro
```

Diese bleiben vollständig getrennte Containerartefakte.

Vorgesehene öffentliche Repositories:

## Docker Hub

```text
marcosudau/voice-stt-server
marcosudau/voice-stt-server-pro
```

## GHCR

```text
ghcr.io/marcosudau-vps/voice-stt-server
ghcr.io/marcosudau-vps/voice-stt-server-pro
```

---

# 11. Docker Hub vor GHCR

Die zuvor vorgesehene Reihenfolge

```text
GHCR
→ Docker Hub
```

wird geändert.

Neue Reihenfolge:

```text
Docker Hub
→ GHCR
```

Entscheidend ist allerdings nicht nur die Reihenfolge, sondern die Art der Promotion.

Die Container sollen nicht für beide Registries getrennt gebaut werden.

Stattdessen gilt:

```text
qualifiziertes OCI-Artefakt
        ↓
Docker Hub exact version
        ↓
verifizieren
        ↓
identisches Manifest nach GHCR kopieren/promoten
        ↓
verifizieren
```

Für die Registry-übergreifende Promotion kann beispielsweise `docker buildx imagetools create` eingesetzt werden.

Ziel:

> Docker Hub und GHCR müssen für die konkrete Releaseversion dasselbe qualifizierte Containerartefakt repräsentieren.

Damit wird vermieden:

```text
Docker Hub Build A
GHCR Build B
```

obwohl beide formal dieselbe Version tragen.

---

# 12. Exakte Versionstags

Für Version `2.0.0` werden zunächst ausschließlich immutable Exact Tags veröffentlicht:

## Free

```text
marcosudau/voice-stt-server:2.0.0

ghcr.io/marcosudau-vps/voice-stt-server:2.0.0
```

## Pro

```text
marcosudau/voice-stt-server-pro:2.0.0

ghcr.io/marcosudau-vps/voice-stt-server-pro:2.0.0
```

Diese Exact Tags stellen die eigentliche Releaseidentität dar.

Ein bereits existierender Exact Tag darf nicht stillschweigend überschrieben werden.

---

# 13. Remote-State-Semantik

Die bereits stärkere VoiceSTT-State-Machine bleibt erhalten.

Für jedes externe Ziel gilt sinngemäß:

```text
ABSENT
→ darf publiziert werden

MATCH
→ bereits korrekt vorhanden
→ Release darf fortgesetzt werden

CONFLICT
→ harter STOP

UNKNOWN
→ harter STOP
```

Besonders wichtig:

> „Remote konnte nicht geprüft werden“ darf niemals als „Remote existiert nicht“ interpretiert werden.

Beispiel:

Ein Registry-Request schlägt wegen fehlender Authentifizierung fehl.

Falsch wäre:

```text
Registry nicht erreichbar
→ wohl noch nicht vorhanden
→ push
```

Richtig:

```text
Registryzustand nicht zuverlässig bestimmbar
→ UNKNOWN
→ Release stoppen
```

Registry-State-Checks erfolgen deshalb nach erfolgreicher Authentifizierung beziehungsweise mit ausreichend privilegiertem Zugriff.

---

# 14. Wiederaufnahme eines teilweise veröffentlichten Releases

Der Releaseprozess muss nach einem technischen Abbruch unter derselben Version wiederaufnehmbar sein.

Beispiel:

```text
PyPI 2.0.0            MATCH
Docker Hub Free       MATCH
Docker Hub Pro        MATCH
GHCR Free             ABSENT
GHCR Pro              ABSENT
GitHub Release        ABSENT
```

Dann wird **nicht** Version 2.0.1 erzeugt.

Stattdessen wird der bestehende Release `2.0.0` fortgesetzt.

Das Release Engine prüft vor jedem Schritt den tatsächlichen Remotezustand.

Bereits korrekt abgeschlossene Schritte werden übersprungen.

Nur noch fehlende Schritte werden ausgeführt.

Bei einem Konflikt dagegen:

```text
2.0.0 existiert
aber Inhalt/Digest stimmt nicht
```

gilt:

```text
CONFLICT
→ STOP
```

Kein automatisches Überschreiben.

---

# 15. Registry-Aliases

Nach erfolgreicher Veröffentlichung und Verifikation aller Exact Tags werden bewegliche Registry-Aliases gesetzt.

Für `2.0.0`:

```text
2.0.0
2.0
2
latest
```

Das gilt für:

- Docker Hub Free,
- Docker Hub Pro,
- GHCR Free,
- GHCR Pro.

Die Exact-Version bleibt immutable.

Die folgenden Tags sind beweglich:

```text
2.0
2
latest
```

Sie werden erst aktualisiert, wenn alle Exact-Artefakte vollständig vorhanden und verifiziert sind.

Damit darf beispielsweise nie passieren:

```text
Free 2.0.0 veröffentlicht
Pro Publish fehlgeschlagen
latest bereits auf 2.0.0
```

Stattdessen gilt:

```text
alle exakten Artefakte
für Free + Pro
auf Docker Hub + GHCR
müssen erfolgreich verifiziert sein
        ↓
erst dann Aliases bewegen
```

Anschließend wird geprüft, dass jeder Alias auf denselben Digest wie der entsprechende `2.0.0`-Tag zeigt.

---

# 16. GitHub Release als letzter öffentlicher Erfolgspunkt

Der GitHub Release wird nicht am Anfang des Publishvorgangs erzeugt.

Er ist bewusst der letzte große öffentliche Schritt.

Reihenfolge:

```text
Git Tag
PyPI
Docker Hub exact
GHCR exact
Remote Verification
Aliases
Alias Verification
GitHub Release
```

Damit bedeutet ein sichtbarer GitHub Release:

> Die vorgesehenen externen Releasekanäle wurden bereits erfolgreich veröffentlicht und verifiziert.

Ein GitHub Release soll daher nicht existieren, während zentrale Releaseartefakte noch fehlen.

---

# 17. GitHub Release Inhalt

Der Release basiert auf dem bereits vorhandenen Git Tag:

```text
v2.0.0
```

Die Releaseinformationen sollen mindestens enthalten beziehungsweise eindeutig referenzieren:

- Produktversion,
- Release Notes,
- exakten Git Commit,
- gegebenenfalls RC-/Manifestreferenz,
- PyPI-Paket,
- Docker Hub Free,
- Docker Hub Pro,
- GHCR Free,
- GHCR Pro.

Ein zusätzlicher vollständiger Neubau findet an dieser Stelle nicht statt.

---

# 18. GitHub Actions Security

Alle Drittanbieter-Actions müssen möglichst auf vollständige Commit-SHAs gepinnt werden.

Nicht ausreichend sind beispielsweise allein:

```text
actions/checkout@v4
docker/login-action@v3
```

Bevorzugt:

```text
actions/checkout@<full-commit-sha>
docker/login-action@<full-commit-sha>
```

Damit wird die Supply-Chain-Angriffsfläche reduziert.

---

# 19. Release Environment

Für die tatsächliche Veröffentlichung ist ein geschütztes GitHub Environment

```text
release
```

sinnvoll.

Dieses kann insbesondere verwendet werden für:

- Publish-Credentials,
- PyPI Trusted Publishing,
- manuelle Freigabe,
- zusätzliche Deployment-Regeln.

Damit bleibt die normale CI von den produktiven Publish-Berechtigungen getrennt.

---

# 20. Docker-Hub-Konfiguration

Öffentliche Docker-Hub-Identity:

```text
Docker ID / Namespace:
marcosudau
```

Empfohlene GitHub-Konfiguration:

## Repository Variable

```text
DOCKERHUB_USERNAME=marcosudau
```

Da der Benutzername keine geheime Information darstellt, muss er nicht zwingend als Secret gespeichert werden.

## Repository Secret

```text
DOCKERHUB_TOKEN=<Docker-Hub-PAT>
```

Zusätzlich:

```text
VOICESTT_RELEASE_DOCKERHUB_REPO=marcosudau
```

---

# 21. GHCR-Konfiguration

GHCR Namespace:

```text
ghcr.io/marcosudau-vps
```

Repository Variable:

```text
VOICESTT_RELEASE_GHCR_REPO=ghcr.io/marcosudau-vps
```

Für die Authentifizierung wird kein separater langfristiger GHCR PAT benötigt.

GitHub Actions verwendet:

```text
${{ secrets.GITHUB_TOKEN }}
```

mit mindestens:

```text
packages: write
```

---

# 22. Preflight

Der Release-Preflight muss vor dem ersten öffentlichen Publish alle deterministisch prüfbaren Voraussetzungen kontrollieren.

Dazu gehören mindestens:

## Git

- erwartetes Repository,
- erwarteter Release Branch,
- sauberer Working Tree,
- exakter Release Commit,
- exakter Tree,
- keine unerwarteten lokalen Änderungen.

## Version

- `VERSION`,
- Package-Version,
- Wheel-Version,
- Runtime-Version,
- Container-Metadaten,
- Release Tag

müssen konsistent sein.

## CI

- erwarteter GitHub-Actions-Workflow,
- exakt der Release Commit,
- alle erforderlichen Plattformen erfolgreich.

## Registries

Zielidentitäten müssen explizit gesetzt sein:

```text
VOICESTT_RELEASE_DOCKERHUB_REPO
VOICESTT_RELEASE_GHCR_REPO
```

Fehlende Registry-Ziele sind **FAIL**, nicht WARN.

Fehlende Credentials sind spätestens vor dem tatsächlichen Publish ebenfalls ein harter Blocker.

## PyPI

- Zielprojekt,
- Authentifizierung,
- bestehende Version prüfen.

## Remote State

Jedes Publikationsziel muss eindeutig klassifiziert werden können:

```text
ABSENT
MATCH
CONFLICT
```

Kann der Zustand nicht sicher bestimmt werden:

```text
UNKNOWN
→ FAIL CLOSED
```

---

# 23. Bestehende Release State Machine

Die bereits implementierte VoiceSTT-State-Machine bleibt konzeptionell erhalten.

Sie ist gegenüber dem Referenzprojekt sogar stärker und soll nicht durch ein einfaches lineares Shell-Skript ersetzt werden.

Die State Machine bleibt zuständig für:

- Releasezustand,
- Wiederaufnahme,
- Konflikterkennung,
- idempotente Schritte,
- externe Verifikation,
- Abschlusszustand.

Lediglich die Reihenfolge einzelner States wird an den neuen Releaseplan angepasst.

Konzeptionell:

```text
PREPARED
↓
TAGGED
↓
PYPI_PUBLISHED
↓
DOCKERHUB_EXACT_PUBLISHED
↓
GHCR_EXACT_PUBLISHED
↓
EXACT_ARTIFACTS_VERIFIED
↓
ALIASES_PUBLISHED
↓
ALIASES_VERIFIED
↓
GITHUB_RELEASE_PUBLISHED
↓
FINAL_VERIFIED
↓
COMPLETE
```

Die tatsächlichen internen State-Namen können hiervon abweichen; maßgeblich ist die Semantik.

---

# 24. Relationship zwischen lokalem Release Tool und GitHub Actions

Es soll weiterhin **eine logische Release Engine** geben.

Es soll nicht entstehen:

```text
lokale Release Engine A
+
komplett unabhängige GitHub Release Engine B
```

mit voneinander abweichender State- und Conflict-Semantik.

Vielmehr:

```text
lokale Vorbereitung / Orchestrierung
               +
GitHub Actions als privilegierter Publish Executor
               ↓
gemeinsamer Releasevertrag
```

Das lokale Tool kann beispielsweise:

- Candidate bestimmen,
- Preflight durchführen,
- CI anstoßen/prüfen,
- Release Manifest erzeugen,
- GitHub Workflow dispatchen,
- Workflowstatus auswerten,
- finalen Remotezustand prüfen.

GitHub Actions übernimmt die Schritte, für die zentrale Credentials und reproduzierbare Ausführungsumgebung besonders wichtig sind.

---

# 25. Artefaktübergabe an GitHub Actions

Der Releaseweg darf die W5-Qualifikation nicht dadurch entwerten, dass GitHub Actions nachträglich andere Artefakte erzeugt.

Langfristiger Zielzustand:

```text
RC Commit
↓
ein Artefakt-Build
↓
immutable Staging
↓
Qualification exakt dieser Artefakte
↓
Root PASS
↓
GitHub Publish
↓
Promotion exakt dieser Artefakte
```

Für kleine Python-Artefakte eignen sich beispielsweise GitHub Actions Artifacts beziehungsweise eine vergleichbare immutable Übergabe.

Für OCI-Images ist eine Registry-basierte Staging-/Promotion-Lösung grundsätzlich geeigneter als große ZIP-Artefakte.

Die konkrete Implementierung muss jedoch so klein wie möglich bleiben und darf für 2.0.0 keine unnötige neue Plattformarchitektur erzeugen.

Maßgeblich bleibt:

> Das veröffentlichte Artefakt muss auf die qualifizierte Artefaktidentität zurückführbar sein.

---

# 26. W5-Auswirkung der Releaseweg-Änderung

Durch die Änderung des Releaseverfahrens wird W5 nicht vollständig neu begonnen.

Die bereits abgeschlossene Produktqualifikation bleibt gültig, soweit die Produktartefakte unverändert bleiben.

Bereits erfolgreich qualifiziert wurden unter anderem:

- Faster-Whisper E2E,
- Kroko Free E2E,
- Kroko Pro E2E,
- Windows Installed Distribution,
- Ubuntu Installed Distribution,
- Wheel/Sdist,
- Kroko Artifact Authority,
- Docker Free,
- Docker Pro,
- D7 read-only Custom Source,
- Security-/Negative-Tests,
- Protocol-v2,
- kontrollierte Audio-End-to-End-Tests.

Diese geschlossenen Produktbereiche werden nicht erneut geöffnet, solange keine Release-Infrastrukturänderung ihre Gültigkeit konkret beeinträchtigt.

Der zusätzliche W5-Lauf konzentriert sich ausschließlich auf:

- Releaseinfrastruktur,
- Artefaktübergabe,
- Publishworkflow,
- State-/Resume-Semantik,
- Registrypromotion,
- Credentials/Preflight,
- Release-Manifeste,
- erforderliche Evidence-Gaps.

---

# 27. Noch offene Evidence-Punkte aus W5

Die bereits identifizierten Evidence-Lücken werden zusammen mit der finalen Release-Infrastrukturqualifikation geschlossen.

Dazu gehören insbesondere:

## Release Preflight

Ein früherer Report markierte den Preflight fälschlich als PASS, obwohl die Registry-Zielidentitäten fehlten.

Dieser Zustand muss korrigiert werden.

Fehlende:

```text
VOICESTT_RELEASE_GHCR_REPO
VOICESTT_RELEASE_DOCKERHUB_REPO
```

müssen zu einem echten Preflight-Failure führen.

## Hash-verifiziertes Provisioning

Es wird einmal konkret nachgewiesen:

```text
Authority SHA
→ Provisioning
→ Managed Store
→ tatsächlicher SHA
→ Equality
→ Discovery
```

## Managed Store Persistence

Es wird konkret nachgewiesen:

```text
Container A
→ Modell im persistenten Store
→ Container A entfernen
→ denselben persistenten Store verwenden
→ Container B
→ Modell vorhanden
→ SHA identisch
→ Discovery erfolgreich
```

Diese Tests stellen keine neue Modellarchitektur dar, sondern schließen lediglich bereits vorhandene W5-Nachweislücken.

---

# 28. Git-Governance

Die vorhandene AP-SRV-070 Git-Governance bleibt unverändert.

Auf:

```text
feat/einheitliche-triggerarchitektur-distributed
```

entsteht pro regulärem Agent-Run genau ein dauerhafter sauberer Commit.

Ein Commit darf erst nach externer Root Review auf die Distributed-Branch gepusht werden.

Ablauf:

```text
Agent erstellt lokalen finalen Commit
↓
Evidence
↓
externe Root Review
↓
Root PASS
↓
exakte Push-Autorisierung
↓
Push exakt dieses Commits
↓
Remote SHA / Tree / Parent prüfen
```

Keine:

- zusätzlichen Source-Commits nach Root PASS,
- Amendments,
- Rebases,
- Force Pushes,
- Tags,
- Canonicalization

ohne neue Freigabe.

---

# 29. Finaler AP-Abschluss

Erst wenn der vollständige Release Candidate und Releaseweg Root PASS erhalten haben, erfolgt die abschließende AP-SRV-070-Canonicalization.

Die Branchstruktur bleibt:

```text
main
└── feat/einheitliche-triggerarchitektur
    └── feat/einheitliche-triggerarchitektur-distributed
```

Die Distributed Branch enthält die geprüften Einzelcommits.

Die kanonische Branch erhält am Ende genau einen zusammengefassten AP-SRV-070-Abschlusscommit gemäß bestehender Projekt-Governance.

Danach erfolgt W6 beziehungsweise die endgültige öffentliche Veröffentlichung gemäß diesem Releaseplan.

---

# 30. Explizite Scope-Grenzen für VoiceSTT 2.0.0

Vor dem Release werden keine zusätzlichen Produktfeatures mehr aufgenommen.

Insbesondere nicht Teil dieses Releasezyklus:

- separate Docker-Images mit vorinstallierten STT-Modellen,
- neues Model-Distribution-System,
- neue Model-Bundle-Architektur,
- Änderungen der Trigger-/Activation-Architektur,
- neue Wake-Word-Architektur,
- neue Settings-Architektur,
- neue Protocol-v2-Funktionalität,
- Client-Redesign,
- neue Agent-/Workflow-Infrastruktur außerhalb des Releasebedarfs,
- zusätzliche Deploymentvarianten ohne konkreten Releaseblocker.

Die vorhandene Model-Provisioning-Architektur bleibt bestehen.

Ein eventuelles zukünftiges OCI-basiertes Model-Provisioning wird als separates Folgearbeitspaket behandelt.

---

# 31. Leitprinzipien für den verbleibenden Releaseweg

Für die verbleibenden Arbeiten gelten folgende verbindliche Prinzipien:

1. **Keine neue Produktentwicklung vor 2.0.0.**

2. **Keine erneute Vollqualifikation bereits geschlossener Bereiche ohne konkreten Grund.**

3. **Build once – qualify exactly – publish exactly.**

4. **Ein Git Commit allein ist keine ausreichende Artefaktidentität.**

5. **Git Tag vor dem ersten öffentlichen Publish.**

6. **Docker Hub exact zuerst, danach identisches OCI-Manifest nach GHCR promoten.**

7. **Exact Version Tags sind immutable.**

8. **Aliases werden erst nach vollständiger Exact-Publikation aktualisiert.**

9. **GitHub Release ist der letzte öffentliche Erfolgspunkt.**

10. **Remote-Verifikation ist fail-closed.**

11. **MATCH wird fortgesetzt, ABSENT publiziert, CONFLICT und UNKNOWN stoppen.**

12. **Ein unterbrochener Release wird unter derselben Version fortgesetzt.**

13. **Keine Versionsnummer nur aufgrund eines technischen Publishfehlers verbrauchen.**

14. **GitHub Actions ist der zentrale privilegierte Publish Executor.**

15. **Die bestehende VoiceSTT Release State Machine bleibt erhalten und wird nicht durch eine schwächere einfache Pipeline ersetzt.**

16. **Root PASS bleibt Voraussetzung für die endgültige Veröffentlichung.**

---

# 32. Finales Zielbild für VoiceSTT 2.0.0

Der Release gilt erst dann als vollständig abgeschlossen, wenn folgender Zustand gleichzeitig nachgewiesen ist:

```text
Git
✓ v2.0.0 zeigt auf den freigegebenen Release Commit

PyPI
✓ qualifizierte 2.0.0-Artefakte veröffentlicht

Docker Hub
✓ Free 2.0.0
✓ Pro 2.0.0
✓ Digests verifiziert

GHCR
✓ Free 2.0.0
✓ Pro 2.0.0
✓ identische promotete OCI-Artefakte verifiziert

Aliases
✓ 2.0
✓ 2
✓ latest
✓ jeweils auf korrektem Release-Digest

GitHub Release
✓ v2.0.0 vorhanden
✓ erst nach erfolgreicher Artifact Publication erzeugt

Release Manifest
✓ Commit
✓ Tree
✓ Version
✓ Package Hashes
✓ Kroko Artifact Identities
✓ Container Identities
✓ Registry Digests
✓ Qualification References

Release Engine
✓ FINAL_VERIFIED
✓ COMPLETE
```

Erst dieser Zustand stellt den vollständigen öffentlichen VoiceSTT-2.0.0-Release dar.

---

## Verbindlicher Planstand

Für AP-SRV-070 wird der hier beschriebene Releaseweg als aktueller Sollzustand verwendet.

Weitere Änderungen am Releaseverfahren erfolgen nur noch, wenn während Umsetzung oder Qualification ein **konkreter reproduzierbarer Releaseblocker** festgestellt wird.

Theoretische Verbesserungen, zusätzliche Features oder neue Distributionsideen werden für 2.0.0 nicht mehr aufgenommen.
