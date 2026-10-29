#!/usr/bin/env python3
"""Safe editor and duplicate finder for the vacancy tracker CSV (stdlib only).

  find  --company X [--position Y] [--url U] [--job-id N]   duplicate check, prints matching rows
  add   --company X --position Y --status S [--url U --date YYYY-MM-DD --note T --match N]
  set   ID FIELD VALUE [--note T]                            change one field (status is validated)
  check                                                      validate statuses and ids, print value_counts

Every write: backup to history/ next to the tracker, append to CHANGELOG.csv there, print row count and
status value_counts before/after and the list of rows whose status changed. Never deletes rows.

The tracker is the data dir's tracker file (see datadir.py). --file PATH works on any CSV without a data
dir (use it on a copy); --config PATH selects the config file (id prefix, decided-by label).
"""
import argparse, collections, copy, csv, datetime, difflib, os, re, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datadir  # noqa: E402

STATUSES = ["ACTIVE", "APPLIED", "NO_RESPONSE", "REJECTED", "DECLINED", "CLOSED", "SKIPPED", "NOT_APPLIED", "DO_NOT_APPLY", "UNKNOWN"]


class EditError(Exception):
    pass


def ck(s):
    """Comparison key: lowercase, keep only Latin, Cyrillic (incl. іїєґё) and digits."""
    return re.sub(r"[^a-zа-яіїєґё0-9]+", "", (s or "").lower())


def load(p):
    """Return (columns, rows, had_bom). Reads a UTF-8 file with or without BOM."""
    with open(p, "rb") as f:
        bom = f.read(3) == b"\xef\xbb\xbf"
    with open(p, encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f, restval="")
        return r.fieldnames or [], list(r), bom


