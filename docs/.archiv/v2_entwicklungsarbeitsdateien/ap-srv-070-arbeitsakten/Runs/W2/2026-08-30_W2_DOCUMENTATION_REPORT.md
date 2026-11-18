# AP-SRV-070 — W2 DOCUMENTATION REPORT

**Datum:** 2026-08-30
**Teilblock:** W2 — Product Surface / Documentation / Repository Hygiene
**Prompt-Datei:** `_workflow-tools/AP-SRV-070/Prompts/AP-SRV-070_W2_PRODUCT_SURFACE_HYGIENE_UPDATED.md`
(Hinweis: Die im Auftrag genannte Datei `AP-SRV-070_W2_PRODUCT_SURFACE_HYGIENE.md`
existiert im Prompts-Ordner nicht mehr; die einzige vorhandene W2-Prompt-Datei
ist die `_UPDATED`-Variante mit identischem Distributed-HEAD-Bezug (`0e191a9…`).
Sie wurde als verbindliche Grundlage verwendet.)
**Ausgangsbasis:** Distributed HEAD `0e191a915d46bc4afcd88ab52049bfc075979cc7`
(= W1B-C1-Commit, W2 ready = JA laut `Runs/W1B-C1/2026-08-30_W1B_C1_STATE.md`)

---

## 1. W2-01 — README.md / Product Surface

`README.md` wurde erweitert (nicht ersetzt): die bestehende Library-zentrierte
Struktur (Install, Microphone Example, External Audio, Configuration
Reference, Engine-Übersicht) bleibt bestehen, da `VoiceSTT` primär eine
Python-Bibliothek mit dem FastAPI-Server als einer Nutzungsform ist.

Ergänzt/korrigiert:

- **Features**-Liste: neuer Hinweis auf Protokoll v2 (`/ws/v2`), das
  server-autoritative Activation-Lifecycle-Modell, die Settings-Control-Plane
  sowie den kanonischen, paketgebundenen Wake-Word-Build-Katalog
  (`GET`/`POST /api/v2/wake-words[/refresh]`), zusätzlich zur bestehenden
  Erwähnung von Legacy-`/ws/transcribe`.
- Neuer Abschnitt **„Protocol v2"** unter „Server Example": Handshake-Kurzform,
  server-autoritatives Activation-Lifecycle (`activation.command`/
  `command.ack`, `eventId`/`eventSeq`/`stateVersion`, `session.snapshot`),
  ausdrückliche Einordnung von `/ws/transcribe` (v1) als dauerhaft benötigter
  Kompatibilitätspfad (nicht Abbau-Kandidat), Settings-v2-Endpunkte und
  Wake-Word-Katalog-v2-Endpunkte, mit Verweis auf `docs/fastapi-server.md` und
  `docs/client-development/`.
- Dokumentationsliste: toter Link auf das jetzt archivierte
  `docs/session-wakeword-erweiterung.md` durch Verweis auf die aktive
  Nachfolgedokumentation ersetzt (`docs/client-development/09-…md`).
- Keine neuen Packaging-/PyPI-Versprechen hinzugefügt; der bestehende
  `pip install "VoiceSTT[...]"`-Install-Abschnitt blieb unverändert, da W3
  (Wheel-Hard-Gates für den Wake-Word-Katalog) noch nicht gelaufen ist.
- Keine Agenten-/AP-/Root-Workflow-Interna im Produkttext.

## 2. W2-02 — docs/fastapi-server.md

- `## WebSocket Protocol` in `## WebSocket Protocol (legacy v1:
  \`/ws/transcribe\`)` umbenannt, mit explizitem Hinweis: Kompatibilitätspfad,
  nicht zur Entfernung vorgesehen, neue Clients gegen v2.
- Neuer Abschnitt **„## Protocol v2"**: `/ws/v2`, Transport-Isolation von v1
  (Invarianten aus `test_protocol_v1_v2_boundary.py`/W1A geprüft),
  `serverVersion`/`serverCommit`/`supportedProtocolVersions`, vollständiges
  `hello`-Beispiel (gegen `protocol_v2/handshake.py` verifiziert — inkl.
  `supportedProtocolVersions`, `clientVersion`, `clientCommit`, `clientRunId`,
  `requestedSession.trigger`, `requestedSession.wakeWordIds`,
  `runtimeSuppression`, die alle laut `_parse_hello_payload` Pflichtfelder
  sind), Admission-Verhalten, Unterabschnitt „Server-authoritative activation
  lifecycle" mit den realen Wire-Namen (`activation.command`, `command.ack`,
  `eventId`/`eventSeq`/`stateVersion`, `session.snapshot`) gegen
  `protocol_v2/schema.py` geprüft.
