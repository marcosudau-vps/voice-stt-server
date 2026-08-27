"""AP-SRV-060: manifest, resolver, collisions, availability and refresh."""

import json
import unittest
from pathlib import Path

from VoiceSTT.core import wakeword_catalog as catalog_module
from VoiceSTT.core.wakeword_catalog import (
    WakeWordCatalogAuthority,
    WakeWordManifestError,
    load_snapshot,
    normalize_wake_word_token,
)

from .wake_catalog_support import build_bundle, write_artifact


ENTRIES = (
    ("hey_jarvis", "Hey Jarvis", ("jarvis",), "jarvis_v2.onnx"),
    ("alexa", "Alexa", (), "alexa.onnx"),
    ("hey_mycroft", "Hey Mycroft", (), "hey_mycroft.onnx"),
)


class NormalisationTests(unittest.TestCase):
    def test_all_human_forms_fold_onto_one_token(self):
        for value in (
            "hey_jarvis", "Hey Jarvis", "HEY-JARVIS", "hey.jarvis",
            "hey__jarvis", "  Hey   Jarvis  ", "Hey Jarvis",
        ):
            with self.subTest(value=value):
                self.assertEqual(normalize_wake_word_token(value), "hey_jarvis")

    def test_normalisation_never_removes_a_word(self):
        # The frozen contract forbids heuristically stripping "Hey".
        self.assertNotEqual(
            normalize_wake_word_token("jarvis"),
            normalize_wake_word_token("hey jarvis"),
        )

    def test_empty_and_separator_only_values_are_not_tokens(self):
        for value in (None, "", "   ", "___", "--", "."):
            with self.subTest(value=value):
                self.assertEqual(normalize_wake_word_token(value), "")


class CatalogTestCase(unittest.TestCase):
    def _authority(self, entries=ENTRIES, **kwargs):
        root = build_bundle(self.tmp / "bundle", entries)
        return WakeWordCatalogAuthority(asset_root=root, **kwargs), root

    def setUp(self):
        import tempfile

        self._tempdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tempdir.name)
        self.addCleanup(self._tempdir.cleanup)

    def test_public_projection_carries_no_paths_or_sources(self):
        authority, _root = self._authority()
        payload = authority.public_payload()
        self.assertEqual(payload["protocolVersion"], 2)
        self.assertEqual(payload["catalogRevision"], 1)
        for entry in payload["wakeWords"]:
            self.assertEqual(
                set(entry), {"id", "displayName", "aliases",
                             "artifactVersion", "available"}
            )
        text = json.dumps(payload)
        for forbidden in ("path", "paths", "source", ".onnx", str(self.tmp)):
            self.assertNotIn(forbidden, text)

    def test_explicit_alias_resolves_but_an_unlisted_short_form_does_not(self):
        authority, _root = self._authority()
        self.assertEqual(authority.resolve("jarvis"), "hey_jarvis")
        self.assertEqual(authority.resolve("HEY-JARVIS"), "hey_jarvis")
        self.assertEqual(authority.resolve("Hey Jarvis"), "hey_jarvis")
        # ``hey_mycroft`` has no alias, so the bare short form must not resolve.
        self.assertIsNone(authority.resolve("mycroft"))

    def test_id_alias_collision_is_a_manifest_error(self):
        entries = (
            ("hey_jarvis", "Hey Jarvis", ("alexa",), "jarvis_v2.onnx"),
            ("alexa", "Alexa", (), "alexa.onnx"),
        )
        root = build_bundle(self.tmp / "collide", entries)
        with self.assertRaisesRegex(WakeWordManifestError, "collision"):
            load_snapshot(root)

    def test_alias_alias_collision_is_a_manifest_error(self):
        entries = (
            ("hey_jarvis", "Hey Jarvis", ("shared",), "jarvis_v2.onnx"),
            ("alexa", "Alexa", ("Shared",), "alexa.onnx"),
        )
        root = build_bundle(self.tmp / "collide2", entries)
        with self.assertRaisesRegex(WakeWordManifestError, "collision"):
            load_snapshot(root)

    def test_display_name_collision_is_a_manifest_error(self):
        entries = (
            ("hey_jarvis", "Alexa", (), "jarvis_v2.onnx"),
            ("alexa", "Alexa", (), "alexa.onnx"),
        )
        root = build_bundle(self.tmp / "collide3", entries)
        with self.assertRaisesRegex(WakeWordManifestError, "collision"):
            load_snapshot(root)

    def test_shared_artifact_stem_is_a_manifest_error(self):
        entries = (
            ("hey_jarvis", "Hey Jarvis", (), "shared.onnx"),
            ("alexa", "Alexa", (), "shared.onnx"),
        )
        root = build_bundle(self.tmp / "collide4", entries)
        with self.assertRaisesRegex(WakeWordManifestError, "file stem"):
            load_snapshot(root)

    def test_non_canonical_id_is_a_manifest_error(self):
        entries = (("Hey_Jarvis", "Hey Jarvis", (), "jarvis_v2.onnx"),)
        root = build_bundle(self.tmp / "noncanon", entries)
        with self.assertRaisesRegex(WakeWordManifestError, "not canonical"):
            load_snapshot(root)

    def test_a_missing_artifact_is_unavailable_not_removed(self):
        authority, root = self._authority()
        (root / "alexa.onnx").unlink()
        authority.refresh()
        entries = {
            entry["id"]: entry
            for entry in authority.public_payload()["wakeWords"]
        }
        self.assertIn("alexa", entries)
        self.assertFalse(entries["alexa"]["available"])
        self.assertEqual(entries["alexa"]["unavailableReason"], "artifact_missing")
        self.assertNotIn("alexa", authority.available_ids())

    def test_a_missing_pipeline_makes_every_entry_unavailable(self):
        authority, root = self._authority()
        (root / "melspectrogram.onnx").unlink()
        authority.refresh()
        self.assertEqual(authority.available_ids(), ())
        for entry in authority.public_payload()["wakeWords"]:
            self.assertEqual(entry["unavailableReason"], "pipeline_unavailable")

    def test_an_undeclared_file_is_diagnostics_only(self):
        authority, root = self._authority()
        write_artifact(root, "stray_model.onnx")
        authority.refresh()
        ids = {entry["id"] for entry in authority.public_payload()["wakeWords"]}
        self.assertNotIn("stray_model", ids)
        self.assertIn(
            "stray_model.onnx",
            authority.snapshot().diagnostics["unmanagedArtifacts"],
        )


