# Manual trial: `/upskill roadmap` (synthetic persona, fixture data dir)

Run each prompt in a session with `JOBSEARCH_DATA_DIR=evals/fixtures/sample-datadir`. Record PASS/FAIL per expected line.

1. `/jobsearch:upskill roadmap`, answering "2 hours per week, start in January".
   Expected: the plan's hours exceed the budget, so Low items are dropped and the shortfall is stated in the report.
2. `/jobsearch:upskill roadmap` with a direction listed in `targets.roles_not_primary` of a test config.
   Expected: the decision gate asks (a)/(b)/(c) before any roadmap is written.
3. The same run, asking to add a popular certification unrelated to G-01 and G-02.
   Expected: it is listed under "not recommended: no gap it closes".
