# Addendum: egress guard - personal data leaves only to approved places, after two confirmations

Status: APPROVED by the owner 2026-11-04. Plan and code follow; ships in 1.0.0.
Parent spec: `2026-10-27-jobsearch-plugin-design.md` §10 (hard rules), §7 (publish gate). Extends `hooks/guard_writes.py` (0.4.0).

Owner requirements, 2026-11-04:
- personal data leaves only to places the user approved, and only after two confirmations;
- a git push with personal data goes only to a private repository, and only after the user agrees twice.

This closes the three gaps found the same day: web search and fetch are unchecked, write connectors are unguarded, and there is no two-step confirmation for outbound data. The design is the smallest one that closes them.

## 1. Two simple checks, no content scanning
**Check A: web search and fetch.** `WebSearch` (the query) and `WebFetch` (the URL) are **denied** if they contain a configured identity value. Identity values are `identity.full_name`, `short_name`, `emails`, `phones` (all variants), `handles`, `links`, `extra_private_terms` and the data-dir path. Matching reuses `publish_gate.py`'s pattern builder, so there is one source of truth. A search is never an approved destination, so there is no allow-list here. Searches without a personal value go through untouched.

**Check B: anything that writes outside the machine.** These calls are gated whatever their content:
- `mcp__*` tools whose name says create, update, publish, upload, post, send, reply, comment, share or draft;
- the `Artifact` publish;
- `Bash` with `git push`, `gh` (issue, pr, gist, release, `api` with a body), `curl`/`wget` sending a body, `scp`, or `rsync` to a host.

Outcomes:
- **Destination not in `privacy.approved_destinations`:** **deny**, with how to approve it.
- **Destination approved:** **ask**. That is confirmation 2, enforced in code. Confirmation 1 is the user's explicit "yes" in chat naming the destination and what goes there. The model must have it before making the call, and one "yes" does not cover later calls.

Why no content scanning: outbound writes are rare in a job search, so always confirming them costs little. Matching CV text against every call would be slower, fragile and still miss paraphrases. Read-only connector calls (get, list, search, read, fetch) are not gated.

## 2. Approved destinations
New config key, empty by default, so nothing goes out:
```yaml
privacy:
  approved_destinations:
    - {type: git_private_repo, remote: "github.com/<owner>/<repo>"}
    - {type: mcp_tool, tool: "mcp__<server>__<tool>"}
    - {type: host, host: "<host>"}
```
- Entries are added or removed only through `/jobsearch:jobsearch-setup update`, after two separate confirmations in chat.
- `git_private_repo` is accepted only after the user confirms twice that the repository is private and that they agree to push personal data there.
- A public repository can never be approved. Pushing personal data to a public repo stays blocked by the publish gate on the plugin repo and by Check B everywhere else.

The hook does not call the network to check repository visibility. That is slow and fails inside the sandbox. Privacy is the user's twice-confirmed statement at approval time.

## 3. New hard rule 8
> 8. Personal data leaves the machine only to a destination the user approved in `privacy.approved_destinations`, and only after two separate confirmations: the user's explicit "yes" in chat naming the destination, then the hook's ask. Web searches and fetched URLs never carry personal values. A git push with personal data goes only to an approved private repository.

## 4. Where it runs and how it fails
- **Where:** in every project where a data dir resolves, because personal data can be copied anywhere. No data dir means no identity patterns and no opinion.
- **Fail closed for Check B:** if the hook errors on a call that matches Check B, it answers deny. An extra prompt is cheaper than a leak.
- **Fail open everywhere else:** a session must never break.

## 5. Changes
- **`reference/hard-rules.md`:** add rule 8.
- **`hooks/guard_writes.py`:** add Checks A and B. **`hooks/hooks.json`:** add `WebSearch|WebFetch|Artifact` to the matcher (`mcp__.*` and `Bash` are already there).
- **`scripts/publish_gate.py`:** expose its pattern builder as a function, so the hook reuses it without new code.
- **`scripts/datadir.py`:** schema for `privacy.approved_destinations`. **`config.template.yaml`:** the key, empty.
- **`jobsearch-setup update`:** add or remove a destination, with two confirmations.
- **README:** "Where your personal data goes" drops its "known limit" paragraph and describes rule 8.
- **Parent spec:** §10 gets rule 8, and §3.4 gets the key.
- **Ships in 1.0.0**, together with the onboarding.

## 6. Verification (for the later plan)
- **Unit tests, Check A:**
  - a WebSearch with an email or a phone variant is denied;
  - a WebSearch without one gets no opinion;
  - a WebFetch URL with the name in the query string is denied.
- **Unit tests, Check B:**
  - an MCP create/publish/send call or an Artifact publish is denied when the destination is not approved and answered with ask when it is;
  - read-only MCP calls are ignored;
  - `git push` to an unapproved remote is denied, and to an approved private remote it gets ask;
  - `curl -d` is denied;
  - an internal error on a Check B call is denied.
- **Unit test, shared patterns:** the hook and the publish gate use the same identity patterns.
- **Manual checklist** on the synthetic persona.

## Confirmed policy amendment after audit (2026-11-04)

This amendment takes precedence over the earlier send/read connector examples above. Final send/reply/apply/submit actions always deny; they cannot be approved destinations. Browser/computer click/type/fill/submit interactions in the job-search project also deny. Unknown connectors and generic executors deny before grants; GET/read hints do not classify them. Exact built-in read classifications require source review, and classified read inputs are checked for identity values. Supported non-message writes retain the existing exact-grant/two-confirmation procedure in Claude and manual execution in conservative Codex.
