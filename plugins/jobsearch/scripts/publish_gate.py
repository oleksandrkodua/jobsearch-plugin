#!/usr/bin/env python3
"""Publish gate: proves the repo (tree + full git history + commit metadata) holds none of the
user's private identity values. Stdlib only.

  publish_gate.py [--repo .] [--config PATH] [--data-dir PATH] [--allow-binary GLOB ...]

The patterns come from the user's PRIVATE config (identity.* and extra_private_terms; --config PATH or
env JOBSEARCH_CONFIG), so this script contains no personal value and cannot match itself.
The data-dir path (--data-dir PATH, else env JOBSEARCH_DATA_DIR) is matched as written and in its ~/ form.
publish_gate.allow in the config lists per-file exceptions {path, value}: a hit is skipped only when it sits in
the content of that exact file AND the matched text is inside value (case-insensitive). Hits in other files,
commit metadata, ref names and file names are never skipped.

Exit codes: 0 PASS (zero hits) | 1 hits | 2 SKIPPED (no config, identity empty or yields no pattern; never a pass)
            | 3 error: unreadable config, bad repo, or git failure.
Hits print as `FAIL <kind> <where> <masked>`; a value is masked to its first and last character.
"""
import argparse
import collections
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datadir  # noqa: E402
import fnmatch  # noqa: E402

Hit = collections.namedtuple("Hit", "where kind masked")

# one source of truth for "secret-looking string"; evals/validate_repo.py check 7 imports it
SECRET_RE = re.compile(
    r"(AKIA[0-9A-Z]{16}|xox[baprs]-[0-9A-Za-z-]{10,}|ghp_[0-9A-Za-z]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|(?i:password|passwd|api[_-]?key|secret|token)\s*[:=]\s*['\"](?![$<{])[^'\"\s]{8,})")
PRIVATE_ROOTS = ("tracker", "applications", "profile")
SEP = r"[\s.\-()/+_]*"


def mask(s):
    s = str(s)
    return "**" if len(s) <= 2 else f"{s[0]}***{s[-1]}"


def _clean(v):
    """A scalar string counts as a one-item list; any other non-list type is a config error."""
    if v is None:
        return []
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, (list, tuple)):
        raise datadir.DataDirError("identity list fields must be lists or strings")
    if any(isinstance(x, (dict, list, tuple)) for x in v):
        raise datadir.DataDirError("identity list items must be scalars")
    return [str(x).strip() for x in v if str(x).strip()]


def _word(term):
    """Whole-word, case-insensitive; between the words of a term: whitespace, dot, underscore or hyphen."""
    words = [w for w in re.split(r"[\s._-]+", term) if w]
    if not any(re.search(r"\w", w) for w in words):
        return None  # only separators: would match the empty string everywhere
    body = r"[\s._-]+".join(re.escape(w) for w in words)
    return re.compile(r"(?<!\w)" + body + r"(?!\w)", re.I)


def build_patterns(identity, extra_terms, data_dir, home=None):
    pats = []

    def add(kind, term):
        rx = _word(term)
        if rx is not None:
            pats.append((kind, rx))

    for key in ("full_name", "short_name"):
        v = identity.get(key)
        if v is not None and not isinstance(v, str):
            raise datadir.DataDirError(f"identity.{key} must be a string")
        v = (v or "").strip()
        if len(v) >= 2:
            add("name", v)
    for h in _clean(identity.get("handles")):
        add("handle", h)
        bare = h.lstrip("@")
        if bare != h and len(bare) >= 3:  # github.com/<handle>, bare mentions
            add("handle", bare)
    for t in _clean(extra_terms):
        if len(t) >= 2:
            add("term", t)
    for e in _clean(identity.get("emails")):
        add("email", e)
        local = e.split("@", 1)[0]
        if len(local) >= 3:
            add("email", local)
    for p in _clean(identity.get("phones")):
        digits = re.sub(r"\D", "", p)
        if len(digits) < 4:
            continue
        pats.append(("phone", re.compile(r"(?<!\d)" + digits + r"(?!\d)")))
        pats.append(("phone", re.compile(r"(?<!\d)" + SEP.join(digits) + r"(?!\d)")))
        if len(digits) > 7:  # the last 7 digits, bare or separated: drops country/area prefix variants
            tail = digits[-7:]
            pats.append(("phone", re.compile(tail)))
            pats.append(("phone", re.compile(SEP.join(tail))))
    d = (data_dir or "").strip().rstrip("/\\")
    if len(d) >= 4:
        pats.append(("datadir", re.compile(re.escape(d), re.I)))
        h = (home or os.path.expanduser("~")).rstrip("/\\")
        if len(h) >= 2 and d.startswith(h + "/") and len(d) - len(h) >= 4:  # the ~/... form of the same folder
            pats.append(("datadir", re.compile(re.escape("~" + d[len(h):]), re.I)))
    return pats


