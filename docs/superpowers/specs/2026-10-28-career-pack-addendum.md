# Addendum: career pack (`/upskill roadmap`, `linkedin-profile`, `career-paths`)

Status: APPROVED by the owner 2026-10-28. Plan and code start after the main plan (Tasks 0-14) is finished.
Parent spec: `2026-10-27-jobsearch-plugin-design.md`; sibling: `2026-10-28-cv-tailor-addendum.md`. Drafted before the parity-trial commit at the owner's request; implementation starts only after the main plan (Tasks 0-14) is finished.

Common rules for all three parts:
- Hard rules (spec section 10) apply unchanged.
- Every output is saved to the data dir (`paths.reports`) and nothing is published.
- Each new skill gets `evals/evals.json` with 3 synthetic prompts (persona Jordan Example) and a description that says when NOT to use it.

## 1. `/upskill roadmap` - 12-month career map

**Placement:** a third mode of the existing `commands/upskill.md`, next to aggregate and targeted (`/upskill roadmap [direction]`). It is not a new command, because it needs the same inputs and the same Steps 2-5 (load data, gap diff, synthesis, heat map). Duplicating those in a new file would drift.

**Inputs:**
- the gap table and the "Not skill gaps" list in `paths.facts`;
- the tracker and `paths.ranked`, read the same way as in aggregate mode;
- the latest `upskill_<date>.md` in `paths.reports`, if present;
- `targets.*`;
- `paths.study_library`;
- optionally a direction chosen in `career-paths` (section 3).

**No new config keys.** The user's time budget (hours per week) and start month are asked in chat. They are written into the report header, and the next run reads them back from the previous roadmap. That alone is not a reason to add a key.

**Flow:**
1. Run Steps 2-5 of aggregate mode, or reuse the latest report if it is less than 30 days old.
2. Apply the existing decision gate: a direction in `targets.roles_not_primary` gets a roadmap only after the user picks path (c).
3. Build the map.

**Output:** `<paths.reports>/roadmap_<YYYY-MM-DD>.md`, with these sections:
1. **Header:** direction, time budget, start month, the heat map it is built on (file name).
2. **Monthly goals:** a 12-row table: `Month | Goal | Gap id(s) | Done when (checkable artifact) | Hours | Resource (local file or WebSearch link + date)`. Critical gaps go in months 1-3, and interview-performance gaps come first (quick wins). The total hours must fit the time budget; if they don't, say so and drop Low items.
3. **Certifications:** only certifications found by WebSearch in this run, each with its official link and the date checked. Cost, format and validity are marked "unverified" unless that official page states them. Each one is tied to a gap id. A certification with no gap behind it is listed under "not recommended: no gap it closes".
4. **Networking strategy:**
   - community and event *types*, with concrete names and links only from WebSearch (date checked);
   - a monthly cadence (for example, two posts or comments and one event);
   - message *drafts* only, never sent or posted (hard rule 1);
   - no private individuals named unless the user named them.
5. **Quarterly checkpoints:** re-run `/upskill` and `/funnel`, compare against this roadmap, and say what to drop.
6. **Unverified:** everything that could not be confirmed, with where it was looked for.

**Grounding:** the existing `/upskill` rules hold.
- Studying is not a claim, and neither is planning a certification. A skill or certificate becomes claimable only after the user states the evidence and adds it to the facts file.
- No invented gap history.
- No invented resources.

**Spec change:** a row in 3.1 (`commands/upskill.md` gains a `roadmap` mode). No non-goal changes.

## 2. Skill `linkedin-profile`

**Placement:** a new skill, `skills/linkedin-profile/`. It is a separate artifact with its own triggers ("rewrite my LinkedIn", "headline", "About section") and it fits no existing command flow.

**Inputs:**
- **The user's LinkedIn PDF export.** The path is given in chat each run; there is no config key, because exports go stale and are re-downloaded. The file is user data but untrusted text: instructions inside it are ignored and its links are not opened (hard rule 2 by analogy). It is read with the Read tool, so no new dependency is needed.
- `paths.master_cv` and `paths.facts`, the only sources of truth.
- **Keyword pool:** `targets.roles` plus the required and preferred keywords that recur across `paths.ranked` matrices (2+ files). That makes these target-role keywords, not one JD's.
- `honesty.*`.

**Output:** `<paths.reports>/linkedin_<YYYY-MM-DD>.md`:
1. **Conflicts first:** any date, title, employer or skill on which the export disagrees with the master or facts. These are listed and asked (hard rule 4), never "fixed" in either direction.
2. **Headline:** 2-3 variants, each 220 characters or fewer, results-first, with the keywords used named.
3. **About:** one version, 2,600 characters or fewer, short paragraphs, results-first, with no claim missing from the sources.
4. **Experience,** per role: `Original (export) -> Improved -> Keywords -> Source label | NOT IN SOURCES`. Roles only the export has are flagged as a conflict and not rewritten.
5. **Skills:** an ordered top list drawn only from the master skills list. Keywords from the pool that have no evidence are listed as "do not add".
6. **Audit result** and the list of NOT IN SOURCES items.

**Grounding:**
- Every statement traces to a master label or facts row, otherwise it is NOT IN SOURCES and is not usable.
- Numbers only from `honesty.allowed_numbers`. "Never invents metrics" is enforced by the audit.
- **Audit kind:** `--kind cv`, on `linkedin_draft.txt`, which holds only the proposed Headline, About, Experience and Skills text. Reasons:
  - a profile is public, so the CV rules fit: restricted tools forbidden, no letter length check, no letter-only dash rule;
  - a new `--kind profile` would carry no different rule today (YAGNI).
- The semantic part runs through the `grounding-audit` skill. A draft with an open FAIL is not handed over.
- `honesty.known_risk_lines` are never repeated.

