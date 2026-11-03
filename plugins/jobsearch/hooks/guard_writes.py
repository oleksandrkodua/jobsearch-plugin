#!/usr/bin/env python3
"""PreToolUse hook: enforces hard rules 5 and 6 on the user's data dir in code, not only in prose.

- Write/Edit/MultiEdit/NotebookEdit of the tracker, its CHANGELOG.csv or history/, any file in
  `paths.cv_files`, or `paths.master_cv` -> deny (the tracker changes only through tracker_edit.py;
  final CV files and the master CV are read-only).
- The same tools on `paths.facts` -> ask (the user confirms each edit of the facts file).
- Bash that names one of those files and looks like a write (redirect, sed -i, tee, cp, mv, rm, ...)
  -> ask. tracker_edit.py itself is allowed.
- In the job-search project itself (project root = data dir, or it holds the .jobsearch-data marker):
  browser / computer-use actions that click, type, fill, press or submit, and any MCP tool that sends
  or replies (mail, chat) -> ask (hard rule 1: never send, apply or submit; the user clicks).
No data dir resolved (JOBSEARCH_DATA_DIR / marker / config in the project) -> no opinion.
Prints nothing and exits 0 when it has no opinion or on any error: a hook must never break the session.
Stdlib only.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import datadir  # noqa: E402

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
HARMLESS_REDIRECT = re.compile(r"\d*>&\d+|\d*>>?\s*/dev/null")  # 2>&1, 2>/dev/null: not a file write
BASH_WRITE = re.compile(r">|\btee\b|\bsed\s+(-\w*\s+)*-i|\bperl\s+-\w*i|\b(cp|mv|rm|truncate|dd|install|rsync)\b")
TRACKER_REASON = ("The tracker is edited only through tracker_edit.py (hard rule 5: backup, changelog, counts). "
                  'Use python3 "${CLAUDE_PLUGIN_ROOT}/scripts/tracker_edit.py" instead.')
READONLY_REASON = ("Final CV files (paths.cv_files) and the master CV are read-only (hard rule 6). "
                   "Write a targeted copy in the application folder instead, and only when the user asks.")
UI_TOOL = re.compile(r"^mcp__.*(browser|chrome|playwright|computer)", re.I)
UI_ACTION_NAME = re.compile(r"(click|type|fill|form_input|press|select_option|file_upload|drag|drop|submit|run_code|evaluate|javascript)", re.I)
UI_BATCH_NAME = re.compile(r"(computer|batch)$", re.I)
UI_ACTION_VALUE = re.compile(r"click|type|key|drag|press|submit|form_input|fill", re.I)
SEND_TOOL = re.compile(r"^mcp__.*(^|_|-)(send|reply|post_message|send_message)(_|-|$)", re.I)
OUTREACH_REASON = ("jobsearch hard rule 1: never send, apply or submit; the user clicks. This action can click, type "
                   "into a page or send a message: confirm it with the user (an Apply / Send / Submit control is "
                   "always the user's).")
FACTS_REASON = "Editing the user's facts file (paths.facts): confirm this change with the user first."


def _real(p, cwd):
    return os.path.realpath(os.path.join(cwd, os.path.expanduser(p)))


def protected(cwd, env):
    """Return [(abs_path, rel_label, kind, is_dir)] or [] when no data dir resolves."""
    try:
        d = datadir.resolve_data_dir(cwd, env)
        cfg = datadir.load_config(d, env)
    except (datadir.DataDirError, ValueError, OSError):
        return []
    paths = cfg.get("paths") or {}
    out = []
    tracker = paths.get("tracker")
    if tracker:
        tdir = os.path.dirname(tracker)
        out += [(tracker, "tracker", False), (os.path.join(tdir, "CHANGELOG.csv"), "tracker", False),
                (os.path.join(tdir, "history"), "tracker", True)]
    for cv in paths.get("cv_files") or []:
        if cv:
            out.append((cv, "readonly", False))
    if paths.get("master_cv"):
        out.append((paths["master_cv"], "readonly", False))
    if paths.get("facts"):
        out.append((paths["facts"], "facts", False))
    return [(os.path.realpath(os.path.join(d, rel)), rel, kind, is_dir) for rel, kind, is_dir in out]


def _match(target, entries):
    for abs_p, rel, kind, is_dir in entries:
        if target == abs_p or (is_dir and target.startswith(abs_p + os.sep)):
            return kind
    return None


def _verdict(kind):
    return {"tracker": ("deny", TRACKER_REASON), "readonly": ("deny", READONLY_REASON),
            "facts": ("ask", FACTS_REASON)}[kind]


def _in_data_project(cwd, env):
    try:
        d = datadir.resolve_data_dir(cwd, env)
    except (datadir.DataDirError, ValueError, OSError):
        return False
    return os.path.realpath(cwd) == os.path.realpath(d) or os.path.isfile(os.path.join(cwd, datadir.MARKER))


def _outreach(tool_name, tool_input):
    if SEND_TOOL.search(tool_name):
        return True
    if not UI_TOOL.search(tool_name):
        return False
    if UI_ACTION_NAME.search(tool_name.rsplit("__", 1)[-1]):
        return True
    if UI_BATCH_NAME.search(tool_name):
        return bool(UI_ACTION_VALUE.search(json.dumps(tool_input or {})))
    return False


def decide(tool_name, tool_input, cwd, env):
    """Return (decision, reason) for a protected target, or None."""
    if isinstance(tool_name, str) and tool_name.startswith("mcp__"):
        if _outreach(tool_name, tool_input) and _in_data_project(cwd, env):
            return ("ask", OUTREACH_REASON)
        return None
    if tool_name not in WRITE_TOOLS and tool_name != "Bash":
        return None
    entries = protected(cwd, env)
    if not entries:
        return None
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    if tool_name in WRITE_TOOLS:
        p = tool_input.get("file_path") or tool_input.get("notebook_path")
        kind = _match(_real(p, cwd), entries) if isinstance(p, str) and p else None
        return _verdict(kind) if kind else None
    cmd = tool_input.get("command")
    if not isinstance(cmd, str) or not BASH_WRITE.search(HARMLESS_REDIRECT.sub("", cmd)):
        return None
    named = {kind for abs_p, rel, kind, _ in entries if abs_p in cmd or rel.rstrip("/") in cmd}
    if "tracker_edit.py" in cmd:
        named.discard("tracker")
    if not named:
        return None
    return ("ask", "This command looks like it writes a protected jobsearch file (tracker, final CV, master CV "
                   "or facts). Hard rules 5 and 6: confirm with the user, or use tracker_edit.py for the tracker.")


def main(stdin=None, env=None):
    try:
        env = os.environ if env is None else env
        try:
            data = json.loads((stdin or sys.stdin).read() or "{}")
        except (ValueError, OSError):
            return 0
        if not isinstance(data, dict):
            return 0
        cwd = data.get("cwd") if isinstance(data.get("cwd"), str) and os.path.isdir(data["cwd"]) else os.getcwd()
        verdict = decide(data.get("tool_name"), data.get("tool_input"), cwd, env)
        if verdict:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                     "permissionDecision": verdict[0],
                                                     "permissionDecisionReason": verdict[1]}}))
    except Exception:  # a hook must never break the session
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
