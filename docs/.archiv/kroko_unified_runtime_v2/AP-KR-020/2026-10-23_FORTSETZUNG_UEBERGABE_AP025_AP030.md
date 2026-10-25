# AP-KR-020 Fortsetzung – Übergabe an AP-KR-025 und AP-KR-030 (23.10.2026)

Ergänzt [2026-10-22_UEBERGABE_AP030.md](2026-10-22_UEBERGABE_AP030.md),
ohne deren BLOCKED-Feststellung umzuschreiben: Die dort geforderte
Fortsetzung ist für die lizenzunabhängigen Anteile erbracht.

## An AP-KR-025 (Dynamischer Modellbezug, vorgesehen nach AP-KR-020)

1. Das Lizenzgate (`_enforce_kroko_license_gate`) schlüsselt über
   `VoiceSTT/kroko/models.py` (`id`/Dateiname). Katalogeinträge aus PR #13
   werden ohne Gate-Änderung übernommen, sobald gemergt.
2. Unmanifestierte Kroko-Modelle werden verweigert (AD07): AP-KR-025 muss
   jede Provisionierung manifestieren (SHA-256/Größe, `requiresRuntimeVariant`).
3. Offene Voraussetzung: Abbildung Portal-UUID (Lizenzserver) →
   manifestierte Modell-ID. Ohne bestätigte Zuordnung darf AP-KR-025 keine
   Lizenzberechtigung aus Katalogdaten ableiten.
4. Keine Downloader-/Katalogdopplung in AP-020 vorhanden; der einzige
   Download-Pfad bleibt der bestehende Engine-Pfad. AP-KR-025 baut darauf
   auf (kein zweiter Katalog).

## An das offizielle AP-KR-030 (Paketierung, nach AP-KR-025)

1. Bootstrap-Vertrag: `VoiceSTT/kroko/bootstrap.py::cold_select`
   (ein Root, `sys.path[0]`, Marker, Konfliktverhalten, No-op ohne
   `VOICESTT_KROKO_PAYLOAD_ROOT`).
2. Supervisor-Vertrag: `VoiceSTT/kroko/supervisor.py::OwnerSupervisor`
   (eine Generation, `start_deadline_seconds`, Retry-Budget je
   Konfigurationsgeneration mit Backoff, bestätigter Exit,
   `accept_event`-Stale-Verwerfung, `VOICESTT_KROKO_OWNER_GENERATION`).
3. Lizenzstatus-Schema: `license_runtime.public_snapshot`
   (`status`, `generation`, `proEnabled`, `validatedModelIds`,
   `keyPresent`, `forceCommunity`, `credentialRevision`,
   `runtimeIdentity`, `reasonCode`, `proofAgeSeconds`,
   `maxProofAgeSeconds`).
4. Interims-`runtimeIdentity` (`payload:<root>` /
   `unmanaged-global-runtime`) durch offizielle Komponentenidentität
   ersetzen; LAB-Schema `LOCAL_NOT_QUALIFIED` nicht übernehmen.
5. Folgeauftrag A (native Status-Ergänzung) vor oder mit AP-030
   qualifizieren: versioniertes Schema, neue Patchrevision, neue
   Plattform-Fingerprints, echte Linux-/Windows-Installation.
6. Vor Release: Besitzerübergabe im Deployment, Reconnect, autorisierte
   Lizenz Positiv-/Negativ-/Ablauf-/Widerrufs-/Timeout-Fälle und
   Portal-UUID-Bindung nachholen (CONDITIONAL-Punkte aus dem Soll/Ist).

## Reihenfolge und Sperren

AP-KR-020 → AP-KR-025 → offizielles AP-KR-030 → V2-Releasequalifikation.
Die LAB-Arbeit bleibt unberührt und unbeauftragt; kein Merge, kein Release,
kein Deployment aus dieser Fortsetzung. PR #13 (Katalog) wird nicht
eigenmächtig gemergt.
