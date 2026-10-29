---
description: Create a new jobsearch data folder (profile/, tracker header, config from the template, optional QA preset). Refuses any folder that is not new or empty.
argument-hint: (asks for the folder)
---

Interactive setup. Never guess a folder and never touch an existing data folder.

1. Ask the user where the data folder should be (an absolute path). Ask whether to use a preset: `none` (default) or `qa` (`${CLAUDE_PLUGIN_ROOT}/presets/qa/`).
2. Check the folder. It must not exist, or exist and be completely empty (`ls -A` prints nothing). If it has any content, stop and say so: setup never writes into an existing data folder; ask for another path.
3. Create the skeleton:
   - `mkdir -p "$DIR/profile" "$DIR/tracker"`
   - `$DIR/tracker/vacancies.csv` with only this header line:
     `id,company,position,url,status,status_confidence,proposed_status,needs_review,review_reason,applied_date,match_pct,domain,format_location,salary_notes,stage_xlsx,notes_xlsx,notes_csv,about_company,ask_comment,company_cell_extra,possible_duplicate_of,status_xlsx_raw,status_csv_raw,decision,override,sources`
   - `$DIR/jobsearch.config.yaml`: copy `${CLAUDE_PLUGIN_ROOT}/reference/config.template.yaml`, or for the `qa` preset copy `${CLAUDE_PLUGIN_ROOT}/presets/qa/preset.yaml`; with the preset also copy `${CLAUDE_PLUGIN_ROOT}/presets/qa/facts.example.md` to `$DIR/profile/facts.md`.
4. Validate the copy: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/datadir.py" validate "$DIR/jobsearch.config.yaml"` and report the result.
5. Print this line for the user to add to their own shell profile, and tell them to restart the shell or run it once:
   `export JOBSEARCH_DATA_DIR="<the folder>"`
6. Next steps for the user: fill `identity`, `targets` and `profile/facts.md`; personal values live only in that folder.

Rules that never bend: never edit a shell profile (`.zshrc`, `.bashrc`, etc.) or any other file outside the new folder; never overwrite or merge into an existing folder; never put personal values into the plugin repository.
