# AP-SRV-070 — W4A — Model Manifest Report

**Datum:** 2026-08-31
**Teilblock:** W4A-07 / W4A-08

---

## 1. Lizenzprüfung (W4A-07, „Prüfe die tatsächliche Lizenz")

Geprüft wurde die reale Upstream-Quelle `Banafo/Kroko-ASR` auf Hugging Face,
lesend über die öffentliche API und die Raw-Dateien.

| Signal | Befund |
|---|---|
| Model-Card `license` | `other` |
| Model-Card `license_name` | `test` |
| Model-Card `license_link` | `LICENSE` |
| Datei `LICENSE` | **0 Bytes** (Git-Empty-Blob `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391`) |
| README-Prosa | bezeichnet die Community-Modelle als CC-BY-SA lizenziert |
| Repository | öffentlich, nicht gated |
| Repo-Revision zum Prüfzeitpunkt | `d45212aeb212dd66083dd22710c9954f40ff8cc1` |

### Bewertung

Die Signale widersprechen sich. Die maschinenlesbare Lizenzangabe ist `other`
mit dem Platzhalternamen `test`, und die dort **verlinkte Lizenzdatei ist
leer**. Dem steht eine Marketing-Aussage in der README gegenüber, die
CC-BY-SA behauptet.

Eine leere Lizenzdatei mit dem Namen „test" ist keine belastbare
Redistributionsgrundlage. Eine README-Prosa ist keine Lizenzgewährung. Damit
greift die Regel des Prompts:

> Wenn nicht eindeutig: NICHT in öffentliches Git/PyPI/Image aufnehmen,
> kontrollierten, hashverifizierten Provisioning-Pfad definieren, Status
> `POLICY_REQUIRED` oder gleichwertig dokumentieren.

**Entscheidung: kein Kroko-Modell wird gebündelt.** Community-Einträge tragen
`redistributionStatus: POLICY_REQUIRED`, Pro-Einträge `PROHIBITED`. Sobald
upstream eine eindeutige Lizenz veröffentlicht, kann der Status auf `ALLOWED`
gehoben und `manifestRevision` erhöht werden; der Pfad dahin ist im Manifest
unter `licensePolicy.resolutionPath` festgehalten.

Die vollständige Beweislage steht maschinenlesbar im Manifest
(`licensePolicy.evidence`), damit ein späterer Leser die Entscheidung
nachvollziehen kann, ohne die Recherche zu wiederholen.

## 2. Manifest (`VoiceSTT/assets/kroko/models.json`)

`schemaVersion: 1`, `manifestRevision: 1`. **Nur Metadaten — keine
Modelldatei.** 12 Einträge:

### Community (4) — upstream-verifiziert

| ID | Datei | Sprache | Bytes | SHA-256 (gekürzt) |
|---|---|---|---|---|
| `kroko-de-community-64-l` | `Kroko-DE-Community-64-L-Streaming-001.data` | de | 155 839 333 | `0013d4b3…` |
| `kroko-de-community-128-l` | `Kroko-DE-Community-128-L-Streaming-001.data` | de | 155 836 296 | `8d39babf…` |
| `kroko-en-community-64-l` | `Kroko-EN-Community-64-L-Streaming-001.data` | en | 155 839 341 | `59a1e64c…` |
| `kroko-en-community-128-l` | `Kroko-EN-Community-128-L-Streaming-001.data` | en | 155 836 304 | `095f7ea4…` |

Alle vier: `tier=community`, `requiresRuntimeVariant=free`,
`licenseClass=community-unresolved`, `redistributionStatus=POLICY_REQUIRED`,
`provenance.kind=upstream-verified` mit immutabler Revision
`d45212aeb212dd66083dd22710c9954f40ff8cc1`.

