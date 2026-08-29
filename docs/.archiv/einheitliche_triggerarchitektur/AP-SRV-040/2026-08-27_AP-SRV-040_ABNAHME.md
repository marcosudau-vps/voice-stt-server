# AP-SRV-040 – Root-Abnahme

**Datum:** 2026-08-27

**Status:** **PASS**

## Basis

```text
AP-SRV-030 Execution Source (Start):
325e55c186713069b25208871da4fef16470f85a
AP-SRV-030 Execution Tree:
ec5b6e0849bb7a0949ae5da05d168b8c19a4456e
```

## Candidates

```text
C1:
49a251fa69601494940185e08d360074de2b41e3
Tree e1461a756da318d0ff979a2b03d38c1f01063fc1

C2:
5e0361b3279eed311556e3cb42414f264e8c731e
Tree ebc4f1dde2d808b01ef064219ac2b1df9d2533e9
Parent C1

C3 (final Root-reviewed candidate):
6f73a4e347be51d02005e81a0c6be546f036deef
Tree 6d36c2639a199c5bdd10a2c8dc1899d8261caee6
```

## C2 Root Finding und Schließung

```text
Finding:
sichtbare Zustandsänderungen ohne Domain-Event erhöhten stateVersion
nicht zuverlässig.

Behoben durch:
ProtocolSessionState.advance_state() plus einmalige Versionierung des
closing_input-Eintritts über __input_closing__.

Nachweise:
runs/02_ROOT_CORRECTION/2026-08-27_REPORT.md
runs/02_ROOT_CORRECTION/evidence/2026-08-27_README.md
```

## C3 Root Finding und Schließung

```text
Finding:
eventSeq wurde unter State-Lock korrekt gemintet, aber Projection/Mint und
Sink-Übergabe waren nicht gemeinsam linearisiert; parallele Domainthreads
konnten 2,1 zustellen.

Behoben durch:
sessionlokaler RLock;
zentrale _dispatch_events()-Seam umfasst Projection/Mint bis send()/Sink.

Nachweise:
runs/03_ROOT_CORRECTION/2026-08-27_REPORT.md
runs/03_ROOT_CORRECTION/evidence/2026-08-27_README.md
```

## Finale Testzahlen

```text
779 passed
14 skipped
448 subtests passed
pytest exit = 0
```

## Zusätzliche Gates

```text
C3 event ordering:       20/20 PASS
git diff --check:        PASS
offene Code-Findings:    keine
```

## Kanonische Einordnung

```text
Der kanonische AP-SRV-040-Commit wird als genau ein Commit auf
CANON030_SHA erzeugt.

Produkt-/Test-/dauerhafte Doku entsprechen dem Root-geprüften C3.

Zusätzliche Unterschiede des kanonischen Commits gegenüber C3 sind
ausschließlich Paketakten-/Archivvollständigkeit.
```

Die endgültige Commit-SHA wird nicht in diese Akte eingeschrieben.