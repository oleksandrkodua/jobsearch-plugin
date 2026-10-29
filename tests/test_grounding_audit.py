import copy
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "plugins", "jobsearch", "scripts")
SCRIPT = os.path.join(SCRIPTS, "grounding_audit.py")
DD = os.path.join(ROOT, "evals", "fixtures", "sample-datadir")
LETTERS = os.path.join(ROOT, "evals", "fixtures", "letters")
sys.path.insert(0, SCRIPTS)

import datadir  # noqa: E402
import grounding_audit as ga  # noqa: E402

CFG = datadir.load_config(DD, {})
with open(datadir.data_path(CFG, DD, "master_cv"), encoding="utf-8") as _f:
    MASTER = _f.read()


def letter(name):
    with open(os.path.join(LETTERS, name + ".md"), encoding="utf-8") as f:
        return f.read()


def run(text, kind="letter", cfg=None, **kw):
    return ga.audit(text, kind, cfg or CFG, MASTER, **kw)


def has(items, needle):
    return any(needle in x for x in items)


def sized(n):
    return "Dear Hiring Team,\n\n" + " ".join(["word"] * n) + "\n\nBest regards,\nJordan Example\n"


class AuditCase(unittest.TestCase):
    def test_clean_letter_passes(self):
        fails, warns = run(letter("clean"))
        self.assertEqual(fails, [])
        self.assertEqual(warns, [])

    def test_never_claim_fail(self):
        fails, _ = run(letter("never_claim"))
        self.assertEqual(len(fails), 1)
        self.assertIn("people management is not claimable", fails[0])

    def test_allowed_exception_sentence_skipped(self):
        t = letter("clean").replace("Outside work", "I hold a degree in blockchain economics. Outside work")
        self.assertEqual(run(t)[0], [])
        t2 = letter("clean").replace("Outside work", "I love blockchain hype. Outside work")
        self.assertTrue(has(run(t2)[0], "not Jordan's experience"))

    def test_scoped_exception_does_not_hide_other_rule(self):
        cfg = copy.deepcopy(CFG)
        cfg["honesty"]["allowed_exceptions"] = [{"pattern": "degree in blockchain", "why": "edu", "rules": ["blockchain"]}]
        t = letter("clean").replace("Outside work", "I hold a degree in blockchain and managed a team. Outside work")
        fails, _ = run(t, cfg=cfg)
        self.assertEqual(len(fails), 1)
        self.assertIn("people management", fails[0])
        # unscoped exception keeps the apply-to-all behaviour
        self.assertEqual(run(t)[0], [])
        # a rule may also be named by its exact pattern
        cfg["honesty"]["allowed_exceptions"][0]["rules"] = [r"\bblockchain\b"]
        self.assertEqual(len(run(t, cfg=cfg)[0]), 1)

    def test_malformed_rules_key_is_an_error(self):
        for bad in ([], "blockchain", [""], [3]):
            cfg = copy.deepcopy(CFG)
            cfg["honesty"]["allowed_exceptions"] = [{"pattern": "degree in blockchain", "rules": bad}]
            with self.assertRaises(ValueError, msg=repr(bad)) as c:
                run(letter("clean"), cfg=cfg)
            self.assertIn("honesty.allowed_exceptions[0].rules", str(c.exception))

    def test_bad_signature_regex_names_config_key(self):
        cfg = copy.deepcopy(CFG)
        cfg["letters"]["signature_lines"] = ["(unclosed"]
        with self.assertRaises(ValueError) as c:
            run(letter("clean"), cfg=cfg)
        self.assertIn("letters.signature_lines[0]", str(c.exception))

    def test_bad_regex_names_config_key(self):
        cfg = copy.deepcopy(CFG)
        cfg["honesty"]["never_claim"] = [{"pattern": "(unclosed", "why": "x"}]
        with self.assertRaises(ValueError) as c:
            run(letter("clean"), cfg=cfg)
        self.assertIn("honesty.never_claim", str(c.exception))

    def test_years_warning_uses_configured_facts_path(self):
        cfg = copy.deepcopy(CFG)
        cfg["paths"]["facts"] = "profile/my_facts.md"
        t = letter("clean").replace("Outside work", "I have 8 years of experience. Outside work")
        self.assertTrue(has(run(t, cfg=cfg)[1], "confirm against profile/my_facts.md"))
        self.assertFalse(has(run(t, cfg=cfg)[1], "profile/facts.md"))

    def test_placeholder_fail(self):
        self.assertTrue(has(run(letter("placeholder"))[0], "placeholder not filled: [COMPANY NAME]"))

    def test_long_dash_fail_letter_only(self):
        self.assertTrue(has(run(letter("long_dash"))[0], "long dash found"))
        self.assertFalse(has(run(letter("long_dash"), kind="cv")[0], "long dash"))
        cfg = copy.deepcopy(CFG)
        cfg["letters"]["no_long_dash"] = False
        self.assertFalse(has(run(letter("long_dash"), cfg=cfg)[0], "long dash"))

    def test_length_bounds(self):
        self.assertTrue(has(run(sized(149))[0], "letter length 149 words (norm 150-320)"))
        self.assertFalse(has(run(sized(150))[0], "letter length"))
        self.assertTrue(has(run(sized(321))[0], "letter length 321"))
        self.assertFalse(has(run(sized(149), no_length=True)[0], "letter length"))
        self.assertTrue(has(run(letter("too_short"))[0], "letter length"))

    def test_restricted_tool_needs_disclaimer(self):
        fails, _ = run(letter("tool_no_disclaimer"))
        self.assertTrue(has(fails, "restricted tool claimed without the required disclaimer"))
        t = letter("clean").replace("Outside work", "I use Selenium only in a side project. Outside work")
        fails, warns = run(t)
        self.assertEqual(fails, [])
        self.assertTrue(has(warns, "restricted tool inside a disclaimer sentence"))
        fails, _ = run(t, kind="cv")
        self.assertTrue(has(fails, "CV mentions restricted tool"))

    def test_tool_not_in_master_warns_unless_extra(self):
        t = letter("clean").replace("Outside work", "I know Docker. Outside work")
        self.assertTrue(has(run(t)[1], "tool «Docker» is not in MASTER skills"))
        self.assertFalse(has(run(t, allowed_extra={"docker"})[1], "Docker"))

    def test_year_not_in_master_warns(self):
        t = letter("clean").replace("Outside work", "I started in 1999. Outside work")
        self.assertTrue(has(run(t)[1], "year 1999 is not in the master CV"))
        self.assertFalse(has(run(t.replace("1999", "2018"))[1], "year 2018"))

    def test_year_claim_allowed_list(self):
        cfg = copy.deepcopy(CFG)
        cfg["honesty"]["allowed_year_claims"] = [{"n": 10}]
        base = letter("clean")
        fails, warns = run(base.replace("Outside work", "I have 10 years of experience. Outside work"), cfg=cfg)
        self.assertEqual(fails, [])
        self.assertTrue(has(warns, "«10 years»: years claim, confirm against profile/facts.md"))
        fails, _ = run(base.replace("Outside work", "I have 12 years of experience. Outside work"), cfg=cfg)
        self.assertTrue(has(fails, "numeric claim not in master: «12 years»"))

    def test_year_claim_notes_listed(self):
        t = letter("clean").replace("Outside work", "I have 8 years of experience. Outside work")
        self.assertTrue(has(run(t)[1], "(8 total; 3 on the platform team)"))

    def test_numeric_claims_and_allowed_numbers(self):
        base = letter("clean")
        self.assertTrue(has(run(base.replace("Outside work", "I cut bugs by 55%. Outside work"))[0], "numeric claim not in master: «55%»"))
        self.assertEqual(run(base.replace("Outside work", "I cut bugs by 40%. Outside work"))[0], [])

    def test_signature_lines_excluded_from_word_count(self):
        # 147 body words fail only when the sign-off (4 words) is excluded, as configured
        t = sized(147)
        self.assertTrue(has(run(t)[0], "letter length 147"))
        cfg = copy.deepcopy(CFG)
        cfg["letters"]["signature_lines"] = []
        self.assertFalse(has(run(t, cfg=cfg)[0], "letter length"))  # sign-off and name counted: 151

    def test_forbidden_openers_and_buzzwords(self):
        t = letter("clean").replace("I build", "I am writing to apply. I am passionate. I build", 1)
        fails, _ = run(t)
        self.assertTrue(has(fails, "forbidden opener"))
        self.assertTrue(has(fails, "forbidden buzzword"))

    def test_empty_honesty_config_still_runs(self):
        cfg = datadir.load_config(DD, {"JOBSEARCH_CONFIG": os.path.join(DD, "nonexistent.yaml")})
        fails, warns = ga.audit(letter("clean"), "letter", cfg, MASTER)
        self.assertTrue(has(warns, "no honesty limits configured"))
        self.assertEqual(fails, [])

    def test_configured_honesty_has_no_empty_warning(self):
        self.assertFalse(has(run(letter("clean"))[1], "no honesty limits"))


