---
description: List applications waiting for an answer for N days and draft a follow-up (draft only, never sent).
argument-hint: [days; default from followup.default_days]
---

Read `${CLAUDE_PLUGIN_ROOT}/reference/hard-rules.md`, then the user's config (data dir; run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/datadir.py" show` to print the data dir, the config path and the absolute `paths.*`). Days: $ARGUMENTS (default `followup.default_days`).

1. Read the tracker (`paths.tracker`). Candidates: status APPLIED or ACTIVE with `applied_date` (or last known event) at least N days before today, and no row in the changelog next to the tracker newer than that. Rows without a date are listed separately as "date unknown", never assumed overdue.
2. Print a table: id, company, position, applied date, days waiting, number of follow-ups already sent (look in `<paths.applications>/<dir>/outcome.md`; if absent, say "unknown"). The normal first-answer window is `followup.window_days` (days); call out ACTIVE rows first.
3. Maximum `followup.max_followups` follow-ups per vacancy. If that many are recorded, propose NO_RESPONSE as a question to the user, do not change the status yourself.
4. For rows the user picks, write a short draft in the language of the previous correspondence: one question, no pressure, no new claims. Facts only from the data dir profile (`paths.facts`). Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/grounding_audit.py" <draft> --kind letter --no-length`, and fix FAILs.
5. Save drafts under `<paths.applications>/<dir>/followup_N.md`. Say "not sent". After the user sends it, they tell you the date and you record it in `outcome.md`. A status change goes only through `tracker_edit.py` on the user's request.
