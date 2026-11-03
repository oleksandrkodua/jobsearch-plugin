import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugins", "jobsearch")
SKILL_DIR = os.path.join(PLUGIN, "skills", "linkedin-profile-optimizer")
DD = os.path.join(ROOT, "evals", "fixtures", "sample-datadir")
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))

import datadir  # noqa: E402
import grounding_audit as ga  # noqa: E402


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as f:
        return f.read()


SKILL = read(SKILL_DIR, "SKILL.md")
FM = re.match(r"---\nname: (.+)\ndescription: (.+)\n---\n", SKILL)
MODE = SKILL[SKILL.index("## Data-dir mode"):SKILL.index("## Review output")] if "## Data-dir mode" in SKILL else ""


class LinkedinDocs(unittest.TestCase):
    def test_frontmatter(self):
        self.assertIsNotNone(FM)
        self.assertEqual(FM.group(1), "linkedin-profile-optimizer")
        d = FM.group(2)
        for w in ("jobsearch data dir", "(use apply)", "(use cover-letter)", "(use ats-screening)", "Do not use"):
            self.assertIn(w, d, w)
        self.assertLess(len(d), 1100)

    def test_existing_guidance_kept(self):
        for w in ("## Workflow", "## Search principles", "## Review output", "Avoid keyword stuffing"):
            self.assertIn(w, SKILL, w)

    def test_mode_limits_and_sources(self):
        self.assertTrue(MODE, "no '## Data-dir mode' section before '## Review output'")
        for w in ("220 characters", "2,600 characters", "paths.master_cv", "paths.facts", "paths.ranked",
                  "2+ files", "targets.roles", "honesty.allowed_numbers", "honesty.known_risk_lines",
                  "NOT IN SOURCES", "untrusted", "datadir.py"):
            self.assertIn(w, MODE, w)

    def test_mode_conflicts_first_and_audit(self):
        self.assertLess(MODE.index("Conflicts"), MODE.index("Headline"))
        self.assertIn('python3 "${CLAUDE_PLUGIN_ROOT}/scripts/grounding_audit.py" <paths.reports>/linkedin_draft_<YYYY-MM-DD>.txt --kind cv', MODE)
        self.assertIn("into the \"Audit result\" section of `linkedin_<YYYY-MM-DD>.md`, not into an application folder's `audit.txt`", MODE)
        self.assertIn("If no export path is given", MODE)
        self.assertIn("linkedin_<YYYY-MM-DD>.md", MODE)
        self.assertIn("open FAIL", MODE)

    def test_mode_never_publishes(self):
        for w in ("never logs in", "posts", "the user copies"):
            self.assertIn(w, MODE, w)

    def test_evals(self):
        ev = json.loads(read(SKILL_DIR, "evals", "evals.json"))
        self.assertEqual(ev["skill_name"], "linkedin-profile-optimizer")
        self.assertEqual(len(ev["evals"]), 5)
        self.assertEqual([e["id"] for e in ev["evals"]], [1, 2, 3, 4, 5])
        for e in ev["evals"]:
            self.assertTrue(e["prompt"] and e["expected_output"])


class LinkedinFixtureAudit(unittest.TestCase):
    def test_one_fail_one_warn(self):
        cfg = datadir.load_config(DD, {})
        master = read(datadir.data_path(cfg, DD, "master_cv"))
        fails, warns = ga.audit(read(ROOT, "evals", "fixtures", "linkedin", "linkedin_draft.txt"), "cv", cfg, master)
        self.assertEqual(len(fails), 1, fails)
        self.assertIn("25%", fails[0])
        self.assertEqual(len(warns), 1, warns)
        self.assertIn("Terraform", warns[0])


if __name__ == "__main__":
    unittest.main()
