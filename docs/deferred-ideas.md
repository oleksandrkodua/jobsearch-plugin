# Deferred ideas

Ideas that were considered and set aside on purpose. Each entry says why it waits and what evidence brings it back. An entry is picked up only with that evidence in hand, through the usual spec addendum, plan and approval.

## D1. ATS pass of `/apply` in a subagent

Recorded 2026-11-04 (plugin audit, item 5 "context cost").

**Idea.** Run the `ats-screening` pass of `/apply` (and `/apply tune` step T3) in a subagent with a fresh context. The subagent gets the CV file, the vacancy text and the hard rules, and returns the scores, the requirement match matrix and the keyword alignment. The main flow then never loads the ~330 lines of ats-screening instructions or the extraction reasoning.

**Why deferred.**
- The saving is small: about 4-5k tokens against a 200k+ context. `/apply tune` needs the full matrix and keyword alignment back, so most of the output returns anyway.
- It adds a model call, re-sends the CV, vacancy and rules, and adds a hand-off where a missing file or rule produces a wrong score. That is harder to debug than one flow.
- The risk that motivated it, hard rules being forgotten late in a long context, is now partly covered in code. `hooks/guard_writes.py` enforces the tracker, CV, click and send rules regardless of context length.
- Splitting long skills into on-demand reference files was also checked and rejected. The humanizer pattern catalogue is needed on every rewrite, so it would load anyway, and the spec keeps that third-party skill unchanged.

**Come back when** a manual run of `/apply` or `/apply tune` on a real vacancy shows a rule being dropped late in the flow, for example:
- a metric outside `honesty.allowed_numbers` reaches a draft;
- the grounding audit step is skipped or its FAIL is ignored;
- `honesty.known_risk_lines` text is repeated;
- the ATS scores or matrix contradict the CV in a way a fresh read would catch.

Record the run (vacancy row number, step, what was dropped) in a parity or trial note without personal values. One such reproducible case is enough to reopen D1.

**If reopened.**
- Measure first: tokens of `/apply` with and without the subagent on the same vacancy.
- Pass inputs as files, not pasted text. The subagent writes its result to `<paths.applications>/<dir>/ats_pass.md`, and the main flow reads that file.
- Keep the guard hook as the backstop: it also fires for the subagent's tool calls.
