from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from progress_report import generate_progress

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "workflow"
REGISTRY = WORK / "task-registry.json"
COVERAGE = WORK / "coverage-matrix.json"
DIAGRAMS = WORK / "diagram-briefs.json"
VALID_STATES = (
    "PLANNED", "RESEARCHED", "DRAFTED", "IN_REVIEW",
    "CHANGES_REQUESTED", "ACCEPTED", "INTEGRATED", "ESCALATE"
)
NEXT = {
    "PLANNED": {"RESEARCHED"},
    "RESEARCHED": {"DRAFTED", "ESCALATE"},
    "DRAFTED": {"IN_REVIEW", "ESCALATE"},
    "IN_REVIEW": {"CHANGES_REQUESTED", "ACCEPTED", "ESCALATE"},
    "CHANGES_REQUESTED": {"RESEARCHED", "DRAFTED", "ESCALATE"},
    "ACCEPTED": {"INTEGRATED", "CHANGES_REQUESTED"},
    "INTEGRATED": {"CHANGES_REQUESTED"},
    "ESCALATE": {"PLANNED", "RESEARCHED"},
}

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def save_json(path: Path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

def chapters():
    obj = load_json(REGISTRY)
    return obj, obj["chapters"]

def require_chapter(items, cid):
    for x in items:
        if x["id"] == cid:
            return x
    raise SystemExit(f"Unbekannte Kapitel-ID: {cid}")

def coverage_rows(items):
    return [{
        "id": c["id"], "state": c["state"],
        "researched": c["state"] in ("RESEARCHED", "DRAFTED", "IN_REVIEW", "ACCEPTED", "INTEGRATED", "CHANGES_REQUESTED"),
        "drafted": c["state"] in ("DRAFTED", "IN_REVIEW", "ACCEPTED", "INTEGRATED", "CHANGES_REQUESTED"),
        "reviewed": c["state"] in ("ACCEPTED", "INTEGRATED"),
        "integrated": c["state"] == "INTEGRATED",
    } for c in items]

def refresh():
    _, items = chapters()
    save_json(COVERAGE, {
        "schema_version": 1, "generated_from": "workflow/task-registry.json",
        "items": coverage_rows(items)
    })
    briefs = load_json(DIAGRAMS)["items"]
    note = ["# Diagrammideen – editierbarer Index", "",
            "**Unbestätigte Vorschläge.** Mermaid-Diagramme erst nach belegter Code-Recherche erstellen.", ""]
    for row in briefs:
        cid = row["id"]
        c = require_chapter(items, cid)
        note.append(f"## {cid} – {c['title']}")
        note.append(f"**Status:** {c['diagram_status']} · "
                    f"[Notizen](diagram-notes/{cid}.md) · "
                    f"[Kapitel](../{c['draft_path']})")
        for p in row["proposals"]:
            note.append(f"- **{p['title']}** ({p['type']}): {p['research_question']}")
        note.append("")
    (WORK / "DIAGRAMM-IDEEN.md").write_text("\n".join(note) + "\n", encoding="utf-8", newline="\n")
    generate_progress(items)
    print(f"Coverage, Diagrammindex und PROGRESS.md aktualisiert: {len(items)} Kapitel, {len(briefs)} Diagrammplanungen")

def validate():
    obj, items = chapters()
    errors = []
    if len(items) != 104 or obj.get("chapter_count") != 104:
        errors.append(f"Erwartet 104 Kapitel, vorhanden {len(items)}")
    ids = [c["id"] for c in items]
    if len(set(ids)) != len(ids):
        errors.append("Doppelte Kapitel-IDs")
    groups = set()
    for item in items:
        cid = item["id"]
        if not re.fullmatch(r"0[1-9]\.\d\d", cid):
            errors.append(f"Ungültige ID {cid}")
        groups.add(cid.split(".")[0])
        if item.get("state") not in VALID_STATES:
            errors.append(f"{cid}: Unbekannter Status")
        for key in ("note_path", "draft_path"):
            if not (ROOT / item[key]).is_file():
                errors.append(f"{cid}: Datei fehlt: {item[key]}")
        if item.get("diagram_brief_path") and not (ROOT / item["diagram_brief_path"]).is_file():
            errors.append(f"{cid}: Diagrammnotiz fehlt")
        if item["state"] in ("ACCEPTED", "INTEGRATED"):
            if not (item.get("source_commit") and item.get("review_verdict") == "PASS"
                    and item.get("acceptance_evidence")):
                errors.append(f"{cid}: Akzeptierter Status ohne Commit/Review PASS/Evidenz")
            if not (ROOT / item["review_path"]).is_file():
                errors.append(f"{cid}: Review-Akte fehlt")
        if item["state"] == "INTEGRATED" and not item.get("integrated_path"):
            errors.append(f"{cid}: Integration ohne Zielpfad")
    if groups != set(f"{i:02}" for i in range(1, 10)):
        errors.append(f"Ungültige Hauptbereiche: {sorted(groups)}")
    diags = load_json(DIAGRAMS)["items"]
    dids = [d["id"] for d in diags]
    if len(set(dids)) != len(dids):
        errors.append("Doppelte Diagramm-ID")
    for entry in diags:
        if entry["id"] not in ids:
            errors.append("Diagramm-Referenz ohne Kapitel: " + entry["id"])
        if not (ROOT / entry["note_path"]).is_file():
            errors.append("Diagrammnotiz fehlt: " + entry["note_path"])
    for path in (ROOT / "SPEZIFIKATION_v0.2.md",
                 ROOT / ".opencode/agents/doc-orchestrator.md",
                 ROOT / ".opencode/agents/doc-researcher.md",
                 ROOT / ".opencode/agents/doc-writer.md",
                 ROOT / ".opencode/agents/doc-reviewer.md"):
        if not path.is_file():
            errors.append("Erwartete Basisdatei fehlt: " + str(path.relative_to(ROOT)))
    if COVERAGE.is_file():
        coverage = load_json(COVERAGE)
        if coverage.get("items") != coverage_rows(items):
            errors.append("Coverage-Matrix nicht synchron: refresh ausführen")
    else:
        errors.append("Coverage-Matrix fehlt")
    if errors:
        print("VALIDIERUNG FEHLGESCHLAGEN:")
        for error in errors:
            print(" - " + error)
        raise SystemExit(1)
    print(f"VALIDIERUNG OK: {len(items)} Kapitel / {len(groups)} Hauptbereiche / "
          f"{len(diags)} Diagramm-Notizen / keine fehlenden Dateien")

def status():
    _, items = chapters()
    print(f"Kapitel insgesamt: {len(items)}")
    print("Status:", ", ".join(f"{k}={v}" for k, v in Counter(x["state"] for x in items).items()))
    for section in sorted(set(x["main_section"] for x in items)):
        local = [x for x in items if x["main_section"] == section]
        active = [x for x in local if x["state"] != "PLANNED"]
        print(f"  {section}: {len(local)} Kapitel, {len(active)} begonnen")
    print("Pilot:", require_chapter(items, "02.03")["state"])

def set_state(cid, target, commit=None, evidence=None):
    obj, items = chapters()
    entry = require_chapter(items, cid)
    old = entry["state"]
    if target == old:
        print(f"Unverändert: {cid} {old}")
        return
    if target not in NEXT[old]:
        raise SystemExit(f"Unzulässiger Übergang {old} → {target} für {cid}")
    if commit:
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise SystemExit("Commit muss ein vollständiger 40-stelliger Git-SHA sein.")
        entry["source_commit"] = commit
    if evidence:
        entry["acceptance_evidence"].append(evidence)
    if target == "ACCEPTED":
        if entry.get("review_verdict") != "PASS" or not entry.get("source_commit") or not entry["acceptance_evidence"]:
            raise SystemExit("ACCEPTED erfordert Review-Vermerk PASS, Quellcommit und Abnahme-Evidenz.")
        if not (ROOT / entry["review_path"]).is_file():
            raise SystemExit("ACCEPTED erfordert einen existierenden Reviewerbericht.")
    if target == "RESEARCHED" and not entry.get("source_commit"):
        raise SystemExit("RESEARCHED erfordert den bestätigten Quellcommit (--commit).")
    entry["state"] = target
    save_json(REGISTRY, obj)
    refresh()
    print(f"{cid}: {old} → {target}")

def review(cid, verdict, evidence):
    obj, items = chapters()
    entry = require_chapter(items, cid)
    if verdict not in ("PASS", "CHANGES_REQUESTED", "ESCALATE"):
        raise SystemExit("Reviewurteil unbekannt.")
    if not evidence:
        raise SystemExit("Review benötigt einen Beleg- oder Berichtverweis.")
    if not (ROOT / entry["review_path"]).is_file():
        raise SystemExit("Reviewbericht-Datei muss existieren.")
    entry["review_verdict"] = verdict
    entry["acceptance_evidence"].append(evidence)
    save_json(REGISTRY, obj)
    refresh()
    print(f"{cid}: Reviewerurteil {verdict} gespeichert (Status separat setzen).")

def main():
    p = argparse.ArgumentParser(description="Voice-STT-Doku-Orchestrierung: Initiales Statuswerkzeug")
    commands = p.add_subparsers(dest="cmd", required=True)
    for name in ("validate", "refresh", "status", "progress"):
        commands.add_parser(name)
    s = commands.add_parser("set-status")
    s.add_argument("chapter_id")
    s.add_argument("new_state", choices=VALID_STATES)
    s.add_argument("--commit", default=None)
    s.add_argument("--evidence", default=None)
    r = commands.add_parser("review")
    r.add_argument("chapter_id")
    r.add_argument("verdict", choices=("PASS", "CHANGES_REQUESTED", "ESCALATE"))
    r.add_argument("--evidence", required=True)
    args = p.parse_args()
    if args.cmd == "validate":
        validate()
    elif args.cmd == "refresh":
        refresh()
    elif args.cmd == "status":
        status()
    elif args.cmd == "progress":
        print("Fortschrittsdatei:", generate_progress())
    elif args.cmd == "set-status":
        set_state(args.chapter_id, args.new_state, args.commit, args.evidence)
    elif args.cmd == "review":
        review(args.chapter_id, args.verdict, args.evidence)

if __name__ == "__main__":
    main()
