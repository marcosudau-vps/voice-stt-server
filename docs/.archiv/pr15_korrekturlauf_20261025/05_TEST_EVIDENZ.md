# Korrekturlauf PR #15 – Testevidenz (25.10.2026)

Finaler Commit: Branch-Spitze von `work/kroko-v2-selective-improvements-20261025`
bei Push (SHA + CI-Links in PR-Beschreibung und Abschlusskommentar). Umgebung: Windows, CPython 3.12,
installierte Runtime für R3/R3b: lokal gebautes Pro-Wheel
`kroko_onnx-1.12.9-1pro` (`KROKO_LICENSE=ON`, per `stt-install-kroko --build
--variant pro`, kein Fingerprint-/Buildinput-Wechsel im Repo).
Secrets ausschließlich zur Laufzeit aus lokaler Secret-Datei/Umgebung;
keine Keys, keine Key-URLs in Ausgaben, Berichten oder Akten.

## D1 – Deterministisch (Pflicht + Regression)

| Befehl | Ergebnis |
| --- | --- |
| `test_kroko_license_lifecycle.py` (neu, 24) | 24 passed |
| 7er-Pflichtdateien + docs_surface + settings_runtime | 217 passed, 2 skipped |
| Protokoll/Multi-User/Operations/Browser/Info/Settings/Manager | 250 passed, 24 subtests |
| `test_kroko_live_license.py` ohne Opt-in | 5 skipped (sauber, kein Netz) |
| `python -m pytest -q tests/unit` (nach allen Änderungen) | **2284 passed, 20 skipped, 1330 subtests passed** in 760 s (nur `websockets.legacy`-DeprecationWarning) |
| `compileall api_fastapi_server VoiceSTT/kroko VoiceSTT_server` | sauber |
| `git diff --check` | sauber |

Wahrheitstabelle abgedeckt: kein Key / Force / gültig / negativ / Timeout /
Rotation / Entfernung / Force-an-aus / stale Generation / Overlap /
TTL-Ablauf / Pro-lokal-fehlend / falsche Runtime / gültig+verfügbar /
negativ-bei-Switch / Neustart-ohne-Persistenz — jeweils über die echte Kette
Gate→State→Service→Manager mit synthetischen Transporten/Uhren/Dateien.

## D2 – Real (Opt-in `VOICESTT_KROKO_LIVE_TESTS=1`, 25.10.2026 abends)

Modellkennung: Header-UUID der lokalen `Kroko-DE-Pro-16-L-Streaming-001.data`
(provider-seitig konsistent mit R1-Positivbefund); Key: Betreiber-Pro-Key zur
Laufzeit aus Secret-Datei; jeweils genau 1 explizite WS-Verbindung pro
Positiv-/Negativ-/Revoke-Durchgang (keine Wiederholungsschleifen).

| Test | Verbindungen | Ergebnis (redigiert) |
| --- | --- | --- |
| R1 positiv | 1 | `tier=pro`, Status VALID, modellgebunden, Socket geschlossen, kein Secret in Decision/Snapshot/Output |
| R2 ungültiger Key | 1 | Community, kein Grant, Status INVALID/CHECK_FAILED |
| R3 Modellintegration (Separater Prozess, Pro-Runtime + Pro-Datei + Key, 8-s-Audio-Smoke) | 0 explizit (nativ-seitig lizenziert) | Modell geladen, Transkription mit Text, Returncode 0, kein Key in Child-Output |
| R3b Community ohne Key auf Pro-Runtime (H-06) | 0 | Modell geladen in 8,7 s |
| R4 Force/Entfernung nach Grant | 1 (nur Initial-Grant) | sofort kein Pro-Zugriff, keine weitere Netzverbindung, danach NOT_CHECKED |

Negativ-Kontrollfall ( Aktennotiz, kein committed Test): Pro-Datei ohne Key
im Kindprozess → native Lizenzwarteschleife bis Timeout (300 s), kein Grant,
kein Absturz des Parents. Bestätigt Fail-closed-Verhalten der nativen Seite;
kein Pro-Start ohne Berechtigung.

## Fehlschläge/Korrekturen im Lauf

- Nach der Vollsuite nur noch: Entfernung eines ungenutzten Imports
  (`server.py`) + gezielter Re-Run (Lifecycle + Multi-User: 80 passed);
  finale CI prüft den finalen Commit vollständig neu.

- Eigene Testverdrahtungsfehler (Fake-Record-Assertion, Manifest-/Dateinamen-
  Mismatch) → behoben, keine Produktionscode-Änderung dafür.
- R3b-Erstlauf mit versehentlich Pro- statt Community-Datei → 300-s-Timeout
  (s. o.), mit Community-Datei 8,7 s grün.
- Pro-Wheel-Erstbuild scheiterte transient am Docker-Build-RPC; Zweitlauf grün.
