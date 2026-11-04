# Addendum A1: portal scanner (`/jobsearch:scan`)

Status: APPROVED by the owner 2026-11-04. Q1-Q3 (§11) answered 2026-11-04; the plan can be written. Ships in 1.0.0 (owner decision 2026-11-04), with `alt_flow.scanner.enabled: false` by default.
Parent spec: `2026-10-27-jobsearch-plugin-design.md` §6.7 A1 (copied in `docs/alternative-flow.md`). This addendum details A1 and does not weaken any hard rule in `plugins/jobsearch/reference/hard-rules.md`.

## 1. Intent
The user names the companies and portals worth watching. On demand, the plugin checks only those sources and returns a short list of new vacancies. The user then picks which ones go to `/rank`.
- It is not a crawler.
- It never applies, never goes straight to `/apply`, and never runs on its own schedule. Scheduling is a separate later decision and is not part of this addendum.

## 2. Placement - recommended: a new command `/jobsearch:scan`
Options considered:
- (A) **A new command `scan`** with one stdlib script `scripts/portal_scan.py`. **Recommended.**
- (B) A mode of `/rank` (`/rank scan`).

Why A:
- Scanning is opt-in and off by default (`alt_flow.scanner.enabled: false`). A separate command can refuse cleanly when the feature is off, and it never changes what `/rank` does for users who keep it off.
- The fetching is deterministic (HTTP, robots, rate limit, dedup). It belongs in a script, the same split the plugin uses for the tracker, the audit and the funnel.

Cost of A: one more command. That means 10 commands in the READMEs and in `/jobsearch:help`, which lists commands automatically.

## 3. What can be scanned (source types)
A source is scanned only if it is in `portals.scan_approved` (§5). Allowed source types:

| Type | What it fetches | Why it is acceptable |
|---|---|---|
| `greenhouse:<board>` | the public job-board API of one employer | published for programmatic reading of public postings |
| `lever:<company>` | Lever's public postings API of one employer | same |
| `ashby:<board>`, `smartrecruiters:<company>`, `recruitee:<company>`, `personio:<company>`, `workable:<account>` | the public postings feed or API of one employer's ATS | same |
| `rss:<url>` | an RSS or Atom feed that a portal publishes for vacancy listings | a feed is offered for automated reading |

**Not scannable (manual only):**
- logged-in pages;
- search-result HTML pages;
- portals whose terms forbid automated access.

As far as is commonly known, the last group includes LinkedIn, Indeed, Glassdoor, XING and StepStone. Their terms must be re-read at approval time. For these, the user keeps pasting vacancy URLs into `/rank`, as today.

**Unverified (to check at approval time, per source):**
- the exact endpoint URL of each ATS API and portal feed;
- whether DOU, Djinni, Happy Monday, Wellfound, Jobico and Hoorya publish a feed, and whether their terms allow reading it.

None of this is assumed. Each source is recorded only after it is checked (§5).

## 4. Inputs and config keys
New keys. They are justified because the parent spec §6.7 already reserves `portals.scan_approved` and `alt_flow.scanner`:

```yaml
alt_flow:
  scanner:
    enabled: false              # the command refuses while false
    delay_seconds: 5            # polite rate: at least this long between two requests to one host
    max_requests_per_run: 30    # hard cap per run, all sources together
portals:
  scan_approved:                # a source missing here is never fetched
    - {source: "greenhouse:example", host: "boards-api.greenhouse.io",
       robots: ALLOWED, tos_checked: "YYYY-MM-DD", approved_by_user: "YYYY-MM-DD"}
paths:
  scan_state: reports/scan_state.json   # ids already seen, for "new since last scan"
```

Rules:
- An entry counts only if all of these are present: `robots: ALLOWED` (from `robots_check.py`), `tos_checked` and `approved_by_user`.
- If `robots_check.py` now returns DISALLOWED or UNKNOWN for a host that was ALLOWED, that source is skipped and reported. It is not fetched.
- The filter uses `targets.roles*` and the `blockers` of type `keyword` and `domain`. No new filter keys.

