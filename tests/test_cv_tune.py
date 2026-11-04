import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugins", "jobsearch")
SCRIPTS = os.path.join(PLUGIN, "scripts")
DD = os.path.join(ROOT, "evals", "fixtures", "sample-datadir")
sys.path.insert(0, SCRIPTS)

import datadir  # noqa: E402
import grounding_audit as ga  # noqa: E402


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as f:
        return f.read()


CMD = read(PLUGIN, "commands", "apply.md")
FMT = read(PLUGIN, "reference", "cv-tune-format.md")
ATS = read(PLUGIN, "skills", "ats-screening", "SKILL.md")
TUNE = CMD[CMD.index("## Mode `tune`"):] if "## Mode `tune`" in CMD else ""


class ApplyTuneDocs(unittest.TestCase):
    def test_argument_hint_names_tune(self):
        hint = [l for l in CMD.splitlines() if l.startswith("argument-hint:")][0]
        self.assertIn("tune <vacancy URL or pasted text>", hint)

    def test_tune_section_reuses_and_audits(self):
        self.assertTrue(TUNE, "apply.md has no '## Mode `tune`' section")
        for w in ("Steps 4-6", "ats-screening", "Stage 2", "Requirement Match Matrix", "ATS Keyword Alignment",
                  "paths.cv_files", "cv_tune.md", "cv_tune_bullets.md", "--kind cv", "grounding-audit",
                  "audit.txt", "honesty.known_risk_lines", "projection on the tuned copy, not a guarantee",
                  "${CLAUDE_PLUGIN_ROOT}/reference/cv-tune-format.md", "/upskill",
                  "as in Gate 0 and step 1", "every WARN is resolved in writing"):
            self.assertIn(w, TUNE, w)

    def test_tune_audit_file_and_no_overwrite(self):
        self.assertIn("audit_tune.txt", TUNE)
        self.assertIn("audit_tune.txt", FMT)
        self.assertIn("Never overwrite an existing file", TUNE)
        self.assertEqual(TUNE.split("## General tune", 1)[0].count("audit.txt"), 1)  # only the "not audit.txt" pointer remains
        desc = [l for l in CMD.splitlines() if l.startswith("description:")][0]
        self.assertIn("Mode `tune`", desc)

    def test_tune_never_edits_final_cv(self):
        self.assertIn("Never edit the files in `paths.cv_files` or the master CV", TUNE)
        self.assertIn("only when the user asks", TUNE)

    def test_format_sections_in_order(self):
        heads = ["## 1. Match score", "## 2. Missing or weak keywords", "## 3. Feedback per section",
                 "## 4. Rewritten bullets", "## 5. Prioritised changes", "## 6. Audit and risk lines"]
        pos = [FMT.index(h) for h in heads]
        self.assertEqual(pos, sorted(pos))

    def test_format_block_and_actions(self):
        for w in ("Original:", "Improved:", "Keywords:", "Source:", "NOT IN SOURCES",
                  "`surface`", "`strengthen`", "`do not add (no evidence)`",
                  "Fits", "Weak or generic", "Change", "Do not add", "5-10"):
            self.assertIn(w, FMT, w)

    def test_format_guardrails(self):
        for w in ("at most 2 newly surfaced keywords per bullet", "more than 3 times in the whole CV",
                  "keyword cloud", "hidden or white text", "verbatim", "master skills list",
                  "Partial in the matrix stays Partial"):
            self.assertIn(w, FMT, w)

    def test_ats_stage2_points_to_tune(self):
        self.assertIn("`/apply tune`", ATS)


class TuneFixtureAudit(unittest.TestCase):
    def test_one_fail_one_warn(self):
        cfg = datadir.load_config(DD, {})
        master = read(datadir.data_path(cfg, DD, "master_cv"))
        text = read(ROOT, "evals", "fixtures", "cv_tune", "cv_tune_bullets.md")
        fails, warns = ga.audit(text, "cv", cfg, master)
        self.assertEqual(len(fails), 1, fails)
        self.assertIn("30%", fails[0])
        self.assertEqual(len(warns), 1, warns)
        self.assertIn("Kubernetes", warns[0])


class TuneFormatRuleSentences(unittest.TestCase):
    """Hard-rule sentences must stay whole: a weakened or split rule fails here."""

    def test_rule_sentences_intact(self):
        for s in (
            '4. **Inputs are read-only.** The final CV files and the master CV are never written.',
            '5. **Nothing is sent or uploaded.**',
            '6. **Conflicts are asked, not resolved.** If the final CV and the master disagree on a date, title or employer, list the conflict and ask the user.',
            'A block with `NOT IN SOURCES` is shown but marked not usable, and it never goes into `cv_tune_bullets.md` or `cv.md`.',
        ):
            self.assertIn(s, FMT, s)

class TuneCommandRuleSentences(unittest.TestCase):
    """Hard-rule sentences must stay whole: a weakened or split rule fails here."""

    def test_rule_sentences_intact(self):
        for s in (
            'It is read-only (hard rule 6).',
            'Never edit the files in `paths.cv_files` or the master CV. Nothing is sent or uploaded; say "not sent".',
        ):
            self.assertIn(s, TUNE, s)

if __name__ == "__main__":
    unittest.main()
