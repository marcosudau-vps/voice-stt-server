#!/usr/bin/env bash
# Kompatibilitaetseinstieg: die Implementierung liegt seit der
# V2-Engineering-Konsolidierung unter engineering/deployment/vps/release-voice-stt.sh.
set -euo pipefail
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../../engineering/deployment/vps/release-voice-stt.sh" "$@"
