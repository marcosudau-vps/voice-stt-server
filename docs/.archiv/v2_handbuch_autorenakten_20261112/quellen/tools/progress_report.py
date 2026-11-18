"""Einfache Fortschrittsanzeige aus der verbindlichen Task-Registry."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "workflow" / "task-registry.json"
OUTPUT = ROOT / "workflow" / "PROGRESS.md"
STATES = {
    "PLANNED": "Geplant",
    "RESEARCHED": "Recherchiert",
    "DRAFTED": "Entwurf erstellt",
    "IN_REVIEW": "Im Review",
    "CHANGES_REQUESTED": "Korrektur angefordert",
    "ACCEPTED": "Review bestanden",
    "INTEGRATED": "Integriert",
    "ESCALATE": "Eskalation",
}
GROUP_NAMES = {
    "01": "Einstieg und Systemverständnis",
    "02": "Funktionsweise und interne Abläufe",
    "03": "Einstellungen und Konfiguration",
    "04": "Schnittstellen und Client-Integration",
    "05": "Administration und Sicherheit",
    "06": "Installation, Betrieb und Diagnose",
    "07": "Entwicklung, Tests, Build und Release",
    "08": "Kataloge und technische Referenzen",
    "09": "Anhänge und Kompatibilität",
}

def generate_progress(items=None):
    """Erstellt PROGRESS.md; verändert keine Aufgaben- oder Reviewdaten."""
    if items is None:
        items = json.loads(REGISTRY.read_text(encoding="utf-8"))["chapters"]
    total = len(items)
    count = Counter(chapter["state"] for chapter in items)
    done = count["INTEGRATED"]
    active = [chapter for chapter in items
              if chapter["state"] not in ("PLANNED", "INTEGRATED")]
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    progress = round(30 * done / total) if total else 0
    lines = [
        "# Voice-STT V2 – Dokumentationsfortschritt",
        "",
        "**Diese Datei wird automatisch aus der Task-Registry generiert. "
        "Bitte die Checkboxen nicht manuell bearbeiten.**",
        "",
        f"Letzte Aktualisierung: {timestamp}",
        "",
        f"## {done} von {total} Kapiteln abgeschlossen ({done / total * 100:.1f} %)",
        "",
        "[" + "█" * progress + "░" * (30 - progress) + "]",
        "",
        f"- Fertig und integriert: **{done}**",
        f"- Noch offen: **{total - done}**",
        f"- In Bearbeitung / Review: **{len(active)}**",
        f"- Noch nicht begonnen: **{count['PLANNED']}**",
        "",
        "### Statusübersicht",
        "",
        "| Status | Anzahl |",
        "|---|---:|",
    ]
    lines += [f"| {label} | {count[state]} |" for state, label in STATES.items()]
    lines += ["", "## Gerade in Bearbeitung", ""]
    if active:
        for item in active:
            lines.append(f"- **{item['id']} {item['title']}** – "
                         f"{STATES.get(item['state'], item['state'])} "
                         f"([Kapitel](../{item['draft_path']}))")
    else:
        lines.append("_Aktuell kein Kapitel in einem Zwischenstatus._")
    lines += ["", "## Vollständige Checkliste", "",
              "Ein Häkchen erscheint ausschließlich bei Status INTEGRATED. "
              "Die externe ROOT-Abnahme ist ein separater späterer Lauf.", ""]
    for group in sorted(set(c["main_section"] for c in items)):
        subset = [c for c in items if c["main_section"] == group]
        completed = sum(c["state"] == "INTEGRATED" for c in subset)
        lines += [f"### {group} – {GROUP_NAMES.get(group, 'Bereich')} "
                  f"({completed}/{len(subset)})", ""]
        for item in subset:
            mark = "x" if item["state"] == "INTEGRATED" else " "
            extra = (f" · [Diagrammideen](diagram-notes/{item['id']}.md)"
                     if item.get("diagram_brief_path") else "")
            lines.append(f"- [{mark}] **{item['id']}** "
                         f"[{item['title']}](../{item['draft_path']}) "
                         f"— {STATES.get(item['state'], item['state'])}{extra}")
        lines.append("")
    lines += [
        "## Aktualisierung",
        "",
        "Die Übersicht aktualisiert sich bei jeder kontrollierten Statusänderung "
        "über workflow_cli.py und bei jedem Aufruf von workflow_cli.py refresh. "
        "Nach jeder Arbeitscharge muss der Orchestrator diesen Refresh ausführen.",
        "",
        "Die verbindliche Statusquelle bleibt workflow/task-registry.json. "
        "Ein Häkchen allein ist kein Beweis für technische Korrektheit.",
        "",
    ]
    OUTPUT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return OUTPUT

if __name__ == "__main__":
    print("Aktualisiert:", generate_progress())
