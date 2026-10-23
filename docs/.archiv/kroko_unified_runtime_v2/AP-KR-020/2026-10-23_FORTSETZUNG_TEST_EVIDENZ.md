# AP-KR-020 Fortsetzung – Test- und Evidenzbericht (23.10.2026)

Gesamtstatus **CONDITIONAL** (s. Soll/Ist-Nachtrag). Dieser Bericht trennt
tatsächliche lokale Ausführung, synthetische Fixtures und nicht ausgeführte
Nachweise. Kein Live-Lizenzserverkontakt, kein natives Kroko-Modell, keine
echte Lizenzprüfung in dieser Fortsetzung.

## Umgebung

Windows 11 AMD64, CPython 3.12.10, pytest 9.1.1, aus dem Sourcecheckout des
AP-020-Branches. `pip check` in der Testumgebung bestanden.

## Neue gezielte Suite: `tests/unit/test_kroko_unified_runtime.py`

**43 passed.** Abdeckung (alle mit synthetischer Infrastruktur):

- Autorität-Wahrheitstabelle: kein Key / Community erzwungen (kein Check,
  kein Pro); Positivnachweis exakt je Modell-ID (fremde ID nie berechtigt);
  unbekannte/leere IDs nie berechtigt; Ablehnung klebt an der Generation;
  Unerreichbarkeit fail-closed und wiederholbar; Produktdefault
  (`UnqualifiedLicenseVerifier`) vergibt nichts; Ablauf nach TTL
  (injizierte Uhr); überlange Backend-TTL abgewiesen; stale
  Generationsverdikte verworfen; Intentwechsel (Rotation/Force/Identität)
  verwirft atomar; INVALID blockiert blinde Retries; rotierter Key ändert
  die opake Revision; Snapshot enthält kein Keymaterial.
- Community-Fallback: echte Manifestauflösung (direkt, sprachgleich, keine
  freie Alternative) plus Duck-type-Grenzen.
- Bootstrap: exakt ein Root an `sys.path[0]`, Idempotenz, Konflikt bei
  vorinstalliertem/fremdem Nativmodul, fehlender Marker, zweite Wurzel,
  kein Payloadimport, Env-No-op.
- Supervisor: echter Start mit Bereitschaft und bestätigtem Exit,
  Deadline-Überschreitung mit Kill und Exit-Bestätigung, Exit-bei-Start als
  Deadlinefehler, Retry-Budget je Konfiguration (2 Versuche + Budget
  erschöpft, Reset bei Konfigurationswechsel, Backoff-Sequenz),
  Stale-Generations-Verwerfung, secretfreie Statusprojektion.
- Server-Gates (Stub-Ebene, echte Manifest-/Settings-/Authority-Objekte):
  Community passiert; unmanifestierte Modelle auditiert-übernommen (niemals
  `VALID`); Pro ohne Nachweis verweigert (redaktierte Meldung); Pro mit Nachweis exakt je ID;
  Force-Community blockiert trotz Nachweis; Nicht-Kroko-Lanes unberührt;
  Keyrotation entwertet Nachweise; Startup-Fallback downgradet
  In-memory auf Community mit Notiz; Authority sieht nie Keymaterial.

## Betroffene Bestandssuiten (gezielt, nach der Integration)

`test_kroko_model_authority`, `test_kroko_fingerprint`,
`test_kroko_artifact_store`, `test_kroko_onnx_engine`,
`test_settings_control_plane`, `test_settings_runtime_persistence`,
`test_server_operations`, `test_server_info`, `test_stt_model_management`:

**399 passed, 2 skipped, 125 subtests passed** (39,14 s). Die 2 Skips sind
bestehende optionale Integrations-/Plattformfälle, keine neuen Skips.

## Volle Unit-Suite

Erstlauf nach der Integration: **2 failed, 2187 passed, 15 skipped,
1326 subtests passed** in 719 s. Die 2 Fehler
(`test_openai_compatible_endpoint.py`: zwei Routingtälle mit
`realtime_model="tiny"` bei Default-Kroko-Engine) wurden durch die
ursprüngliche Startup-Fassung des Gates verursacht (unmanifestiertes
Modell wurde downgegradet). Befund aus den Audit-Events des Fehlerlaufs:
`kroko.pro_refused_community_fallback` für die Realtime-Lane.

Konsequenz: Gate-Semantik auf die etablierte Autoritätsregel korrigiert
(manifestiertes Pro fail-closed, Unmanaged auditiert-übernommen, s.
Abweichungsnachtrag AD07).

Finaler Re-Run nach der Korrektur: **2189 passed, 15 skipped,
1326 subtests passed** in 624,77 s, keine Fehler. Die 15 Skips sind
bestehende optionale Integrations-/Plattformfälle (unverändert seit
22.10.2026). Keine neue GitHub-CI oder RC-Qualifikation damit behauptet;
der Draft-PR stößt die gewöhnliche CI an.

## Nachlauf nach der AD07-Korrektur

- `tests/unit/test_openai_compatible_endpoint.py` (komplett, 20 Fälle) plus
  `tests/unit/test_kroko_unified_runtime.py` (43 Fälle): **63 passed**.
- Betroffene Bestandssuiten (Abschnitt oben): **399 passed, 2 skipped,
  125 subtests passed** (40,09 s, Re-Run nach der Korrektur).
- Voller Re-Run der Unit-Suite läuft; Endergebnis wird hier nachgetragen.

## Nicht ausgeführte Nachweise (NOT_RUN, kein Ersatz durch Mocks)

Echte Lizenz-Positiv-/Negativ-/Ablauf-/Widerrufs-/Timeout-Fälle, nativer
Besitzerprozesswechsel mit Community-Fallback unter Last, reale
Reconnect-/Session-Invalidierung, Linux-/Windows-/Docker-Qualifikation,
Portal-UUID-Bindung. Fehlende Realtests allein begrenzen auf CONDITIONAL.
