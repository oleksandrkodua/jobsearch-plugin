import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugins", "jobsearch")
HOOK = os.path.join(PLUGIN, "hooks", "guard_writes.py")
sys.path.insert(0, os.path.join(PLUGIN, "hooks"))
import guard_writes  # noqa: E402


def write(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class GuardCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = os.path.realpath(self.tmp.name)
        self.dd = os.path.join(self.base, "data")
        write(os.path.join(self.dd, "jobsearch.config.json"),
              json.dumps({"paths": {"cv_files": ["cv/final_cv.pdf"]}}))
        for rel in ("tracker/vacancies.csv", "profile/facts.md", "profile/master_cv/MASTER_CONTENT.md",
                    "cv/final_cv.pdf"):
            write(os.path.join(self.dd, rel))
        self.env = {"JOBSEARCH_DATA_DIR": self.dd}
        self.proj = os.path.join(self.base, "project")
        os.makedirs(self.proj)

    def decide(self, tool, tool_input, cwd=None, env=None):
        return guard_writes.decide(tool, tool_input, cwd or self.proj, self.env if env is None else env)

    def path(self, rel):
        return os.path.join(self.dd, rel)


class WriteTools(GuardCase):
    def test_tracker_write_denied_with_pointer_to_tracker_edit(self):
        decision, reason = self.decide("Write", {"file_path": self.path("tracker/vacancies.csv")})
        self.assertEqual(decision, "deny")
        self.assertIn("tracker_edit.py", reason)

    def test_tracker_changelog_and_history_denied(self):
        for rel in ("tracker/CHANGELOG.csv", "tracker/history/vacancies_20261104.csv"):
            self.assertEqual(self.decide("Edit", {"file_path": self.path(rel)})[0], "deny", rel)

    def test_cv_files_and_master_cv_denied(self):
        for rel in ("cv/final_cv.pdf", "profile/master_cv/MASTER_CONTENT.md"):
            decision, reason = self.decide("MultiEdit", {"file_path": self.path(rel)})
            self.assertEqual(decision, "deny", rel)
            self.assertIn("read-only", reason)

    def test_facts_edit_asks_the_user(self):
        decision, reason = self.decide("Edit", {"file_path": self.path("profile/facts.md")})
        self.assertEqual(decision, "ask")
        self.assertIn("facts", reason)

    def test_other_data_dir_files_allowed(self):
        for rel in ("applications/acme_qa/cv_tune.md", "reports/roadmap_2026-11-04.md", "profile/notes.md"):
            self.assertIsNone(self.decide("Write", {"file_path": self.path(rel)}), rel)

    def test_relative_path_resolved_from_cwd(self):
        self.assertEqual(self.decide("Write", {"file_path": "tracker/vacancies.csv"}, cwd=self.dd)[0], "deny")

    def test_symlink_to_tracker_denied(self):
        link = os.path.join(self.proj, "t.csv")
        os.symlink(self.path("tracker/vacancies.csv"), link)
        self.assertEqual(self.decide("Write", {"file_path": link})[0], "deny")

    def test_notebook_path_checked(self):
        self.assertEqual(self.decide("NotebookEdit", {"notebook_path": self.path("cv/final_cv.pdf")})[0], "deny")

    def test_no_data_dir_means_no_opinion(self):
        self.assertIsNone(self.decide("Write", {"file_path": self.path("tracker/vacancies.csv")}, env={}))

    def test_unknown_tool_ignored(self):
        self.assertIsNone(self.decide("Read", {"file_path": self.path("tracker/vacancies.csv")}))


class BashTool(GuardCase):
    def test_tracker_edit_script_allowed(self):
        cmd = f'python3 "$CLAUDE_PLUGIN_ROOT/scripts/tracker_edit.py" set VAC-001 status APPLIED'
        self.assertIsNone(self.decide("Bash", {"command": cmd}))

    def test_reading_protected_file_allowed(self):
        self.assertIsNone(self.decide("Bash", {"command": f"cat {self.path('tracker/vacancies.csv')}"}))

    def test_writing_protected_file_asks(self):
        for cmd in (f"sed -i '' 's/a/b/' {self.path('tracker/vacancies.csv')}",
                    f"echo x >> {self.path('profile/master_cv/MASTER_CONTENT.md')}",
                    "cp new.pdf cv/final_cv.pdf",
                    "rm tracker/vacancies.csv"):
            decision, reason = self.decide("Bash", {"command": cmd})
            self.assertEqual(decision, "ask", cmd)
            self.assertIn("protected", reason)

    def test_stderr_redirects_are_not_writes(self):
        for cmd in (f"grep x {self.path('tracker/vacancies.csv')} 2>/dev/null",
                    "wc -l tracker/vacancies.csv 2>&1 | head"):
            self.assertIsNone(self.decide("Bash", {"command": cmd}), cmd)

    def test_unrelated_write_allowed(self):
        self.assertIsNone(self.decide("Bash", {"command": "echo hi > reports/out.md"}))


class OutreachTools(GuardCase):
    def in_project(self, tool, tool_input):
        return guard_writes.decide(tool, tool_input, self.dd, self.env)  # project root = the data dir

    def test_clicks_types_and_sends_ask_in_the_data_project(self):
        for tool, ti in (("mcp__claude-in-chrome__computer", {"action": "left_click", "coordinate": [1, 2]}),
                         ("mcp__Claude_Browser__computer", {"action": "type", "text": "x"}),
                         ("mcp__plugin_playwright_playwright__browser_click", {"element": "Apply"}),
                         ("mcp__plugin_playwright_playwright__browser_fill_form", {}),
                         ("mcp__claude-in-chrome__form_input", {"ref": "r1", "value": "x"}),
                         ("mcp__Claude_Browser__browser_batch", {"actions": [{"name": "computer", "input": {"action": "left_click"}}]}),
                         ("mcp__computer-use__app_click", {}),
                         ("mcp__gmail__send_message", {"to": "a@example.com"}),
                         ("mcp__slack__reply", {})):
            decision, reason = self.in_project(tool, ti) or (None, "")
            self.assertEqual(decision, "ask", tool)
            self.assertIn("never send, apply or submit", reason)

    def test_reading_and_navigation_allowed(self):
        for tool, ti in (("mcp__claude-in-chrome__computer", {"action": "screenshot"}),
                         ("mcp__Claude_Browser__get_page_text", {}),
                         ("mcp__Claude_Browser__navigate", {"url": "https://example.com"}),
                         ("mcp__plugin_playwright_playwright__browser_snapshot", {}),
                         ("mcp__notion__search", {"query": "send"})):
            self.assertIsNone(self.in_project(tool, ti), tool)

    def test_other_projects_are_not_affected(self):
        decision = guard_writes.decide("mcp__plugin_playwright_playwright__browser_click", {}, self.proj, self.env)
        self.assertIsNone(decision)

    def test_marker_project_counts_as_the_data_project(self):
        with open(os.path.join(self.proj, ".jobsearch-data"), "w", encoding="utf-8") as f:
            f.write(self.dd)
        decision = guard_writes.decide("mcp__claude-in-chrome__computer", {"action": "left_click"}, self.proj, {})
        self.assertEqual(decision[0], "ask")


class HookProcess(GuardCase):
    def run_hook(self, payload, env):
        e = {k: v for k, v in os.environ.items() if not k.startswith("JOBSEARCH_")}
        e.update(env)
        return subprocess.run([sys.executable, "-B", HOOK], input=payload, capture_output=True, text=True, env=e)

    def test_deny_prints_pretooluse_decision(self):
        payload = json.dumps({"tool_name": "Write", "cwd": self.proj,
                              "tool_input": {"file_path": self.path("tracker/vacancies.csv")}})
        r = self.run_hook(payload, self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "PreToolUse")
        self.assertEqual(out["permissionDecision"], "deny")
        self.assertTrue(out["permissionDecisionReason"])

    def test_allowed_and_broken_input_print_nothing(self):
        ok = json.dumps({"tool_name": "Write", "cwd": self.proj, "tool_input": {"file_path": self.path("reports/a.md")}})
        for payload in (ok, "not json", ""):
            r = self.run_hook(payload, self.env)
            self.assertEqual((r.returncode, r.stdout), (0, ""), payload)

    def test_registered_in_hooks_json(self):
        with open(os.path.join(PLUGIN, "hooks", "hooks.json"), encoding="utf-8") as f:
            pre = json.load(f)["hooks"]["PreToolUse"]
        self.assertEqual(len(pre), 2)
        self.assertEqual(set(pre[0]["matcher"].split("|")), {"Write", "Edit", "MultiEdit", "NotebookEdit", "Bash"})
        self.assertEqual(pre[1]["matcher"], "mcp__.*")
        for entry in pre:
            self.assertEqual(entry["hooks"][0]["command"], 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/guard_writes.py"')


if __name__ == "__main__":
    unittest.main()
