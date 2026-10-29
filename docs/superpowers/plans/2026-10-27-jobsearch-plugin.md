# jobsearch plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `jobsearch` Claude Code plugin (neutral job-search engine) in a private repo, reading all personal data from a user data dir, with a publish gate that proves the repo holds none of the owner's personal values.

**Architecture:** One marketplace repo with one plugin (`plugins/jobsearch/`). Markdown commands and skills drive Claude; stdlib Python scripts do the deterministic work (data-dir resolution, tracker edits, grounding audit, ATS score, repost check, funnel report, publish gate). Every personal value comes from `jobsearch.config.yaml` resolved via `JOBSEARCH_DATA_DIR` / `JOBSEARCH_CONFIG`.

**Tech Stack:** Python 3 stdlib only (`unittest` for tests); optional PyMuPDF for the ATS PDF check; Claude Code plugin format (`.claude-plugin/marketplace.json`, `plugin.json`, `commands/`, `skills/`, `hooks/hooks.json`).

**Spec:** `docs/superpowers/specs/2026-10-27-jobsearch-plugin-design.md` (approved 2026-10-27). Section numbers below (§) refer to it.

## Global Constraints

- Repo: `<plugin repo>` (the repo folder), public GitHub repo (Q1, changed 2026-10-28; owner config in a separate private repo). Plugin name `jobsearch`; marketplace name `jobsearch-marketplace`.
- Run the executing session with this repo as its working directory (the sandbox lets Bash write only to the working dir and temp). The source workspace (`$JOBSEARCH_DATA_DIR` of the owner, called SRC below) is READ-ONLY: never write, edit, create a marker or config file there.
- No personal value of the owner in any file or commit of this repo, including tests and docs. Fixtures use the synthetic persona only: `Jordan Example`, `jordan.example@example.com`, `+1 555 0100`, handle `@jordan_example`, employer `Example Corp`.
- Owner's private config: `<private config path, outside the repo>` (Q3). Never copied into this repo; tests never read it (only Task 13 and the gate do).
- Git: neutral committer identity for this repo (`git config user.name "jobsearch maintainers"`, `git config user.email "jobsearch@users.noreply.github.com"`). Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push without the owner's go-ahead; push only after Task 14 PASS.
- Python: stdlib only (except optional PyMuPDF in the ATS PDF path); run tests with `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`.
- Files in English. Engine text says "the user", never a name.
- Env vars: `JOBSEARCH_DATA_DIR`, `JOBSEARCH_CONFIG`. Marker file `.jobsearch-data`. Config file `jobsearch.config.yaml` (YAML subset) or `jobsearch.config.json`.
- Tracker statuses (unchanged): `ACTIVE, APPLIED, NO_RESPONSE, REJECTED, DECLINED, CLOSED, SKIPPED, NOT_APPLIED, DO_NOT_APPLY, UNKNOWN`.
- Defaults pinned by the spec: match weights 60/10/10/10/10; thresholds apply 80, decline 65; letters 150-320 words; follow-up default 10 days, window 3-7, max 2; repost window 90 days; small-sample mark n < 5; employer ATS list `greenhouse, lever, workable, ashby, recruitee, personio, teamtailor, smartrecruiters, breezy`.
- Hard rules §10 are copied into `reference/hard-rules.md` and are never read from config.
- Licences: keep the humanizer MIT notice (Siqi Chen); credit MadsLorentzen/ai-job-search (MIT) and career-ops (MIT) in `THIRD-PARTY-NOTICES.md`; the string "career-ops" appears only there and in `docs/`.
- Alternative flow (§6.7) is NOT built in this plan: only the `alt_flow` config keys (all `false`). Each A1-A3 gets its own design addendum and plan later.

## Review Focus

1. User tracker CSV with fewer columns than the owner's (no `notes_xlsx`, `notes_csv`) or with a UTF-8 BOM -> `find`/`check` must work, not KeyError. Test in Task 3.
2. `JOBSEARCH_DATA_DIR` set to a folder that does not exist -> clear error, nothing created. Test in Task 1.
3. Publish gate with no private config or empty `identity` -> exit 2 "SKIPPED", never exit 0 PASS. Test in Task 2.
4. Personal phone written with spaces, dashes or dots, or email in upper case -> still a gate hit. Test in Task 2.
5. Cyrillic or accented company names and titles in duplicate check and repost fingerprint -> matched like ASCII. Tests in Tasks 3 and 7.

