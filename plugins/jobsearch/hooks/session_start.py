#!/usr/bin/env python3
"""SessionStart hook: puts the start file and the open items of the todo file into Claude's context.

Speaks only when the project root is the resolved data dir or holds the .jobsearch-data marker.
Silent (prints nothing, exit 0) in any other project, on any data-dir error, and when the project's
own .claude/settings.json or settings.local.json already defines a SessionStart hook.
On startup and clear (not on resume or compact) it also lists every command and skill with a one-line
description taken from their own frontmatter, and asks Claude to show that overview to the user first.
`session_start.py --list` prints only that overview (used by /jobsearch:help; needs no data dir).
Read-only. Stdlib only. A missing file is reported in the text instead of failing.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import datadir  # noqa: E402

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OVERVIEW_SOURCES = ("startup", "clear", None)  # resume / compact: the user has already seen it
MAX_OPEN_ITEMS = 30  # keep the session context small; the full list stays in the todo file


def _same(a, b):
    return os.path.realpath(a) == os.path.realpath(b)


def _has_own_hook(root):
    for name in ("settings.json", "settings.local.json"):
        try:
            with open(os.path.join(root, ".claude", name), encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("hooks"), dict) and data["hooks"].get("SessionStart"):
                return True
        except (OSError, ValueError):
            continue
    return False


def _read(path, label):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return f"(missing: {label})"


def _description(path):
    try:
        with open(path, encoding="utf-8") as f:
            head = f.read(4000)
    except OSError:
        return ""
    m = re.search(r"(?m)^description:\s*(.+)$", head.split("\n---", 1)[0])
    return m.group(1).strip() if m else ""


def _one_liner(desc, limit=200):
    first = re.split(r"(?<=[.!?])\s", desc, maxsplit=1)[0]
    return first if len(first) <= limit else first[:limit - 1].rstrip() + "…"


def _modes(desc):
    """Mode names a command description announces: "Mode `tune`: ..." or "Modes - prep (...), debrief (...)"."""
    names = re.findall(r"Mode `([a-z]+)", desc)
    m = re.search(r"Modes\s*-\s*(.+)", desc)
    if m:
        names += re.findall(r"(?:^|,\s*)([a-z]+)\s*\(", m.group(1))
    return list(dict.fromkeys(names))


def capabilities(plugin_root=PLUGIN_ROOT):
    """Markdown list of the plugin's commands and skills, one line each, from their frontmatter."""
    lines = ["Commands (type them as /jobsearch:<name>):"]
    cdir = os.path.join(plugin_root, "commands")
    for f in sorted(os.listdir(cdir)) if os.path.isdir(cdir) else []:
        if f.endswith(".md"):
            desc = _description(os.path.join(cdir, f))
            modes = _modes(desc)
            lines.append(f"- `/jobsearch:{f[:-3]}` - {_one_liner(desc)}"
                         + (" Modes: " + ", ".join(f"`{m}`" for m in modes) + "." if modes else ""))
    lines.append("Skills (Claude uses them inside the commands, or when you ask for that task):")
    sdir = os.path.join(plugin_root, "skills")
    for d in sorted(os.listdir(sdir)) if os.path.isdir(sdir) else []:
        p = os.path.join(sdir, d, "SKILL.md")
        if os.path.isfile(p):
            lines.append(f"- `{d}` - {_one_liner(_description(p))}")
    return "\n".join(lines)


def context(project_root, env, source=None):
    try:
        d = datadir.resolve_data_dir(project_root, env)
        if not (_same(project_root, d) or os.path.isfile(os.path.join(project_root, datadir.MARKER))):
            return None
        if _has_own_hook(project_root):
            return None
        cfg = datadir.load_config(d, env)
    except (datadir.DataDirError, ValueError, OSError):
        return None
    start_rel, todo_rel = cfg["paths"]["start_file"], cfg["paths"]["todo_file"]
    todo = _read(datadir.data_path(cfg, d, "todo_file"), todo_rel)
    open_items = [l for l in todo.splitlines() if re.match(r"\s*- \[ \]", l)]
    lang = cfg["language"].get("chat")
    overview = source in OVERVIEW_SOURCES
    text = ("SESSION START for a job-search data folder. "
            + ("First give the user a short overview of the commands and skills listed at the end (one line each, "
               "in plain words: what it does for them and when to use it). Then " if overview else "")
            + "Show the overview below, then the open to-do items, and ask which to take.")
    if lang:
        text += f" Always answer in {lang}."
    text += (f"\n\n===== {start_rel} =====\n" + _read(datadir.data_path(cfg, d, "start_file"), start_rel)
             + f"\n\n===== {todo_rel} open items ({len(open_items)}) =====\n" + "\n".join(open_items[:MAX_OPEN_ITEMS] or ([todo] if todo.startswith("(missing:") else [])))
    if len(open_items) > MAX_OPEN_ITEMS:
        text += f"\n... and {len(open_items) - MAX_OPEN_ITEMS} more open items in {todo_rel}"
    if overview:
        text += "\n\n===== jobsearch commands and skills =====\n" + capabilities()
    return {
        "systemMessage": f"jobsearch: {start_rel} and {todo_rel} loaded ({len(open_items)} open items).",
        "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text},
    }


def main(stdin=None, env=None, argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--list"]:  # used by /jobsearch:help; needs no data dir
        print(capabilities())
        return 0
    try:
        env = os.environ if env is None else env
        try:
            data = json.loads((stdin or sys.stdin).read() or "{}")
        except (ValueError, OSError):
            data = {}
        cwd = data.get("cwd") if isinstance(data, dict) else None
        root = cwd if isinstance(cwd, str) and os.path.isdir(cwd) else os.getcwd()
        source = data.get("source") if isinstance(data, dict) else None
        ctx = context(root, env, source if isinstance(source, str) else None)
        if ctx is not None:
            print(json.dumps(ctx, ensure_ascii=False))
    except Exception:  # a hook must never break the session
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
