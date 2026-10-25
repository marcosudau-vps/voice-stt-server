# OpenAI-kompatible HTTP-API – Modulreferenz

**Stand:** 25.10.2026 · **Implementierung:** [`api_fastapi_server/openai_routes.py`](../api_fastapi_server/openai_routes.py) · **Einführung:** PR [#15](https://github.com/marcosudau-vps/voice-stt-server/pull/15)

## Zweck und Modulgrenze

Die OpenAI-kompatiblen HTTP-Endpunkte sind seit PR #15 ein **eigenständiges Router-Modul**. `api_fastapi_server/server.py` erstellt weiterhin die FastAPI-App und bindet den Router über `app.include_router(create_openai_router(...))` ein. Das Modul importiert **nicht** `api_fastapi_server.server`; die Abhängigkeiten werden ausdrücklich beim Appaufbau übergeben.

| Verantwortung | Zuständiger Code |
| --- | --- |
| HTTP-Routen, Multipart-Upload, HTTP-Fehler, Antwortheader, SSE-Streaming, HTTP-Telemetrie | `api_fastapi_server/openai_routes.py` |
| Formular-Parsing, Validierung, unterstützte Formate, Fehler- und Responseformatierung | `VoiceSTT_server/openai_compat.py` |
| Modellkatalog, `whisper-1`-Alias, Lane-/Override-Auflösung | `VoiceSTTService.model_catalog()`, `resolve_openai_model()` in `api_fastapi_server/server.py` |
| Inferenz, Scheduler, Pending-Result-Korrelation | `VoiceSTTService.transcribe_openai()`, `complete_pending_api_transcription()` und bestehender Scheduler |
| Optionaler Bearer-Key und Fehler-Audit | `api_fastapi_server/security/openai.py` über `SecurityService` |

Diese Aufteilung ist ein **Refactoring**, kein neues API-Protokoll und keine eigene Inferenz-Engine. Die OpenAI-HTTP-Routen verwenden denselben serverautoritativen Modell- und Inferenzpfad wie zuvor.

## Öffentliche Routen und Authentifizierung

| Methode | Pfad | Beschreibung |
| --- | --- | --- |
| `GET` | `/v1/models` | Modellliste als `{"object":"list","data":[...]}`; bei Bedarf inklusive des `whisper-1`-Routing-Alias |
| `POST` | `/v1/audio/transcriptions` | Multipart-Audiodatei zur Transkription; normale Antwort oder SSE-Stream |

Die OpenAI-Authentifizierung ist **optional konfigurierbar**: `openai_api_key` bzw. `VOICESTT_API_KEY`. Ohne eingerichteten Key bleibt der Zugriff wie bisher offen. Mit Key muss der Header `Authorization: Bearer <openai-api-key>` exakt passen; sonst folgt HTTP 401 (`WWW-Authenticate: Bearer`, OpenAI-Fehlerformat) und ein `authentication.failed`-Audit. Admin-Keys und Logtokens sind **keine** Ersatzberechtigungen. Details: [Zentrale Server-Authentifizierung](server-authentication.md).

`openai_api_enabled=false` deaktiviert den Transkriptionsendpunkt mit HTTP 404. Die Prüfung dieser Einstellung findet vor der Transkriptionsauthentifizierung statt. Die Modellliste hat diese spezifische Deaktivierungsprüfung nicht.

## Multipart-Parameter und Modellauflösung

Pflichtfelder des POST: `file` (unterstützte Endungen `.flac`, `.mp3`, `.mp4`, `.mpeg`, `.mpga`, `.m4a`, `.ogg`, `.wav`, `.webm`) und `model`.

Weitere implementierte Formularparameter: `language`, `prompt`, `temperature`, `response_format`, `timestamp_granularities[]`, `stream`, `include[]` (aktuell `logprobs`), `threshold`, `known_speaker_names[]`, `known_speaker_references[]`. Die Parserregeln und Wertebereiche werden ausschließlich in `VoiceSTT_server/openai_compat.py` definiert. Wort-Zeitstempel sind an `verbose_json` gebunden.

Das Modell `whisper-1` dient als kompatibler Alias für das konfigurierte finale Routing. Für diesen Alias kann das Zielmodell über das Formularfeld `voicestt_model` (alternativ `model_override`) oder den Header `X-VoiceSTT-Model` übersteuert werden; der Formular-Override hat Vorrang. Nicht zulässige Overrides werden abgewiesen. Der Server bleibt die Authority für aufgelöste Modelle, Verfügbarkeit und Lanes.

Die Transkriptionsantwort kann die Header `X-Request-ID`, `X-VoiceSTT-Requested-Model`, `X-VoiceSTT-Resolved-Model`, `X-VoiceSTT-Route`, bei Overrides zusätzlich `X-VoiceSTT-Override-Model` und `X-VoiceSTT-Override-Source` enthalten. Seit dem PR-#15-Korrekturlauf trägt auch die Authentifizierungs-Fehlerantwort `X-Request-ID`. Die exakte Fehlerpfad-/Headerabdeckung entspricht dem bestehenden Implementierungsvertrag.

## Antwortformate und Streaming

| `response_format` | Verarbeitung |
| --- | --- |
| `json` | JSON mit Transkripttext und Nutzungs-/Dauerangaben |
| `text` | Textantwort |
| `verbose_json` | Text, Segmente, Sprache, Dauer; optional Wort-Zeitstempel |
| `srt` / `vtt` | Untertiteltext |
| `diarized_json` | Diarisierungs-kompatibles JSON; aktuell lediglich **Single-Speaker-Fallback**, kein echtes Diarisierungsmodell |

Mit `stream=true` liefert der POST `text/event-stream`, zunächst passende `transcript.text.delta`-Nachrichten und nach erfolgreich abgeschlossener Inferenz `transcript.text.done`; bei Streamfehlern wird ein Fehlerereignis ausgegeben. Für `diarized_json` werden zusätzlich Segmentereignisse ausgegeben. Die SSE-Datenformatierung liegt im bestehenden Kompatibilitätsmodul; die Erzeugung/Übermittlung im Router. Kein eigener Scheduler wird angelegt.

Validierungsfehler folgen dem OpenAI-kompatiblen Fehlerobjekt `{"error":{"message":...,"type":...,"param":...,"code":...}}`. Übergrößen verwenden HTTP 413; nicht verfügbare/ungültige Modellrouten folgen den bestehenden Fehlervorgaben. Unbehandelte Transkriptionsfehler werden als HTTP 500 ausgegeben. Die Fehlerbehandlung und der Auditpfad sind Teil der Abnahme, nicht beliebig veränderbar.

## Telemetrie, Tests und Grenzen

Der Router korreliert Request-, Session-, Transkriptions- und optionale Client-ID und verwendet die vorhandenen strukturierten Events, Audit- und Performance-Sinks. Keine neue Log- oder Modell-Authority wird eingeführt.

**Relevante Vertragstests:**

```bash
python -m pytest -q tests/unit/test_openai_compatible_endpoint.py tests/unit/test_server_security_modularization.py
```

Die Tests prüfen reale HTTP-Aufrufe über einen FastAPI-Testclient, einschließlich Formate, Modellrouting, Parallelität, SSE und Bearer-Fehlern. Weitere Tests und die CI-Qualifikation stehen unter [Testing](testing.md) sowie der [PR-#15-Arbeitsakte](.archiv/pr15_final_abnahmevorbereitung/2026-10-25_07_ABSCHLUSSBERICHT.md). Der [Modularisierungsfahrplan](architecture/server-modularization-roadmap.md) beschreibt spätere Extraktionen; weder Scheduler- noch V2-WebSocket-Umbau gehören zu diesem PR.