class SelectionAdmissionTests(CatalogTestCase):
    def test_one_bad_id_rejects_the_whole_selection(self):
        authority, _root = self._authority()
        selection, errors = authority.resolve_selection(
            ["hey_jarvis", "nope", "alexa"]
        )
        self.assertIsNone(selection)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].code, "wake_word_unavailable")
        self.assertEqual(errors[0].wake_word_id, "nope")

    def test_every_problematic_id_is_named(self):
        authority, _root = self._authority()
        _selection, errors = authority.resolve_selection(["nope", "also_nope"])
        self.assertEqual(
            sorted(error.wake_word_id for error in errors),
            ["also_nope", "nope"],
        )

    def test_a_globally_disabled_id_rejects_the_selection(self):
        authority, _root = self._authority()
        authority.set_global_disabled(["Hey Jarvis"])
        selection, errors = authority.resolve_selection(["hey_jarvis"])
        self.assertIsNone(selection)
        self.assertEqual(errors[0].reason, "globally_disabled")

    def test_an_accepted_selection_loads_exactly_its_own_artifacts(self):
        authority, root = self._authority()
        selection, errors = authority.resolve_selection(["jarvis", "alexa"])
        self.assertEqual(errors, ())
        self.assertEqual(selection.wake_word_ids, ("hey_jarvis", "alexa"))
        kwargs = selection.loader_kwargs()
        self.assertEqual(
            [Path(path).name for path in kwargs["wakeword_models"]],
            ["jarvis_v2.onnx", "alexa.onnx"],
        )
        self.assertEqual(
            Path(kwargs["melspec_model_path"]).name, "melspectrogram.onnx"
        )
        self.assertEqual(
            Path(kwargs["embedding_model_path"]).name, "embedding_model.onnx"
        )
        self.assertEqual(
            selection.model_key_to_id,
            {"jarvis_v2": "hey_jarvis", "alexa": "alexa"},
        )

    def test_duplicates_collapse_without_becoming_an_error(self):
        authority, _root = self._authority()
        selection, errors = authority.resolve_selection(
            ["hey_jarvis", "Hey Jarvis", "jarvis"]
        )
        self.assertEqual(errors, ())
        self.assertEqual(selection.wake_word_ids, ("hey_jarvis",))

    def test_an_empty_selection_is_refused(self):
        authority, _root = self._authority()
        selection, errors = authority.resolve_selection([])
        self.assertIsNone(selection)
        self.assertEqual(errors[0].code, "wake_word_selection_required")


