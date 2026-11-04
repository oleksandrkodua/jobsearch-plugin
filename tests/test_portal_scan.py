import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "plugins", "jobsearch", "scripts")
FIX = os.path.join(ROOT, "evals", "fixtures", "scan")
sys.path.insert(0, SCRIPTS)

import portal_scan as ps  # noqa: E402


def load(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return json.load(f)


GH = ps.parse_postings("greenhouse:examplecorp", load("greenhouse_jobs.json"))
LV = ps.parse_postings("lever:northwind", load("lever_postings.json"))


def cfg(roles=("QA Engineer",), blockers=(), country="any", remote="any"):
    return {"targets": {"roles": list(roles), "country": country, "remote": remote}, "blockers": list(blockers)}


class Endpoints(unittest.TestCase):
    def test_known_sources(self):
        self.assertEqual(ps.endpoint("greenhouse:examplecorp"), "https://boards-api.greenhouse.io/v1/boards/examplecorp/jobs")
        self.assertEqual(ps.endpoint("lever:northwind"), "https://api.lever.co/v0/postings/northwind?mode=json")

    def test_unsupported_source_raises(self):
        for s in ("indeed:x", "greenhouse:", "lever:Bad Name", ""):
            with self.assertRaises(ValueError):
                ps.endpoint(s)


class Parse(unittest.TestCase):
    def test_greenhouse_fields_and_empty_title_dropped(self):
        self.assertEqual([p["id"] for p in GH], ["greenhouse:examplecorp:1001", "greenhouse:examplecorp:1002",
                                                 "greenhouse:examplecorp:1003", "greenhouse:examplecorp:1004"])
        p = GH[0]
        self.assertEqual((p["company"], p["title"], p["location"], p["posted"]),
                         ("examplecorp", "Senior QA Engineer", "Kyiv, Ukraine", "2026-11-01"))
        self.assertEqual(p["url"], "https://boards.greenhouse.io/examplecorp/jobs/1001")

    def test_lever_fields(self):
        p = LV[0]
        self.assertEqual((p["id"], p["title"], p["location"], p["workplace"]),
                         ("lever:northwind:a1b2", "QA Automation Engineer", "Lviv", "remote"))
        self.assertRegex(p["posted"], r"^\d{4}-\d{2}-\d{2}$")

    def test_garbage_input_gives_empty_list(self):
        self.assertEqual(ps.parse_postings("greenhouse:x", {"jobs": "nope"}), [])
        self.assertEqual(ps.parse_postings("lever:x", {"not": "a list"}), [])


class Classify(unittest.TestCase):
    def test_country(self):
        self.assertEqual([ps.classify_country(p) for p in GH], ["ukraine", "unknown", "not_ukraine", "not_ukraine"])
        self.assertEqual(ps.classify_country(LV[0]), "ukraine")

    def test_remote(self):
        self.assertEqual([ps.classify_remote(p) for p in GH], ["unknown", "yes", "no", "unknown"])
        self.assertEqual([ps.classify_remote(p) for p in LV], ["yes", "no"])


class Filter(unittest.TestCase):
    def test_location_filter_and_unknown_kept(self):
        c = cfg(country="ukraine", remote="yes")
        self.assertIsNone(ps.filter_reason(LV[0], c, "ukraine", "yes"))   # Lviv + remote
        self.assertEqual(ps.filter_reason(GH[2], c, "ukraine", "yes"), "FILTERED (country)")
        self.assertIsNone(ps.filter_reason(GH[1], c, "ukraine", "yes"))   # country unknown, remote yes
        self.assertIsNone(ps.filter_reason(GH[0], c, "ukraine", "yes"))   # remote unknown: kept

    def test_roles_and_blockers(self):
        c = cfg(blockers=[{"type": "keyword", "any": ["blockchain"], "severity": "hard", "label": "no crypto"}])
        self.assertEqual(ps.filter_reason(GH[3], c, "any", "any"), "not in targets.roles")
        self.assertEqual(ps.filter_reason(LV[1], c, "any", "any"), "blocker (hard): no crypto")
        self.assertIsNone(ps.filter_reason(GH[1], c, "any", "any"))

    def test_no_roles_means_no_role_filter(self):
        self.assertIsNone(ps.filter_reason(GH[3], cfg(roles=()), "any", "any"))


class Dedup(unittest.TestCase):
    def test_known_by_company_and_title(self):
        rows = [{"id": "VAC-009", "company": "Example Corp", "position": "QA Engineer"}]
        fresh, known = ps.split_known(GH, rows)
        self.assertEqual([(p["id"], i) for p, i in known], [("greenhouse:examplecorp:1002", "VAC-009")])
        self.assertEqual(len(fresh), len(GH) - 1)

    def test_unseen(self):
        state = {"greenhouse:examplecorp": ["greenhouse:examplecorp:1001"]}
        self.assertNotIn("greenhouse:examplecorp:1001", [p["id"] for p in ps.unseen(GH, state)])
        self.assertEqual(len(ps.unseen(GH, {})), len(GH))


def one(title, location="", workplace="", source="greenhouse:x"):
    """Single posting built through parse_postings (the public path)."""
    if source.startswith("lever:"):
        return ps.parse_postings(source, [{"id": "p", "text": title, "categories": {"location": location},
                                           "workplaceType": workplace, "hostedUrl": "https://e/p"}])[0]
    return ps.parse_postings(source, {"jobs": [{"id": 1, "title": title, "location": {"name": location},
                                                "absolute_url": "https://e/1"}]})[0]


class Robust(unittest.TestCase):
    def test_garbage_fields_do_not_crash(self):
        gh = {"jobs": [
            {"id": 1, "title": ["t"], "location": {"name": "Kyiv"}, "absolute_url": "https://e/1"},
            {"id": 2, "title": "Valid QA Engineer", "location": {"name": ["x"]}, "absolute_url": "https://e/2"},
            {"id": 3, "title": "Valid QA Engineer", "location": {"name": "Remote"}, "absolute_url": "https://e/3"},
        ]}
        out = ps.parse_postings("greenhouse:x", gh)
        ids = [p["id"] for p in out]
        self.assertIn("greenhouse:x:3", ids)
        self.assertNotIn("greenhouse:x:1", ids)
        self.assertEqual([p["location"] for p in out if p["id"] == "greenhouse:x:2"], [""])

        lv = [
            {"id": "e1", "text": "QA Engineer", "categories": {"location": "Lviv"}, "createdAt": 1e30,
             "workplaceType": "remote", "hostedUrl": "https://e/e1"},
            {"id": "e2", "text": "QA Engineer", "categories": {"location": "Lviv"}, "createdAt": True,
             "workplaceType": "remote", "hostedUrl": "https://e/e2"},
            {"id": "e3", "text": "QA Engineer", "categories": {"location": "Lviv"}, "createdAt": 1762128000000,
             "workplaceType": {"a": 1}, "hostedUrl": "https://e/e3"},
        ]
        out = ps.parse_postings("lever:x", lv)
        by_id = {p["id"]: p for p in out}
        self.assertEqual(by_id["lever:x:e1"]["posted"], "")
        self.assertEqual(by_id["lever:x:e2"]["posted"], "")
        self.assertEqual(by_id["lever:x:e3"]["workplace"], "")
        self.assertRegex(by_id["lever:x:e3"]["posted"], r"^\d{4}-\d{2}-\d{2}$")


class Keywords(unittest.TestCase):
    def test_symbol_keywords_match_on_boundaries(self):
        c = cfg(roles=(), blockers=[{"type": "keyword", "any": ["c++"]}])
        p = one("Senior C++ QA Engineer", "Kyiv")
        self.assertEqual(ps.filter_reason(p, c, "any", "any"), "blocker (hard): c++")

    def test_substring_does_not_match(self):
        c = cfg(roles=(), blockers=[{"type": "keyword", "any": ["java"]}])
        self.assertIsNone(ps.filter_reason(one("JavaScript QA Engineer"), c, "any", "any"))


class Severity(unittest.TestCase):
    def test_soft_blocker_labelled_soft(self):
        c = cfg(roles=(), blockers=[{"type": "keyword", "any": ["blockchain"], "severity": "soft", "label": "meh"}])
        self.assertEqual(ps.filter_reason(LV[1], c, "any", "any"), "blocker (soft): meh")


class CountryCode(unittest.TestCase):
    def test_ua_code_is_case_sensitive(self):
        self.assertEqual(ps.classify_country(one("QA Engineer", "Remote, UA")), "ukraine")
        self.assertEqual(ps.classify_country(one("QA Engineer", "Uganda")), "not_ukraine")


import shutil  # noqa: E402
import tempfile  # noqa: E402

DD = os.path.join(ROOT, "evals", "fixtures", "sample-datadir")
OK = {"robots": "ALLOWED", "tos_checked": "2026-11-04", "approved_by_user": "2026-11-04"}


class Clock:
    def __init__(self):
        self.t, self.slept = 0.0, []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.slept.append(round(s, 3))
        self.t += s


class RunCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dd = os.path.join(tmp.name, "data")
        shutil.copytree(DD, self.dd)
        self.calls = []

    def cfg(self, enabled=True, sources=("greenhouse:examplecorp", "lever:northwind"), cap=30, roles=("QA Engineer",)):
        c = ps.datadir.load_config(self.dd, {})
        c["alt_flow"]["scanner"].update({"enabled": enabled, "max_requests_per_run": cap})
        c["portals"]["scan_approved"] = [{"source": s, **OK} for s in sources]
        c["targets"]["roles"] = list(roles)
        return c

    def fetch(self, url):
        self.calls.append(("fetch", url))
        return load("greenhouse_jobs.json") if "greenhouse" in url else load("lever_postings.json")

    def robots(self, verdict="ALLOWED"):
        def f(url):
            self.calls.append(("robots", url))
            return verdict
        return f

    def run_scan(self, c, robots=None, **kw):
        clock = Clock()
        res, state = ps.run_scan(c, self.dd, "2026-11-04", fetch=self.fetch, robots=robots or self.robots(),
                                 sleep=clock.sleep, clock=clock, **kw)
        return res, state, clock


class Run(RunCase):
    def test_disabled_refuses_without_any_call(self):
        with self.assertRaises(ps.ScanDisabled):
            self.run_scan(self.cfg(enabled=False))
        self.assertEqual(self.calls, [])

    def test_robots_then_fetch_per_source_and_polite_delay(self):
        res, state, clock = self.run_scan(self.cfg())
        self.assertEqual([k for k, _ in self.calls], ["robots", "fetch", "robots", "fetch"])
        self.assertEqual(res["requests"], 4)
        self.assertIn(5.0, clock.slept)   # robots -> fetch on the same host waits delay_seconds
        self.assertEqual(sorted(state), ["greenhouse:examplecorp", "lever:northwind"])

    def test_cap_stops_and_reports(self):
        res, _, _ = self.run_scan(self.cfg(cap=2))
        self.assertEqual(res["requests"], 2)
        self.assertIn(("lever:northwind", "request cap reached"), res["skipped"])

    def test_robots_not_allowed_is_skipped_not_fetched(self):
        res, _, _ = self.run_scan(self.cfg(sources=("greenhouse:examplecorp",)), robots=self.robots("DISALLOWED"))
        self.assertNotIn("fetch", [k for k, _ in self.calls])
        self.assertIn(("greenhouse:examplecorp", "robots DISALLOWED"), res["skipped"])

    def test_unapproved_entry_skipped(self):
        c = self.cfg(sources=())
        c["portals"]["scan_approved"] = [{"source": "greenhouse:examplecorp", "robots": "ALLOWED"}]
        res, _, _ = self.run_scan(c)
        self.assertEqual(self.calls, [])
        self.assertTrue(res["skipped"] and res["skipped"][0][0] == "greenhouse:examplecorp")

    def test_fetch_error_reported_once(self):
        def boom(url):
            self.calls.append(("fetch", url))
            raise OSError("timeout")
        clock = Clock()
        res, _ = ps.run_scan(self.cfg(sources=("lever:northwind",)), self.dd, "2026-11-04", fetch=boom,
                             robots=self.robots(), sleep=clock.sleep, clock=clock)
        self.assertEqual([k for k, _ in self.calls].count("fetch"), 1)
        self.assertEqual(res["skipped"][0][0], "lever:northwind")
        self.assertIn("timeout", res["skipped"][0][1])

    def test_filtered_listed_and_state_holds_all_ids(self):
        res, state, _ = self.run_scan(self.cfg(), country="ukraine")
        reasons = {p["id"]: r for p, r in res["filtered"]}
        self.assertEqual(reasons.get("greenhouse:examplecorp:1003"), "FILTERED (country)")
        self.assertIn("greenhouse:examplecorp:1004", reasons)   # not in roles, still listed
        self.assertEqual(len(state["greenhouse:examplecorp"]), 4)

    def test_second_run_shows_only_new(self):
        c = self.cfg()
        _, state, _ = self.run_scan(c)
        ps.save_state(ps.datadir.data_path(c, self.dd, "scan_state"), state)
        res, _, _ = self.run_scan(c)
        self.assertEqual(res["new"] + [p for p, _ in res["filtered"]], [])


class Report(RunCase):
    def test_report_never_overwrites_and_has_sections(self):
        res, _, _ = self.run_scan(self.cfg())
        rdir = os.path.join(self.dd, "reports")
        p1 = ps.write_report(res, "2026-11-04", rdir)
        p2 = ps.write_report(res, "2026-11-04", rdir)
        self.assertNotEqual(p1, p2)
        self.assertTrue(p2.endswith("scan_2026-11-04_2.md"))
        with open(p1, encoding="utf-8") as f:
            text = f.read()
        for h in ("## Sources", "## New candidates", "## Filtered", "## Already in tracker", "## Next step",
                  "| # | Company | Title | Location | Posted | Source | URL |"):
            self.assertIn(h, text)

    def test_tracker_never_written(self):
        tracker = os.path.join(self.dd, "tracker", "vacancies.csv")
        before = os.path.getmtime(tracker)
        res, state, _ = self.run_scan(self.cfg())
        ps.write_report(res, "2026-11-04", os.path.join(self.dd, "reports"))
        self.assertEqual(os.path.getmtime(tracker), before)


class Cli(RunCase):
    def write_cfg(self, enabled):
        with open(os.path.join(self.dd, "jobsearch.config.yaml"), "a", encoding="utf-8") as f:
            f.write(f"\nalt_flow:\n  scanner: {{enabled: {'true' if enabled else 'false'}}}\n")

    def test_disabled_exit_2(self):
        self.write_cfg(False)
        self.assertEqual(ps.main(["run"], env={"JOBSEARCH_DATA_DIR": self.dd}, cwd=self.dd,
                                 fetch=self.fetch, robots=self.robots()), 2)

    def test_endpoint_prints(self):
        self.assertEqual(ps.main(["endpoint", "lever:northwind"], env={}, cwd=self.dd), 0)
        self.assertEqual(ps.main(["endpoint", "indeed:x"], env={}, cwd=self.dd), 1)


class FixRound1(RunCase):
    def test_markdown_injection_neutralised(self):
        bad = {"id": "s:1", "source": "lever:x\nS", "company": "C", "title": "x | y\nz\r| 9 | q",
               "location": "A\n## Next step", "workplace": "", "url": "http://e/1", "posted": ""}
        res = {"requests": 1, "cap": 30, "sources": [("lever:x", 1, 1)],
               "skipped": [("lever:y\n# H", "error: boom\n## Next step")],
               "new": [bad], "filtered": [(bad, "r\n## Next step")], "in_tracker": [(bad, "id\n#")]}
        path = ps.write_report(res, "2026-11-04", os.path.join(self.dd, "reports"))
        with open(path, encoding="utf-8") as f:
            lines = f.read().split("\n")
        self.assertEqual(len([l for l in lines if "x / y z" in l and l.startswith("| 1 |")]), 2)  # new + filtered
        self.assertEqual(len([l for l in lines if l.startswith("## Next step")]), 1)
        self.assertEqual(len([l for l in lines if l.startswith("#") and "H" == l.strip("# ")]), 0)
        i = lines.index("## New candidates")
        j = lines.index("## Filtered (shown, not dropped)")
        table = [l for l in lines[i + 1:j] if l.startswith("|")]
        self.assertEqual(len(table), len(res["new"]) + 2)

    def test_bad_today_rejected(self):
        self.assertEqual(ps.main(["run", "--today", "../x"], env={"JOBSEARCH_DATA_DIR": self.dd}, cwd=self.dd,
                                 fetch=self.fetch, robots=self.robots()), 1)
        self.assertEqual(self.calls, [])
        self.assertFalse(os.path.isdir(os.path.join(self.dd, "reports")) and os.listdir(os.path.join(self.dd, "reports")))

    def test_parse_error_does_not_abort(self):
        real = ps.parse_postings

        def flaky(src, data):
            if src.startswith("lever:"):
                raise KeyError("bad feed")
            return real(src, data)
        ps.parse_postings = flaky
        try:
            res, state, _ = self.run_scan(self.cfg())
        finally:
            ps.parse_postings = real
        self.assertIn("greenhouse:examplecorp", state)
        self.assertNotIn("lever:northwind", state)
        self.assertTrue(any(s == "lever:northwind" and "parse error" in r for s, r in res["skipped"]))
        self.assertEqual([s for s, _, _ in res["sources"]], ["greenhouse:examplecorp"])

    def test_duplicate_entry_skipped_without_request(self):
        res, _, _ = self.run_scan(self.cfg(sources=("lever:northwind", "lever:northwind")))
        self.assertEqual(res["requests"], 2)
        self.assertEqual([k for k, _ in self.calls], ["robots", "fetch"])
        self.assertIn(("lever:northwind", "duplicate entry"), res["skipped"])


class Approve(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cfg_path = os.path.join(tmp.name, "jobsearch.config.yaml")
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            f.write('targets: {roles: ["QA Engineer"]}\nportals:\n  job_portals:\n    - "dou.ua"\n  employer_ats: [greenhouse]\n'
                    'letters: {words_min: 150}\n')

    def approve(self, source="greenhouse:examplecorp", robots="ALLOWED", confirmed=True, tos="2026-11-04"):
        return ps.approve_source(self.cfg_path, source, tos, "2026-11-04", robots=lambda u: robots, confirmed=confirmed)

    def entries(self):
        return ps.datadir.load_config(os.path.dirname(self.cfg_path), {})["portals"]["scan_approved"]

    def test_appends_entry_keeps_rest_and_backs_up(self):
        backup = self.approve()
        e = self.entries()
        self.assertEqual(len(e), 1)
        self.assertEqual(ps.datadir.scan_entry_problems(e[0]), [])
        self.assertEqual(e[0]["host"], "boards-api.greenhouse.io")
        self.assertTrue(os.path.isfile(backup))
        cfg = ps.datadir.load_config(os.path.dirname(self.cfg_path), {})
        self.assertEqual(cfg["portals"]["job_portals"], ["dou.ua"])
        self.assertEqual(cfg["letters"]["words_min"], 150)

    def test_second_source_appended_after_first(self):
        self.approve()
        self.approve("lever:northwind")
        self.assertEqual([x["source"] for x in self.entries()], ["greenhouse:examplecorp", "lever:northwind"])

    def read(self):
        with open(self.cfg_path, encoding="utf-8") as f:
            return f.read()

    def test_refusals_leave_config_untouched(self):
        before = self.read()
        for kw, needle in (({"confirmed": False}, "two confirmations"), ({"robots": "DISALLOWED"}, "robots"),
                           ({"source": "indeed:x"}, "unsupported"), ({"tos": "soon"}, "tos")):
            with self.assertRaises(ValueError) as cm:
                self.approve(**kw)
            self.assertIn(needle, str(cm.exception))
        self.assertEqual(self.read(), before)
        self.assertEqual([f for f in os.listdir(os.path.dirname(self.cfg_path)) if ".bak-" in f], [])
        self.approve()
        after = self.read()
        with self.assertRaises(ValueError) as cm:
            self.approve()
        self.assertIn("already approved", str(cm.exception))
        self.assertEqual(self.read(), after)

    def test_json_config_refused(self):
        p = self.cfg_path[:-5] + ".json"
        with open(p, "w") as f:
            f.write("{}")
        with self.assertRaises(ValueError) as cm:
            ps.approve_source(p, "lever:northwind", "2026-11-04", "2026-11-04", robots=lambda u: "ALLOWED", confirmed=True)
        self.assertIn("by hand", str(cm.exception))


    def write(self, text, newline=""):
        with open(self.cfg_path, "w", encoding="utf-8", newline=newline) as f:
            f.write(text)

    def test_prefix_source_does_not_block(self):
        self.approve("greenhouse:acme-corp")
        self.approve("greenhouse:acme")
        self.assertEqual([x["source"] for x in self.entries()], ["greenhouse:acme-corp", "greenhouse:acme"])

    def test_commented_line_does_not_block(self):
        self.write('portals:\n  scan_approved:\n#    - {source: "greenhouse:acme"}\n  confirmed_domains: []\n')
        self.approve("greenhouse:acme")
        self.assertEqual([x["source"] for x in self.entries()], ["greenhouse:acme"])

    def test_block_map_entry_then_sibling_key(self):
        self.write('portals:\n  scan_approved:\n    - source: "lever:northwind"\n      host: "api.lever.co"\n'
                   '      robots: ALLOWED\n      tos_checked: "2026-11-04"\n      approved_by_user: "2026-11-04"\n'
                   '# note\n  confirmed_domains: []\n')
        self.approve()
        cfg = ps.datadir.load_config(os.path.dirname(self.cfg_path), {})
        e = cfg["portals"]["scan_approved"]
        self.assertEqual([x["source"] for x in e], ["lever:northwind", "greenhouse:examplecorp"])
        self.assertEqual([ps.datadir.scan_entry_problems(x) for x in e], [[], []])
        self.assertEqual(cfg["portals"]["confirmed_domains"], [])

    def test_inline_empty_list(self):
        self.write('portals:\n  scan_approved: []\n  confirmed_domains: []\n')
        self.approve()
        self.assertEqual(len(self.entries()), 1)

    def test_trailing_newline_source_rejected(self):
        with self.assertRaises(ValueError):
            ps.endpoint("lever:a\n")

    def test_crlf_preserved(self):
        self.write('portals:\r\n  job_portals:\r\n    - "dou.ua"\r\nletters: {words_min: 150}\r\n')
        self.approve()
        with open(self.cfg_path, "rb") as f:
            b = f.read()
        self.assertEqual(b.count(b"\r\n"), b.count(b"\n"))
        self.assertEqual(len(self.entries()), 1)

    def test_restore_on_broken_result(self):
        before = self.read()
        orig = ps._insert_entry
        ps._insert_entry = lambda text, line: "portals: [\n"
        self.addCleanup(setattr, ps, "_insert_entry", orig)
        with self.assertRaises(ValueError) as cm:
            self.approve()
        self.assertIn("restored", str(cm.exception))
        self.assertEqual(self.read(), before)
        self.assertEqual(len([f for f in os.listdir(os.path.dirname(self.cfg_path)) if ".bak-" in f]), 1)

    def test_cli(self):
        d = os.path.dirname(self.cfg_path)
        base = ["approve", "lever:northwind", "--tos-checked", "2026-11-04", "--config", self.cfg_path]
        self.assertEqual(ps.main(base, env={}, cwd=d, robots=lambda u: "ALLOWED"), 1)
        self.assertEqual(ps.main(base + ["--confirmed"], env={}, cwd=d, robots=lambda u: "ALLOWED"), 0)
        self.assertEqual(len(self.entries()), 1)


if __name__ == "__main__":
    unittest.main()
