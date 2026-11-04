#!/usr/bin/env python3
"""Data-dir resolver and config loader (stdlib only).

  datadir.py show              print the resolved data dir, config path, the effective absolute paths.*
                               (one 'key: path' per line) and warnings
  datadir.py validate [PATH]   exit 1 if the config is not a mapping or has keys the schema does not know
                               (PATH defaults to the resolved config)

Precedence for the data dir: env JOBSEARCH_DATA_DIR, then a .jobsearch-data marker file in the
current project, then the current project if it holds jobsearch.config.yaml. Otherwise stop.
Never creates folders, never guesses.
"""
import copy
import json
import os
import re
import sys

import runtime

ENV_DIR, ENV_CONFIG, MARKER = "JOBSEARCH_DATA_DIR", "JOBSEARCH_CONFIG", ".jobsearch-data"
CONFIG_NAMES = ("jobsearch.config.yaml", "jobsearch.config.json")


class DataDirError(Exception):
    pass


DEFAULTS = {
    "identity": {"full_name": "", "short_name": "", "emails": [], "phones": [], "handles": [], "links": [], "extra_private_terms": []},
    "privacy": {"approved_destinations": []},
    "language": {"chat": "", "files": "en"},
    "paths": {
        "facts": "profile/facts.md", "master_cv": "profile/master_cv/MASTER_CONTENT.md", "cv_files": [],
        "letter_kb": "cover_letters/", "tracker": "tracker/vacancies.csv", "applications": "applications/",
        "ranked": "vacancies/ranked/", "story_bank": "interview/story_bank.md", "reports": "reports/",
        "start_file": "START_HERE.md", "todo_file": "TODO.md", "study_library": [],
        "scan_state": "reports/scan_state.json",
    },
    "tracker": {"id_prefix": "VAC-", "decided_by_label": "DECIDED_BY_USER", "statuses": "default"},
    "targets": {"roles": [], "roles_selective": [], "roles_not_primary": [], "domains_priority": [], "formats": [],
                "country": "any", "remote": "any"},
    "blockers": [],
    "match_weights": {"must_have": 60, "nice_to_have": 10, "seniority": 10, "domain": 10, "format_salary": 10},
    "thresholds": {"apply": 80, "decline": 65},
    "portals": {"job_portals": [], "confirmed_domains": [], "scan_approved": [],
                "employer_ats": ["greenhouse", "lever", "workable", "ashby", "recruitee", "personio",
                                 "teamtailor", "smartrecruiters", "breezy"]},
    "honesty": {
        "never_claim": [], "allowed_exceptions": [],
        "restricted_tools": {"pattern": "", "disclaimer_pattern": "", "cv_forbidden": True},
        "tool_dictionary": [], "allowed_numbers": [], "allowed_year_claims": [], "known_risk_lines": [],
    },
    "letters": {"words_min": 150, "words_max": 320, "salutation": "", "forbidden_openers": [],
                "forbidden_buzzwords": [], "no_long_dash": True, "signature_lines": [], "base_letters": []},
    "followup": {"default_days": 10, "window_days": [3, 7], "max_followups": 2},
    "interview": {"redflag_checks": []},
    "alt_flow": {"scanner": {"enabled": False, "delay_seconds": 5, "max_requests_per_run": 30}, "apply_assistant": {"enabled": False}, "reply_watch": {"enabled": False}},
    "publish_gate": {"allow": []},
}


# ---------------------------------------------------------------- data dir

def project_root(cwd):
    """Find config/marker from a nested cwd, without crossing the nearest git boundary."""
    here = os.path.abspath(cwd)
    while True:
        if (os.path.lexists(os.path.join(here, MARKER))
                or any(os.path.isfile(os.path.join(here, n)) for n in CONFIG_NAMES)):
            return here
        parent = os.path.dirname(here)
        if parent == here or os.path.lexists(os.path.join(here, ".git")):
            return None
        here = parent