---

### Task 0: Repo skeleton and adapted validator

**Files:**
- Create: `.claude-plugin/marketplace.json`, `plugins/jobsearch/.claude-plugin/plugin.json`, `plugins/jobsearch/CHANGELOG.md`, `.gitignore`, `LICENSE` (MIT, holder "jobsearch maintainers"), `CLAUDE.md` (stub, filled in Task 9), `evals/validate_repo.py`, `tests/test_validate_repo.py`

**Interfaces:**
- Produces: `python3 evals/validate_repo.py` -> prints `PASS|FAIL <check>` lines, exit 1 on any FAIL. Check function `check(name: str, ok: bool, detail: str = "")`. Later tasks add checks by appending blocks.

- [x] **Step 1 (owner, Terminal):** `cd <plugin repo> && git init && git config user.name "jobsearch maintainers" && git config user.email "jobsearch@users.noreply.github.com"`. Expected: "Initialized empty Git repository".
- [x] **Step 2: Write failing test** `tests/test_validate_repo.py::test_validator_passes_on_repo` - runs the validator as subprocess, asserts exit code 0 and no line starts with `FAIL`.
- [x] **Step 3:** run it; expected FAIL (validator missing).
- [x] **Step 4: Create** `evals/validate_repo.py` by adapting a reference validator from another repo: keep checks 1 (CLAUDE.md < 100 lines), 2 (JSON valid), 3/3b/3c (frontmatter, name = folder, description < 1100 chars and says when NOT to use, documented keys, `evals/evals.json` or `STATUS: SKELETON`) pointed at `plugins/jobsearch/skills/*/`, 6 (README relative paths exist), 7 (secret-looking strings). Drop 3e, 4, 5, 8-11. Add: 12 every `scripts/<name>.py` mentioned in `plugins/jobsearch/commands/*.md` and skills exists. `.gitignore`: `__pycache__/`, `*.pyc`, `.DS_Store`, `tracker/`, `applications/`, `profile/`, `*.config.yaml` except `plugins/jobsearch/reference/config.template.yaml` and `evals/fixtures/**`.
- [x] **Step 5: Create** marketplace.json (`name: jobsearch-marketplace`, plugin `jobsearch`, `source: ./plugins/jobsearch`) and plugin.json (`name: jobsearch`, `version: 0.1.0`, description "Job-search engine: triage, honest letters, grounding audit, tracker; personal data stays in your data dir").
- [x] **Step 6:** run tests; expected PASS.
- [x] **Step 7: Commit** `git add -A && git commit -m "chore: repo skeleton and structure validator"`.

### Task 1: Data-dir resolver and config loader

**Files:** Create `plugins/jobsearch/scripts/datadir.py`, `plugins/jobsearch/reference/config.template.yaml`, `plugins/jobsearch/reference/data-contract.md`, `evals/fixtures/sample-datadir/` (`jobsearch.config.yaml`, `profile/facts.md`, `profile/master_cv/MASTER_CONTENT.md`, `tracker/vacancies.csv` with 40 synthetic rows covering every status, 3 portals, 2 Cyrillic company names, `tracker/CHANGELOG.csv`, `vacancies/ranked/` 3 files, `interview/story_bank.md` 2 stories), `tests/test_datadir.py`

**Interfaces:**
- Produces:
  - `class DataDirError(Exception)`
  - `resolve_data_dir(cwd: str, env: Mapping[str, str]) -> str` (precedence §3.3; raises `DataDirError` with setup text; never creates folders)
  - `config_path(data_dir: str, env: Mapping[str, str]) -> str` (`JOBSEARCH_CONFIG` wins; else `.yaml` then `.json` in data dir)
  - `parse_yaml_subset(text: str) -> Any` (maps, block lists, flow lists `[a, b]`, flow maps `{k: v}`, quoted/unquoted scalars, ints, `true/false`, comments)
  - `load_config(data_dir: str, env: Mapping[str, str]) -> dict` (deep-merge onto `DEFAULTS`; missing file -> `DEFAULTS` + `cfg["_warnings"]` list)
  - `data_path(cfg: dict, data_dir: str, key: str) -> str` (joins `cfg["paths"][key]`)
  - `DEFAULTS: dict` = schema of §3.4 with the pinned defaults (Global Constraints) and `alt_flow.*.enabled = False`
  - CLI: `datadir.py show` (data dir, config path, warnings) and `datadir.py validate` (unknown keys -> exit 1)

