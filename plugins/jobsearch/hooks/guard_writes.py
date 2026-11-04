#!/usr/bin/env python3
"""PreToolUse hook: enforces hard rules 5 and 6 on the user's data dir in code, not only in prose.

- Write/Edit/MultiEdit/NotebookEdit of the tracker, its CHANGELOG.csv or history/, any file in
  `paths.cv_files`, or `paths.master_cv` -> deny (the tracker changes only through tracker_edit.py;
  final CV files and the master CV are read-only).
- The same tools on `paths.facts` -> ask (the user confirms each edit of the facts file).
- Supported Bash writes to the tracker or existing CV/master (including parent removal and downloads)
  -> deny; facts/config and create-only CV writes -> ask. Read/copy-out of a CV is allowed.
- In the job-search project itself (project root = data dir, or it holds the .jobsearch-data marker):
  browser / computer-use actions that click, type, fill, press or submit, and any MCP tool that sends
  or replies (mail, chat) -> deny (hard rule 1: never send, apply or submit; the user clicks).
No data dir resolved (JOBSEARCH_DATA_DIR / marker / config in the project) -> no opinion.
Prints nothing when it has no opinion. In a configured project, check errors deny outbound or protected writes; unrelated reads stay silent.
Stdlib only.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import datadir  # noqa: E402
import egress  # noqa: E402

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
TRACKER_REASON = ("The tracker is edited only through tracker_edit.py (hard rule 5: backup, changelog, counts). "
                  'Use python3 "${CLAUDE_PLUGIN_ROOT}/scripts/tracker_edit.py" instead.')
READONLY_REASON = ("Final CV files (paths.cv_files) and the master CV are read-only (hard rule 6). "
                   "Write a targeted copy in the application folder instead, and only when the user asks.")
UI_TOOL = re.compile(r"^mcp__.*(browser|chrome|playwright|computer)", re.I)
UI_ACTION_NAME = re.compile(r"(click|type|fill|form_input|press|select_option|file_upload|drag|drop|submit|run_code|evaluate|javascript)", re.I)
UI_BATCH_NAME = re.compile(r"(computer|batch)$", re.I)
UI_ACTION_VALUE = re.compile(r"click|type|key|drag|press|submit|form_input|fill", re.I)
SEND_TOOL = re.compile(r"^mcp__.*(^|_|-)(send|reply|post_message|send_message)(_|-|$)", re.I)
OUTREACH_REASON = ("jobsearch hard rule 1: never send, apply or submit; the user clicks. "
                   "Browser/computer interactions are blocked because they can activate Send, Apply or Submit. "
                   "Prepare the materials and let the user interact with the page manually.")
FACTS_REASON = "Editing the user's facts file (paths.facts): confirm this change with the user first."


def _real(p, cwd):
    return os.path.realpath(os.path.join(cwd, os.path.expanduser(p)))


def protected(cwd, env):
    """Return [(abs_path, rel_label, kind, is_dir, existed)] or [] when no data dir resolves."""
    try:
        d = datadir.resolve_data_dir(cwd, env)
        cfg = datadir.load_config(d, env)
    except (datadir.DataDirError, ValueError, OSError):
        if egress.configured(cwd, env):
            raise
        return []
    paths = cfg.get("paths") or {}
    out = [(datadir.config_path(d, env), "config", False)]
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
    return [(os.path.realpath(os.path.join(d, rel)), rel, kind, is_dir, os.path.lexists(os.path.join(d, rel)))
            for rel, kind, is_dir in out]


def _verdict(kind):
    return {"tracker": ("deny", TRACKER_REASON), "readonly": ("deny", READONLY_REASON),
            "facts": ("ask", FACTS_REASON),
            "config": ("ask", "Confirm this config change. Overwrites and privacy grants require two separate confirmations in chat and a backup.")}[kind]


def _in_data_project(cwd, env):
    try:
        d = datadir.resolve_data_dir(cwd, env)
    except (datadir.DataDirError, ValueError, OSError):
        if egress.configured(cwd, env):
            raise
        return False
    here, root = os.path.realpath(cwd), os.path.realpath(d)
    hint = datadir.project_root(cwd)
    return here == root or here.startswith(root + os.sep) or bool(hint and os.path.isfile(os.path.join(hint, datadir.MARKER)))


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


def file_decision(tool, path, cwd, entries, ancestors=False):
    if not isinstance(path, str) or not path:
        return None
    target = _real(path, cwd)
    hits = [(p, kind, existed) for p, _, kind, is_dir, existed in entries
            if target == p or (is_dir and target.startswith(p + os.sep))
            or (ancestors and p.startswith(target.rstrip(os.sep) + os.sep))]
    if any(kind == "tracker" for _, kind, _ in hits):
        return _verdict("tracker")
    readonly = [(p, existed) for p, kind, existed in hits if kind == "readonly"]
    if readonly:
        if (tool == "Write" and all(p == target and not existed for p, existed in readonly)
                and not os.path.lexists(os.path.join(cwd, os.path.expanduser(path)))):
            return ("ask", "Create-only setup: confirm creating this CV/master CV from the user's English CV. Existing files stay read-only.")
        return _verdict("readonly")
    return _verdict(hits[0][1]) if hits else None


def bash_file_decisions(command, cwd, entries):
    results = []
    for words in egress.segments(command):
        while words and (words[0] in ("env", "command", "sudo") or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0])):
            words = words[1:]
        if not words:
            continue
        exe = os.path.basename(words[0])
        if exe == "cd" and len(words) == 2:
            cwd = os.path.abspath(os.path.join(cwd, words[1]))
            continue
        body = egress.shell_body(words)
        if body is not None:
            results += bash_file_decisions(body, cwd, entries)
            continue
        if exe in ("curl", "wget"):
            for output in egress.network_args(words)[3]:
                result = file_decision("Write", output, cwd, entries, ancestors=True)
                if result:
                    results.append(result)
        redirections = [words[i + 1] for i, w in enumerate(words[:-1])
                        if w in (">", ">>") and words[i + 1] != "/dev/null"]
        excluded = {i for i, w in enumerate(words) if w in ("<", ">", ">>")}
        excluded |= {i + 1 for i in excluded}
        args = [w for i, w in enumerate(words[1:], 1) if i not in excluded and not w.startswith("-")]
        mutator = (exe in ("cp", "mv", "rm", "unlink", "rmdir", "truncate", "dd", "install", "rsync", "tee")
                   or (exe == "sed" and any(w.startswith("-i") for w in words[1:]))
                   or (exe == "perl" and any(w.startswith("-") and "i" in w for w in words[1:])))
        targets = args if mutator else []
        if exe in ("cp", "install") and args:
            targets = [args[-1]]  # the protected input is read, not changed
            if "-t" in words:
                at = words.index("-t") + 1
                targets = [words[at]] if at < len(words) else targets
        elif exe == "dd":
            targets = [w[3:] for w in words if w.startswith("of=")]
        targets += redirections
        for path in targets:
            result = file_decision("Write", path, cwd, entries, ancestors=True)
            if result:
                results.append(result)
    return results


def decide(tool_name, tool_input, cwd, env):
    """Return a decision for local protected paths before checking external permissions."""
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    if (isinstance(tool_name, str) and tool_name.startswith("mcp__")
            and _outreach(tool_name, tool_input) and _in_data_project(cwd, env)):
        return ("deny", OUTREACH_REASON)
    entries = None
    local = []
    is_mcp = isinstance(tool_name, str) and tool_name.startswith("mcp__")
    mcp_write = is_mcp and egress.connector_write(tool_name, tool_input)
    if tool_name in WRITE_TOOLS or tool_name == "Bash" or mcp_write:
        entries = protected(cwd, env)
        if tool_name in WRITE_TOOLS:
            p = tool_input.get("file_path") or tool_input.get("notebook_path")
            result = file_decision(tool_name, p, cwd, entries)
            if result:
                local.append(result)
        elif tool_name == "Bash":
            local = bash_file_decisions(tool_input.get("command", ""), cwd, entries)
        elif mcp_write:
            for key in ("path", "file_path", "notebook_path", "source", "source_path", "destination", "destination_path"):
                result = file_decision("Edit", tool_input.get(key), cwd, entries, ancestors=True)
                if result:
                    local.append(result)
    deny = next((r for r in local if r[0] == "deny"), None)
    if deny:
        return deny
    external = egress.check(tool_name, tool_input, cwd, env)
    if external:
        return external
    if local:
        return local[0]
    return None


def main(stdin=None, env=None):
    data = {}
    env = os.environ if env is None else env
    cwd = os.getcwd()
    verdict = None
    try:
        try:
            data = json.loads((stdin or sys.stdin).read() or "{}")
        except (ValueError, OSError):
            return 0
        if not isinstance(data, dict):
            return 0
        cwd = data.get("cwd") if isinstance(data.get("cwd"), str) and os.path.isdir(data["cwd"]) else os.getcwd()
        verdict = decide(data.get("tool_name"), data.get("tool_input"), cwd, env)
    except Exception:
        # Deny protected writes and outbound calls on errors when a data configuration exists.
        tool, ti = data.get("tool_name"), data.get("tool_input", {})
        if egress.configured(cwd, env) and (egress.risky(tool, ti) or tool in WRITE_TOOLS or tool == "Bash" or (isinstance(tool, str) and _outreach(tool, ti))):
            verdict = ("deny", "Jobsearch guard failed while checking this action. Fix the data/privacy configuration and retry; the action was not approved.")
    if verdict:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                 "permissionDecision": verdict[0],
                                                 "permissionDecisionReason": verdict[1]}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
