# jobsearch

A Claude Code plugin that works as a neutral job-search engine for any profession. It triages vacancies, drafts honest cover letters, audits every claim against the user's own facts, and edits a tracker only through a safe script. It never sends, applies or submits anything.

Personal data (profile, tracker, applications, private config) lives in the user's own data folder. This repository holds none.

## What's inside

Most of the workflow lives in 9 slash commands, called as `/jobsearch:<name>`. The 6 skills are helpers: Claude uses them inside those commands, or on their own when you ask for that task directly. Scripts do the deterministic work (tracker edits, audits, reports), so the model never edits the tracker by hand.

### Commands

| Command | What it does | Typical use |
|---|---|---|
| `rank` | Triages one or more vacancies (URL, pasted text, screenshot): host check, legitimacy observations, repost and duplicate check, blockers from config, requirement matrix, match %, verdict APPLY / NOT APPLY / ASK THE USER. Up to 10 vacancies per run; the rest is offered as the next batch. Optional location filter: Ukraine or not, remote or not (`--country`, `--remote`, defaults in `targets.country` / `targets.remote`); a vacancy whose location is not stated is never filtered out. Writes no CV and no letter. | You found a vacancy and want to know whether it is worth applying. |
| `apply` | Prepares one application: ATS pass, optional targeted CV copy, cover letter (drafter, reviewer, humanizer passes), then a mandatory grounding audit before hand-over. Never sends. Mode `tune`: ATS feedback and grounded CV rewrite suggestions for one vacancy; a targeted CV copy only on request. | The verdict is APPLY and you want the letter and a checklist ready to send yourself. Or `tune`: see how to tailor your CV to one vacancy without inventing anything. |
| `outcome` | Records a reply, rejection, interview or silence in the tracker with valid statuses, via `tracker_edit.py`. Offers `/interview debrief` after an interview. | A company answered, or you decided it will not. |
| `followup` | Lists applications waiting for an answer for N days and drafts a short follow-up. Draft only. | A week or two passed with no reply. |
| `interview` | Interview support for a tracked application, in three modes. `prep` (default): likely questions mapped to your story bank, consistency brief, gap bridges, questions to ask, optional mock interview. `debrief`: captures what was asked and what went badly, writes a debrief file, tags gaps. `redflags`: checks the employer against your blockers and red-flag list as SEEN / NOT SEEN / ASK. | Before a call (`prep`), right after it (`debrief`), or when something feels off about an employer (`redflags`). |
| `upskill` | Skill-gap heat map from your real rejections and declined vacancies, with a prioritized learning plan and study order. Aggregate mode, one vacancy URL, or `roadmap`: a 12-month career map with monthly goals, certifications and networking. | You want to know which gaps actually cost you vacancies. |
| `funnel` | Read-only funnel report from the tracker: stages, reply rate by host class and role type, rejection reasons by gap tag, median days to first reply. | You want the numbers and patterns across all applications. |
| `jobsearch-setup` | Creates a new data folder skeleton (profile, tracker header, config from the template, optional preset). Refuses any folder that is not new or empty. | First run, once. |
| `help` | Shows every command (with its modes) and skill in one line each, the usual workflow and whether a data folder is set up. Works in any project, also before setup. Changes nothing. | You are new to the plugin, or forgot which command does what. |

### Skills

