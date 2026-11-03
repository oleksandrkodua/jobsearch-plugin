# Manual trial: `/apply tune` (synthetic persona, fixture data dir)

Run each prompt in a session with `JOBSEARCH_DATA_DIR=evals/fixtures/sample-datadir`. Record PASS/FAIL per expected line.

1. `/jobsearch:apply tune` with a pasted vacancy for a Senior Backend Engineer that requires "REST APIs" and "CI/CD".
   Expected: both keywords `surface` or `strengthen`, each with a master label as Source; no NOT IN SOURCES rewrite reaches `cv_tune_bullets.md`.
2. The same, with a vacancy that requires "Kubernetes".
   Expected: Kubernetes is `do not add (no evidence)`, and no Improved line uses it.
3. After the report, ask: "add that I cut response time by 30%".
   Expected: the audit FAILs on `30%`, the line is marked NOT IN SOURCES, and the report is not handed over with the FAIL open.
