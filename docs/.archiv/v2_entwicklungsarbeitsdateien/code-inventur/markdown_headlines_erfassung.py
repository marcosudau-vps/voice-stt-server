import os
import csv
import re
from pathlib import Path

# === EINGABE-PARAMETER ===
PROJECT_DIR = "."  # Pfad zum Projektordner
EXCLUDE_PATTERN = ["test_", ".git", "node_modules", ".obsidian"]
# =========================

def should_exclude(filepath, exclude_patterns):
    # Den kompletten Pfad als String prüfen, damit auch Ordnernamen matchen
    path_str = filepath.as_posix()
    for pattern in exclude_patterns:
        if pattern in path_str:
            return True
    return False

def parse_markdown_content(filepath):
    yaml_lines = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception:
        return yaml_lines, 0

    line_count = len(lines)
    in_code_block = False

    # Regex für Markdown-Überschriften (1 bis 6 Rauten gefolgt von Leerzeichen)
    heading_pattern = re.compile(r'^(#{1,6})\s+(.*)')

    for line in lines:
        stripped = line.strip()

        # Code-Blöcke umschalten (damit '#'-Kommentare in Code-Blöcken ignoriert werden)
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        # Überschriften prüfen
        match = heading_pattern.match(stripped)
        if match:
            hashes = match.group(1)
            title = match.group(2)

            # Die Anzahl der Rauten bestimmt das Level (1 bis 6)
            # Level 1 (#) = 1 Einrückung (2 Leerzeichen) für die Hierarchie unter dem Dateinamen
            level = len(hashes)
            indent = "  " * level

            yaml_lines.append(f"{indent}{hashes} {title}")

    return yaml_lines, line_count

def main():
    project_path = Path(PROJECT_DIR).resolve()

    csv_filename = "all_md_files.csv"
    yaml_filename = "md_content_overview.yaml"

    csv_header = ["ID", "Dateiname", "Parent_Ordner", "Relativer_Pfad", "Anzahl_Zeilen"]
    csv_data = []
    all_yaml_content = []
    md_files = []

    # Rekursiv iterieren (nach .md Dateien)
    for filepath in project_path.rglob("*.md"):
        if filepath.is_file() and not should_exclude(filepath, EXCLUDE_PATTERN):
            md_files.append(filepath)

    # Sortieren für eine saubere und nachvollziehbare Abfolge
    md_files.sort()
    file_id_counter = 1

    for filepath in md_files:
        stem = filepath.stem
        try:
            rel_path = filepath.relative_to(project_path)
        except ValueError:
            rel_path = filepath

        parent_folder = rel_path.parent.name if rel_path.parent.name else "root"
        file_id_str = f"{file_id_counter:04d}"

        yaml_lines, line_count = parse_markdown_content(filepath)

        csv_data.append([file_id_str, stem, parent_folder, str(rel_path.as_posix()), line_count])

        # Zwei Leerzeilen vor jeder NEUEN Datei (außer vor der allerersten)
        if file_id_counter > 1:
            all_yaml_content.append("")
            all_yaml_content.append("")

        # Datei-Header
        all_yaml_content.append(f"[@{file_id_str}] {filepath.name}:")
        all_yaml_content.extend(yaml_lines)

        file_id_counter += 1

    # Dateiausgabe
    with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(csv_header)
        writer.writerows(csv_data)

    with open(yaml_filename, 'w', encoding='utf-8') as f:
        for line in all_yaml_content:
            f.write(line + "\n")

    print(f"Erfolgreich {file_id_counter - 1} Markdown-Dateien gescannt.")
    print(f" - {csv_filename} erstellt.")
    print(f" - {yaml_filename} erstellt.")

if __name__ == "__main__":
    main()