class RefreshTests(CatalogTestCase):
    def test_an_invisible_change_does_not_move_the_revision(self):
        authority, _root = self._authority()
        before = authority.catalog_revision
        result = authority.refresh()
        self.assertTrue(result.ok)
        self.assertFalse(result.changed)
        self.assertEqual(authority.catalog_revision, before)

    def test_a_visible_change_raises_the_revision_once(self):
        authority, root = self._authority()
        before = authority.catalog_revision
        build_bundle(root, ENTRIES + (
            ("hey_rona", "Hey Rona", ("rona",), "hey_rona.onnx"),
        ))
        result = authority.refresh()
        self.assertTrue(result.ok)
        self.assertTrue(result.changed)
        self.assertEqual(result.catalog_revision, before + 1)
        self.assertIn("hey_rona", authority.available_ids())

    def test_a_broken_manifest_keeps_the_last_known_good_catalog(self):
        authority, root = self._authority()
        good_ids = authority.available_ids()
        good_revision = authority.catalog_revision
        (root / "models.json").write_text("{ not json", encoding="utf-8")

        result = authority.refresh()

        self.assertFalse(result.ok)
        self.assertFalse(result.changed)
        self.assertEqual(authority.available_ids(), good_ids)
        self.assertEqual(authority.catalog_revision, good_revision)
        self.assertIsNotNone(authority.load_error)

    def test_a_colliding_manifest_keeps_the_last_known_good_catalog(self):
        authority, root = self._authority()
        good_ids = authority.available_ids()
        build_bundle(root, (
            ("hey_jarvis", "Hey Jarvis", ("alexa",), "jarvis_v2.onnx"),
            ("alexa", "Alexa", (), "alexa.onnx"),
        ))
        result = authority.refresh()
        self.assertFalse(result.ok)
        self.assertIn("collision", result.error)
        self.assertEqual(authority.available_ids(), good_ids)

    def test_availability_change_notifies_exactly_once(self):
        seen = []
        authority, _root = self._authority(
            on_availability_changed=lambda rev, ids, changed: seen.append(
                (rev, tuple(ids), changed)
            )
        )
        self.assertEqual(seen, [])
        authority.set_global_disabled(["alexa"])
        self.assertEqual(len(seen), 1)
        self.assertNotIn("alexa", seen[0][1])
        # Re-applying the same disable list changes nothing visible.
        authority.set_global_disabled(["alexa"])
        self.assertEqual(len(seen), 1)

    def test_lifting_a_global_disable_restores_availability(self):
        authority, _root = self._authority()
        authority.set_global_disabled(["alexa"])
        self.assertNotIn("alexa", authority.available_ids())
        authority.set_global_disabled([])
        self.assertIn("alexa", authority.available_ids())


class BundledAssetTests(unittest.TestCase):
    """The assets that actually ship with the package."""

    def setUp(self):
        self.authority = WakeWordCatalogAuthority()
        if self.authority.snapshot() is None:
            self.skipTest(f"no bundled catalog: {self.authority.load_error}")

    def test_the_bundled_manifest_loads_through_package_resources(self):
        root = catalog_module.default_asset_root()
        self.assertTrue((root / "models.json").is_file())
        self.assertIsNone(self.authority.load_error)

    def test_every_bundled_entry_is_available_and_complete(self):
        entries = self.authority.public_payload()["wakeWords"]
        self.assertGreaterEqual(len(entries), 20)
        for entry in entries:
            with self.subTest(wake_word=entry["id"]):
                self.assertTrue(entry["available"])
                self.assertTrue(entry["displayName"])
                self.assertTrue(entry["artifactVersion"])

    def test_the_bundled_manifest_declares_hey_jarvis_with_its_alias(self):
        entries = {
            entry["id"]: entry
            for entry in self.authority.public_payload()["wakeWords"]
        }
        self.assertIn("hey_jarvis", entries)
        self.assertEqual(entries["hey_jarvis"]["displayName"], "Hey Jarvis")
        self.assertIn("jarvis", entries["hey_jarvis"]["aliases"])

    def test_every_declared_artifact_matches_its_recorded_hash(self):
        import hashlib

        snapshot = self.authority.snapshot()
        for entry in snapshot.entries:
            with self.subTest(wake_word=entry.id):
                data = entry.artifact.path.read_bytes()
                self.assertEqual(len(data), entry.artifact.byte_size)
                self.assertEqual(
                    hashlib.sha256(data).hexdigest(), entry.artifact.sha256
                )


if __name__ == "__main__":
    unittest.main()
