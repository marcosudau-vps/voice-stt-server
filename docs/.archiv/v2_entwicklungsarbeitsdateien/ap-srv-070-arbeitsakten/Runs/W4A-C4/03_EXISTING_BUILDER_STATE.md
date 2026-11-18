# AP-SRV-070 / W4A-C4 — Phase 1: Vorhandener C3-Builderzustand

## 1. Relevante Docker-Images und Container

- **Builder-Image:** `kroko-onnx-windows-builder:latest`
  - Image-ID: `b57c9ef6855e`
  - Größe: 4.4 GB (Content: 1.09 GB)
  - Erstellt: 2026-09-01T03:30 CEST (im W4A-C3-Lauf)
- **Base-Image:** `ubuntu@sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517`
  - Image-ID: `33ceb71981b6`
- **Relevante Container:**
  - Keine aktiven C3-Build-Container vorhanden (der C3-Build lief in einem ephemeren Container).

## 2. Untersuchte Pfade und Artefakte

Untersuchung im vorhandenen Builder-Image `kroko-onnx-windows-builder:latest` (ohne Mutation, ohne Neubau):

### 2.1 Microsoft Top-Level-Manifest

- **Dateipfad im Image:** `/tmp/.xwin-cache/dl/manifest_17.json`
- **Dateigröße:** `91833` Bytes
- **SHA-256:** `4c81e902fb7fe2acea779b828e6dc548fe0bbb693df50eda0224263c16686bdd`
- **Enthaltene Metadaten:**
  - `manifestName`: `VisualStudio.17.Release`
  - `manifestType`: `channel`
  - `buildVersion`: `17.14.37614.0`
  - `productDisplayVersion`: `17.14.39 (August 2026)`
  - `productSemanticVersion`: `17.14.39+37614.0.-august.2026-`
  - Referenziertes Installer-Paketmanifest: `https://download.visualstudio.microsoft.com/download/pr/fa619120-9c0e-47e6-bfe0-3ee96fb671b2/bd98dd01efa4195cb1c11030da63b9e4a3bcec7bc406799a9db80339d6dabd79/VisualStudio.vsman`

- **Zugehöriges vsman-Manifest im Image:** `/tmp/.xwin-cache/dl/pkg_manifest_bd98dd01efa4195cb1c11030da63b9e4a3bcec7bc406799a9db80339d6dabd79.vsman`
  - Dateigröße: `17955171` Bytes
  - SHA-256: `3891c3018a07338b3880cbb28088bb22ef7762eb9206523655b2e3972b9d527e`

### 2.2 Windows SDK Artefakte

- **Sysroot-Pfad im Image:** `/opt/xwin/sdk`
  - Enthaltene Symlinks: `10.0.26100 -> .` in `include/` und `lib/`
  - Erkennbare SDK-Version: `10.0.26100` (Windows 11 SDK 10.0.26100.0)
- **Pakete im Download-Cache (`/tmp/.xwin-cache/dl/`):**
  - `Win11SDK_10.0.26100_headers.msi`
  - `Win11SDK_10.0.26100_uap_headers.msi`
  - `Win11SDK_10.0.26100_store_headers.msi`
  - `Win11SDK_10.0.26100_store_headers_onecoreuap.msi`
  - `Win11SDK_10.0.26100_x64_headers.msi`
  - `Win11SDK_10.0.26100_libs_x86_64.msi`
  - `Win11SDK_10.0.26100_store_libs.msi`
  - `ucrt.msi`

### 2.3 MSVC CRT Artefakte

- **Sysroot-Pfad im Image:** `/opt/xwin/crt`
  - Header `crtversion.h` (`/opt/xwin/crt/include/crtversion.h`):
    - `_VC_CRT_MAJOR_VERSION 14`
    - `_VC_CRT_MINOR_VERSION 44`
    - `_VC_CRT_BUILD_VERSION 35220`
    - `_VC_CRT_RBUILD_VERSION 0`
    - Bedeutet: MSVC Toolset 14.44, CRT Build 14.44.35220
- **Pakete im Download-Cache (`/tmp/.xwin-cache/dl/`):**
  - `Microsoft.VC.14.44.17.14.CRT.Headers.base.vsix`
  - `Microsoft.VC.14.44.17.14.CRT.x64.Desktop.base.vsix`
  - `Microsoft.VC.14.44.17.14.CRT.x64.Store.base.vsix`
- **xwin-Versionierung:**
  - xwin Version-Identifier für `--crt-version`: `14.44.17.14`

### 2.4 Probe des deterministischen xwin-Aufrufs gegen vorhandenen Cache

Befehl im vorhandenen Image:

```bash
xwin --accept-license \
  --cache-dir /tmp/.xwin-cache \
  --manifest /tmp/.xwin-cache/dl/manifest_17.json \
  --sdk-version 10.0.26100 \
  --crt-version 14.44.17.14 \
  list
```

Ergebnis:
- 11 Pakete exakt aufgelöst (identisch mit den im C3-Image vorhandenen `.vsix`- und `.msi`-Dateien)
- Download Size: 82.41 MiB, Install Size: 308.97 MiB
- Exit-Code: 0 (Erfolgreich offline gegen Cache validiert)

## 3. Rekonstruierbarkeitsaussage

```text
C3_MANIFEST_AUTHORITY_RECONSTRUCTABLE: YES
C3_SDK_AUTHORITY_RECONSTRUCTABLE: YES
C3_CRT_AUTHORITY_RECONSTRUCTABLE: YES
```

### Begründung:

1. **Manifest (`YES`):** Die exakte Datei `/tmp/.xwin-cache/dl/manifest_17.json` ist im vorhandenen Builder-Image `kroko-onnx-windows-builder:latest` erhalten (Dateigröße `91833` Bytes, SHA-256 `4c81e902fb7fe2acea779b828e6dc548fe0bbb693df50eda0224263c16686bdd`).
2. **SDK (`YES`):** Die SDK-Version ist durch die Sysroot-Symlinks `10.0.26100 -> .` sowie die 8 vorhandenen `Win11SDK_10.0.26100_*`-Pakete zweifelsfrei als `10.0.26100` belegt.
3. **CRT (`YES`):** Die CRT-Version ist durch `crtversion.h` (`14.44.35220`), die Paketnamen `Microsoft.VC.14.44.17.14.CRT.*` und die xwin-Akzeptanz von `--crt-version 14.44.17.14` zweifelsfrei belegt.