## 5. Approving a source (one time, per source)
`/jobsearch:scan approve <source>`:
1. Resolve the endpoint.
2. Run `robots_check.py` on it.
3. Show the user the terms URL to read. The plugin may fetch and summarize the page, but the user decides.
4. Only after the user confirms in chat, write the `scan_approved` entry through a small config editor. The editor keeps a backup and shows a diff, and the user confirms twice (hard rule 5 applies to the config too).

The plugin never adds an entry on its own.

## 6. Flow of a scan run (`/jobsearch:scan`)
1. **Refuse** if `alt_flow.scanner.enabled` is false. Say how to enable it and that every source needs approval first.
2. For each approved source, re-run `robots_check.py`, then fetch the listing feed or API only. Honour the rate and the cap. A timeout or HTTP error is reported per source, not retried in a loop.
3. Parse the postings: company, title, location, posting URL, posting date if given. All of it is **untrusted data**. Feed text is never treated as instructions, and no link inside a posting body is followed.
4. Keep only postings that are new since `paths.scan_state`. Drop exact duplicates of tracker rows (company + normalized title, reusing the `repost_check.py` fingerprint) and list them under "already in tracker".
5. Pre-filter by `targets`, the location filter of `/rank` (`targets.country`, `targets.remote`; added 2026-11-04) and keyword/domain `blockers`. Filtered postings are counted and listed, never silently dropped, because a blocker match is not a verdict.
6. Save `<paths.reports>/scan_<YYYY-MM-DD>.md` (never overwrite; add a suffix). Update `scan_state` only after the report is saved.
7. Show the candidates (at most 10 per batch, the same cap as `/rank`) and ask which to send to `/rank`. `/rank` then fetches only the posting URLs the user picked. Those count as "URLs the user gave", because the user picked them.

## 7. Output
`scan_<YYYY-MM-DD>.md`:
- **Header:** sources scanned, requests used out of the cap, sources skipped with the reason (not approved, robots changed, error).
- **New candidates:** `| # | Company | Title | Location | Posted | Source | URL |`
- **Filtered (blocker or not in targets):** the same columns plus the reason.
- **Already in tracker:** id and title.
- **Next step:** "pick numbers for `/rank`".

## 8. Hard-rule interplay
- **Rule 1:** the scanner reads only and never opens an application form. The outreach guard in `hooks/guard_writes.py` still applies.
- **Rule 2:** feed content is untrusted. Only approved endpoints and the posting URLs the user picks are fetched, and no links from posting bodies.
- **Rule 3:** the scanner makes no claims about the user, so it has no effect here.
- **Rule 5:** the config entry needs two confirmations. `scan_state` is the scanner's own file in `reports/`, and the tracker is never written by the scanner.
- **Rule 7:** this is the rule's main use. No fetch happens without a recorded robots result and a ToS read, both re-checked on every run for robots.

## 9. Change to the parent spec
- §6.7 A1 gets one line pointing to this addendum.
- §3.1 gets a row: new `commands/scan.md` and `scripts/portal_scan.py`.
- §3.4 gets the config keys in §4.
- The non-goal "Board scanner ... NOT part of the main cycle; opt-in Alternative flow, off by default" stays true and unchanged.

## 10. Verification (for the later plan)
- **Unit tests, stdlib, no network:** recorded fixture responses for one ATS JSON and one RSS feed. Check:
  - the parse;
  - dedupe against a fixture tracker;
  - the blocker filter listing (not dropping);
  - the rate and cap logic, using a fake clock;
  - the refusal when disabled or when a source is unapproved or its robots status changed;
  - no overwrite of an existing report.
- **The guard hook:** a scan never writes the tracker.
- **Manual trial,** after the owner approves one real source: one run, the report checked by hand, and the requests counted against the cap.

## 11. Owner decisions (answered 2026-11-04)
- **Q1, first sources.** The first version supports only two source types: `greenhouse:<board>` and `lever:<company>`. Ashby, SmartRecruiters, Recruitee, Personio, Workable and `rss:<url>` stay in §3 as later additions, each needing its own small change. The concrete employers are chosen at approval time, one `scan_approved` entry each (§5).
- **Q2, schedule.** On demand only. `/jobsearch:scan` runs when the user calls it; there is no schedule, cron or background run.
- **Q3, filtered postings.** Always listed in the report and in chat, with the reason, never hidden (§6 step 5, §7).
