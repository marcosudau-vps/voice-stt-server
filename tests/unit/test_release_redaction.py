"""AP-SRV-070 W5: secret redaction/detection for release state and manifests."""

from __future__ import annotations

import unittest

from release_tooling.errors import SecretDetectedError
from release_tooling.redaction import assert_no_secrets, looks_like_secret_key_name, redact_text


class SecretKeyNameTests(unittest.TestCase):
    def test_flags_common_secret_field_names(self):
        for name in ("apiKey", "KROKO_API_KEY", "pypiToken", "password", "clientSecret", "credential"):
            with self.subTest(name=name):
                self.assertTrue(looks_like_secret_key_name(name))

    def test_does_not_flag_ordinary_field_names(self):
        for name in ("sourceCommit", "wheel", "imageId", "releaseReadiness", "kroko_variant"):
            with self.subTest(name=name):
                self.assertFalse(looks_like_secret_key_name(name))

    def test_allows_documented_boolean_status_flags(self):
        self.assertFalse(looks_like_secret_key_name("hasApiKey"))
        self.assertFalse(looks_like_secret_key_name("pypiTokenPresent"))


class AssertNoSecretsTests(unittest.TestCase):
    def test_passes_for_a_clean_release_state_document(self):
        payload = {
            "version": "2.0.0",
            "sourceCommit": "a" * 40,
            "wheel": {"filename": "voicestt-2.0.0-py3-none-any.whl", "sha256": "b" * 64},
            "credentials": {"pypiTokenPresent": True, "ghcrTokenPresent": False},
            "history": [{"state": "PREPARED", "atUtc": "2026-09-06T00:00:00Z"}],
        }
        assert_no_secrets(payload)  # must not raise

    def test_raises_on_a_secret_shaped_field_with_a_value(self):
        with self.assertRaises(SecretDetectedError):
            assert_no_secrets({"pypiToken": "pypi-AAAAAAAAAAAAAAAAAAAAAAAA"})

    def test_raises_on_a_nested_secret_field(self):
        with self.assertRaises(SecretDetectedError):
            assert_no_secrets({"images": {"free": {"registryPassword": "hunter2hunter2"}}})

    def test_raises_on_a_secret_shaped_value_in_an_unflagged_field(self):
        with self.assertRaises(SecretDetectedError):
            assert_no_secrets({"notes": "used ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA to test"})

    def test_does_not_raise_for_an_empty_secret_shaped_field(self):
        assert_no_secrets({"apiKey": ""})

    def test_walks_lists_too(self):
        with self.assertRaises(SecretDetectedError):
            assert_no_secrets([{"token": "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}])


class RedactTextTests(unittest.TestCase):
    def test_redacts_known_credential_shapes(self):
        text = "used token ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA during upload"
        self.assertNotIn("ghp_AAAA", redact_text(text))
        self.assertIn("<redacted>", redact_text(text))

    def test_leaves_ordinary_text_untouched(self):
        text = "uploaded voicestt-2.0.0-py3-none-any.whl to PyPI"
        self.assertEqual(redact_text(text), text)


if __name__ == "__main__":
    unittest.main()
