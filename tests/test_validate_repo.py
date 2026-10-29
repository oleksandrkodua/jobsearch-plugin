import os
import subprocess
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def clean_env():
    """The validator must never read the owner's private config: drop every JOBSEARCH_* variable."""
    return {k: v for k, v in os.environ.items() if not k.startswith("JOBSEARCH_")}


class ValidatorTest(unittest.TestCase):
    def test_validator_passes_on_repo(self):
        r = subprocess.run([sys.executable, "-B", os.path.join(ROOT, "evals", "validate_repo.py")],
                           capture_output=True, text=True, cwd=ROOT, env=clean_env())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        fails = [l for l in r.stdout.splitlines() if l.startswith("FAIL")]
        self.assertEqual(fails, [], "\n".join(fails))

    def test_owner_env_does_not_leak_into_validator_runs(self):
        sentinel = os.path.join(ROOT, "no-such-dir", "sentinel-private-config.yaml")
        with mock.patch.dict(os.environ, {"JOBSEARCH_CONFIG": sentinel, "JOBSEARCH_DATA_DIR": sentinel}):
            self.test_validator_passes_on_repo()
            r = subprocess.run([sys.executable, "-B", os.path.join(ROOT, "evals", "validate_repo.py")],
                               capture_output=True, text=True, cwd=ROOT, env=clean_env())
        self.assertIn("WARN  publish gate skipped (no private config)", r.stdout)
        self.assertNotIn("sentinel", r.stdout + r.stderr)


class Check3cPointerTest(unittest.TestCase):
    """A '(use X)' pointer resolves to a skill folder or a command file; unknown names FAIL."""

    def _run(self, pointer):
        import shutil, tempfile
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "evals"))
            shutil.copy(os.path.join(ROOT, "evals", "validate_repo.py"), os.path.join(tmp, "evals"))
            shutil.copytree(os.path.join(ROOT, "plugins"), os.path.join(tmp, "plugins"),
                            ignore=shutil.ignore_patterns("__pycache__"))
            sp = os.path.join(tmp, "plugins", "jobsearch", "skills", "cover-letter", "SKILL.md")
            with open(sp, encoding="utf-8") as f:
                text = f.read()
            self.assertIn("(use outcome)", text)
            with open(sp, "w", encoding="utf-8") as f:
                f.write(text.replace("(use outcome)", f"(use {pointer})", 1))
            r = subprocess.run([sys.executable, "-B", os.path.join(tmp, "evals", "validate_repo.py")],
                               capture_output=True, text=True, cwd=tmp, env=clean_env())
            return [l for l in r.stdout.splitlines() if "named in its description" in l]

    def test_existing_command_passes(self):
        lines = self._run("outcome")
        self.assertTrue(lines and all(l.startswith("PASS") for l in lines), lines)

    def test_unknown_name_fails_and_is_named(self):
        lines = self._run("no-such-thing")
        self.assertTrue(any(l.startswith("FAIL") and "no-such-thing" in l for l in lines), lines)


class Check15ScriptPathTest(unittest.TestCase):
    """A scripts/<name>.py path in commands and skills must carry ${CLAUDE_PLUGIN_ROOT}/ or ${CLAUDE_SKILL_DIR}/."""

    def _run(self, line):
        import shutil, tempfile
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "evals"))
            shutil.copy(os.path.join(ROOT, "evals", "validate_repo.py"), os.path.join(tmp, "evals"))
            shutil.copytree(os.path.join(ROOT, "plugins"), os.path.join(tmp, "plugins"),
                            ignore=shutil.ignore_patterns("__pycache__"))
            cp = os.path.join(tmp, "plugins", "jobsearch", "commands", "outcome.md")
            with open(cp, "a", encoding="utf-8") as f:
                f.write("\n" + line + "\n")
            r = subprocess.run([sys.executable, "-B", os.path.join(tmp, "evals", "validate_repo.py")],
                               capture_output=True, text=True, cwd=tmp, env=clean_env())
            return [l for l in r.stdout.splitlines() if "bare relative" in l]

    def test_bare_relative_path_fails_with_file_and_line(self):
        lines = self._run("`python3 scripts/datadir.py validate x`")
        self.assertTrue(any(l.startswith("FAIL") and "outcome.md:" in l for l in lines), lines)

    def test_plugin_root_prefix_passes(self):
        lines = self._run('`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/datadir.py" validate x`')
        self.assertTrue(lines and all(l.startswith("PASS") for l in lines), lines)

    def test_skill_dir_prefix_passes(self):
        lines = self._run('`python3 "${CLAUDE_SKILL_DIR}/scripts/datadir.py" validate x`')
        self.assertTrue(lines and all(l.startswith("PASS") for l in lines), lines)

    def test_bare_reference_path_fails(self):
        lines = self._run("Read `reference/hard-rules.md` first.")
        self.assertTrue(any(l.startswith("FAIL") and "outcome.md:" in l for l in lines), lines)

    def test_bare_presets_path_fails(self):
        lines = self._run("Copy `presets/qa/preset.yaml` to the data dir.")
        self.assertTrue(any(l.startswith("FAIL") and "outcome.md:" in l for l in lines), lines)

    def test_anchored_reference_and_presets_pass(self):
        lines = self._run('Read "${CLAUDE_PLUGIN_ROOT}/reference/hard-rules.md"; copy "${CLAUDE_PLUGIN_ROOT}/presets/qa/preset.yaml".')
        self.assertTrue(lines and all(l.startswith("PASS") for l in lines), lines)

    def test_skill_dir_reference_passes(self):
        lines = self._run('Read "${CLAUDE_SKILL_DIR}/reference/x.md".')
        self.assertTrue(lines and all(l.startswith("PASS") for l in lines), lines)


class BareScriptNameTest(unittest.TestCase):
    """A runnable `python3 <name>.py` with a bare script name (no anchored path) FAILs."""

    def _runb(self, line):
        self._filter = "bare script name"
        return self._run(line)

    def _run(self, line):  # same copy-and-run, other summary line
        import shutil, tempfile
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "evals"))
            shutil.copy(os.path.join(ROOT, "evals", "validate_repo.py"), os.path.join(tmp, "evals"))
            shutil.copytree(os.path.join(ROOT, "plugins"), os.path.join(tmp, "plugins"),
                            ignore=shutil.ignore_patterns("__pycache__"))
            with open(os.path.join(tmp, "plugins", "jobsearch", "commands", "outcome.md"), "a", encoding="utf-8") as f:
                f.write("\n" + line + "\n")
            r = subprocess.run([sys.executable, "-B", os.path.join(tmp, "evals", "validate_repo.py")],
                               capture_output=True, text=True, cwd=tmp, env=clean_env())
            return [l for l in r.stdout.splitlines() if getattr(self, "_filter", "bare relative") in l]

    def test_bare_runnable_script_fails(self):
        for line in ("Run `python3 tracker_edit.py check`.", 'Run `python3 -B "robots_check.py" <url>`.',
                     "python3 datadir.py show"):
            with self.subTest(line=line):
                lines = self._runb(line)
                self.assertTrue(any(l.startswith("FAIL") and "outcome.md:" in l for l in lines), lines)

    def test_anchored_runnable_script_passes(self):
        for line in ('Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/tracker_edit.py" check`.',
                     'Run `python3 "${CLAUDE_SKILL_DIR}/scripts/ats_technical_score.py" x.pdf`.',
                     "Prose naming `tracker_edit.py` is fine."):
            with self.subTest(line=line):
                lines = self._runb(line)
                self.assertTrue(lines and all(l.startswith("PASS") for l in lines), lines)


if __name__ == "__main__":
    unittest.main()
