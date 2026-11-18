import os
import csv
import re
from pathlib import Path

# === EINGABE-PARAMETER ===
PROJECT_DIR = r"P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\restructure_cleanup\voice-stt-server\tests"  # Pfad zum Projektordner
# EXCLUDE_PATTERN = ["test_", "__init__", "venv", ".git", "__pycache__", "cache", "app_"]
EXCLUDE_PATTERN = ["__init__", "venv", ".git", "__pycache__", "cache", "app_"]
ADD_COMMENTS = True
# =========================

def should_exclude(filepath, exclude_patterns):
    # Den kompletten Pfad als String prüfen, damit auch Ordnernamen matchen
    path_str = filepath.as_posix()
    for pattern in exclude_patterns:
        if pattern in path_str:
            return True
    return False

def get_yaml_indent(expanded_line):
    # Python-Einrückung auslesen (4 Leerzeichen = 1 Ebene)
    indent_spaces = len(expanded_line) - len(expanded_line.lstrip(' '))
    # +1 Ebene (2 Leerzeichen extra), da der Inhalt dem Datei-Header untergeordnet ist
    yaml_level = (indent_spaces // 4) + 1
    return "  " * yaml_level

def parse_file_content(filepath, add_comments):
    yaml_lines = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception:
        return yaml_lines, 0

    line_count = len(lines)

    in_multiline_string = False
    string_delimiter = ""
    multiline_buffer = []
    just_saw_method = False
    just_saw_method_docstring = False
    current_indent = ""

    for line in lines:
        expanded_line = line.expandtabs(4)
        stripped = expanded_line.strip()

        if not stripped:
            continue

        # --- 1. Mehrzeilige Strings (Block-Kommentare/Docstrings) verarbeiten ---
        if in_multiline_string:
            if string_delimiter in stripped:
                # Ende des multiline Strings gefunden
                idx = stripped.find(string_delimiter)
                multiline_buffer.append(stripped[:idx + 3])

                # Alles zu einer einzigen Zeile zusammenfügen (mit sichtbarem \n)
                combined = "\\n".join(multiline_buffer)
                if add_comments:
                    if just_saw_method_docstring:
                        combined = combined.replace(string_delimiter, f"{string_delimiter} DocString: ", 1)
                    yaml_lines.append(f"{current_indent}{combined}")

                in_multiline_string = False
                just_saw_method = False
            else:
                multiline_buffer.append(stripped)
            continue

        current_indent = get_yaml_indent(expanded_line)

        # --- 2. Start eines potenziell mehrzeiligen Strings prüfen ---
        if stripped.startswith('"""') or stripped.startswith("'''"):
            delimiter = stripped[:3]
            # Prüfen ob er direkt in derselben Zeile wieder geschlossen wird
            if stripped.endswith(delimiter) and len(stripped) > 3:
                if add_comments:
                    val = stripped
                    if just_saw_method:
                        val = val.replace(delimiter, f"{delimiter} DocString: ", 1)
                    yaml_lines.append(f"{current_indent}{val}")
                just_saw_method = False
            else:
                in_multiline_string = True
                string_delimiter = delimiter
                multiline_buffer = [stripped]
                just_saw_method_docstring = just_saw_method
            continue

        # --- 3. Klassen ---
        if stripped.startswith("class "):
            yaml_lines.append("") # Gewünschte Leerzeile vor der Klasse
            yaml_lines.append(f"{current_indent}{stripped}")
            just_saw_method = False
            continue

        # --- 4. Methoden ---
        if stripped.startswith("def "):
            yaml_lines.append(f"{current_indent}{stripped}")
            just_saw_method = True
            continue

        # Wenn die aktuelle Zeile weder Methode noch Docstring war, Flag für Docstrings zurücksetzen
        just_saw_method = False

        # --- 5. Konstanten (Großbuchstaben) ---
        match_const = re.match(r'^([A-Z_][A-Z0-9_]*)(?:\s*:\s*[A-Za-z0-9_\[\], ]+)?\s*=\s*(.+)', stripped)
        if match_const:
            name = match_const.group(1)
            val = match_const.group(2)
            if val:
                char = val[0]
                closures = {'[': ']', '{': '}', '(': ')', '"': '"', "'": "'"}
                if char in closures:
                    val_rep = f"{char}...{closures[char]}"
                else:
                    val_rep = char
                yaml_lines.append(f"{current_indent}{name} = {val_rep}")
            continue

        # --- 6. Kommentare ---
        if add_comments:
            if stripped.startswith("#"):
                yaml_lines.append(f"{current_indent}{stripped}")
            elif "#" in stripped:
                # Inline-Kommentare abtrennen
                parts = stripped.split("#", 1)
                if len(parts) > 1:
                    comment = parts[1].strip()
                    yaml_lines.append(f"{current_indent}# {comment}")

    return yaml_lines, line_count

def main():
    project_path = Path(PROJECT_DIR).resolve()

    csv_filename = "all_py_files_tests.csv"
    yaml_filename = "content_overview_tests.yaml"

    # CSV Header (Anzahl Zeilen stand im Prompt zweimal, hier der Übersichtlichkeit halber 1x am Ende)
    csv_header = ["ID", "Dateiname", "Parent_Ordner", "Relativer_Pfad", "Anzahl_Zeilen"]
    csv_data = []
    all_yaml_content = []
    py_files = []

    # Rekursiv iterieren
    for filepath in project_path.rglob("*.py"):
        if filepath.is_file() and not should_exclude(filepath, EXCLUDE_PATTERN):
            py_files.append(filepath)

    # Sortieren für eine saubere und nachvollziehbare Abfolge
    py_files.sort()
    file_id_counter = 1

    for filepath in py_files:
        stem = filepath.stem
        try:
            rel_path = filepath.relative_to(project_path)
        except ValueError:
            rel_path = filepath

        parent_folder = rel_path.parent.name if rel_path.parent.name else "root"
        file_id_str = f"{file_id_counter:04d}"

        yaml_lines, line_count = parse_file_content(filepath, ADD_COMMENTS)

        csv_data.append([file_id_str, stem, parent_folder, str(rel_path.as_posix()), line_count])

        # Leerzeile vor jeder NEUEN Datei (außer vor der allerersten)
        if file_id_counter > 1:
            all_yaml_content.append("")

        # Datei-Header mit angehängtem Doppelpunkt, damit gängige Editoren es als sauberes YAML interpretieren
        # all_yaml_content.append(f"[@{file_id_str}] {filepath.name}:")
        all_yaml_content.append(f"{file_id_str} - {filepath.name}:")
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

    print(f"Erfolgreich {file_id_counter - 1} Dateien gescannt.")
    print(f" - {csv_filename} erstellt.")
    print(f" - {yaml_filename} erstellt.")

if __name__ == "__main__":
    main()
