#!/usr/bin/env python3
"""Read-only onboarding status, shared by setup, help and session start.

  onboarding.py status

Exit 0 with a missing-steps list (or complete); exit 1 when no data folder/config resolves.
No profile values are printed. An explicit no-links answer is recorded in the facts file
as <!-- jobsearch:links-none -->, avoiding another config key.
"""
import os
import sys

import datadir
import runtime

NO_LINKS = "<!-- jobsearch:links-none -->"


def missing_steps(cfg, data_dir):
    paths = cfg["paths"]
    missing = []
    if (cfg.get("language") or {}).get("chat") not in ("uk", "en"):
        missing.append("chat language (uk/en)")
    name = (cfg.get("identity") or {}).get("full_name")
    if not isinstance(name, str) or not name.strip():
        missing.append("confirmed identity")
    cvs = paths.get("cv_files") or []
    if not cvs or any(not os.path.isfile(os.path.join(data_dir, p)) for p in cvs):
        missing.append("English CV (paths.cv_files)")
    for key, label in (("master_cv", "labelled master CV"), ("facts", "confirmed facts")):
        p = os.path.join(data_dir, paths[key])
        if not os.path.isfile(p) or not os.path.getsize(p):
            missing.append(label)
    bases = (cfg.get("letters") or {}).get("base_letters") or []
    kb = os.path.join(data_dir, paths["letter_kb"])
    has_text = os.path.isfile(kb) and os.path.getsize(kb) > 0
    if os.path.isdir(kb):
        has_text = any(os.path.isfile(os.path.join(kb, n)) and os.path.getsize(os.path.join(kb, n)) > 0
                       for n in os.listdir(kb))
    missing_base = not bases or not has_text
    for base in bases:
        if isinstance(base, dict):
            p = os.path.join(kb, str(base.get("path") or ""))
            missing_base |= not os.path.isfile(p) or not os.path.getsize(p)
    if missing_base:
        missing.append("agreed base cover letter")
    if not (cfg.get("identity") or {}).get("links"):
        try:
            with open(os.path.join(data_dir, paths["facts"]), encoding="utf-8") as f:
                answered_none = NO_LINKS in f.read()
        except OSError:
            answered_none = False
        if not answered_none:
            missing.append("links for letters (or explicit none)")
    if not (cfg.get("targets") or {}).get("roles"):
        missing.append("target roles")
    return missing


def status(cfg, data_dir):
    missing = missing_steps(cfg, data_dir)
    return ("Setup status: incomplete\n" + "\n".join("- " + s for s in missing)
            + f"\nContinue with {runtime.command('jobsearch-setup')} update.") if missing else "Setup status: complete"


def main(argv=None, env=None, cwd=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv != ["status"]:
        print(__doc__)
        return 2
    try:
        env = os.environ if env is None else env
        d = datadir.resolve_data_dir(cwd or os.getcwd(), env)
        cfg = datadir.load_config(d, env)
        for w in cfg.get("_warnings", []):
            print(f"Warning: {w}")
        print(status(cfg, d))
        return 0
    except (datadir.DataDirError, ValueError, OSError, TypeError) as e:
        print(f"Setup status unavailable: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
