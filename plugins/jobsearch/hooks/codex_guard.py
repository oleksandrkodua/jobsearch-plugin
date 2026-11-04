#!/usr/bin/env python3
"""Codex adapter: supported deny output only, never unsupported permissionDecision ask.

  codex_guard.py                 read a PreToolUse JSON event on stdin
  codex_guard.py --preflight     read a WebSearch/WebFetch event, exit 1 when blocked

In conservative mode every shared ask becomes deny. The user executes that action manually.
Hosted web calls have no hook event: skills must run --preflight before the exact query/URL.
"""
import json
import os
import re
import sys

import guard_writes
import egress
import runtime
import datadir

MANUAL = ("Codex conservative mode: this action needs user confirmation and was blocked. "
          "Codex does not support a PreToolUse ask. The user must perform it manually after reviewing "
          "the exact action; do not retry via a different tool or disable the guard.")


def decide(data, env):
    cwd = data.get("cwd") or os.getcwd()
    # Resolve the data scope from the session before a tool changes its execution directory.
    if egress.configured(cwd, env):
        data_dir = os.path.abspath(datadir.resolve_data_dir(cwd, env))
        config = os.path.abspath(datadir.config_path(data_dir, env))
        env = {**env, datadir.ENV_DIR: data_dir, datadir.ENV_CONFIG: config}
    tool = data.get("tool_name")
    ti = data.get("tool_input") or {}
    if not isinstance(ti, dict):
        raise ValueError("tool input must be an object")
    # Codex reports canonical Bash with a command field; accept exec_command for direct preflight/tests too.
    if tool == "exec_command":
        tool, ti = "Bash", {"command": ti.get("cmd", ""), **ti}
    cwd = ti.get("workdir") or cwd
    if tool == "apply_patch":
        patch = ti.get("command")
        if not isinstance(patch, str):
            return ("deny", "Cannot inspect this patch; no file write was approved.")
        changes = re.findall(r"^\*\*\* (Add File|Update File|Delete File|Move to): (.+)$", patch, re.M)
        if not changes:
            return ("deny", "Cannot inspect patch paths; no file write was approved.")
        verdicts = []
        for action, path in changes:
            kind = "Write" if action in ("Add File", "Move to") else "Edit"
            result = guard_writes.decide(kind, {"file_path": path}, cwd, env)
            if result:
                verdicts.append(result)
        return next((v for v in verdicts if v[0] == "deny"), verdicts[0] if verdicts else None)
    return guard_writes.decide(tool, ti, cwd, env)


def main(stdin=None, env=None, argv=None):
    env = os.environ if env is None else env
    argv = sys.argv[1:] if argv is None else argv
    preflight = argv == ["--preflight"]
    try:
        data = json.loads((stdin or sys.stdin).read())
        if not isinstance(data, dict):
            raise ValueError("event must be an object")
        if preflight and (data.get("tool_name") not in ("WebSearch", "WebFetch")
                          or not egress.configured(data.get("cwd") or os.getcwd(), env)):
            raise ValueError("preflight requires a configured data folder and WebSearch/WebFetch")
        result = decide(data, env)
    except Exception:
        result = ("deny", "Codex jobsearch guard could not check this action; it was not approved. Fix configuration/input and retry.")
    if result and result[0] == "ask":
        result = ("deny", MANUAL)
    if result:
        result = (result[0], runtime.render_text(result[1]).replace("${CLAUDE_PLUGIN_ROOT}", runtime.PLUGIN_ROOT))
    if preflight:
        print("DENIED: " + result[1] if result else "PASS: exact search/fetch input checked against configured identity patterns. This is not automatic interception of hosted web tools.")
        return 1 if result else 0
    if result:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": result[1]}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
