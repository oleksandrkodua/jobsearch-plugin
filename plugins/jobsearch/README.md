# jobsearch plugin

A neutral job-search engine for any profession. It triages vacancies, drafts honest cover letters, audits every claim against your own facts, and edits a tracker only through a safe script. It never sends, applies or submits anything. All personal data stays in your own data folder; this plugin carries none.

## Data folder and config
Point the plugin at your private data folder with `JOBSEARCH_DATA_DIR`. Put your settings in `jobsearch.config.yaml` inside it, or set `JOBSEARCH_CONFIG` to a config file kept elsewhere. Start from `reference/config.template.yaml` (or run `/jobsearch:jobsearch-setup`, which copies and validates it); to re-check a copy later, run the plugin's `scripts/datadir.py` with `validate PATH`. Layout and `paths.*` keys: `reference/data-contract.md`.

## Commands and skills
Most of the workflow lives in the commands (`/jobsearch:<name>`); the skills are helpers used inside them or on request. Full tables: the "What's inside" section of the root `README.md`.

Commands:
- `commands/rank.md` - triage a vacancy: duplicate check, legitimacy, blockers, match %, verdict.
- `commands/apply.md` - letter draft, optional targeted CV copy, grounding audit, hand-over (not sent).
- `commands/outcome.md` - record a reply, rejection, interview or silence in the tracker.
- `commands/followup.md` - applications waiting for an answer, follow-up drafts.
- `commands/interview.md` - interview support: `prep` (questions mapped to the story bank), `debrief` (capture and tag gaps), `redflags` (employer checklist).
- `commands/upskill.md` - skill-gap heat map from rejections, with a learning plan.
- `commands/funnel.md` - funnel and patterns report from the tracker.
- `commands/jobsearch-setup.md` - create the data folder skeleton.

Skills:
- `skills/ats-screening/` - ATS CV screening and job-match analysis.
- `skills/cover-letter/` - letters from your facts and letter knowledge base.
- `skills/grounding-audit/` - claim-by-claim check against your facts.
- `skills/humanizer/` - removes signs of AI-written text (MIT, see its `LICENSE`).

## Scripts
`scripts/datadir.py` (data folder and config), `scripts/tracker_edit.py` (the only way the tracker is changed), `scripts/grounding_audit.py`, `scripts/funnel_report.py`, `scripts/repost_check.py`, `scripts/robots_check.py`, `scripts/publish_gate.py`, `skills/ats-screening/scripts/ats_technical_score.py` and `skills/ats-screening/scripts/pdf_technical_check.py`. Python standard library only, except two optional extras for the ATS scripts: PyMuPDF for `ats_technical_score.py`, pdfplumber + pypdf for `pdf_technical_check.py` (each says so when its extra is missing). `scripts/datadir.py show` prints the resolved data folder, config and absolute `paths.*`; data folder resolution order: `JOBSEARCH_DATA_DIR`, a `.jobsearch-data` marker file, a `jobsearch.config.yaml` in the project root.

## Rules
The hard rules are in `reference/hard-rules.md` and cannot be switched off by config. Tracker statuses: `reference/statuses.md`. Changes: `CHANGELOG.md`.
