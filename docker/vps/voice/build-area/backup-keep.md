# Immer sichern / für einen Restore erforderlich

- `requirements.txt`
- `restore-venv.sh`
- `backup-ignore.md`
- `backup-keep.md`

Der eigentliche STT-Quellcode liegt im versionierten Selfhost-Repository unter
`/home/marco/selfhost/apps/services/voice/stt-voice`. Die venv und der
Kroko-Build werden mit `restore-venv.sh` reproduzierbar neu aufgebaut.
