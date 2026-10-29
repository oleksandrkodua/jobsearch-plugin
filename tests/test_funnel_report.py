import contextlib
import csv
import datetime
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "plugins", "jobsearch", "scripts")
SCRIPT = os.path.join(SCRIPTS, "funnel_report.py")
sys.path.insert(0, SCRIPTS)
import datadir  # noqa: E402
import funnel_report  # noqa: E402

FIXTURE = os.path.join(ROOT, "evals", "fixtures", "sample-datadir")
TODAY = datetime.date(2026, 10, 28)
APPLIED_STATUSES = {"APPLIED", "NO_RESPONSE", "REJECTED", "ACTIVE"}


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def cfg_of(**over):
    cfg = datadir.load_config(FIXTURE, {})
    for k, v in over.items():
        sec, key = k.split("__")
        cfg[sec][key] = v
    return cfg


def mk(i, status, url="https://boards.greenhouse.io/x/1", applied="2026-10-01", title="Backend Engineer", notes=""):
    return {"id": f"VAC-{i:03d}", "company": "Co", "position": title, "url": url, "status": status,
            "applied_date": applied, "notes_csv": notes}


class FunnelCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dd = os.path.join(os.path.realpath(tmp.name), "data")
        shutil.copytree(FIXTURE, self.dd)
        self.tracker = os.path.join(self.dd, "tracker", "vacancies.csv")
        self.rows = read_csv(self.tracker)
        self.log = read_csv(os.path.join(self.dd, "tracker", "CHANGELOG.csv"))

    def report(self, rows=None, log=None, cfg=None):
        return funnel_report.build_report(self.rows if rows is None else rows, self.log if log is None else log,
                                          cfg or cfg_of(), TODAY)

    def test_funnel_counts(self):
        rows = self.rows
        applied = [r for r in rows if r["applied_date"] or r["status"] in APPLIED_STATUSES]
        replied = {r["id"] for r in rows if r["status"] in ("REJECTED", "ACTIVE")}
        replied |= {c["id"] for c in self.log if c["field"] == "status" and c["new"] in ("REJECTED", "ACTIVE")}
        replied |= {c["id"] for c in self.log if funnel_report.is_reply_note(c["note"])}
        n = sum(1 for r in applied if r["id"] in replied)  # "any reply" counts applied rows only
        want = f"Funnel: evaluated {len(rows)} -> applied {len(applied)} -> any reply {n}"
        self.assertIn(want, self.report())

    def test_reply_rate_by_host_class(self):
        out = self.report()
        cfg = cfg_of()
        for cls in ("job portal", "employer ATS", "other"):
            grp = [r for r in self.rows if funnel_report.host_class(r["url"], cfg) == cls
                   and (r["applied_date"] or r["status"] in APPLIED_STATUSES)]
            rep = [r for r in grp if r["status"] in ("REJECTED", "ACTIVE")]
            pat = rf"\| {cls} \| {len(grp)} \| {len(rep)} \|"
            self.assertRegex(out, pat)
        self.assertEqual(funnel_report.host_class("https://www.linkedin.com/jobs/1", cfg), "job portal")
        self.assertEqual(funnel_report.host_class("https://boards.greenhouse.io/a", cfg), "employer ATS")
        self.assertEqual(funnel_report.host_class("https://x.example.org/a", cfg), "other")

    def test_small_sample_marked(self):
        rows = [mk(i, "REJECTED" if i == 1 else "APPLIED", title="QA Lead") for i in range(1, 4)]
        rows += [mk(i, "APPLIED", title="Backend Engineer") for i in range(10, 17)]
        out = self.report(rows, [], cfg_of(targets__roles=["QA Lead"]))
        line = [l for l in out.splitlines() if l.startswith("| QA Lead")][0]
        self.assertIn("too few to conclude", line)
        big = [l for l in out.splitlines() if l.startswith("| other |") and "Backend" not in l]
        self.assertTrue(any("too few" not in l for l in big))

    def test_no_job_portals_header_note(self):
        out = self.report(cfg=cfg_of(portals__job_portals=[]))
        self.assertIn("no job portals configured", out)
        self.assertEqual(funnel_report.host_class("https://www.linkedin.com/x", cfg_of(portals__job_portals=[])), "other")

    def test_tracker_unchanged(self):
        logp = os.path.join(self.dd, "tracker", "CHANGELOG.csv")
        before, log_before = read_bytes(self.tracker), read_bytes(logp)
        env = {k: v for k, v in os.environ.items() if not k.startswith("JOBSEARCH_")}
        env["JOBSEARCH_DATA_DIR"] = self.dd
        p = subprocess.run([sys.executable, "-B", SCRIPT, "--today", "2026-10-28"], env=env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(read_bytes(self.tracker), before)
        self.assertEqual(read_bytes(logp), log_before)
        out = os.path.join(self.dd, "reports", "funnel_2026-10-28.md")
        self.assertTrue(os.path.isfile(out))
        self.assertEqual(read_bytes(out).decode("utf-8").strip(), p.stdout.split("\nsaved:")[0].strip())
        self.assertFalse(os.path.exists(os.path.join(self.dd, "tracker", "history")))

    def test_empty_targets_role_other(self):
        cfg = cfg_of(targets__roles=[])
        for r in self.rows:
            self.assertEqual(funnel_report.role_type(r["position"], cfg), "other")
        cfg = cfg_of(targets__roles=["senior engineer"], targets__roles_selective=["QA Lead"])
        self.assertEqual(funnel_report.role_type("Senior Engineer", cfg), "senior engineer")
        self.assertEqual(funnel_report.role_type("QA Lead", cfg), "QA Lead")
        self.assertEqual(funnel_report.role_type("Data Engineer", cfg), "other")

    def test_median_days_and_gap_tags(self):
        rows = [mk(1, "REJECTED", applied="2026-10-01", notes="gap:kubernetes; x"),
                mk(2, "REJECTED", applied="2026-10-01", notes="gap:kubernetes gap:sql"),
                mk(3, "APPLIED", applied="2026-10-02"), mk(4, "APPLIED", applied="")]
        log = [{"timestamp": "20261005_100000_000001", "id": "VAC-001", "field": "status", "old": "", "new": "REJECTED", "note": ""},
               {"timestamp": "20261011_100000_000002", "id": "VAC-002", "field": "status", "old": "", "new": "REJECTED", "note": ""},
               {"timestamp": "20261012_100000_000003", "id": "VAC-003", "field": "note", "old": "", "new": "", "note": "got a reply"}]
        out = self.report(rows, log)
        self.assertIn("Median days to first reply: 10.0 (n=3)", out)  # 4, 10 and the reply note 10
        self.assertRegex(out, r"gap:kubernetes \| 2")
        self.assertRegex(out, r"gap:sql \| 1")
        self.assertIn("any reply 3", out)
        none = self.report([mk(1, "APPLIED")], [])
        self.assertIn("Median days to first reply: n/a", none)
        self.assertIn("none tagged", none)

    def test_minimal_columns(self):
        out = self.report([{"id": "V1", "status": "APPLIED", "url": "", "position": ""}], [])
        self.assertIn("evaluated 1", out)

    # ---- item 1: reply metrics
    def test_negated_reply_notes_not_counted(self):
        rows = [mk(i, "APPLIED") for i in range(1, 8)]
        notes = ["no response", "No reply yet", "not replied", "awaiting reply", "waiting for reply",
                 "still waiting for a response", "recruiter replied"]
        log = [{"timestamp": f"2026100{i}_100000_00000{i}", "id": f"VAC-00{i}", "field": "note", "old": "", "new": "",
                "note": n} for i, n in enumerate(notes, 1)]
        out = self.report(rows, log)
        self.assertIn("-> any reply 1 ", out)
        for n in notes[:-1] + ["they haven't replied"]:
            self.assertFalse(funnel_report.is_reply_note(n), n)
        for n in ("got a reply", "recruiter replied", "response received"):
            self.assertTrue(funnel_report.is_reply_note(n), n)

    def test_negation_further_before_reply_word_and_auto_reply(self):
        for n in ("did not get a reply", "didn't receive any response", "never got a reply", "no reply yet",
                  "still no response", "not replied", "Did not get a reply from them", "auto-reply received",
                  "got an automatic reply", "Auto-Reply only"):
            self.assertFalse(funnel_report.is_reply_note(n), n)
        for n in ("got a reply", "they replied", "response received", "recruiter responded",
                  "no luck on phone, but they replied by mail", "No news. Recruiter replied today"):
            self.assertTrue(funnel_report.is_reply_note(n), n)

    def test_any_reply_counts_only_applied_rows(self):
        rows = [mk(1, "DECLINED", applied=""), mk(2, "APPLIED")]
        log = [{"timestamp": "20261005_100000_000001", "id": "VAC-001", "field": "note", "old": "", "new": "",
                "note": "recruiter replied"}]
        out = self.report(rows, log)
        self.assertIn("-> applied 1 -> any reply 0 ", out)

    def test_median_counts_only_reply_changes(self):
        rows = [mk(1, "REJECTED", applied="2026-10-01"), mk(2, "APPLIED", applied="2026-10-02")]
        log = [{"timestamp": "20261001_100000_000001", "id": "VAC-001", "field": "status", "old": "", "new": "APPLIED", "note": ""},
               {"timestamp": "20261003_100000_000002", "id": "VAC-001", "field": "status", "old": "APPLIED", "new": "NO_RESPONSE", "note": ""},
               {"timestamp": "20261008_100000_000003", "id": "VAC-001", "field": "status", "old": "NO_RESPONSE", "new": "REJECTED", "note": ""},
               {"timestamp": "20261001_100000_000004", "id": "VAC-002", "field": "note", "old": "", "new": "", "note": "got a reply"},
               {"timestamp": "20261003_100000_000005", "id": "VAC-002", "field": "note", "old": "", "new": "", "note": "no reply yet"},
               {"timestamp": "20261005_100000_000006", "id": "VAC-002", "field": "note", "old": "", "new": "", "note": "recruiter replied"}]
        out = self.report(rows, log)
        self.assertIn("Median days to first reply: 5.0 (n=2)", out)  # 7 and 3; the note before applied_date is ignored

    def test_status_row_decided_by_new_status_not_note(self):
        rows = [mk(1, "APPLIED", applied="2026-10-01"), mk(2, "NO_RESPONSE", applied="2026-10-01")]
        log = [{"timestamp": "20261001_100000_000001", "id": "VAC-001", "field": "status", "old": "", "new": "APPLIED",
                "note": "auto-reply received"},
               {"timestamp": "20261004_100000_000002", "id": "VAC-002", "field": "status", "old": "APPLIED",
                "new": "NO_RESPONSE", "note": "recruiter replied"}]
        out = self.report(rows, log)
        self.assertIn("Median days to first reply: n/a", out)
        self.assertIn("-> any reply 0 ", out)

    # ---- item 3: never overwrite, never write into the tracker folder
    def run_main(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = funnel_report.main(["--today", "2026-10-28", *args], env={"JOBSEARCH_DATA_DIR": self.dd}, cwd=self.dd)
        return rc, buf.getvalue()

    def test_existing_report_is_never_overwritten(self):
        rep = os.path.join(self.dd, "reports")
        self.assertEqual(self.run_main()[0], 0)
        first = os.path.join(rep, "funnel_2026-10-28.md")
        with open(first, "w", encoding="utf-8") as f:
            f.write("user edit")
        rc, out = self.run_main()
        self.assertEqual(rc, 0)
        self.assertEqual(read_bytes(first), b"user edit")
        self.assertIn("saved: " + os.path.join(rep, "funnel_2026-10-28_2.md"), out)
        self.assertEqual(self.run_main()[0], 0)
        self.assertTrue(os.path.isfile(os.path.join(rep, "funnel_2026-10-28_3.md")))
        custom = os.path.join(self.dd, "mine.md")
        with open(custom, "w", encoding="utf-8") as f:
            f.write("keep")
        rc, out = self.run_main("--out", custom)
        self.assertEqual((rc, read_bytes(custom)), (0, b"keep"))
        self.assertIn("saved: " + os.path.join(self.dd, "mine_2.md"), out)

    def test_out_inside_tracker_folder_is_refused(self):
        tdir = os.path.join(self.dd, "tracker")
        logp = os.path.join(tdir, "CHANGELOG.csv")
        before = {p: read_bytes(p) for p in (self.tracker, logp)}
        for target in (self.tracker, logp, os.path.join(tdir, "history", "r.md"),
                       os.path.join(self.dd, "x", "..", "tracker", "CHANGELOG.csv")):
            with self.subTest(target=target):
                rc, out = self.run_main("--out", target)
                self.assertEqual(rc, 1, out)
                self.assertIn("refusing", out)
        self.assertEqual({p: read_bytes(p) for p in before}, before)
        self.assertFalse(os.path.exists(os.path.join(tdir, "history")))

    def _fs_case_insensitive(self):
        return os.path.exists(self.dd.swapcase()) and os.path.samefile(self.dd, self.dd.swapcase())

    def test_out_case_variant_is_refused(self):
        if not self._fs_case_insensitive():
            self.skipTest("test filesystem is case-sensitive: case variants are different paths")
        tdir = os.path.join(self.dd, "tracker")
        for target in (os.path.join(self.dd, "TRACKER", "changelog.csv"),
                       os.path.join(self.dd, "Tracker", "HISTORY", "r.md"),
                       os.path.join(self.dd, "tracker", "VACANCIES.CSV")):
            with self.subTest(target=target):
                rc, out = self.run_main("--out", target)
                self.assertEqual(rc, 1, out)
                self.assertIn("refusing", out)
        self.assertFalse(os.path.exists(os.path.join(tdir, "history")))

    def test_symlinked_tracker_real_folder_is_protected(self):
        real = os.path.join(os.path.dirname(self.dd), "real_tracker")
        os.rename(os.path.join(self.dd, "tracker"), real)
        os.symlink(real, os.path.join(self.dd, "tracker"))
        for target in (os.path.join(real, "history", "r.md"), os.path.join(real, "CHANGELOG.csv"),
                       os.path.join(self.dd, "tracker", "history", "r.md")):
            with self.subTest(target=target):
                rc, out = self.run_main("--out", target)
                self.assertEqual(rc, 1, out)
        self.assertFalse(os.path.exists(os.path.join(real, "history")))

    def test_root_level_tracker_layout_writes_default_report(self):
        # paths.tracker at the data-folder root: the folder holding the tracker IS the data dir
        os.rename(self.tracker, os.path.join(self.dd, "vacancies.csv"))
        os.rename(os.path.join(self.dd, "tracker", "CHANGELOG.csv"), os.path.join(self.dd, "CHANGELOG.csv"))
        cfg = datadir.load_config(self.dd, {})
        env = {"JOBSEARCH_DATA_DIR": self.dd, "JOBSEARCH_CONFIG": self._root_cfg(cfg)}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = funnel_report.main(["--today", "2026-10-28"], env=env, cwd=self.dd)
        self.assertEqual(rc, 0, buf.getvalue())
        self.assertTrue(os.path.isfile(os.path.join(self.dd, "reports", "funnel_2026-10-28.md")))
        for target in (os.path.join(self.dd, "vacancies.csv"), os.path.join(self.dd, "CHANGELOG.csv"),
                       os.path.join(self.dd, "history", "r.md")):
            with self.subTest(target=target):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = funnel_report.main(["--today", "2026-10-28", "--out", target], env=env, cwd=self.dd)
                self.assertEqual(rc, 1, buf.getvalue())
        self.assertFalse(os.path.exists(os.path.join(self.dd, "history")))

    def _root_cfg(self, cfg):
        import json
        p = os.path.join(self.dd, "root.config.json")
        cfg = {k: v for k, v in cfg.items() if not k.startswith("_")}
        cfg["paths"]["tracker"] = "vacancies.csv"
        with open(p, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
        return p


if __name__ == "__main__":
    unittest.main()
