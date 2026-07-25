#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
venv_dir="${root_dir}/.venv"
project_dir="/home/marco/selfhost/apps/services/voice/stt-voice"

test -f "${root_dir}/requirements.txt"
test -f "${project_dir}/VoiceSTT/install_kroko.py"

python3.12 -m venv "${venv_dir}"
"${venv_dir}/bin/python" -m pip install --upgrade pip setuptools wheel
"${venv_dir}/bin/python" -m pip install -r "${root_dir}/requirements.txt"
"${venv_dir}/bin/stt-install-kroko" --build --work-dir "${root_dir}/kroko-build"
"${venv_dir}/bin/python" -m pip check
