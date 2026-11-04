# Codex conservative runtime

These restrictions apply to the Codex package, in addition to the shared hard rules. The package is for local execution with Python 3.9+ and a private data folder. It is manually installed in a supported Codex desktop client; hooks must be reviewed and trusted. Do not claim the hooks are active merely because the plugin appears installed. Do not change the host's approval or trust settings automatically.

## Commands and helpers

Use the packaged skills: `$jobsearch-help`, `$jobsearch-setup` (or update), `$jobsearch-rank`, `$jobsearch-apply` (or tune), `$jobsearch-outcome`, `$jobsearch-followup`, `$jobsearch-interview`, `$jobsearch-upskill`, `$jobsearch-funnel` and `$jobsearch-scan`. These are skills, not Claude slash commands. Existing helper skills (ats-screening, cover-letter, grounding-audit, humanizer, linkedin-profile-optimizer, career-paths) use the same installed files and config.

Resolve the plugin root from the actual loaded SKILL.md (two directories above its folder). Replace instruction placeholders `${JOBSEARCH_PLUGIN_ROOT}` / `${JOBSEARCH_SKILL_DIR}` with actual absolute paths in every file read or command; they are not Codex macros or automatically exported variables. Do not rely on the user's project cwd or a variable saved by a previous shell call.

## Permission decisions

Current Codex PreToolUse supports deny but NOT ask: unsupported ask output can fail the hook and continue the action. The adapter therefore converts EVERY shared ask to deny. There is no retry permission or token in this mode. If an operation requires confirmation (protected facts/config edits, first creation of a CV/master, or an approved outbound write), show its exact proposed content/action and ask the user to execute it themselves in their Terminal or app. Do not retry with Bash, another connector, altered paths, approval escalation or a disabled hook to evade the denial. Prepare new unprotected draft files where useful for review; a draft is never the saved authoritative fact or CV.

Setup/update may therefore require manual saves by the user. Report each unsaved step as pending; re-read after the user reports saving it. No automatic applications or recruiter messages. An approved destination never overrides the manual-execution requirement.

## Hosted search/fetch preflight

Hosted WebSearch is outside Codex's local hook path. Before EVERY hosted query or fetched URL, run the shared local check on the exact pending input. Prepare one local JSON event (not in the public repo): `{"tool_name":"WebSearch","cwd":"<project>","tool_input":{"query":"<exact query>"}}` or `{"tool_name":"WebFetch","cwd":"<project>","tool_input":{"url":"<exact URL>"}}`. Pipe that file into the installed `hooks/codex_guard.py` with `--preflight`. For a batch check every query/URL separately, immediately before use. This runs no web request. Exit 1 = stop; exit 0 = use exactly that checked query/URL. Any changed query needs a fresh check. Do not include profile/CV text in search strings or URLs.

This preflight is a workflow requirement; the host cannot technically force it before hosted web calls. Explicit denials from supported local calls are covered by hook tests. A missing Python executable, process-start failure, timeout, untrusted hook or unsupported host path is not a fail-closed guarantee; do not label this runtime as full security parity with Claude or as a sandbox for arbitrary code.