- [x] **Step 1: Write failing tests** in `tests/test_datadir.py`:
  - `test_env_wins`: env `JOBSEARCH_DATA_DIR=<fixture>` -> returns fixture path.
  - `test_marker_file`: tmp project with `.jobsearch-data` containing fixture path -> fixture path.
  - `test_config_in_root`: tmp project containing `jobsearch.config.yaml` -> project path.
  - `test_nothing_raises`: empty tmp dir, empty env -> `DataDirError`, message contains `JOBSEARCH_DATA_DIR`.
  - `test_missing_env_dir_raises_and_creates_nothing` (Review Focus 2): env points to `<tmp>/nope` -> `DataDirError`; `os.path.exists("<tmp>/nope")` is False.
  - `test_config_env_override`: `JOBSEARCH_CONFIG=<tmp>/other.yaml` -> `config_path` returns it.
  - `test_yaml_subset`: parses `a: {b: 1, c: [x, "y z"]}\nlist:\n  - {k: v}\n  - plain\nflag: false # c` to `{"a": {"b": 1, "c": ["x", "y z"]}, "list": [{"k": "v"}, "plain"], "flag": False}`.
  - `test_defaults_merge`: fixture config overrides `thresholds.apply` to 75 -> `cfg["thresholds"] == {"apply": 75, "decline": 65}` and `cfg["match_weights"]["must_have"] == 60`.
  - `test_alt_flow_off_by_default`: `DEFAULTS["alt_flow"]["scanner"]["enabled"] is False` (same for `apply_assistant`, `reply_watch`).
  - `test_template_matches_defaults`: keys of parsed `config.template.yaml` == keys of `DEFAULTS` (recursive).
- [x] **Step 2:** run; expected FAIL (module missing).
- [x] **Step 3: Implement** `datadir.py` (indentation-based recursive parser; no anchors, no multi-line strings) and the template (every §3.4 key, empty personal values, comments).
- [x] **Step 4:** run; expected PASS. Add validator check 13: `datadir.py validate` on `config.template.yaml` exits 0.
- [x] **Step 5: Commit** `feat: data-dir resolver, config loader, synthetic fixture`.

### Task 2: Publish gate

**Files:** Create `plugins/jobsearch/scripts/publish_gate.py`, `tests/test_publish_gate.py`; Modify `evals/validate_repo.py` (check 14)

**Interfaces:**
- Consumes: `load_config` (Task 1).
- Produces:
  - `build_patterns(identity: dict, extra_terms: list[str], data_dir: str | None) -> list[tuple[str, re.Pattern]]` (label, regex). Names/terms: `\b...\b`, case-insensitive. Emails: full address and local part. Phones: digits-only form, and a regex allowing `[\s.\-()]*` between every digit, also for the last 7+ digits.
  - `scan_tree(repo: str, patterns) -> list[Hit]`, `scan_history(repo: str, patterns) -> list[Hit]` (`git log -p --all` and `git log --all --format=%an%n%ae%n%cn%n%ce`), `Hit = namedtuple("Hit", "where kind masked")`; `masked` keeps first and last char only.
  - CLI `publish_gate.py [--repo .] [--config PATH]`: exit 0 = zero hits ("PUBLISH GATE: PASS"), 1 = hits, 2 = no config or empty identity ("PUBLISH GATE: SKIPPED - no private identity configured").
- Also FAIL kinds: data dir path string present; non-empty `tracker/`, `applications/`, `profile/` at repo root.

