"""Public documentation surface guards (AP-SRV-070 W5-R04).

Gates W5R4-G51..G60: the README is the project's front door and must tell the
truth about what is installable today; the maintained engine documentation is
reduced to the two qualified production engines; and no maintained document may
link into the removed ``docs/engines/`` tree.

These are deliberately mechanical checks. Prose quality is a review question;
"this link 404s" and "this page advertises a product surface that does not
exist" are not, and they are exactly the failures that make a front page
untrustworthy.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs"
README = REPO_ROOT / "README.md"
ARCHIVE = DOCS / ".archiv"

#: Engine guides that were removed from the public surface in W5-R04.
REMOVED_ENGINE_GUIDES = (
    "cohere",
    "funasr",
    "hf-transformers",
    "moonshine",
    "omnilingual-asr",
    "openai-whisper",
    "parakeet-nemo",
    "sherpa-onnx",
    "whisper-cpp",
)

_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def maintained_markdown():
    """Every maintained Markdown document - the archive is history, not docs."""
    for path in sorted(REPO_ROOT.rglob("*.md")):
        if ARCHIVE in path.parents or path == ARCHIVE:
            continue
        if any(part in {".git", "node_modules"} or part.startswith(".venv") for part in path.parts):
            continue
        yield path


class EngineDocumentationLayoutTests(unittest.TestCase):
    def test_the_engines_directory_is_gone(self):
        # W5R4-G56.
        self.assertFalse((DOCS / "engines").exists())

    def test_the_two_retained_guides_live_directly_under_docs(self):
        # W5R4-G54/G55.
        for name in ("faster-whisper.md", "kroko-onnx.md"):
            with self.subTest(guide=name):
                path = DOCS / name
                self.assertTrue(path.is_file(), f"{name} is missing")
                self.assertGreater(len(path.read_text(encoding="utf-8")), 500)

    def test_the_removed_guides_are_not_anywhere_under_docs(self):
        for name in REMOVED_ENGINE_GUIDES:
            with self.subTest(guide=name):
                self.assertFalse((DOCS / f"{name}.md").exists())

    def test_no_maintained_document_links_into_docs_engines(self):
        # W5R4-G57.
        offenders = []
        for path in maintained_markdown():
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"\(\.{0,2}/?(docs/)?engines/", line):
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{number}")
        self.assertEqual(offenders, [])

    def test_the_archive_is_left_alone(self):
        # W5R4-G59: historical records are evidence and are not rewritten just
        # because they mention an engine whose current docs were removed.
        self.assertTrue(ARCHIVE.is_dir())
        self.assertTrue(any(ARCHIVE.rglob("*.md")))


class MaintainedEngineOverviewTests(unittest.TestCase):
    def setUp(self):
        self.text = (DOCS / "transcription-engines.md").read_text(encoding="utf-8")

    def test_it_links_to_both_retained_guides(self):
        # W5R4-G58.
        self.assertIn("(faster-whisper.md)", self.text)
        self.assertIn("(kroko-onnx.md)", self.text)

    def test_it_does_not_advertise_a_removed_engine_as_a_production_backend(self):
        lowered = self.text.lower()
        for phrase in ("optional production backend", "default production backend | [engines/"):
            self.assertNotIn(phrase, lowered)

    def test_it_marks_the_remaining_adapters_as_internal(self):
        # The honest distinction the prompt asks for: the source still has
        # them, the product does not advertise them.
        lowered = self.text.lower()
        self.assertIn("internal", lowered)
        self.assertIn("experimental", lowered)
        self.assertIn("not part of the supported production surface", lowered)


class ReadmeTests(unittest.TestCase):
    def setUp(self):
        self.text = README.read_text(encoding="utf-8")
        self.lowered = self.text.lower()

    def test_the_readme_was_actually_rewritten(self):
        # W5R4-G51. Cheap structural evidence that this is a new document and
        # not the old one with patched sentences.
        self.assertGreater(len(self.text), 4000)
        self.assertNotIn("Featured Integration", self.text)
        self.assertNotIn("Automatic Recording Loop", self.text)
        self.assertNotIn("This checkout is configured as a CPU-only deployment", self.text)

    def test_it_presents_both_public_distributions(self):
        # W5R4-G52 and the new packaging authority.
        self.assertIn("pip install voice-stt-server", self.text)
        self.assertIn("pip install voice-stt-server-pro", self.text)

    def test_it_teaches_the_canonical_import_package(self):
        self.assertIn("from voice_stt_server import AudioToTextRecorder", self.text)

    def test_it_teaches_the_canonical_cli(self):
        self.assertIn("voice-stt-server --host", self.text)

    def test_it_never_tells_a_user_to_build_kroko(self):
        # The whole point of the two distributions: no end-user native build.
        self.assertNotIn("stt-install-kroko --build", self.text)
        self.assertNotIn("kroko-builder", self.lowered)

    def test_it_advertises_only_the_two_supported_production_engines(self):
        # W5R4-G53.
        for removed in ("whisper.cpp", "sherpa-onnx", "parakeet", "moonshine",
                        "omnilingual", "cohere", "funasr", "granite"):
            with self.subTest(engine=removed):
                index = self.lowered.find(removed)
                if index == -1:
                    continue
                context = self.lowered[max(0, index - 400):index + 200]
                self.assertIn(
                    "internal", context,
                    f"README mentions {removed!r} without marking it internal",
                )

    def test_it_names_both_supported_engines(self):
        self.assertIn("faster_whisper", self.text)
        self.assertIn("kroko_onnx", self.text)

    def test_it_states_the_honest_platform_matrix(self):
        # Section 8: do not promise a platform the shipped runtime lacks.
        self.assertIn("3.12", self.text)
        self.assertIn("x86-64", self.text)

    def test_it_claims_no_unpublished_public_url(self):
        # Section 27: no invented PyPI/registry links, no fake badges.
        for forbidden in ("pypi.org/project/voice-stt-server",
                          "hub.docker.com/r/marcosudau",
                          "img.shields.io",
                          "badge.fury.io"):
            with self.subTest(url=forbidden):
                self.assertNotIn(forbidden, self.lowered)

    def test_it_says_the_release_is_not_published_yet(self):
        self.assertIn("not published yet", self.lowered)

    def test_it_does_not_present_the_private_vps_path_as_the_public_default(self):
        # build/vps is a private, server-specific deployment.
        self.assertNotIn("build/vps", self.text.split("## Release model")[0])

    def test_every_relative_link_resolves_to_a_real_repository_path(self):
        # W5R4: "GitHub links must point to real repository paths".
        missing = []
        for target in _MARKDOWN_LINK_RE.findall(self.text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            path = (REPO_ROOT / target.split("#", 1)[0]).resolve()
            if not path.exists():
                missing.append(target)
        self.assertEqual(missing, [])

    def test_it_leaks_no_secret_or_operator_local_path(self):
        self.assertIsNone(re.search(r"\b[A-Za-z]:[\\/]", self.text))
        for marker in ("pypi-Ag", "dckr_pat_", "ghp_", "BEGIN PRIVATE KEY", ".env"):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, self.text)

    def test_it_explains_that_the_distribution_selects_the_runtime(self):
        # New authority section 13: never key-driven runtime selection.
        self.assertIn("runtime credential", self.lowered)


class MaintainedLinkIntegrityTests(unittest.TestCase):
    def test_every_maintained_relative_markdown_link_resolves(self):
        missing = []
        for path in maintained_markdown():
            for target in _MARKDOWN_LINK_RE.findall(path.read_text(encoding="utf-8")):
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                resolved = (path.parent / target.split("#", 1)[0]).resolve()
                if not resolved.exists():
                    missing.append(f"{path.relative_to(REPO_ROOT)} -> {target}")
        self.assertEqual(missing, [])


class ReleaseProcessDocumentationTests(unittest.TestCase):
    def setUp(self):
        self.path = DOCS / "release-process.md"
        self.text = self.path.read_text(encoding="utf-8")

    def test_the_release_guide_exists(self):
        # W5R4-G60.
        self.assertTrue(self.path.is_file())

    def test_it_documents_the_operator_setup_exactly(self):
        for expected in ("DOCKERHUB_USERNAME", "DOCKERHUB_TOKEN",
                         "Trusted Publish", "release-publish.yml", "`release`"):
            with self.subTest(item=expected):
                self.assertIn(expected, self.text)

    def test_it_documents_two_trusted_publishers(self):
        self.assertIn("voice-stt-server-pro", self.text)
        self.assertIn("two Trusted Publishers", self.text)

    def test_it_documents_the_canonical_state_order(self):
        for state in ("TAGGED", "PYPI_PUBLISHED", "DOCKERHUB_PUBLISHED",
                      "GHCR_PUBLISHED", "EXTERNAL_VERIFIED", "ALIASES_PUBLISHED",
                      "GITHUB_RELEASED", "FINAL_VERIFIED", "COMPLETE"):
            with self.subTest(state=state):
                self.assertIn(state, self.text)

    def test_it_states_the_reproducibility_boundary_honestly(self):
        # Section 12 asks for an honest boundary, not an overclaim.
        self.assertIn("Not pinned", self.text)
        self.assertIn("snapshot.debian.org", self.text)

    def test_it_justifies_the_sdist_decision(self):
        # Section 9 asks for a technical justification, not a silent omission.
        self.assertIn("no sdist", self.text.lower())

    def test_it_states_that_no_pypi_token_is_stored(self):
        self.assertIn("No PyPI API token is stored", self.text)


if __name__ == "__main__":
    unittest.main()