def resolve_data_dir(cwd, env):
    d = env.get(ENV_DIR)
    if d:
        if not os.path.isdir(d):
            raise DataDirError(f"{ENV_DIR} points to '{d}', which is not an existing folder. Create it or fix the variable.")
        return d
    root = project_root(cwd)
    if root:
        marker = os.path.join(root, MARKER)
        if os.path.lexists(marker):
            try:
                with open(marker, encoding="utf-8") as f:
                    d = f.read().strip()
            except OSError as ex:
                raise DataDirError("The data-folder marker cannot be read; repair it before continuing.") from ex
            d = os.path.join(root, os.path.expanduser(d)) if d else ""
            if not d or not os.path.isdir(d):
                raise DataDirError(f"Marker file {marker} points to '{d}', which is not an existing folder.")
            return d
        return root
    raise DataDirError(
        "No data folder found. Set it up in one of three ways:\n"
        f"  1. export {ENV_DIR}=/path/to/your/data\n"
        f"  2. put a file named {MARKER} in this project, containing the path to your data folder\n"
        f"  3. keep a {CONFIG_NAMES[0]} in this project's root\n"
        f"Run {runtime.command('jobsearch-setup')} to create one from the plugin's config template. The tool never guesses a folder.")


def config_path(data_dir, env):
    if env.get(ENV_CONFIG):
        return env[ENV_CONFIG]
    for name in CONFIG_NAMES:
        p = os.path.join(data_dir, name)
        if os.path.isfile(p):
            return p
    return os.path.join(data_dir, CONFIG_NAMES[0])


# ---------------------------------------------------------------- YAML subset

def _opens_quote(s, i):
    """A quote opens a string only at the start of a token: user's, team's stay plain text."""
    return s[i] in "\"'" and (i == 0 or s[i - 1] in " \t[{,:")


def _strip_comment(s):
    q = None
    for i, c in enumerate(s):
        if q:
            if c == q:
                q = None
        elif _opens_quote(s, i):
            q = c
        elif c == "#" and (i == 0 or s[i - 1] in " \t"):
            return s[:i]
    return s


def _split_top(s):
    """Split on commas that are outside quotes and brackets."""
    parts, depth, q, cur = [], 0, None, ""
    for i, c in enumerate(s):
        if q:
            q = None if c == q else q
        elif _opens_quote(s, i):
            q = c
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
        elif c == "," and depth == 0:
            parts.append(cur)
            cur = ""
            continue
        cur += c
    if cur.strip():
        parts.append(cur)
    return parts


def _key_split(s):
    """Return (key, rest) for 'key: rest' / 'key:', else None. Colon must be outside quotes."""
    q = None
    for i, c in enumerate(s):
        if q:
            q = None if c == q else q
        elif _opens_quote(s, i):
            q = c
        elif c in "[{":
            return None
        elif c == ":" and (i + 1 == len(s) or s[i + 1] in " \t"):
            return _scalar(s[:i].strip()), s[i + 1:].strip()
    return None


def _scalar(s):
    s = s.strip()
    if s.startswith("[") and s.endswith("]"):
        return [_scalar(p) for p in _split_top(s[1:-1])]
    if s.startswith("{") and s.endswith("}"):
        out = {}
        for p in _split_top(s[1:-1]):
            kv = _key_split(p.strip())
            if not kv:
                raise ValueError(f"bad flow map entry: {p!r}")
            out[kv[0]] = _scalar(kv[1]) if kv[1] else None
        return out
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1].replace('\\"', '"').replace("\\\\", "\\") if s[0] == '"' else s[1:-1]
    low = s.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "~", ""):
        return None
    if re.fullmatch(r"[-+]?\d+", s):
        return int(s)
    if re.fullmatch(r"[-+]?\d*\.\d+", s):
        return float(s)
    return s


def parse_yaml_subset(text):
    lines = []
    for raw in text.splitlines():
        body = _strip_comment(raw.replace("\t", "    ")).rstrip()
        if body.strip():
            lines.append((len(body) - len(body.lstrip()), body.strip()))
    if not lines:
        return {}
    val, i = _block(lines, 0, lines[0][0])
    if i != len(lines):
        raise ValueError(f"unexpected indentation near: {lines[i][1]!r}")
    return val


def _block(lines, i, indent):
    if lines[i][1].startswith("- ") or lines[i][1] == "-":
        return _list(lines, i, indent)
    return _map(lines, i, indent)


