# PR #15 – Befunde und Abweichungen (25.10.2026)

Legende: K=kritisch, H=hoch, M=mittel, N=niedrig. Status: OFFEN/BEHOBEN/ZURÜCKGESTELLT/KEIN_MANGEL.

## 1. Befunde aus Prüfaufträgen A–D

| # | Schwere | Befund + Beleg | Auswirkung | Entscheidung/Korrektur | Verifikation |
| --- | --- | --- | --- | --- | --- |
| F-01 | N | Auth-Fehlerpfad im OpenAI-Router ohne `X-Request-ID` (`openai_routes.py:104-111`) | Client-Korrelation erschwert, kein Funktions-/Sicherheitsbruch | Zurückgestellt: keine beauftragte Invariantenverletzung, kein Fix ohne Scope-Risiko | HTTP-Vertragstests grün |
| F-02 | N | Ungültige `openai_model_aliases`-Route → generisch 500 statt 400 (`server.py:7704`) | Unschärfe im Fehlercode, kein Rechte-/Datenrisiko | Zurückgestellt wie F-01 | Routing-Tests grün |
| F-03 | N | Tote Fassade `admin_key_matches` ungenutzt; `LOCAL_ADMIN_HOSTS` in `admin.py`+`logs.py` dupliziert | Driftgefahr, kein Verhaltensbruch | Zurückgestellt (Stil, kein Fix-Grund per §11) | Grep + Admin-Tests grün |
| F-04 | N | Log-Token-Pruning nur bei `issue`; `validate_log_access` ohne Admin-Pfad (kein Aufrufer) | Wachstum bei vielen Sessions; keine Rechteausweitung nachweisbar | Zurückgestellt | Log-Tests + Regression (125 passed) grün |
| F-05 | N | Kroko-Adapter ohne Server-Call (korrekt isoliert) | Live-Pfad ungeprüft, aber genau das Beauftragte | Kein Mangel: kein Auto-Call gefordert | Adapter-Negativtests grün |
| F-06 | N | `recognizer` nicht-dict asymmetrisch (Resolver ignoriert, Engine wirft); `None`-Key an Native durchgereicht | Fail-closed, dokumentiert | Kein Mangel | C1-Paritätstests grün |
| F-07 | N | `stop()`-Exception könnte Startup-Exception maskieren (Mock-Ebene) | Diagnoseschärfe, kein Cleanup-Verlust | Zurückgestellt | Lifespan-Test grün; Doppel-Cleanup-Analyse ohne verdeckten Fehler |
| F-08 | N | Arbeitsbaum zu Beginn durch `install_windows_cpu.ps1`-Rest aus `main` verschmutzt | Kein PR-Inhalt, Verwechslungsrisiko | Behoben: `git restore`, Tree clean verifiziert | `git status` clean |
| F-09 | M | Archiv-README: selektive Kroko-Arbeit fälschlich PR #14 zugeordnet | Falsche Implementierungszuschreibung | **Behoben:** Zeile korrigiert (Impl-PR #15 / Ref-PR #14, nicht gemergt) + Registerzeile dieser Akte | Diff + Linkprüfung |

## 2. Abweichungen vom Plan

Keine funktionalen Abweichungen: OpenAI-Adapter-Grenze, vier Security-Gates,
Kroko-Bausteine ohne Runtime-Anschluss, unveränderte V2-/Persistenz-/Modellverträge —
alle Planpunkte erfüllt. Einzige Korrektur: F-09 (Dokumentationszuordnung).

**Keine materiellen Abweichungen festgestellt** — über F-09 (behoben, Dokumentation)
und die zurückgestellten N-Befunde hinaus bestehen keine offenen funktionalen
oder sicherheitsrelevanten Abweichungen.