**Herkunftsnachweis:** Die SHA-256 stammen aus den LFS-Metadaten des
Upstream-Repos und wurden gegen die lokal vorhandenen Kopien unter
`S:\MODELS\stt\kroko_asr\` geprüft — **alle vier stimmen byte-genau überein**
(Hash und Größe). Die manifestierten Werte sind also nicht behauptet, sondern
beidseitig belegt.

### Pro (8) — betreiberprovisioniert

`Kroko-DE-Pro-{16,32,64,128}-{L,M}-Streaming-001.data`, alle mit
`tier=pro`, `requiresRuntimeVariant=pro`, `licenseClass=commercial`,
`redistributionStatus=PROHIBITED`, `provenance.kind=operator-provisioned`.

Die SHA-256 dieser Einträge stammen aus den **lizenzierten Kopien des
Betreibers** auf dieser Maschine und dienen ausschließlich der Integritäts- und
Variantenprüfung. Sie sind ausdrücklich keine Redistributionsfreigabe und
enthalten keinerlei Modellinhalt — ein Hash ist kein Modell und kein Secret.
Der Prompt verlangt für private Provisionierung genau das: „nur mit
manifestierter Identität/Hash und klarer Secret-/Lizenzgrenze".

*Hinweis für den Betreiber:* Falls diese Pro-Hashes nicht in einem öffentlichen
Repository stehen sollen, ist das ein einzeiliger Eingriff pro Eintrag
(`sha256` leeren); die Integritätsprüfung fällt dann für Pro-Modelle auf die
Größenprüfung zurück.

## 3. Was das Manifest ersetzt

Vorher löste `resolve_kroko_model()` ein Modell auf, indem es Kandidatenpfade
abklapperte und die **erste namentlich passende Datei** zurückgab — ohne Hash,
ohne Lizenzklasse, ohne Variantenbezug; existierte gar nichts, wurde der
Rohpfad durchgereicht. Ein beliebiger Ordnerinhalt war damit faktisch
Produkt-Authority.

Jetzt kennt die Authority (`VoiceSTT/kroko/models.py`) zu jedem bekannten
Modell Identität, Integrität, Lizenzklasse und die geforderte Runtime-Variante:

- `locate_model()` liefert einen **Bericht** statt eines nackten Pfades:
  manifestiert ja/nein, Fundort, verifiziert ja/nein, konkrete Probleme,
  durchsuchte Roots.
- `verify_model_file()` erkennt Größen- und Hash-Abweichungen.
- `check_variant_compatibility()` verweigert Pro-Modell auf Free-Runtime und
  umgekehrt — und behandelt eine **unbekannte** Runtime-Variante ebenfalls als
  inkompatibel statt als „passt vermutlich".
- `describe_local_availability()` liefert ein Inventar; die Verfügbarkeit wird
  **berechnet** und steht bewusst nicht im Manifest, weil sie eine Eigenschaft
  der Maschine ist, nicht des Produkts.

Explizite externe Modellpfade bleiben als Operator-Override möglich, werden
aber als `unmanaged` gekennzeichnet statt still gesegnet.

## 4. Offline-/Runtime-Vertrag (W4A-08)

**Vertragsänderung:** `auto_download_model` defaultete vorher auf
`not offline_models_enabled(...)` — ein normaler Serverstart lud also selbst
Modelle von Hugging Face. Das widerspricht „kein spontaner Modell-Download beim
normalen Serverstart" direkt.

Neu: Download ist **standardmäßig aus**. Er passiert nur bei ausdrücklicher
Freigabe über `engine_options["auto_download_model"]=True` oder
`VOICESTT_KROKO_ALLOW_MODEL_DOWNLOAD=1`; Offline-Modus überstimmt weiterhin
alles. Ein fehlendes Modell ist jetzt ein klarer Fehler, der nennt, was zu
provisionieren ist, welchen SHA-256 die Datei haben muss und wie ein Download
bei Bedarf explizit erlaubt wird.

**Zwei bestehende Tests mussten deshalb angepasst werden** — sie pinnten genau
das alte Download-by-default-Verhalten fest, das W4A-08 ersetzt. Sie testen
jetzt den expliziten Opt-in-Pfad und heißen entsprechend; zusätzlich belegen
zwei neue Tests, dass ohne Opt-in **kein** Download stattfindet und dass der
Env-Opt-in greift. Details im Test-Report.

Kein spontaner Kroko-Source-Build beim Serverstart: unverändert gegeben — der
Builder ist ein separates CLI (`stt-install-kroko`) und wird vom Server nie
aufgerufen.

## 5. Verifikationstiefe zur Laufzeit

Provisionierung verifiziert immer per SHA-256. Der Laufzeitpfad prüft
standardmäßig Existenz, Größe und Variante und re-hasht ein 150-MB-Modell nur
auf ausdrücklichen Wunsch (`VOICESTT_KROKO_VERIFY_MODEL_HASH=1`). Begründung:
Der Moment, in dem ein falsches oder abgeschnittenes Modell auffallen muss, ist
die Provisionierung; ein erneuter Voll-Hash bei jedem Serverstart kostet reale
Startzeit und fängt praktisch nur noch stille Bitfehler ab. Beide Modi sind
getestet.
