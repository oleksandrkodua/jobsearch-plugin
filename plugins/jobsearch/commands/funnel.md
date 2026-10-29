---
description: Funnel and patterns report from the tracker - stages, reply rate by host class and role type, rejection reasons by gap tag, median days to first reply. Read-only.
argument-hint: (no arguments)
---

Run the report (it reads the tracker and CHANGELOG.csv from the data dir; `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/datadir.py" show` prints where they are):

`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/funnel_report.py"`

It prints the report and saves it to `paths.reports/funnel_<date>.md`. Optional flags: `--config PATH`, `--out PATH`, `--today YYYY-MM-DD`.

Rules that never bend: this command never changes the tracker or the CHANGELOG. The only thing it writes is the report file in the reports folder. Show the numbers as the script printed them; do not round up, re-derive or invent any figure.

Small-sample rule: a group with fewer than 5 applications is marked "too few to conclude". Report such a group as an observation only. Never draw a conclusion, a ranking or a recommendation from it, and say so in your summary.

If `portals.job_portals` is empty, the report says no row is classed as a job portal. Tell the user that; do not guess portals for them.

After the report, give the user a short read-out (what the funnel shows, which groups are too small to judge) and suggest at most 3 concrete actions, each tied to a number in the report that is not marked "too few to conclude" (for example: tag gaps in the notes as `gap:<tag>` so rejection reasons become visible; favour the host class or role type with a clearly higher reply rate; follow up on applications with no reply). If no group is large enough, suggest only how to collect more data. Do not change statuses; if the user wants a change, use `tracker_edit.py` on their request.
