import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "plugins", "jobsearch", "skills", "ats-screening", "scripts", "ats_technical_score.py")


class AtsScoreTest(unittest.TestCase):
    def test_selftest_passes(self):
        r = subprocess.run([sys.executable, "-B", SCRIPT, "--selftest"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("0 failed", r.stdout)

    def test_synthetic_fixtures(self):
        with open(SCRIPT, encoding="utf-8") as f:
            src = f.read()
        self.assertIn('"+10000000000"', src)
        self.assertIn('"+1 000 000 00 00"', src)
        self.assertIn("Senior Engineer | Example Corp 04/2014 - Present", src)

    def test_one_copy_of_each_script(self):
        found = [os.path.join(dp, n) for dp, _, fn in os.walk(os.path.join(ROOT, "plugins"))
                 for n in fn if n in ("ats_technical_score.py", "pdf_technical_check.py")]
        self.assertEqual(len(found), 2, found)


if __name__ == "__main__":
    unittest.main()
