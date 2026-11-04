import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "plugins", "jobsearch", "commands", "rank.md"), encoding="utf-8") as f:
    CMD = f.read()


class RankDocs(unittest.TestCase):
    def test_batch_is_capped_at_ten(self):
        self.assertIn("Batch mode: at most 10 vacancies per run", CMD)
        self.assertIn("offer them as the next batch", CMD)


if __name__ == "__main__":
    unittest.main()


class RankLocationFilter(unittest.TestCase):
    def test_hint_and_filter_step(self):
        hint = [l for l in CMD.splitlines() if l.startswith("argument-hint:")][0]
        self.assertIn("[--country any|ukraine|not_ukraine] [--remote any|yes|no]", hint)
        for s in ("targets.country", "targets.remote",
                  "A value given in the arguments overrides the config for this run.",
                  "Unknown is never filtered out",
                  "FILTERED (country)", "FILTERED (remote)",
                  "Hybrid counts as not remote."):
            self.assertIn(s, CMD, s)

    def test_template_documents_the_keys(self):
        with open(os.path.join(ROOT, "plugins", "jobsearch", "reference", "config.template.yaml"), encoding="utf-8") as f:
            t = f.read()
        self.assertIn("country: any", t)
        self.assertIn("remote: any", t)
