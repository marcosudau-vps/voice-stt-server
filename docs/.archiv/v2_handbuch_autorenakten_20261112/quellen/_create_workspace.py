from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC = ROOT / "SPEZIFIKATION_v0.2.md"
WORK = ROOT / "workflow"
DOC = ROOT / "docs" / "v2-handbuch"
AGENTS = ROOT / ".opencode" / "agents"

PARTS = {
    "01": "01-grundlagen",
    "02": "02-funktionsweise",
    "03": "03-konfiguration",
    "04": "04-schnittstellen",
    "05": "05-administration",
    "06": "06-betrieb",
    "07": "07-entwicklung",
    "08": "08-referenzen",
    "09": "09-anhaenge",
}

# Vorschläge sind redaktionelle Ideen, KEINE technisch bestätigten Abläufe.
DIAGRAMS = {
    "01.02": [("Komponentenübersicht", "flowchart", "Welche Hauptkomponenten kommunizieren direkt miteinander?")],
    "01.03": [("Schichten und Zuständigkeiten", "flowchart", "Welche Komponente besitzt welche Verantwortung?")],
    "01.04": [("Audio-zu-Text-Datenfluss", "flowchart", "Welche nachgewiesenen Datenübergaben führen zum Ergebnis?")],
    "01.05": [("Betriebsmodi im Vergleich", "flowchart", "Welche Modi und Triggerkombinationen existieren tatsächlich?")],
    "01.06": [("Shared vs. Session", "flowchart", "Welche Ressourcen sind serverweit, welche sitzungsgebunden?")],
    "01.07": [("Identitäten und Lebensdauer", "flowchart", "Wie sind Client, Connection, Session und Segment verknüpft?")],
    "01.09": [("Gesamtarchitektur", "flowchart", "Welche Systeme und Grenzen sind architektonisch sichtbar?")],
    "02.01": [("Session-Lebenszyklus", "stateDiagram-v2", "Welche Sessionzustände und Übergänge existieren?")],
    "02.02": [("Audio-Pipeline", "flowchart", "Wie durchläuft Audio Eingang, Puffer, VAD und ASR?")],
    "02.03": [("Activation-Phasen", "stateDiagram-v2", "Welche Phasen und erlaubten Übergänge sind im Code definiert?"), ("Activation-Zeitablauf", "sequenceDiagram", "Wie wirken Trigger, Timer, Audiofreigabe und Events zeitlich zusammen?")],
    "02.04": [("Wake-Word-Detektion und Rearm", "sequenceDiagram", "Welche Schritte von Treffer über Admission bis Rearm sind belegt?")],
    "02.05": [("Realtime-/Final-Korrelation", "sequenceDiagram", "Wie werden vorläufige und finale Ergebnisse tatsächlich zugeordnet?")],
    "02.06": [("Engine-Auswahl", "flowchart", "Wie werden ausschließlich die zwei freigegebenen Engines ausgewählt?")],
    "02.07": [("Modell-Lifecycle", "stateDiagram-v2", "Welche Modellzustände und Übergänge sind implementiert?")],
    "02.08": [("Inference-Queues", "flowchart", "Wie werden Lanes, Worker und Sessions in der Inferenz koordiniert?")],
    "03.01": [("Konfigurationsebenen", "flowchart", "Welche Konfigurationsinstanzen existieren tatsächlich?")],
    "03.02": [("Setting-Scopes", "flowchart", "Welche Scopes gelten und wie beeinflussen sie sich?")],
    "03.05": [("Konfigurationspriorität", "flowchart", "Welche wirksame Prioritätsreihenfolge definiert der Code?")],
    "03.08": [("Settings-Patch", "sequenceDiagram", "Wie laufen Validierung, Anwendung, Revision und Quittierung?")],
    "03.09": [("Wirksamkeitszeitpunkt", "sequenceDiagram", "Wann greifen Änderungen und welche Grenzen sind relevant?")],
    "04.03": [("V2-Handshake", "sequenceDiagram", "Wie läuft der reale hello-Handshake ab?")],
    "04.04": [("Command und ACK", "sequenceDiagram", "Wie werden Kommando, Ack, Replay und Konflikt gehandhabt?")],
    "04.06": [("Eventzustellung", "sequenceDiagram", "Was ist hinsichtlich Reihenfolge und eventSeq garantiert?")],
    "04.07": [("Snapshot/Resync", "sequenceDiagram", "Wie wird der Zustand nach Lücken synchronisiert?")],
    "04.08": [("Reconnect", "sequenceDiagram", "Wie erfolgt der real implementierte Wiederanlauf?")],
    "04.09": [("Client-State-Reducer", "flowchart", "Welche State-Inputs und Aktualisierungsregeln gelten?")],
    "04.10": [("OpenAI-HTTP-Transkription", "sequenceDiagram", "Wie laufen Upload, Modellauflösung, ASR und Antwort ab?")],
    "05.01": [("Vertrauenszonen", "flowchart", "Welche Schnittstellen sind öffentlich und welche geschützt?")],
    "05.03": [("Admin-Gate", "flowchart", "Welche Admin-Requests passieren welche Prüfung?")],
    "05.05": [("Logtoken-Lebensdauer", "sequenceDiagram", "Wie werden Logrechte und Tokens ausgegeben und validiert?")],
    "05.07": [("Community/Pro-Entscheidung", "flowchart", "Wie wird der Kroko-Modellzugriff entschieden?")],
    "05.08": [("Native-Guard-Lifecycle", "stateDiagram-v2", "Welche Native-Lifecycle-Grenzen sind tatsächlich implementiert?")],
    "06.05": [("Container-Aufbau", "flowchart", "Wie hängen Image, Container, Netz und Volumes zusammen?")],
    "06.07": [("Serverstart und Shutdown", "sequenceDiagram", "Welche Start-/Stopphasen sind beobachtbar?")],
    "06.10": [("Monitoring-Datenfluss", "flowchart", "Woher kommen Metriken, Health-Daten und Logs?")],
    "07.08": [("Kroko-Buildkette", "flowchart", "Welche verifizierbaren Eingänge und Artefakte umfasst der Native-Build?")],
    "07.10": [("RC-Qualifikation", "flowchart", "Welche Gates bestehen auf dem Release-Candidate-Pfad?")],
    "07.11": [("Release-State-Machine", "stateDiagram-v2", "Welche Release-Zustände und Freigabegates sind implementiert?")],
    "08.05": [("Zustandsautomaten-Übersicht", "stateDiagram-v2", "Welche echten State-Machines gibt es?")],
    "08.06": [("Zeitlinien und Fristen", "sequenceDiagram", "Welche Timer beeinflussen welchen fachlichen Ablauf?")],
    "09.03": [("V1-/V2-Abgrenzung", "flowchart", "Welche Endpunkte und Vertragsgrenzen sind jeweils gültig?")],
    "09.04": [("Client-Migrationspfad", "flowchart", "Welche nachweisbaren Schritte sind für die Umstellung erforderlich?")],
    "09.06": [("End-to-End-Szenario", "sequenceDiagram", "Welcher vollständige Praxisablauf lässt sich sicher belegen?")],
}

