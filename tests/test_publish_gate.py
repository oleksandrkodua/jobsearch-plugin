import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "plugins", "jobsearch", "scripts")
GATE = os.path.join(SCRIPTS, "publish_gate.py")
FIXTURE_CFG = os.path.join(ROOT, "evals", "fixtures", "sample-datadir", "jobsearch.config.yaml")
sys.path.insert(0, SCRIPTS)

# synthetic persona (same as the fixture config)
NAME, SHORT = "Jordan Example", "Jordan"
EMAIL = "jordan.example@example.com"
PHONE = "+1 555 0100"
IDENTITY = {"full_name": NAME, "short_name": SHORT, "emails": [EMAIL], "phones": [PHONE],
            "handles": ["@jordan_example"], "extra_private_terms": ["Example Corp"]}
NEUTRAL = ["-c", "user.name=Neutral Dev", "-c", "user.email=dev@invalid.test", "-c", "commit.gpgsign=false"]


def git(repo, *args, extra=()):
    r = subprocess.run(["git", *NEUTRAL, *extra, "-C", repo, *args], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


class GateCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = os.path.realpath(self.tmp.name)
        self.repo = os.path.join(base, "repo")
        os.mkdir(self.repo)
        git(self.repo, "init", "-q")
        self.cfg = os.path.join(base, "private.json")  # outside the repo
        self.write_cfg(IDENTITY)

    def write_cfg(self, identity):
        with open(self.cfg, "w", encoding="utf-8") as f:
            json.dump({"identity": identity}, f)

    def put(self, rel, text):
        p = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)

    def repo_reset(self):
        # fresh repo for the next subtest so history from earlier variants does not leak in
        import shutil
        shutil.rmtree(self.repo)
        os.mkdir(self.repo)
        git(self.repo, "init", "-q")

    def put_bytes(self, rel, data):
        p = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(p) or self.repo, exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)

    def commit(self, msg="c", extra=()):
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", msg, extra=extra)

    def gate(self, cfg="default", env_extra=None, args=()):
        env = {k: v for k, v in os.environ.items() if not k.startswith("JOBSEARCH_")}
        env.update(env_extra or {})
        a = [sys.executable, "-B", GATE, "--repo", self.repo]
        if cfg == "default":
            a += ["--config", self.cfg]
        elif cfg:
            a += ["--config", cfg]
        return subprocess.run(a + list(args), capture_output=True, text=True, env=env)


