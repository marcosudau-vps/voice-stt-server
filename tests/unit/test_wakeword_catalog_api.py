"""AP-SRV-060: the v2 catalog HTTP contract (SET-13b) and the admin refresh."""

import unittest

from fastapi.testclient import TestClient

from api_fastapi_server import settings_control as sc

from .test_protocol_v2_settings import build_admin_app
from .test_server_controlled_e2e import GateAwareRecorder


ADMIN_HEADERS = {"x-admin-key": "test-admin-secret"}


class CatalogHttpContractTests(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_admin_app()

    def test_the_catalog_is_publicly_readable(self):
        with TestClient(self.app) as client:
            response = client.get("/api/v2/wake-words")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["protocolVersion"], 2)
        self.assertIsInstance(payload["catalogRevision"], int)
        self.assertGreaterEqual(payload["catalogRevision"], 1)
        self.assertTrue(payload["wakeWords"])

    def test_every_entry_matches_the_frozen_shape(self):
        with TestClient(self.app) as client:
            payload = client.get("/api/v2/wake-words").json()
        for entry in payload["wakeWords"]:
            with self.subTest(wake_word=entry.get("id")):
                self.assertIsInstance(entry["id"], str)
                self.assertIsInstance(entry["displayName"], str)
                self.assertIsInstance(entry["aliases"], list)
                self.assertIsInstance(entry["artifactVersion"], str)
                self.assertIsInstance(entry["available"], bool)
                allowed = {"id", "displayName", "aliases", "artifactVersion",
                           "available", "unavailableReason", "backends",
                           "catalogRevision"}
                self.assertLessEqual(set(entry), allowed)
                # AP-SRV-060 C3: per-backend health is public and carries only
                # availability plus a machine-readable reason - never a path.
                self.assertEqual(set(entry["backends"]), {"onnx", "tflite"})
                for health in entry["backends"].values():
                    self.assertIsInstance(health["available"], bool)
                    self.assertLessEqual(
                        set(health), {"available", "unavailableReason"}
                    )
                # Root F9: the entry carries the revision it came from.
                self.assertEqual(
                    entry["catalogRevision"], payload["catalogRevision"]
                )

    def test_the_payload_never_exposes_internal_paths(self):
        with TestClient(self.app) as client:
            text = client.get("/api/v2/wake-words").text
        for forbidden in ('"path"', '"paths"', '"source"', ".onnx",
                          "assets", "models.json"):
            self.assertNotIn(forbidden, text)

    def test_the_catalog_revision_is_separate_from_the_settings_revision(self):
        with TestClient(self.app) as client:
            catalog = client.get("/api/v2/wake-words").json()
            settings = client.get("/api/v2/settings/server").json()
        self.assertIn("catalogRevision", catalog)
        self.assertNotIn("catalogRevision", settings)
        self.assertNotIn("settingsRevision", catalog)


class CatalogRefreshTests(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_admin_app()

    def test_refresh_requires_the_existing_admin_key(self):
        with TestClient(self.app) as client:
            unauthorised = client.post("/api/v2/wake-words/refresh")
            self.assertEqual(unauthorised.status_code, 401)
            wrong = client.post(
                "/api/v2/wake-words/refresh",
                headers={"x-admin-key": "wrong"},
            )
            self.assertEqual(wrong.status_code, 401)

    def test_an_unchanged_catalog_refreshes_without_moving_the_revision(self):
        with TestClient(self.app) as client:
            before = client.get("/api/v2/wake-words").json()["catalogRevision"]
            response = client.post(
                "/api/v2/wake-words/refresh", headers=ADMIN_HEADERS
            )
            after = client.get("/api/v2/wake-words").json()["catalogRevision"]

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["changed"])
        self.assertEqual(payload["catalogRevision"], before)
        self.assertEqual(after, before)

    def test_a_failing_refresh_keeps_the_last_known_good_catalog(self):
        with TestClient(self.app) as client:
            good = client.get("/api/v2/wake-words").json()
            service = self.app.state.voicestt_service

            class BrokenCatalog:
                """A refresh that fails after the catalog was already good."""

                def __init__(self, real):
                    self._real = real

                def __getattr__(self, name):
                    return getattr(self._real, name)

                def refresh(self, **kwargs):
                    from VoiceSTT.core.wakeword_catalog import RefreshResult

                    return RefreshResult(
                        ok=False,
                        changed=False,
                        catalog_revision=self._real.catalog_revision,
                        available_wake_word_ids=self._real.available_ids(),
                        error="unreadable wake-word manifest",
                        snapshot=self._real.snapshot(),
                    )

                def set_global_disabled(self, values):
                    return self._real.set_global_disabled(values)

            service.wakeword_catalog = BrokenCatalog(service.wakeword_catalog)
            response = client.post(
                "/api/v2/wake-words/refresh", headers=ADMIN_HEADERS
            )
            after = client.get("/api/v2/wake-words").json()

        self.assertEqual(response.status_code, 422)
        self.assertFalse(response.json()["ok"])
        self.assertIn("manifest", response.json()["error"])
        self.assertEqual(after["catalogRevision"], good["catalogRevision"])
        self.assertEqual(after["wakeWords"], good["wakeWords"])


class GlobalDisableProjectionTests(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_admin_app()

    def test_a_global_disable_makes_the_entry_unavailable_and_bumps_revision(self):
        with TestClient(self.app) as client:
            before = client.get("/api/v2/wake-words").json()
            revision = client.get("/api/v2/settings/server").json()[
                "settingsRevision"
            ]
            patch = client.patch(
                "/api/v2/settings/server",
                headers=ADMIN_HEADERS,
                json={
                    "baseSettingsRevision": revision,
                    "changes": {sc.WAKE_WORD_GLOBAL_DISABLED: ["hey_jarvis"]},
                },
            )
            self.assertEqual(patch.status_code, 200, patch.text)
            after = client.get("/api/v2/wake-words").json()

        entries = {entry["id"]: entry for entry in after["wakeWords"]}
        self.assertIn("hey_jarvis", entries)
        self.assertFalse(entries["hey_jarvis"]["available"])
        self.assertEqual(
            entries["hey_jarvis"]["unavailableReason"], "globally_disabled"
        )
        self.assertEqual(
            after["catalogRevision"], before["catalogRevision"] + 1
        )

    def test_a_disabled_wake_word_is_refused_at_session_admission(self):
        with TestClient(self.app) as client:
            revision = client.get("/api/v2/settings/server").json()[
                "settingsRevision"
            ]
            client.patch(
                "/api/v2/settings/server",
                headers=ADMIN_HEADERS,
                json={
                    "baseSettingsRevision": revision,
                    "changes": {sc.WAKE_WORD_GLOBAL_DISABLED: ["hey_jarvis"]},
                },
            )
            service = self.app.state.voicestt_service
            selection, errors = service.wakeword_catalog.admit_selection(
                ["hey_jarvis"]
            )

        self.assertIsNone(selection)
        self.assertEqual(errors[0].code, "wake_word_unavailable")
        self.assertEqual(errors[0].reason, "globally_disabled")


if __name__ == "__main__":
    unittest.main()
