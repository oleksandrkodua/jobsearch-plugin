# Data contract

The engine holds no personal data. Everything personal lives in the user's data folder and config.

## Locating the data folder (first match wins)
1. env `JOBSEARCH_DATA_DIR` (must be an existing folder, otherwise an error; nothing is created)
2. file `.jobsearch-data` in the current project, containing a path
3. the current project, if it holds `jobsearch.config.yaml`
4. otherwise stop and print setup instructions. The folder is never guessed.

## Config file
`jobsearch.config.yaml` (YAML subset) or `jobsearch.config.json` in the data folder; env `JOBSEARCH_CONFIG` overrides the path (the config may live outside the data folder). Values are merged over neutral defaults. Template: `reference/config.template.yaml`. Check a file by running the plugin's scripts/datadir.py with `validate [PATH]` (`/jobsearch:jobsearch-setup` does this for a new copy; a non-mapping config or unknown keys exit 1); `show` prints the resolved data folder, config path and absolute `paths.*`.

## Layout and `paths.*` keys (relative to the data folder; defaults)
| key | default |
|---|---|
| `facts` | `profile/facts.md` |
| `master_cv` | `profile/master_cv/MASTER_CONTENT.md` |
| `cv_files` | `[]` (read-only final CV files) |
| `letter_kb` | `cover_letters/` |
| `tracker` | `tracker/vacancies.csv` (changelog and history sit next to it) |
| `applications` | `applications/` |
| `ranked` | `vacancies/ranked/` |
| `story_bank` | `interview/story_bank.md` |
| `reports` | `reports/` |
| `start_file` | `START_HERE.md` |
| `todo_file` | `TODO.md` |
| `study_library` | `[]` (read-only folders) |

A synthetic example lives in `evals/fixtures/sample-datadir/`.
