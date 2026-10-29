# jobsearch

A Claude Code plugin that works as a neutral job-search engine for any profession. It triages vacancies, drafts honest cover letters, audits every claim against the user's own facts, and edits a tracker only through a safe script. It never sends, applies or submits anything.

Personal data (profile, tracker, applications, private config) lives in the user's own data folder. This repository holds none.

## What's inside

Most of the workflow lives in 8 slash commands, called as `/jobsearch:<name>`. The 4 skills are helpers: Claude uses them inside those commands, or on their own when you ask for that task directly. Scripts do the deterministic work (tracker edits, audits, reports), so the model never edits the tracker by hand.

### Commands

| Command | What it does | Typical use |
|---|---|---|
| `rank` | Triages one or more vacancies (URL, pasted text, screenshot): host check, legitimacy observations, repost and duplicate check, blockers from config, requirement matrix, match %, verdict APPLY / NOT APPLY / ASK THE USER. Writes no CV and no letter. | You found a vacancy and want to know whether it is worth applying. |
| `apply` | Prepares one application: ATS pass, optional targeted CV copy, cover letter (drafter, reviewer, humanizer passes), then a mandatory grounding audit before hand-over. Never sends. | The verdict is APPLY and you want the letter and a checklist ready to send yourself. |
| `outcome` | Records a reply, rejection, interview or silence in the tracker with valid statuses, via `tracker_edit.py`. Offers `/interview debrief` after an interview. | A company answered, or you decided it will not. |
| `followup` | Lists applications waiting for an answer for N days and drafts a short follow-up. Draft only. | A week or two passed with no reply. |
| `interview` | Interview support for a tracked application, in three modes. `prep` (default): likely questions mapped to your story bank, consistency brief, gap bridges, questions to ask, optional mock interview. `debrief`: captures what was asked and what went badly, writes a debrief file, tags gaps. `redflags`: checks the employer against your blockers and red-flag list as SEEN / NOT SEEN / ASK. | Before a call (`prep`), right after it (`debrief`), or when something feels off about an employer (`redflags`). |
| `upskill` | Skill-gap heat map from your real rejections and declined vacancies, with a prioritized learning plan and study order. Aggregate mode, or one vacancy URL. | You want to know which gaps actually cost you vacancies. |
| `funnel` | Read-only funnel report from the tracker: stages, reply rate by host class and role type, rejection reasons by gap tag, median days to first reply. | You want the numbers and patterns across all applications. |
| `jobsearch-setup` | Creates a new data folder skeleton (profile, tracker header, config from the template, optional preset). Refuses any folder that is not new or empty. | First run, once. |

### Skills

| Skill | What it does | Not for |
|---|---|---|
| `ats-screening` | ATS CV screening and job-match analysis, including PDF technical checks (text layer, hidden text, parsing risk). Reads English, Russian and Ukrainian. | Writing or rewriting a CV or letter (use `cover-letter`). |
| `cover-letter` | Cover letters and application form answers for one vacancy, strictly from your facts file, master CV and letter knowledge base. Invents nothing, never sends. | CV scoring (`ats-screening`), fact-checking a finished text (`grounding-audit`), tracker updates (`outcome`). |
| `grounding-audit` | Factual audit of CVs, letters and recruiter replies: every date, employer, metric, tool and claim is checked against your facts file and master CV, after the mechanical script pass. | Writing letters (`cover-letter`), ATS scoring (`ats-screening`). |
| `humanizer` | Removes signs of AI-generated writing from a text (based on Wikipedia's "Signs of AI writing" guide). | Checking facts (`grounding-audit`), drafting a letter from scratch (`cover-letter`). |

Plugin-level list with the scripts: `plugins/jobsearch/README.md`.

### Coming next

Two approved addenda are designed but not built yet: CV tailoring (`docs/superpowers/specs/2026-10-28-cv-tailor-addendum.md`) and a career pack with a LinkedIn profile skill, career paths and `/upskill roadmap` (`docs/superpowers/specs/2026-10-28-career-pack-addendum.md`).

## Install

```
claude plugin marketplace add <github-owner>/jobsearch-plugin
claude plugin install jobsearch@jobsearch-marketplace
```

Then run `/jobsearch:jobsearch-setup`. It asks for a data folder, creates the skeleton (profile, tracker with header, config from the template, optional preset) in a new or empty folder only, and prints the `JOBSEARCH_DATA_DIR` line to put in your shell profile. The plugin never edits shell profiles.

## Data folder and config

The plugin finds your data folder in this order: (1) `JOBSEARCH_DATA_DIR`; (2) a `.jobsearch-data` marker file in the current project that contains the path; (3) a `jobsearch.config.yaml` in the current project's root, which makes the project itself the data folder. Nothing found means it stops and says so; it never guesses. Run `/jobsearch:jobsearch-setup` to create one. Settings live in `jobsearch.config.yaml` inside that folder; set `JOBSEARCH_CONFIG` to use a config kept elsewhere. Details and the `paths.*` keys: `plugins/jobsearch/reference/data-contract.md` (pointer page: `docs/data-contract.md`). Config template: `plugins/jobsearch/reference/config.template.yaml`.

## Privacy model

- The repo holds no personal value: no real names, employers, contacts, salary figures, vacancy ids or machine paths. Fixtures use a synthetic persona.
- The publish gate (`plugins/jobsearch/scripts/publish_gate.py`) takes its patterns from the user's private config, so it carries no personal value itself. It scans the working tree, the full git history and commit author and committer fields. Claude Code's local checkpoint refs (`refs/time-machine/*`) are skipped: they are never pushed and only keep old local snapshots reachable. Run it before any push; a pre-push hook that calls it is installed by the user, not by this repo.
- The gate also looks for the data-folder path (`--data-dir PATH` or `JOBSEARCH_DATA_DIR`, as written and in its `~/` form) and prints whether that check is active.
- `publish_gate.allow` in the private config lists per-file exceptions (for example the copyright line in `LICENSE`): a hit is skipped only inside that exact file and only for text within the allowed value. Commit authors and messages, ref names and file names are never exempt.
- The validator skips the gate with a WARN when no private config is available.

## Hard rules

Never send or apply, facts only from the data folder, the tracker changes only through `tracker_edit.py`. They cannot be switched off by config: `plugins/jobsearch/reference/hard-rules.md`.

## Presets

`plugins/jobsearch/presets/qa/` is an example configuration for a manual QA search (an example, not a default). To write one for another profession: `docs/presets.md`.

## Opt-in alternative flow

Board scanner, application assistant and reply watch are not part of the main cycle and are off by default: `docs/alternative-flow.md`.

## Tests and validator

```
PYTHONDONTWRITEBYTECODE=1 python3 -X dev -m unittest discover -s tests -v
python3 -B evals/validate_repo.py
JOBSEARCH_CONFIG=<private config> python3 plugins/jobsearch/scripts/publish_gate.py --repo .
```

Requires Python 3.9+. Python standard library only, with two optional extras for the `ats-screening` skill: PyMuPDF (`pip install pymupdf`) for `ats_technical_score.py`, and pdfplumber + pypdf (`pip install pdfplumber pypdf`) for `pdf_technical_check.py`. Each script says so when its extra is missing; everything else runs without them.

## Licence and notices

`LICENSE`. Third-party licences and credited ideas: `THIRD-PARTY-NOTICES.md`.