- [x] **Step 1: Write failing tests** (each builds a tmp git repo with `git init` + neutral identity, synthetic persona config):
  - `test_clean_repo_passes` -> exit 0.
  - `test_name_in_file_fails` -> file containing "Jordan Example" -> exit 1, hit `where` ends with `:1`.
  - `test_phone_variants_fail` (Review Focus 4): files with `+1 555 0100`, `1-555-0100`, `15550100`, `555.0100`... -> each is a hit (identity phones `["+1 555 0100"]`).
  - `test_email_case_insensitive`: `JORDAN.EXAMPLE@EXAMPLE.COM` -> hit.
  - `test_history_only_hit`: commit a file with the name, then delete it in a second commit -> tree clean, history hit -> exit 1.
  - `test_author_metadata_hit`: commit with `user.name "Jordan Example"` -> exit 1.
  - `test_no_identity_skips` (Review Focus 3): empty `identity` -> exit 2 and stdout contains `SKIPPED`.
  - `test_gate_script_has_no_fixture_values`: the text of `publish_gate.py` contains none of the persona values.
- [x] **Step 2:** run; expected FAIL.
- [x] **Step 3: Implement** `publish_gate.py`.
- [x] **Step 4:** run; expected PASS. Add validator check 14: run the gate with `JOBSEARCH_CONFIG` if set; exit 2 -> print `WARN  publish gate skipped (no private config)` without failing; exit 1 -> FAIL.
- [x] **Step 5: Commit** `feat: publish gate over tree and git history`.

### Task 3: Tracker editor port

**Files:** Create `plugins/jobsearch/scripts/tracker_edit.py`, `plugins/jobsearch/reference/statuses.md`, `tests/test_tracker_edit.py`

**Interfaces:**
- Consumes: `resolve_data_dir`, `load_config`, `data_path` (Task 1).
- Produces: same CLI as SRC `tools/tracker_edit.py` (`find`, `add`, `set`, `check`, `--file`) plus `--config`. Default file = `data_path(cfg, dd, "tracker")`. Functions: `ck(s: str) -> str` (keeps Latin, Cyrillic incl. `іїєґё`, digits), `next_id(rows: list[dict], prefix: str) -> str` (`prefix + 3-digit`), `counts(rows) -> dict`. Row fields read with `r.get(col, "")`. Status set by the user writes `cfg["tracker"]["decided_by_label"]`. Messages say "ask the user".

- [x] **Step 1: Write failing tests** on a temp copy of the fixture tracker:
  - `test_find_exact_url` -> output contains `ALREADY APPLIED/SEEN`.
  - `test_find_cyrillic_company` (Review Focus 5): searching the Cyrillic fixture company with different case/spacing -> `SAME COMPANY`.
  - `test_minimal_columns_and_bom` (Review Focus 1): CSV with BOM and only `id,company,position,url,status,applied_date` -> `find` and `check` exit 0.
  - `test_add_uses_prefix`: config `id_prefix: "JOB-"` -> new id `JOB-041`.
  - `test_set_invalid_status_rejected` -> non-zero exit, file unchanged (byte compare).
  - `test_set_writes_backup_changelog_and_counts` -> `history/` has one new file, CHANGELOG has a new row, stdout contains `status value_counts before`, `after` and `rows whose status changed: [(`.
  - `test_never_deletes_rows`: row count after `add` = before + 1; after `set` = before.
- [x] **Step 2:** run; expected FAIL.
- [x] **Step 3: Implement** by porting SRC `tools/tracker_edit.py`; replace the owner name, id prefix and decided-by label per spec §4 row 8. `statuses.md`: SRC `tracker/statuses.md` with "the user".
- [x] **Step 4:** run; expected PASS.
- [x] **Step 5: Commit** `feat: tracker editor reads data dir and config`.

### Task 4: Grounding audit port

**Files:** Create `plugins/jobsearch/scripts/grounding_audit.py`, `tests/test_grounding_audit.py`, fixture letters `evals/fixtures/letters/{clean,never_claim,placeholder,long_dash,too_short,tool_no_disclaimer}.md`

**Interfaces:**
- Consumes: Task 1.
- Produces: `audit(text: str, kind: str, cfg: dict, master_text: str, no_length: bool = False, allowed_extra: set[str] = frozenset()) -> tuple[list[str], list[str]]` (fails, warns); CLI identical to SRC (`FILE --kind letter|cv [--allowed-extra] [--no-length]`) plus `--config`. Rule sources: `honesty.never_claim`, `honesty.allowed_exceptions`, `honesty.restricted_tools` (`pattern`, `disclaimer_pattern`, `cv_forbidden`), `honesty.tool_dictionary`, `honesty.allowed_numbers`, `honesty.allowed_year_claims`, `letters.words_min/words_max/no_long_dash/forbidden_openers/forbidden_buzzwords/signature_lines`. Generic checks kept in code: placeholders `[A-Z_ ...]`, years absent from master, numeric claims with units.

