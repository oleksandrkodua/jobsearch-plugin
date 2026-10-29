#!/usr/bin/env python3
"""Funnel and patterns report from the tracker and CHANGELOG.csv (stdlib only, read-only on the tracker).

  funnel_report.py [--config PATH] [--out PATH] [--today YYYY-MM-DD]

Stages: evaluated (all rows) -> applied -> any reply -> active / rejected. Reply rate by host class (job portal /
employer ATS / other) and by role type, rejection reasons by gap:<tag> tokens in the notes columns, median days
from applied_date to the first reply (a CHANGELOG change to REJECTED/ACTIVE or a reply note, on/after applied_date).
A reply note mentions a reply or response not preceded by no / not / awaiting / waiting for. A group with fewer
than 5 applications is marked "too few to conclude". Writes <paths.reports>/funnel_<date>.md (creates only that
folder) and prints it. Never overwrites: an existing report gets a _2, _3 ... suffix. Refuses any --out equal to the
tracker or CHANGELOG.csv, or inside the tracker's history/ folder (exit 1).
"""
import argparse, collections, csv, datetime, os, re, statistics, sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datadir  # noqa: E402

MIN_N = 5
APPLIED_STATUSES = {"APPLIED", "NO_RESPONSE", "REJECTED", "ACTIVE"}
REPLY_STATUSES = {"REJECTED", "ACTIVE"}
REPLY_RE = re.compile(r"\b(repl(y|ied|ies)|respon(se|ded))\b", re.I)
NEGATION_RE = re.compile(r"(\b(no|not|never|without|awaiting|waiting\s+for)|n't)\s+((a|an|any|the|their|yet)\s+)?$", re.I)
GAP_RE = re.compile(r"\bgap:([\w.+#-]+)", re.I)
TOO_FEW = "too few to conclude"


def _host(url):
    try:
        return (urlparse(url if "//" in url else "//" + url).hostname or "").lower()
    except ValueError:
        return ""


def host_class(url, cfg):
    h = _host(url or "")
    if not h:
        return "other"
    p = cfg.get("portals", {})
    if any(str(a).lower() in h for a in (p.get("employer_ats") or [])):
        return "employer ATS"
    for d in (p.get("job_portals") or []):
        d = str(d).lower().lstrip(".")
        if d and (h == d or h.endswith("." + d)):
            return "job portal"
    return "other"


def role_type(title, cfg):
    t = (title or "").lower()
    tg = cfg.get("targets", {})
    for key in ("roles", "roles_selective", "roles_not_primary"):
        for entry in (tg.get(key) or []):
            if str(entry).strip() and str(entry).lower() in t:
                return str(entry)
    return "other"


def _date(s):
    try:
        return datetime.date.fromisoformat((s or "").strip()[:10])
    except ValueError:
        return None


def _is_applied(r):
    return bool((r.get("applied_date") or "").strip()) or r.get("status", "") in APPLIED_STATUSES


def is_reply_note(note):
    """A note reports a reply when a reply word is not preceded by no / not / awaiting / waiting for."""
    note = note or ""
    return any(not NEGATION_RE.search(note[:m.start()]) for m in REPLY_RE.finditer(note))


def _is_reply_change(c):
    """A status row counts by its new status only (->APPLIED / ->NO_RESPONSE never, whatever the note says);
    any other row counts when its note reports a reply."""
    if c.get("field") == "status":
        return (c.get("new") or "").strip() in REPLY_STATUSES
    return is_reply_note(c.get("note", ""))


def _reply_ids(rows, changelog):
    ids = {r.get("id", "") for r in rows if r.get("status", "") in REPLY_STATUSES}
    ids |= {c.get("id", "") for c in changelog if _is_reply_change(c)}
    return ids & {r.get("id", "") for r in rows}


def _change_date(c):
    m = re.match(r"(\d{4})(\d{2})(\d{2})", c.get("timestamp", "") or "")
    try:
        return datetime.date(*map(int, m.groups())) if m else None
    except ValueError:
        return None


def _median_days(rows, changelog):
    """Days from applied_date to the first reply change dated on/after it (->APPLIED, ->NO_RESPONSE never count)."""
    replies = collections.defaultdict(list)
    for c in changelog:
        d = _change_date(c)
        if d and _is_reply_change(c):
            replies[c.get("id", "")].append(d)
    days = []
    for r in rows:
        a = _date(r.get("applied_date"))
        later = [d for d in replies.get(r.get("id", ""), []) if a and d >= a]
        if later:
            days.append((min(later) - a).days)
    return f"{statistics.median(days):.1f} (n={len(days)})" if days else "n/a"


def _table(title, groups, replied):
    lines = [f"## {title}", "", "| group | applied | replied | rate | note |", "|---|---|---|---|---|"]
    for g in sorted(groups):
        n = len(groups[g])
        k = sum(1 for r in groups[g] if r.get("id", "") in replied)
        rate = f"{100 * k // n}%" if n else "n/a"
        lines.append(f"| {g} | {n} | {k} | {rate} | {TOO_FEW if n < MIN_N else ''} |".replace("|  |", "| |"))
    if not groups:
        lines.append("| (no applications) | 0 | 0 | n/a | |")
    return lines + [""]