class CliCase(unittest.TestCase):
    def cli(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith("JOBSEARCH_")}
        env["JOBSEARCH_DATA_DIR"] = DD
        return subprocess.run([sys.executable, "-B", SCRIPT, *args], capture_output=True, text=True, env=env)

    def test_cli_pass_and_fail_exit_codes(self):
        r = self.cli(os.path.join(LETTERS, "clean.md"), "--kind", "letter")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("RESULT: PASS  (0 fail, 0 warn)", r.stdout)
        r = self.cli(os.path.join(LETTERS, "never_claim.md"), "--kind", "letter")
        self.assertEqual(r.returncode, 1)
        self.assertIn("  FAIL ", r.stdout)
        self.assertIn("RESULT: FAIL", r.stdout)

    def test_cli_config_option_and_no_length(self):
        r = self.cli(os.path.join(LETTERS, "too_short.md"), "--kind", "letter", "--config",
                     os.path.join(DD, "jobsearch.config.yaml"))
        self.assertEqual(r.returncode, 1)
        r = self.cli(os.path.join(LETTERS, "too_short.md"), "--kind", "letter", "--no-length")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_cli_bad_regex_exit_2(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            cfgp = os.path.join(d, "c.yaml")
            with open(cfgp, "w") as f:
                f.write("honesty:\n  never_claim:\n    - {pattern: '(unclosed', why: x}\n")
            r = self.cli(os.path.join(LETTERS, "clean.md"), "--kind", "letter", "--config", cfgp)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("honesty.never_claim", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_cli_bad_signature_regex_exit_2(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            cfgp = os.path.join(d, "c.yaml")
            with open(cfgp, "w") as f:
                f.write("letters:\n  signature_lines: ['(unclosed']\n")
            r = self.cli(os.path.join(LETTERS, "clean.md"), "--kind", "letter", "--config", cfgp)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("letters.signature_lines", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_cli_missing_master_is_an_error(self):
        r = self.cli(os.path.join(LETTERS, "clean.md"), "--kind", "letter", "--master", os.path.join(DD, "nope.md"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("master", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