def write_once(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(data, encoding="utf-8", newline="\n")

def write_json_once(path: Path, obj) -> None:
    write_once(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")

def slug(value: str) -> str:
    value = value.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    value = "".join(x for x in unicodedata.normalize("NFKD", value) if not unicodedata.combining(x))
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value)).strip("-")

def load_outline():
    raw = SPEC.read_text(encoding="utf-8")
    assert "## C. Verbindliche Gesamtkapitelgliederung" in raw and "## D. Redaktionelle Gestaltungskriterien" in raw
    block = raw.split("## C. Verbindliche Gesamtkapitelgliederung", 1)[1].split("## D. Redaktionelle Gestaltungskriterien", 1)[0]
    groups = {}
    chapters = []
    current = None
    for line in block.splitlines():
        match = re.match(r"^### (\d{2}) – (.+)$", line)
        if match:
            current = match.group(1)
            groups[current] = match.group(2).strip()
        item = re.match(r"^- \*\*(\d{2}\.\d{2}) (.+?):\*\* (.+)$", line)
        if item:
            cid, title, scope = item.groups()
            assert cid[:2] == current, (cid, current)
            chapters.append((cid, title, scope))
    assert len(chapters) == 104 and len(groups) == 9, (len(chapters), len(groups))
    assert len({x[0] for x in chapters}) == len(chapters)
    return groups, chapters

