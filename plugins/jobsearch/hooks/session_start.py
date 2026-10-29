#!/usr/bin/env python3
"""SessionStart hook: puts the start file and the open items of the todo file into Claude's context.

Speaks only when the project root is the resolved data dir or holds the .jobsearch-data marker.
Silent (prints nothing, exit 0) in any other project, on any data-dir error, and when the project's
own .claude/settings.json or settings.local.json already defines a SessionStart hook.
Read-only. Stdlib only. A missing file is reported in the text instead of failing.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import datadir  # noqa: E402


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


def context(project_root, env):
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
    text = ("SESSION START for a job-search data folder. Show the overview below, then the open to-do items, "
            "and ask which to take.")
    if lang:
        text += f" Always answer in {lang}."
    text += (f"\n\n===== {start_rel} =====\n" + _read(datadir.data_path(cfg, d, "start_file"), start_rel)
             + f"\n\n===== {todo_rel} open items ({len(open_items)}) =====\n" + "\n".join(open_items or ([todo] if todo.startswith("(missing:") else [])))
    return {
        "systemMessage": f"jobsearch: {start_rel} and {todo_rel} loaded ({len(open_items)} open items).",
        "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text},
    }


def main(stdin=None, env=None):
    try:
        env = os.environ if env is None else env
        try:
            data = json.loads((stdin or sys.stdin).read() or "{}")
        except (ValueError, OSError):
            data = {}
        cwd = data.get("cwd") if isinstance(data, dict) else None
        root = cwd if isinstance(cwd, str) and os.path.isdir(cwd) else os.getcwd()
        ctx = context(root, env)
        if ctx is not None:
            print(json.dumps(ctx, ensure_ascii=False))
    except Exception:  # a hook must never break the session
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
