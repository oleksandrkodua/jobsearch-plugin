import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_codex
import runtime

FIXTURE = ROOT / "evals" / "fixtures" / "sample-datadir"


class CodexPackage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        base = Path(cls.tmp.name)
        original = build_codex.build(base / "initial")
        # Installed caches relocate packages. No generated workflow may rely on its build location.
        cls.out = base / "relocated-marketplace"
        shutil.move(str(original), str(cls.out))
        cls.plugin = cls.out / "plugins" / "jobsearch"
        cls.env = {k: v for k, v in os.environ.items() if not k.startswith("JOBSEARCH_")}

    def run_script(self, rel, *args, data=None, configured=True):
        env = dict(self.env)
        if configured:
            env["JOBSEARCH_DATA_DIR"] = str(FIXTURE)
        return subprocess.run([sys.executable, "-B", str(self.plugin / rel), *args],
                              input=json.dumps(data) if data is not None else "", capture_output=True, text=True,
                              env=env, cwd=self.out)

    def test_package_has_no_local_tool_dirs(self):
        self.assertEqual([p for p in self.plugin.rglob(".claude")], [])

    def test_marketplace_manifest_and_all_workflows(self):
        market = json.loads((self.out / ".agents/plugins/marketplace.json").read_text())
        self.assertEqual((self.out / market["plugins"][0]["source"]["path"]).resolve(), self.plugin.resolve())
        manifest = json.loads((self.plugin / ".codex-plugin/plugin.json").read_text())
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertTrue((self.plugin / manifest["hooks"]).is_file())
        commands = {p.stem for p in (ROOT / "plugins/jobsearch/commands").glob("*.md")}
        self.assertEqual(commands, set(runtime.NAMES))
        for name in commands:
            d = self.plugin / "skills" / runtime.skill_name(name)
            text = (d / "SKILL.md").read_text()
            self.assertIn("## Codex runtime", text)
            self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", text)
            self.assertNotIn("$ARGUMENTS", text)
            self.assertEqual(len(json.loads((d / "evals/evals.json").read_text())["evals"]), 3)
        for textfile in list((self.plugin / "skills").rglob("SKILL.md")) + list((self.plugin / "reference").glob("*.md")):
            text = textfile.read_text()
            self.assertNotIn("/jobsearch:", text, str(textfile))
            self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", text, str(textfile))
            self.assertNotIn("compatibility: claude-code", text, str(textfile))
            if textfile.name == 'SKILL.md':
                front = text.split('\n---', 1)[0]
                self.assertNotIn('allowed-tools:', front)
                value = next(l.split(': ', 1)[1] for l in front.splitlines() if l.startswith('description: '))
                self.assertIsInstance(json.loads(value), str)
            self.assertNotIn('the model in Chrome', text)
        helper_readme = (self.plugin / "skills/humanizer/README.md").read_text()
        self.assertIn("$humanizer", helper_readme)
        self.assertNotIn("/plugin install", helper_readme)
        self.assertTrue((self.plugin / "skills/humanizer/README.upstream.md").is_file())
        self.assertFalse((self.plugin / "hooks/hooks.json").exists())
        readme = (self.out / "README.md").read_text()
        for title in ("## Build and install", "## Behavior in Codex", "## Check after installation"):
            self.assertIn(title, readme)
        self.assertFalse((self.plugin / "profile").exists())
        self.assertFalse((self.plugin / "tracker").exists())

    def test_create_only_output(self):
        before = (self.out / "README.md").read_bytes()
        with self.assertRaises(ValueError):
            build_codex.build(self.out)
        self.assertEqual((self.out / "README.md").read_bytes(), before)

    def test_help_and_missing_setup_use_codex_names_after_relocation(self):
        r = self.run_script("hooks/session_start.py", "--list", configured=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("$jobsearch-help", r.stdout)
        self.assertIn("$jobsearch-setup", r.stdout)
        self.assertIn("update", r.stdout)
        self.assertNotIn("/jobsearch:", r.stdout)
        self.assertNotIn("Claude", r.stdout)
        r = self.run_script("scripts/datadir.py", "show", configured=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("$jobsearch-setup", r.stdout)
        self.assertNotIn("/jobsearch:", r.stdout)
        r = self.run_script("scripts/onboarding.py", "status")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("$jobsearch-setup update", r.stdout)
        self.assertNotIn("/jobsearch:", r.stdout)
        r = self.run_script("scripts/portal_scan.py", "run")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("$jobsearch-scan approve", r.stderr)
        self.assertNotIn("/jobsearch:", r.stderr)

    def test_native_patch_and_ask_are_denied_but_draft_is_allowed(self):
        for path in ("tracker/vacancies.csv", "profile/facts.md"):
            event = {"cwd": str(FIXTURE), "tool_name": "apply_patch", "tool_input": {
                "command": f"*** Begin Patch\n*** Update File: {path}\n@@\n-x\n+y\n*** End Patch"}}
            r = self.run_script("hooks/codex_guard.py", data=event)
            self.assertEqual(r.returncode, 0, r.stderr)
            decision = json.loads(r.stdout)["hookSpecificOutput"]
            self.assertEqual(decision["permissionDecision"], "deny")
            self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", decision["permissionDecisionReason"])
        event["tool_input"]["command"] = "*** Begin Patch\n*** Add File: applications/example/draft.md\n+Draft\n*** End Patch"
        r = self.run_script("hooks/codex_guard.py", data=event)
        self.assertEqual((r.returncode, r.stdout), (0, ""), r.stderr)

    def test_unconfigured_heredoc_with_apostrophe_is_not_blocked(self):
        with tempfile.TemporaryDirectory() as other:
            command = "cat > spec.md <<EOF\nIt" + chr(39) + "s a specification.\nEOF"
            event = {"cwd": other, "tool_name": "Bash", "tool_input": {"command": command}}
            result = self.run_script("hooks/codex_guard.py", data=event, configured=False)
            self.assertEqual((result.returncode, result.stdout), (0, ""), result.stderr)
            result = self.run_script("hooks/codex_guard.py", data=event, configured=True)
            self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_patch_move_target_checked_and_full_batch_denied(self):
        event = {"cwd": str(FIXTURE), "tool_name": "apply_patch", "tool_input": {"command":
            "*** Begin Patch\n*** Update File: applications/draft.md\n*** Move to: tracker/vacancies.csv\n@@\n-x\n+y\n*** End Patch"}}
        r = self.run_script("hooks/codex_guard.py", data=event)
        self.assertEqual(json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_query_preflight_exact_safe_and_private(self):
        event = {"cwd": str(FIXTURE), "tool_name": "WebSearch", "tool_input": {"query": "QA remote jobs"}}
        r = self.run_script("hooks/codex_guard.py", "--preflight", data=event)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        event["tool_input"]["query"] = "jordan.example@example.com jobs"
        r = self.run_script("hooks/codex_guard.py", "--preflight", data=event)
        self.assertEqual(r.returncode, 1)
        self.assertIn("DENIED", r.stdout)
        self.assertNotIn("jordan.example@example.com", r.stdout)
        r = self.run_script("hooks/codex_guard.py", "--preflight", data=event, configured=False)
        self.assertEqual(r.returncode, 1)

    def test_final_sends_and_unknown_connectors_remain_denied_in_generated_package(self):
        for tool, reason in (("mcp__gmail__send_message", "hard rule 1"),
                             ("mcp__artifact_session__js", "Unclassified connector")):
            event = {"cwd": str(FIXTURE), "tool_name": tool, "tool_input": {"method": "GET"}}
            result = self.run_script("hooks/codex_guard.py", data=event)
            decision = json.loads(result.stdout)["hookSpecificOutput"]
            self.assertEqual(decision["permissionDecision"], "deny")
            self.assertIn(reason, decision["permissionDecisionReason"])
        event["tool_name"] = "mcp__notion__search"
        event["tool_input"] = {"query": "QA jobs"}
        result = self.run_script("hooks/codex_guard.py", data=event)
        self.assertEqual((result.returncode, result.stdout), (0, ""), result.stderr)

    def test_shared_commands_render_for_both_programs(self):
        source = "Use /jobsearch:rank or /apply tune; read vacancies/ranked/ and /interview/notes."
        converted = runtime.render_text(source, codex=True)
        self.assertIn("$jobsearch-rank", converted)
        self.assertIn("$jobsearch-apply tune", converted)
        self.assertIn("vacancies/ranked/", converted)
        self.assertIn("/interview/notes", converted)
        back = runtime.render_text(converted, codex=False)
        self.assertIn("/jobsearch:rank", back)
        self.assertIn("/jobsearch:apply tune", back)


if __name__ == "__main__":
    unittest.main()