class TreeTest(GateCase):
    def test_clean_repo_passes(self):
        self.put("README.md", "A neutral engine.\nVersion 1.2.3 released 2026-10-27 build 20261027.\n")
        self.commit()
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PUBLISH GATE: PASS", r.stdout)

    def test_name_in_file_fails(self):
        self.put("notes.md", f"{NAME} wrote this\n")
        self.commit()
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stdout, r"notes\.md:1\b")

    def test_untracked_file_is_scanned(self):
        self.put("a.txt", "ok\n")
        self.commit()
        self.put("untracked.txt", f"x\n{NAME}\n")
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("untracked.txt:2", r.stdout)

    def test_phone_variants_fail(self):
        variants = ["+1 555 0100", "1-555-0100", "15550100", "555.0100", "(555) 0100", "555 0100", "+15550100"]
        for i, v in enumerate(variants):
            with self.subTest(v=v):
                self.repo_reset()
                self.put("p.txt", f"call {v} now\n")
                self.commit()
                r = self.gate()
                self.assertEqual(r.returncode, 1, v)
                self.assertIn("p.txt:1", r.stdout)

    def test_phone_no_false_positive_on_dates_and_versions(self):
        self.put("n.txt", "2026-10-27 v1.5.5 build 5550 and 0100 id 20261027 +1 555 0199 (555) 1000\n")
        self.commit()
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_email_case_insensitive(self):
        self.put("m.txt", EMAIL.upper() + "\n")
        self.commit()
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("m.txt:1", r.stdout)

    def test_email_local_part_hit_and_whole_word_only(self):
        self.put("a.txt", "user jordan.example logged in\n")
        self.put("b.txt", "xjordan.examplex is not a hit\n")
        self.commit()
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("a.txt:1", r.stdout)
        self.assertNotIn("b.txt", r.stdout)

    def test_masked_value_never_printed_raw(self):
        self.put("a.txt", f"{NAME} {EMAIL} {PHONE}\n")
        self.commit()
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        for raw in (NAME, EMAIL, "jordan.example", PHONE, "5550100"):
            self.assertNotIn(raw.lower(), r.stdout.lower())
        self.assertIn("J***n", r.stdout)

    def test_secret_looking_string_fails(self):
        self.put("s.txt", "key AKIA" + "0123456789ABCDEF" + "\n")
        self.commit()
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("s.txt:1", r.stdout)
        self.assertIn("secret", r.stdout)

    def test_data_dir_path_string_fails(self):
        d = "/srv/someone/private-jobs-data"
        self.put("doc.md", f"see {d}/tracker\n")
        self.commit()
        r = self.gate(env_extra={"JOBSEARCH_DATA_DIR": d})
        self.assertEqual(r.returncode, 1)
        self.assertIn("doc.md:1", r.stdout)
        self.assertNotIn("private-jobs-data", r.stdout)
        self.assertEqual(self.gate().returncode, 0)  # env unset: that kind is skipped

    def test_root_private_folders_fail_fixture_subfolders_do_not(self):
        self.put("evals/fixtures/x/tracker/vacancies.csv", "id\n")
        self.put("evals/fixtures/x/profile/facts.md", "f\n")
        self.commit()
        self.assertEqual(self.gate().returncode, 0)
        for folder in ("tracker", "applications", "profile"):
            with self.subTest(folder=folder):
                self.put(f"{folder}/a.txt", "x\n")
                r = self.gate()
                self.assertEqual(r.returncode, 1)
                self.assertIn(folder + "/", r.stdout)
                os.remove(os.path.join(self.repo, folder, "a.txt"))
                os.rmdir(os.path.join(self.repo, folder))
        os.mkdir(os.path.join(self.repo, "tracker"))  # empty folder is fine
        self.assertEqual(self.gate().returncode, 0)

    def test_phone_slash_plus_underscore_separators(self):
        for v in ("+1/555/0100", "1_555_0100", "1+555+0100"):
            with self.subTest(v=v):
                self.repo_reset()
                self.put("p.txt", f"x {v} y\n")
                self.commit()
                self.assertEqual(self.gate().returncode, 1, v)

    def test_scalar_identity_values_are_not_split(self):
        self.write_cfg({"phones": PHONE, "emails": EMAIL})
        self.put("p.txt", f"call {PHONE}\n")
        self.commit()
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_non_list_identity_value_is_config_error(self):
        self.put("a.txt", "x\n")
        self.commit()
        for bad in ({"phones": 5}, {"emails": {"a": 1}}, {"handles": [["x"]]}):
            with self.subTest(bad=bad):
                self.write_cfg(bad)
                r = self.gate()
                self.assertEqual(r.returncode, 3, r.stdout)

    def test_pattern_less_identity_never_passes(self):
        self.write_cfg({"full_name": "x"})  # too short to make a pattern
        self.put("a.txt", "x\n")
        self.commit()
        self.assertEqual(self.gate().returncode, 2)

    def test_bare_handle_hit(self):
        self.put("a.md", "see github.com/jordan_example/repo\n")
        self.commit()
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_bad_repo_is_error_not_pass(self):
        r = subprocess.run([sys.executable, "-B", GATE, "--repo", os.path.join(self.tmp.name, "nope"), "--config", self.cfg],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 3)
        plain = os.path.join(self.tmp.name, "plain")
        os.mkdir(plain)
        r = subprocess.run([sys.executable, "-B", GATE, "--repo", plain, "--config", self.cfg], capture_output=True, text=True,
                           env={**os.environ, "GIT_CEILING_DIRECTORIES": self.tmp.name})
        self.assertEqual(r.returncode, 3, r.stdout)
        self.assertNotIn("PASS", r.stdout)

    def test_no_raw_value_anywhere_in_output(self):
        self.put(f"{NAME}.md", f"{EMAIL}\n")
        self.put("n.txt", f"{NAME} {PHONE} jordan_example\n")
        self.commit(f"by {NAME}")
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        blob = (r.stdout + r.stderr).lower()
        for raw in ("jordan", "example.com", "555", "0100", "example corp"):
            self.assertNotIn(raw, blob, raw)

    def test_utf16_file_with_name_is_a_hit(self):
        self.put_bytes("w.txt", ("hello\n" + NAME + "\n").encode("utf-16"))
        self.commit()
        r = self.gate(args=["--allow-binary", "*.txt"])
        self.assertEqual(r.returncode, 1)
        self.assertIn("w.txt", r.stdout)
        self.assertNotIn("unscanned-binary", r.stdout)

    def test_binary_file_unscanned_unless_allowed(self):
        self.put_bytes("img/logo.bin", b"\x00\x01\x02neutral\x00")
        self.commit()
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("unscanned-binary", r.stdout)
        self.assertEqual(self.gate(args=["--allow-binary", "*.bin"]).returncode, 0)

    def test_name_separator_variants(self):
        self.write_cfg({"full_name": NAME})  # no short name, so only the full-name pattern can hit
        for fn in ("Jordan-Example-CV.pdf", "jordan_example.txt", "Jordan.Example.md"):
            with self.subTest(fn=fn):
                self.repo_reset()
                self.put(fn, "neutral\n")
                self.commit()
                self.assertEqual(self.gate().returncode, 1, fn)

    def test_separator_only_term_is_ignored(self):
        self.write_cfg({"full_name": NAME, "extra_private_terms": ["--", " . ", "_"]})
        self.put("a.txt", "a -- b . c_d\n")
        self.commit()
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_name_field_must_be_a_string(self):
        self.put("a.txt", "x\n")
        self.commit()
        for bad in ({"full_name": [NAME]}, {"short_name": 5}):
            with self.subTest(bad=bad):
                self.write_cfg(bad)
                self.assertEqual(self.gate().returncode, 3)

    def test_datadir_alone_is_not_an_identity(self):
        self.write_cfg({"full_name": "J", "phones": ["12"]})
        self.put("a.txt", "x\n")
        self.commit()
        r = self.gate(env_extra={"JOBSEARCH_DATA_DIR": "/srv/someone/private-jobs-data"})
        self.assertEqual(r.returncode, 2, r.stdout)

    def test_yaml_config_works(self):
        self.put("a.txt", f"{NAME}\n")
        self.commit()
        self.assertEqual(self.gate(cfg=FIXTURE_CFG).returncode, 1)

    def test_config_via_env(self):
        self.put("a.txt", f"{NAME}\n")
        self.commit()
        self.assertEqual(self.gate(cfg=None, env_extra={"JOBSEARCH_CONFIG": self.cfg}).returncode, 1)


