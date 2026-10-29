#!/usr/bin/env python3
"""Repost check for one vacancy against the tracker and the ranked/ files (stdlib only).

  repost_check.py --company X --title Y [--body-file F] [--today YYYY-MM-DD] [--window-days 90] [--config PATH]

Prints one 'possible repost' line per observation, or 'no repost found'. These are observations for the
user to weigh, never a verdict. A tracker row matches when company and normalised title are equal; a ranked
file matches the same way or, with --body-file, when the description fingerprints are equal. Titles are compared
after dropping a gender marker such as "(m/f/d)". Ranked files are fingerprinted on their "## Description"
section when present, else on the text minus Company/Title/Date/heading lines. Rows and files
with no parsable date are listed with date 'unknown', never dropped. Tracker and ranked dir come from the
data dir (see datadir.py).
"""
import argparse, csv, datetime, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datadir  # noqa: E402
from tracker_edit import ck  # noqa: E402

STOPWORDS = frozenset("""a an and are as at be by for from in is it of on or that the this to we with you your
і й та в у на з із до для по що як це ми ви ваш наш а але або
и в на с со для по что как это мы вы ваш наш но или""".split())
HEADER_RE = re.compile(r"^\s*(#.*|(company|title|date)\s*:.*)$", re.I)
FIELD_RE = {k: re.compile(rf"^\s*{k}\s*:\s*(.+?)\s*$", re.I | re.M) for k in ("company", "title", "date")}
DESC_RE = re.compile(r"^##[ \t]+Description[ \t]*$(.*?)(?=^##[ \t]|\Z)", re.I | re.M | re.S)
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def fingerprint(text, n=40):
    """Lowercase Unicode word tokens, stop-words dropped, first n joined by a space."""
    toks = [t for t in re.findall(r"\w+", (text or "").lower(), re.UNICODE) if t not in STOPWORDS]
    return " ".join(toks[:n])


def norm_title(t):
    """Comparison key for a title: drops a (m/f/d)-style marker, then ck()."""
    return ck(re.sub(r"\(\s*[a-zа-яіїєґё]\s*/\s*[a-zа-яіїєґё](\s*/\s*[a-zа-яіїєґё*]+)*\s*\)", " ", t or "", flags=re.I))


def ranked_description(text):
    """The '## Description' section of a ranked file; older files without it: the text minus header lines."""
    m = DESC_RE.search(text)
    if m:
        return m.group(1)
    return "\n".join(l for l in text.splitlines() if not HEADER_RE.match(l))


def parse_date(s):
    m = DATE_RE.search(s or "")
    if not m:
        return None
    try:
        return datetime.date.fromisoformat(m.group(0))
    except ValueError:
        return None


def _in_window(d, today, window_days):
    """Returns (include, date_text)."""
    if d is None:
        return True, "unknown"
    return 0 <= (today - d).days <= window_days, d.isoformat()


def _ranked_files(ranked_dir):
    if not ranked_dir or not os.path.isdir(ranked_dir):
        return
    for name in sorted(os.listdir(ranked_dir)):
        p = os.path.join(ranked_dir, name)
        if name.lower().endswith(".md") and os.path.isfile(p):
            with open(p, encoding="utf-8-sig", errors="replace") as f:
                yield name, f.read()


def find_reposts(company, title, body, rows, ranked_dir, today, window_days=90):
    """Observations: [{"source": "tracker"|"ranked", "id_or_file", "date", "reason"}]."""
    c, t, fp = ck(company), norm_title(title), fingerprint(body)
    hits = []
    for r in rows:
        if c and ck(r.get("company")) == c and norm_title(r.get("position")) == t:
            ok, dt = _in_window(parse_date(r.get("applied_date")), today, window_days)
            if ok:
                hits.append({"source": "tracker", "id_or_file": r.get("id", ""), "date": dt,
                             "reason": "same company and title"})
    for name, text in _ranked_files(ranked_dir):
        get = lambda k: (FIELD_RE[k].search(text).group(1) if FIELD_RE[k].search(text) else "")
        reasons = []
        if c and ck(get("company")) == c and norm_title(get("title")) == t:
            reasons.append("same company and title")
        if fp and fingerprint(ranked_description(text)) == fp:
            reasons.append("same description fingerprint")
        if reasons:
            ok, dt = _in_window(parse_date(get("date")) or parse_date(name), today, window_days)
            if ok:
                hits.append({"source": "ranked", "id_or_file": name, "date": dt, "reason": " and ".join(reasons)})
    return hits


def _load_tracker(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, restval=""))


def main(argv=None, env=None, cwd=None):
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="Possible-repost observations from tracker and ranked/ files.")
    ap.add_argument("--company", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--body-file", help="vacancy description text file, for the fingerprint match")
    ap.add_argument("--today", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--window-days", type=int, default=90)
    ap.add_argument("--config", help="config file to use (default: the data dir's jobsearch.config.yaml)")
    a = ap.parse_args(argv)
    env = dict(os.environ if env is None else env)
    try:
        today = datetime.date.fromisoformat(a.today) if a.today else datetime.date.today()
        if a.config:
            env[datadir.ENV_CONFIG] = os.path.abspath(a.config)
        dd = datadir.resolve_data_dir(cwd or os.getcwd(), env)
        cfg = datadir.load_config(dd, env)
        tracker = datadir.data_path(cfg, dd, "tracker")
        rows = _load_tracker(tracker) if os.path.isfile(tracker) else []
        body = ""
        if a.body_file:
            with open(a.body_file, encoding="utf-8-sig", errors="replace") as f:
                body = f.read()
        hits = find_reposts(a.company, a.title, body, rows, datadir.data_path(cfg, dd, "ranked"), today, a.window_days)
    except (datadir.DataDirError, ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if not hits:
        print("no repost found")
    for h in hits:
        print(f"possible repost: {h['source']} {h['id_or_file']} date {h['date']} ({h['reason']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
