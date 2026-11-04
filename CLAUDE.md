# jobsearch

Claude Code and Codex job-search plugin repo: a neutral job-search engine (triage, honest cover letters, grounding audit, tracker).
Personal data (profile, tracker, applications, private config) lives in the user's data dir, never in this repo.

## Layout
- `plugins/jobsearch/` - the plugin.
  - `commands/` - slash commands (rank, apply, outcome, followup, interview, upskill, funnel, scan, jobsearch-setup, help).
  - `skills/` - cover-letter, grounding-audit, ats-screening, humanizer, linkedin-profile-optimizer, career-paths (SKILL.md + evals.json each).
  - `scripts/` - stdlib-only tools (datadir, runtime, onboarding, tracker_edit, grounding_audit, funnel_report, repost_check, robots_check, portal_scan, publish_gate).
  - `skills/ats-screening/scripts/` - PDF checks with optional extras: PyMuPDF for ats_technical_score.py, pdfplumber + pypdf for pdf_technical_check.py.
  - `hooks/` (Claude guard plus conservative Codex adapter), `reference/` (hard rules, statuses, data contract, config template).
- `evals/validate_repo.py` - structure checks; `evals/fixtures/` - synthetic persona and data dir.
- `tests/` - stdlib unittest.
- `docs/superpowers/` - spec and plans.

## Run
- Tests: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`
- Validator (exit 0 = no FAIL): `python3 evals/validate_repo.py`
- Publish gate (needs the private config; the validator skips it with a WARN without one):
  `JOBSEARCH_CONFIG=<private config> python3 plugins/jobsearch/scripts/publish_gate.py --repo .`

## Rules
- Hard rules of the engine: `plugins/jobsearch/reference/hard-rules.md`. They are not configurable. Never send or apply; facts only from the data dir; the tracker changes only through `tracker_edit.py`.
- No personal values in this repo: no real names, employers, contacts, salary figures, vacancy ids or machine paths in any file or commit. Every personal value is a config key; fixtures use the synthetic persona (Jordan Example, Example Corp). Exception: the copyright holder's name in `LICENSE` is intentional (the owner's choice); keep it, and keep its `publish_gate.allow` entry in the private config.
- Python 3.9+, stdlib only; the only exceptions are the optional PDF extras of the ats-screening scripts (PyMuPDF; pdfplumber + pypdf).
- Engine text says "the user", never a person's name. Files in English.
- Commit locally when asked; never push without the user's say-so, and run the publish gate before any push.
- A skill description says when NOT to use the skill; each new skill gets an evals.json with 3 synthetic prompts.

Codex packaging: `python3 tools/build_codex.py --out <new-folder>` creates a local marketplace without installing it. `docs/codex.md` documents runtime differences. Workflow instructions stay canonical in commands/ and skills/; never hand-maintain a duplicate Codex workflow.
