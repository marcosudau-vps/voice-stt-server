# Immer sichern / fuer einen Restore erforderlich

- `requirements.txt`
- `restore-venv.sh`
- `backup-ignore.md`
- `backup-keep.md`

Der eigentliche STT-Quellcode liegt im separaten Git-Repository unter
`/home/marco/selfhost/apps/services/voice/voice-stt-server`. Die venv und der
Kroko-Pro-Build werden mit `restore-venv.sh` reproduzierbar neu aufgebaut.
