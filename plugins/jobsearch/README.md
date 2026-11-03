# jobsearch plugin

A neutral job-search engine for any profession. It triages vacancies, drafts honest cover letters, audits every claim against your own facts, and edits a tracker only through a safe script. It never sends, applies or submits anything. All personal data stays in your own data folder; this plugin carries none.

## Data folder and config
Point the plugin at your private data folder with `JOBSEARCH_DATA_DIR`. Put your settings in `jobsearch.config.yaml` inside it, or set `JOBSEARCH_CONFIG` to a config file kept elsewhere. Start from `reference/config.template.yaml` (or run `/jobsearch:jobsearch-setup`, which copies and validates it); to re-check a copy later, run the plugin's `scripts/datadir.py` with `validate PATH`. Layout and `paths.*` keys: `reference/data-contract.md`.

## Commands and skills
The plugin has 8 commands (`/jobsearch:<name>`) and 6 skills. Most of the workflow lives in the commands; the skills are helpers used inside them or on request. Full tables: the "What's inside" section of the root `README.md`.

Commands:
- `commands/rank.md` - triage a vacancy: duplicate check, legitimacy, blockers, match %, verdict.
- `commands/apply.md` - letter draft, optional targeted CV copy, grounding audit, hand-over (not sent); mode `tune` for grounded CV suggestions (format in `reference/cv-tune-format.md`).
- `commands/outcome.md` - record a reply, rejection, interview or silence in the tracker.
- `commands/followup.md` - applications waiting for an answer, follow-up drafts.
- `commands/interview.md` - interview support: `prep` (questions mapped to the story bank), `debrief` (capture and tag gaps), `redflags` (employer checklist).
- `commands/upskill.md` - skill-gap heat map from rejections, with a learning plan; mode `roadmap` for a 12-month career map.
- `commands/funnel.md` - funnel and patterns report from the tracker.
- `commands/jobsearch-setup.md` - create the data folder skeleton.

Skills:
- `skills/ats-screening/` - ATS CV screening and job-match analysis.
- `skills/cover-letter/` - letters from your facts and letter knowledge base.
- `skills/grounding-audit/` - claim-by-claim check against your facts.
- `skills/humanizer/` - edits formulaic wording while preserving facts and the author's supplied voice; no detector guarantee (MIT, see its `LICENSE`).
- `skills/linkedin-profile-optimizer/` - reviews or drafts supplied LinkedIn headline, About, Experience and skills sections from verified sources; distinguishes documented search behavior from recommendations. No automatic profile changes or ranking promises.
- `skills/career-paths/` - better-paid directions that fit your experience, salary only with source and date.

For LinkedIn review, ask Claude to use `linkedin-profile-optimizer` with your supplied profile sections and source CV. This is a skill, not an additional file in `commands/`.

## Scripts
`scripts/datadir.py` (data folder and config), `scripts/tracker_edit.py` (the only way the tracker is changed), `scripts/grounding_audit.py`, `scripts/funnel_report.py`, `scripts/repost_check.py`, `scripts/robots_check.py`, `scripts/publish_gate.py`, `skills/ats-screening/scripts/ats_technical_score.py` and `skills/ats-screening/scripts/pdf_technical_check.py`. Python standard library only, except two optional extras for the ATS scripts: PyMuPDF for `ats_technical_score.py`, pdfplumber + pypdf for `pdf_technical_check.py` (each says so when its extra is missing). `scripts/datadir.py show` prints the resolved data folder, config and absolute `paths.*`; data folder resolution order: `JOBSEARCH_DATA_DIR`, a `.jobsearch-data` marker file, a `jobsearch.config.yaml` in the project root.

## Session-start hook

`hooks/hooks.json` registers `hooks/session_start.py` for startup, resume, clear and compact. The hook reads the files configured by `paths.start_file` and `paths.todo_file` and adds the overview plus unchecked TODO items to Claude's context. It does not modify files.

It runs only when the current project is the resolved data folder or contains a `.jobsearch-data` marker. It stays silent in other projects, on data/config errors, and when the project's own Claude settings already define a SessionStart hook. A missing overview or TODO file is reported in the loaded context rather than breaking the session.

## Planned features

CV tailoring (`apply tune`), `upskill roadmap`, the LinkedIn data-dir mode and `career-paths` are shipped. Portal auto-scanning, an application-form assistant and email reply-watch are later opt-in designs; see the root README and [alternative-flow design](../../docs/alternative-flow.md) for their status and approval gates.

## Rules
The hard rules are in `reference/hard-rules.md` and cannot be switched off by config. Tracker statuses: `reference/statuses.md`. Changes: `CHANGELOG.md`.
