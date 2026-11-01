# Changelog

## 0.1.0 (unreleased)
- Repo skeleton and structure validator.
- Commands: rank, apply, outcome, followup, interview, upskill, funnel, jobsearch-setup.
- Skills: grounding-audit, cover-letter, humanizer, ats-screening, linkedin-profile-optimizer.
- Stdlib scripts: data folder and config loader, tracker editor, grounding audit, funnel report, repost and robots checks, publish gate.
- Hard rules, tracker statuses, data contract, config template; QA example preset.
- Docs: root README, third-party notices, alternative-flow note.
- Final review fixes: funnel reply metrics ignore "no reply"-style notes and count applied rows only; the funnel report never overwrites and never writes into the tracker folder; YAML apostrophes inside words; `datadir.py show` prints absolute `paths.*`; `validate` rejects a non-mapping config; publish gate `--data-dir` (also matches the `~/` form) and per-file `publish_gate.allow`.

### 2026-11-01
- Added the LinkedIn profile optimizer skill and three synthetic evaluation prompts: grounded profile review, documented search behavior, no ranking guarantees or automatic profile edits.
- Updated cover-letter and humanizer guidance: concise vacancy-specific wording, no invented personal reactions, factual review after rewriting, and no detector guarantees.
- Updated both READMEs to list all 8 commands, 5 skills, 9 scripts and the SessionStart hook; separated included LinkedIn support from planned CV tailoring and career-roadmap modes.
