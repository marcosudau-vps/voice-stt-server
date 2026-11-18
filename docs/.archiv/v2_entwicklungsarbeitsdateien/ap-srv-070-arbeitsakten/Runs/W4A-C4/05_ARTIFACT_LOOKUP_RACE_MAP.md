# AP-SRV-070 / W4A-C4 — Phase 1: Artifact-Store-Lookup-Race-Kartierung

Dieses Dokument kartiert den im Gesamtauftrag beschriebenen TOCTOU-Race-Condition-Zustand zwischen Reader (`lookup()`) und Writer (`store()`) in `VoiceSTT/kroko/artifacts.py`.

Gemäß Phase-1-Vorgaben enthält dieses Dokument **keine** Implementierung und **keine** Architekturentscheidung.

## 1. Relevante Funktionen

- `KrokoArtifactStore.lookup()` (`VoiceSTT/kroko/artifacts.py`, Zeilen 717–758)
- `KrokoArtifactStore._verify_slot_dir()` (`VoiceSTT/kroko/artifacts.py`, Zeilen 586–620)
- `KrokoArtifactStore.replaced_backups()` (`VoiceSTT/kroko/artifacts.py`, Zeilen 622–635)
- `KrokoArtifactStore.recover_slot()` (`VoiceSTT/kroko/artifacts.py`, Zeilen 704–716)
- `KrokoArtifactStore._recover_slot_locked()` (`VoiceSTT/kroko/artifacts.py`, Zeilen 636–703)
- `KrokoArtifactStore.store()` (`VoiceSTT/kroko/artifacts.py`, Zeilen 761–880)

## 2. Aktuelle Aufrufreihenfolge und Interaktion

### 2.1 Ablauf in `lookup()`

1. **Zeile 738–743:** Ungesperrter Aufruf von `_verify_slot_dir(self.slot_dir(variant, fingerprint))`.
   - Liest Metadaten und validiert Wheel-Hashes, Tags, Variant.
   - Wenn `slot_dir` nicht existiert, liefert es `(None, ["no stored artifact for this variant/fingerprint"])`.
2. **Zeile 744–745:** Ungesperrte Prüfung:
   ```python
   if not recover or not self.replaced_backups(variant, fingerprint):
       return record, problems
   ```
   - Wenn keine Verzeichnisse mit Namensmuster `<fingerprint>.replaced-*` existieren, wird das Ergebnis aus Schritt 1 direkt zurückgegeben.
3. **Zeile 751–757:** Nur falls Backups existieren:
   - Aufruf von `recover_slot()`, welcher den exklusiven OS-Lock `_slot_lock` erwirbt und `_recover_slot_locked()` ausführt.
   - Anschließend erneute Prüfung von `_verify_slot_dir()`.

### 2.2 Ablauf in `store()` (insbesondere bei Rebuild / Swap)

1. Staging und Vorab-Verifikation des neuen Artefakts in `.staging/<uuid>`.
2. Erwerb des exklusiven Locks `with self._slot_lock(variant, fingerprint):`.
3. Eventuelle Altreste bereinigen: `self._recover_slot_locked(...)`.
4. **Zeile 860–864:** Falls `final.exists()`:
   ```python
   backup = final.with_name(final.name + REPLACED_SUFFIX + uuid.uuid4().hex)
   os.replace(final, backup)
   ```
   *(Zwischenzustand: `final` existiert nicht; Artefakt liegt unter `backup`)*
5. **Zeile 866:**
   ```python
   os.replace(staging, final)
   ```
   *(Neues Artefakt ist jetzt atomar an `final` platziert)*
6. **Zeilen 875–876:**
   ```python
   for stale in self.replaced_backups(variant, fingerprint):
       shutil.rmtree(stale, ignore_errors=True)
   ```
   *(Alle Backups werden gelöscht)*
7. Verlassen des Lock-Blocks.

## 3. Konkretes Reader/Writer-Interleaving

Zwischen `lookup()` (Reader) und `store()` (Writer) kann sich exakt folgende Ausführungsreihenfolge einstellen:

```text
[Zeit t0] Writer (in store):
          Hat Lock erworben.
          Führt Zeile 864 aus: os.replace(final, backup)
          => 'final' existiert auf dem Dateisystem temporär NICHT.
          => 'backup' existiert.

[Zeit t1] Reader (in lookup):
          Führt Zeile 738 aus: _verify_slot_dir(final)
          => read_metadata_in(final) findet keine Datei.
          => record = None, problems = ["no stored artifact..."]

[Zeit t2] Writer (in store):
          Führt Zeile 866 aus: os.replace(staging, final)
          => 'final' existiert wieder und ist vollständig gültig.
          Führt Zeilen 875-876 aus: shutil.rmtree(backup)
          => 'backup' ist vollständig gelöscht.
          Writer gibt _slot_lock frei.

[Zeit t3] Reader (in lookup):
          Fährt fort bei Zeile 744:
          if not recover or not self.replaced_backups(variant, fingerprint):
              return record, problems
          Da Writer das Backup bei t2 gelöscht hat, ist self.replaced_backups() == [].
          => 'not self.replaced_backups()' ist TRUE.
          => Reader führt Zeile 745 aus: return record, problems

[Zeit t4] Reader-Ergebnis:
          Gibt (None, ["no stored artifact..."]) (MISS) zurück!
```

## 4. Betroffene Codebereiche

- `VoiceSTT/kroko/artifacts.py`:
  - Reader-Pfad: Zeilen 738–746
  - Writer-Pfad: Zeilen 860–877

## 5. Ursache des Miss-Verhaltens

Der Reader führt zwei voneinander abhängige Beobachtungen ungesperrt und nicht-atomar nacheinander durch:
1. Ist `final` vorhanden und valide? (bei `t1`: Nein)
2. Gibt es ein `backup`? (bei `t3`: Nein)

Weil der Writer zwischen Schritt 1 und Schritt 2 die Slot-Transition abschließt (`staging -> final`) und die Backups entfernt, fallen die beiden Beobachtungen des Readers in zwei unterschiedliche Epochen des Writers. Obwohl `final` zum Rückgabezeitpunkt (`t3`/`t4`) absolut fehlerfrei und gültig auf der Festplatte liegt, meldet `lookup()` einen Cache-Miss.

Dies führt nicht zu einer Datenkorruption, kann jedoch einen unnötigen, teuren nativen Kroko-Build (~30 Minuten) auslösen.
