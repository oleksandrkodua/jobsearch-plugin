# Addendum: CV tailoring mode (`/apply tune`)

Status: APPROVED by the owner 2026-10-28. Plan and code start after the main plan (Tasks 0-14) is finished.
Parent spec: `2026-10-27-jobsearch-plugin-design.md`. Drafted before the parity-trial commit at the owner's request; implementation starts only after the main plan (Tasks 0-14) is finished.

## 1. Intent
The user gets ATS-oriented feedback on the CV for one vacancy. Per section it shows what fits, what is weak or generic, what to change and what not to add. It also lists the keywords from the JD that are missing or weak, and proposes rewritten bullets built only from real experience. The mode is not a CV builder: the output is suggestions, plus a targeted copy only when the user asks for one.

## 2. Placement - recommended: `/apply tune <vacancy>`
Options considered:
- (A) **A sub-mode of `/apply`** (`/apply tune <vacancy URL or text> [company]`). **Recommended.**
- (B) A separate `cv-tailor` skill.

Why A:
- `/apply` already owns everything this mode needs:
  - Gate 0 (rank first, stop on duplicate or blocker);
  - the application folder;
  - the targeted `cv.md` rule (step 3) and the `honesty.known_risk_lines` warning;
  - the mandatory `grounding_audit.py --kind cv` run (step 7).
  A skill would have to duplicate these steps or call back into `/apply`.
- Hard rule 6 ("targeted copies only when asked") is already enforced in one place, step 3 of `/apply`. A second entry point for building CV copies would be a second place to get it wrong.
- ats-screening Stage 2 already tells the user that CV optimization "is a separate task". That pointer becomes `/apply tune`, so the user meets it in the flow they already use.

Cost of A: commands have no `evals.json`. Mitigation in section 9: three synthetic prompts are kept as a manual trial checklist, and the validator checks the command text.

## 3. Inputs
| Input | Source | Access |
|---|---|---|
| JD | URL or pasted text from the user (hard rule 2: data, only the given URL is fetched) | read |
| Ranked file | `paths.ranked` (Gate 0 creates it if missing) | read |
| Final CV ("Original" lines) | one file of `paths.cv_files`; if there are several, ask which one | **read-only** (hard rule 6) |
| Master CV labels | `paths.master_cv` | read-only |
| Facts and gap table | `paths.facts` | read-only |
| Honesty limits | `honesty.*` (`allowed_numbers`, `tool_dictionary`, `restricted_tools`, `known_risk_lines`) | config |

There are no new config keys. If `paths.cv_files` is empty, the "Original" lines are the master CV lines and the report says so.

## 4. Reuse of ats-screening Stage 2
The mode does not re-implement matching. It runs the `ats-screening` skill in Stage 2 on the chosen final CV and the JD, then consumes these parts of its output:
- **Requirement Match Matrix** (Strong / Partial / Mentioned only / Not stated / Contradicted): this decides which bullets are worth rewriting.
- **ATS Keyword Alignment** (required vs preferred): this is the source of the "missing or weak keywords" list.
- **Job Match** and **Candidate Quality**: these are shown as the match score, unchanged.

Tune-only work, which ats-screening is not allowed to do:
- feedback per section;
- bullet rewrites;
- deciding, for each missing keyword, whether evidence exists in the master or facts.

Small edit to ats-screening Stage 2: the "separate task" sentence names `/apply tune`. Nothing else in the skill changes, and it stays analysis-only.

## 5. Output
Two files go into `<paths.applications>/<company>_<role>/`:
- `cv_tune.md`, the report (format below);
- `cv_tune_bullets.md`, only the Improved lines and the proposed Summary and Skills text, one item per line. This is the file the audit checks.

`cv_tune.md` contains, in order:
1. **Match score:** `Job Match XX/100`, `Candidate Quality XX/100` (from Stage 2), with the formula line.
2. **Missing or weak keywords:**

   | Keyword | Required/Preferred | Status in CV | Evidence in master/facts | Action |
   |---|---|---|---|---|

   Action is one of: `surface` (evidence exists, the CV does not show it), `strengthen` (shown, but weak), `do not add (no evidence)`. A `do not add` row with a gap-table match points to `/upskill`.