def build_report(rows, changelog, cfg, today):
    applied = [r for r in rows if _is_applied(r)]
    replied = _reply_ids(rows, changelog)
    n_rep = sum(1 for r in applied if r.get("id", "") in replied)
    active = sum(1 for r in rows if r.get("status") == "ACTIVE")
    rej_rows = [r for r in rows if r.get("status") == "REJECTED"]
    portals = cfg.get("portals", {}).get("job_portals") or []
    L = [f"# Funnel report {today.isoformat()}", "",
         f"Read-only view of the tracker. A group with fewer than {MIN_N} applications is marked \"{TOO_FEW}\".",
         "Any reply = an applied row with status REJECTED or ACTIVE, a CHANGELOG change to one of them, or a CHANGELOG "
         "note reporting a reply or response (\"no reply\", \"awaiting response\" and the like do not count)."]
    if not portals:
        L.append("Host class: no job portals configured (portals.job_portals is empty), so none is classed as a job portal.")
    L += ["", "## Funnel", "",
          f"Funnel: evaluated {len(rows)} -> applied {len(applied)} -> any reply {n_rep} "
          f"-> active {active} / rejected {len(rej_rows)}", "",
          f"Applied rows with a reply: {n_rep} of {len(applied)}."
          + (f" ({TOO_FEW})" if len(applied) < MIN_N else ""), ""]
    by_host, by_role = collections.defaultdict(list), collections.defaultdict(list)
    for r in applied:
        by_host[host_class(r.get("url", ""), cfg)].append(r)
        by_role[role_type(r.get("position", ""), cfg)].append(r)
    for c in ("job portal", "employer ATS", "other"):
        by_host.setdefault(c, [])
    L += _table("Reply rate by host class", by_host, replied)
    L += _table("Reply rate by role type", by_role, replied)
    tags = collections.Counter()
    for r in rej_rows:
        text = " ".join(r.get(k, "") or "" for k in ("notes_csv", "notes_xlsx"))
        tags.update({f"gap:{t.lower()}" for t in GAP_RE.findall(text)})
    L += ["## Rejection reasons by gap tag", ""]
    if tags:
        L += ["| tag | rejected rows |", "|---|---|"] + [f"| {t} | {n} |" for t, n in sorted(tags.items(), key=lambda x: (-x[1], x[0]))]
        if len(rej_rows) < MIN_N:
            L.append(f"\nOnly {len(rej_rows)} rejected rows: {TOO_FEW}.")
    else:
        L.append(f"none tagged ({len(rej_rows)} rejected rows; tag a gap in the notes as gap:<tag>)")
    L += ["", "## Timing", "", f"Median days to first reply: {_median_days(rows, changelog)}", ""]
    return "\n".join(L)


def _read(path):
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _inside(path, folder):
    path, folder = os.path.realpath(path), os.path.realpath(folder)
    return path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)


def _free_name(path):
    """Never overwrite: report.md -> report_2.md, report_3.md ..."""
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(f"{stem}_{n}{ext}"):
        n += 1
    return f"{stem}_{n}{ext}"


def main(argv, env=None, cwd=None):
    env = os.environ if env is None else env
    ap = argparse.ArgumentParser(description="Funnel and patterns report (read-only on the tracker).")
    ap.add_argument("--config")
    ap.add_argument("--out")
    ap.add_argument("--today")
    a = ap.parse_args(argv)
    try:
        today = datetime.date.fromisoformat(a.today) if a.today else datetime.date.today()
        env = dict(env)
        if a.config:
            env[datadir.ENV_CONFIG] = a.config
        dd = datadir.resolve_data_dir(cwd or os.getcwd(), env)
        cfg = datadir.load_config(dd, env)
    except (datadir.DataDirError, ValueError) as e:
        print(f"error: {e}")
        return 1
    tracker = datadir.data_path(cfg, dd, "tracker")
    if not os.path.isfile(tracker):
        print(f"error: tracker not found: {tracker}")
        return 1
    tracker_dir = os.path.dirname(os.path.abspath(tracker))
    changelog_path = os.path.join(tracker_dir, "CHANGELOG.csv")
    out = a.out or os.path.join(datadir.data_path(cfg, dd, "reports"), f"funnel_{today.isoformat()}.md")
    # off-limits: the tracker, its CHANGELOG and the history/ backup folder (the tracker may sit at the data-dir root)
    if any(_inside(out, p) for p in (tracker, changelog_path, os.path.join(tracker_dir, "history"))):
        print(f"error: refusing to write the report over the tracker, its CHANGELOG or into its history/ folder "
              f"({tracker_dir}); choose another --out")
        return 1
    rows = _read(tracker)
    changelog = _read(changelog_path)
    text = build_report(rows, changelog, cfg, today)
    out = _free_name(out)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    print(f"saved: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