def save(p, cols, rows, bom=False):
    with open(p, "w", encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def counts(rows):
    return dict(collections.Counter(r.get("status", "") for r in rows))


def next_id(rows, prefix):
    """prefix + 3-digit (highest numeric suffix over all ids, any prefix) + 1."""
    top = 0
    for r in rows:
        m = re.search(r"(\d+)\s*$", r.get("id", "") or "")
        if m:
            top = max(top, int(m.group(1)))
    return f"{prefix}{top + 1:03d}"


def cmd_find(a, cols, rows):
    c, p, u = ck(a.company), ck(a.position), (a.url or "").strip().rstrip("/")
    hits = []
    for r in rows:
        rc, rp = ck(r.get("company", "")), ck(r.get("position", ""))
        score = difflib.SequenceMatcher(None, c, rc).ratio() if c else 0
        same_co = bool(c) and (c in rc or rc in c or score >= 0.82)
        same_url = bool(u) and u == (r.get("url", "") or "").strip().rstrip("/")
        hay = " ".join(r.get(k, "") or "" for k in ("url", "position", "notes_xlsx", "notes_csv"))
        jid = bool(a.job_id) and a.job_id in hay
        if same_url or jid:
            kind = "ALREADY APPLIED/SEEN (URL or job id)"
        elif same_co and p and (p in rp or rp in p or difflib.SequenceMatcher(None, p, rp).ratio() >= 0.8):
            kind = "SAME COMPANY + SIMILAR POSITION"
        elif same_co:
            kind = "SAME COMPANY, other position (ask the user)"
        else:
            continue
        hits.append((kind, r))
    if not hits:
        print("NO MATCH: nothing in the tracker for this company/URL (verdict: NOT APPLIED)")
        return
    for kind, r in sorted(hits, key=lambda x: x[0]):
        print(f"{kind}\n  {r.get('id', '')} | {r.get('company', '')} | {r.get('position', '')} | {r.get('status', '')} | "
              f"applied {r.get('applied_date') or '-'} | {(r.get('url') or '')[:70]}")
    print("\nRule: exact company+position or same URL/job id = ALREADY APPLIED. Same company with different or similar title = ask the user, never decide.")


def backup(path):
    """Copy the tracker to history/ BEFORE it is written, so the backup is the previous state."""
    hist = os.path.join(os.path.dirname(os.path.abspath(path)), "history")
    os.makedirs(hist, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")   # microseconds: two edits in one second must not share a backup
    shutil.copy2(path, os.path.join(hist, f"vacancies_{stamp}.csv"))
    return stamp


def log_and_report(path, stamp, rows_before, rows_after, change_rows):
    tdir = os.path.dirname(os.path.abspath(path))
    log = os.path.join(tdir, "CHANGELOG.csv")
    new = not os.path.exists(log)
    with open(log, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "id", "field", "old", "new", "note"])
        for ch in change_rows:
            w.writerow([stamp] + list(ch))
    print(f"backup: history/vacancies_{stamp}.csv")
    print(f"rows before/after: {len(rows_before)} / {len(rows_after)}")
    print(f"status value_counts before: {counts(rows_before)}")
    print(f"status value_counts after : {counts(rows_after)}")
    chg = [(r0.get("id", ""), r0.get("status", ""), r1.get("status", "")) for r0, r1 in zip(rows_before, rows_after)
           if r0.get("status", "") != r1.get("status", "")]
    print(f"rows whose status changed: {chg or 'none'}")


def _need_status(s):
    if s not in STATUSES:
        raise EditError(f"invalid status {s}; valid: {STATUSES}")


def cmd_add(a, cols, rows, path, bom, cfg):
    _need_status(a.status)
    t = cfg["tracker"]
    before = [dict(r) for r in rows]
    r = {c: "" for c in cols}
    r.update({"id": next_id(rows, t["id_prefix"]), "company": a.company, "position": a.position, "url": a.url or "",
              "status": a.status, "status_confidence": t["decided_by_label"], "needs_review": "N",
              "applied_date": a.date or "", "match_pct": a.match or "", "notes_csv": a.note or "",
              "sources": f"manual:{datetime.date.today().isoformat()}"})
    rows.append(r)
    stamp = backup(path)
    save(path, cols, rows, bom)
    log_and_report(path, stamp, before, rows, [(r["id"], "ROW", "", f"{a.company} / {a.position} / {a.status}", a.note or "")])
    print("added", r["id"])


def cmd_set(a, cols, rows, path, bom, cfg):
    row = next((r for r in rows if r.get("id") == a.id), None)
    if not row:
        raise EditError(f"no such id {a.id}")
    if a.field not in cols:
        raise EditError(f"no such column {a.field}")
    if a.field == "status":
        _need_status(a.value)
    before = [dict(r) for r in rows]
    old = row.get(a.field, "")
    row[a.field] = a.value
    if a.field == "status":
        row.update({"status_confidence": cfg["tracker"]["decided_by_label"], "proposed_status": "", "needs_review": "N"})
    stamp = backup(path)
    save(path, cols, rows, bom)
    log_and_report(path, stamp, before, rows, [(a.id, a.field, old, a.value, a.note or "")])


def cmd_check(cols, rows):
    bad = [r.get("id", "") for r in rows if r.get("status", "") not in STATUSES]
    dup = [i for i, c in collections.Counter(r.get("id", "") for r in rows).items() if c > 1]
    print(f"rows: {len(rows)}; invalid statuses: {bad or 'none'}; duplicate ids: {dup or 'none'}")
    print("value_counts:", counts(rows))


def settings(a, env, cwd):
    """Return (config, tracker path). --file needs no data dir; the default file does."""
    env = dict(env)
    if a.config:
        env[datadir.ENV_CONFIG] = os.path.abspath(a.config)
    try:
        dd = datadir.resolve_data_dir(cwd, env)
    except datadir.DataDirError as e:
        if not a.file:
            raise
        if env.get(datadir.ENV_DIR):
            print(f"warning: data dir from {datadir.ENV_DIR} not found ({e}); with --file using defaults, "
                  f"or {datadir.ENV_CONFIG} if set", file=sys.stderr)
        dd = os.path.dirname(os.path.abspath(env[datadir.ENV_CONFIG])) if env.get(datadir.ENV_CONFIG) else None
    cfg = datadir.load_config(dd, env) if dd else copy.deepcopy(datadir.DEFAULTS)
    if a.file:
        return cfg, os.path.abspath(a.file)
    return cfg, os.path.abspath(datadir.data_path(cfg, dd, "tracker"))


def build_parser():
    ap = argparse.ArgumentParser(description="Safe tracker editor and duplicate finder.")
    ap.add_argument("--file", help="tracker CSV to work on (default: the data dir's tracker; works without a data dir)")
    ap.add_argument("--config", help="config file to use (default: the data dir's jobsearch.config.yaml)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("find")
    f.add_argument("--company", required=True)
    for x in ("--position", "--url", "--job-id"):
        f.add_argument(x, default="")
    ad = sub.add_parser("add")
    for x in ("--company", "--position", "--status", "--url", "--date", "--note", "--match"):
        ad.add_argument(x, required=x in ("--company", "--position", "--status"))
    s = sub.add_parser("set")
    s.add_argument("id")
    s.add_argument("field")
    s.add_argument("value")
    s.add_argument("--note", default="")
    sub.add_parser("check")
    return ap


def main(argv=None, env=None, cwd=None):
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    a = build_parser().parse_args(argv)
    try:
        cfg, path = settings(a, os.environ if env is None else env, cwd or os.getcwd())
        if not os.path.isfile(path):
            raise EditError(f"tracker file not found: {path}")
        cols, rows, bom = load(path)
        if a.cmd == "find":
            cmd_find(a, cols, rows)
        elif a.cmd == "add":
            cmd_add(a, cols, rows, path, bom, cfg)
        elif a.cmd == "set":
            cmd_set(a, cols, rows, path, bom, cfg)
        else:
            cmd_check(cols, rows)
    except (EditError, datadir.DataDirError, ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
