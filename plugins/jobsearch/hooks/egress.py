"""Outbound checks for the jobsearch guard. No network or content uploads.

Shared identity patterns come from publish_gate. Connector grants name an exact tool;
host grants apply to explicit network destinations, never to URLs embedded in a document.
Shell inspection covers the documented command families, not arbitrary executable code.
"""
import json
import os
import re
import shlex
import subprocess
from urllib.parse import unquote_plus, urlsplit

import datadir
import publish_gate

WRITE_VERBS = re.compile(r"(?:^|[_-])(create|update|publish|upload|post|send|reply|comment|share|draft|write|edit|patch|put|replace|delete|remove|attach)(?:[_-]|$)", re.I)
# Reviewed exact read tools; an unfamiliar get/search name is not evidence of read-only behavior.
READ_ONLY_CONNECTORS = frozenset({
    "mcp__notion__search", "mcp__notion__get_page",
    "mcp__browser__navigate", "mcp__Claude_Browser__navigate", "mcp__Claude_Browser__get_page_text",
    "mcp__plugin_playwright_playwright__browser_snapshot",
})
SCREENSHOT_CONNECTORS = frozenset({"mcp__claude-in-chrome__computer", "mcp__Claude_Browser__computer"})
GENERIC_EXECUTOR = re.compile(r"(?:^|[_-])(js|javascript|execute|exec|run|code|evaluate|eval|script|python|bash|request)(?:[_-]|$)", re.I)
FINAL_ACTION = re.compile(r"(?:^|[_/-])(send|reply|submit|apply|forward|post_message)(?:[_/-]|$)", re.I)
FINAL_DENIED = "jobsearch hard rule 1: never send, apply or submit. Prepare a draft; the user performs final delivery. Destination grants cannot override this rule."
UNCLASSIFIED = "Unclassified connector denied: review and classify this exact tool in the plugin before use. Generic executors cannot be authorized by destination grants or a read/GET hint. Do not switch tools to bypass this block."
DENIED = "Outbound write denied: approve this destination with jobsearch-setup update after two separate confirmations."
ASK = ("Approved destination. Confirmation 2: approve this specific outbound write only after your explicit "
       "confirmation 1 in chat naming the destination and what will go there. Approval never carries to later calls. "
       "Applications and messages remain drafts; the user sends them (hard rule 1).")


SCOPE_KEY = "JOBSEARCH_GUARD_SCOPE"  # set by codex_guard after it resolved the session scope


def configured(cwd, env):
    """True only inside the job-search project: cwd is in the data folder, or the project holds the
    marker/config file. The env vars alone do not activate the guard in unrelated projects."""
    if env.get(SCOPE_KEY) == "1" or datadir.project_root(cwd) is not None:
        return True
    d = env.get(datadir.ENV_DIR)
    if not d:
        return False
    here, root = os.path.realpath(cwd), os.path.realpath(os.path.expanduser(d))
    return here == root or here.startswith(root + os.sep)


def _git(cwd, *args):
    r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=3)
    return r.stdout.strip() if r.returncode == 0 else ""


def repo_id(remote):
    """Canonical host/owner/repo from SSH/HTTPS git remotes; reject local paths."""
    m = re.fullmatch(r"(?:[^/@:]+@)?([A-Za-z0-9.-]+):([^\s]+)", remote or "")
    if m and "://" not in remote:
        host, path = m.groups()
    else:
        u = urlsplit(remote or "")
        if u.scheme not in ("https", "http", "ssh", "git") or not u.hostname:
            return None
        host, path = u.hostname, u.path.lstrip("/")
    path = path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = path.split("/")
    if len(parts) != 2 or any(p in ("", ".", "..") for p in parts):
        return None
    return host.lower() + "/" + path


