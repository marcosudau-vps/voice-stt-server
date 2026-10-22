# Kroko-Modellkatalog – offene Voraussetzungen

22.10.2026. Der Offlinekatalog ist unabhängig von diesen Folgearbeiten nutzbar.

## Onlinequelle

- Unterstützten/versionierten Metadatenvertrag und eigenständige
  Authentifizierung tatsächlich nachweisen. Beobachtete Portalrouten sind
  keine Freigabe für ihre produktive Nutzung. `licenses` lieferte den Export;
  `models` ist unbestätigt. Keine Sessioncookies oder nachgebildeten Logins.
- Portal- und On-Premise-Authentifizierung getrennt halten. Ein erfolgreicher
  Key-/Modell-Lizenztest liefert keinen modellunabhängigen Katalogzugang.
- Einen Adapter hinter `CatalogSource` ergänzen, der nur geprüfte sichere
  Felder extrahiert, keine Rohantworten/Secrets persistiert und denselben
  strikten Validator nutzt. Refresh atomar veröffentlichen; bei Fehlern den
  letzten guten Offlinekatalog behalten. Timeout, Größenlimit, Quellen-/
  Redirectregeln und Credentialgrenzen benötigen eigene Contracttests.

## Download und Aktivierung

- Für 112 der 124 Modelle fehlt eine bestehende autoritative Hash-/Bytebindung.
  Anbieterhashes dürfen erst nach belegter Authority und Identitätszuordnung
  in die bestehende Produktverwaltung integriert werden.
- Die zwölf Manifestmodelle behalten ihre Integritätsbindung, aber kein
  Auto-Provisioningrecht: Community POLICY_REQUIRED, Pro PROHIBITED.
  Rechteänderungen benötigen eine explizite fachliche Grundlage.
- Neue Communityquellen brauchen immutable Revisionen und Provenienzbindung;
  veränderliche `main`-Links und bekannte Pro-URLs reichen nicht aus.
- Zugänglichkeit wurde nicht geprüft. Ein späterer Download muss jeden
  Redirect vor Kontakt begrenzen, ungeprüfte Bytes isolieren, Sollhash und
  Größe prüfen und die vorhandene atomare Provisionierung nutzen. Kein
  zweiter Downloader oder dauerhafter Modellcache.
- Tatsächliche Aktivierung benötigt Betreiberabsicht, kompatible Runtime,
  echten Load-Probe und für Pro den serverseitigen Lizenz-/Entitlementnachweis
  aus AP-KR-020. Katalogfilter und Plan erteilen keine Berechtigung.

## Review und Integration

Unabhängiger PR-Review und spätere Übernahme bleiben offen. Kein Merge,
Release oder Deployment Bestandteil dieses Auftrags. AP-KR-020 / PR #12,
native Komponenten und V2-Protokoll werden nicht geändert.

Der vollständige lokale Testlauf hatte einen bestehenden Keepalive-Timing-Flake;
vier gezielte Wiederholungen und anschließend die gesamte betroffene Testdatei
bestanden. Der erste Gesamtlauf bleibt als nicht vollständig grün dokumentiert.
GitHub-CI und unabhängiger Review sind gesonderte Nachweise; Details stehen in
der [Testevidenz](2026-10-22_TEST_EVIDENZ.md).
