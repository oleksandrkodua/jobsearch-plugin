import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugins", "jobsearch")


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as f:
        return f.read()


CMD = read(PLUGIN, "commands", "upskill.md")
FACTS = read(ROOT, "evals", "fixtures", "sample-datadir", "profile", "facts.md")
RM = CMD[CMD.index("## Mode `roadmap`"):] if "## Mode `roadmap`" in CMD else ""


class RoadmapDocs(unittest.TestCase):
    def test_hint_and_mode_detection(self):
        hint = [l for l in CMD.splitlines() if l.startswith("argument-hint:")][0]
        self.assertIn("roadmap [direction]", hint)
        step1 = CMD[CMD.index("## Step 1 - Mode"):CMD.index("## Step 2")]
        self.assertIn("`roadmap [direction]`", step1)
        self.assertIn("aggregate mode", step1)
        self.assertIn("targeted mode", step1)

    def test_roadmap_reuses_steps_and_gate(self):
        self.assertTrue(RM, "upskill.md has no '## Mode `roadmap`' section")
        for w in ("Steps 2-5", "less than 30 days old", "targets.roles_not_primary", "path (c)",
                  "hours per week", "start month", "No new config keys"):
            self.assertIn(w, RM, w)

    def test_roadmap_direction_and_no_overwrite(self):
        self.assertIn("treat it as the target for this run", RM)
        self.assertIn("latest aggregate", RM)
        self.assertIn("never overwrite an existing file", RM.lower())
        desc = [l for l in CMD.splitlines() if l.startswith("description:")][0]
        self.assertIn("roadmap [direction]", desc)

    def test_roadmap_output(self):
        for w in ("roadmap_<YYYY-MM-DD>.md", "12-row table",
                  "| Month | Goal | Gap id(s) | Done when | Hours | Resource |",
                  "months 1-3", "drop Low items", "Certifications", "date checked", "unverified",
                  "not recommended: no gap it closes", "Networking strategy", "never sent or posted",
                  "Quarterly checkpoints", "Unverified"):
            self.assertIn(w, RM, w)

    def test_roadmap_claims_rule(self):
        self.assertIn("planning a certification is not a claim", RM)

    def test_fixture_has_gap_table(self):
        self.assertIn("## Gaps from rejections", FACTS)
        self.assertRegex(FACTS, r"(?m)^\| G-\d{2} \|")
        self.assertIn("## Not skill gaps", FACTS)


class RoadmapRuleSentences(unittest.TestCase):
    """Hard-rule sentences must stay whole: a weakened or split rule fails here."""

    def test_rule_sentences_intact(self):
        for s in (
            'Message drafts only: never sent or posted (hard rule 1).',
            'A roadmap is built only after the user picks path (c).',
            'studying is not a claim, and planning a certification is not a claim either.',
            'A skill or certificate becomes claimable only after the user states the evidence and adds it to the facts file.',
            'No invented gap history, no invented resources.',
        ):
            self.assertIn(s, RM, s)

if __name__ == "__main__":
    unittest.main()
