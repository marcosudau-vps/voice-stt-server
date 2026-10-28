# Kroko-Modellkatalog – Testevidenz

22.10.2026, lokales Windows, CPython 3.12, pytest 9.1.1.
Basis `acdffc7`, Arbeitsbranch `feat/v2-unified-kroko-catalog`.
Keine realen Modell-Downloads, Portal-/Lizenzanfragen oder nativen Lizenzproben.
Die neue Testsuite sperrt Socketverbindungen und `urllib.request.urlopen`.
Der CLI-Subprozesstest liest ausschließlich das lokale Testfixture.

## Quelldaten

Die bereinigte Entwicklerdatei wurde strikt validiert und ausschließlich aus
freigegebenen Datenobjekten als sortierter 124er-Testmetadatensnapshot geschrieben.
Ein unabhängiger Vergleich über die Original-IDs bestätigt identische Werte
aller elf Felder für sämtliche 124 Einträge.
SHA-256 der bereitgestellten bereinigten Eingabedatei:
`4577d08a8e2bfb657ea28baaa37cee9db24ab08c51b7848a61de601727d7e1f8`.
Die sensitive ursprüngliche Portal-JSON wurde nicht gelesen oder übernommen.

124 Modelle, 105 Pro, 19 Community; Sprachen:
DE, EN, ES, FR, IT, IW, JP, NL, PL, PT, SV, TR.
Chunks 16/32/64/128, Größen S/M/L, Revisionen 001/002.
Zwölf exakte Manifestzuordnungen; 112 ohne bestehende Integritätsauthority.

## Neue Tests

```powershell
python -m pytest tests/unit/test_kroko_catalog.py -q --tb=short
```

**84 bestanden**, 1,72 s beim letzten gezielten Lauf. Abgedeckt sind:
Originalwerte, exakte Sprachcodes, Metadatenextraktion, kombinierte Filter,
Sortierung bei umgekehrter Eingabe, Dateinamen/Traversal/ADS/Staging,
Pflichtfelder und strikte Typen, ID-/Namens-/URL-Konflikte, Host-/Pfad-/Query-
und Credentialinjektion, fehlende URL/Integrität, fremde Hash-/Rechtefelder,
Manifestkonflikte und unveränderte Produktautorität, gemeinsame Diagnosen,
JSON-Doppelfelder, Encoding-/Tiefen-/Größenfehler, Secret-Sentinels an mehreren
Positionen, alle CLI-Befehle/Exitcodes und Scriptaufruf außerhalb des Checkouts.

Ein synthetisch erlaubtes Manifest prüft zusätzlich, dass selbst ein erfülltes
statisches Manifestgate keine technische Zugänglichkeit, Byteprüfung oder
Aktivierungsberechtigung behauptet. Es wird kein Produktionsmanifest geändert.

## Bestehende relevante Unit-/Contracttests

```powershell
python -m pytest tests/unit/test_kroko_catalog.py tests/unit/test_kroko_model_authority.py tests/unit/test_stt_model_management.py tests/unit/test_kroko_onnx_engine.py tests/unit/test_local_model_resolver.py tests/unit/test_protocol_v2_contract.py tests/unit/test_browser_client_contract.py tests/unit/test_server_trigger_contract.py -q --tb=short
```

**283 bestanden, 2 übersprungen, 78 Subtests bestanden**, Exit 0, 61,36 s.
Dieser Lauf enthielt die ersten 81 Katalogtests; anschließend wurden drei
weitere Sicherheits-/Quellenfälle ergänzt und alle 84 erneut erfolgreich geprüft.
Die zwei übersprungenen Tests erfordern ausdrücklich optionale reale Backends.

## Gesamtsuite und Zusatzprüfungen

Die unveränderte CI-Auswahl `tests/unit` wird vollständig ausgeführt.
Vorherige Standardläufe wurden wegen sehr langsamer nativer ONNX-
Sitzungsinitialisierung abgebrochen; daraus wird kein PASS abgeleitet.
Stackdiagnosen ohne Variablenwerte zeigen den realen Wake-Word-Prober in
`onnxruntime.InferenceSession._create_inference_session`. Das betrifft
bestehende Servertests, nicht den neuen Offlinekatalog.

Für den vollständigen lokalen Lauf wurden nur die standardmäßig unbegrenzten
ONNX-Threadzahlen auf eins begrenzt. Echte Modellinitialisierung, Graphprüfung,
Modellbytes und Testauswahl bleiben erhalten; keine Testdeselektion und keine
Produktcodeänderung. Ein externer lokaler Runner verwendet äquivalent:

```python
import onnxruntime as ort
import pytest

original_init = ort.InferenceSession.__init__

def limited_init(self, *args, **kwargs):
    positional = list(args)
    options = positional[1] if len(positional) >= 2 else kwargs.get("sess_options")
    if options is None:
        options = ort.SessionOptions()
    if options.intra_op_num_threads == 0:
        options.intra_op_num_threads = 1
    if options.inter_op_num_threads == 0:
        options.inter_op_num_threads = 1
    if len(positional) >= 2:
        positional[1] = options
    else:
        kwargs["sess_options"] = options
    original_init(self, *positional, **kwargs)

ort.InferenceSession.__init__ = limited_init
raise SystemExit(pytest.main([
    "tests/unit", "-q", "--tb=short", "-o", "faulthandler_timeout=60",
]))
```

Gesamtergebnis: **2230 bestanden, 1 fehlgeschlagen, 15 übersprungen,
1326 Subtests bestanden**, 832,71 s, Exit 1. Alle 84 neuen Katalogtests sind
auch in diesem Lauf erfolgreich. Zehn bestehende WebSocket-Deprecationwarnings.
Der Gesamtlauf wird ausdrücklich nicht als vollständig grün bezeichnet.

Ein bestehender zeitabhängiger Test meldete im Gesamtlauf einen Fehler:
`FastAPIMultiUserWebSocketTests.test_admin_live_keepalive_rescans_without_commit_wakeup`.
Er liegt vor der Ausführung der neuen Katalogtests. Ein isolierter Lauf mit
dem normalen `python -m pytest <node-id> -q --tb=short` bestand (3,59 s);
drei weitere getrennte Wiederholungen bestanden ebenfalls (5,40/4,81/4,86 s),
alle mit Exit 0. Die Beobachtung wird als Timing-Flake eingeordnet, nicht
als durch diese Arbeit behobener Bestandsfehler. Zusätzlich wurde seine gesamte
Testdatei mit derselben ONNX-Threadbegrenzung erneut ausgeführt:
`tests/unit/test_fastapi_server_multi_user.py`: **56 bestanden, 6 Subtests
bestanden**, 43,39 s, Exit 0. Damit bestehen alle ausgeführten Testfälle über
Gesamt- und gezielte Wiederholungsläufe; das erste Gesamt-FAIL bleibt sichtbar.
Keine Änderung am Keepalive-/WebSocketcode oder seinem Test.

`python -m compileall -q` für Modul, CLI und neue Tests sowie
`git diff --check` waren erfolgreich. Lokale Links der neuen Fachdokumentation
und Katalogakte wurden geprüft. Die aus der echten bereinigten Datei
erzeugte CLI-Planansicht bestätigt getrennte `main`-/immutable Quellen,
Manifest-Sollhash, ungeprüfte Bytes und gesperrte automatische Installation.

Keine erzeugten Logs oder Binärartefakte werden committed. Unabhängiger
GitHub-CI-/PR-Review bleibt von lokalem Test-PASS getrennt.