def diagram_note(cid, title, scope):
    lines = [f"# Diagrammideen – {cid} {title}", "", "**Status:** Idee, noch keine Code-Verifikation.",
             "", "## Zugeordneter Kapitelumfang", "", scope, "",
             "## Vorschläge (redaktionell, keine bestätigten Aussagen)", ""]
    for idx, (name, kind, question) in enumerate(DIAGRAMS[cid], 1):
        lines += [f"### Idee {idx}: {name}", "", f"- **Mögliche Form:** {kind}",
                  f"- **Zu klärende Frage:** {question}", "- **Zielgruppe/Nutzen:** _(hier ergänzen)_",
                  "- **Eigene Wünsche und Ergänzungen:** _(hier ergänzen)_", "- **Unbedingt vermeiden:** unbelegte Phasen, Pfeile und Zahlen.", ""]
    lines += ["## Meine zusätzlichen Diagrammideen", "", "_Hier kannst du frei zusätzliche Darstellungswünsche oder Skizzen beschreiben._",
              "", "## Auftrag an Researcher", "", "Finde alle tatsächlich beteiligten Zustände, Events, Zeitbezüge und Übergänge im aktuellen Produktcode. "
              "Belege jede mögliche Diagrammkante mit einer Fakten-ID.", "",
              "## Review", "", "- [ ] Alle beschrifteten Übergänge und Pfeile belegt.",
              "- [ ] Keine historischen/entfernten Engines oder Pseudogarantien.",
              "- [ ] Mermaid rendert; ergänzender Erklärungstext vorhanden.", ""]
    return "\n".join(lines)

def note_text(cid, title, scope, diagram_ref):
    lines = [f"# Persönliche Hinweise – {cid} {title}", "",
             "**Diese Datei ist ausdrücklich für deine Ergänzungen gedacht.** "
             "Sie ist keine belegte technische Quelle und darf nicht ungeprüft als Implementierung übernommen werden.",
             "", "## Verbindliche Themen aus der Gliederung", "", scope, "",
             "## Meine inhaltlichen Wünsche", "", "_Hier ergänzen._", "",
             "## Praxisbeispiele, die ich gerne sehen würde", "", "_Hier ergänzen._", "",
             "## Besonders verständlich erklären", "", "_Hier ergänzen._", "",
             "## Was der Autor vermeiden soll", "", "_Hier ergänzen._", ""]
    if diagram_ref:
        lines += ["## Diagrammplanung", "", f"Siehe [{cid} Diagrammideen](../diagram-notes/{cid}.md).", ""]
    return "\n".join(lines)

def chapter_text(cid, title, scope, diagram):
    lines = [f"# {cid} – {title}", "", "> **Noch nicht recherchiert / nicht veröffentlicht.**",
             "> Technische Behauptungen dürfen erst nach Recherche aus aktuellem Code und unabhängiger Prüfung in dieses Kapitel.",
             "", "## Geplanter Umfang", "", scope, "", "## Was soll die Leserin oder der Leser hier verstehen?", "",
             "_Vom Writer anhand der geprüften Faktenakte ausarbeiten; Motivation, praktische Relevanz und ein verständliches Beispiel._",
             "", "## Nachgewiesene Funktionsweise", "", "_Noch nicht recherchiert._", "",
             "## Praxisbeispiel oder Ablauf", "", "_Noch nicht ausgearbeitet._", "",
             "## Grenzen, Fehlerfälle und Hinweise", "", "_Noch nicht untersucht._", ""]
    if diagram:
        lines += ["## Passende Schaubilder", "", "Für dieses Unterkapitel liegen redaktionelle Diagrammideen vor. "
                  "Erst nach belegter Code-Recherche als korrektes Mermaid-Diagramm umsetzen.", ""]
    lines += ["## Quellen und Referenzbelege", "", "_Noch keine verifizierten Fakten-IDs oder Quellstellen._", "",
              "## Redaktioneller Hinweis", "", f"Persönliche Ergänzungen stehen in der Arbeitsakte: {cid}.md.", ""]
    return "\n".join(lines)

