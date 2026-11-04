# Jobsearch for Claude Code and Codex

A neutral job-search engine for any profession. It triages vacancies, drafts honest cover letters, audits every claim against your own facts, and edits a tracker only through a safe script. It never sends, applies or submits anything. All personal data stays in your own data folder; this plugin carries none.

## Data folder and config
Point the plugin at your private data folder with `JOBSEARCH_DATA_DIR`. Put your settings in `jobsearch.config.yaml` inside it, or set `JOBSEARCH_CONFIG` to a config file kept elsewhere. Start from `reference/config.template.yaml` (or run `/jobsearch:jobsearch-setup`, which copies and validates it); to re-check a copy later, run the plugin's `scripts/datadir.py` with `validate PATH`. Layout and `paths.*` keys: `reference/data-contract.md`.

## Commands and skills
The plugin has 10 commands (`/jobsearch:<name>`) and 6 skills. Most of the workflow lives in the commands; the skills are helpers used inside them or on request. Full tables: the "What's inside" section of the root `README.md`.

Commands:
- `commands/rank.md` - triage a vacancy: duplicate check, legitimacy, blockers, match %, verdict; up to 10 vacancies per run; optional filter by country (Ukraine or not) and remote (`--country`, `--remote`, or `targets.country` / `targets.remote` in the config).
- `commands/apply.md` - letter draft, optional targeted CV copy, grounding audit, hand-over (not sent); mode `tune` for grounded CV suggestions (format in `reference/cv-tune-format.md`).
- `commands/outcome.md` - record a reply, rejection, interview or silence in the tracker.
- `commands/followup.md` - applications waiting for an answer, follow-up drafts.
- `commands/interview.md` - interview support: `prep` (questions mapped to the story bank), `debrief` (capture and tag gaps), `redflags` (employer checklist).
- `commands/upskill.md` - skill-gap heat map from rejections, with a learning plan; mode `roadmap` for a 12-month career map.
- `commands/funnel.md` - funnel and patterns report from the tracker.
- `commands/scan.md` - on-demand scan of approved Greenhouse/Lever boards, off by default; candidates go to rank.
- `commands/jobsearch-setup.md` - create the data folder skeleton.
- `commands/help.md` - overview of all commands, modes and skills, the workflow and the setup status; works without a data folder.

Skills:
- `skills/ats-screening/` - ATS CV screening and job-match analysis.
- `skills/cover-letter/` - letters from your facts and letter knowledge base.
- `skills/grounding-audit/` - claim-by-claim check against your facts.
- `skills/humanizer/` - edits formulaic wording while preserving facts and the author's supplied voice; no detector guarantee (MIT, see its `LICENSE`).
- `skills/linkedin-profile-optimizer/` - reviews or drafts supplied LinkedIn headline, About, Experience and skills sections from verified sources; distinguishes documented search behavior from recommendations. No automatic profile changes or ranking promises.
- `skills/career-paths/` - better-paid directions that fit your experience, salary only with source and date.

For LinkedIn review, ask Claude to use `linkedin-profile-optimizer` with your supplied profile sections and source CV. This is a skill, not an additional file in `commands/`.

## Scripts
`scripts/datadir.py` (data folder and config), `scripts/tracker_edit.py` (the only way the tracker is changed; it holds a lock file while it writes), `scripts/grounding_audit.py`, `scripts/funnel_report.py`, `scripts/repost_check.py`, `scripts/robots_check.py`, `scripts/portal_scan.py`, `scripts/publish_gate.py`, `skills/ats-screening/scripts/ats_technical_score.py` and `skills/ats-screening/scripts/pdf_technical_check.py`. Python standard library only, except two optional extras for the ATS scripts: PyMuPDF for `ats_technical_score.py`, pdfplumber + pypdf for `pdf_technical_check.py` (each says so when its extra is missing). `scripts/datadir.py show` prints the resolved data folder, config and absolute `paths.*`; data folder resolution order: `JOBSEARCH_DATA_DIR`, a `.jobsearch-data` marker file, a `jobsearch.config.yaml` in the project root.

## Write guard hook

`hooks/hooks.json` also registers `hooks/guard_writes.py` as a PreToolUse hook for Write, Edit, MultiEdit, NotebookEdit and Bash. When a data folder resolves, it denies direct writes to the tracker (and its CHANGELOG.csv and history folder), to the files in `paths.cv_files` and to `paths.master_cv`, and asks before an edit of `paths.facts` or a Bash command that looks like it writes one of those files; `tracker_edit.py` is allowed. Without a data folder it has no opinion. In a configured project, check errors deny protected writes and connector calls. Recognized send/reply/apply/submit tools deny regardless of destination grants. In the job-search project itself (the data folder, or a project with the `.jobsearch-data` marker), browser/computer click/type/fill/submit actions also deny; the user interacts manually (hard rule 1). Unknown/generic connectors deny until classified in the plugin source. It cannot see writes made by other programs outside Claude's tools.

## Session-start hook

`hooks/hooks.json` registers `hooks/session_start.py` for startup, resume, clear and compact. The hook reads the files configured by `paths.start_file` and `paths.todo_file` and adds the overview plus unchecked TODO items to Claude's context. It does not modify files.

On startup and clear (not on resume or compact) it also adds a list of every command and skill with a one-line description and its modes, taken from their own frontmatter, and asks Claude to show that overview to the user first, so a new user sees what the plugin can do. At most 30 open TODO items are shown, plus a count of the rest.

It runs only when the current project is the resolved data folder or contains a `.jobsearch-data` marker. It stays silent in other projects, on data/config errors, and when the project's own Claude settings already define a SessionStart hook. A missing overview or TODO file is reported in the loaded context rather than breaking the session.

## Planned features

CV tailoring (`apply tune`), `upskill roadmap`, the LinkedIn data-dir mode and `career-paths` are shipped. The portal scanner `/jobsearch:scan` (Greenhouse and Lever) is shipped and off by default. An application-form assistant and email reply-watch remain later opt-in designs; see the root README and [alternative-flow design](../../docs/alternative-flow.md) for their status and approval gates.

## Rules
The hard rules are in `reference/hard-rules.md` and cannot be switched off by config. Tracker statuses: `reference/statuses.md`. Changes: `CHANGELOG.md`.

## Onboarding and outbound checks

Setup is guided and skippable; `jobsearch-setup update` revisits only selected answers, with backups and two confirmations before overwrite. English CV/master files are create-only at setup and then read-only. `scripts/onboarding.py status` reports missing pieces and is used by help and session start. Chat supports Ukrainian/English; letters use those two languages, CV output English.

`hooks/egress.py` reuses the publish gate's identity patterns for search/fetch. Supported non-message external writes need exact grants in `privacy.approved_destinations`; every call still needs fresh chat confirmation followed by the hook ask. Git grants name private repositories only, as twice confirmed by the user. Erroring checks deny outbound/protected writes in a configured project; classified read-only connector inputs are checked for personal values. Exact built-in read classifications live in `hooks/egress.py`; a destination grant or read/GET hint cannot authorize an unknown/generic executor. The hook covers documented command/tool families, not arbitrary or deliberately obfuscated executable code.

The Codex edition is generated by `tools/build_codex.py` in the repo root; see `docs/codex.md` there for install, host-specific command names and conservative behavior. It converts commands to skills and uses `hooks/codex_guard.py` / `hooks/codex-hooks.json`; all ask decisions become deny/manual execution. The Claude package continues to load `hooks/hooks.json`. Neither edition installs itself.
