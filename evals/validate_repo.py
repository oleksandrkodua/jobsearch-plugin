#!/usr/bin/env python3
"""Structure checks for the repository. Run from the root: python3 evals/validate_repo.py
Checks structure only; says nothing about whether content is correct or the rules work.
Output: one 'PASS|FAIL <check>' line per check; exit 1 on any FAIL.
Later tasks append new checks as numbered blocks above the summary at the bottom."""
import json, os, re, sys, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
PLUGIN = "plugins/jobsearch"
problems, passed = [], 0
# skill frontmatter: name and description first, one line each; other keys only from the documented Claude Code list,
# because Claude Code ignores an unknown key without an error (a typo such as allowed_tools would do nothing)
FM = re.compile(r"---\nname: (.+)\ndescription: (.+)\n((?:(?:[A-Za-z_-]+:.*|[ \t]+.*)\n)*)---\n")
FM_KEYS = {"when_to_use", "argument-hint", "arguments", "disable-model-invocation", "user-invocable", "allowed-tools",
           "disallowed-tools", "model", "effort", "context", "agent", "background", "hooks", "paths", "shell",
           "metadata", "license", "compatibility"}

def check(name, ok, detail=""):
    global passed
    if ok: passed += 1; print(f"PASS  {name}")
    else: problems.append(name); print(f"FAIL  {name} {detail}")

def read(p): return open(p, encoding="utf-8").read()

# 1 CLAUDE.md length
if os.path.exists("CLAUDE.md"):
    n = len(read("CLAUDE.md").splitlines())
    check("CLAUDE.md under 100 lines", n < 100, f"({n} lines)")
else:
    check("CLAUDE.md exists", False)

# 2 JSON files valid (glob skips dot-directories, so the plugin manifests are listed explicitly)
_json = set(glob.glob("**/*.json", recursive=True)) | set(glob.glob(".claude-plugin/*.json")) \
    | set(glob.glob(f"{PLUGIN}/.claude-plugin/*.json"))
for f in sorted(_json):
    try: json.load(open(f, encoding="utf-8")); ok = True
    except Exception: ok = False
    check(f"valid JSON: {f}", ok)

# 3 skills: frontmatter, folder name, evals (vacuous when there are no skills yet)
SKILLS = sorted(glob.glob(f"{PLUGIN}/skills/*/"))
for d in SKILLS:
    name = os.path.basename(d.rstrip("/"))
    p = os.path.join(d, "SKILL.md")
    if not os.path.exists(p): check(f"skill {name}: SKILL.md exists", False); continue
    t = read(p)
    m = FM.match(t)
    check(f"skill {name}: frontmatter name matches folder", bool(m) and m.group(1).strip() == name)
    check(f"skill {name}: description present and < 1100 chars", bool(m) and 20 < len(m.group(2)) < 1100)
    _extra = [k for k in re.findall(r"^([A-Za-z_-]+):", m.group(3), re.M) if k not in FM_KEYS] if m else []
    check(f"skill {name}: other frontmatter keys are documented ones", not _extra, f"(unknown: {_extra})")
    if re.search(r"^STATUS: SKELETON", t, re.M):
        check(f"skill {name}: SKELETON, evals not required yet (not claimed as working)", True)
    else:
        check(f"skill {name}: evals/evals.json exists", os.path.exists(os.path.join(d, "evals", "evals.json")))

# 3b skill descriptions say when NOT to use the skill (names the neighbour)
EXCL = r"\b(not for|not a|not an|do not use|never use)\b|\(use [a-z-]+\)|use [a-z-]+ instead"
for p in sorted(glob.glob(f"{PLUGIN}/skills/*/SKILL.md")):
    name = os.path.basename(os.path.dirname(p))
    m = FM.match(read(p))
    check(f"plugin skill {name}: description says when NOT to use it", bool(m) and bool(re.search(EXCL, m.group(2), re.I)))

# 3c a "(use X)" or "use X instead" pointer in a description names a skill folder or a command file that exists
_skill_names = {os.path.basename(os.path.dirname(p)) for p in glob.glob(f"{PLUGIN}/skills/*/SKILL.md")} \
    | {os.path.basename(p)[:-3] for p in glob.glob(f"{PLUGIN}/commands/*.md")}
for p in sorted(glob.glob(f"{PLUGIN}/skills/*/SKILL.md")):
    name = os.path.basename(os.path.dirname(p))
    m = FM.match(read(p))
    refs = [(a or b).lower() for a, b in re.findall(r"\(use ([a-z][a-z-]*)\)|use ([a-z][a-z-]*) instead", m.group(2), re.I)] if m else []
    unknown = [r for r in refs if r not in _skill_names]
    check(f"plugin skill {name}: skills named in its description exist", not unknown, ("(unknown: " + ", ".join(unknown) + ")") if unknown else "")

# 6 relative paths in READMEs exist (backticked, with a slash or known extension)
SKIP = ("evals/runs", "settings.json", "~/", "<", "*", "http")
# descriptive names (what a skill or project contains), not claims that the path exists here
GENERIC = {"SKILL.md", "package.json", "references/", "evals/"}
ALLNAMES = {n + ("/" if os.path.isdir(os.path.join(dp, n)) else "") for dp, dn, fn in os.walk(".")
            if not dp.startswith(("./.git", "./.superpowers", "./.claude/")) for n in dn + fn}
