import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugins", "jobsearch")


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as f:
        return f.read()


class VersionConsistency(unittest.TestCase):
    """The version a reader sees must be the version the manifest ships."""

    def setUp(self):
        self.version = json.loads(read(PLUGIN, ".claude-plugin", "plugin.json"))["version"]

    def test_manifest_version_is_semver(self):
        self.assertRegex(self.version, r"^\d+\.\d+\.\d+$")

    def test_readme_current_version_matches_manifest(self):
        m = re.search(r"Current version: (\d+\.\d+\.\d+)", read(ROOT, "README.md"))
        self.assertIsNotNone(m, "README.md has no 'Current version: X.Y.Z' line")
        self.assertEqual(m.group(1), self.version)

    def test_readme_names_the_matching_tag(self):
        text = read(ROOT, "README.md")
        for tag in re.findall(r"tagged `v(\d+\.\d+\.\d+)`", text):
            self.assertEqual(tag, self.version)

    def test_changelog_has_a_section_for_the_manifest_version(self):
        self.assertRegex(read(PLUGIN, "CHANGELOG.md"), r"(?m)^## " + re.escape(self.version) + r"\s*$")


if __name__ == "__main__":
    unittest.main()