def agents():
    research = """---
description: Recherchiert verifizierbare V2-Fakten ausschließlich anhand des aktuellen Implementierungscodes.
mode: subagent
model: opencode-go/muse-spark-1.3-contributor
permissions:
  - action: edit
    resource: "*"
    effect: deny
  - action: shell
    resource: "*"
    effect: deny
  - action: webfetch
    resource: "*"
    effect: deny
---
Du bist der DOC-Researcher. Dein Auftrag ergibt sich aus SPEZIFIKATION_v0.2.md und der Task-Registry.
Benutze **niemals** README, docs, alte Legacy-STT-Dokumente oder fremde Berichte als technische Wahrheitsquelle.
Untersuche den vom Orchestrator bestätigten exakten Git-Commit in Python-Code, Schemas, Routen-Registrierungen,
Tests, Build- und CI-Definitionen. Tests beweisen erwartetes Verhalten, Code ist die Implementierungsautorität.
Gib Fakten-ID, Pfad, Symbol, Evidenzstärke, Gültigkeitsbereich, Konflikte und NOT_IMPLEMENTED/UNKNOWN aus.
Kein Raten von Timeouts, Feldern, Defaultwerten oder Übergängen. Keine Dateibearbeitung; liefere die Faktenakte
als Text an den Orchestrator, damit er sie unter workflow/research/ ablegt.
"""
    writer = """---
description: Erstellt didaktische, praxisnahe Kapitel mit belegten Mermaid-Diagrammen.
mode: subagent
model: opencode-go/muse-spark-1.3-contributor
permissions:
  - action: edit
    resource: "*"
    effect: deny
  - action: shell
    resource: "*"
    effect: deny
---
Du bist der DOC-Writer. Lies das zugewiesene Unterkapitel, workflow/notes/<ID>.md und ggf. workflow/diagram-notes/<ID>.md.
Technische Fakten NUR aus der vom Orchestrator freigegebenen aktuellen Faktenakte und deren Codebelegen.
Nicht auf vorhandene Legacy-STT-Dokumentation zurückgreifen. Verfasse einen verständlichen Fachtext statt
einer bloßen Klassen-, Parameter- oder Faktensammlung: Wozu? Wie funktioniert es? Was bedeutet es praktisch?
Nutze passende nachvollziehbare Beispiele und Mermaid nur bei begründetem Mehrwert. Jede Diagrammkante
benötigt eine Fakten-ID. Markiere Schema/Pseudocode eindeutig und erkläre jedes Diagramm in Worten.
Gib einen vollständigen Kapitelentwurf an den Orchestrator zurück. Du nimmst dich selbst nicht ab.
"""
    review = """---
description: Prüft Dokumentation unabhängig und ausschließlich gegen Originalimplementierung und Schemas.
mode: subagent
model: opencode-go/deepseek-v4.1-flash
permissions:
  - action: edit
    resource: "*"
    effect: deny
  - action: shell
    resource: "*"
    effect: deny
---
Du bist der unabhängige DOC-Reviewer. Lies Kapitel, Faktenakte, Unterkapitelvorgabe und persönliche Notizen.
Prüfe alle relevanten technischen Aussagen SELBST gegen den zugehörigen Git-Commit im tatsächlichen Code,
nicht nur gegen die Faktenakte und niemals gegen alte Dokumentation. Prüfe Feldnamen, Defaults, Timing,
Kanten und Beschriftungen sämtlicher Diagramme, Beispiele, Grenzfälle und Gliederungsabdeckung.
Prüfe Verständlichkeit, Praxisnutzen, Terminologiekonsistenz und Querverweise.
Antworte mit PASS, CHANGES_REQUESTED oder ESCALATE und nummerierten Findings mit Severity,
präziser Belegstelle, erwarteter Korrektur und erneutem Prüfauftrag.
Ändere nie das von dir geprüfte Kapitel; keine Eigenabnahme des Autors.
"""
    orch = """---
description: Steuert den vollständigen 104-Kapitel-Dokumentationsworkflow mit getrennten Agenten und Reviewgates.
mode: primary
model: opencode-go/deepseek-v4.1-flash
permissions:
  - action: edit
    resource: "*"
    effect: allow
  - action: shell
    resource: "*"
    effect: ask
  - action: external_directory
    resource: "*"
    effect: ask
---
Du bist der DOC-Orchestrator. Arbeitsvertrag: SPEZIFIKATION_v0.2.md und AGENTS.md.
Kontrolliere vor jedem Auftrag die Registry und den exakten Git-Commit des Produktquellcodes.
Alle 104 IDs sind verpflichtend. Bearbeite zuerst 02.03 Activation als Pilot mit echter Recherche,
Lesbarkeit, Diagrammprüfung, unabhängigem Review, Korrektur und Integration.
Delegiere per Subagenten doc-researcher, doc-writer, doc-reviewer. Keine Selbstabnahme;
die Ergebnisse der Subagenten müssen als versionierte Artefakte in workflow/research/
bzw. workflow/reviews/ gesichert werden. Stelle strikte Faktentreue, sinnvolle Schaubilder
und die Katalog-Coverage sicher. Nach drei gescheiterten identischen Korrekturrunden ESCALATE
und Ursache klären, statt endlos zu wiederholen. Keine Produktcodeänderungen, keine Änderungen
bestehender Legacy-STT-Dokumentation, kein Git-Merge, Push oder Release ohne Freigabe.
Das Dokumentationsarbeitsverzeichnis ist separat vom Produkt-Repository; schreibe ausschließlich hier.
Ändere Status ausschließlich über kontrollierte Registry-Aktualisierung. COMPLETE nur nach
vollständig nachgewiesenem technischen Review und sämtlichen globalen Prüfgates.
Bei Unklarheit über die tatsächliche Quell-Worktree-Lage: vor Beginn auflösen, nicht raten.
"""
    return {"doc-orchestrator.md": orch, "doc-researcher.md": research,
            "doc-writer.md": writer, "doc-reviewer.md": review}

