import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "plugins", "jobsearch", "scripts")
PRESET_DIR = os.path.join(ROOT, "plugins", "jobsearch", "presets", "qa")
sys.path.insert(0, SCRIPTS)
import datadir  # noqa: E402

PERSONA = ["Jordan Example", "jordan.example@example.com", "+1 555 0100", "@jordan_example", "Example Corp"]


class QaPresetTest(unittest.TestCase):
    def test_qa_preset_merges(self):
        with tempfile.TemporaryDirectory() as t:
            cfg_path = os.path.join(t, "jobsearch.config.yaml")
            with open(os.path.join(PRESET_DIR, "preset.yaml"), encoding="utf-8") as src, \
                    open(cfg_path, "w", encoding="utf-8") as dst:
                dst.write(src.read())
            cfg = datadir.load_config(t, {})
            self.assertTrue(cfg["honesty"]["tool_dictionary"])
            self.assertTrue(cfg["honesty"]["restricted_tools"]["pattern"])
            self.assertTrue(cfg["honesty"]["restricted_tools"]["disclaimer_pattern"])
            self.assertIs(cfg["honesty"]["restricted_tools"]["cv_forbidden"], True)
            self.assertTrue([b for b in cfg["blockers"] if b.get("type") == "keyword"])
            self.assertTrue(cfg["letters"]["base_letters"])
            r = subprocess.run([sys.executable, "-B", os.path.join(SCRIPTS, "datadir.py"), "validate", cfg_path],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_preset_identity_is_empty(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "jobsearch.config.yaml")
            with open(os.path.join(PRESET_DIR, "preset.yaml"), encoding="utf-8") as f, open(p, "w", encoding="utf-8") as g:
                g.write(f.read())
            ident = datadir.load_config(t, {})["identity"]
            self.assertEqual(ident["full_name"], "")
            self.assertEqual(ident["emails"], [])
            self.assertEqual(ident["phones"], [])

    def test_preset_has_no_personal_values(self):
        files = [os.path.join(dp, f) for dp, _, fs in os.walk(PRESET_DIR) for f in fs]
        self.assertTrue(files)
        for p in files:
            with open(p, encoding="utf-8") as fh:
                text = fh.read().lower()
            for v in PERSONA:
                self.assertNotIn(v.lower(), text, f"{p} contains {v}")


if __name__ == "__main__":
    unittest.main()