def _push_destination(words, cwd):
    # -C/-c are git global options; the caller already found the push subcommand.
    i = 1
    while i < len(words) and words[i] != "push":
        if words[i] == "-C" and i + 1 < len(words):
            cwd = os.path.abspath(os.path.join(cwd, words[i + 1]))
            i += 2
        elif words[i] == "-c":
            # Config overrides can rewrite destinations; do not infer safety from them.
            return None
        else:
            return None
    rest = words[i + 1:]
    remote = None
    i = 0
    while i < len(rest):
        token = rest[i]
        if token == "--repo" and i + 1 < len(rest):
            remote = rest[i + 1]
            break
        if token.startswith("--repo="):
            remote = token.split("=", 1)[1]
            break
        if token in ("-o", "--push-option", "--receive-pack", "--exec"):
            i += 2
            continue
        if token == "--":
            remote = rest[i + 1] if i + 1 < len(rest) else None
            break
        if not token.startswith("-"):
            remote = token
            break
        i += 1
    if not remote:
        branch = _git(cwd, "symbolic-ref", "--short", "HEAD")
        remote = (_git(cwd, "config", f"branch.{branch}.pushRemote")
                  or _git(cwd, "config", "remote.pushDefault")
                  or _git(cwd, "config", f"branch.{branch}.remote") or "origin")
    if repo_id(remote):
        # An explicit URL can still be rewritten by insteadOf; expand it through git.
        # get-url --push applies pushInsteadOf as well as insteadOf, without network access.
        resolved = _git(cwd, "-c", "remote._jobsearch_probe.url=" + remote,
                        "remote", "get-url", "--push", "--all", "_jobsearch_probe").splitlines()
        return repo_id(resolved[0]) if len(resolved) == 1 else None
    urls = _git(cwd, "remote", "get-url", "--push", "--all", remote).splitlines()
    ids = [repo_id(u) for u in urls]
    # Multiple push URLs would need multiple independent grants; reject ambiguous remotes.
    return ids[0] if len(ids) == 1 else None


def segments(command):
    """Tokenize supported simple shell commands; no command is executed."""
    lex = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    segments, part = [], []
    for token in lex:
        if token and all(c in ";&|()\n" for c in token):
            if part:
                segments.append(part)
                part = []
        else:
            part.append(token)
    if part:
        segments.append(part)
    return segments


def shell_body(words):
    if os.path.basename(words[0]) in ("bash", "sh", "zsh"):
        for i, word in enumerate(words[1:], 1):
            if re.fullmatch(r"-[a-zA-Z]*c[a-zA-Z]*", word) and i + 1 < len(words):
                return words[i + 1]
    return None


def network_args(words):
    """(explicit URLs, writing, ambiguous). Unsupported routing/options fail closed."""
    exe = os.path.basename(words[0])
    urls, writing, ambiguous, redirects, outputs = [], False, False, False, []
    remote_name = False
    boolean = {"--silent", "--show-error", "--fail", "--fail-with-body", "--compressed", "--head", "--quiet"}
    safe_values = {"--output", "--output-document", "--max-time", "--connect-timeout", "--retry", "--timeout", "--user-agent"}
    body_values = {"--data", "--data-raw", "--data-binary", "--data-urlencode", "--json", "--form", "--upload-file",
                   "--post-data", "--post-file", "--body-data", "--body-file", "--request", "--method", "--header"}
    short_bool = set("sSfILO") if exe == "curl" else set("qcS")
    short_values = {"d": "body", "F": "body", "T": "body", "X": "body", "H": "body", "o": "safe", "A": "safe"} if exe == "curl" else {"O": "safe", "U": "safe", "T": "safe", "t": "safe"}
    args, i = words[1:], 0
    while i < len(args):
        arg = args[i]
        i += 1
        if arg.isdigit() and i < len(args) and args[i] in (">", ">>", "<"):
            continue
        if arg in (">", ">>", "<"):
            i += 1
            continue
        if arg.startswith("--"):
            flag, sep, value = arg.partition("=")
            if flag in ("--location", "--location-trusted"):
                redirects = True
            elif flag in boolean:
                pass
            elif flag in safe_values | body_values | {"--url"}:
                if not sep:
                    value = args[i] if i < len(args) else ""
                    i += 1
                if not value:
                    ambiguous = True
                if flag in body_values:
                    writing = True
                if flag == "--url":
                    urls.append(value)
                elif flag in ("--output", "--output-document"):
                    outputs.append(value)
            else:
                ambiguous = True
        elif arg.startswith("-"):
            j = 1
            while j < len(arg):
                flag = arg[j]
                j += 1
                if flag in short_bool:
                    redirects |= flag == "L"
                    remote_name |= flag == "O" and exe == "curl"
                elif flag in short_values:
                    value = arg[j:] or (args[i] if i < len(args) else "")
                    if j == len(arg):
                        i += 1
                    ambiguous |= not bool(value)
                    writing |= short_values[flag] == "body"
                    if (exe == "curl" and flag == "o") or (exe == "wget" and flag == "O"):
                        outputs.append(value)
                    break
                else:
                    ambiguous = True
        else:
            urls.append(arg)
    # Scheme-less extra recipients must never disappear from the destination check.
    ambiguous |= not urls or any(not u.startswith(("http://", "https://")) or not urlsplit(u).hostname for u in urls)
    ambiguous |= redirects and writing
    if remote_name:
        outputs += [os.path.basename(urlsplit(u).path) for u in urls]
    return urls, writing, ambiguous, outputs


