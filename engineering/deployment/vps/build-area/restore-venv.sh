#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
build_area_root="${VOICESTT_BUILD_AREA_ROOT:-/home/marco/selfhost_outsourced/build_area/services/voice}"
venv_dir="${build_area_root}/.venv"
project_dir="/home/marco/selfhost/apps/services/voice/voice-stt-server"
kroko_variant="${KROKO_VARIANT:-pro}"

test -f "${root_dir}/requirements.txt"
test -f "${project_dir}/VoiceSTT/install_kroko.py"

python3.12 -m venv "${venv_dir}"
"${venv_dir}/bin/python" -m pip install --upgrade pip setuptools wheel
"${venv_dir}/bin/python" -m pip install -r "${root_dir}/requirements.txt"
"${venv_dir}/bin/stt-install-kroko" --build --variant "${kroko_variant}" \
  --work-dir "${build_area_root}/kroko-build"
"${venv_dir}/bin/python" -m pip check