- Neuer Abschnitt **„## Settings v2"**: `/api/v2/settings/schema`,
  `/api/v2/settings/server` (GET/PATCH), `baseSettingsRevision`,
  `requestedSettings`/`effectiveSettings`/`settingsRevision`, Apply-Policies
  — gegen `settings_control.py::APPLY_POLICIES` geprüft und dabei ein
  Falsch-Zitat korrigiert (`startup` existiert nicht; korrekt ist
  `server_restart`).
- „Server Overview"-Endpunktliste um `/ws/v2`, die Settings-v2-Routen und
  Querverweise auf die neuen Abschnitte ergänzt; `/ws/transcribe` dort explizit
  als „legacy (v1)" markiert.
- Bestehender Wake-Word-Abschnitt (v1 `GET /api/wake-word`,
  `--openwakeword-model-paths`) unverändert gelassen — er wurde bereits in
  W1B-C1 auf den aktuellen Backend-Health-/Kein-Default-Vertrag korrigiert und
  ist weiterhin zutreffend.

## 3. W2-03 — Aktive technische Dokumentation bereinigt

Bekannte Befunde aus dem Prompt, geprüft und behandelt:

1. `activation_command.py` → `activation_commands.py`: **kein Treffer mehr**
   in aktiver Doku (repo-weite Suche); W1A hatte dies bereits korrigiert.
   Keine Änderung nötig.
2. Toter Verweis auf `docs/ARCHITECTURE.md`: Datei existiert nirgends im
   Repository. Verweis in `docs/module-map.md` entfernt.
3. Persönlicher absoluter Pfad `D:/Projekte/STT/VoiceSTT/VoiceSTT`: einziger
   Treffer in `docs/api-compatibility.md` (Validierungsbefehl), entfernt.
4. Sprach-/Terminologie-Inkonsistenzen: siehe Punkt 5 unten
   (`AP-SRV-070`-Zeitform) als Hauptbefund; `docs/configuration.md` wurde
   geprüft und zeigte keine vergleichbaren Inkonsistenzen.