def shell_urls(command):
    out = []
    for words in segments(command):
        while words and (words[0] in ("env", "command", "sudo") or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0])):
            words = words[1:]
        if not words:
            continue
        body = shell_body(words)
        if body is not None:
            out += shell_urls(body)
        elif os.path.basename(words[0]) in ("curl", "wget"):
            out += network_args(words)[0]
    return out


def shell_writes(command, cwd, env=None):
    """Return [(kind, destination)] for the supported outbound command families."""
    env = os.environ if env is None else env
    writes = []
    for words in segments(command):
        while words and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]) or words[0] in ("env", "command", "sudo")):
            # Environment changes can alter network destinations: never approve automatically.
            if "=" in words[0] and re.search(r"\b(git|curl|wget|scp|rsync|gh)\b", " ".join(words[1:])):
                writes.append(("unknown", None))
            words = words[1:]
        if not words:
            continue
        exe = os.path.basename(words[0])
        if exe == "cd" and len(words) == 2:
            cwd = os.path.abspath(os.path.join(cwd, words[1]))
        elif shell_body(words) is not None:
            writes += shell_writes(shell_body(words), cwd, env)
        elif exe == "git" and "push" in words[1:]:
            writes.append(("git_private_repo", _push_destination(words, cwd)))
        elif exe == "gh":
            args = words[1:]
            if (any(v in args for v in ("create", "edit", "comment", "merge", "upload", "close", "review"))
                    or ("api" in args and any(a in ("-f", "-F", "--field", "--raw-field", "--input", "--method", "-X")
                                             or a.startswith(("--field=", "--raw-field=", "--input=", "--method=")) for a in args))):
                # --hostname can select another service; only the effective explicit/default host is checked.
                host = env.get("GH_HOST") or "github.com"
                for j, a in enumerate(args):
                    if a == "--hostname" and j + 1 < len(args):
                        host = args[j + 1]
                    elif a.startswith("--hostname="):
                        host = a.split("=", 1)[1]
                # API endpoint URLs and --repo can override GH_HOST without --hostname.
                extra_hosts = []
                if "api" in args:
                    rest = args[args.index("api") + 1:]
                    values = {"--hostname", "-X", "--method", "--input", "-f", "-F", "--field", "--raw-field", "-H", "--header", "-q", "--jq", "-t", "--template", "--cache", "--preview"}
                    at = 0
                    while at < len(rest):
                        arg = rest[at]
                        if arg in values:
                            at += 2
                        elif arg.startswith("-"):
                            at += 1
                        else:
                            if arg.startswith(("https://", "http://")):
                                extra_hosts.append(urlsplit(arg).hostname)
                            elif "$" in arg:
                                extra_hosts.append(None)  # unresolved endpoint: cannot approve a guessed host
                            break
                    if None in extra_hosts:
                        writes.append(("unknown", None))
                for j, a in enumerate(args):
                    value = args[j + 1] if a in ("-R", "--repo") and j + 1 < len(args) else a.split("=", 1)[1] if a.startswith("--repo=") else ""
                    if value.startswith(("https://", "http://")):
                        extra_hosts.append(urlsplit(value).hostname)
                writes += [("host", h.lower()) for h in extra_hosts or [host] if h]
        elif exe in ("curl", "wget"):
            urls, writing, ambiguous, _ = network_args(words)
            if ambiguous:
                writes.append(("unknown", None))
            elif writing:
                if any(FINAL_ACTION.search(unquote_plus(urlsplit(u).path)) for u in urls):
                    writes.append(("final_delivery", None))
                writes += [("host", urlsplit(u).hostname) for u in urls]
        elif exe in ("scp", "rsync"):
            dest = words[-1] if len(words) > 1 else ""
            m = re.match(r"(?:[^@/:]+@)?([A-Za-z0-9.-]+):", dest)
            if dest.startswith("rsync://"):
                writes.append(("host", urlsplit(dest).hostname))
            elif m:
                writes.append(("host", m.group(1).lower()))
    return writes


