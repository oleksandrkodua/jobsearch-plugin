import csv
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "plugins", "jobsearch", "scripts")
SCRIPT = os.path.join(SCRIPTS, "tracker_edit.py")
sys.path.insert(0, SCRIPTS)
import tracker_edit  # noqa: E402

FIXTURE = os.path.join(ROOT, "evals", "fixtures", "sample-datadir")
UA_COMPANY = "Тестова Компанія"


class TrackerCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dd = os.path.join(os.path.realpath(tmp.name), "data")
        shutil.copytree(FIXTURE, self.dd)
        self.csv = os.path.join(self.dd, "tracker", "vacancies.csv")

    def run_cli(self, *args, cwd=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith("JOBSEARCH_")}
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        p = subprocess.run([sys.executable, "-B", SCRIPT, *args], capture_output=True, cwd=cwd or self.dd, env=env)
        return p.returncode, p.stdout.decode("utf-8"), p.stderr.decode("utf-8")

    def rows(self, path=None):
        with open(path or self.csv, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    def read_bytes(self):
        with open(self.csv, "rb") as f:
            return f.read()


class FindTest(TrackerCase):
    def test_find_exact_url(self):
        code, out, _ = self.run_cli("--file", self.csv, "find", "--company", "Zzz",
                                    "--url", "https://www.linkedin.com/jobs/view/1001/")
        self.assertEqual(code, 0)
        self.assertIn("ALREADY APPLIED/SEEN", out)

    def test_find_cyrillic_company(self):
        code, out, _ = self.run_cli("--file", self.csv, "find", "--company", "  ТЕСТОВА   компанія ")
        self.assertEqual(code, 0)
        self.assertIn("SAME COMPANY", out)
        self.assertIn(UA_COMPANY, out)

    def test_find_no_match(self):
        code, out, _ = self.run_cli("--file", self.csv, "find", "--company", "Nonexistent Qwerty")
        self.assertEqual(code, 0)
        self.assertIn("NO MATCH", out)

    def test_ck_keeps_cyrillic_letters(self):
        self.assertEqual(tracker_edit.ck("Їжак-Ґанок, Ёлка & Є 1"), "їжакґанокёлкає1")
        self.assertEqual(tracker_edit.ck(None), "")


class MinimalColumnsTest(TrackerCase):
    def test_minimal_columns_and_bom(self):
        p = os.path.join(self.dd, "min.csv")
        with open(p, "w", encoding="utf-8-sig", newline="") as f:
            f.write("id,company,position,url,status,applied_date\r\nVAC-001,Acme,QA,https://a.example/1,APPLIED,2026-10-01\r\n")
        self.assertEqual(self.run_cli("--file", p, "find", "--company", "Acme", "--job-id", "77")[0], 0)
        code, out, _ = self.run_cli("--file", p, "check")
        self.assertEqual(code, 0)
        self.assertIn("rows: 1", out)

    def test_minimal_columns_write_keeps_columns_and_bom(self):
        p = os.path.join(self.dd, "min.csv")
        with open(p, "w", encoding="utf-8-sig", newline="") as f:
            f.write("id,company,position,url,status,applied_date\r\nVAC-001,Acme,QA,u,APPLIED,\r\n")
        code, _, err = self.run_cli("--file", p, "add", "--company", "B", "--position", "P", "--status", "ACTIVE")
        self.assertEqual(code, 0, err)
        with open(p, "rb") as f:
            raw = f.read()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(raw.decode("utf-8-sig").splitlines()[0], "id,company,position,url,status,applied_date")
        self.assertEqual(self.rows(p)[-1]["id"], "VAC-002")


class NextIdTest(unittest.TestCase):
    def test_max_suffix_any_prefix(self):
        self.assertEqual(tracker_edit.next_id([{"id": "VAC-007"}, {"id": "OLD-012"}, {"id": "x"}], "JOB-"), "JOB-013")
        self.assertEqual(tracker_edit.next_id([], "VAC-"), "VAC-001")


class AddSetTest(TrackerCase):
    def write_config(self, text):
        p = os.path.join(self.dd, "jobsearch.config.yaml")
        with open(p, "a", encoding="utf-8") as f:
            f.write(text)

    def test_add_uses_prefix(self):
        self.write_config('tracker: {id_prefix: "JOB-", decided_by_label: "DECIDED_BY_ME"}\n')
        code, out, err = self.run_cli("add", "--company", "Example Corp", "--position", "QA", "--status", "APPLIED")
        self.assertEqual(code, 0, err)
        self.assertIn("added JOB-041", out)
        last = self.rows()[-1]
        self.assertEqual((last["id"], last["status_confidence"]), ("JOB-041", "DECIDED_BY_ME"))

    def test_add_default_prefix_without_config_key(self):
        code, out, _ = self.run_cli("add", "--company", "X", "--position", "Y", "--status", "APPLIED")
        self.assertIn("added VAC-041", out)
        self.assertEqual(self.rows()[-1]["status_confidence"], "DECIDED_BY_USER")

    def test_config_flag_and_file_without_data_dir(self):
        cfg = os.path.join(self.dd, "other.yaml")
        with open(cfg, "w") as f:
            f.write('tracker: {id_prefix: "ZZ-"}\n')
        elsewhere = tempfile.TemporaryDirectory()
        self.addCleanup(elsewhere.cleanup)
        code, out, err = self.run_cli("--file", self.csv, "--config", cfg, "add", "--company", "X", "--position", "Y",
                                      "--status", "APPLIED", cwd=elsewhere.name)
        self.assertEqual(code, 0, err)
        self.assertIn("added ZZ-041", out)

    def test_default_file_needs_data_dir(self):
        elsewhere = tempfile.TemporaryDirectory()
        self.addCleanup(elsewhere.cleanup)
        code, _, err = self.run_cli("check", cwd=elsewhere.name)
        self.assertNotEqual(code, 0)
        self.assertIn("No data folder", err)

    def test_set_invalid_status_rejected(self):
        before = self.read_bytes()
        code, _, err = self.run_cli("set", "VAC-001", "status", "MAYBE")
        self.assertNotEqual(code, 0)
        self.assertIn("invalid status", err)
        self.assertEqual(self.read_bytes(), before)
        self.assertNotIn("history", os.listdir(os.path.join(self.dd, "tracker")))

    def test_set_unknown_id_or_column_rejected(self):
        before = self.read_bytes()
        self.assertNotEqual(self.run_cli("set", "VAC-999", "status", "APPLIED")[0], 0)
        self.assertNotEqual(self.run_cli("set", "VAC-001", "nope", "x")[0], 0)
        self.assertEqual(self.read_bytes(), before)

    def test_set_writes_backup_changelog_and_counts(self):
        hist = os.path.join(self.dd, "tracker", "history")
        log = os.path.join(self.dd, "tracker", "CHANGELOG.csv")
        log_before = len(self.rows(log))
        old = next(r for r in self.rows() if r["id"] == "VAC-001")["status"]
        new = "REJECTED" if old != "REJECTED" else "APPLIED"
        code, out, err = self.run_cli("set", "VAC-001", "status", new, "--note", "test")
        self.assertEqual(code, 0, err)
        self.assertEqual(len(os.listdir(hist)), 1)
        self.assertEqual(len(self.rows(log)), log_before + 1)
        self.assertEqual(self.rows(log)[-1]["new"], new)
        for needle in ("status value_counts before", "status value_counts after", "rows whose status changed: [("):
            self.assertIn(needle, out)
        self.assertEqual(next(r for r in self.rows() if r["id"] == "VAC-001")["status"], new)

    def test_never_deletes_rows(self):
        n = len(self.rows())
        self.assertEqual(self.run_cli("add", "--company", "A", "--position", "B", "--status", "APPLIED")[0], 0)
        self.assertEqual(len(self.rows()), n + 1)
        self.assertEqual(self.run_cli("set", "VAC-002", "notes_csv", "hello")[0], 0)
        self.assertEqual(len(self.rows()), n + 1)

    def test_check_fixture(self):
        code, out, _ = self.run_cli("check")
        self.assertEqual(code, 0)
        self.assertIn("rows: 40; invalid statuses: none; duplicate ids: none", out)

    def test_fixture_untouched(self):
        self.run_cli("add", "--company", "A", "--position", "B", "--status", "APPLIED")
        with open(os.path.join(FIXTURE, "tracker", "vacancies.csv"), encoding="utf-8") as f:
            self.assertEqual(len(list(csv.DictReader(f))), 40)


class FixRound1Test(TrackerCase):
    def only_backup(self):
        h = os.path.join(self.dd, "tracker", "history")
        names = os.listdir(h)
        self.assertEqual(len(names), 1)
        with open(os.path.join(h, names[0]), "rb") as f:
            return f.read()

    def test_backup_is_pre_edit_state_for_add(self):
        before = self.read_bytes()
        self.assertEqual(self.run_cli("add", "--company", "A", "--position", "B", "--status", "APPLIED")[0], 0)
        self.assertEqual(self.only_backup(), before)
        self.assertNotEqual(self.read_bytes(), before)

    def test_backup_is_pre_edit_state_for_set(self):
        before = self.read_bytes()
        self.assertEqual(self.run_cli("set", "VAC-002", "notes_csv", "changed")[0], 0)
        self.assertEqual(self.only_backup(), before)
        self.assertNotEqual(self.read_bytes(), before)

    def test_short_row_has_no_none(self):
        p = os.path.join(self.dd, "short.csv")
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write("id,company,position,url,status,applied_date\r\nVAC-001,Acme,QA,u,APPLIED,\r\nVAC-002,Beta\r\n")
        _, rows, _ = tracker_edit.load(p)
        self.assertNotIn(None, tracker_edit.counts(rows))
        self.assertIn("", tracker_edit.counts(rows))
        code, out, _ = self.run_cli("--file", p, "check")
        self.assertEqual(code, 0)
        self.assertIn("invalid statuses: ['VAC-002']", out)
        self.assertNotIn("None", out)

    def test_file_with_missing_env_data_dir_warns_and_works(self):
        env = {"JOBSEARCH_DATA_DIR": os.path.join(self.dd, "nope")}
        code, out, err = self.run_env(env, "--file", self.csv, "check")
        self.assertEqual(code, 0)
        self.assertIn("rows: 40", out)
        self.assertIn("JOBSEARCH_DATA_DIR", err)
        self.assertIn("not found", err)

    def test_file_with_missing_env_data_dir_still_honours_config_env(self):
        cfg = os.path.join(self.dd, "other.yaml")
        with open(cfg, "w") as f:
            f.write('tracker: {id_prefix: "ENV-"}\n')
        env = {"JOBSEARCH_DATA_DIR": os.path.join(self.dd, "nope"), "JOBSEARCH_CONFIG": cfg}
        code, out, err = self.run_env(env, "--file", self.csv, "add", "--company", "X", "--position", "Y", "--status", "APPLIED")
        self.assertEqual(code, 0, err)
        self.assertIn("added ENV-041", out)
        self.assertIn("JOBSEARCH_DATA_DIR", err)

    def run_env(self, extra, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith("JOBSEARCH_")}
        env.update(extra, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
        p = subprocess.run([sys.executable, "-B", SCRIPT, *args], capture_output=True, cwd=self.dd, env=env)
        return p.returncode, p.stdout.decode("utf-8"), p.stderr.decode("utf-8")


if __name__ == "__main__":
    unittest.main()