class DataDirCheckTest(GateCase):
    """Item 6: the data dir comes from --data-dir or JOBSEARCH_DATA_DIR; the ~/ form is matched too."""

    def test_data_dir_flag(self):
        d = "/srv/someone/private-jobs-data"
        self.put("doc.md", f"see {d}/tracker\n")
        self.commit()
        r = self.gate(args=["--data-dir", d])
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("doc.md:1", r.stdout)
        self.assertIn("data-dir check: active (", r.stdout)
        self.assertNotIn("private-jobs-data", r.stdout)

    def test_home_relative_form_matches(self):
        home = os.path.join(os.path.realpath(self.tmp.name), "home")
        d = os.path.join(home, "private-jobs-data")
        os.makedirs(d)
        self.put("doc.md", "data lives in ~/private-jobs-data/tracker\n")
        self.commit()
        for how in ("flag", "env"):
            with self.subTest(how=how):
                if how == "flag":
                    r = self.gate(args=["--data-dir", d], env_extra={"HOME": home})
                else:
                    r = self.gate(env_extra={"HOME": home, "JOBSEARCH_DATA_DIR": d})
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("doc.md:1", r.stdout)
                self.assertNotIn("private-jobs-data", r.stdout)

    def test_inactive_line(self):
        self.put("a.txt", "ok\n")
        self.commit()
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("data-dir check: inactive (no --data-dir / JOBSEARCH_DATA_DIR)", r.stdout)