for f in ("README.md", "CLAUDE.md", f"{PLUGIN}/README.md"):
    if not os.path.exists(f): continue
    for ref in sorted(set(re.findall(r"`([A-Za-z0-9_.\-/]+(?:/|\.md|\.json|\.py))`", read(f)))):
        if any(k in ref for k in SKIP) or ref.startswith(("npm", "npx")) or ref in GENERIC: continue
        if "/" not in ref.rstrip("/"):
            check(f"{f} bare name exists somewhere: {ref}", ref in ALLNAMES); continue
        check(f"{f} references existing path: {ref}", os.path.exists(ref) or os.path.exists(os.path.join(PLUGIN, ref)))

# 7 no secret-looking strings
sys.path.insert(0, os.path.join(ROOT, PLUGIN, "scripts"))
from publish_gate import SECRET_RE as pat  # one source of truth, shared with the publish gate
hits = []
# synthetic test inputs that are meant to look like secrets; exact file + exact string only
KNOWN_FIXTURES = set()
for f in glob.glob("**/*", recursive=True) + glob.glob(".claude-plugin/*") + glob.glob(f"{PLUGIN}/.claude-plugin/*"):
    if os.path.isfile(f) and not f.endswith((".png",)):
        try: t = read(f)
        except Exception: continue
        for m in pat.finditer(t):
            if (f, m.group(0)) in KNOWN_FIXTURES: continue
            hits.append((f, m.group(0)[:20]))
check("no secret-looking strings", not hits, str(hits[:3]))

# 12 every scripts/<name>.py mentioned in commands and skill docs exists under plugins/jobsearch/
# (scripts/ or a skill's own scripts/). Checks existence only, not that the script works.
_docs = sorted(glob.glob(f"{PLUGIN}/commands/*.md") + glob.glob(f"{PLUGIN}/skills/**/*.md", recursive=True))
_have = {os.path.basename(p) for p in glob.glob(f"{PLUGIN}/**/scripts/*.py", recursive=True)}
_missing = sorted({(d, s) for d in _docs for s in re.findall(r"scripts/([A-Za-z0-9_.\-]+\.py)", read(d)) if s not in _have})
check("every scripts/*.py mentioned in commands and skills exists", not _missing, f"(missing: {_missing[:5]})")

# 15 a scripts/<name>.py, reference/<file> or presets/<path> PATH in commands and skills must be anchored: an installed plugin runs with the user's project as cwd.
# Allowed prefixes: ${CLAUDE_PLUGIN_ROOT}/, ${CLAUDE_PLUGIN_ROOT}/skills/<x>/, ${CLAUDE_SKILL_DIR}/. Prose may use the bare file name.
_ANCHOR = re.compile(r"\$\{CLAUDE_(?:PLUGIN_ROOT\}/(?:skills/[A-Za-z0-9_\-]+/)?|SKILL_DIR\}/)$")
_bare = []
for _d in _docs:
    for _n, _line in enumerate(read(_d).splitlines(), 1):
        for _m in re.finditer(r"(?<![A-Za-z0-9_.\-])(?:scripts/[A-Za-z0-9_.\-]+\.py|(?:reference|presets)/[A-Za-z0-9_.\-]+)", _line):
            if not _ANCHOR.search(_line[:_m.start()]): _bare.append(f"{_d}:{_n}")
check("no bare relative scripts/ reference/ presets/ paths in commands and skills", not _bare, f"(at: {_bare[:8]})")

# 15b a runnable `python3 <name>.py` with a bare script name (no directory) only works with the plugin as cwd: FAIL.
# Anchor it as python3 "${CLAUDE_PLUGIN_ROOT}/scripts/<name>.py". Prose naming `<name>.py` alone is fine.
_RUN_BARE = re.compile(r"\bpython3?\s+(?:-[A-Za-z]+\s+)*[\"']?[A-Za-z0-9_.\-]+\.py(?![A-Za-z0-9_./\-])")
_runbare = [f"{_d}:{_n}" for _d in _docs for _n, _line in enumerate(read(_d).splitlines(), 1) if _RUN_BARE.search(_line)]
check("no runnable python3 <name>.py with a bare script name in commands and skills", not _runbare, f"(at: {_runbare[:8]})")

# 13 the config template parses and has no keys the loader does not know
import subprocess
_r = subprocess.run([sys.executable, "-B", f"{PLUGIN}/scripts/datadir.py", "validate", f"{PLUGIN}/reference/config.template.yaml"],
                    capture_output=True, text=True)
check("datadir.py validate accepts reference/config.template.yaml", _r.returncode == 0, (_r.stdout + _r.stderr).strip()[:120])

# 14 publish gate over tree and git history; needs the owner's private config (JOBSEARCH_CONFIG), else WARN-skip
_cfg = os.environ.get("JOBSEARCH_CONFIG")
if _cfg and not os.path.isfile(_cfg):
    check("publish gate: JOBSEARCH_CONFIG points at an existing file", False, "(file not found)")
elif _cfg:
    _r = subprocess.run([sys.executable, "-B", f"{PLUGIN}/scripts/publish_gate.py", "--repo", ".", "--config", _cfg],
                        capture_output=True, text=True)
    if _r.returncode == 2: print("WARN  publish gate skipped (no private config)")
    else: check("publish gate: no private identity in tree or history", _r.returncode == 0, "(" + (_r.stdout.strip().splitlines() or ["?"])[-1] + ")")
else:
    print("WARN  publish gate skipped (no private config)")

# --- append new checks (15, 16, ...) above this line ---
print(f"\n{passed} passed, {len(problems)} failed")
sys.exit(1 if problems else 0)
