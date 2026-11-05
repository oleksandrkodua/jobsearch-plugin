# Jobsearch for Codex (local conservative edition)

The repository maintains one job-search workflow and Python toolset. Claude Code uses its slash commands directly. A create-only build converts the same commands to Codex skills and packages the helpers, scripts, references and runtime hooks. No personal data or private config is copied into the package.

## Build and install

From a source checkout, run `python3 tools/build_codex.py --out <absolute-new-marketplace-folder>`. The output must not exist. Rebuild to a new path after changes; the builder never replaces another installation, edits a shell profile, writes Codex settings or installs a plugin.

Run `codex plugin marketplace add <absolute-new-marketplace-folder>` in your own Terminal. Then open the plugin browser in a supported Codex desktop client, select Jobsearch for Codex and install Jobsearch. Review and trust the bundled hooks, then start a fresh chat. Availability varies by client/version: if hooks are unsupported or not trusted, do not treat them as active protection. This edition depends on local files/Python and is not a hosted web plugin or a public-directory submission.

Set `JOBSEARCH_DATA_DIR` and, when needed, `JOBSEARCH_CONFIG` yourself, or use a `.jobsearch-data` marker in the project. In the observed Codex setup, values configured through `shell_environment_policy.set` reached shell commands but not hooks; use a marker containing the absolute data-folder path so hooks can resolve the same folder. An empty or invalid marker blocks actions until fixed. The personal data folder is shared with Claude; it is not duplicated. Do not run both hosts against the same config simultaneously while updating it. Tracker operations use the existing exclusive lock.

## Program-specific commands and helpers

| Task | Claude Code | Codex skill |
|---|---|---|
| Help | `/jobsearch:help` | `$jobsearch-help` |
| Setup/update | `/jobsearch:jobsearch-setup [update]` | `$jobsearch-setup [update]` |
| Rank | `/jobsearch:rank` | `$jobsearch-rank` |
| Application/tune | `/jobsearch:apply [tune]` | `$jobsearch-apply [tune]` |
| Outcome | `/jobsearch:outcome` | `$jobsearch-outcome` |
| Follow-up | `/jobsearch:followup` | `$jobsearch-followup` |
| Interview | `/jobsearch:interview` | `$jobsearch-interview` |
| Upskill/roadmap | `/jobsearch:upskill [roadmap]` | `$jobsearch-upskill [roadmap]` |
| Funnel | `/jobsearch:funnel` | `$jobsearch-funnel` |
| Scan | `/jobsearch:scan` | `$jobsearch-scan` |

Select the named skill in the client UI if it does not accept `$` invocation. Codex's startup/help lists these skill names and modes. Resolver errors, setup reminders and scanner next steps also use that host's names. Stored overview text is displayed with matching commands without rewriting the user's files. The six helper skills keep their names but receive package-relative Codex instructions, not Claude macros. Root paths are resolved from the installed skill location, including when the package is relocated into a plugin cache.

## Behavior in Claude Code

The Claude package keeps native commands and PreToolUse decisions `ask`/`deny`. Outbound writes to exact approved destinations require a fresh explicit yes in chat plus the hook's permission ask. WebSearch/WebFetch inputs are checked for configured identity values. Creation of the first CV/master and facts/config edits ask; overwriting final CV/master is denied. Recognized send/reply/apply/submit tools always deny, even with grants. Browser/computer interactions that can submit are denied in the job-search project. Unknown connectors and generic executors deny before grants or read/GET hints are considered. Exact built-in read classifications live in `hooks/egress.py`; classified read inputs are checked for personal values. Applications and recruiter messages remain drafts.

## Behavior in Codex

Analysis, letters, CV suggestions, interview support and reports use the same rules. The Codex adapter inspects Bash/MCP events and every Add/Update/Delete/Move path in apply_patch. Since Codex currently ignores unsupported `ask` decisions, the adapter returns deny for every action that would ask in Claude. Approved outbound writes, facts/config changes and first CV/master creation are therefore manual: the plugin prepares the proposed action/content, the user executes it, and the plugin re-reads the result. It never silently promotes a denial to allow. The same absolute final-delivery denial and default denial of unknown/generic connectors apply in Codex; a different tool is not an escape from the policy. The tracker still uses its safe editor; no direct patch of the tracker is permitted.

Hosted WebSearch has no local hook event. Every Codex workflow requires a local preflight of the exact query/URL before the hosted call, as described in the packaged `reference/codex-runtime.md`. This is a procedural check, not forced interception. Hooks must actually run: process startup failures/timeouts and untrusted/unsupported hooks are outside the Python fail-closed guarantee.

The conservative behavior was explicitly selected for this edition. There are no one-time tokens or automatic permission bypasses. Installing or publishing is a separate user action. Nothing is sent or applied automatically.

## Check after installation

1. Invoke `$jobsearch-help`: it should list Codex skills, including setup update and apply tune, and report missing setup pieces rather than claiming ready from the data path alone.
2. In a disposable synthetic data folder, try a direct patch of `tracker/vacancies.csv`: it must be denied. Try editing a harmless draft under applications/: it should proceed. Do not use real applications for this check.
3. Run the privacy preflight with the synthetic identity email: it must exit 1 and print DENIED. A generic job query must exit 0. A changed query needs another preflight.

[Live smoke checks](audit-2026-11-04.md#follow-up-verification) covered these behaviors with synthetic data at `d57712e`. Repeat the checks after updating the installed package and reviewing hook trust. Full first-time onboarding remains outside the verified scope.

Official references checked 2026-11-04: [plugin packaging](https://developers.openai.com/plugins/build/plugins), [Claude plugin conversion](https://developers.openai.com/plugins/guides/submit-claude-plugin), [Codex hooks and limitations](https://learn.chatgpt.com/docs/hooks).

The pre-release audit additionally checks that a tool workdir cannot discard the session's marker-based data scope, helper metadata does not carry Claude-only allowed-tools, and generated/source frontmatter parses as YAML. See the repository audit report for reproducible checks, confirmed policies and remaining live checks.