| Skill | What it does | Not for |
|---|---|---|
| `ats-screening` | ATS CV screening and job-match analysis, including PDF technical checks (text layer, hidden text, parsing risk). Reads English, Russian and Ukrainian. | Rewriting or tailoring a CV (`apply tune`), writing a letter (`cover-letter`). |
| `cover-letter` | Concise cover letters and application form answers for one vacancy, strictly from your facts file, master CV and letter knowledge base. Humanizer preserves the facts; a final grounding audit checks the rewrite. Invents nothing, never sends. | CV scoring (`ats-screening`), fact-checking a finished text (`grounding-audit`), tracker updates (`outcome`). |
| `grounding-audit` | Factual audit of CVs, letters and recruiter replies: every date, employer, metric, tool and claim is checked against your facts file and master CV, after the mechanical script pass. | Writing letters (`cover-letter`), ATS scoring (`ats-screening`). |
| `humanizer` | Edits formulaic wording while preserving the author's facts and supplied voice. Based on Wikipedia's "Signs of AI writing" guide; does not guarantee detector results. | Checking facts (`grounding-audit`), drafting a letter from scratch (`cover-letter`). |
| `linkedin-profile-optimizer` | Reviews or drafts LinkedIn headlines, About, Experience and skills from supplied sources. Separates documented search behavior from recommendations and explains how to check discovery without invented ranking scores. With a jobsearch data dir it lists conflicts with the master CV first, traces every line to the master CV or facts file (else NOT IN SOURCES) and runs the grounding audit. | Sending messages, applying, or making unrequested profile edits. |
| `career-paths` | Recommends 3-5 better-paid directions that fit your experience and gap table, with labelled evidence for each; salary figures only with source link, date, region and gross/net, never converted or averaged. | One vacancy's fit (`rank`), a study plan (`upskill`), offer negotiation. |

For LinkedIn help, ask Claude to review the profile sections you provide using `linkedin-profile-optimizer`, for example: "Review my LinkedIn About and headline against my supplied CV; suggest only grounded changes." It is a skill, not an extra file in the slash-command directory. It prepares suggestions; it does not update your profile automatically.

Plugin-level list with the scripts: `plugins/jobsearch/README.md`.

### Session-start context

A PreToolUse write guard (`plugins/jobsearch/hooks/guard_writes.py`) enforces hard rules 5 and 6 in code: Claude cannot write the tracker, the final CV files or the master CV directly, and must ask before editing the facts file. In the job-search project it also asks before any browser or computer-use click, typing, form filling or submit, and before any tool that sends or replies, so an Apply or Send control is always yours (hard rule 1). `tracker_edit.py` locks the tracker while it writes, so two sessions cannot lose each other's edit. The plugin also includes a read-only SessionStart hook (`plugins/jobsearch/hooks/session_start.py`). In the configured job-search project it first shows what each command and skill does (one line each, with its modes), then loads the overview and open TODO items (at most 30, plus a count of the rest) into Claude's context on startup, resume, clear or compact. It stays silent in unrelated projects, on data/config errors, or when the project already defines its own SessionStart hook. Details: the "Session-start hook" section of `plugins/jobsearch/README.md`.

### Coming next

Both approved addenda are shipped: CV tailoring (`/apply tune`) and the career pack (`/upskill roadmap`, the data-dir mode of `linkedin-profile-optimizer`, `career-paths`). The next planned phases are portal auto-scanning, an application-form assistant and email reply-watch; see `docs/alternative-flow.md`. Ideas set aside on purpose, with the evidence that would bring them back, are in `docs/deferred-ideas.md`.

## Install

```
claude plugin marketplace add <github-owner>/jobsearch-plugin
claude plugin install jobsearch@jobsearch-marketplace
```

Run `/jobsearch:help` for an overview of what the plugin does. Then run `/jobsearch:jobsearch-setup`. It asks for a data folder, creates the skeleton (profile, tracker with header, config from the template, optional preset) in a new or empty folder only, and prints the `JOBSEARCH_DATA_DIR` line to put in your shell profile. The plugin never edits shell profiles.

## Data folder and config

The plugin finds your data folder in this order: (1) `JOBSEARCH_DATA_DIR`; (2) a `.jobsearch-data` marker file in the current project that contains the path; (3) a `jobsearch.config.yaml` in the current project's root, which makes the project itself the data folder. Nothing found means it stops and says so; it never guesses. Run `/jobsearch:jobsearch-setup` to create one. Settings live in `jobsearch.config.yaml` inside that folder; set `JOBSEARCH_CONFIG` to use a config kept elsewhere. Details and the `paths.*` keys: `plugins/jobsearch/reference/data-contract.md` (pointer page: `docs/data-contract.md`). Config template: `plugins/jobsearch/reference/config.template.yaml`.

