import contextlib
import copy
import io
import json
import os
import sys
import tempfile
import unittest

from test_guard_writes import GuardCase
import datadir
import onboarding
import session_start


class CreateOnly(GuardCase):
    def test_create_asks_and_existing_or_edit_denied(self):
        for rel in ("cv/final_cv.pdf", "profile/master_cv/MASTER_CONTENT.md"):
            p = self.path(rel)
            os.remove(p)
            self.assertEqual(self.decide("Write", {"file_path": p})[0], "ask")
            self.assertEqual(self.decide("Edit", {"file_path": p})[0], "deny")
            with open(p, "w") as f:
                f.write("Original")
            self.assertEqual(self.decide("Write", {"file_path": p})[0], "deny")
            with open(p) as f:
                self.assertEqual(f.read(), "Original")

    def test_dangling_symlink_is_not_a_new_file(self):
        p = self.path("cv/final_cv.pdf")
        os.remove(p)
        os.symlink(self.path("not-created.pdf"), p)
        # lexists on the submitted path, not only its resolved target.
        self.assertEqual(self.decide("Write", {"file_path": p})[0], "deny")

    def test_config_write_requires_confirmation(self):
        self.assertEqual(self.decide("Write", {"file_path": self.path("jobsearch.config.json")})[0], "ask")


class OnboardingStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = self.tmp.name
        self.cfg = copy.deepcopy(datadir.DEFAULTS)

    def write(self, rel, text="Confirmed English content"):
        p = os.path.join(self.d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(text)

    def complete(self):
        self.cfg["language"]["chat"] = "en"
        self.cfg["identity"]["full_name"] = "Jordan Example"
        self.cfg["paths"]["cv_files"] = ["profile/final.txt"]
        for rel in ("profile/final.txt", self.cfg["paths"]["master_cv"], self.cfg["paths"]["facts"]):
            self.write(rel)
        self.cfg["targets"]["roles"] = ["Engineer"]
        self.cfg["letters"]["base_letters"] = [{"key": "base_en", "path": "base_en.md"}]
        self.cfg["identity"]["links"] = [{"label": "Portfolio", "url": "https://example.org"}]
        self.write("cover_letters/base_en.md", "Agreed base letter")

    def test_missing_then_complete_and_explicit_no_links(self):
        self.assertIn("target roles", onboarding.missing_steps(self.cfg, self.d))
        self.assertIn("English CV (paths.cv_files)", onboarding.missing_steps(self.cfg, self.d))
        self.complete()
        self.assertEqual(onboarding.missing_steps(self.cfg, self.d), [])
        self.assertEqual(onboarding.status(self.cfg, self.d), "Setup status: complete")
        self.cfg["identity"]["links"] = []
        self.assertIn("links for letters (or explicit none)", onboarding.missing_steps(self.cfg, self.d))
        self.write(self.cfg["paths"]["facts"], "Facts\n" + onboarding.NO_LINKS)
        self.assertEqual(onboarding.missing_steps(self.cfg, self.d), [])

    def test_missing_config_file_warning_is_printed(self):
        env = {"JOBSEARCH_DATA_DIR": self.d, "JOBSEARCH_CONFIG": os.path.join(self.d, "absent.yaml")}
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = onboarding.main(["status"], env=env)
        self.assertEqual(code, 0)
        self.assertIn("Warning: config file not found", out.getvalue())
        self.assertIn("Setup status: incomplete", out.getvalue())

    def test_reminder_only_when_incomplete(self):
        self.complete()
        self.cfg["language"]["chat"] = "en"
        p = os.path.join(self.d, "jobsearch.config.json")
        self.write("jobsearch.config.json", json.dumps(self.cfg))
        self.write("START_HERE.md", "Overview")
        self.write("TODO.md", "")
        env = {"JOBSEARCH_DATA_DIR": self.d}
        full = session_start.context(self.d, env)["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn("Setup status: incomplete", full)
        os.remove(os.path.join(self.d, "profile/final.txt"))
        incomplete = session_start.context(self.d, env)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Setup status: incomplete", incomplete)
        self.assertIn("jobsearch-setup update", incomplete)

    def test_language_and_privacy_schema(self):
        for lang in ("", "en", "uk"):
            self.assertEqual(datadir.bad_choices({"language": {"chat": lang}}), [])
        self.assertTrue(datadir.bad_choices({"language": {"chat": "de"}}))
        self.assertEqual(datadir.privacy_problems({"identity": {"links": [{"label": "Portfolio", "url": "https://example.org"}]}}), [])
        for item in ({"label": "CV", "url": "file:///tmp/cv"}, {"label": "CV", "url": "https://[bad"}):
            self.assertTrue(datadir.privacy_problems({"identity": {"links": [item]}}))
        for dest in ({"type": "host", "host": "*.example.org"}, {"type": "git_public_repo", "remote": "example.org/a/b"},
                     {"type": "git_private_repo", "remote": "https://example.org/a/b"},
                     {"type": "mcp_tool", "tool": "mcp__notion__*"}):
            self.assertTrue(datadir.privacy_problems({"privacy": {"approved_destinations": [dest]}}))

    def test_wizard_order_and_general_tune_contract(self):
        from pathlib import Path
        plugin = Path(__file__).resolve().parents[1] / "plugins" / "jobsearch"
        setup = (plugin / "commands" / "jobsearch-setup.md").read_text()
        steps = ["1. **Language.", "2. **Targets.", "3. **Optional limits.", "4. **English CV.", "5. **Identity.",
                 "6. **Facts and master CV.", "7. **Numbers.", "8. **ATS read.", "9. **Base cover letter.", "10. **Links.", "11. **Done."]
        indexes = [setup.index(s) for s in steps]
        self.assertEqual(indexes, sorted(indexes))
        for text in ("two separate confirmations", "do not translate", "base_en", "base_uk", "open FAIL", "create-only"):
            self.assertIn(text, setup)
        apply = (plugin / "commands" / "apply.md").read_text()
        for text in ("Stage 1", "at least 2 distinct files", "cv_tune_general_", "never invent a Job Match", "Never overwrite"):
            self.assertIn(text, apply)


if __name__ == "__main__":
    unittest.main()