class AllowTest(GateCase):
    """Item 7: publish_gate.allow skips a hit only in that exact file and only for text inside `value`."""
    LICENSE_LINE = f"Copyright (c) 2026 {NAME}"

    def write_allow(self, allow, identity=IDENTITY):
        with open(self.cfg, "w", encoding="utf-8") as f:
            json.dump({"identity": identity, "publish_gate": {"allow": allow}}, f)

    def test_name_allowed_in_license_passes(self):
        self.put("LICENSE", f"MIT License\n\n{self.LICENSE_LINE}\n")
        self.commit()
        self.write_allow([{"path": "LICENSE", "value": self.LICENSE_LINE}])
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("PUBLISH GATE: PASS", r.stdout)
        self.assertRegex(r.stdout, r"allowed: [1-9]\d* hit\(s\) via publish_gate\.allow")
        self.assertNotIn(NAME, r.stdout)
        self.assertNotIn(self.LICENSE_LINE, r.stdout)

    def test_same_name_in_readme_fails(self):
        self.put("LICENSE", f"{self.LICENSE_LINE}\n")
        self.put("README.md", f"by {NAME}\n")
        self.commit()
        self.write_allow([{"path": "LICENSE", "value": self.LICENSE_LINE}])
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("README.md:1", r.stdout)
        self.assertNotRegex(r.stdout, r"FAIL .*LICENSE")

    def test_name_in_commit_author_fails(self):
        self.put("LICENSE", f"{self.LICENSE_LINE}\n")
        self.commit(extra=["-c", f"user.name={NAME}"])
        self.write_allow([{"path": "LICENSE", "value": self.LICENSE_LINE}])
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("meta", r.stdout)

    def test_license_allow_does_not_cover_email_or_phone(self):
        self.put("LICENSE", f"{self.LICENSE_LINE} <{EMAIL}>, {PHONE}\n")
        self.commit()
        self.write_allow([{"path": "LICENSE", "value": self.LICENSE_LINE}])
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        kinds = {l.split()[1] for l in r.stdout.splitlines() if l.startswith("FAIL ")}
        self.assertIn("email", kinds)
        self.assertIn("phone", kinds)  # (the name-shaped email local part may also hit as name: still a FAIL)

    def test_dotfile_path_is_matched_exactly(self):
        self.put(".mailmap", f"{NAME}\n")
        self.commit()
        self.write_allow([{"path": "./.mailmap", "value": NAME}])
        self.assertEqual(self.gate().returncode, 0)
        self.write_allow([{"path": "mailmap", "value": NAME}])
        self.assertEqual(self.gate().returncode, 1)

    def test_file_name_hit_is_not_allowed(self):
        self.put("Jordan_Example.md", "ok\n")
        self.commit()
        self.write_allow([{"path": "Jordan_Example.md", "value": "Jordan_Example.md"}])
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_bad_allow_entry_is_config_error(self):
        self.put("a.txt", "ok\n")
        self.commit()
        for bad in ("LICENSE", [{"path": "LICENSE"}], [{"path": "", "value": "x"}], [["LICENSE", "x"]]):
            with self.subTest(bad=bad):
                self.write_allow(bad)
                self.assertEqual(self.gate().returncode, 3)


