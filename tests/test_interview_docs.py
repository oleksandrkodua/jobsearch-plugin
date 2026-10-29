import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugins", "jobsearch")
FIXTURE = os.path.join(ROOT, "evals", "fixtures", "sample-datadir")


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as f:
        return f.read()


CMD = read(PLUGIN, "commands", "interview.md")
FMT = read(PLUGIN, "reference", "story-bank-format.md")
BANK = read(FIXTURE, "interview", "story_bank.md")
FIELDS = ["Source", "Tags", "Last used", "Situation", "Task", "Action", "Result", "Reflection"]


class InterviewDocs(unittest.TestCase):
    def test_three_modes(self):
        for m in ("Mode `prep`", "Mode `debrief", "Mode `redflags"):
            self.assertIn(m, CMD)

    def test_debrief_asks_before_writing(self):
        s = CMD[CMD.index("Mode `debrief"):CMD.index("Mode `redflags")]
        self.assertIn("Ask before writing anything", s)
        self.assertLess(s.index("Ask, in one short message"), s.index("debrief_<stage>_<date>.md"))
        self.assertIn("tracker_edit.py", s)
        self.assertIn("/outcome", s)

    def test_redflags_statuses_and_sources(self):
        s = CMD[CMD.index("Mode `redflags"):]
        for w in ("SEEN", "NOT SEEN", "ASK", "blockers", "interview.redflag_checks", "OPINION"):
            self.assertIn(w, s)

    def test_prep_flags_gaps_and_no_salary(self):
        self.assertIn("GAP: no story", CMD)
        self.assertIn("paths.story_bank", CMD)
        self.assertIn("paths.study_library", CMD)
        self.assertIn("honesty.known_risk_lines", CMD)

    def test_format_names_every_field(self):
        for f in ["id", "title"] + FIELDS:
            self.assertRegex(FMT, r"\| " + re.escape(f) + r" \|")
        self.assertIn("no number, observed effect", FMT)
        self.assertIn("approval", FMT)
        self.assertIn("5 to 10", FMT)

    def test_fixture_stories_have_every_field(self):
        blocks = re.split(r"(?m)^## ", BANK)[1:]
        self.assertGreaterEqual(len(blocks), 2)
        for b in blocks:
            self.assertRegex(b.splitlines()[0], r"^S-\d{3}: \S")
            for f in FIELDS:
                self.assertRegex(b, r"(?m)^- " + f + r": \S", f)


if __name__ == "__main__":
    unittest.main()
