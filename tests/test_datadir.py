import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "plugins", "jobsearch", "scripts")
sys.path.insert(0, SCRIPTS)
import datadir  # noqa: E402

FIXTURE = os.path.join(ROOT, "evals", "fixtures", "sample-datadir")
TEMPLATE = os.path.join(ROOT, "plugins", "jobsearch", "reference", "config.template.yaml")


def keys(d):
    return {k: keys(v) for k, v in d.items()} if isinstance(d, dict) else None


class ResolveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.t = os.path.realpath(self.tmp.name)

    def test_env_wins(self):
        self.assertEqual(datadir.resolve_data_dir(self.t, {"JOBSEARCH_DATA_DIR": FIXTURE}), FIXTURE)

    def test_marker_file(self):
        with open(os.path.join(self.t, ".jobsearch-data"), "w") as f:
            f.write(FIXTURE + "\n")
        self.assertEqual(datadir.resolve_data_dir(self.t, {}), FIXTURE)

    def test_config_in_root(self):
        open(os.path.join(self.t, "jobsearch.config.yaml"), "w").close()
        self.assertEqual(datadir.resolve_data_dir(self.t, {}), self.t)

    def test_nothing_raises(self):
        with self.assertRaises(datadir.DataDirError) as cm:
            datadir.resolve_data_dir(self.t, {})
        self.assertIn("JOBSEARCH_DATA_DIR", str(cm.exception))

    def test_missing_env_dir_raises_and_creates_nothing(self):
        nope = os.path.join(self.t, "nope")
        with self.assertRaises(datadir.DataDirError):
            datadir.resolve_data_dir(self.t, {"JOBSEARCH_DATA_DIR": nope})
        self.assertFalse(os.path.exists(nope))

    def test_config_env_override(self):
        other = os.path.join(self.t, "other.yaml")
        self.assertEqual(datadir.config_path(FIXTURE, {"JOBSEARCH_CONFIG": other}), other)

    def test_config_path_default_and_json_fallback(self):
        self.assertEqual(datadir.config_path(self.t, {}), os.path.join(self.t, "jobsearch.config.yaml"))
        j = os.path.join(self.t, "jobsearch.config.json")
        with open(j, "w") as f:
            f.write("{}")
        self.assertEqual(datadir.config_path(self.t, {}), j)


class ParserTest(unittest.TestCase):
    def test_yaml_subset(self):
        text = 'a: {b: 1, c: [x, "y z"]}\nlist:\n  - {k: v}\n  - plain\nflag: false # c'
        self.assertEqual(datadir.parse_yaml_subset(text), {
            "a": {"b": 1, "c": ["x", "y z"]}, "list": [{"k": "v"}, "plain"], "flag": False})

    def test_nested_blocks_and_hash_in_quotes(self):
        text = 'top:\n  inner:\n    - one\n    - "two # not comment"\n  n: 7\nempty: []\n'
        self.assertEqual(datadir.parse_yaml_subset(text), {
            "top": {"inner": ["one", "two # not comment"], "n": 7}, "empty": []})


    def test_odd_dash_spacing_is_an_error_not_silent_loss(self):
        with self.assertRaises(ValueError):
            datadir.parse_yaml_subset("a:\n  -   x: 1\n      y: 2\n")

    def test_apostrophe_inside_a_word_is_not_a_quote(self):
        text = 'never_claim: [{pattern: "lead", why: user\'s never led}, {pattern: "x", why: y}]\n'
        self.assertEqual(datadir.parse_yaml_subset(text), {"never_claim": [
            {"pattern": "lead", "why": "user's never led"}, {"pattern": "x", "why": "y"}]})
        self.assertEqual(datadir.parse_yaml_subset("salutation: Dear team's lead  # comment\n"),
                         {"salutation": "Dear team's lead"})
        self.assertEqual(datadir.parse_yaml_subset("k: it's: fine\n"), {"k": "it's: fine"})
        # a quote at the start of a token still opens a string
        self.assertEqual(datadir.parse_yaml_subset("a: ['x, y', \"z # w\"]  # c\n"), {"a": ["x, y", "z # w"]})

    def test_block_map_in_list_item(self):
        self.assertEqual(datadir.parse_yaml_subset("a:\n  - x: 1\n    y: 2\n  - z: 3\n"),
                         {"a": [{"x": 1, "y": 2}, {"z": 3}]})


