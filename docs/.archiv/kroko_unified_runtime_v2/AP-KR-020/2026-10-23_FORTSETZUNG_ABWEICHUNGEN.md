# AP-KR-020 Fortsetzung – Abweichungen (Nachtrag 23.10.2026)

Ergänzt [2026-10-22_ABWEICHUNGEN.md](2026-10-22_ABWEICHUNGEN.md); D01–D03
dort bleiben historisch gültig.

## AD04 – Kein produktiver Python-Lizenzclient (Variante B verworfen)

**Grund:** Die erfolgreiche WebSocket-Probe nutzt exakt das native
Lizenzprotokoll (`wss://…/ws/v1/<key>/<modelId>`). Sie als Python-Produktpfad
zu übernehmen, wäre eine eigene Ersatzimplementierung des
Lizenzprotokolls ohne stabilen Anbietervertrag – im Auftrag ausdrücklich
verboten. Die Probe bleibt reine Testevidenz für die Modellbindung.

**Auswirkung:** Die modellbezogene Prüfung existiert produktiv nur als
Verifizierer-Schnittstelle (mit fail-closed Default) und als nativer
Aktivierungsnachweis in der Owner-Generation. Kein neuer Netzwerkpfad.

## AD05 – Keine native Schnittstellenergänzung in dieser Fortsetzung

**Grund:** Variante A erfordert Patch, neue Fingerprints, Plattformbuilds
und Live-Qualifikation. Ohne autorisierte Testumgebung und ohne
Native-Toolchain-Lauf wäre jede Ergänzung unqualifiziert.

**Auswirkung:** `PATCH_SET_REVISION`, Buildinputs und Artefakt-Fingerprints
unverändert; kein neues natives Payload. A ist als versionierter
Folgeauftrag mit den Anforderungen aus dem Lizenzentscheidungsnachtrag
spezifiziert.

## AD06 – Supervisor noch nicht ASGI-Besitzer im Deployment

**Grund:** `OwnerSupervisor` ist als Modul vollständig implementiert und
mit synthetischen Prozessen qualifiziert (Deadline, Retry-Budget,
bestätigter Exit, Stale-Verwerfung). Die Übergabe des laufenden
ASGI-Dienstprozesses an diese Aufsicht erfordert Deployment- und
Reconnect-Qualifikation, die in dieser Umgebung nicht erbracht werden kann.

**Auswirkung:** CONDITIONAL-Anteil (Soll/Ist-Nachtrag, Punkt 2). Keine
Behauptung eines qualifizierten unterbrechungsfreien Wechsels.

## AD07 – Unmanifestierte Kroko-Modelle: gekennzeichnet statt verweigert

**Grund:** Die etablierte Semantik der Modellautorität
(`VoiceSTT/kroko/models.py`, `locate_model`) lässt explizite
Operator-Overrides außerhalb des Manifests ausdrücklich zu – gemeldet als
`unmanaged`, nicht stillschweigend gesegnet. Ein hartes Verweigern am
Startup brach bestehende, gemockt qualifizierte Konfigurationen
(z. B. `realtime_model="tiny"` mit Default-Engine in
`test_openai_compatible_endpoint.py`). Die tatsächliche Durchsetzung gegen
Pro-Inhalte ohne Berechtigung bleibt nativ (Header-ID-Aktivierung) plus
Gate für manifestiertes Pro bestehen.

**Auswirkung:** Gate und Startup-Fallback verweigern nur manifestiertes Pro
ohne aktuellen Nachweis. Unmanifestierte Modelle bleiben möglich, werden
als `unmanaged` auditiert (`kroko.unmanaged_model_selected`) und können
niemals `VALID` werden. Dokumentiert und getestet.
