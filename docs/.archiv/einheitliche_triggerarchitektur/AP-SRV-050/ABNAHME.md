# AP-SRV-050 – Root-Abnahme

**Datum:** 2026-08-27

**Status:** **PASS**

## Canonical Base

```text
SHA:
c0806e5bc5d503580070f2dacc88831d51447938

Tree:
e9a1a93aecf433941db91827393bc51afef4ebff

Branch:
feat/einheitliche-triggerarchitektur
```

## Execution Provenance

```text
C1:
489ac23a192b2a64abbcdb6779ed132f159e4518
Tree 17eeb88254809c535404c84872111241470f1010

C2:
536ff67cda872b1449f88c5d99e8d8c3017139f4
Tree 9ff02381fef0b6c8dd6e01482d4633e21ef56be4
Parent 489ac23a192b2a64abbcdb6779ed132f159e4518

C3 (Root-PASS Source):
18b65216433329456946afd3c41d8df6bbd07d44
Tree b0dec32ddde90052956165c249b313478c267773
Parent 536ff67cda872b1449f88c5d99e8d8c3017139f4

Review-Branch:
review/AP-SRV-050/run-01
```

## Root Findings

```text
F1 PASS
F2 PASS
F3 PASS
F4 PASS
F5 PASS
F6 PASS
```

## Kernabnahme

- eine `SessionSettingsState` je v2-Session;
- getrennte `ServerSettingsState`;
- `ProtocolSessionState` nur Wire-Spiegel;
- monotone getrennte Session-/Serverrevisionen;
- `next_activation` reale immutable Timing-Latches;
- `requested`/`effective` vollständig resyncbar;
- Settings-Patch, Wire-Mirror und `settings.changed` linearisiert;
- Snapshot auf derselben AP-SRV-040 Dispatchgrenze;
- Persistenz strikt validiert und `prepare → persist → commit`;
- REST/Auth/Secret-Schutz PASS;
- v1-Isolation erhalten;
- keine AP-SRV-060-Fachlogik vorgezogen.

## Test Evidence

```text
Settings:
120 passed

Protocol v2:
205 passed / 1 skipped / 281 subtests passed

Activation/Timer:
218 passed / 82 subtests passed

Full Unit:
899 passed / 14 skipped / 448 subtests passed

C3 Races:
Snapshot/Patch                    20/20
settings.changed/Domain ordering  20/20
```

## Root Disposition

```text
GET /api/v2/wake-words gehört AP-SRV-060.

SET-13 wird im Clienttracking aufgeteilt in
Settings-REST (SET-13a, AP-SRV-050) und
Wake-Katalog (SET-13b, AP-SRV-060).
```

## Non-blocking Notes

```text
1. Die byteidentisch archivierte C3-Promptdatei
   runs/03_ROOT_CORRECTION/2026-08-27_PROMPT.md
   enthält Markdown-Hardbreak-Trailing-Spaces.
   Bewusst nicht verändert, sonst geht der Byte-/SHA-Nachweis verloren.

2. C3 schließt das Wire-Race strukturell.
   Keine C4-Runde erforderlich.
```

## Kanonische Einordnung

```text
Der kanonische AP-SRV-050-Commit wird als genau ein Commit auf
c0806e5bc5d503580070f2dacc88831d51447938 erzeugt.

Produkt-, Test- und dauerhafte Doku entsprechen dem Root-geprüften C3
(Tree b0dec32ddde90052956165c249b313478c267773).

Zusätzliche Unterschiede des kanonischen Commits gegenüber C3 sind
ausschließlich Root-Close-Dokumente dieser Akte.
```

Die endgültige Commit-SHA wird nicht in diese Akte eingeschrieben.

## Next Dependency

```text
AP-SRV-060 freigegeben auf dem kanonischen AP-SRV-050-SHA.
```