class Allow:
    """publish_gate.allow: per-file exceptions; counts the hits it skipped."""

    def __init__(self, entries):
        self.entries = [(e["path"].strip().removeprefix("./"), e["value"].lower()) for e in entries]
        self.used = set()

    def permits(self, path, text, key):
        for p, v in self.entries:
            if path == p and text.lower() in v:
                self.used.add(key)
                return True
        return False


def parse_allow(cfg_gate):
    if cfg_gate is None:
        return []
    if not isinstance(cfg_gate, dict):
        raise datadir.DataDirError("publish_gate must be a mapping")
    allow = cfg_gate.get("allow")
    if allow is None:
        return []
    if not isinstance(allow, list):
        raise datadir.DataDirError("publish_gate.allow must be a list of {path, value}")
    for e in allow:
        if not (isinstance(e, dict) and isinstance(e.get("path"), str) and isinstance(e.get("value"), str)
                and e["path"].strip() and e["value"].strip()):
            raise datadir.DataDirError("each publish_gate.allow item needs a non-empty path and value")
    return allow


def _safe(where, patterns):
    """A path in `where` can itself hold a private value: mask every matched span."""
    for _, rx in list(patterns) + [("secret", SECRET_RE)]:
        where = rx.sub(lambda m: mask(m.group(0)), where)
    return where


def _scan_line(line, where, patterns, hits, secrets=True, path=None, allow=None):
    """`path` is set only for file CONTENT; only then may `allow` skip a hit (never for secrets)."""
    for kind, rx in patterns:
        for m in rx.finditer(line):
            if allow is not None and path is not None and allow.permits(path, m.group(0), (where, kind, m.start())):
                continue
            hits.append(Hit(_safe(where, patterns), kind, mask(m.group(0))))
            break
    if secrets:
        m = SECRET_RE.search(line)
        if m:
            hits.append(Hit(_safe(where, patterns), "secret", mask(m.group(0))))


def _git(repo, *args):
    # neutralise user git config that changes what a log shows or how it is laid out
    cfg = ["core.quotepath=off", "log.showRoot=true", "diff.noprefix=false", "diff.mnemonicPrefix=false",
           "diff.renames=false", "color.ui=false", "log.mailmap=false"]
    r = subprocess.run(["git", *[x for c in cfg for x in ("-c", c)], "-C", repo, *args], capture_output=True)
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")


