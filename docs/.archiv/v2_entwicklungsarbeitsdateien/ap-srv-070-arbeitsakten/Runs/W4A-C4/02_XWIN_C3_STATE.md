# AP-SRV-070 / W4A-C4 — Phase 1: Aktueller C3-xwin-Vertrag

## 1. xwin-Version und Hash

- **xwin-Version:** `0.6.5`
- **xwin-Binary-SHA256:** `9fd53950b064d067f42428a69453b927656cae68dbd7f8d3f86dcb81c80dd22d`
- **Download-URL:** `https://github.com/Jake-Shadle/xwin/releases/download/0.6.5/xwin-0.6.5-x86_64-unknown-linux-musl.tar.gz`

## 2. Real generierter xwin-Aufruf

Im Dockerfile des Windows-Builders (`Dockerfile.windows`, ungepatcht übernommen von Upstream in `VoiceSTT/install_kroko.py`):

```dockerfile
xwin --accept-license --arch x86_64 splat --output /opt/xwin
```

VoiceSTT C3 patcht in `VoiceSTT/install_kroko.py` (Zeilen 838–857) ausschließlich den Download von `xwin.tar.gz` inklusive SHA256-Prüfung (`declaration["xwin"]["sha256"]`). Der eigentliche `xwin ... splat`-Aufruf wird durch VoiceSTT nicht modifiziert.

## 3. Aktuell fingerprintete Eingaben der Windows-Toolchain

In `VoiceSTT/kroko/buildinputs.py` definiert `windows_toolchain_declaration()`:

- `baseImage`: `"ubuntu:24.04"`
- `baseImageDigest`: `"sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517"`
- `aptSnapshot`: `"https://snapshot.ubuntu.com/ubuntu/20260825T000000Z"`
- `aptSuites`: `["noble", "noble-updates", "noble-security"]`
- `aptComponents`: `["main", "restricted", "universe", "multiverse"]`
- `clangVersion`: `"19"`
- `nsisVersion`: `"3.10"`
- `cmake`: `{"version": "3.30.5", "url": "https://github.com/Kitware/CMake/releases/download/v3.30.5/cmake-3.30.5-linux-x86_64.tar.gz", "sha256": "f747d9b23e1a252a8beafb4ed2bc2ddf78cff7f04a8e4de19f4ff88e9b51dc9d"}`
- `xwin`: `{"version": "0.6.5", "url": "https://github.com/Jake-Shadle/xwin/releases/download/0.6.5/xwin-0.6.5-x86_64-unknown-linux-musl.tar.gz", "sha256": "9fd53950b064d067f42428a69453b927656cae68dbd7f8d3f86dcb81c80dd22d"}`
- `pythonTarget`: `{"version": "3.12.7", "tag": "312", "url": "https://www.nuget.org/api/v2/package/python/3.12.7", "sha256": "149dd298e0b7a82250ca019471770fff079874088a4e8501ca20922d7df3a6ac"}`
- `vcRedist`: `{"url": "https://download.visualstudio.microsoft.com/download/pr/9d270333-8b7b-4f96-9458-6fcdb2ec0b25/CC0FF0EB1DC3F5188AE6300FAEF32BF5BEEBA4BDD6E8E445A9184072096B713B/VC_redist.x64.exe", "sha256": "cc0ff0eb1dc3f5188ae6300faef32bf5beeba4bdd6e8e445a9184072096b713b"}`
- `openssl`: `{"version": "3.6.4", "condaBuild": "hf411b9b_0", "url": "https://conda.anaconda.org/conda-forge/win-64/openssl-3.6.4-hf411b9b_0.conda", "sha256": "9dddb559ba49744d5d94092d8d13cb0567f5c3b3f439f3acf28433d1f4256acc"}`
- `openfst`: `{"tag": "sherpa-onnx-2024-06-19", "url": "https://github.com/csukuangfj/openfst/archive/refs/tags/sherpa-onnx-2024-06-19.tar.gz", "sha256": "5c98e82cc509c5618502dde4860b8ea04d843850ed57e6d6b590b644b268853d"}`
- `packagingTools`: `["setuptools==75.8.2", "wheel==0.45.1", "delvewheel==1.10.1", "pefile==2024.8.26"]`

## 4. Fingerprint-Wirksamkeit

- `VoiceSTT/kroko/fingerprint.py:windows_toolchain_authority()` serialisiert die gesamte von `windows_toolchain_declaration()` zurückgegebene Struktur per `canonical_json` und berechnet `sha256(...).hexdigest()[:16]`.
- Diese 16-stellige Hex-ID wird als `toolchain.authority` im Fingerprint-Dokument eingetragen; die vollständige Deklaration liegt unter `toolchain.inputs`.
- **Alle** in `windows_toolchain_declaration()` vorhandenen Felder beeinflussen somit den Fingerprint.

## 5. Status von Manifest, SDK und CRT

| Komponente | Technisch festgelegt in C3? | Wert / Verhalten |
|---|---|---|
| Microsoft Top-Level-Manifest | **NEIN** | Weder URL noch SHA-256 noch lokaler Pfad in `windows_toolchain_declaration()` deklariert; kein `--manifest`-Parameter im Aufruf |
| Windows SDK Version | **NEIN** | Nicht in `windows_toolchain_declaration()` deklariert; kein `--sdk-version`-Parameter im Aufruf |
| CRT / MSVC Version | **NEIN** | Nicht in `windows_toolchain_declaration()` deklariert; kein `--crt-version`-Parameter im Aufruf |
| Implizite `latest`-Auswahl durch xwin möglich? | **JA** | Da xwin 0.6.5 ohne `--manifest`, `--sdk-version` und `--crt-version` aufgerufen wird, lädt es das Standard-Manifest von Microsoft live herunter und wählt die jeweils neueste SDK- und CRT-Version aus |

## 6. Relevante Codestellen

1. `VoiceSTT/kroko/buildinputs.py`:
   - Zeilen 218–221: `WINDOWS_XWIN_VERSION`, `WINDOWS_XWIN_SHA256`
   - Zeilen 289–294: `windows_xwin_url()`
   - Zeilen 325–374: `windows_toolchain_declaration()` (enthält `xwin`-Block, aber keine Manifest-/SDK-/CRT-Authority)
2. `VoiceSTT/kroko/fingerprint.py`:
   - Zeilen 76–94: `windows_toolchain_authority()`
   - Zeilen 122–129: `toolchain_identity("windows")`
3. `VoiceSTT/install_kroko.py`:
   - Zeilen 838–857: `_patch_windows_dockerfile()` ersetzt nur den `curl`/`sha256sum`-Download von xwin; der Aufruf `xwin ... splat` verbleibt ungepatcht
4. Upstream `Dockerfile.windows`:
   - Zeile 808–809 (abgebildet in `tests/unit/test_kroko_fingerprint.py:808-809`):
     `mv xwin-${XWIN_VERSION}-x86_64-unknown-linux-musl/xwin /usr/local/bin/xwin && xwin --accept-license --arch x86_64 splat --output /opt/xwin`