class HistoryTest(GateCase):
    def test_history_only_hit(self):
        self.put("leak.txt", f"{NAME}\n")
        self.commit("add")
        git(self.repo, "rm", "-q", "leak.txt")
        self.commit("remove")
        self.assertFalse(os.path.exists(os.path.join(self.repo, "leak.txt")))
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("leak.txt:1", r.stdout)

    def _leak_reachable_only_from(self, ref):
        self.put("a.txt", "x\n")
        self.commit("base")
        git(self.repo, "checkout", "-q", "-b", "side")
        self.put("leak.txt", f"{NAME}\n")
        self.commit("leak")
        git(self.repo, "update-ref", ref, "HEAD")
        git(self.repo, "checkout", "-q", "-")
        git(self.repo, "branch", "-q", "-D", "side")

    def test_claude_checkpoint_refs_are_skipped(self):
        self._leak_reachable_only_from("refs/time-machine/session/tool-1")
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_other_unpushed_refs_are_still_scanned(self):
        self._leak_reachable_only_from("refs/keep/old")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_merge_conflict_resolution_only_hit(self):
        self.put("f.txt", "x\n")
        self.commit("base")
        git(self.repo, "checkout", "-q", "-b", "side")
        self.put("f.txt", "side\n")
        self.commit("side")
        git(self.repo, "checkout", "-q", "-")
        self.put("f.txt", "main\n")
        self.commit("main")
        m = subprocess.run(["git", *NEUTRAL, "-C", self.repo, "merge", "side"], capture_output=True, text=True)
        self.assertNotEqual(m.returncode, 0)  # conflict, as intended
        self.put("f.txt", f"{NAME}\n")
        self.commit("merge")
        self.put("f.txt", "x\n")
        self.commit("clean")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_minus_diff_attribute_does_not_hide_content(self):
        self.put(".gitattributes", "* -diff\n")
        self.put("a.txt", f"{NAME}\n")
        self.commit("add")
        git(self.repo, "rm", "-q", "a.txt")
        self.commit("rm")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_pure_rename_to_value_name_then_delete(self):
        self.put("plain.txt", "neutral content here\nsecond line\n")
        self.commit("add")
        git(self.repo, "mv", "plain.txt", f"{NAME}.txt")
        self.commit("rename")
        git(self.repo, "rm", "-q", f"{NAME}.txt")
        self.commit("rm")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_quoted_filename_content_is_scanned(self):
        self.put('a"b.md', f"{NAME}\n")
        self.commit("add")
        git(self.repo, "rm", "-q", 'a"b.md')
        self.commit("rm")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_dashes_in_content_are_not_headers(self):
        self.put("d.txt", "-- old\n")
        self.commit("a")
        self.put("d.txt", f"++ {NAME}\n")
        self.commit("b")
        self.put("d.txt", "clean\n")
        self.commit("c")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_utf16_content_committed_then_deleted(self):
        self.put_bytes("w.txt", ("hello\n" + NAME + "\n").encode("utf-16"))
        self.commit("add")
        git(self.repo, "rm", "-q", "w.txt")
        self.commit("rm")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertNotIn("unscanned-binary", r.stdout)  # tree is clean; the hit is from history

    def test_odd_line_separators_do_not_hide_text(self):
        for sep in ("\r", "\x0c", "\x0b", "\x1c", "\x85"):
            with self.subTest(sep=repr(sep)):
                self.repo_reset()
                self.put_bytes("a.txt", ("clean" + sep + NAME + sep).encode("utf-8"))
                self.commit("add")
                git(self.repo, "rm", "-q", "a.txt")
                self.commit("rm")
                self.assertEqual(self.gate().returncode, 1, repr(sep))

    def test_annotated_tag_message_and_tagger(self):
        self.put("a.txt", "ok\n")
        self.commit()
        git(self.repo, "tag", "-a", "v1", "-m", f"release by {NAME}")
        self.assertEqual(self.gate().returncode, 1)
        git(self.repo, "tag", "-d", "v1")
        self.assertEqual(self.gate().returncode, 0)
        git(self.repo, "tag", "-a", "v2", "-m", "release", extra=["-c", f"user.name={NAME}"])
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("tagger", r.stdout)
        git(self.repo, "tag", "-d", "v2")
        git(self.repo, "tag", f"{NAME.replace(' ', '-')}-1")  # lightweight tag whose name holds the value
        self.assertEqual(self.gate().returncode, 1)

    def test_user_git_config_cannot_hide_root_commit(self):
        self.put("a.txt", f"{NAME}\n")
        self.commit("root")
        git(self.repo, "rm", "-q", "a.txt")
        self.commit("rm")
        env = {"GIT_CONFIG_COUNT": "2", "GIT_CONFIG_KEY_0": "log.showRoot", "GIT_CONFIG_VALUE_0": "false",
               "GIT_CONFIG_KEY_1": "diff.noprefix", "GIT_CONFIG_VALUE_1": "true"}
        self.assertEqual(self.gate(env_extra=env).returncode, 1)

    def test_hunkless_diff_keeps_correct_sha(self):
        self.put("a.txt", f"{NAME}\n")
        self.commit("first")
        first = git(self.repo, "rev-parse", "HEAD").strip()
        self.put("empty.txt", "")
        self.commit("empty")
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn(first[:10], r.stdout)

    def test_control_chars_in_messages_do_not_hide_text(self):
        self.put("a.txt", "ok\n")
        self.commit("msg\x1eJordan\x1fExample " + NAME)
        self.assertEqual(self.gate().returncode, 1)
        self.repo_reset()
        self.put("a.txt", "ok\n")
        self.commit()
        git(self.repo, "tag", "-a", "v1", "-m", "rel\x1e" + NAME)
        self.assertEqual(self.gate().returncode, 1)

    def test_control_chars_in_file_names(self):
        self.put("x\x1e" + NAME + ".txt", "ok\n")
        self.commit()
        self.assertEqual(self.gate().returncode, 1)

    def test_tag_pointing_at_blob_or_tree(self):
        self.put("a.txt", "ok\n")
        self.commit()
        blob = subprocess.run(["git", "-C", self.repo, "hash-object", "-w", "--stdin"], input=NAME + "\n",
                              capture_output=True, text=True).stdout.strip()
        git(self.repo, "tag", "blobtag", blob)
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("blobtag", r.stdout)
        git(self.repo, "tag", "-d", "blobtag")
        self.assertEqual(self.gate().returncode, 0)
        idx = os.path.join(self.tmp.name, "idx")
        env = {**os.environ, "GIT_INDEX_FILE": idx}
        subprocess.run(["git", "-C", self.repo, "update-index", "--add", "--cacheinfo", f"100644,{blob},deep/f.txt"],
                       env=env, check=True)
        tree = subprocess.run(["git", "-C", self.repo, "write-tree"], env=env, capture_output=True, text=True).stdout.strip()
        git(self.repo, "tag", "treetag", tree)
        self.assertEqual(self.gate().returncode, 1)

    def test_history_on_other_branch(self):
        self.put("a.txt", "ok\n")
        self.commit()
        git(self.repo, "checkout", "-q", "-b", "side")
        self.put("b.txt", f"{NAME}\n")
        self.commit("side")
        git(self.repo, "checkout", "-q", "-")
        git(self.repo, "branch", "-q", "-m", "keep")
        r = self.gate()
        self.assertEqual(r.returncode, 1)

    def test_author_metadata_hit(self):
        self.put("a.txt", "ok\n")
        self.commit(extra=["-c", f"user.name={NAME}"])
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("meta", r.stdout)
        self.assertNotIn(NAME, r.stdout)

    def test_author_email_metadata_hit(self):
        self.put("a.txt", "ok\n")
        self.commit(extra=["-c", f"user.email={EMAIL}"])
        self.assertEqual(self.gate().returncode, 1)

    def test_commit_message_hit(self):
        self.put("a.txt", "ok\n")
        self.commit(f"by {NAME}")
        self.assertEqual(self.gate().returncode, 1)

    def test_history_private_folder_path(self):
        self.put("tracker/v.csv", "id\n")
        self.commit()
        git(self.repo, "rm", "-q", "-r", "tracker")
        self.commit("rm")
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("tracker/", r.stdout)