- [x] **Step 1: Write failing tests** (fixture config carries persona honesty rules):
  - `test_clean_letter_passes` -> fails == [].
  - `test_never_claim_fail` -> one fail containing the configured `why`.
  - `test_allowed_exception_sentence_skipped` -> configured exception sentence gives no fail.
  - `test_placeholder_fail`, `test_long_dash_fail_letter_only` (cv kind -> no fail), `test_length_bounds` (149 words fail, 150 pass, `no_length=True` skips).
  - `test_restricted_tool_needs_disclaimer` -> fail without, warn with disclaimer; `kind="cv"` -> fail.
  - `test_year_claim_allowed_list` -> `10 years` with `allowed_year_claims [{n: 10}]` -> warn not fail; `12 years` -> fail.
  - `test_signature_lines_excluded_from_word_count`.
  - `test_empty_honesty_config_still_runs` -> no exception, warns contain `no honesty limits configured`.
- [x] **Step 2:** run; expected FAIL.
- [x] **Step 3: Implement** by porting SRC `tools/grounding_audit.py` per spec §4 rows 1-6.
- [x] **Step 4:** run; expected PASS.
- [x] **Step 5: Commit** `feat: config-driven grounding audit`.

### Task 5: ATS screening skill with one score script

**Files:** Create `plugins/jobsearch/skills/ats-screening/SKILL.md`, `.../scripts/ats_technical_score.py`, `.../scripts/pdf_technical_check.py`, `.../evals/evals.json`, `tests/test_ats_score.py`

**Interfaces:** Produces CLI and `--selftest` exactly as SRC `tools/ats_technical_score.py`; output line `ATS Technical Score: XX/100` unchanged.

- [x] **Step 1: Write failing test** `test_selftest_passes` (runs `--selftest`, exit 0) and `test_synthetic_fixtures` (assert the selftest phone fixture is `+10000000000` and the header fixture contains `Example Corp`; real-value absence is proven by the gate in Task 14).
- [x] **Step 2:** run; expected FAIL.
- [x] **Step 3:** copy SRC `.claude/skills/<owner-prefix>-ats-screening/` content (one script copy only); replace selftest phone and employer header fixtures with `+10000000000` / `+1 000 000 00 00` and `Senior Engineer | Example Corp 04/2014 - Present`; SKILL.md: name `ats-screening`, drop owner example (§4 row 12), default chat language = `language.chat` from config, description ends with "Not for writing or rewriting a CV or letter (use cover-letter)". `evals.json`: 3 prompts on synthetic CV text.
- [x] **Step 4:** run tests + validator; expected PASS.
- [x] **Step 5: Commit** `feat: ats-screening skill, single score script, synthetic selftest`.

### Task 6: robots check and session-start hook

**Files:** Create `plugins/jobsearch/scripts/robots_check.py` (copy of SRC, unchanged), `plugins/jobsearch/hooks/hooks.json`, `plugins/jobsearch/hooks/session_start.py`, `tests/test_session_start.py`

**Interfaces:**
- Produces: `context(project_root: str, env: Mapping[str, str]) -> dict | None` - returns the Claude Code SessionStart JSON (`systemMessage`, `hookSpecificOutput.additionalContext` with `paths.start_file` text + open `- [ ]` items of `paths.todo_file`, instruction to answer in `language.chat`) or None. hooks.json: SessionStart, matcher `startup|resume|clear|compact`, command `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/session_start.py"`.

- [x] **Step 1: Write failing tests:**
  - `test_silent_outside_data_dir`: project root != resolved data dir and no marker -> None (prints nothing).
  - `test_silent_when_project_has_own_hook`: project root = data dir but `.claude/settings.json` contains a SessionStart hook -> None.
  - `test_context_in_data_dir`: fixture as project root -> additionalContext contains start-file text and the count of open TODO items.
  - `test_missing_files_reported`: no start file -> text contains `(missing: START_HERE.md)`.
- [x] **Step 2:** run; expected FAIL.
- [x] **Step 3: Implement.** `main()` prints `json.dumps(ctx)` only when not None; exit 0 always.
- [x] **Step 4:** run; expected PASS.
- [x] **Step 5: Commit** `feat: robots check and session-start hook (silent outside the data dir)`.