def main():
    groups, chapters = load_outline()
    for sub in ("notes", "diagram-notes", "research", "reviews", "reports", "templates", "pilot"):
        (WORK / sub).mkdir(parents=True, exist_ok=True)
    registry = []
    nav = ["# Geplante Dokumentation – 104 Unterkapitel", "",
           "> Dies sind vorbereitete Entwurfsdateien, **keine fertig recherchierte technische Dokumentation**.", ""]
    gl = ["# Verbindliche Gliederung", "",
          "Quelle: [Spezifikation V0.2](../SPEZIFIKATION_v0.2.md). "
          "Inhaltliche Beschreibungen sind Rechercheaufträge, keine technische Implementierungsbestätigung.", ""]
    for main_id, main_title in groups.items():
        nav += [f"## {main_id} – {main_title}", ""]
        gl += [f"## {main_id} – {main_title}", ""]
        for cid, title, scope in (c for c in chapters if c[0].startswith(main_id + ".")):
            fname = f"{cid}-{slug(title)}.md"
            docrel = f"docs/v2-handbuch/{PARTS[main_id]}/{fname}"
            note = f"workflow/notes/{cid}.md"
            dref = f"workflow/diagram-notes/{cid}.md" if cid in DIAGRAMS else None
            write_once(ROOT / docrel, chapter_text(cid, title, scope, dref))
            write_once(ROOT / note, note_text(cid, title, scope, dref))
            if dref:
                write_once(ROOT / dref, diagram_note(cid, title, scope))
            nav += [f"- [{cid} {title}]({PARTS[main_id]}/{fname})"]
            gl += [f"- **{cid} {title}:** {scope}  ",
                   f"  [Entwurf](../{docrel}) · [Eigene Hinweise](../{note})" +
                   (f" · [Diagrammideen](../{dref})" if dref else "")]
            registry.append({
                "id": cid, "title": title, "main_section": main_id, "scope": scope,
                "source_ref": "feat/v2-release-cleanup", "source_commit": None,
                "owner_role": None, "state": "PLANNED",
                "research_path": f"workflow/research/{cid}.json",
                "draft_path": docrel, "review_path": f"workflow/reviews/{cid}.md",
                "note_path": note, "diagram_brief_path": dref,
                "diagram_status": "IDEA" if dref else "NOT_REQUESTED",
                "findings": [], "correction_round": 0, "dependencies": [],
                "review_verdict": None, "acceptance_evidence": [],
                "integrated_path": None, "updated_at": None
            })
        nav.append("")
        gl.append("")
    write_once(DOC / "README.md", "\n".join(nav) + "\n")
    write_once(ROOT / "GLIEDERUNG.md", "\n".join(gl) + "\n")
    write_json_once(WORK / "task-registry.json", {
        "schema_version": 1, "plan_version": "0.2",
        "source_repository": "marcosudau-vps/voice-stt-server",
        "source_branch": "feat/v2-release-cleanup",
        "source_commit": None, "status_authority": "workflow/task-registry.json",
        "pilot_chapter": "02.03", "chapter_count": len(registry), "chapters": registry
    })
    write_json_once(WORK / "diagram-briefs.json", {
        "schema_version": 1, "note": "Künstlerische/redaktionelle Vorschläge, nicht als Implementierung verifiziert",
        "items": [{"id": cid, "status": "IDEA", "note_path": f"workflow/diagram-notes/{cid}.md",
                   "proposals": [{"title": p[0], "type": p[1], "research_question": p[2]} for p in proposal]}
                  for cid, proposal in DIAGRAMS.items()]
    })
    write_json_once(WORK / "coverage-matrix.json", {
        "schema_version": 1, "generated_from": "workflow/task-registry.json",
        "items": [{"id": c["id"], "state": "PLANNED", "researched": False,
                   "drafted": False, "reviewed": False, "integrated": False}
                  for c in registry]
    })
    write_json_once(WORK / "terminology.json", {"schema_version": 1, "terms": [],
                                                 "note": "Erst durch bestätigte Code-Recherche befüllen; keine alten Glossare kopieren."})
    write_once(WORK / "decisions.md", "# Entscheidungen\n\n- 2026-11-06: Vollständige Gliederung V0.2 mit 104 einzelnen Statusobjekten.\n"
               "- Recherche ausschließlich aus aktuellem Code, unabhängig geprüft.\n"
               "- Diagrammwünsche sind redaktionelle Ideen, keine Code-Fakten.\n"
               "- Kein bestehender Produktcode / keine alte Dokumentation geändert.\n")
    write_once(WORK / "master-plan.md", "# Gesamtplan\n\n1. Alle 104 Unterkapitel nach Spezifikation inventarisieren (angelegt).\n"
               "2. Quell-Worktree und aktuellen Commit **vor Recherche verifizieren**.\n"
               "3. Pilot 02.03 Activation: Research → Writer → unabhängiger Review → Korrektur → Integration.\n"
               "4. Weitere Kapitel abhängigkeitsschonend delegieren, keine parallele Bearbeitung derselben Datei.\n"
               "5. Kataloge mechanisch gegen Code/Schemas/Routen prüfen; Links und Mermaid prüfen.\n"
               "6. Gesamtprüfung; nur REVIEW_READY, kein automatischer Merge oder Release.\n"
               "\n**Explizite Grenze:** Die Arbeitsdateien liegen im lokalen Planungsordner, nicht auf einem Git-Arbeitsbranch.\n")
    write_once(WORK / "README.md", "# Arbeitsakten und Statuspflege\n\n"
               "**Einzige Statusautorität:** task-registry.json. coverage-matrix.json wird daraus mit tools/workflow_cli.py refresh neu erzeugt.\n\n"
               "Die Dateien unter notes/ gehören dem Auftraggeber und dürfen vor und während der Arbeit ergänzt werden.\n"
               "Die Dateien unter diagram-notes/ enthalten zunächst rein redaktionelle Visualisierungsideen.\n"
               "Researcher nutzen NUR Implementierung, Schemas, Tests und echte Build-/CI-Konfigurationen; nie alte Dokumente.\n\n"
               "Jede Faktenakte und jeder Review nennt den exakten Quell-Commit. "
               "Nie PLACEHOLDER als abgenommene technische Dokumentation ausgeben.\n\n"
               "Status: PLANNED → RESEARCHED → DRAFTED → IN_REVIEW → ACCEPTED → INTEGRATED. "
               "Bei Fehlern CHANGES_REQUESTED, nach drei erfolglosen Runden ESCALATE.\n")
    write_once(WORK / "pilot" / "02.03-activation.md", "# Pilotplan 02.03 Activation\n\n"
               "Ziel: ersten vollständigen Agentenworkflow nachweisbar erproben, bevor parallelisiert wird.\n\n"
               "- [ ] HEAD des aktuellen Cleanup-Quellworktrees kontrollieren.\n"
               "- [ ] Code-Recherche mit Fakten-IDs und gesonderter Akte durchführen.\n"
               "- [ ] Persönliche Hinweise in workflow/notes/02.03.md und Diagrammideen lesen.\n"
               "- [ ] Zustands- und Sequenzdiagramm nur mit belegten Kanten erstellen.\n"
               "- [ ] Unabhängig gegen Code prüfen, ggf. Korrektur und erneuter Review.\n"
               "- [ ] Registry nur bei echter Evidenz auf ACCEPTED/INTEGRATED setzen.\n")
    for sub, msg in {
        "research": "Eine Faktenakte je ID; Pfad, Symbol, Commit und Evidenzklasse zwingend.",
        "reviews": "Reviewerberichte je ID, strikt getrennt vom Autor, mit PASS/CHANGES_REQUESTED/ESCALATE.",
        "reports": "Meilenstein-, Gate- und Gesamtberichte sowie Abnahmeprotokolle.",
        "notes": "104 frei editierbare Unterkapitelhinweise des Auftraggebers.",
        "diagram-notes": "Diagramm-Wunschzettel je ausgewähltem Unterkapitel; kein Beweis implementierter Zustände."
    }.items():
        write_once(WORK / sub / "README.md", "# " + sub + "\n\n" + msg + "\n")
    write_once(WORK / "templates" / "research-template.md", "# Faktenakte <ID>\n\n"
               "Quellcommit: <SHA>\n\n## Fakten mit IDs\n\n| ID | Aussage | Pfad/Symbol | Evidenzklasse | Unsicherheit |\n"
               "|---|---|---|---|---|\n\n## Relevante States/Events/Defaults\n\n## Explizite NOT_IMPLEMENTED/UNKNOWN/CONFLICT\n\n"
               "## Belegbare Diagrammkanten\n")
    write_once(WORK / "templates" / "review-template.md", "# Unabhängiger Review <ID>\n\n"
               "Quellcommit: <SHA>\n\nUrteil: PASS / CHANGES_REQUESTED / ESCALATE\n\n"
               "## Befunde\n\n| Finding | Severity | Behauptung | Gegenbeleg im Code | Korrektur |\n"
               "|---|---|---|---|---|\n\n## Diagramm- und Beispielprüfung\n\n## Abdeckung und Lesbarkeit\n")
    write_once(WORK / "templates" / "diagram-template.md", "# Diagrammbrief <ID>\n\n"
               "Form: flowchart / sequenceDiagram / stateDiagram-v2\n\n"
               "Leserfrage:\n\nBelegte Zustände/Kanten (Fakten-IDs):\n\n"
               "Entwurfsnotizen:\n\nTextalternative:\n\nReviewerbestätigung:\n")
    for name, body in agents().items():
        write_once(AGENTS / name, body)
    write_once(ROOT / "AGENTS.md", "# Verbindliche Regeln für Agenten\n\n"
               "Erst SPEZIFIKATION_v0.2.md und workflow/master-plan.md lesen.\n"
               "Für alle 104 Kapitel jeweils Registry-Status und persönliche Hinweise beachten.\n"
               "Codequelle ist ein separat zu identifizierender aktueller Checkout des Repositories.\n"
               "Researcher dürfen vorhandene Dokumentation als technische Evidenz nicht verwenden.\n"
               "Writer schreiben gut verständliche, praxisnahe und diagrammgestützte Kapitel, "
               "Diagramme nur nach Quellenverifikation. Reviewer unabhängig.\n"
               "Keine Änderungen außerhalb dieses lokalen Arbeitsordners; keine Remote-/Git-Aktionen ohne Freigabe.\n"
               "SPEZIFIKATION_v0.2.md hat Vorrang vor allgemeinen Agententexten.\n")
    write_once(ROOT / "OPEN_CODE_EINRICHTUNG.md",
               "# OpenCode V2: Vorbereitete Agenten\n\n"
               "Auf diesem PC wurde OpenCode v2.2.5 festgestellt. Die vorbereiteten vier Agenten liegen "
               "projektlokal unter .opencode/agents/.\n\n"
               "Modelle nach der tatsächlich verfügbaren Liste:\n\n"
               "- Orchestrator & Reviewer: opencode-go/deepseek-v4.1-flash\n"
               "- Researcher & Writer: opencode-go/muse-spark-1.3-contributor\n\n"
               "Diese Konfiguration wurde **noch nicht in einem echten Subagent-Lauf getestet**. "
               "Beim Start prüfe Agentenauswahl, Modellzugriff, Berechtigungssemantik und Worktree-Zugriff.\n\n"
               "Achtung: Der Dokumentationsordner ist kein vollständiger Git-Quellcheckout. "
               "Die Produktquellen müssen als aktueller Git-Worktree auf feat/v2-release-cleanup "
               "explizit identifiziert und lesend eingebunden werden. Die Pfade aus workspaces/ "
               "dürfen nicht einfach als aktueller Stand vorausgesetzt werden.\n\n"
               "Agentenprofile allein liefern keine harte Filesystem-Sandbox. "
               "Vor autonomer Bearbeitung Schreibzugriffe auf diesen Ordner begrenzen, "
               "keine produktiven Commits/Pushes zulassen und die Pilotrecherche separat testen.\n")
    write_once(ROOT / "README.md",
               "# Voice-STT-V2 – lokaler Dokumentationsarbeitsplatz\n\n"
               "**Stand:** Vollständig angelegte Planung, noch keine inhaltliche Code-Recherche, "
               "**kein fertiges Handbuch**.\n\n"
               "- [Verbindliche Spezifikation](SPEZIFIKATION_v0.2.md)\n"
               "- [Komplette Gliederung mit 104 Kapiteln](GLIEDERUNG.md)\n"
               "- [Vorbereitete Dokumentationsdateien](docs/v2-handbuch/README.md)\n"
               "- [Task-Registry](workflow/task-registry.json)\n"
               "- [Diagrammideen](workflow/diagram-briefs.json)\n"
               "- [Arbeitsakten und Statusverfahren](workflow/README.md)\n"
               "- [OpenCode-Einrichtung](OPEN_CODE_EINRICHTUNG.md)\n"
               "- [Pilot Activation](workflow/pilot/02.03-activation.md)\n\n"
               "## Eigene Ergänzungen\n\n"
               "Jedes Unterkapitel besitzt workflow/notes/<ID>.md. Dort kannst du "
               "Wünsche, Beispiele, mögliche Schaubilder und erläuterungsbedürftige Punkte frei ergänzen.\n"
               f"Für {len(DIAGRAMS)} ausgewählte Kapitel gibt es zusätzliche "
               "workflow/diagram-notes/<ID>.md mit konkreten Visualisierungsvorschlägen.\n\n"
               "## Status prüfen\n\n"
               "Im lokalen Ordner: python tools/workflow_cli.py validate\n\n"
               "Danach: python tools/workflow_cli.py status\n\n"
               "Es wurde kein Coding-Agent gestartet; der bestehende Server-Quellcode "
               "und PR #18 bleiben unverändert.\n")
    # Nur beim Initialisieren das Workflow-Skript anlegen; bestehende Dateien bleiben erhalten.
    print(f"SUCCESS chapters={len(chapters)} groups={len(groups)} diagram_chapters={len(DIAGRAMS)} "
          f"files={sum(1 for p in ROOT.rglob('*') if p.is_file())}")

if __name__ == "__main__":
    main()
