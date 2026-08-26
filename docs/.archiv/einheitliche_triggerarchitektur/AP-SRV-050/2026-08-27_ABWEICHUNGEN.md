# AP-SRV-050 – Abweichungen und bewusste Entscheidungen

**Datum:** 2026-08-27

Es gibt keine materiellen Abweichungen vom Planungsstand. Zwei Umfangsdetails
wurden als bewusste Lesart festgehalten und sollen hier ausdrücklich
nachvollziehbar bleiben.

## 1. Admin-Key-Header

**Plan/Prompt:** „bestehender `X-Admin-Key`“.
**Ist:** Der bestehende Admin-Guard `admin_auth_error` in `create_app` liest
`x-voicestt-admin-key` beziehungsweise `Authorization: Bearer …` und verwaltet
den Loopback-Fallback ohne Key. `PATCH /api/v2/settings/server` reicht exakt
diesen Guard durch.

**Grund:** Der Prompt verlangt ausdrücklich die Wiederverwendung der
„bestehenden Admin-Key-Authentifizierung“. `X-Admin-Key` wird daher als
Beschreibung des vorhandenen Mechanismus gelesen, nicht als neuer Headername.
**Wirkung:** kein neuer Duplikatpfad; Tests decken beide Lesarten ab
(wrong-key 401, korrekt 200).
**Entscheidung:** bewusst so umgesetzt.

## 2. HTTP-Statuscodes des Server-Patches

**Ist:** `settings_revision_conflict` → `409 Conflict`, `settings_rejected`
(Feldfehler) → `422 Unprocessable Entity`, Erfolg (`applied`/`no_change`) →
`200`.

**Grund:** Die Wire-Resultcodes sind die fachliche Referenz; HTTP-Status ist
Transportdetail. 409/422 unterscheiden stale Revision und ungültige Felder
maschinenlesbar und passen zu den strukturierten Fehlbody-Formen.
**Entscheidung:** bewusst so umgesetzt; die eigentliche
`command.ack`-Projektion (SRV-040) stützt sich weiterhin ausschließlich auf
`result`/`accepted`.