class ConfigTest(unittest.TestCase):
    def test_bare_section_keeps_defaults(self):
        with tempfile.TemporaryDirectory() as t:
            with open(os.path.join(t, "jobsearch.config.yaml"), "w") as f:
                f.write("paths:\nthresholds:\n")
            cfg = datadir.load_config(t, {})
        self.assertEqual(cfg["thresholds"], datadir.DEFAULTS["thresholds"])
        self.assertEqual(datadir.data_path(cfg, t, "tracker"), os.path.join(t, "tracker/vacancies.csv"))

    def test_defaults_merge(self):
        cfg = datadir.load_config(FIXTURE, {})
        self.assertEqual(cfg["thresholds"], {"apply": 75, "decline": 65})
        self.assertEqual(cfg["match_weights"]["must_have"], 60)
        self.assertEqual(cfg["identity"]["full_name"], "Jordan Example")
        self.assertNotIn("_warnings", cfg)

    def test_missing_file_gives_defaults_and_warning(self):
        with tempfile.TemporaryDirectory() as t:
            cfg = datadir.load_config(t, {})
        self.assertEqual(cfg["thresholds"], datadir.DEFAULTS["thresholds"])
        self.assertTrue(cfg["_warnings"])

    def test_defaults_not_mutated(self):
        cfg = datadir.load_config(FIXTURE, {})
        self.assertEqual(datadir.DEFAULTS["thresholds"]["apply"], 80)
        cfg["thresholds"]["apply"] = 1
        self.assertEqual(datadir.DEFAULTS["thresholds"]["apply"], 80)

    def test_data_path(self):
        cfg = datadir.load_config(FIXTURE, {})
        self.assertEqual(datadir.data_path(cfg, FIXTURE, "tracker"), os.path.join(FIXTURE, "tracker/vacancies.csv"))

    def test_alt_flow_off_by_default(self):
        for k in ("scanner", "apply_assistant", "reply_watch"):
            self.assertIs(datadir.DEFAULTS["alt_flow"][k]["enabled"], False)

    def test_template_matches_defaults(self):
        with open(TEMPLATE, encoding="utf-8") as f:
            parsed = datadir.parse_yaml_subset(f.read())
        self.assertEqual(keys(parsed), keys(datadir.DEFAULTS))

    def test_unknown_keys(self):
        self.assertEqual(datadir.unknown_keys({"thresholds": {"apply": 1}, "restricted": 1}, datadir.DEFAULTS), ["restricted"])
        self.assertEqual(datadir.unknown_keys({"thresholds": {"bogus": 1}}, datadir.DEFAULTS), ["thresholds.bogus"])
        self.assertEqual(datadir.unknown_keys({"letters": {"base_letters": [{"anything": 1}]}}, datadir.DEFAULTS), [])


class CliTest(unittest.TestCase):
    def run_cli(self, *args, env=None):
        e = {k: v for k, v in os.environ.items() if not k.startswith("JOBSEARCH_")}
        e.update(env or {})
        return subprocess.run([sys.executable, "-B", os.path.join(SCRIPTS, "datadir.py"), *args],
                              capture_output=True, text=True, env=e, cwd=ROOT)

    def test_validate_template_ok(self):
        self.assertEqual(self.run_cli("validate", TEMPLATE).returncode, 0)

    def test_validate_fixture_ok_via_env(self):
        self.assertEqual(self.run_cli("validate", env={"JOBSEARCH_DATA_DIR": FIXTURE}).returncode, 0)

    def test_validate_unknown_key_fails(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "bad.yaml")
            with open(p, "w") as f:
                f.write("thresholds: {apply: 80, nope: 1}\n")
            r = self.run_cli("validate", p)
        self.assertEqual(r.returncode, 1)
        self.assertIn("thresholds.nope", r.stdout + r.stderr)

    def test_show(self):
        r = self.run_cli("show", env={"JOBSEARCH_DATA_DIR": FIXTURE})
        self.assertEqual(r.returncode, 0)
        self.assertIn(FIXTURE, r.stdout)

    def test_show_prints_absolute_paths(self):
        r = self.run_cli("show", env={"JOBSEARCH_DATA_DIR": FIXTURE})
        self.assertEqual(r.returncode, 0, r.stdout)
        lines = r.stdout.splitlines()
        self.assertIn(f"  tracker: {os.path.join(FIXTURE, 'tracker', 'vacancies.csv')}", lines)
        self.assertIn(f"  reports: {os.path.join(FIXTURE, 'reports')}", lines)
        self.assertIn(f"  facts: {os.path.join(FIXTURE, 'profile', 'facts.md')}", lines)
        for key in datadir.DEFAULTS["paths"]:
            self.assertTrue(any(l.startswith(f"  {key}:") for l in lines), key)

    def test_validate_rejects_non_mapping_top_level(self):
        with tempfile.TemporaryDirectory() as t:
            for name, body in (("list.yaml", "- a\n- b\n"), ("scalar.yaml", "just text\n"), ("list.json", "[1, 2]")):
                with self.subTest(name=name):
                    p = os.path.join(t, name)
                    with open(p, "w") as f:
                        f.write(body)
                    r = self.run_cli("validate", p)
                    self.assertEqual(r.returncode, 1, r.stdout)
                    self.assertIn("mapping", r.stdout)


if __name__ == "__main__":
    unittest.main()
