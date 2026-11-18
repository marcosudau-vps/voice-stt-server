# AP-SRV-070 / W4A-C4 — Phase 2: Windows-Dependency-Closure

Dieses Dokument klassifiziert die buildwirksamen externen Download-Dependencies des Windows-Builds nach der erfolgreichen Umsetzung von Finding L/M in Phase 2.

## Klassifizierungsübersicht

| Dependency | Klassifizierung | Absicherungsmechanismus / Nachweis |
|---|---|---|
| `kaldi-native-fbank` | **CLOSED_BY_PINNED_UPSTREAM** | Gepinnt in `cmake/kaldi-native-fbank.cmake` auf `v1.21.3`, verifiziert via `URL_HASH SHA256=d409eddae5a46dc796f0841880f489ff0728b96ae26218702cd438c28667c70e` in `FetchContent_Declare`. |
| `kissfft` | **CLOSED_BY_PINNED_UPSTREAM** | Gepinnt in `cmake/kissfft.cmake` (via `kaldi-native-fbank`) auf Commit `febd4caeed32e33ad8b2e0bb5ea77542c40f18ec`, verifiziert via `URL_HASH SHA256=497103e664168ebe39580b757adbe616f6cf85a16572af581ca7bc42d0ab13fd`. |
| `kaldi-decoder` | **CLOSED_BY_PINNED_UPSTREAM** | Gepinnt in `cmake/kaldi-decoder.cmake` auf `v0.2.6`, verifiziert via `URL_HASH SHA256=b13c78b37495cafc6ef3f8a7b661b349c55a51abbd7f7f42f389408dcf86a463`. |
| `kaldifst` | **CLOSED_BY_PINNED_UPSTREAM** | Gepinnt in `cmake/kaldifst.cmake` auf `v1.7.13`, verifiziert via `URL_HASH SHA256=f8dc15fdaf314d7c9c3551ad8c11ed15da0f34de36446798bbd1b90fa7946eb2`. |
| `openfst` | **CLOSED_BY_VOICESTT_AUTHORITY** | Deklariert in `VoiceSTT/kroko/buildinputs.py` (`WINDOWS_OPENFST_TAG = "sherpa-onnx-2024-06-19"`, `WINDOWS_OPENFST_SHA256 = "5c98e82cc509c5618502dde4860b8ea04d843850ed57e6d6b590b644b268853d"`). Vorab-Download und `sha256sum -c`-Prüfung in `in_windows_container.sh`, zusätzlich upstream in `cmake/openfst.cmake` gehasht. |
| `eigen` | **CLOSED_BY_PINNED_UPSTREAM** | Gepinnt in `cmake/eigen.cmake` auf `3.4.0`, verifiziert via `URL_HASH SHA256=8586084f71f9bde545ee7fa6d00288b264a2b7ac3607b974e54d13e7162c1c72`. |
| `onnxruntime` | **CLOSED_BY_PINNED_UPSTREAM** | Gepinnt in `cmake/onnxruntime-win-x64-gpu.cmake` (bzw. `onnxruntime-win-x64.cmake`) auf `v1.17.1`, verifiziert via `URL_HASH SHA256=b7a66f50ad146c2ccb43471d2d3b5ad78084c2d4ddbd3ea82d65f86c867408b2` (GPU) bzw. `SHA256=4802af9598db02153d7da39432a48823ff69b2fb4b59155461937f20782aa91c` (CPU). |
| `simple-sentencepiece` | **CLOSED_BY_PINNED_UPSTREAM** | Gepinnt in `cmake/simple-sentencepiece.cmake` auf `v0.7`, verifiziert via `URL_HASH SHA256=1748a822060a35baa9f6609f84efc8eb54dc0e74b9ece3d82367b7119fdc75af`. |
| `websocketpp` | **CLOSED_BY_PINNED_UPSTREAM** | Gepinnt in `cmake/websocketpp.cmake` auf Commit `b9aeec6eaf3d5610503439b4fae3581d9aff08e8`, verifiziert via `URL_HASH SHA256=1385135ede8191a7fbef9ec8099e3c5a673d48df0c143958216cd1690567f583`. |
| `asio` | **CLOSED_BY_PINNED_UPSTREAM** | Gepinnt in `cmake/asio.cmake` auf `asio-1-24-0`, verifiziert via `URL_HASH SHA256=cbcaaba0f66722787b1a7c33afe1befb3a012b5af3ad7da7ff0f6b8c9b7a8a5b`. |
| `cppjieba` | **CLOSED_BY_PINNED_UPSTREAM** | Gepinnt in `cmake/cppjieba.cmake` auf Tag `sherpa-onnx-2024-04-19`, verifiziert via `URL_HASH SHA256=03e5264687f0efaef05487a07d49c3f4c0f743347bfbf825df4b30cc75ac5288`. |
| `hclust_cpp` | **CLOSED_BY_PINNED_UPSTREAM** | Gepinnt in `cmake/hclust-cpp.cmake` auf Tag `2024-09-29`, verifiziert via `URL_HASH SHA256=abab51448a3cb54272aae07522970306e0b2cc6479d59d7b19e7aee4d6cedd33`. |
| `pybind11` | **CLOSED_BY_PINNED_UPSTREAM** | Gepinnt in `cmake/pybind11.cmake` auf `v2.12.0`, verifiziert via `URL_HASH SHA256=bf8f242abd1abcd375d516a7067490fb71abd79519a282d22b6e4d19282185a7`. |
| `xwin binary` | **CLOSED_BY_VOICESTT_AUTHORITY** | Deklariert in `VoiceSTT/kroko/buildinputs.py` (`WINDOWS_XWIN_VERSION = "0.6.5"`, `WINDOWS_XWIN_SHA256 = "9fd53950b064d067f42428a69453b927656cae68dbd7f8d3f86dcb81c80dd22d"`). Im Dockerfile vor dem Entpacken via `sha256sum -c -` geprüft. |
| `xwin channel manifest` | **CLOSED_BY_VOICESTT_AUTHORITY** | Deklariert in `VoiceSTT/kroko/buildinputs.py` (`WINDOWS_XWIN_MANIFEST_URL`, `WINDOWS_XWIN_MANIFEST_BYTES = 91833`, `WINDOWS_XWIN_MANIFEST_SHA256 = "4c81e902fb7fe2acea779b828e6dc548fe0bbb693df50eda0224263c16686bdd"`). Expliziter Download, Bytezahlprüfung (`stat -c %s`) und `sha256sum -c -` im Dockerfile vor Aufruf von `xwin`. |
| `xwin package manifest` | **CLOSED_BY_VOICESTT_AUTHORITY** | Deklariert in `VoiceSTT/kroko/buildinputs.py` (`WINDOWS_XWIN_PACKAGE_MANIFEST_URL`, `WINDOWS_XWIN_PACKAGE_MANIFEST_CACHE_KEY`, `WINDOWS_XWIN_PACKAGE_MANIFEST_BYTES = 17955171`, `WINDOWS_XWIN_PACKAGE_MANIFEST_SHA256 = "3891c3018a07338b3880cbb28088bb22ef7762eb9206523655b2e3972b9d527e"`). Expliziter Download, Bytezahlprüfung und Verifikation der echten Datei-Bytes gegen `3891c301...` vor xwin-Aufruf. |
| `Windows SDK/CRT payloads` | **CLOSED_BY_VOICESTT_AUTHORITY** | Vollständig geschlossen durch dreistufige Absicherung: 1. VoiceSTT verifiziert das Package Manifest (`3891c301...`); 2. explizite Pinned-Versionen `--sdk-version 10.0.26100` und `--crt-version 14.44.17.14` ohne `latest`-Fallback; 3. xwin lädt ausschließlich die darin definierten Payloads herunter und validiert jede einzelne gegen den im verifizierten Manifest hinterlegten SHA-256 (`get_and_validate(..., Some(payload.sha256))`). |

## Ergebnis

- **Status:** `DEPENDENCY_CLOSURE: PASS`
- **Verbleibende offene Build-Dependencies:** `0`