def action_name(tool):
    return re.sub(r"([a-z])([A-Z])", r"\1_\2", tool.rsplit("__", 1)[-1])


def final_action(tool, ti):
    if FINAL_ACTION.search(action_name(tool)):
        return True
    for key in ("action", "operation", "tool_name"):
        if isinstance(ti.get(key), str) and FINAL_ACTION.search(action_name(ti[key])):
            return True
    actions = ti.get("actions", [])
    return isinstance(actions, list) and any(
        final_action(str(action.get("name") or ""), action) for action in actions if isinstance(action, dict))


def connector_read(tool, ti):
    return tool in READ_ONLY_CONNECTORS or (tool in SCREENSHOT_CONNECTORS and ti.get("action") == "screenshot")


def connector_write(tool, ti):
    if WRITE_VERBS.search(action_name(tool)):
        return True
    if str(ti.get("method") or "").upper() in ("POST", "PUT", "PATCH", "DELETE"):
        return True
    return any(WRITE_VERBS.search(action_name(str(ti.get(k) or ""))) for k in ("action", "operation"))


def outbound(tool, ti, cwd, env=None):
    if not isinstance(tool, str):
        return []
    if tool.startswith("mcp__"):
        return [("mcp_tool", tool)] if connector_write(tool, ti) else []
    if tool == "Artifact" and "publish" in json.dumps(ti).lower():
        url = ti.get("destination") or ti.get("url") or ""
        return [("host", urlsplit(url).hostname)] if isinstance(url, str) else [("unknown", None)]
    if tool == "Bash":
        return shell_writes(ti.get("command", ""), cwd, env)
    return []


def risky(tool, ti):
    """Conservative fallback when parsing/config evaluation fails."""
    if tool in ("WebSearch", "WebFetch", "Artifact"):
        return True
    if isinstance(tool, str) and tool.startswith("mcp__"):
        return True  # Unknown and generic connectors must also fail closed.
    return tool == "Bash" and bool(re.search(r"\b(git|gh|curl|wget|scp|rsync)\b", str(ti)))


def check(tool, ti, cwd, env):
    if not configured(cwd, env):
        return None
    if isinstance(tool, str) and (tool.startswith("mcp__") or tool == "Artifact") and final_action(tool, ti):
        return ("deny", FINAL_DENIED)
    if isinstance(tool, str) and tool.startswith("mcp__"):
        if (GENERIC_EXECUTOR.search(action_name(tool))
                or not (WRITE_VERBS.search(action_name(tool)) or connector_read(tool, ti))):
            return ("deny", UNCLASSIFIED)
    writes = outbound(tool, ti, cwd, env)
    if any(kind == "final_delivery" for kind, _ in writes):
        return ("deny", FINAL_DENIED)
    connector_search = isinstance(tool, str) and tool.startswith("mcp__") and not connector_write(tool, ti)
    search = tool in ("WebSearch", "WebFetch") or connector_search
    fetch_urls = shell_urls(ti.get("command", "")) if tool == "Bash" else []
    search |= bool(fetch_urls)
    if not writes and not search:
        return None
    d = datadir.resolve_data_dir(cwd, env)
    cfg = datadir.load_config(d, env)
    if datadir.privacy_problems(cfg):
        return ("deny", "Invalid privacy configuration: fix it before external calls.")
    if search:
        identity = cfg.get("identity") or {}
        patterns = publish_gate.build_patterns(identity, identity.get("extra_private_terms"), d)
        text = json.dumps(ti if tool != "Bash" else fetch_urls, ensure_ascii=False)
        for _ in range(3):
            if any(rx.search(text) for _, rx in patterns):
                return ("deny", "Search/fetch contains a configured personal value. Remove it; searches and URLs cannot be approved destinations.")
            text = unquote_plus(text)
        if not writes:
            return None
    grants = cfg.get("privacy", {}).get("approved_destinations", [])
    for kind, dest in writes:
        key = {"git_private_repo": "remote", "mcp_tool": "tool", "host": "host"}.get(kind)
        if not key or not dest or not any(e.get("type") == kind and e.get(key) == dest for e in grants):
            return ("deny", DENIED)
    return ("ask", ASK)
