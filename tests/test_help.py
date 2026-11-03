import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugins", "jobsearch")
HOOK = os.path.join(PLUGIN, "hooks", "session_start.py")


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as f:
        return f.read()


CMD = read(PLUGIN, "commands", "help.md")


class HelpCommand(unittest.TestCase):
    def test_frontmatter(self):
        self.assertTrue(CMD.startswith("---\ndescription: "))
        self.assertIn("argument-hint:", CMD.split("\n---", 1)[0])

    def test_lists_from_the_plugin_and_needs_no_data_dir(self):
        self.assertIn('python3 "${CLAUDE_PLUGIN_ROOT}/hooks/session_start.py" --list', CMD)
        self.assertIn('python3 "${CLAUDE_PLUGIN_ROOT}/scripts/datadir.py" show', CMD)
        self.assertIn("/jobsearch:jobsearch-setup", CMD)
        self.assertIn("works without a data folder", CMD)

    def test_explains_the_workflow_and_hard_rules(self):
        for w in ("/jobsearch:rank", "/jobsearch:apply", "/jobsearch:outcome", "never sends, applies or submits",
                  "${CLAUDE_PLUGIN_ROOT}/reference/hard-rules.md"):
            self.assertIn(w, CMD, w)

    def test_read_only(self):
        self.assertIn("Read-only: this command changes no file", CMD)


class ListFlag(unittest.TestCase):
    def test_list_prints_every_command_without_a_data_dir(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("JOBSEARCH_")}
        with tempfile.TemporaryDirectory() as empty:
            r = subprocess.run([sys.executable, "-B", HOOK, "--list"], capture_output=True, text=True,
                               cwd=empty, env=env, stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stderr)
        cmds = sorted(f[:-3] for f in os.listdir(os.path.join(PLUGIN, "commands")) if f.endswith(".md"))
        self.assertIn("help", cmds)
        for c in cmds:
            self.assertIn(f"`/jobsearch:{c}`", r.stdout, c)
        self.assertIn("`linkedin-profile-optimizer`", r.stdout)


if __name__ == "__main__":
    unittest.main()
