# AP-KR-020 Fortsetzung – Lizenzentscheidung (Nachtrag 23.10.2026)

Status am 23.10.2026: Der Schnittstellenblocker aus
[2026-10-22_SCHNITTSTELLEN_LIFECYCLE.md](2026-10-22_SCHNITTSTELLEN_LIFECYCLE.md)
ist für den produktiven Pfad entschieden und die davon unabhängige
Runtimeintegration implementiert. Diese Datei ergänzt die historische Akte;
sie schreibt sie nicht um.

## 1. Neue Evidenz seit dem 22.10.2026

Ein unabhängiger Python-WebSocket-Test gegen den Lizenzserver lieferte mit
echtem On-Premise-Key und der konkreten Pro-Modell-UUID
`c529370f-77c7-4348-b5dc-2e9fcda1a568` eine positive Antwort
(`allowed: True`, `remaining_seconds: 86400`, `max_connections: 2`,
`offline_timeout: 60`, `report_interval: 15`, `expirable: False`,
`password_present: True`).

Das belegt: **Eine modellbezogene Lizenzprüfung ohne zuvor gestarteten
Recognizer ist technisch möglich.** Es belegt nicht: pauschale Berechtigung
aller Pro-Modelle, modellunabhängige Keyvalidierung, dauerhafte Freigabe,
garantierte Widerrufserkennung oder einen dokumentierten öffentlichen
Drittanbieter-API-Vertrag.

## 2. Erneute Prüfung des gepinnten Upstream-Commits

Geprüft am 23.10.2026 gegen
[`license.h` auf `8657e655192623b98d7708e742a72987f953d3a2`](https://github.com/kroko-ai/kroko-onnx/blob/8657e655192623b98d7708e742a72987f953d3a2/sherpa-onnx/csrc/license.h)
(derselbe Authority-Stand wie `VoiceSTT/kroko/buildinputs.py`;
kein Upstreamwechsel, keine neue Nativeprüfung):

- Der Client baut `wss://<server>/ws/v1/<key>/<modelId>` – die Prüfung ist
  **protokollseitig immer modellgebunden**. Der Python-Probe-Erfolg nutzt
  exakt dieses Protokoll (gleiche Antwortfelder: `allowed`,
  `remaining_seconds`, `max_connections`, `offline_timeout`,
  `report_interval`, `expirable`, Passwortfeld). Die Probe bestätigt damit
  die Modellbindung, keine globale Keygültigkeit.
- `allowed`/`is_finish`/Zeitfelder sind gewöhnliche mutable Felder ohne
  Snapshot-Lock; die erste Antwort setzt `allowed` vor dem weiteren Parsing;
  Fehler sind frei formulierte Texte ohne typisierte Codes
  (Key ungültig vs. Ablauf vs. Widerruf vs. fehlendes Modellrecht vs.
  Technikfehler sind nicht unterscheidbar).
- `BanafoLicense::getInstance(key, modelId)` ist ein Prozess-Singleton: die
  erste ID bindet den Prozess; `mActivated` wird einmalig kopiert (kein
  laufender Widerrufssnapshot); der Netzwerkthread läuft in einer endlosen
  Reconnect-Schleife; `check_offline_timeout()` ruft bei überschrittener
  Frist `std::exit(1)` auf (fataler Prozess-Exit, keine Exception).
- `features` ist eine untypisierte Stringliste ohne Whitelist und ohne
  Zuordnung zu Server-Modell-IDs. Eine erfolgreiche Aktivierung berechtigt
  deshalb nur genau dieses Modell.

Fazit: Die Codeanalyse vom 22.10.2026 bleibt gültig. Die neue Probe
widerlegt keinen einzigen der dokumentierten Punkte; sie schärft die
Modellbindung und den konservativen TTL-Rahmen (siehe 4).

## 3. Variantenentscheidung A / B / C

- **A – schmale, versionierte Ergänzung des nativen Lizenzclients**
  (strukturierter, snapshot-gelockter Statusexport): Technisch der saubere
  Zielvertrag. Erfordert nativen Patch, `PATCH_SET_REVISION`-Bump, neue
  plattformspezifische Fingerprints/Guard-Digests und reale
  Linux-/Windows-Qualifikation. **Als versionierter Folgeauftrag
  spezifiziert, in dieser Fortsetzung nicht implementiert** (kein
  Native-Toolchain-Lauf, keine Live-Qualifikation, keine erfundene
  Anbietersemantik).
- **B – isolierte modellbezogene Prüfung mit eigener Lebensdauer:**
  Als Python-Neuimplementierung des beobachteten WebSocket-Protokolls
  **ausdrücklich verworfen** (eigene Ersatzimplementierung des
  Lizenzprotokolls, kein stabiler Produktvertrag, im Auftrag verboten).
  Als isolierter *nativer* Kandidatprozess ist B mechanisch identisch mit C
  und wird nicht als eigener Pfad verfolgt.
- **C – bestehender nativer Mechanismus in der späteren
  Besitzerprozessgeneration: GEWÄHLT und implementiert.**
  Der einzig belastbare produktive Nachweis bleibt die erfolgreiche native
  Aktivierung des ausdrücklich konfigurierten, integritätsgeprüften,
  berechtigten Pro-Modells in der aktuellenOwner-Generation plus
  generationsgebundene Readiness. Keine globale Freigabe, keine
  Probe-neben-Community, kein Community-Default-Tausch für die Prüfung.

Die Produktformel bleibt unverändert:

```text
pro_enabled = api_key_present AND NOT force_community
              AND license_validation_successful
```

mit `license_validation_successful` = Status `VALID` mit an Generation,
opake Credentialrevision, Payloadidentität, bestätigte Modellrechte,
Aktualität und lebenden Besitzerprozess gebundenem Nachweis.

## 4. Konservative fail-closed Umsetzung und Nachweisgrenzen

- `VALID`-Nachweise verfallen nach spätestens **60 Sekunden** ohne frische
  Bestätigung (`DEFAULT_MAX_PROOF_AGE_SECONDS = 60.0`). Das ist eine
  ausdrücklich konservative *Interpretation* des beobachteten
  `offline_timeout: 60` (der Anbieter selbst traut einem Offline-Client
  nicht länger), kein behaupteter Anbietervertrag. Kürzere
  Backend-Grenzen werden übernommen, längere abgewiesen.
- `INVALID` (autorisierte Ablehnung) klebt an der Generation; blinde
  Retries ohne Intentwechsel sind verweigert. `CHECK_FAILED` ist jederzeit
  wiederholbar. Unbelegbare Prüfung bedeutet Community, niemals Pro.
- Unmanifestierte Kroko-Modelle sind nicht prüffähig und werden verweigert
  (keine ungeprüfte Freischaltung zusätzlicher Modelle).
- Der produktive Verifikations-Backend ist `UnqualifiedLicenseVerifier`
  (vergibt nichts). Echte `VALID`-Nachweise erfordern den qualifizierten
  Backend aus Folgeauftrag A plus autorisierte Testumgebung; synthetische
  Verifizierer existieren nur in `tests/unit/test_kroko_unified_runtime.py`.
- Keine weiteren Live-Lizenzserverkontakte ohne ausdrücklich freigegebenen
  Testumfang. In dieser Fortsetzung fand kein einziger statt.