def _map(lines, i, indent):
    out = {}
    while i < len(lines) and lines[i][0] == indent and not lines[i][1].startswith("- "):
        kv = _key_split(lines[i][1])
        if not kv:
            raise ValueError(f"expected 'key: value' (the config must be a mapping), got: {lines[i][1]!r}")
        key, rest = kv
        i += 1
        if rest:
            out[key] = _scalar(rest)
        elif i < len(lines) and (lines[i][0] > indent or (lines[i][0] == indent and lines[i][1].startswith("- "))):
            out[key], i = _block(lines, i, lines[i][0])
        else:
            out[key] = None
    return out, i


def _list(lines, i, indent):
    out = []
    while i < len(lines) and lines[i][0] == indent and (lines[i][1].startswith("- ") or lines[i][1] == "-"):
        item = lines[i][1][1:].strip()
        i += 1
        kv = _key_split(item) if item else None
        if kv:  # block map starting on the dash line; continues at deeper indent
            sub = [(indent + 2, item)]
            while i < len(lines) and lines[i][0] > indent:
                sub.append(lines[i])
                i += 1
            val, j = _map(sub, 0, indent + 2)
            if j != len(sub):
                raise ValueError(f"inconsistent indentation in list item near: {sub[j][1]!r}")
            out.append(val)
        else:
            out.append(_scalar(item) if item else None)
    return out, i


# ---------------------------------------------------------------- config

def _merge(base, over):
    if isinstance(base, dict) and isinstance(over, dict):
        out = copy.deepcopy(base)
        for k, v in over.items():
            if v is None and isinstance(base.get(k), dict):
                continue  # bare "section:" keeps the defaults
            out[k] = _merge(base[k], v) if k in base else copy.deepcopy(v)
        return out
    return copy.deepcopy(over)


def _read(path):
    with open(path, encoding="utf-8-sig") as f:
        text = f.read()
    return json.loads(text) if path.endswith(".json") else parse_yaml_subset(text)


def load_config(data_dir, env):
    p = config_path(data_dir, env)
    cfg = copy.deepcopy(DEFAULTS)
    if not os.path.isfile(p):
        cfg["_warnings"] = [f"config file not found: {p}; using neutral defaults"]
        return cfg
    user = _read(p)
    if user is not None and not isinstance(user, dict):
        raise DataDirError(f"config {p} must be a mapping at the top level")
    return _merge(cfg, user or {})


def data_path(cfg, data_dir, key):
    return os.path.join(data_dir, cfg["paths"][key])


# keys whose value must be one of a fixed set (the vacancy location filter of /rank)
CHOICES = {("targets", "country"): ("any", "ukraine", "not_ukraine"), ("targets", "remote"): ("any", "yes", "no"),
           ("language", "chat"): ("", "uk", "en")}