def _tree_files(repo):
    rc, out, err = _git(repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if rc != 0:
        raise RuntimeError("git ls-files failed: " + err.strip()[:200])
    return sorted({f for f in out.split("\0") if f})


def _private_root_hits(repo):
    hits = []
    for name in PRIVATE_ROOTS:
        p = os.path.join(repo, name)
        if os.path.isdir(p) and os.listdir(p):
            hits.append(Hit(name + "/", "private-folder", name + "/"))
    return hits


def scan_tree(repo, patterns, allow_binary=(), allow=None):
    hits = _private_root_hits(repo)
    for rel in _tree_files(repo):
        _scan_line(rel, rel, patterns, hits, secrets=False)  # file names too
        p = os.path.join(repo, rel)
        if not os.path.isfile(p) or os.path.islink(p):
            continue
        with open(p, "rb") as f:
            data = f.read()
        if b"\0" in data:
            # cannot be proven clean as text: decode every plausible way, and still fail unless allowed
            if not any(fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(os.path.basename(rel), g) for g in allow_binary):
                hits.append(Hit(_safe(rel, patterns), "unscanned-binary", "binary"))
            decodings = [data.decode("latin-1"), data.decode("utf-16-le", "replace"), data.decode("utf-16-be", "replace")]
        else:
            decodings = [data.decode("utf-8", "replace")]
        for text in decodings:
            for n, line in enumerate(text.split("\n"), 1):
                _scan_line(line, f"{rel}:{n}", patterns, hits, path=rel, allow=allow)
    return _uniq(hits)


def _uniq(hits):
    seen, out = set(), []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def _scan_text(text, where, patterns, hits):
    for n, line in enumerate(text.split("\n"), 1):
        _scan_line(line, f"{where}:{n}", patterns, hits)
        if "\x00" in line:  # UTF-16
            _scan_line(line.replace("\x00", ""), f"{where}:{n}", patterns, hits)


def _scan_tag_target(repo, ref, patterns, hits):
    """`git log --all` only walks commits: a tag may point straight at a blob or a tree."""
    rc, oid, _ = _git(repo, "rev-parse", "--verify", "-q", ref + "^{}")
    oid = oid.strip()
    if rc != 0 or not oid:
        return
    typ = _git(repo, "cat-file", "-t", oid)[1].strip()
    safe = _safe(ref, patterns)
    if typ == "blob":
        _scan_text(_git(repo, "cat-file", "blob", oid)[1], f"{safe}:blob", patterns, hits)
    elif typ == "tree":
        rc, out, err = _git(repo, "ls-tree", "-r", "-z", oid)
        if rc != 0:
            raise RuntimeError("git ls-tree failed: " + err.strip()[:200])
        for ent in out.split("\0"):
            meta, _, path = ent.partition("\t")
            parts = meta.split()
            if len(parts) != 3:
                continue
            _scan_line(path, f"{safe}:{path}", patterns, hits, secrets=False)
            if parts[1] == "blob":
                _scan_text(_git(repo, "cat-file", "blob", parts[2])[1], f"{safe}:{path}", patterns, hits)


# Claude Code's own local checkpoint refs: snapshots for rewind, never pushed, and they keep pre-rewrite
# history reachable. Every other ref (branches, tags, stash, remotes, notes) is still scanned.
CHECKPOINT_PREFIX = "refs/time-machine/"
CHECKPOINTS = f"--exclude={CHECKPOINT_PREFIX}*"


def scan_history(repo, patterns, allow=None):
    hits = []
    empty = ("does not have any commits", "bad default revision")
    # NUL separates fields and records: git names and messages cannot contain NUL, so nothing can break the split
    rc, out, err = _git(repo, "log", CHECKPOINTS, "--all", "--format=%x00%H%x00%an%x00%ae%x00%cn%x00%ce%x00%B")
    if rc != 0:
        if any(e in err for e in empty):
            return hits
        raise RuntimeError("git log failed: " + err.strip()[:200])
    toks = out.split("\0")[1:]
    if len(toks) % 6:
        raise RuntimeError("unexpected git log output (commit metadata)")
    for k in range(0, len(toks), 6):
        sha, *fields = toks[k:k + 6]
        for i, field in enumerate(fields):
            for line in field.split("\n"):
                _scan_line(line, f"{sha[:10]}:{'meta' if i < 4 else 'message'}", patterns, hits)
    # refs: names of every branch/tag, annotated-tag tagger and message, content of tags that point at a blob/tree
    rc, out, err = _git(repo, "for-each-ref", "--format=%(refname)%00%(taggername)%00%(taggeremail)%00%(contents)%00")
    if rc != 0:
        raise RuntimeError("git for-each-ref failed: " + err.strip()[:200])
    toks = out.split("\0")[:-1]
    if len(toks) % 4:
        raise RuntimeError("unexpected git for-each-ref output")
    for k in range(0, len(toks), 4):
        ref, *fields = toks[k:k + 4]
        ref = ref.lstrip("\n")
        if ref.startswith(CHECKPOINT_PREFIX):
            continue
        for i, field in enumerate([ref, *fields]):
            for line in field.split("\n"):
                _scan_line(line, f"ref:{_safe(ref, patterns)}:{('name', 'tagger', 'tagger', 'message')[i]}", patterns, hits)
        if ref.startswith("refs/tags/"):
            _scan_tag_target(repo, ref, patterns, hits)
    # every path ever touched (merges and stashes included); -z makes each token one exact path or marker
    rc, out, err = _git(repo, "log", CHECKPOINTS, "--all", "--diff-merges=separate", "--no-renames", "--name-only", "-z", "--format=@@C@@%H")
    if rc != 0:
        raise RuntimeError("git log --name-only failed: " + err.strip()[:200])
    sha = "?"
    for tok in out.split("\0"):
        name = tok.lstrip("\n")
        if re.fullmatch(r"@@C@@[0-9a-f]{40,64}", name):
            sha = name[5:15]
            continue
        if not name:
            continue
        _scan_line(name, f"{sha}:{name}", patterns, hits, secrets=False)
        root = name.split("/", 1)[0]
        if "/" in name and root in PRIVATE_ROOTS:
            hits.append(Hit(f"{sha}:{root}/", "private-folder", root + "/"))
    # content: every added line of every diff, whatever the path parsing says
    rc, out, err = _git(repo, "log", "-p", CHECKPOINTS, "--all", "--diff-merges=separate", "--no-renames", "--text", "--no-textconv",
                        "--no-color", "--no-ext-diff", "--format=@@COMMIT@@%H")
    if rc != 0:
        raise RuntimeError("git log -p failed: " + err.strip()[:200])
    sha, path, lineno, in_header = "", "?", 0, False
    for line in out.split("\n"):  # not splitlines(): \r, \f, \x85 ... are not git line ends
        if line.startswith("@@COMMIT@@"):
            sha, path, lineno, in_header = line[10:20], "?", 0, False
        elif line.startswith(("diff --git ", "diff --cc ")):
            in_header, path = True, "?"
        elif in_header:
            if line.startswith("+++ "):
                path = line[4:]
                path = path[2:] if path.startswith("b/") else path
            elif line.startswith("@@ "):
                in_header = False
                m = re.match(r"@@+ (?:-\d+(?:,\d+)? )+\+(\d+)", line)
                lineno = int(m.group(1)) if m else 0
        elif line.startswith("@@ "):
            m = re.match(r"@@+ (?:-\d+(?:,\d+)? )+\+(\d+)", line)
            lineno = int(m.group(1)) if m else 0
        elif line.startswith("+"):
            where = f"{sha}:{path}:{lineno}"
            _scan_line(line[1:], where, patterns, hits, path=path, allow=allow)
            if "\x00" in line:  # UTF-16 content: NULs between the letters
                _scan_line(line[1:].replace("\x00", ""), where, patterns, hits, path=path, allow=allow)
            lineno += 1
        elif line.startswith(" "):
            lineno += 1
    return _uniq(hits)


def load_gate_config(config):
    """(identity, allow entries); (None, []) when there is no config file."""
    if not config or not os.path.isfile(config):
        return None, []
    user = datadir._read(config)
    if user is not None and not isinstance(user, dict):
        raise datadir.DataDirError("config must be a mapping at the top level")
    cfg = datadir._merge(datadir.DEFAULTS, user or {})
    ident = cfg["identity"]
    if not isinstance(ident, dict):
        raise datadir.DataDirError("identity must be a mapping")
    return ident, parse_allow(cfg.get("publish_gate"))


def load_identity(config):
    return load_gate_config(config)[0]


def main(argv=None, env=None):
    env = os.environ if env is None else env
    ap = argparse.ArgumentParser(description="Publish gate over tree and git history")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--config", default=env.get(datadir.ENV_CONFIG))
    ap.add_argument("--data-dir", default=env.get(datadir.ENV_DIR),
                    help="the private data folder; its path (and ~/ form) must not appear in the repo")
    ap.add_argument("--allow-binary", action="append", default=[], metavar="GLOB",
                    help="binary (NUL-containing) files matching GLOB are not reported as unscanned-binary")
    args = ap.parse_args(argv)
    try:
        ident, allow_entries = load_gate_config(args.config)
        terms = _clean(ident.get("extra_private_terms")) if ident else []
        configured = ident and (str(ident.get("full_name") or "").strip() or str(ident.get("short_name") or "").strip()
                                or any(_clean(ident.get(k)) for k in ("emails", "phones", "handles")) or terms)
    except (datadir.DataDirError, ValueError, OSError) as e:
        print(f"PUBLISH GATE: ERROR - config unreadable ({type(e).__name__})")
        return 3
    if not configured:
        print("PUBLISH GATE: SKIPPED - no private identity configured")
        return 2
    repo = os.path.abspath(args.repo)
    if not os.path.isdir(repo) or _git(repo, "rev-parse", "--git-dir")[0] != 0:
        print("PUBLISH GATE: ERROR - repo is not a git repository (history cannot be scanned)")
        return 3
    try:
        has_identity = bool(build_patterns(ident, terms, None))  # decided before the data dir path is added
        patterns = build_patterns(ident, terms, args.data_dir, env.get("HOME"))
    except datadir.DataDirError as e:
        print(f"PUBLISH GATE: ERROR - {e}")
        return 3
    if not has_identity:
        print("PUBLISH GATE: SKIPPED - no private identity configured")
        return 2
    dd = (args.data_dir or "").strip()
    print(f"data-dir check: active ({mask(dd)})" if len(dd.rstrip("/\\")) >= 4
          else "data-dir check: inactive (no --data-dir / JOBSEARCH_DATA_DIR)")
    allow = Allow(allow_entries)
    try:
        hits = scan_tree(repo, patterns, args.allow_binary, allow) + scan_history(repo, patterns, allow)
    except RuntimeError as e:
        print(f"PUBLISH GATE: ERROR - {e}")
        return 3
    if allow_entries:
        print(f"allowed: {len(allow.used)} hit(s) via publish_gate.allow")
    for h in hits:
        print(f"FAIL  {h.kind}  {h.where}  {h.masked}")
    if hits:
        print(f"PUBLISH GATE: FAIL ({len(hits)} hits)")
        return 1
    print("PUBLISH GATE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
