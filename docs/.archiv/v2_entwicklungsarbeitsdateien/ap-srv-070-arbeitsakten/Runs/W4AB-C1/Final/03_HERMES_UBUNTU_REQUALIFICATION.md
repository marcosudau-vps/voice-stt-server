# AP-SRV-070 / W4AB-C1 — Hermes / Ubuntu Requalification Plan

Status:
```text
HERMES_REQUALIFICATION_REQUIRED: YES
```

> **Wichtig**: Diese Befehle sind für die spätere Requalifikation auf Ubuntu (Hermes) vorbereitet und werden im aktuellen lokalen Windows-Lauf **nicht** ausgeführt.

## Requalifikationsschritte und exakte Kommandos auf Hermes

### 1. Checkout des exakten finalen Commits
```bash
cd /opt/voice-stt-server
git fetch origin
git checkout b2ec1657d40b4015cf8cf92c17eef1371b127b78
git status
```

### 2. Linux Development Dependencies prüfen / sicherstellen
```bash
sudo apt-get update
sudo apt-get install -y cmake g++ libssl-dev pkg-config python3-dev
pkg-config --modversion openssl
```

### 3. Fingerprint ermitteln
```bash
python3 VoiceSTT/install_kroko.py --print-fingerprint
```
Erwartung: JSON mit `targetPlatform: linux`, `builderRevision: 1`, `opensslDevelopment` mit gehashten Headern/Libraries.

### 4. Nativer Free-Build
```bash
python3 VoiceSTT/install_kroko.py --variant free --rebuild-kroko
```

### 5. Prüfung Wheel-Tagging (1free Dateiname und WHEEL-Metadaten)
```bash
STORE_DIR="${VOICESTT_KROKO_ARTIFACT_STORE:-$HOME/.cache/voicestt/kroko-artifacts}"
ls -la "$STORE_DIR/free"/*/*.whl
unzip -p "$STORE_DIR/free"/*/*.whl "*.dist-info/WHEEL" | grep "Build: 1free"
```

### 6. Store Lookup & Rebuild-Schutz (REUSE)
```bash
python3 VoiceSTT/install_kroko.py --describe-artifact
# Zweiter Aufruf muss sofort "Reusing verified Kroko artifact" melden ohne Neubau:
python3 VoiceSTT/install_kroko.py --variant free
```

### 7. Disposable venv Installation & Import-Test
```bash
TEST_VENV=$(mktemp -d /tmp/kroko-venv-XXXXXX)
python3 -m venv "$TEST_VENV"
"$TEST_VENV/bin/pip" install "$STORE_DIR/free"/*/*.whl
"$TEST_VENV/bin/python" -c "import kroko_onnx; print('kroko_onnx import ok')"
```

### 8. Free positiv / Pro negativ Validierung
```bash
"$TEST_VENV/bin/python" -c "
import kroko_onnx
# Free-Modus initialisieren - muss gelingen
print('Free runtime available')
"
# Pro-Aufruf ohne Pro-Build muss scheitern
python3 VoiceSTT/install_kroko.py --describe-artifact --variant pro
```

### 9. Kleiner Kroko / VoiceSTT Smoke
```bash
"$TEST_VENV/bin/python" -c "
import VoiceSTT
from VoiceSTT.kroko import artifacts, buildinputs, fingerprint
print('VoiceSTT kroko modules ok')
"
```

### 10. Relevante Linux-Tests ausführen
```bash
python3 -m pytest -q tests/unit/test_install_kroko_cpu.py tests/unit/test_kroko_artifact_store.py tests/unit/test_kroko_fingerprint.py
```

### 11. Hygiene / Cleanup
```bash
rm -rf "$TEST_VENV"
```