### Task 7: Repost check and `/rank` command

**Files:** Create `plugins/jobsearch/scripts/repost_check.py`, `plugins/jobsearch/commands/rank.md`, `tests/test_repost_check.py`

**Interfaces:**
- Consumes: `ck` (Task 3), Task 1.
- Produces: `fingerprint(text: str, n: int = 40) -> str` (lowercase, Unicode word tokens, stop-words removed, first `n` tokens joined); `find_reposts(company: str, title: str, body: str, rows: list[dict], ranked_dir: str, today: date, window_days: int = 90) -> list[dict]` (`{"source", "id_or_file", "date", "reason"}`); CLI `repost_check.py --company --title [--body-file] [--today]` printing `possible repost` lines or `no repost found`.

- [x] **Step 1: Write failing tests:**
  - `test_same_company_title_within_90_days` -> one hit; at day 91 -> none.
  - `test_fingerprint_unicode` (Review Focus 5): Cyrillic body and same body with different punctuation/case -> equal fingerprints.
  - `test_ranked_file_match` -> hit with `source == "ranked"`.
  - `test_no_date_rows_reported_not_dropped` -> hit with `date == "unknown"`.
- [x] **Step 2:** run; expected FAIL.
- [x] **Step 3: Implement** `repost_check.py`.
- [x] **Step 4:** run; expected PASS.
- [x] **Step 5: Write** `commands/rank.md` by porting SRC `.claude/commands/rank.md`: read hard rules + config; host classes from `portals`; blockers from typed `blockers` list (hard overrides %, soft = flag and ask, unpublished = Unknown, gross never converted); requirement matrix labels from `paths.master_cv` / `paths.facts`; match % with `match_weights` and `targets.domains_priority`; thresholds from config; new "Legitimacy" step after host check (§6.2: still open, age, `repost_check.py`, ghost signals as observations, never a verdict); output block unchanged with an added `Legitimacy:` line. Run validator; expected PASS (check 12 finds `repost_check.py`, `tracker_edit.py`, `robots_check.py`).
- [x] **Step 6: Commit** `feat: repost check and config-driven /rank with legitimacy block`.

### Task 8: Funnel report and `/funnel`

**Files:** Create `plugins/jobsearch/scripts/funnel_report.py`, `plugins/jobsearch/commands/funnel.md`, `tests/test_funnel_report.py`

**Interfaces:**
- Produces: `host_class(url: str, cfg: dict) -> str` (`"job portal" | "employer ATS" | "other"`); `role_type(title: str, cfg: dict) -> str` (first matching entry of `targets.roles`, `roles_selective`, `roles_not_primary`, else `"other"`); `build_report(rows: list[dict], changelog: list[dict], cfg: dict, today: date) -> str`; CLI `funnel_report.py [--config] [--out PATH]` writes `paths.reports/funnel_<YYYY-MM-DD>.md` and prints it. Read-only on tracker.

- [x] **Step 1: Write failing tests** on the fixture tracker:
  - `test_funnel_counts`: report contains the funnel line with counts equal to fixture truth (precompute in test from CSV).
  - `test_reply_rate_by_host_class` -> three rows, rates match fixture.
  - `test_small_sample_marked` -> a group with n=3 shows `too few to conclude`.
  - `test_tracker_unchanged` -> tracker bytes identical after run.
  - `test_empty_targets_role_other` -> all titles `other` with empty `targets`.
- [x] **Step 2:** run; expected FAIL.
- [x] **Step 3: Implement.** "Any reply" = status in `{REJECTED, ACTIVE}` or CHANGELOG note mentioning a reply; median days from `applied_date` to first CHANGELOG status change.
- [x] **Step 4:** run; expected PASS.
- [x] **Step 5: Write** `commands/funnel.md` (runs the script, explains the small-sample rule, suggests at most 3 actions, never changes the tracker).
- [x] **Step 6: Commit** `feat: funnel and patterns report`.

### Task 9: Core commands, skills, reference and CLAUDE.md