def privacy_problems(user):
    """Validate identity links and exact outbound destination grants. No network calls."""
    from urllib.parse import urlsplit
    bad = []
    identity = user.get("identity") or {}
    if not isinstance(identity, dict):
        bad.append("identity must be a mapping")
    else:
        links = identity.get("links", [])
        if not isinstance(links, list):
            bad.append("identity.links must be a list")
        else:
            for item in links:
                if not isinstance(item, dict) or set(item) != {"label", "url"}:
                    bad.append("identity.links items need label and url")
                    continue
                try:
                    url = urlsplit(str(item.get("url") or ""))
                except ValueError:
                    bad.append("identity.links contains an invalid URL")
                    continue
                if (not isinstance(item["label"], str) or not item["label"].strip()
                        or url.scheme not in ("http", "https") or not url.hostname
                        or url.username or url.password):
                    bad.append("identity.links needs a non-empty label and an HTTP(S) URL without credentials")
    privacy = user.get("privacy") or {}
    if not isinstance(privacy, dict):
        return bad + ["privacy must be a mapping"]
    entries = privacy.get("approved_destinations", [])
    if not isinstance(entries, list):
        return bad + ["privacy.approved_destinations must be a list"]
    for e in entries:
        if not isinstance(e, dict):
            bad.append("privacy.approved_destinations items must be mappings")
            continue
        kind = e.get("type")
        key = {"git_private_repo": "remote", "mcp_tool": "tool", "host": "host"}.get(kind)
        value = e.get(key) if key else None
        if not key or set(e) != {"type", key} or not isinstance(value, str):
            bad.append("privacy.approved_destinations needs type and its remote, tool or host")
        elif kind == "git_private_repo" and not re.fullmatch(r"[A-Za-z0-9.-]+/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value):
            bad.append("git_private_repo remote must be host/owner/repo, without URL credentials or .git")
        elif kind == "git_private_repo" and value.endswith(".git"):
            bad.append("git_private_repo remote must omit .git")
        elif kind == "mcp_tool" and not re.fullmatch(r"mcp__[A-Za-z0-9_-]+__[A-Za-z0-9_-]+", value):
            bad.append("mcp_tool must name one exact MCP tool")
        elif kind == "host" and not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", value):
            bad.append("host must be an exact hostname, without a scheme, wildcard or path")
    return bad


def bad_choices(user):
    out = []
    for sec in {s for s, _ in CHOICES}:
        if sec in user and user[sec] is not None and not isinstance(user[sec], dict):
            out.append(f"{sec} must be a mapping")
    for (sec, key), allowed in CHOICES.items():
        val = (user.get(sec) or {}).get(key) if isinstance(user.get(sec), dict) else None
        if val is not None and val not in allowed:
            out.append(f"{sec}.{key} = {val!r} (allowed: {', '.join(allowed)})")
    return out


SCAN_SOURCE_RE = re.compile(r"^(greenhouse|lever):([a-z0-9][a-z0-9-]*)\Z")  # A1: first-version source types
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def scan_entry_problems(entry):
    """Why a portals.scan_approved entry is not usable (empty list = usable)."""
    if not isinstance(entry, dict):
        return ["not a mapping"]
    out = []
    if not SCAN_SOURCE_RE.match(str(entry.get("source") or "")):
        out.append("source must be greenhouse:<board> or lever:<company>")
    if entry.get("robots") != "ALLOWED":
        out.append("robots must be ALLOWED (run the approve step)")
    for k in ("tos_checked", "approved_by_user"):
        if not _DATE.match(str(entry.get(k) or "")):
            out.append(f"{k} must be a date YYYY-MM-DD")
    return out


def unknown_keys(user, schema, prefix=""):
    """Dotted paths of mapping keys absent from the schema. Lists and free-form values are not checked."""
    bad = []
    if isinstance(user, dict) and isinstance(schema, dict):
        for k, v in user.items():
            if k not in schema:
                bad.append(prefix + str(k))
            else:
                bad += unknown_keys(v, schema[k], f"{prefix}{k}.")
    return bad


# ---------------------------------------------------------------- CLI

def main(argv, env=None, cwd=None):
    env = os.environ if env is None else env
    cwd = cwd or os.getcwd()
    if not argv or argv[0] not in ("show", "validate"):
        print(__doc__)
        return 2
    try:
        if argv[0] == "validate" and len(argv) > 1:
            path = argv[1]
        else:
            d = resolve_data_dir(cwd, env)
            path = config_path(d, env)
            if argv[0] == "show":
                cfg = load_config(d, env)
                print(f"data dir:    {d}\nconfig path: {path}\npaths:")
                for key, val in cfg["paths"].items():
                    vals = val if isinstance(val, list) else [val]
                    shown = [os.path.abspath(os.path.join(d, os.path.expanduser(str(v)))) for v in vals if str(v or "").strip()]
                    print(f"  {key}: {', '.join(shown) if shown else '(none)'}")
                for w in cfg.get("_warnings", []):
                    print(f"warning: {w}")
                return 0
        if not os.path.isfile(path):
            print(f"config file not found: {path}")
            return 1
        user = _read(path)
    except (DataDirError, ValueError) as e:
        print(f"error: {e}")
        return 1
    if user is not None and not isinstance(user, dict):
        print(f"error: config {path} must be a mapping at the top level (got a {type(user).__name__})")
        return 1
    bad = unknown_keys(user, DEFAULTS)
    if bad:
        print("unknown config keys: " + ", ".join(bad))
        return 1
    bad = bad_choices(user or {}) + privacy_problems(user or {})
    scan = ((user or {}).get("portals") or {}).get("scan_approved") if isinstance((user or {}).get("portals"), dict) else None
    for i, e in enumerate(scan or []):
        bad += [f"portals.scan_approved[{i}]: {p}" for p in scan_entry_problems(e)]
    if bad:
        print("invalid config values: " + "; ".join(bad))
        return 1
    print(f"OK: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
