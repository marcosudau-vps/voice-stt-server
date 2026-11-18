# AP-SRV-070 / W4C-R01-C1 - Updated Gate Status

Nur die durch diesen Korrekturlauf betroffenen Gates. Alle anderen W4C-Gates
(siehe `W4C-R01/03_EVIDENCE_INDEX.md`) sind durch diesen Lauf unveraendert
und werden hier nicht wiederholt.

| Gate | Original W4C-R01 | C1 Ergebnis | Finaler Stand | Evidence |
|---|---|---|---|---|
| W4C-G22 (Managed Model Store Persistence) | PASS, aber nur ueber einen generischen Marker direkt unter `/var/lib/voicestt` belegt - Root Review bewertete das als zu schwach fuer die kanonischen Store-Pfade selbst | PASS - direkter Persistenz- und Schreibbarkeitsnachweis fuer `models/stt/fasterwhisper` UND `models/stt/kroko_asr` ueber echten Container-Recreate, inkl. dokumentierter Randbeobachtung zur Bind-Mount-Semantik | **PASS** | `Evidence/01_Managed_Model_Store_Persistence/01_summary.txt` |
| W4C-G24 (SIGTERM gesendet) | PASS (Exit 143 beobachtet) | PASS - SIGTERM ueber `docker compose stop -t 15` nachweislich zugestellt, Uvicorn-Lifecycle-Logs bestaetigen Empfang | **PASS** | `Evidence/02_Graceful_Shutdown/01_summary.txt` |
| W4C-G25 (sauberer Shutdown nachgewiesen) | PASS, aber Root Review bewertete "Exit 143 + schneller Exit" allein als nicht ausreichend fuer einen vollstaendig abgearbeiteten Application-Shutdownpfad | PASS - zwei unabhaengige, bereits vorhandene technische Signale (Uvicorn-ASGI-Lifespan-Logs + zeitlich exakt passender persistenter Event-Store-Eintrag `server.stopping`) belegen den vollstaendigen Lifecycle-Durchlauf | **PASS** | `Evidence/02_Graceful_Shutdown/01_summary.txt` |
| W4C-G26 (kein erzwungener Kill als Normalpfad) | PASS (Stopdauer ~1.1s, kein OOM) | PASS - erneut bestaetigt (Stopdauer ~1.32s, weit unter 15s-Timeout, `OOMKilled: false`, Exit 143 statt 137) | **PASS** | `Evidence/02_Graceful_Shutdown/01_summary.txt` |

## Ergebnis

Beide Root-Review-Findings sind mit dieser zusaetzlichen, eng begrenzten
Evidence vollstaendig geschlossen. Keines der betroffenen Gates musste auf
FAIL oder BLOCKED gesetzt werden. Keine Sourceaenderung war erforderlich.
