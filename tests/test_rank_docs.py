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
