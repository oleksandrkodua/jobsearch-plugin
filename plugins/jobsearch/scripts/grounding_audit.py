#!/usr/bin/env python3
"""Deterministic part of the Factual Grounding Audit (stdlib only).

  grounding_audit.py FILE --kind letter|cv [--allowed-extra "word,word"] [--no-length]
                     [--config PATH] [--master PATH]

Checks a CV or cover-letter text (md/txt) against the master CV and the user's honesty limits.
Every rule comes from the user's config (honesty.*, letters.*); nothing personal lives in this file.
It cannot judge meaning: every WARN needs a human/Claude look. A FAIL blocks handing the text over.
The master text is paths.master_cv of the resolved data folder unless --master is given.
Exit code 1 if any FAIL, 2 if the config or master cannot be read.
Idea and checks adapted from MadsLorentzen/ai-job-search (MIT); see THIRD-PARTY-NOTICES.md.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datadir  # noqa: E402

YEAR = r"\b(?:19|20)\d{2}\b"


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def master_skills(master_text):
    """Lower-cased skills text: `SKILLS.X` — lines, else the section under a 'Skills' heading."""
    dotted = re.findall(r"`SKILLS\.[A-Z_0-9.]+` — (.+)", master_text)
    if dotted:
        return " ".join(dotted).lower()
    m = re.search(r"^#+\s*skills\b.*\n((?:(?!#).*\n?)*)", master_text, re.I | re.M)
    return m.group(1).lower() if m else ""


def _rules(entries):
    """[(pattern, why)] from a list of {pattern, why}; entries with an empty pattern are absent."""
    out = []
    for e in entries or []:
        if isinstance(e, dict) and e.get("pattern"):
            out.append((str(e["pattern"]), str(e.get("why") or "")))
        elif isinstance(e, str) and e:
            out.append((e, ""))
    return out


def _check_re(pattern, key):
    try:
        re.compile(pattern, re.I)
    except re.error as e:
        raise ValueError(f"invalid regex in config key {key}: {pattern!r} ({e})")


def _exceptions(entries):
    """[(pattern, rules)]; rules is None (applies to all rules) or a list of substrings/patterns."""
    out = []
    for i, e in enumerate(entries or []):
        if isinstance(e, dict) and e.get("pattern"):
            _check_re(str(e["pattern"]), f"honesty.allowed_exceptions[{i}].pattern")
            rules = None
            if "rules" in e:
                r = e["rules"]
                if not (isinstance(r, list) and r and all(isinstance(x, str) and x for x in r)):
                    raise ValueError(f"config key honesty.allowed_exceptions[{i}].rules must be a non-empty list of "
                                     f"non-empty strings (omit the key to apply the exception to every rule), got {r!r}")
                rules = list(r)
            out.append((str(e["pattern"]), rules))
    return out


def _covers(rules, pat, why):
    return rules is None or any(r == pat or (why and r in why) for r in rules)


def audit(text, kind, cfg, master_text, no_length=False, allowed_extra=frozenset()):
    """Return (fails, warns) for a CV or letter text. kind: 'letter' or 'cv'."""
    hon, let = cfg.get("honesty") or {}, cfg.get("letters") or {}
    never = _rules(hon.get("never_claim"))
    exceptions = _exceptions(hon.get("allowed_exceptions"))
    rt = hon.get("restricted_tools") or {}
    automation, disclaim = rt.get("pattern") or "", rt.get("disclaimer_pattern") or ""
    cv_forbidden = rt.get("cv_forbidden", True)
    tool_dict = [t for t in (hon.get("tool_dictionary") or []) if t]
    allowed_numbers = {str(x).replace(" ", "").lower() for x in (hon.get("allowed_numbers") or []) if x}
    year_claims = [c for c in (hon.get("allowed_year_claims") or []) if isinstance(c, dict) and c.get("n") not in (None, "")]
    for i, (pat, _) in enumerate(_rules(hon.get("never_claim"))):
        _check_re(pat, f"honesty.never_claim[{i}].pattern")
    for key in ("pattern", "disclaimer_pattern"):
        if rt.get(key):
            _check_re(rt[key], f"honesty.restricted_tools.{key}")
    for key in ("forbidden_openers", "forbidden_buzzwords"):
        for i, p in enumerate(let.get(key) or []):
            if p:
                _check_re(p, f"letters.{key}[{i}]")
    for i, p in enumerate(let.get("signature_lines") or []):
        if p:
            _check_re(str(p), f"letters.signature_lines[{i}]")
    facts = (cfg.get("paths") or {}).get("facts") or "the facts file"
    skills = master_skills(master_text)
    years = set(re.findall(YEAR, master_text))
    extra = {x.lower() for x in allowed_extra}
    fails, warns = [], []
    sents = sentences(text)

    if not never and not automation and not tool_dict:
        warns.append("no honesty limits configured: set honesty.* in the config so the audit has rules to check")

    # 1 placeholders left in the text
    for m in re.finditer(r"\[[A-Z][A-Z_ 0-9.\-]{2,}\]", text):
        fails.append(f"placeholder not filled: {m.group(0)}")
    # 2 long dash anywhere (letters only: CV templates use en/em dash in date ranges by design)
    if kind == "letter" and let.get("no_long_dash", True) and ("—" in text or "–" in text):
        fails.append("long dash found (use ' - ')")
    # 3 never-claim phrases; a sentence matching an allowed exception is skipped
    never += [(p, "forbidden opener") for p in (let.get("forbidden_openers") or []) if p]
    never += [(p, "forbidden buzzword") for p in (let.get("forbidden_buzzwords") or []) if p]
    for pat, why in never:
        for s in sents:
            if re.search(pat, s, re.I):
                if any(re.search(ex, s, re.I) and _covers(rl, pat, why) for ex, rl in exceptions):
                    continue
                fails.append(f"{why} -> «{s[:110]}»")
    # 4 restricted tools: allowed only inside a disclaimer sentence; never on a CV
    if automation:
        for s in sents:
            if re.search(automation, s, re.I):
                if kind == "cv" and cv_forbidden:
                    fails.append(f"CV mentions restricted tool/language (not allowed on the CV) -> «{s[:110]}»")
                elif not (disclaim and re.search(disclaim, s, re.I)):
                    fails.append(f"restricted tool claimed without the required disclaimer -> «{s[:110]}»")
                else:
                    warns.append(f"restricted tool inside a disclaimer sentence (check wording) -> «{s[:100]}»")
    # 5 tools not in the master skills list
    for t in tool_dict:
        if re.search(rf"\b{re.escape(t)}\b", text, re.I) and t.lower() not in skills and t.lower() not in extra \
                and t.lower() not in automation.lower():
            warns.append(f"tool «{t}» is not in MASTER skills: confirm with the user or remove")
    # 6 years: any 4-digit year must exist in master
    for y in sorted(set(re.findall(YEAR, text)) - years):
        warns.append(f"year {y} is not in the master CV")
    # 7 numbers with units that look like claims
    ok_years = {str(c["n"]) for c in year_claims}
    notes = "; ".join(str(c["note"]) for c in year_claims if c.get("note"))
    for m in re.finditer(r"\b(\d+)\+?\s*(years?|%|x\b|days?|bugs?|defects?)", text, re.I):
        n, unit = m.group(1), m.group(2).lower()
        if unit.startswith("year") and n in ok_years:
            warns.append(f"«{m.group(0)}»: years claim, confirm against {facts}" + (f" ({notes})" if notes else ""))
        elif unit.startswith("year") or unit in ("%", "x") or unit.startswith(("bug", "defect")):
            if m.group(0).replace(" ", "").lower() in allowed_numbers:
                continue
            fails.append(f"numeric claim not in master: «{m.group(0)}»")
    # 8 letter length (greeting and signature lines are not counted)
    if kind == "letter" and not no_length:
        lines = [r"Dear .*"] + [p for p in (let.get("signature_lines") or []) if p]
        if let.get("salutation"):
            lines.append(re.escape(str(let["salutation"])) + ".*")
        body = re.sub(r"^(?:" + "|".join(lines) + r")$", "", text, flags=re.M)
        n = len(body.split())
        lo, hi = let.get("words_min", 150), let.get("words_max", 320)
        if not lo <= n <= hi:
            fails.append(f"letter length {n} words (norm {lo}-{hi})")
    return fails, warns


def main(argv=None, env=None, cwd=None):
    env = dict(os.environ if env is None else env)
    cwd = cwd or os.getcwd()
    ap = argparse.ArgumentParser(description="Deterministic grounding audit of a CV or letter.")
    ap.add_argument("file")
    ap.add_argument("--kind", choices=["letter", "cv"], required=True)
    ap.add_argument("--allowed-extra", default="", help="tools the user confirmed for THIS check, comma separated")
    ap.add_argument("--no-length", action="store_true", help="skip the word-count check (follow-up drafts)")
    ap.add_argument("--config", help="config file (default: the resolved data folder's config)")
    ap.add_argument("--master", help="master CV text file (default: paths.master_cv)")
    a = ap.parse_args(argv)
    if a.config:
        env[datadir.ENV_CONFIG] = a.config
    try:
        try:
            dd = datadir.resolve_data_dir(cwd, env)
        except datadir.DataDirError:
            if not a.config:
                raise
            dd = os.path.dirname(os.path.abspath(a.config))
        cfg = datadir.load_config(dd, env)
        master_path = a.master or datadir.data_path(cfg, dd, "master_cv")
        if not os.path.isfile(master_path):
            raise datadir.DataDirError(f"master CV not found: {master_path}")
        with open(master_path, encoding="utf-8") as f:
            master = f.read()
        with open(a.file, encoding="utf-8") as f:
            text = f.read()
    except (datadir.DataDirError, ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    extra = {x.strip().lower() for x in a.allowed_extra.split(",") if x.strip()}
    try:
        fails, warns = audit(text, a.kind, cfg, master, a.no_length, extra)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"GROUNDING AUDIT: {os.path.basename(a.file)} ({a.kind})")
    for x in fails:
        print("  FAIL ", x)
    for x in warns:
        print("  WARN ", x)
    print(f"RESULT: {'FAIL' if fails else 'PASS'}  ({len(fails)} fail, {len(warns)} warn)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
