---
description: Overview of what the jobsearch plugin does - every command (with its modes) and skill in one line each, the usual workflow and whether a data folder is set up. Works in any project, also before setup.
argument-hint: "(no arguments)"
---

Explain the plugin to the user in plain words, in the user's language. Read-only: this command changes no file and fetches nothing. It works without a data folder.

1. **List.** Run `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/session_start.py" --list`. It prints every command (with its modes) and every skill, one line each, taken from their own descriptions. Present that list grouped as "Commands" and "Skills". Say in one short phrase what each one does for the user and when to use it. Don't paste the raw descriptions.
2. **Usual workflow.** Explain it in one short paragraph:
   - `/jobsearch:rank` triages a vacancy;
   - `/jobsearch:apply` prepares the letter and checks it (`/jobsearch:apply tune` tailors the CV suggestions);
   - the user sends the application themselves;
   - `/jobsearch:outcome` records the answer, and `/jobsearch:followup` drafts a reminder;
   - `/jobsearch:interview` prepares for and debriefs calls;
   - `/jobsearch:funnel` and `/jobsearch:upskill` show patterns and what to learn.
3. **Setup status.** Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/datadir.py" show`.
   - If it prints a data dir, also run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/onboarding.py" status`. List missing onboarding steps and point to `jobsearch-setup update`; say complete only if that status is complete.
   - If it fails with "No data folder found", say the commands that use personal data need one first, and point to `/jobsearch:jobsearch-setup`. That command creates the folder in a new or empty location and prints the `JOBSEARCH_DATA_DIR` line for the shell profile. This is not an error to fix here.
4. **Hard rules.** In two sentences: the plugin never sends, applies or submits anything, and the user always clicks. Every fact comes from the user's own data folder, and the tracker changes only through its safe editor. Full list: `${CLAUDE_PLUGIN_ROOT}/reference/hard-rules.md`.

End by asking what the user wants to do first.