## Privacy model

- The repo holds no personal value: no real names, employers, contacts, salary figures, vacancy ids or machine paths. Fixtures use a synthetic persona.
- The publish gate (`plugins/jobsearch/scripts/publish_gate.py`) takes its patterns from the user's private config, so it carries no personal value itself. It scans the working tree, the full git history and commit author and committer fields. Claude Code's local checkpoint refs (`refs/time-machine/*`) are skipped: they are never pushed and only keep old local snapshots reachable. Run it before any push; a pre-push hook that calls it is installed by the user, not by this repo.
- The gate also looks for the data-folder path (`--data-dir PATH` or `JOBSEARCH_DATA_DIR`, as written and in its `~/` form) and prints whether that check is active.
- `publish_gate.allow` in the private config lists per-file exceptions (for example the copyright line in `LICENSE`): a hit is skipped only inside that exact file and only for text within the allowed value. Commit authors and messages, ref names and file names are never exempt.
- The validator skips the gate with a WARN when no private config is available.

## Where your personal data goes

What the plugin itself does with your profile, CV, tracker and config (checked 2026-11-04):
- **Stays on your machine:** everything personal lives in your data folder and your private config. The plugin's scripts read and write only there (the tracker only through `tracker_edit.py`, with a backup and a changelog).
- **No telemetry, no uploads:** no script sends anything anywhere. The only network call in a script is `robots_check.py`, which downloads a site's public `robots.txt` and sends nothing about you.
- **Fetches send nothing personal:** commands fetch only the vacancy or employer URLs you give, plus web searches for study resources or salary ranges. The plugin's rules forbid opening links found inside a vacancy.
- **Nothing is sent, posted or submitted on your behalf** (hard rule 1). You send every letter and every application yourself. In the job-search project, the write and outreach guard hook asks before any browser click, typing or submit, and before any tool that sends or replies.
- **Never in the public repo:** the publish gate blocks any push that contains your configured identity values, data-folder path or secrets.
- **Claude itself:** like any Claude Code session, the text you work with is processed by the model you use. The plugin adds no other recipient.

Known limit, to be closed in 1.0.0 by the approved egress guard (hard rule 8, `docs/superpowers/specs/2026-11-04-egress-guard-addendum.md`): the plugin's rules say what to fetch and send, but no hook yet checks that a web search, a fetched URL or another connector call (for example publishing a page or creating a document) carries no personal value. Until then, nothing personal should leave except where you explicitly asked for it.

## Hard rules

Never send or apply, facts only from the data folder, the tracker changes only through `tracker_edit.py`. They cannot be switched off by config: `plugins/jobsearch/reference/hard-rules.md`.

## Presets

`plugins/jobsearch/presets/qa/` is an example configuration for a manual QA search (an example, not a default). To write one for another profession: `docs/presets.md`.

## Opt-in alternative flow

Portal auto-scanning, an application-form assistant and email reply-watch are planned later phases, not shipped features. Their opt-in design and approval gates are documented in `docs/alternative-flow.md`.

## Tests and validator

```
PYTHONDONTWRITEBYTECODE=1 python3 -X dev -m unittest discover -s tests -v
python3 -B evals/validate_repo.py
JOBSEARCH_CONFIG=<private config> python3 plugins/jobsearch/scripts/publish_gate.py --repo .
```

Requires Python 3.9+. Python standard library only, with two optional extras for the `ats-screening` skill: PyMuPDF (`pip install pymupdf`) for `ats_technical_score.py`, and pdfplumber + pypdf (`pip install pdfplumber pypdf`) for `pdf_technical_check.py`. Each script says so when its extra is missing; everything else runs without them.

## Licence and notices

`LICENSE`. Third-party licences and credited ideas: `THIRD-PARTY-NOTICES.md`.
