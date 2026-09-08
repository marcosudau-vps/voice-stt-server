"""Movable-alias mapping rules (AP-SRV-070 W5-R04, section 21).

Gates W5R4-G33..G37 live here: the exact tag is immutable, ``2.0``/``2``/
``latest`` are the aliases a stable ``>=1`` release owns, a ``0.x`` release
owns no broad ``0``, and a pre-release owns none at all.
"""

from __future__ import annotations

import unittest

from release_tooling import aliases
from release_tooling.errors import ReleaseError


class AliasMappingTests(unittest.TestCase):
    def test_two_zero_zero_owns_minor_major_and_latest(self):
        # W5R4-G34/G35/G36
        self.assertEqual(aliases.alias_tags_for("2.0.0"), ["2.0", "2", "latest"])

    def test_aliases_are_ordered_most_specific_first(self):
        # Not cosmetic: the publish step walks them in order, so the narrowest
        # claim is made first and `latest` is the last thing to move.
        self.assertEqual(aliases.alias_tags_for("1.4.7"), ["1.4", "1", "latest"])

    def test_zero_x_releases_omit_the_broad_zero_alias(self):
        # W5R4-G37. Under SemVer a 0.x release promises no compatibility
        # across minor versions, so a bare "0" would advertise a guarantee the
        # version scheme explicitly withholds.
        self.assertEqual(aliases.alias_tags_for("0.5.3"), ["0.5", "latest"])
        self.assertNotIn("0", aliases.alias_tags_for("0.5.3"))

    def test_zero_zero_x_still_omits_the_broad_zero_alias(self):
        self.assertEqual(aliases.alias_tags_for("0.0.1"), ["0.0", "latest"])

    def test_a_prerelease_owns_no_aliases_at_all(self):
        # `latest` must never point at a release candidate.
        for version in ("2.0.0-rc.1", "1.0.0-alpha", "0.9.0-beta.2"):
            with self.subTest(version=version):
                self.assertEqual(aliases.alias_tags_for(version), [])
                self.assertTrue(aliases.is_prerelease(version))

    def test_build_metadata_does_not_suppress_aliases(self):
        self.assertEqual(aliases.alias_tags_for("2.0.0+build.5"), ["2.0", "2", "latest"])

    def test_exact_tag_is_the_version_itself(self):
        # W5R4-G33: the exact tag is the immutable identity, never rewritten.
        self.assertEqual(aliases.exact_tag_for("2.0.0"), "2.0.0")

    def test_git_tag_is_v_prefixed(self):
        self.assertEqual(aliases.git_tag_for("2.0.0"), "v2.0.0")

    def test_an_unparseable_version_fails_closed(self):
        # Guessing alias names for a version nobody can parse could silently
        # repoint `latest`, so this refuses rather than improvising.
        for version in ("", "2.0", "two.0.0", "2.0.0.1", "v2.0.0", "2.01.0"):
            with self.subTest(version=version):
                with self.assertRaises(ReleaseError):
                    aliases.alias_tags_for(version)

    def test_parse_version_exposes_the_components(self):
        parts = aliases.parse_version("2.1.3-rc.1+meta")
        self.assertEqual(parts["major"], "2")
        self.assertEqual(parts["minor"], "1")
        self.assertEqual(parts["patch"], "3")
        self.assertEqual(parts["prerelease"], "rc.1")
        self.assertEqual(parts["build"], "meta")


if __name__ == "__main__":
    unittest.main()
