# AP-SRV-070 / W4A-C4 — Phase 2R: Python-Packaging-Tool-Provenienz

Dieses Dokument erfasst die reale Provenienz der buildwirksamen Python-Packaging-Tools im vorhandenen C3-Builder-Image `kroko-onnx-windows-builder:latest`.

## A. C3 Image Metadaten

- **Image-Tag:** `kroko-onnx-windows-builder:latest`
- **Image-ID:** `sha256:b57c9ef6855e2763d243a2c0ef2ddad7469a274392d581ce002ea55c5308c3be` (`b57c9ef6855e`)
- **Python-Version:** `Python 3.12.3`
- **pip-Version:** `pip 24.0 from /usr/lib/python3/dist-packages/pip (python 3.12)`

## B. Aktive Python-Packaging-Dependency-Closure

Im C3-Builder-Image unter `/usr/local/lib/python3.12/dist-packages` aktiv:

| Name | Installed Version | Direct/Transitive | Required By | Active Marker/Reason | Installed Location |
|---|---|---|---|---|---|
| `setuptools` | `75.8.2` | Direct | `buildinputs.py` (`WINDOWS_PACKAGING_TOOLS`) | Build- und Wheel-Erzeugung, Setup-Keywords; vendored interne Hilfsmodule unter `_vendor/` | `/usr/local/lib/python3.12/dist-packages/setuptools-75.8.2.dist-info` |
| `wheel` | `0.45.1` | Direct | `buildinputs.py` (`WINDOWS_PACKAGING_TOOLS`) | `bdist_wheel`-Kommando und Wheel-Tagging; CLI unter `/usr/local/bin/wheel` | `/usr/local/lib/python3.12/dist-packages/wheel-0.45.1.dist-info` |
| `delvewheel` | `1.10.1` | Direct | `buildinputs.py` (`WINDOWS_PACKAGING_TOOLS`) | DLL-Repair-Tool für Windows-Wheels; CLI unter `/usr/local/bin/delvewheel` | `/usr/local/lib/python3.12/dist-packages/delvewheel-1.10.1.dist-info` |
| `pefile` | `2024.8.26` | Direct / Transitive | `buildinputs.py` (`WINDOWS_PACKAGING_TOOLS`) und `delvewheel>=1.10.1` (`Requires-Dist: pefile>=2024.8.26`) | PE/DLL-Header-Parser für `delvewheel` | `/usr/local/lib/python3.12/dist-packages/pefile-2024.8.26.dist-info` |

*Hinweis:* Es existieren keine weiteren aktiven transitiven Abhängigkeiten in der Packaging-Closure (Setuptools verwendet interne vendored Subpakete, wheel und pefile deklarieren keine aktiven Default-Dependencies, delvewheel deklariert ausschließlich `pefile>=2024.8.26`).

## C. Heruntergeladene Kandidaten-Wheels aus Package Index

Heruntergeladen via `python3 -m pip download --only-binary=:all: --no-deps` im C3-Container-Kontext:

| Name | Version | Wheel-Dateiname | Bytes | SHA-256 | Tags |
|---|---|---|---:|---|---|
| `setuptools` | `75.8.2` | `setuptools-75.8.2-py3-none-any.whl` | 1229385 | `558e47c15f1811c1fa7adbd0096669bf76c1d3f433f58324df69f3f5ecac4e8f` | `py3-none-any` |
| `wheel` | `0.45.1` | `wheel-0.45.1-py3-none-any.whl` | 72494 | `708e7481cc80179af0e556bbf0cc00b8444c7321e2700b8d8580231d13017248` | `py3-none-any` |
| `delvewheel` | `1.10.1` | `delvewheel-1.10.1-py3-none-any.whl` | 58612 | `08bc03a0be2d5abe4605da15f829ac4af373fa728882082c4bfe574a4e7ed902` | `py3-none-any` |
| `pefile` | `2024.8.26` | `pefile-2024.8.26-py3-none-any.whl` | 74766 | `76f8b485dcd3b1bb8166f1128d395fa3d87af26360c2358fb75b80019b957c6f` | `py3-none-any` |

## D. Installierter Zustand vs. Wheel-Content-Vergleich

Jede im Wheel `.dist-info/RECORD` enthaltene Datei wurde gegen die im C3-Image unter `/usr/local/lib/python3.12/dist-packages` installierte Datei verglichen (ohne `.pyc`, Cache- oder reine pip-State-Dateien):

| Name | Compared Files | Matches | Mismatches | Unresolved | Result |
|---|---:|---:|---:|---:|---|
| `delvewheel` | 11 | 11 | 0 | 0 | **YES** |
| `pefile` | 10 | 10 | 0 | 0 | **YES** |
| `setuptools` | 460 | 460 | 0 | 0 | **YES** |
| `wheel` | 36 | 36 | 0 | 0 | **YES** |

### Details:
- **`delvewheel`:** 100% Übereinstimmung aller 11 Python-/Metadaten-Dateien. Console Script `/usr/local/bin/delvewheel` ist im Image vorhanden.
- **`pefile`:** 100% Übereinstimmung aller 10 Python-/Metadaten-Dateien.
- **`setuptools`:** 100% Übereinstimmung aller 460 Dateien inklusive aller vendored Module (`setuptools/_vendor/*`).
- **`wheel`:** 100% Übereinstimmung aller 36 Python-/Metadaten-Dateien. Console Script `/usr/local/bin/wheel` ist im Image vorhanden.

## E. Gesamtstatus

```text
C3_PACKAGING_IMAGE_AVAILABLE: YES
ACTIVE_PACKAGING_DEPENDENCY_CLOSURE_COMPLETE: YES
ALL_CANDIDATE_WHEELS_IDENTIFIED: YES
ALL_CANDIDATE_WHEEL_HASHES_CAPTURED: YES
C3_PACKAGING_PROVENANCE_RECONSTRUCTABLE: YES
```
