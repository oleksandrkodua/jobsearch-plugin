import datetime
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "plugins", "jobsearch", "scripts")
SCRIPT = os.path.join(SCRIPTS, "repost_check.py")
sys.path.insert(0, SCRIPTS)
import repost_check  # noqa: E402

FIXTURE = os.path.join(ROOT, "evals", "fixtures", "sample-datadir")
TODAY = datetime.date(2026, 10, 28)


def row(rid, company, position, applied):
    return {"id": rid, "company": company, "position": position, "applied_date": applied}


class RepostCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = os.path.realpath(tmp.name)
        self.ranked = os.path.join(self.tmp, "ranked")
        os.makedirs(self.ranked)

    def find(self, rows, company="Northwind Labs", title="Platform Engineer", body="", **kw):
        return repost_check.find_reposts(company, title, body, rows, self.ranked, TODAY, **kw)

    def test_same_company_title_within_90_days(self):
        d90 = (TODAY - datetime.timedelta(days=90)).isoformat()
        d91 = (TODAY - datetime.timedelta(days=91)).isoformat()
        hits = self.find([row("VAC-001", "northwind labs", "Platform  Engineer!", d90)])
        self.assertEqual(len(hits), 1)
        self.assertEqual((hits[0]["source"], hits[0]["id_or_file"], hits[0]["date"]), ("tracker", "VAC-001", d90))
        self.assertEqual(self.find([row("VAC-001", "Northwind Labs", "Platform Engineer", d91)]), [])

    def test_future_date_is_not_a_hit(self):
        fut = (TODAY + datetime.timedelta(days=1)).isoformat()
        self.assertEqual(self.find([row("VAC-001", "Northwind Labs", "Platform Engineer", fut)]), [])

    def test_different_company_or_title_no_hit(self):
        d = TODAY.isoformat()
        self.assertEqual(self.find([row("V1", "Other Co", "Platform Engineer", d),
                                    row("V2", "Northwind Labs", "QA Lead", d)]), [])

    def test_fingerprint_unicode(self):
        a = "Ми шукаємо інженера з тестування: Python, API; досвід 3+ років!"
        b = "ми ШУКАЄМО інженера з тестування -- python API (досвід 3+ років)"
        self.assertEqual(repost_check.fingerprint(a), repost_check.fingerprint(b))
        self.assertIn("інженера", repost_check.fingerprint(a))
        self.assertNotEqual(repost_check.fingerprint(a), repost_check.fingerprint("зовсім інший текст вакансії"))

    def test_fingerprint_drops_stopwords_and_limits_n(self):
        fp = repost_check.fingerprint("The quick and the brown fox", n=2)
        self.assertEqual(fp, "quick brown")
        self.assertEqual(len(repost_check.fingerprint(" ".join(f"w{i}" for i in range(100))).split()), 40)

    def test_ranked_file_match(self):
        with open(os.path.join(self.ranked, "2026-10-20_01.md"), "w", encoding="utf-8") as f:
            f.write("# R\n\nCompany: Northwind Labs\nTitle: Platform Engineer\nDate: 2026-10-20\n\nbody\n")
        hits = self.find([])
        self.assertEqual(len(hits), 1)
        self.assertEqual((hits[0]["source"], hits[0]["id_or_file"], hits[0]["date"]),
                         ("ranked", "2026-10-20_01.md", "2026-10-20"))

    def test_ranked_file_body_fingerprint_match(self):
        body = "Build reliable pipelines with Python and Kafka for payments data teams across Europe"
        with open(os.path.join(self.ranked, "a.md"), "w", encoding="utf-8") as f:
            f.write(f"Company: Renamed Corp\nTitle: Something Else\nDate: 2026-10-01\n\n{body.upper()}.\n")
        hits = self.find([], body=body)
        self.assertEqual(len(hits), 1)
        self.assertIn("description", hits[0]["reason"])

    def test_no_date_rows_reported_not_dropped(self):
        hits = self.find([row("VAC-009", "Northwind Labs", "Platform Engineer", ""),
                          row("VAC-010", "Northwind Labs", "Platform Engineer", "not a date")])
        self.assertEqual([h["date"] for h in hits], ["unknown", "unknown"])

    def test_ranked_file_without_date_reported(self):
        with open(os.path.join(self.ranked, "x.md"), "w", encoding="utf-8") as f:
            f.write("Company: Northwind Labs\nTitle: Platform Engineer\n")
        self.assertEqual(self.find([])[0]["date"], "unknown")

    def test_cyrillic_company_matches(self):
        d = TODAY.isoformat()
        hits = self.find([row("VAC-002", "Тестова Компанія", "Backend Engineer", d)],
                         company="ТЕСТОВА компанія", title="Backend Engineer")
        self.assertEqual(len(hits), 1)

    def _ranked(self, name, company, desc, verdict):
        with open(os.path.join(self.ranked, name), "w", encoding="utf-8") as f:
            f.write(f"Vacancy Check\nCompany: {company}\nTitle: Something Else\nDate: 2026-10-01\n"
                    f"Match: {verdict}%  (arithmetic with many words {verdict} {verdict} {verdict})\n"
                    f"Decision: APPLY - reason number {verdict}\n\n## Notes\nother {verdict}\n\n## Description\n{desc}\n")

    def test_ranked_description_section_fingerprint(self):
        desc = "Build reliable pipelines with Python and Kafka for payments data teams across Europe"
        self._ranked("r1.md", "Renamed Corp", desc, 71)
        hits = self.find([], body=desc)
        self.assertEqual(len(hits), 1)
        self.assertIn("description", hits[0]["reason"])

    def test_ranked_check_blocks_differ_descriptions_equal(self):
        desc = "Build reliable pipelines with Python and Kafka for payments data teams across Europe"
        self._ranked("r1.md", "Renamed Corp", desc, 71)
        self._ranked("r2.md", "Other Corp", desc, 88)
        self.assertEqual(sorted(h["id_or_file"] for h in self.find([], body=desc)), ["r1.md", "r2.md"])
        self.assertEqual(self.find([], body="a completely different vacancy text about nursing shifts"), [])

    def _write(self, name, text):
        with open(os.path.join(self.ranked, name), "w", encoding="utf-8", newline="") as f:
            f.write(text)

    def test_description_with_inner_heading_is_fully_fingerprinted(self):
        full = ("Build reliable pipelines with Python and Kafka.\n\n## Requirements\nFive years of Go and SQL "
                "experience for payments data teams across Europe\n")
        self._write("h.md", "Company: Renamed Corp\nTitle: Other\nDate: 2026-10-01\n\n## Notes\nx\n\n## Description\n" + full)
        hits = self.find([], body=full)
        self.assertEqual([h["id_or_file"] for h in hits], ["h.md"])
        self.assertIn("description", hits[0]["reason"])

    def test_description_crlf_and_no_space_heading(self):
        full = "Build reliable pipelines with Python and Kafka.\n\n## Requirements\nGo and SQL for payments data\n"
        self._write("c.md", ("Company: A\nTitle: B\nDate: 2026-10-01\n\n## Description\n" + full).replace("\n", "\r\n"))
        self._write("n.md", "Company: C\nTitle: D\nDate: 2026-10-01\n\n##Description\n" + full)
        self._write("u.md", "Company: E\nTitle: F\nDate: 2026-10-01\n\n## DESCRIPTION  \n" + full)
        self.assertEqual(sorted(h["id_or_file"] for h in self.find([], body=full)), ["c.md", "n.md", "u.md"])

    def test_gender_marker_normalised(self):
        d = TODAY.isoformat()
        for t in ("Platform Engineer (m/f/d)", "Platform Engineer (m/w/d)"):
            self.assertEqual(len(self.find([row("V1", "Northwind Labs", t, d)])), 1, t)
        self.assertEqual(len(self.find([row("V1", "Northwind Labs", "Platform Engineer", d)],
                                       title="Platform Engineer (m/f/d)")), 1)

    def test_non_gender_parenthesis_kept(self):
        d = TODAY.isoformat()
        self.assertEqual(self.find([row("V1", "Northwind Labs", "Platform Engineer (Python/Go)", d)]), [])

    def test_missing_ranked_dir_ok(self):
        self.assertEqual(repost_check.find_reposts("A", "B", "", [], os.path.join(self.tmp, "nope"), TODAY), [])


class CliCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dd = os.path.join(os.path.realpath(tmp.name), "data")
        shutil.copytree(FIXTURE, self.dd)

    def run_cli(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith("JOBSEARCH_")}
        env["PYTHONIOENCODING"] = "utf-8"
        env["JOBSEARCH_DATA_DIR"] = self.dd
        return subprocess.run([sys.executable, "-B", SCRIPT, *args], capture_output=True, text=True,
                              encoding="utf-8", env=env, cwd=self.dd)

    def test_possible_repost_lines(self):
        r = self.run_cli("--company", "Northwind Labs", "--title", "Platform Engineer", "--today", "2026-10-28")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("possible repost", r.stdout)
        self.assertIn("VAC-001", r.stdout)
        self.assertIn("2026-10-20_01.md", r.stdout)

    def test_no_repost_found(self):
        r = self.run_cli("--company", "Nonexistent Inc", "--title", "Wizard", "--today", "2026-10-28")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "no repost found")

    def test_body_file_and_bad_today(self):
        bf = os.path.join(self.dd, "body.txt")
        with open(bf, "w", encoding="utf-8") as f:
            f.write("Synthetic posting body. Must have: Python, testing, API design. Nice to have: cloud basics. Remote-friendly, fictional data.")
        r = self.run_cli("--company", "Zzz", "--title", "Yyy", "--body-file", bf, "--today", "2026-10-28")
        self.assertIn("possible repost", r.stdout)
        self.assertNotEqual(self.run_cli("--company", "a", "--title", "b", "--today", "garbage").returncode, 0)


if __name__ == "__main__":
    unittest.main()
