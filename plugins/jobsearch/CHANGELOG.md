# Changelog

## 0.5.0 (unreleased)
- `/rank` location filter: country (`any` | `ukraine` | `not_ukraine`) and remote (`any` | `yes` | `no`), defaults in `targets.country` / `targets.remote`, overridden per run with `--country` / `--remote`. Classified from the vacancy text only; Unknown is never filtered out; filtered vacancies stay in the batch table as FILTERED (country) / FILTERED (remote). `datadir.py validate` rejects other values.

## 0.4.0 (2026-11-04)
- Write guard: PreToolUse hook `hooks/guard_writes.py` enforces hard rules 5 and 6 in code. Direct Write/Edit/MultiEdit/NotebookEdit of the tracker (with CHANGELOG.csv and history/), `paths.cv_files` and `paths.master_cv` is denied; edits of `paths.facts` and Bash commands that look like writes to protected files ask the user. Silent without a data dir or on error.
- Outreach guard (same hook): in the job-search project, browser / computer-use clicks, typing, form filling and submits, and MCP send/reply tools, ask the user first (hard rule 1).
- Tracker lock: `tracker_edit.py add/set` hold an exclusive `<tracker>.lock` from read to write, so two sessions cannot lose each other's edit; a foreign lock is reported, never removed.
- `/rank` batch mode is capped at 10 vacancies per run; the rest is offered as the next batch.
- SessionStart hook shows at most 30 open TODO items plus a count of the rest.
- SessionStart overview: on startup and clear the hook lists every command and skill with a one-line description and its modes (built from their frontmatter) and asks Claude to show it to the user first.
- `/jobsearch:help`: the same overview on demand, plus the usual workflow and the setup status; works in any project, also before a data folder exists. `session_start.py --list` prints the overview.

## 0.3.0 (2026-11-03)
- `/apply tune`: ATS feedback and grounded CV rewrite suggestions for one vacancy (format and guardrails in `reference/cv-tune-format.md`); a targeted copy only on request; the final CV files are never edited.
- `/upskill roadmap`: 12-month career map built on the gap table, with monthly goals, sourced certifications and networking drafts; no new config keys.
- `linkedin-profile-optimizer`: data-dir mode (conflicts first, every line traced to the master CV or facts, `grounding_audit.py --kind cv` on the draft).
- Skills: career-paths (sourced salary ranges only, own-market signal from the funnel report).

## 0.2.0 (2026-11-03)
- LinkedIn profile optimizer skill (fifth skill) with three synthetic evaluation prompts: grounded profile review, documented search behavior, no ranking guarantees or automatic profile edits.
- Cover-letter and humanizer guidance: concise vacancy-specific wording, no invented personal reactions, factual review after rewriting, no detector guarantees; punctuation follows the user's config.
- Funnel report: negated reply notes ("did not get a reply", "no response yet") and auto-replies no longer count as replies; `--out` guard is case-safe on case-insensitive filesystems and protects a symlinked tracker's real folder.
- Repost check: the `## Description` section is the last section of a ranked file and runs to end of file, so headings inside the vacancy text no longer truncate it.
- Portals: `portals.job_portals` and `portals.employer_ats` accept portal names or hosts; name matching uses whole host labels (never the TLD), so "lever" no longer matches unrelated hosts.
- Docs: READMEs list 8 commands, 5 skills, 9 scripts and the SessionStart hook; planned CV tailoring and career-roadmap modes are marked as not yet published; AGENTS.md points to CLAUDE.md.

## 0.1.0 (2026-10-28)
- Repo skeleton and structure validator.
- Commands: rank, apply, outcome, followup, interview, upskill, funnel, jobsearch-setup.
- Skills: grounding-audit, cover-letter, humanizer, ats-screening.
- Stdlib scripts: data folder and config loader, tracker editor, grounding audit, funnel report, repost and robots checks, publish gate.
- Hard rules, tracker statuses, data contract, config template; QA example preset.
- Docs: root README, third-party notices, alternative-flow note.
- Final review fixes: funnel reply metrics ignore "no reply"-style notes and count applied rows only; the funnel report never overwrites and never writes into the tracker folder; YAML apostrophes inside words; `datadir.py show` prints absolute `paths.*`; `validate` rejects a non-mapping config; publish gate `--data-dir` (also matches the `~/` form) and per-file `publish_gate.allow`.