**Files:** Create `plugins/jobsearch/commands/{apply,outcome,followup,upskill}.md`, `plugins/jobsearch/skills/grounding-audit/` (SKILL.md + evals), `plugins/jobsearch/skills/cover-letter/` (SKILL.md + evals), `plugins/jobsearch/skills/humanizer/` (SRC copy incl. LICENSE, README), `plugins/jobsearch/reference/hard-rules.md`, `CLAUDE.md`, `plugins/jobsearch/README.md`

**Interfaces:** Consumes script CLIs of Tasks 1-5. Commands refer to data via config keys (`paths.*`, `honesty.*`, `letters.*`, `followup.*`), never to fixed paths.

- [x] **Step 1: Write** `reference/hard-rules.md` = spec §10 verbatim; `CLAUDE.md` (< 100 lines): what the repo is, layout, how to run tests/validator/gate, hard rules pointer, "no personal values" rule.
- [x] **Step 2: Port** `apply.md`, `outcome.md`, `followup.md`, `upskill.md` from SRC per spec §3.1 and §4 rows 13-17: owner name -> "the user"; risk lines from `honesty.known_risk_lines`; letter KB from `paths.letter_kb`; follow-up numbers from `followup.*`; `/upskill` gap table from `paths.facts`, library from `paths.study_library`, target from `targets`; `/outcome` offers `/interview debrief` when the event is an interview.
- [x] **Step 3: Port skills:** `grounding-audit` (generic procedure §4 row 11; description ends "Not for writing letters (use cover-letter) and not for ATS scoring (use ats-screening)"); `cover-letter` translated to English (§4 row 10; base letters from `letters.base_letters`; prohibitions from `honesty`; description ends "Not for tracker updates (use outcome)"); `humanizer` unchanged except a "Not for ..." clause in the description if the validator needs it. Each gets `evals/evals.json` with 3 synthetic prompts.
- [x] **Step 4: Verify:** validator exit 0; `grep -rn "the owner" plugins/jobsearch/` returns nothing; publish gate with the owner config (if available in the session) exits 0.
- [x] **Step 5: Commit** `feat: core commands and skills ported to config`.

### Task 10: `/interview` with story bank, debrief and red flags

**Files:** Create `plugins/jobsearch/commands/interview.md`, `plugins/jobsearch/reference/story-bank-format.md`, `evals/fixtures/sample-datadir/interview/story_bank.md` (already from Task 1; extend to match the format)

- [x] **Step 1: Write** `story-bank-format.md` (§6.3 fields: id, title, S, T, A, R, Reflection, source label, tags, last used; approval rule; "no number, observed effect").
- [x] **Step 2: Port** SRC `interview.md` per §4 row 15 (prior feedback from tracker notes; STAR from story bank by tag; questions without a story flagged as gaps; salary never in engine; study library from config) and add modes: `prep` (default), `debrief` (§6.4 output file `applications/<dir>/debrief_<stage>_<date>.md`, proposes `/outcome` change and story updates, user confirms), `redflags` (§6.4 checklist from `blockers` + `interview.redflag_checks`, SEEN / NOT SEEN / ASK).
- [x] **Step 3: Verify:** validator exit 0; manual dry run in a session with `JOBSEARCH_DATA_DIR=<fixture>`: `/jobsearch:interview debrief Example Corp` asks questions and writes nothing before answers.
- [x] **Step 4: Commit** `feat: interview prep, debrief and red-flag modes with story bank`.

### Task 11: QA preset and setup command

**Files:** Create `plugins/jobsearch/presets/qa/{preset.yaml,facts.example.md,README.md}`, `plugins/jobsearch/commands/jobsearch-setup.md`, `docs/presets.md`, `tests/test_preset.py`

- [x] **Step 1: Write failing test** `test_qa_preset_merges`: `load_config` on a tmp data dir whose config is `preset.yaml` -> `honesty.tool_dictionary` non-empty, keyword blockers present, `datadir.py validate` exit 0; `test_preset_has_no_personal_values` (none of the persona values, and none of SRC-specific employer/domain wording - assert against a short list kept in the test: `Example Corp` must not appear either, preset is generic).
- [x] **Step 2:** run; expected FAIL.
- [x] **Step 3: Create** preset per spec §5 (QA tool dictionary + automation regex + disclaimer words from SRC grounding script lines 26-31; example keyword blockers; example domains; neutral letter archetype keys; facts skeleton with gap table). `jobsearch-setup.md` per §6.6 (new or empty folder only; prints the `export JOBSEARCH_DATA_DIR=...` line; never edits shell profiles).
- [x] **Step 4:** run; expected PASS.
- [x] **Step 5: Commit** `feat: QA example preset and setup command`.

