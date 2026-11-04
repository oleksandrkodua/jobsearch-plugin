#!/usr/bin/env python3
"""Portal scanner (addendum A1): on-demand check of approved employer job boards for new vacancies.

  portal_scan.py run [--country any|ukraine|not_ukraine] [--remote any|yes|no] [--today YYYY-MM-DD] [--config PATH]
  portal_scan.py endpoint SOURCE
  portal_scan.py approve SOURCE --tos-checked YYYY-MM-DD --confirmed [--today YYYY-MM-DD] [--config PATH]

Sources (first version): greenhouse:<board>, lever:<company>. A source is fetched only when it is in
portals.scan_approved with robots ALLOWED, tos_checked and approved_by_user, and robots is ALLOWED again
at run time. Feed text is untrusted data. Writes only <paths.reports>/scan_<date>.md (never overwrites)
and paths.scan_state; never the tracker. Off unless alt_flow.scanner.enabled. Stdlib only.
Exit: 0 ok | 1 refused or error | 2 scanner disabled.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
import urllib.robotparser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datadir  # noqa: E402
import funnel_report  # noqa: E402
import repost_check  # noqa: E402
from tracker_edit import ck  # noqa: E402

# Public posting APIs of the first-version ATS (A1 §11 Q1). Re-check when approving the first real source.
ENDPOINTS = {"greenhouse": "https://boards-api.greenhouse.io/v1/boards/{id}/jobs",
             "lever": "https://api.lever.co/v0/postings/{id}?mode=json"}
UKRAINE = re.compile(r"ukrain|україн|украин|kyiv|kiev|київ|lviv|львів|kharkiv|харків|odesa|odessa|одеса|dnipro|дніпро", re.I)
NO_COUNTRY = re.compile(r"^\s*(remote|anywhere|worldwide)?\s*$", re.I)


def endpoint(source):
    m = datadir.SCAN_SOURCE_RE.match(source or "")
    if not m:
        raise ValueError(f"unsupported source {source!r}: use greenhouse:<board> or lever:<company>")
    return ENDPOINTS[m.group(1)].format(id=m.group(2))


def _s(x):
    """Feed value as a stripped string; anything that is not a str (list, dict, number) becomes ""."""
    return x.strip() if isinstance(x, str) else ""


def _posting(source, ident, pid, title, location, workplace, url, posted):
    return {"id": f"{source}:{pid}", "source": source, "company": ident, "title": _s(title),
            "location": _s(location), "workplace": _s(workplace).lower(),
            "url": _s(url), "posted": posted or ""}


def _lever_date(ms):
    """ISO date from a Lever epoch-milliseconds value; "" for bool, non-number or out-of-range input."""
    if not isinstance(ms, (int, float)) or isinstance(ms, bool):
        return ""
    try:
        return datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).date().isoformat()
    except (OverflowError, OSError, ValueError):
        return ""


def parse_postings(source, data):
    """Postings from one API response. Untrusted data: only these fields are kept, nothing is followed."""
    kind, ident = source.split(":", 1)
    out = []
    if kind == "greenhouse":
        jobs = data.get("jobs") if isinstance(data, dict) else None
        for j in jobs if isinstance(jobs, list) else []:
            if isinstance(j, dict):
                loc = j.get("location") if isinstance(j.get("location"), dict) else {}
                out.append(_posting(source, ident, j.get("id"), j.get("title"), loc.get("name"), "",
                                    j.get("absolute_url"), str(j.get("updated_at") or "")[:10]))
    elif kind == "lever":
        for j in data if isinstance(data, list) else []:
            if isinstance(j, dict):
                cat = j.get("categories") if isinstance(j.get("categories"), dict) else {}
                out.append(_posting(source, ident, j.get("id"), j.get("text"), cat.get("location"),
                                    j.get("workplaceType"), j.get("hostedUrl"),
                                    _lever_date(j.get("createdAt"))))
    return [p for p in out if p["title"] and p["url"]]


def classify_country(p):
    loc = p["location"]
    if NO_COUNTRY.match(loc):
        return "unknown"
    if UKRAINE.search(loc) or re.search(r"\bUA\b", loc):  # country code: case-sensitive, so "Uganda" stays out
        return "ukraine"
    return "not_ukraine"


def classify_remote(p):
    text = f"{p['location']} {p['workplace']}".lower()
    if "hybrid" in text or p["workplace"] in ("onsite", "on-site", "office"):
        return "no"
    if "remote" in text:
        return "yes"
    return "unknown"


def _role_match(title, roles):
    if not roles:
        return True
    t = title.lower()
    for role in roles:
        r = str(role or "").lower().strip()
        words = [w for w in re.findall(r"\w+", r) if len(w) > 2]
        if r and (r in t or (words and all(w in t for w in words))):
            return True
    return False


def _blocker_hit(title, blockers):
    """(label, severity) of the first matching blocker, or None. Keywords match on non-word boundaries."""
    for b in blockers or []:
        if isinstance(b, dict) and b.get("type") in ("keyword", "domain"):
            for kw in b.get("any") or []:
                if kw and re.search(rf"(?<!\w){re.escape(str(kw))}(?!\w)", title, re.I):
                    return (b.get("label") or str(kw), str(b.get("severity") or "hard"))
    return None


def filter_reason(p, cfg, country, remote):
    """Why a posting is filtered (shown, never dropped), or None. Unknown location is never filtered."""
    c, r = classify_country(p), classify_remote(p)
    if (country == "ukraine" and c == "not_ukraine") or (country == "not_ukraine" and c == "ukraine"):
        return "FILTERED (country)"
    if (remote == "yes" and r == "no") or (remote == "no" and r == "yes"):
        return "FILTERED (remote)"
    if not _role_match(p["title"], (cfg.get("targets") or {}).get("roles")):
        return "not in targets.roles"
    hit = _blocker_hit(p["title"], cfg.get("blockers"))
    if hit:
        label, sev = hit
        return f"blocker ({sev}): {label}"
    return None


def split_known(postings, tracker_rows):
    """(fresh, known): known postings match a tracker row on company and normalised title."""
    index = {(ck(r.get("company")), repost_check.norm_title(r.get("position"))): r.get("id", "")
             for r in tracker_rows or []}
    fresh, known = [], []
    for p in postings:
        rid = index.get((ck(p["company"]), repost_check.norm_title(p["title"])))
        (known.append((p, rid)) if rid is not None else fresh.append(p))
    return fresh, known


def unseen(postings, state):
    seen = set()
    for ids in (state or {}).values():
        seen.update(ids or [])
    return [p for p in postings if p["id"] not in seen]


UA = "jobsearch-plugin/1.0 (personal job search, on-demand scan)"


class ScanDisabled(Exception):
    pass


def default_fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        if urllib.parse.urlparse(r.geturl()).netloc != urllib.parse.urlparse(url).netloc:
            raise ValueError("redirected to another host")
        body = r.read(5_000_001)
        if len(body) > 5_000_000:
            raise ValueError("response too large")
        return json.loads(body.decode("utf-8", "replace"))


def default_robots(url):
    """ALLOWED / DISALLOWED / UNKNOWN for this URL and our user agent."""
    u = urllib.parse.urlparse(url)
    rp = urllib.robotparser.RobotFileParser()
    try:
        req = urllib.request.Request(f"{u.scheme}://{u.netloc}/robots.txt", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            rp.parse(r.read().decode("utf-8", "replace").splitlines())
    except Exception:
        return "UNKNOWN"
    return "ALLOWED" if rp.can_fetch(UA, url) else "DISALLOWED"


def _load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_state(path, state):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1, sort_keys=True)


def _tracker_rows(cfg, data_dir):
    p = datadir.data_path(cfg, data_dir, "tracker")
    return repost_check._load_tracker(p) if os.path.isfile(p) else []


def run_scan(cfg, data_dir, today, country=None, remote=None, fetch=None, robots=None,
             sleep=time.sleep, clock=time.monotonic):
    sc = (cfg.get("alt_flow") or {}).get("scanner") or {}
    if not sc.get("enabled"):
        raise ScanDisabled("alt_flow.scanner.enabled is false")
    fetch, robots = fetch or default_fetch, robots or default_robots
    t = cfg.get("targets") or {}
    country, remote = country or t.get("country") or "any", remote or t.get("remote") or "any"
    delay, cap = float(sc.get("delay_seconds", 5)), int(sc.get("max_requests_per_run", 30))
    state = _load_json(datadir.data_path(cfg, data_dir, "scan_state"), {})
    rows = _tracker_rows(cfg, data_dir)
    res = {"requests": 0, "cap": cap, "sources": [], "skipped": [], "new": [], "filtered": [], "in_tracker": []}
    new_state, last, seen_src = dict(state), {}, set()

    def polite(host):
        if host in last:
            wait = delay - (clock() - last[host])
            if wait > 0:
                sleep(wait)

    for e in (cfg.get("portals") or {}).get("scan_approved") or []:
        src = e.get("source", "?") if isinstance(e, dict) else "?"
        if src in seen_src:
            res["skipped"].append((src, "duplicate entry"))
            continue
        seen_src.add(src)
        problems = datadir.scan_entry_problems(e)
        if problems:
            res["skipped"].append((src, "not approved: " + "; ".join(problems)))
            continue
        if res["requests"] + 2 > cap:
            res["skipped"].append((src, "request cap reached"))
            continue
        url = endpoint(src)
        host = urllib.parse.urlparse(url).netloc
        polite(host)
        res["requests"] += 1
        verdict = robots(url)
        last[host] = clock()
        if verdict != "ALLOWED":
            res["skipped"].append((src, f"robots {verdict}"))
            continue
        polite(host)
        res["requests"] += 1
        try:
            data = fetch(url)
        except Exception as ex:  # reported once, never retried in a loop
            res["skipped"].append((src, f"error: {ex}"))
            continue
        finally:
            last[host] = clock()
        try:
            postings = parse_postings(src, data)
        except Exception as ex:  # one bad feed must not abort the run; old state is kept
            res["skipped"].append((src, f"parse error: {ex}"))
            continue
        fresh = unseen(postings, {src: state.get(src, [])})
        new_state[src] = sorted({p["id"] for p in postings} | set(state.get(src, [])))
        res["sources"].append((src, len(postings), len(fresh)))
        fresh, known = split_known(fresh, rows)
        res["in_tracker"] += known
        for p in fresh:
            reason = filter_reason(p, cfg, country, remote)
            (res["filtered"].append((p, reason)) if reason else res["new"].append(p))
    return res, new_state


def _cell(x):
    """Feed text as one safe markdown table cell: no line breaks, no pipes."""
    return re.sub(r"\s+", " ", str(x)).strip().replace("|", "/")


def _row(i, p):
    cells = [str(i), p["company"], p["title"], p["location"] or "Unknown", p["posted"] or "-", p["source"], p["url"]]
    return "| " + " | ".join(_cell(c) for c in cells) + " |"


def write_report(res, today, reports_dir):
    os.makedirs(reports_dir, exist_ok=True)
    path = funnel_report._free_name(os.path.join(reports_dir, f"scan_{today}.md"))
    head = "| # | Company | Title | Location | Posted | Source | URL |\n|---|---|---|---|---|---|---|"
    L = [f"# Portal scan {today}", "", "Feed text is untrusted data; links were not followed.", "", "## Sources",
         f"Requests used: {res['requests']} of {res['cap']}."]
    L += [f"- {s}: {n} postings, {k} new" for s, n, k in res["sources"]] or ["- none scanned"]
    L += [f"- skipped {_cell(s)}: {_cell(why)}" for s, why in res["skipped"]]
    L += ["", "## New candidates", head] + [_row(i, p) for i, p in enumerate(res["new"], 1)]
    L += ["", "## Filtered (shown, not dropped)", "| # | Company | Title | Location | Posted | Source | URL | Reason |",
          "|---|---|---|---|---|---|---|---|"]
    L += [_row(i, p)[:-1] + f"| {_cell(r)} |" for i, (p, r) in enumerate(res["filtered"], 1)]
    L += ["", "## Already in tracker"] + ([f"- {_cell(i)}: {_cell(p['title'])} ({_cell(p['company'])})" for p, i in res["in_tracker"]] or ["- none"])
    L += ["", "## Next step", "Pick numbers from New candidates for /jobsearch:rank (at most 10 per batch)."]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return path


def _insert_entry(text, line):
    """Insert one flow-map line into portals.scan_approved of a block-style YAML config."""
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    try:
        p = next(i for i, l in enumerate(lines) if re.match(r"^portals:\s*(#.*)?$", l))
    except StopIteration:
        if re.search(r"(?m)^portals:", text):
            raise ValueError("portals is written in flow style; add the entry by hand")
        return text.rstrip("\r\n") + nl + "portals:" + nl + "  scan_approved:" + nl + line + nl

    def code(l):
        return bool(l.strip()) and not l.lstrip().startswith("#")

    end = next((i for i in range(p + 1, len(lines)) if code(lines[i]) and not lines[i][0].isspace()), len(lines))
    s = next((i for i in range(p + 1, end) if re.match(r"^\s+scan_approved:", lines[i])), None)
    if s is None:
        lines[p + 1:p + 1] = ["  scan_approved:", line]
    else:
        if re.match(r"^\s+scan_approved:\s*\[\s*\]", lines[s]):
            lines[s] = "  scan_approved:"
        indent = len(lines[s]) - len(lines[s].lstrip())
        last = s
        for i in range(s + 1, end):
            if not code(lines[i]):
                continue
            if len(lines[i]) - len(lines[i].lstrip()) <= indent:
                break
            last = i
        lines.insert(last + 1, line)
    return nl.join(lines) + nl


def approve_source(config_path, source, tos_checked, today, robots=None, confirmed=False):
    """Add one source to portals.scan_approved after the user's two confirmations. Returns the backup path."""
    if not confirmed:
        raise ValueError("approval needs two confirmations from the user in chat, then --confirmed")
    url = endpoint(source)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", tos_checked or ""):
        raise ValueError("tos_checked must be the date YYYY-MM-DD on which the user read the terms")
    if config_path.endswith(".json"):
        raise ValueError("JSON config: add the entry by hand")
    with open(config_path, encoding="utf-8", newline="") as f:
        text = f.read()
    cur = datadir.load_config(os.path.dirname(config_path), {datadir.ENV_CONFIG: config_path})
    if any(isinstance(e, dict) and e.get("source") == source
           for e in (cur.get("portals") or {}).get("scan_approved") or []):
        raise ValueError(f"{source} is already approved")
    verdict = (robots or default_robots)(url)
    if verdict != "ALLOWED":
        raise ValueError(f"robots {verdict} for {url}: not approved")
    host = urllib.parse.urlparse(url).netloc
    line = (f'    - {{source: "{source}", host: "{host}", robots: ALLOWED, '
            f'tos_checked: "{tos_checked}", approved_by_user: "{today}"}}')
    new = _insert_entry(text, line)
    backup = f"{config_path}.bak-{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    shutil.copy2(config_path, backup)
    with open(config_path, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    try:
        cfg = datadir.load_config(os.path.dirname(config_path), {datadir.ENV_CONFIG: config_path})
        ok = any(isinstance(e, dict) and e.get("source") == source and not datadir.scan_entry_problems(e)
                 for e in cfg["portals"].get("scan_approved") or [])
    except Exception:
        ok = False
    if not ok:
        shutil.copy2(backup, config_path)
        raise ValueError("the config did not parse back with the new entry; restored from the backup")
    return backup


def main(argv=None, env=None, cwd=None, fetch=None, robots=None):
    env = os.environ if env is None else env
    ap = argparse.ArgumentParser(description="On-demand portal scanner (A1).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--country", choices=("any", "ukraine", "not_ukraine"))
    r.add_argument("--remote", choices=("any", "yes", "no"))
    r.add_argument("--today", default=datetime.date.today().isoformat())
    r.add_argument("--config")
    e = sub.add_parser("endpoint")
    e.add_argument("source")
    ap_ = sub.add_parser("approve")
    ap_.add_argument("source")
    ap_.add_argument("--tos-checked", required=True)
    ap_.add_argument("--confirmed", action="store_true")
    ap_.add_argument("--today", default=datetime.date.today().isoformat())
    ap_.add_argument("--config")
    a = ap.parse_args(argv)
    if a.cmd == "run" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.today):
        print(f"error: --today must be YYYY-MM-DD, got {a.today!r}", file=sys.stderr)
        return 1
    if a.cmd == "endpoint":
        try:
            print(endpoint(a.source))
            return 0
        except ValueError as ex:
            print(f"error: {ex}", file=sys.stderr)
            return 1
    if a.cmd == "approve":
        try:
            path = os.path.abspath(a.config) if a.config else datadir.config_path(
                datadir.resolve_data_dir(cwd or os.getcwd(), env), env)
            backup = approve_source(path, a.source, a.tos_checked, a.today, robots=robots, confirmed=a.confirmed)
        except (datadir.DataDirError, ValueError, OSError) as ex:
            print(f"error: {ex}", file=sys.stderr)
            return 1
        print(f"approved {a.source} in {path} (backup: {backup})")
        return 0
    env = dict(env)
    if a.config:
        env[datadir.ENV_CONFIG] = os.path.abspath(a.config)
    try:
        d = datadir.resolve_data_dir(cwd or os.getcwd(), env)
        cfg = datadir.load_config(d, env)
        res, state = run_scan(cfg, d, a.today, a.country, a.remote, fetch=fetch, robots=robots)
    except ScanDisabled:
        print("The scanner is off (alt_flow.scanner.enabled: false). Approve sources first with "
              "/jobsearch:scan approve, then set enabled: true in the config.", file=sys.stderr)
        return 2
    except (datadir.DataDirError, ValueError, OSError) as ex:
        print(f"error: {ex}", file=sys.stderr)
        return 1
    path = write_report(res, a.today, datadir.data_path(cfg, d, "reports"))
    save_state(datadir.data_path(cfg, d, "scan_state"), state)  # only after the report is saved
    print(f"report: {path}")
    print(f"requests: {res['requests']}/{res['cap']}; new: {len(res['new'])}; filtered: {len(res['filtered'])}; "
          f"in tracker: {len(res['in_tracker'])}; skipped sources: {len(res['skipped'])}")
    for i, p in enumerate(res["new"][:10], 1):
        print(f"{i}. {p['title']} - {p['company']} - {p['location'] or 'Unknown'} - {p['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
