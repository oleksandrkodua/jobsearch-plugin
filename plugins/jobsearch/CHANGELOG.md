# Changelog

## 0.1.0 (unreleased)
- Repo skeleton and structure validator.
- Commands: rank, apply, outcome, followup, interview, upskill, funnel, jobsearch-setup.
- Skills: grounding-audit, cover-letter, humanizer, ats-screening.
- Stdlib scripts: data folder and config loader, tracker editor, grounding audit, funnel report, repost and robots checks, publish gate.
- Hard rules, tracker statuses, data contract, config template; QA example preset.
- Docs: root README, third-party notices, alternative-flow note.
- Final review fixes: funnel reply metrics ignore "no reply"-style notes and count applied rows only; the funnel report never overwrites and never writes into the tracker folder; YAML apostrophes inside words; `datadir.py show` prints absolute `paths.*`; `validate` rejects a non-mapping config; publish gate `--data-dir` (also matches the `~/` form) and per-file `publish_gate.allow`.