class SkipTest(GateCase):
    def test_no_identity_skips(self):
        self.write_cfg({"full_name": "", "emails": []})
        self.put("a.txt", f"{NAME}\n")
        self.commit()
        r = self.gate()
        self.assertEqual(r.returncode, 2)
        self.assertIn("SKIPPED", r.stdout)
        self.assertNotIn("PASS", r.stdout)

    def test_no_config_skips(self):
        self.put("a.txt", "x\n")
        self.commit()
        r = self.gate(cfg=None)
        self.assertEqual(r.returncode, 2)
        self.assertIn("PUBLISH GATE: SKIPPED - no private identity configured", r.stdout)

    def test_missing_config_file_skips(self):
        r = self.gate(cfg=os.path.join(self.tmp.name, "nope.json"))
        self.assertEqual(r.returncode, 2)

    def test_broken_config_is_an_error_not_a_pass(self):
        with open(self.cfg, "w") as f:
            f.write("{not json")
        r = self.gate()
        self.assertNotIn(r.returncode, (0, 2))


class UnitTest(unittest.TestCase):
    def test_mask(self):
        import publish_gate
        self.assertEqual(publish_gate.mask("Jordan Example"), "J***e")
        self.assertEqual(publish_gate.mask("ab"), "**")

    def test_build_patterns_labels(self):
        import publish_gate
        labels = {l for l, _ in publish_gate.build_patterns(IDENTITY, ["Zed"], "/srv/x/data")}
        self.assertTrue({"name", "email", "phone", "term", "datadir"} <= labels)

    def test_script_has_no_fixture_values(self):
        with open(GATE, encoding="utf-8") as f:
            text = f.read().lower()
        for v in (NAME, SHORT, EMAIL, "jordan", "example", "555", "0100", "example corp", "jordan_example"):
            if v == "example":
                continue  # appears in the neutral word "example" of documentation; persona-specific values are checked above
            self.assertNotIn(v.lower(), text, v)


class ValidatorCheck14Test(unittest.TestCase):
    def run_validator(self, env_extra):
        env = {k: v for k, v in os.environ.items() if not k.startswith("JOBSEARCH_")}
        env.update(env_extra)
        return subprocess.run([sys.executable, "-B", os.path.join(ROOT, "evals", "validate_repo.py")],
                              capture_output=True, text=True, cwd=ROOT, env=env)

    def test_unset_env_warns_and_passes(self):
        r = self.run_validator({})
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("WARN  publish gate skipped (no private config)", r.stdout)

    def test_missing_config_file_fails_validator(self):
        r = self.run_validator({"JOBSEARCH_CONFIG": os.path.join(ROOT, "no-such-private-config.yaml")})
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL  publish gate", r.stdout)

    def test_hits_make_validator_fail(self):
        # the fixture persona lives in this repo's fixtures, so the gate must report hits
        r = self.run_validator({"JOBSEARCH_CONFIG": FIXTURE_CFG})
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL  publish gate", r.stdout)


if __name__ == "__main__":
    unittest.main()