### Task 12: Docs and notices

**Files:** Create `README.md`, `THIRD-PARTY-NOTICES.md`, `docs/data-contract.md` link from `reference/`, `docs/alternative-flow.md`

- [x] **Step 1: Write** README (install from private marketplace, setup, commands list, data dir, privacy model, gate). `THIRD-PARTY-NOTICES.md`: humanizer MIT (Siqi Chen, full licence text), MadsLorentzen/ai-job-search (MIT, ideas used: grounding audit, interview, upskill, robots check), career-ops (MIT, ideas used: data-dir precedence, funnel/patterns, posting legitimacy, STAR+R bank, debrief, red flags; name not used per its trademark policy). `docs/alternative-flow.md`: §6.7 verbatim + "each phase needs its own approved addendum".
- [x] **Step 2: Verify:** validator exit 0 (README relative paths exist).
- [x] **Step 3: Commit** `docs: README, third-party notices, alternative flow`.

### Task 13: Owner config and parity trial on a copy

**Files:** none in this repo. Creates the owner's private config at `<private config path, outside the repo>` and a data copy in `$TMPDIR`.

- [x] **Step 1: Copy data:** `cp -R "$SRC" "$TMPDIR/jobsearch-datacopy"` (SRC read only). Expected: copy exists; `git -C "$SRC" status --short` unchanged before/after.
- [x] **Step 2: Write owner config** from SRC `CLAUDE.md` s1-s7, `profile/facts.md`, SRC grounding script lists, with `paths.*` mapped to SRC's existing layout (master CV artifact folder, canonical letter KB, tracker). Show it to the owner; owner confirms each `identity` and `extra_private_terms` entry (the gate's quality depends on it).
- [x] **Step 3: Parity, tracker:** `JOBSEARCH_DATA_DIR=$TMPDIR/jobsearch-datacopy JOBSEARCH_CONFIG=<owner config> python3 plugins/jobsearch/scripts/tracker_edit.py check` == output of SRC `tools/tracker_edit.py --file $TMPDIR/jobsearch-datacopy/tracker/vacancies.csv check`.
- [x] **Step 4: Parity, grounding:** for 3 sent letters in the copy's `applications/`, new `grounding_audit.py` FAIL/WARN sets == SRC script's sets (sorted lines). Any difference is listed and explained to the owner.
- [x] **Step 5: Parity, rank:** in a session with the env above, run `/jobsearch:rank` on 5 vacancies that already have files in `vacancies/ranked/`; duplicate verdict and blockers equal the saved ones. Record results in `docs/parity-2026-MM-DD.md` without personal values (VAC ids replaced by row numbers 1-5).
- [x] **Step 6: Verify SRC untouched:** `git -C "$SRC" status --short` identical to Step 1.
- [x] **Step 7: Commit** `docs: parity trial results`.

### Task 14: Gate run and first push (owner go-ahead)

- [x] **Step 1:** `JOBSEARCH_CONFIG=<owner config> python3 plugins/jobsearch/scripts/publish_gate.py --repo .` Expected: `PUBLISH GATE: PASS`, exit 0. Any hit -> fix; if the hit is in history, start fresh history (`git checkout --orphan` + recommit) after owner approval.
- [x] **Step 2:** `python3 evals/validate_repo.py` and full unittest suite: exit 0.
- [x] **Step 3 (owner):** install the pre-push hook: `printf '#!/bin/sh\nJOBSEARCH_CONFIG=%s python3 plugins/jobsearch/scripts/publish_gate.py --repo .\n' "<owner config>" > .git/hooks/pre-push && chmod +x .git/hooks/pre-push`.
- [x] **Step 4 (owner):** create the PUBLIC GitHub repo and push (`gh repo create jobsearch-plugin --public --source . --push`; changed from private 2026-10-28). Claude does not push.
- [ ] **Step 5 (owner, optional):** `claude plugin marketplace add <local path>` and `claude plugin install jobsearch@jobsearch-marketplace`; confirm `/jobsearch:rank` appears.