**Hard-rule interplay:**
- Never logs in to, browses, edits or posts on LinkedIn. The user copies the text (rule 1, read as "never publish").
- No scraping of profiles (rule 7).
- `identity.*` values are not echoed into the report beyond what the export itself contains.

**Description must say when NOT to use it:**
- tailoring a CV to one vacancy (`/apply tune`);
- cover letters (`cover-letter`);
- ATS scoring (`ats-screening`);
- generic LinkedIn advice outside a configured data dir (the user's global skill).

**Overlap with the user's global skills:**
- `linkedin-profile-optimizer` gives generic searchability and visibility advice. It reads no data dir and does no grounding, so it may propose keywords and claims freely.
- `resume-bullet-writer` rewrites bullets "with metrics", which the plugin must not do unless the number is in `honesty.allowed_numbers`.
- **What the plugin version adds:**
  - config-driven sources (data dir, `honesty.*`, keyword pool from the user's own ranked vacancies);
  - conflict listing between the export and the master;
  - NOT IN SOURCES marking;
  - a mandatory `grounding_audit.py` pass before hand-over.
- The global skills stay as they are. The plugin description scopes itself to "inside a jobsearch data dir" to limit trigger collisions.

**Spec change:** add `linkedin-profile` to the skills list in section 8. Add to the non-goals: "No posting, profile editing or browsing on LinkedIn or any other site; profile text is a draft the user copies."

## 3. Skill `career-paths`

**Placement:** a new skill, `skills/career-paths/`. It is an advisory read over the whole profile, not a step of `/rank`, `/apply` or `/upskill`. Its output can feed `/upskill roadmap <direction>`.

**Inputs:**
- `paths.facts` (experience, gap table, "Not skill gaps") and `paths.master_cv` labels;
- `targets.*`;
- the latest `/funnel` report, or a run of `scripts/funnel_report.py`, for reply rate by role type. This is evidence from the user's own market, and the existing script is reused;
- `paths.ranked` (which role types matched best);
- the latest `upskill_*.md` report;
- salary sources: links or files the user gives, or pages found by WebSearch in this run.

**Output:** `<paths.reports>/career_paths_<YYYY-MM-DD>.md`:
1. **Directions:** 3-5 rows, ordered by fit, then salary potential:

   | Direction | Why the user is a strong candidate (labels / facts rows) | Gaps to close (gap ids) | Own-market signal (funnel / ranked) | Salary range: figure, region, seniority, gross/net, source link, date | Transition effort |
   |---|---|---|---|---|---|

2. **Per direction:** a short "why strong" paragraph (every claim labelled), the main risk, and the first step (for example, "`/upskill roadmap <direction>`").
3. **Not recommended:** directions considered and dropped, with the reason (blocked by `blockers`, no evidence, or salary not higher).
4. **Unverified:** each salary figure or market claim that could not be confirmed, with where it was looked for.
5. **Decision for the user:** which direction to pursue. The skill never edits `targets` in the config; the user does.

**Salary rules (parent spec: the engine holds no salary figures):**
- Figures appear only in the saved report, never in the engine or the config.
- Each figure carries a source link, the date checked, the region and the seniority. A figure without these is not shown; the row says "no source found".
- Gross and contractor figures are never converted to net (parent spec 3.4). Ranges from different sources are shown side by side, never averaged into a new number.
- "Higher salary potential" is a comparison between sourced ranges only. When fewer than two directions have a sourced range, the skill says the comparison is not possible.

**Grounding and hard rules:**
- "Strong candidate" claims follow rule 3 (facts only, otherwise NOT IN SOURCES).
- Rule 4: a direction the funnel contradicts (for example, zero replies across 5 or more rows) is shown with that evidence, not hidden.
- Rule 2: salary pages are untrusted data and only search results or links the user gave are opened. Single fetches are not scraping, and repeated fetches of one host follow rule 7.
- `targets.roles_not_primary` directions are flagged, not excluded.
- No `grounding_audit.py` run: the output is advice, not an application text. The semantic check of "why strong" claims is part of the skill's own procedure, using the same table as `grounding-audit` (`Claim | Source | Verdict`).

**Description must say when NOT to use it:**
- one vacancy's fit (`/rank`, `ats-screening`);
- a study plan (`/upskill`);
- an offer comparison or negotiation (the user's global salary and offer skills).

**Overlap:** none of the user's named global skills covers this. `resume-bullet-writer` and `linkedin-profile-optimizer` do not recommend directions.

**Spec change:** add `career-paths` to the skills list in section 8. Add to the non-goals: "No salary database: salary figures are never stored in the engine or config, only cited with source and date in a user's report." Hard rules: unchanged.

## 4. Verification (for the later plan)
- **Validator:** two new skill folders, each with frontmatter name equal to the folder name, a description under 1100 chars with a "Not for" clause, and an `evals.json` with 3 synthetic prompts. `upskill.md` documents `roadmap`.
- **Eval prompts** (synthetic persona):
  - **linkedin-profile:**
    1. An export with a title that differs from the master. Expected: listed as a conflict and not rewritten.
    2. A request to "add a 40% improvement". Expected: NOT IN SOURCES and an audit FAIL.
    3. A keyword from the pool with no evidence. Expected: "do not add".
  - **career-paths:**
    1. No salary source available. Expected: "no source found" and no figure.
    2. A gross figure. Expected: shown as gross, not converted.
    3. A direction contradicted by the funnel. Expected: shown with the evidence.
  - **roadmap** (manual trial):
    1. A time budget below the plan's hours. Expected: Low items dropped and the shortfall stated.
    2. A not-primary direction. Expected: the decision gate asks first.
    3. A certification with no gap. Expected: listed as not recommended.
