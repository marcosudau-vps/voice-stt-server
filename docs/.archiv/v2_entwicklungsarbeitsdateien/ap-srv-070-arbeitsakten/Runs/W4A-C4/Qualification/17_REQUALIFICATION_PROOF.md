# AP-SRV-070 / W4A-C4 — Final Qualification: Requalification Proof

## 1. C3 Artifact Identity

- **C3 Fingerprint:** `b2483a5a5c488f59`
- **Wheel Filename:** `kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64.whl`
- **SHA-256:** `cdaa28193366c21d21b6f59e73cd0733fd59ba3eba6a471d540ba11a34f48f38`
- **Bytes:** `12549999`
- **C3 Store-Slot:** `C:\Users\user\AppData\Local\VoiceSTT\kroko-artifacts\free\b2483a5a5c488f59\` (unverändert erhalten)

## 2. C4 Fingerprint und Toolchain Authority

- **C4 Windows Free Fingerprint:** `28594e6d201fc4a7`
- **C4 Toolchain Authority:** `63224eaaaa84424e`
- **`PATCH_SET_REVISION`:** `3`
- **`BUILDER_REVISION`:** `4`
- **C4 Store-Slot:** `C:\Users\user\AppData\Local\VoiceSTT\kroko-artifacts\free\28594e6d201fc4a7\`

## 3. Provenienz-Mapping C3 → C4

Die Requalification des bestehenden C3-Wheels unter dem C4-Fingerprint ist vollständig legitimiert, da Phase 1 und Phase 2R bewiesen haben, dass die in C4 neu deklarierten Toolchain- und Manifest-Eingaben exakt den tatsächlichen Inputs des C3-Builds entsprechen:

| Komponente | C3 Reale Eingabe (Phase 1 / 2R Evidence) | C4 Deklarierte Authority (`buildinputs.py`) | Übereinstimmung |
|---|---|---|---|
| Kroko Upstream Revision | `8657e655192623b98d7708e742a72987f953d3a2` | `8657e655192623b98d7708e742a72987f953d3a2` | 100% |
| xwin Version / SHA | `0.6.5` / `9fd53950b064...` | `0.6.5` / `9fd53950b064...` | 100% |
| Channel Manifest URL / SHA | `https://aka.ms/vs/17/release/channel` / `4c81e902...` (91833 B) | `https://aka.ms/vs/17/release/channel` / `4c81e902...` (91833 B) | 100% |
| Package Manifest URL / SHA | `VisualStudio.vsman` / `3891c301...` (17955171 B) | `VisualStudio.vsman` / `3891c301...` (17955171 B) | 100% |
| Windows SDK Version | `10.0.26100` | `10.0.26100` | 100% |
| MSVC CRT Version | `14.44.17.14` | `14.44.17.14` | 100% |
| Packaging Tools | `setuptools==75.8.2`, `wheel==0.45.1`, `delvewheel==1.10.1`, `pefile==2024.8.26` (517/517 Files gematcht) | identisch deklariert | 100% |

## 4. Slot-Zustand und Verifikation

- **Alter C3-Slot:** `C:\Users\user\AppData\Local\VoiceSTT\kroko-artifacts\free\b2483a5a5c488f59\` (unberührt, intakt)
- **Neuer C4-Slot:** `C:\Users\user\AppData\Local\VoiceSTT\kroko-artifacts\free\28594e6d201fc4a7\`
- **Wheel-Bytes im neuen C4-Slot:** `12549999`
- **Wheel-SHA256 im neuen C4-Slot:** `cdaa28193366c21d21b6f59e73cd0733fd59ba3eba6a471d540ba11a34f48f38`
- **Metadaten-Verifikation:** `artifacts.verify_artifact()` = **PASS**

## 5. Ergebnis

```text
REQUALIFICATION_PROVENANCE: PASS
```
