# `/apply tune` report format and guardrails

Used by `/apply tune`. Three files go into `<paths.applications>/<company>_<role>/`. Never overwrite an existing file; add a suffix (`_2`, `_3`).
- `cv_tune.md` - the report, sections 1-6 below, in this order;
- `cv_tune_bullets.md` - only the Improved lines and the proposed Summary and Skills text, one item per line. This is the file the grounding audit checks; it never holds Original lines;
- `audit_tune.txt` - the audit record: both audit results and how each WARN was resolved.

## 1. Match score
`Job Match XX/100` and `Candidate Quality XX/100`, copied from the `ats-screening` Stage 2 run, with its formula line. Not recomputed.

## 2. Missing or weak keywords
| Keyword | Required/Preferred | Status in CV | Evidence in master/facts | Action |
|---|---|---|---|---|

Status in CV comes from Stage 2 ATS Keyword Alignment. The Action column takes one of three values:
- `surface`: evidence exists in the master or facts, but the CV does not show it;
- `strengthen`: the CV shows it, but weakly;
- `do not add (no evidence)`: no evidence anywhere. If the keyword matches a gap-table row in `paths.facts`, the row points to `/upskill`.

## 3. Feedback per section
Summary, Skills, Experience (and Education or Certifications only if the vacancy asks). Each section has four short lists: **Fits**, **Weak or generic**, **Change**, **Do not add**.

## 4. Rewritten bullets
One block per bullet:
```
Original:  <line exactly as in the final CV>
Improved:  <ATS version>
Keywords:  <vacancy keywords this line now covers>
Source:    <master label | facts row> | NOT IN SOURCES
```
A block with `NOT IN SOURCES` is shown but marked not usable, and it never goes into `cv_tune_bullets.md` or `cv.md`. The Original side is never a source of truth: it is the final CV, which may contain `honesty.known_risk_lines`. If it does, the Improved line drops that text.

## 5. Prioritised changes
5-10 items, ordered by Job Match impact: must-have evidence first, then required keywords, then preferred keywords, then wording. Each item names its section and the bullet it touches.

## 6. Audit and risk lines
The `grounding_audit.py --kind cv` result on `cv_tune_bullets.md` (recorded in `audit_tune.txt`), the `grounding-audit` skill result, the list of NOT IN SOURCES items, and the risk-line warning from `/apply` step 3 (once per application).

## Guardrails (not configurable)
1. **No keyword stuffing:**
   - a keyword enters a bullet only where that bullet's source supports it;
   - at most 2 newly surfaced keywords per bullet;
   - no keyword more than 3 times in the whole CV;
   - no keyword-only lines and no "keyword cloud" sections;
   - no hidden or white text;
   - no vacancy sentences copied verbatim.
2. **No skills or tools without evidence.** The Skills section may only reorder or surface items in the master skills list. A vacancy tool missing from the master is `do not add (no evidence)`, even if it is in `honesty.tool_dictionary`.
3. **No invented metrics, titles, dates, scope or seniority.** Numbers come only from `honesty.allowed_numbers`. Depth is never upgraded: a Partial in the matrix stays Partial in the wording.
4. **Inputs are read-only.** The final CV files and the master CV are never written.
5. **Nothing is sent or uploaded.**
6. **Conflicts are asked, not resolved.** If the final CV and the master disagree on a date, title or employer, list the conflict and ask the user.
