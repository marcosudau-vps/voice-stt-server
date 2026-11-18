# AP-SRV-070 / W4A-C4 — Final Qualification: Reuse & Runtime Proof

## 1. Normaler CLI REUSE-Beweis

### Befehl
```powershell
python -m VoiceSTT.install_kroko --build --skip-install --variant free --artifact-store "C:\Users\user\AppData\Local\VoiceSTT\kroko-artifacts"
```

### Ausgabe
```text
Kroko build fingerprint: 28594e6d201fc4a7 (variant free, upstream https://github.com/kroko-ai/kroko-onnx.git @ 8657e655192623b98d7708e742a72987f953d3a2)
Reusing verified Kroko artifact: C:\Users\user\AppData\Local\VoiceSTT\kroko-artifacts\free\28594e6d201fc4a7\kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64.whl
Kroko-ONNX is ready in this Python environment.
```

### Laufzeit und Build-Vermeidung
- **Ausführungsdauer:** ~2.1 Sekunden
- **NATIVE_BUILD_INVOKED:** `NO`
- **DOCKER_BUILD_INVOKED:** `NO`
- **NEW_BUILD_CONTAINER_CREATED:** `NO` (überprüft via `docker ps -a` vor und nach Ausführung)

## 2. Disposable Install / Import / Runtime Variant Proof

In einer temporären, isolierten virtuellen Umgebung (`C:\Users\user\AppData\Local\Temp\w4a-c4-qualification-venv`):

### 2.1 Installation
```text
Processing c:\users\marco\appdata\local\voicestt\kroko-artifacts\free\28594e6d201fc4a7\kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64.whl
Installing collected packages: kroko-onnx
Successfully installed kroko-onnx-1.12.9
```

### 2.2 Import Proof
```python
import kroko_onnx
print("Kroko-ONNX import success:", kroko_onnx.__file__)
```
**Ergebnis:** `Kroko-ONNX import success: ...\site-packages\kroko_onnx\__init__.py` -> **PASS**

### 2.3 Free-vs-Pro Variant Verification
```python
from VoiceSTT.kroko import artifacts
free_res = artifacts.verify_installed_runtime("free")
pro_res = artifacts.verify_installed_runtime("pro")
```
- **FREE VERIFY:** `{'expectedVariant': 'free', 'importable': True, 'installedBuildTag': '1free', 'installedVariant': 'free', 'ok': True}` -> **PASS**
- **PRO VERIFY:** `{'expectedVariant': 'pro', 'importable': True, 'installedBuildTag': '1free', 'installedVariant': 'free', 'ok': False, 'problem': "installed Kroko runtime variant 'free' does not match the expected 'pro'"}` -> **FAIL_AS_EXPECTED**

## 3. Status

```text
NORMAL_REUSE: PASS
NATIVE_BUILD_INVOKED: NO
DOCKER_BUILD_INVOKED: NO
DISPOSABLE_INSTALL: PASS
IMPORT_KROKO_ONNX: PASS
FREE_VARIANT_VERIFY: PASS
PRO_NEGATIVE_VERIFY: PASS
```
