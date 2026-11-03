# Changelog

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