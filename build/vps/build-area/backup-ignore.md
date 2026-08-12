# Nicht sichern / automatisch reproduzierbar

- `.venv/`
- `kroko-build/`
- `workdir/`
- `artifacts/`
- `history_versions/`
- `.pytest_cache/`
- `__pycache__/`
- `*.log`

Modelle und Secrets gehoeren ebenfalls nicht in Build-Area-Backups. Sie werden
ueber die separaten Selfhost-Modell- und Secret-Pfade verwaltet.