5. Formulierung „v1 behält kompakte IDs bis AP-SRV-070" geschärft: repo-weite
   Suche nach `bis AP-SRV-070` / äquivalenten Zeitform-Aussagen fand **9**
   Stellen, die AP-SRV-070 fälschlich als künftigen Zeitpunkt des
   v1-Transport-Abbaus oder der ID-Migration darstellten. W1A/W1B haben
   jedoch nur gezielten toten Code entfernt und `activation_config.mode ==
   "legacy"` sowie die kompakten v1-IDs ausdrücklich als `KEEP_REQUIRED`
   bestätigt (siehe `Runs/W1A/…SCOPE_TRACE.md` §6, `Runs/W1B/…SCOPE_TRACE.md`
   §3). Alle 9 Stellen wurden auf den tatsächlichen Ist-Zustand korrigiert
   (keine ID-Migration implementiert, keine neue Semantik erfunden — reine
   Zeitform-/Tatsachenkorrektur):
   - `docs/einheitliche-triggerarchitektur.md` (6 Stellen: §1 Einleitung,
     Legacy-Mode-Autorität, §12.2 Boundary, §12.10 Koexistenz, §13.6
     Abgrenzung, §14.8 `wake_word_buffer_duration` — Letztere korrigierte
     zugleich einen internen Widerspruch zu §14.11 desselben Dokuments, das
     bereits korrekt „bleibt Legacykompatibilität" sagt)
   - `docs/api-compatibility.md` (1 Stelle: „legacy removal is AP-SRV-070")
   - `docs/wake-words.md` (1 Stelle: `wake_word_buffer_duration`-Abschaffung
     — widersprach dem in W1B tatsächlich getroffenen und dokumentierten
     Entschluss, den Parameter zu erhalten)
   - `docs/client-development/08-protokollabgrenzung.md` (1 Stelle)
   - Zusätzlich zwei Quellcode-Docstrings/-Kommentare mit derselben falschen
     Zeitform (`api_fastapi_server/protocol_v2/schema.py`,
     `api_fastapi_server/protocol_v2/__init__.py`,
     `api_fastapi_server/server.py:2255-2257` und `:9375`) — reine
     Kommentartext-Korrektur, keine Verhaltensänderung; per `py_compile`
     verifiziert.
6. `docs/session-wakeword-erweiterung.md` (stale `default_model`): siehe W2-04
   — archiviert statt korrigiert, wie im Prompt vorgesehen. Zusätzlich wurden
   dieselben jetzt widerlegten `default_model`-Aussagen in der aktiven
   Nachfolgedokumentation `docs/client-development/09-…md` gefunden (Zeilen
   304-305, 377 vor Korrektur) und dort korrigiert — dieser Fund ging über die
   im Prompt genannte Liste hinaus, war aber sachlich identisch begründet
   (per Test `test_wakeword_registry_resolve_without_ids_returns_nothing` und
   direkter Prüfung von `PUT /api/wake-word` in `server.py:7809-7866`
   verifiziert: kein Fallback auf ein Standardmodell mehr).

Zusätzlich auditiert, keine Änderung nötig:

- `docs/configuration.md` — aktuell, keine Stale-Referenzen gefunden.
- `docs/client-development/01–07`, `09` — 09 s.o.; 01–07 zeigten in der
  Suche nach `AP-SRV-070`/`default_model`/`ARCHITECTURE.md`/personenbezogenen
  Pfaden keine Treffer.

## 4. W2-04 — Historische Dokumente archiviert

Vor jeder Archivierung wurde geprüft, ob noch gültige Produktinformation nur
dort existiert. In allen vier Fällen ist die fachliche Information bereits
vollständig oder besser in aktiver Doku vorhanden; nichts musste migriert
werden, weil nichts Neues/Gültiges ausschließlich dort stand:

| Dokument | Ziel | Begründung |
|---|---|---|
| `Planning/logging-fixes-implementierungsplan.md` | `docs/.archiv/logging-fixes/2026-07-31_…md` | Historischer Implementierungsplan, laut eigenem Status „Implementiert, … verifiziert"; Fachvertrag lebt vollständig in `docs/structured-logging.md`. |
| `api_fastapi_server/MULTI_USER_IMPLEMENTATION_GUIDE.md` | `docs/.archiv/multi-user-design/2026-07-25_…md` | Vor-Implementierungs-Designdokument (nennt noch `RealtimeSession` als Zielentwurf); die tatsächliche Multi-User-Architektur ist in `docs/module-map.md` und den Server-Docs beschrieben. |
| `docs/stt-server-specification.md` | `docs/.archiv/desktop-client-spec/2026-07-25_…md` | Übergabespezifikation für einen externen Desktop-Client mit Stand „12.08.2026"; vollständig redundant zu `docs/client-development/` und `docs/fastapi-server.md`, keine inbound-Links aus aktiver Doku. |
| `docs/session-wakeword-erweiterung.md` | `docs/.archiv/session-wakeword/2026-07-26_…md` (bestehender Archivordner derselben Aktion) | S20; enthielt stale `default_model`-Beschreibung und einen alten Verzeichnis-Scan-Fallback, der seit W1B nicht mehr existiert. Fachvertrag vollständig durch `docs/wake-words.md` und `docs/client-development/09-…md` abgedeckt. |

Archivdatum-Präfixe entsprechen dem tatsächlichen `git log --follow
--diff-filter=A`-Erstellungsdatum jeder Datei, wie von der Konvention in
`docs/.archiv/README.md` gefordert. Archivierte Inhalte wurden **nicht**
inhaltlich verändert (`git mv`, keine Textänderung); nur die vier Dateien, die
aktiv auf `docs/session-wakeword-erweiterung.md` verwiesen
(`README.md`, `docs/README.md`, `docs/client-development/README.md`,
`VoiceSTT_server/README.md`), wurden auf die aktive Nachfolgedokumentation
umgebogen.

**Bewusst nicht verändert:** Das Register in `docs/.archiv/README.md`
(Tabelle „Abgeschlossene und laufende Änderungsaktionen") wurde nicht um neue
Zeilen für diese vier Archivierungen erweitert. Diese Verschiebungen sind
Repository-Hygiene innerhalb des bereits unter `_workflow-tools/AP-SRV-070/`
getrackten W2-Laufs, keine eigenständige „größere Änderungsaktion" im Sinne
dieses Registers (keine Architektur-/API-/Datenformat-/Sicherheits-/
Deployment-Änderung). Offene Entscheidung für einen künftigen Lauf, falls
gewünscht: das Register nachträglich um einen Verweis auf diese W2-Archivierung
zu ergänzen.

## 5. Nicht im Mandat behandelt (Befund, keine Aktion)

`VoiceSTT/assets/wakeword_models/generate_models_json.ps1:192` enthält
dieselbe stale „…Legacyspiegel für den v1-Pfad bis AP-SRV-070"-Formulierung
und erzeugt zusätzlich noch das inzwischen entfernte
`openwakeword_models`-Manifestfeld — im Widerspruch zum tatsächlichen,
kanonischen Generator `tools/sync_wakeword_assets.py` (dessen Ausgabe dieses
Feld seit W1B nicht mehr enthält). Das Skript ist repo-weit unreferenziert
(keine Doku, kein anderes Skript ruft es auf). Es steht nicht auf der im
Prompt vorgegebenen Löschliste (§ W2-05) und wurde daher **nicht** verändert
oder gelöscht, um das Mandat nicht eigenmächtig zu erweitern. Empfehlung: als
eigener, kleiner Korrekturkandidat für einen künftigen Lauf vormerken.
