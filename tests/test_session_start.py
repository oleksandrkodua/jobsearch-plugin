import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugins", "jobsearch")
HOOK = os.path.join(PLUGIN, "hooks", "session_start.py")
FIXTURE = os.path.join(ROOT, "evals", "fixtures", "sample-datadir")
sys.path.insert(0, os.path.join(PLUGIN, "hooks"))
import session_start  # noqa: E402


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class ContextCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = os.path.realpath(self.tmp.name)

    def data_dir(self, chat="en", start=True):
        d = os.path.join(self.base, "data")
        write(os.path.join(d, "jobsearch.config.yaml"), f'language: {{chat: "{chat}"}}\n')
        write(os.path.join(d, "TODO.md"), "- [ ] one\n- [x] done\n- [ ] two\n")
        if start:
            write(os.path.join(d, "START_HERE.md"), "Overview text")
        return d

    def test_silent_outside_data_dir(self):
        d = self.data_dir()
        proj = os.path.join(self.base, "other")
        os.mkdir(proj)
        self.assertIsNone(session_start.context(proj, {"JOBSEARCH_DATA_DIR": d}))
        self.assertIsNone(session_start.context(proj, {}))

    def test_marker_project_speaks(self):
        d = self.data_dir()
        proj = os.path.join(self.base, "proj")
        write(os.path.join(proj, ".jobsearch-data"), d)
        self.assertIn("Overview text", session_start.context(proj, {})["hookSpecificOutput"]["additionalContext"])

    def test_silent_when_project_has_own_hook(self):
        d = self.data_dir()
        for name in ("settings.json", "settings.local.json"):
            p = os.path.join(d, ".claude", name)
            write(p, json.dumps({"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "x"}]}]}}))
            self.assertIsNone(session_start.context(d, {}))
            os.remove(p)
        write(os.path.join(d, ".claude", "settings.json"), json.dumps({"hooks": {"Stop": []}}))
        self.assertIsNotNone(session_start.context(d, {}))
        write(os.path.join(d, ".claude", "settings.json"), "{not json")
        self.assertIsNotNone(session_start.context(d, {}))

    def test_context_in_data_dir(self):
        out = session_start.context(FIXTURE, {})
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("Overview of the sample job search", ctx)
        self.assertIn("open items (3)", ctx)
        self.assertIn("- [ ] Review the ranked vacancies", ctx)
        self.assertNotIn("Update the master CV", ctx)
        self.assertIn("(3 open", out["systemMessage"])
        self.assertIn("answer in en", ctx)

    def test_no_language_line_when_chat_empty(self):
        d = self.data_dir(chat="")
        ctx = session_start.context(d, {})["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn("answer in", ctx)
        self.assertNotIn("language", ctx.lower())

    def test_missing_files_reported(self):
        d = self.data_dir(start=False)
        os.remove(os.path.join(d, "TODO.md"))
        ctx = session_start.context(d, {})["hookSpecificOutput"]["additionalContext"]
        self.assertIn("(missing: START_HERE.md)", ctx)
        self.assertIn("(missing: TODO.md)", ctx)

    def test_bad_config_is_silent(self):
        d = self.data_dir()
        write(os.path.join(d, "jobsearch.config.yaml"), "- just\n- a list\n")
        self.assertIsNone(session_start.context(d, {}))


class MainCase(unittest.TestCase):
    def run_hook(self, stdin, cwd, env_extra=None):
        env = {k: v for k, v in os.environ.items() if k != "JOBSEARCH_DATA_DIR"}
        env.update(env_extra or {})
        return subprocess.run([sys.executable, "-B", HOOK], input=stdin, capture_output=True, text=True,
                              cwd=cwd, env=env)

    def test_stdin_cwd_used(self):
        with tempfile.TemporaryDirectory() as other:
            r = self.run_hook(json.dumps({"cwd": FIXTURE}), other)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("SessionStart", json.loads(r.stdout)["hookSpecificOutput"]["hookEventName"])

    def test_defensive_stdin_and_silence(self):
        with tempfile.TemporaryDirectory() as other:
            for stdin in ("", "not json", "[1]", json.dumps({"cwd": 5}), json.dumps({"cwd": other})):
                r = self.run_hook(stdin, other)
                self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""), stdin)
        r = self.run_hook("", FIXTURE)  # no cwd in input: falls back to os.getcwd()
        self.assertEqual(r.returncode, 0)
        self.assertIn("additionalContext", r.stdout)

    def test_main_never_raises(self):
        with mock.patch.object(session_start, "context", side_effect=RuntimeError("boom")), \
                mock.patch("sys.stdout", new=io.StringIO()) as out:
            self.assertEqual(session_start.main(io.StringIO("{}"), {}), 0)
        self.assertEqual(out.getvalue(), "")


class HooksJsonCase(unittest.TestCase):
    def test_hooks_json(self):
        with open(os.path.join(PLUGIN, "hooks", "hooks.json"), encoding="utf-8") as f:
            h = json.load(f)
        entry = h["hooks"]["SessionStart"][0]
        self.assertEqual(entry["matcher"], "startup|resume|clear|compact")
        self.assertEqual(entry["hooks"][0]["type"], "command")
        self.assertEqual(entry["hooks"][0]["command"], 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/session_start.py"')


class RobotsCase(unittest.TestCase):
    def test_script_present_and_usage(self):
        p = os.path.join(PLUGIN, "scripts", "robots_check.py")
        self.assertTrue(os.path.isfile(p))
        r = subprocess.run([sys.executable, "-B", p], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)  # argparse usage error, no network


if __name__ == "__main__":
    unittest.main()