3. **Feedback per section** (Summary, Skills, Experience; Education/Certifications only if the JD asks). Each section has four short lists: *Fits* / *Weak or generic* / *Change* / *Do not add*.
4. **Rewritten bullets.** One block per bullet:
   ```
   Original:  <line exactly as in the final CV>
   Improved:  <ATS version>
   Keywords:  <JD keywords this line now covers>
   Source:    <master label | facts row> | NOT IN SOURCES
   ```
   A rewrite with `NOT IN SOURCES` is shown, but marked not usable; it never goes into `cv.md`.
5. **Prioritised changes:** 5-10 items, ordered by Job Match impact (must-have evidence first, then required keywords, then preferred keywords, then wording). Each item names its section and the bullet it touches.
6. **Audit result** and the **risk-line warning** (`/apply` step 3, once per application).

**Targeted copy:** `cv.md` is built only when the user asks after reading the report. It is assembled from the master labels plus the accepted Improved lines, following the existing `/apply` step 3 rules (reorder and emphasise, every sentence keeps its label, no PDF before the user confirms). Job Match may be re-run on `cv.md`, labelled "projection on the tuned copy, not a guarantee".

## 6. Grounding
- Every Improved line traces to a master-CV label or a facts row, otherwise it is `NOT IN SOURCES`. The "Original" side is never a source of truth: it is the final CV, which may contain `known_risk_lines`.
- Mechanical check: `python3 scripts/grounding_audit.py <dir>/cv_tune_bullets.md --kind cv`. If `cv.md` exists, the same check runs on `cv.md` too. The existing CV rules then apply as they are:
  - numbers only from `honesty.allowed_numbers`;
  - year claims only from `honesty.allowed_year_claims`;
  - restricted tools are forbidden on a CV;
  - tools outside the master skills are WARNed.
- Semantic check: the `grounding-audit` skill runs on the same file. Its result goes into `audit.txt`, exactly as in `/apply` step 7. A report with an open FAIL is not handed over.
- An Improved line must never repeat `honesty.known_risk_lines` text. If the Original contains it, the rewrite drops it.

## 7. Change to the parent spec
Non-goal, current text: "No new CV builder. CV files are the user's data; the engine only analyzes and audits them."
Proposed text: "No new CV builder. CV files are the user's data; the engine analyzes and audits them and, in `/apply tune`, suggests grounded edits. It builds a targeted copy (`cv.md`) only when the user asks, and it never edits the files in `paths.cv_files` or the master CV."
Also add one row to section 3.1: `commands/apply.md` gains a `tune` mode (this addendum). Hard rule 6 is unchanged.

## 8. Guardrails
1. **No keyword stuffing:**
   - a keyword enters a bullet only where that bullet's source supports it;
   - at most 2 newly surfaced keywords per bullet;
   - no keyword more than 3 times in the whole CV;
   - no keyword-only lines or "keyword cloud" sections;
   - no hidden or white text;
   - no JD sentences copied verbatim.
2. **No skills or tools without evidence.** The Skills section may only reorder or surface items in the master skills list. A JD tool that is missing from the master is `do not add (no evidence)`, even if it is in `honesty.tool_dictionary`.
3. **No invented metrics, titles, dates, scope or seniority.** Depth is never upgraded: a Partial in the matrix stays Partial in the wording.
4. **Inputs are read-only.** The final CV files and the master CV are never written.
5. **Nothing is sent or uploaded** (hard rule 1).
6. **Conflicts are asked, not resolved** (hard rule 4). If the final CV and the master disagree on a date, title or employer, list the conflict and ask.

## 9. Verification (for the later plan)
- **Validator:** `apply.md` documents the `tune` mode, names `cv_tune.md` and `cv_tune_bullets.md`, and references only scripts that exist.
- **Manual trial checklist** with the synthetic persona (Jordan Example, Example Corp):
  1. A JD with one must-have the persona has. Expected: `surface`, with a label.
  2. A JD with a tool absent from the master. Expected: `do not add`, and no rewrite uses it.
  3. A request to "add 30% faster" with no allowed number. Expected: the audit FAILs and the line is marked NOT IN SOURCES.
- **Unit test:** `grounding_audit.py --kind cv` on a fixture `cv_tune_bullets.md` with one invented percentage and one tool from the fixture's `honesty.tool_dictionary` that is absent from the master skills gives exactly one FAIL and one WARN. The script is not changed.
