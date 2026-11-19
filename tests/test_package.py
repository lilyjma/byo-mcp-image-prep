"""Check portable references and keep the public skill independent of private setup."""

from pathlib import Path
import re
import unittest


ROOT = Path("/package")


class PackageTests(unittest.TestCase):
    def test_local_markdown_links_resolve(self):
        checked = 0
        for path in ROOT.rglob("*.md"):
            for match in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", path.read_text()):
                destination = match.group(1).split("#")[0]
                if not destination or "://" in destination:
                    continue
                self.assertTrue((path.parent / destination).exists(),
                                str(path) + ": " + destination)
                checked += 1
        self.assertGreater(checked, 5)

    def test_skill_has_frontmatter_and_bounded_main_instructions(self):
        text = (ROOT / "skills/byo-mcp-image-prep/SKILL.md").read_text()
        self.assertTrue(text.startswith("---\nname: byo-mcp-image-prep\n"))
        self.assertIn("\ndescription:", text)
        self.assertLess(len(text.splitlines()), 500)

    def test_public_package_has_no_environment_specific_sources(self):
        prohibited = (
            "dev.azure.com/", "msft.ghe.com/", "serverless-paas-balam/",
            "/Users/", "jiaymabyomcp", "app-08.westcentralus",
        )
        for path in ROOT.rglob("*"):
            if path.is_file():
                for term in prohibited:
                    self.assertNotIn(term, path.read_text(), str(path))


if __name__ == "__main__":
    unittest.main()
