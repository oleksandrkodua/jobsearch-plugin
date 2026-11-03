import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_DIR = os.path.join(ROOT, "plugins", "jobsearch", "skills", "career-paths")


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as f:
        return f.read()


SKILL = read(SKILL_DIR, "SKILL.md")
FM = re.match(r"---\nname: (.+)\ndescription: (.+)\n---\n", SKILL)


class CareerPathsDocs(unittest.TestCase):
    def test_frontmatter(self):
        self.assertIsNotNone(FM)
        self.assertEqual(FM.group(1), "career-paths")
        d = FM.group(2)
        for w in ("Not for", "(use rank)", "(use upskill)", "data dir"):
            self.assertIn(w, d, w)
        self.assertLess(len(d), 1100)

    def test_inputs_reuse_funnel(self):
        for w in ('python3 "${CLAUDE_PLUGIN_ROOT}/scripts/funnel_report.py"', "Reply rate by role type",
                  "paths.ranked", "paths.facts", "paths.master_cv", "targets.roles_not_primary", "blockers"):
            self.assertIn(w, SKILL, w)

    def test_salary_rules(self):
        for w in ("source link", "date checked", "region", "seniority", "gross/net", "no source found",
                  "never converted to net", "never averaged", "comparison is not possible",
                  "never stored in the engine or the config"):
            self.assertIn(w, SKILL, w)

    def test_output_and_grounding(self):
        for w in ("career_paths_<YYYY-MM-DD>.md", "3-5", "| Direction |", "Not recommended", "Unverified",
                  "Decision for the user", "/upskill roadmap <direction>", "| Claim | Source | Verdict |",
                  "NOT IN SOURCES", "never edits `targets`"):
            self.assertIn(w, SKILL, w)

    def test_evals(self):
        ev = json.loads(read(SKILL_DIR, "evals", "evals.json"))
        self.assertEqual(ev["skill_name"], "career-paths")
        self.assertEqual(len(ev["evals"]), 3)


if __name__ == "__main__":
    unittest.main()
